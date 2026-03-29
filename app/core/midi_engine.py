"""
MIDI Engine -- core playback, file I/O, and editing operations.

Provides real-time MIDI playback via a background QThread, file load/save
through mido, and a complete set of note/track manipulation helpers used
by the rest of the workstation.
"""
from __future__ import annotations

import copy
import logging
import threading
import time
from typing import Optional

import mido
import mido.backends.rtmidi  # noqa: F401  ensure backend is registered

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from core.models import Note, Track, ProjectState, TimeSignature, TICKS_PER_BEAT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Playback thread
# ---------------------------------------------------------------------------

class PlaybackThread(QThread):
    """Background thread that drives real-time MIDI playback.

    Emits *position_changed* approximately every 20 ms with the current
    playback tick.  Sends note_on / note_off messages through an optional
    mido output port.
    """

    position_changed = pyqtSignal(int)   # current tick
    playback_finished = pyqtSignal()

    # Internal resolution for the scheduling loop (seconds).
    _POLL_INTERVAL = 0.005

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()

        # State that the engine sets before calling start()
        self._project: Optional[ProjectState] = None
        self._output_port: Optional[mido.ports.BaseOutput] = None
        self._audio_engine = None  # FluidSynth AudioEngine

        # Transport controls (guarded by _lock)
        self._playing = False
        self._stop_requested = False
        self._seek_tick: Optional[int] = None

        # Position bookkeeping
        self._current_tick: int = 0

    # -- public helpers (called from main thread) ---------------------------

    def configure(
        self,
        project: ProjectState,
        output_port: Optional[mido.ports.BaseOutput],
        start_tick: int = 0,
        audio_engine=None,
    ) -> None:
        """Set up state before starting the thread."""
        self._project = project
        self._output_port = output_port
        self._audio_engine = audio_engine
        self._current_tick = start_tick

    def request_stop(self) -> None:
        with self._lock:
            self._stop_requested = True

    def request_seek(self, tick: int) -> None:
        with self._lock:
            self._seek_tick = max(0, tick)

    def pause(self) -> None:
        with self._lock:
            self._playing = False

    def unpause(self) -> None:
        with self._lock:
            self._playing = True

    @property
    def current_tick(self) -> int:
        return self._current_tick

    # -- thread body --------------------------------------------------------

    def run(self) -> None:  # noqa: C901  (complexity acceptable for a scheduler)
        if self._project is None:
            return

        project = self._project
        self._playing = True
        self._stop_requested = False

        # Pre-sort every track's notes for efficient scanning.
        track_notes: list[list[Note]] = []
        for trk in project.tracks:
            sorted_notes = sorted(trk.notes, key=lambda n: n.start_tick)
            track_notes.append(sorted_notes)

        # Track which notes are currently sounding so we can send note_off.
        active_notes: set[tuple[int, int]] = set()  # (pitch, channel)

        last_emit_time = 0.0
        wall_start = time.perf_counter()
        tick_start = self._current_tick

        try:
            while True:
                # --- check control flags ---
                with self._lock:
                    if self._stop_requested:
                        break

                    if self._seek_tick is not None:
                        self._all_notes_off(active_notes)
                        active_notes.clear()
                        tick_start = self._seek_tick
                        self._current_tick = self._seek_tick
                        wall_start = time.perf_counter()
                        self._seek_tick = None

                    playing = self._playing

                if not playing:
                    # Paused -- keep the thread alive but idle.
                    time.sleep(self._POLL_INTERVAL)
                    wall_start = time.perf_counter()
                    tick_start = self._current_tick
                    continue

                # --- compute current tick from wall clock ---
                elapsed = time.perf_counter() - wall_start
                ticks_per_second = (project.bpm / 60.0) * project.ticks_per_beat
                self._current_tick = tick_start + int(elapsed * ticks_per_second)

                # --- loop handling ---
                if project.loop_enabled and self._current_tick >= project.loop_end:
                    self._all_notes_off(active_notes)
                    active_notes.clear()
                    tick_start = project.loop_start
                    self._current_tick = project.loop_start
                    wall_start = time.perf_counter()

                # --- end of project ---
                if self._current_tick >= project.total_ticks and not project.loop_enabled:
                    self._all_notes_off(active_notes)
                    break

                # --- emit position signal (throttled to ~20 ms) ---
                now = time.perf_counter()
                if now - last_emit_time >= 0.020:
                    self.position_changed.emit(self._current_tick)
                    last_emit_time = now

                # --- send MIDI events ---
                cur_tick = self._current_tick
                for trk_idx, trk in enumerate(project.tracks):
                    if trk.muted:
                        continue
                    # Check solo: if any track is soloed, only play soloed tracks.
                    if any(t.solo for t in project.tracks) and not trk.solo:
                        continue

                    if trk_idx >= len(track_notes):
                        continue
                    for note in track_notes[trk_idx]:
                        if note.start_tick > cur_tick:
                            break  # notes are sorted; no point scanning further
                        # note_on
                        key = (note.pitch, note.channel)
                        if note.start_tick <= cur_tick < note.end_tick and key not in active_notes:
                            self._send_note_on(note)
                            active_notes.add(key)
                        # note_off
                        if cur_tick >= note.end_tick and key in active_notes:
                            self._send_note_off(note)
                            active_notes.discard(key)

                time.sleep(self._POLL_INTERVAL)

        except Exception:
            logger.exception("Playback thread encountered an error")
        finally:
            self._all_notes_off(active_notes)
            self._playing = False
            self.playback_finished.emit()

    # -- MIDI output helpers ------------------------------------------------

    def _send_note_on(self, note: Note) -> None:
        # FluidSynth AudioEngine (우선)
        if self._audio_engine is not None and self._audio_engine.available:
            try:
                self._audio_engine.note_on(note.channel, note.pitch, note.velocity)
            except Exception:
                logger.debug("AudioEngine note_on failed pitch=%d", note.pitch)
            return
        # mido output port (폴백)
        if self._output_port is not None and not self._output_port.closed:
            try:
                msg = mido.Message("note_on", note=note.pitch, velocity=note.velocity, channel=note.channel)
                self._output_port.send(msg)
            except Exception:
                logger.debug("Failed to send note_on pitch=%d", note.pitch)

    def _send_note_off(self, note: Note) -> None:
        # FluidSynth AudioEngine (우선)
        if self._audio_engine is not None and self._audio_engine.available:
            try:
                self._audio_engine.note_off(note.channel, note.pitch)
            except Exception:
                logger.debug("AudioEngine note_off failed pitch=%d", note.pitch)
            return
        # mido output port (폴백)
        if self._output_port is not None and not self._output_port.closed:
            try:
                msg = mido.Message("note_off", note=note.pitch, velocity=0, channel=note.channel)
                self._output_port.send(msg)
            except Exception:
                logger.debug("Failed to send note_off pitch=%d", note.pitch)

    def _all_notes_off(self, active: set[tuple[int, int]]) -> None:
        """Silence every currently-sounding note."""
        # FluidSynth
        if self._audio_engine is not None and self._audio_engine.available:
            try:
                self._audio_engine.all_notes_off()
            except Exception:
                pass
            active.clear()
            return
        # mido
        if self._output_port is not None and not self._output_port.closed:
            for pitch, channel in list(active):
                try:
                    msg = mido.Message("note_off", note=pitch, velocity=0, channel=channel)
                    self._output_port.send(msg)
                except Exception:
                    pass
        active.clear()


# ---------------------------------------------------------------------------
# MIDI Engine
# ---------------------------------------------------------------------------

class MidiEngine(QObject):
    """Central MIDI engine used by the workstation.

    Responsibilities:
      - Load / save MIDI files via *mido*
      - Drive real-time playback through :class:`PlaybackThread`
      - Provide track and note editing helpers
      - Copy / paste of note selections
      - Quantization
    """

    # Signals
    position_changed = pyqtSignal(int)
    playback_state_changed = pyqtSignal(str)  # "playing" | "paused" | "stopped"
    project_loaded = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._project = ProjectState()
        self._playback_thread: Optional[PlaybackThread] = None
        self._output_port: Optional[mido.ports.BaseOutput] = None
        self._audio_engine = None  # FluidSynth AudioEngine 연동
        self._clipboard: list[Note] = []
        self._state: str = "stopped"  # playing | paused | stopped

    # -- properties ---------------------------------------------------------

    @property
    def project(self) -> ProjectState:
        return self._project

    @project.setter
    def project(self, value: ProjectState) -> None:
        self.stop()
        self._project = value

    @property
    def state(self) -> str:
        return self._state

    @property
    def current_tick(self) -> int:
        if self._playback_thread is not None and self._playback_thread.isRunning():
            return self._playback_thread.current_tick
        return 0

    # -----------------------------------------------------------------------
    # MIDI port management
    # -----------------------------------------------------------------------

    @staticmethod
    def available_output_ports() -> list[str]:
        """Return names of MIDI output ports visible to the system."""
        try:
            return mido.get_output_names()
        except Exception:
            logger.warning("Could not enumerate MIDI output ports")
            return []

    def set_audio_engine(self, audio_engine) -> None:
        """FluidSynth AudioEngine 연결 — Play 시 가상악기로 소리 출력."""
        self._audio_engine = audio_engine
        logger.info("AudioEngine connected to MidiEngine")

    def open_output_port(self, port_name: str | None = None) -> bool:
        """Open *port_name* (or the default port) for MIDI output."""
        self.close_output_port()
        try:
            if port_name:
                self._output_port = mido.open_output(port_name)
            else:
                self._output_port = mido.open_output()
            logger.info("Opened MIDI output: %s", self._output_port.name)
            return True
        except Exception:
            logger.warning("Could not open MIDI output port %r", port_name)
            self._output_port = None
            return False

    def close_output_port(self) -> None:
        if self._output_port is not None and not self._output_port.closed:
            try:
                self._output_port.close()
            except Exception:
                pass
            self._output_port = None

    # -----------------------------------------------------------------------
    # File I/O
    # -----------------------------------------------------------------------

    def load_midi_file(self, path: str) -> ProjectState:
        """Parse a Standard MIDI File and return a new :class:`ProjectState`."""
        mid = mido.MidiFile(path)
        project = ProjectState(
            name=path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1],
            file_path=path,
            ticks_per_beat=mid.ticks_per_beat,
        )

        # First pass: extract tempo & time-signature from all tracks.
        for mido_track in mid.tracks:
            abs_tick = 0
            for msg in mido_track:
                abs_tick += msg.time
                if msg.type == "set_tempo":
                    project.bpm = round(mido.tempo2bpm(msg.tempo), 2)
                elif msg.type == "time_signature":
                    project.time_signature = TimeSignature(
                        numerator=msg.numerator,
                        denominator=msg.denominator,
                    )

        # Second pass: build Track objects from note events.
        for trk_idx, mido_track in enumerate(mid.tracks):
            track = Track(
                name=mido_track.name or f"Track {trk_idx + 1}",
                channel=0,
            )
            # Assign a colour from the palette.
            from core.models import TRACK_COLORS
            track.color = TRACK_COLORS[trk_idx % len(TRACK_COLORS)]

            abs_tick = 0
            pending: dict[tuple[int, int], Note] = {}  # (pitch, channel) -> Note

            for msg in mido_track:
                abs_tick += msg.time

                if msg.type == "note_on" and msg.velocity > 0:
                    key = (msg.note, msg.channel)
                    # Close any prior note with the same key (running status).
                    if key in pending:
                        pending[key].duration_ticks = max(1, abs_tick - pending[key].start_tick)
                        track.notes.append(pending[key])
                    pending[key] = Note(
                        pitch=msg.note,
                        velocity=msg.velocity,
                        start_tick=abs_tick,
                        duration_ticks=0,
                        channel=msg.channel,
                    )
                    track.channel = msg.channel

                elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                    key = (msg.note, msg.channel)
                    if key in pending:
                        pending[key].duration_ticks = max(1, abs_tick - pending[key].start_tick)
                        track.notes.append(pending[key])
                        del pending[key]

                elif msg.type == "program_change":
                    track.instrument = msg.program

            # Flush any notes that were never closed.
            for note in pending.values():
                if note.duration_ticks <= 0:
                    note.duration_ticks = project.ticks_per_beat
                track.notes.append(note)

            track.notes.sort(key=lambda n: n.start_tick)

            # Only keep tracks that actually contain notes.
            if track.notes:
                project.tracks.append(track)

        # Ensure at least one track exists.
        if not project.tracks:
            project.tracks.append(Track(name="Track 1"))

        # Set a sensible loop range (first 4 bars).
        beats_per_bar = project.time_signature.numerator
        project.loop_end = project.ticks_per_beat * beats_per_bar * 4

        self._project = project
        self.project_loaded.emit()
        return project

    def save_midi_file(self, path: str, project: Optional[ProjectState] = None) -> None:
        """Export *project* (or the current project) to a Standard MIDI File."""
        proj = project or self._project
        mid = mido.MidiFile(ticks_per_beat=proj.ticks_per_beat)

        # -- Tempo / meta track --
        meta_track = mido.MidiTrack()
        mid.tracks.append(meta_track)
        meta_track.append(
            mido.MetaMessage(
                "time_signature",
                numerator=proj.time_signature.numerator,
                denominator=proj.time_signature.denominator,
                time=0,
            )
        )
        meta_track.append(
            mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(proj.bpm), time=0)
        )
        meta_track.append(mido.MetaMessage("track_name", name=proj.name, time=0))
        meta_track.append(mido.MetaMessage("end_of_track", time=0))

        # -- Note tracks --
        for trk in proj.tracks:
            mido_track = mido.MidiTrack()
            mid.tracks.append(mido_track)
            mido_track.append(mido.MetaMessage("track_name", name=trk.name, time=0))

            if trk.instrument > 0:
                mido_track.append(
                    mido.Message("program_change", program=trk.instrument, channel=trk.channel, time=0)
                )

            # Build a flat event list sorted by absolute tick.
            events: list[tuple[int, mido.Message]] = []
            for note in trk.notes:
                events.append((
                    note.start_tick,
                    mido.Message("note_on", note=note.pitch, velocity=note.velocity, channel=note.channel),
                ))
                events.append((
                    note.end_tick,
                    mido.Message("note_off", note=note.pitch, velocity=0, channel=note.channel),
                ))

            events.sort(key=lambda e: e[0])

            # Convert absolute ticks to delta times.
            last_tick = 0
            for abs_tick, msg in events:
                delta = abs_tick - last_tick
                msg.time = max(0, delta)
                mido_track.append(msg)
                last_tick = abs_tick

            mido_track.append(mido.MetaMessage("end_of_track", time=0))

        mid.save(path)
        proj.file_path = path
        logger.info("Saved MIDI file: %s", path)

    # -----------------------------------------------------------------------
    # Transport controls
    # -----------------------------------------------------------------------

    @pyqtSlot()
    def play(self, start_tick: int = 0) -> None:
        """Begin or resume playback."""
        if self._state == "paused" and self._playback_thread is not None:
            self._playback_thread.unpause()
            self._set_state("playing")
            return

        self.stop()

        # AudioEngine에 각 트랙의 악기/볼륨/팬 설정
        if self._audio_engine is not None and self._audio_engine.available:
            for trk in self._project.tracks:
                self._audio_engine.program_change(trk.channel, trk.instrument)
                self._audio_engine.set_channel_volume(trk.channel, trk.volume)
                self._audio_engine.set_channel_pan(trk.channel, trk.pan)

        thread = PlaybackThread(self)
        thread.configure(self._project, self._output_port, start_tick, self._audio_engine)
        thread.position_changed.connect(self.position_changed)
        thread.playback_finished.connect(self._on_playback_finished)
        self._playback_thread = thread

        self._set_state("playing")
        thread.start()

    @pyqtSlot()
    def pause(self) -> None:
        if self._state != "playing" or self._playback_thread is None:
            return
        self._playback_thread.pause()
        self._set_state("paused")

    @pyqtSlot()
    def stop(self) -> None:
        if self._playback_thread is not None:
            self._playback_thread.request_stop()
            if not self._playback_thread.wait(2000):
                logger.warning("Playback thread did not stop in time; terminating")
                self._playback_thread.terminate()
                self._playback_thread.wait(1000)
            self._playback_thread.position_changed.disconnect(self.position_changed)
            self._playback_thread.playback_finished.disconnect(self._on_playback_finished)
            self._playback_thread = None

        self._set_state("stopped")
        self.position_changed.emit(0)

    @pyqtSlot(int)
    def seek(self, tick: int) -> None:
        if self._playback_thread is not None and self._playback_thread.isRunning():
            self._playback_thread.request_seek(tick)
        self.position_changed.emit(max(0, tick))

    def toggle_playback(self, start_tick: int = 0) -> None:
        """Convenience: play if stopped/paused, pause if playing."""
        if self._state == "playing":
            self.pause()
        else:
            self.play(start_tick)

    # -- internal transport helpers -----------------------------------------

    def _set_state(self, state: str) -> None:
        self._state = state
        self.playback_state_changed.emit(state)

    @pyqtSlot()
    def _on_playback_finished(self) -> None:
        self._set_state("stopped")

    # -----------------------------------------------------------------------
    # Track management
    # -----------------------------------------------------------------------

    def add_track(self, name: str | None = None, channel: int | None = None) -> Track:
        """Append a new empty track and return it."""
        from core.models import TRACK_COLORS

        idx = len(self._project.tracks)
        track = Track(
            name=name or f"Track {idx + 1}",
            channel=channel if channel is not None else min(idx, 15),
            color=TRACK_COLORS[idx % len(TRACK_COLORS)],
        )
        self._project.tracks.append(track)
        self._project.modified = True
        return track

    def remove_track(self, index: int) -> Optional[Track]:
        """Remove track at *index* and return it, or ``None`` if invalid."""
        if 0 <= index < len(self._project.tracks):
            removed = self._project.tracks.pop(index)
            self._project.modified = True
            return removed
        return None

    def duplicate_track(self, index: int) -> Optional[Track]:
        """Deep-copy the track at *index*, append it, and return the copy."""
        if not (0 <= index < len(self._project.tracks)):
            return None
        original = self._project.tracks[index]
        dup = original.copy()
        dup.name = f"{original.name} (copy)"
        self._project.tracks.insert(index + 1, dup)
        self._project.modified = True
        return dup

    def move_track(self, from_idx: int, to_idx: int) -> bool:
        """Reorder a track from one position to another."""
        tracks = self._project.tracks
        if not (0 <= from_idx < len(tracks)) or not (0 <= to_idx < len(tracks)):
            return False
        track = tracks.pop(from_idx)
        tracks.insert(to_idx, track)
        self._project.modified = True
        return True

    # -----------------------------------------------------------------------
    # Note operations
    # -----------------------------------------------------------------------

    def add_note(self, track_index: int, note: Note) -> bool:
        if not (0 <= track_index < len(self._project.tracks)):
            return False
        note.pitch = max(0, min(127, note.pitch))
        note.velocity = max(1, min(127, note.velocity))
        note.duration_ticks = max(1, note.duration_ticks)
        note.start_tick = max(0, note.start_tick)
        self._project.tracks[track_index].add_note(note)
        self._project.modified = True
        return True

    def remove_note(self, track_index: int, note: Note) -> bool:
        if not (0 <= track_index < len(self._project.tracks)):
            return False
        self._project.tracks[track_index].remove_note(note)
        self._project.modified = True
        return True

    def move_note(self, note: Note, new_start: int, new_pitch: int) -> None:
        """Move *note* to a new start tick and/or pitch (in-place)."""
        note.start_tick = max(0, new_start)
        note.pitch = max(0, min(127, new_pitch))
        self._project.modified = True

    def resize_note(self, note: Note, new_duration: int) -> None:
        note.duration_ticks = max(1, new_duration)
        self._project.modified = True

    def transpose_notes(self, notes: list[Note], semitones: int) -> None:
        """Shift every note's pitch by *semitones*, clamping to 0-127."""
        for n in notes:
            n.pitch = max(0, min(127, n.pitch + semitones))
        self._project.modified = True

    def set_velocity(self, notes: list[Note], velocity: int) -> None:
        velocity = max(1, min(127, velocity))
        for n in notes:
            n.velocity = velocity
        self._project.modified = True

    def adjust_velocity(self, notes: list[Note], delta: int) -> None:
        """Add *delta* to every note's velocity, clamping to 1-127."""
        for n in notes:
            n.velocity = max(1, min(127, n.velocity + delta))
        self._project.modified = True

    # -----------------------------------------------------------------------
    # Copy / paste
    # -----------------------------------------------------------------------

    def copy_notes(self, notes: list[Note]) -> None:
        """Store deep copies of *notes* on the internal clipboard."""
        if not notes:
            return
        self._clipboard = [n.copy() for n in notes]

    def paste_notes(self, track_index: int, tick_offset: int = 0) -> list[Note]:
        """Paste clipboard contents into the given track.

        Notes are shifted so the earliest note starts at *tick_offset*.
        Returns the newly-created note objects.
        """
        if not self._clipboard or not (0 <= track_index < len(self._project.tracks)):
            return []

        min_start = min(n.start_tick for n in self._clipboard)
        pasted: list[Note] = []
        track = self._project.tracks[track_index]

        for src in self._clipboard:
            n = src.copy()
            n.start_tick = max(0, n.start_tick - min_start + tick_offset)
            n.channel = track.channel
            track.add_note(n)
            pasted.append(n)

        self._project.modified = True
        return pasted

    def cut_notes(self, track_index: int, notes: list[Note]) -> None:
        """Copy *notes* to clipboard and remove them from the track."""
        self.copy_notes(notes)
        if 0 <= track_index < len(self._project.tracks):
            track = self._project.tracks[track_index]
            for n in notes:
                track.remove_note(n)
            self._project.modified = True

    @property
    def clipboard_empty(self) -> bool:
        return len(self._clipboard) == 0

    # -----------------------------------------------------------------------
    # Quantization
    # -----------------------------------------------------------------------

    def quantize_notes(
        self,
        notes: list[Note],
        grid_ticks: int | None = None,
        strength: float = 1.0,
        quantize_duration: bool = True,
    ) -> None:
        """Snap note start times (and optionally durations) to a grid.

        Parameters
        ----------
        notes:
            The notes to quantize (modified in-place).
        grid_ticks:
            Grid resolution in ticks.  Defaults to ``TICKS_PER_BEAT``
            (quarter-note grid).
        strength:
            0.0 = no change, 1.0 = full snap.  Values in between move
            the note proportionally toward the nearest grid line.
        quantize_duration:
            If *True*, note durations are also snapped to the grid
            (with a minimum of one grid unit).
        """
        if grid_ticks is None:
            grid_ticks = TICKS_PER_BEAT
        grid_ticks = max(1, grid_ticks)
        strength = max(0.0, min(1.0, strength))

        for note in notes:
            # Snap start
            nearest = round(note.start_tick / grid_ticks) * grid_ticks
            note.start_tick = max(0, int(note.start_tick + (nearest - note.start_tick) * strength))

            if quantize_duration:
                nearest_dur = round(note.duration_ticks / grid_ticks) * grid_ticks
                nearest_dur = max(grid_ticks, nearest_dur)
                note.duration_ticks = max(1, int(
                    note.duration_ticks + (nearest_dur - note.duration_ticks) * strength
                ))

        self._project.modified = True

    def quantize_track(
        self,
        track_index: int,
        grid_ticks: int | None = None,
        strength: float = 1.0,
        quantize_duration: bool = True,
    ) -> None:
        """Quantize every note in the specified track."""
        if 0 <= track_index < len(self._project.tracks):
            self.quantize_notes(
                self._project.tracks[track_index].notes,
                grid_ticks,
                strength,
                quantize_duration,
            )

    # -----------------------------------------------------------------------
    # MIDI export (standalone helper)
    # -----------------------------------------------------------------------

    def export_midi(
        self,
        path: str,
        project: Optional[ProjectState] = None,
        *,
        include_meta: bool = True,
    ) -> None:
        """High-level export with full tempo/time-sig meta messages.

        Identical to :meth:`save_midi_file` but kept as a separate entry
        point so callers can distinguish "Save" from "Export".
        """
        self.save_midi_file(path, project)

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def shutdown(self) -> None:
        """Stop playback and release MIDI resources.  Call on app exit."""
        self.stop()
        self.close_output_port()
        logger.info("MidiEngine shut down")
