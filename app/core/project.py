"""
Project management for the MIDI AI Workstation.
Handles save/load (.maw JSON), MIDI import/export, recent files, and auto-save.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, QSettings, pyqtSignal

from core.models import (
    Note, Track, ProjectState, TimeSignature,
    TICKS_PER_BEAT, TRACK_COLORS,
)

logger = logging.getLogger(__name__)

MAW_VERSION = 1
MAX_RECENT_FILES = 10
DEFAULT_AUTOSAVE_MINUTES = 3


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _note_to_dict(n: Note) -> dict:
    return dict(pitch=n.pitch, velocity=n.velocity,
                start_tick=n.start_tick, duration_ticks=n.duration_ticks,
                channel=n.channel)


def _note_from_dict(d: dict) -> Note:
    return Note(pitch=d["pitch"], velocity=d["velocity"],
                start_tick=d["start_tick"], duration_ticks=d["duration_ticks"],
                channel=d.get("channel", 0))


def _track_to_dict(t: Track) -> dict:
    return dict(name=t.name, channel=t.channel,
                notes=[_note_to_dict(n) for n in t.notes],
                muted=t.muted, solo=t.solo, volume=t.volume, pan=t.pan,
                color=t.color, instrument=t.instrument)


def _track_from_dict(d: dict) -> Track:
    return Track(name=d["name"], channel=d.get("channel", 0),
                 notes=[_note_from_dict(n) for n in d.get("notes", [])],
                 muted=d.get("muted", False), solo=d.get("solo", False),
                 volume=d.get("volume", 100), pan=d.get("pan", 64),
                 color=d.get("color", TRACK_COLORS[0]),
                 instrument=d.get("instrument", 0))


def _project_to_dict(p: ProjectState) -> dict:
    return {
        "maw_version": MAW_VERSION,
        "name": p.name,
        "bpm": p.bpm,
        "time_signature": [p.time_signature.numerator,
                           p.time_signature.denominator],
        "key": p.key,
        "scale": p.scale,
        "ticks_per_beat": p.ticks_per_beat,
        "loop_start": p.loop_start,
        "loop_end": p.loop_end,
        "loop_enabled": p.loop_enabled,
        "tracks": [_track_to_dict(t) for t in p.tracks],
    }


def _project_from_dict(d: dict) -> ProjectState:
    ts = d.get("time_signature", [4, 4])
    return ProjectState(
        name=d.get("name", "Untitled"),
        tracks=[_track_from_dict(t) for t in d.get("tracks", [])],
        bpm=float(d.get("bpm", 120.0)),
        time_signature=TimeSignature(numerator=ts[0], denominator=ts[1]),
        key=d.get("key", "C"),
        scale=d.get("scale", "minor"),
        ticks_per_beat=d.get("ticks_per_beat", TICKS_PER_BEAT),
        loop_start=d.get("loop_start", 0),
        loop_end=d.get("loop_end", TICKS_PER_BEAT * 16),
        loop_enabled=d.get("loop_enabled", False),
    )


# ---------------------------------------------------------------------------
# ProjectManager
# ---------------------------------------------------------------------------

class ProjectManager(QObject):
    """Central manager for project lifecycle, persistence, and auto-save."""

    project_changed = pyqtSignal()
    project_saved = pyqtSignal(str)       # path
    auto_saved = pyqtSignal(str)          # path

    def __init__(self, parent: Optional[QObject] = None,
                 autosave_minutes: int = DEFAULT_AUTOSAVE_MINUTES):
        super().__init__(parent)
        self._state: ProjectState = self._make_default_project()
        self._settings = QSettings("MidiAIWorkstation", "MAW")

        self._autosave_dir = Path(tempfile.gettempdir()) / "maw_autosave"
        self._autosave_dir.mkdir(parents=True, exist_ok=True)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._on_autosave)
        self.set_autosave_interval(autosave_minutes)

    # -- properties ----------------------------------------------------------

    @property
    def state(self) -> ProjectState:
        return self._state

    @state.setter
    def state(self, value: ProjectState) -> None:
        self._state = value
        self._state.modified = True
        self.project_changed.emit()

    # -- new / save / load ---------------------------------------------------

    def new_project(self) -> ProjectState:
        """Create a blank project with one default track."""
        self._state = self._make_default_project()
        self.project_changed.emit()
        return self._state

    def save_project(self, path: str) -> None:
        """Serialize the current project to a .maw JSON file."""
        path = os.path.abspath(path)
        data = _project_to_dict(self._state)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError as exc:
            logger.error("Failed to save project to %s: %s", path, exc)
            raise
        self._state.file_path = path
        self._state.modified = False
        self.add_to_recent(path)
        self.project_saved.emit(path)
        logger.info("Project saved: %s", path)

    def load_project(self, path: str) -> ProjectState:
        """Deserialize a .maw JSON file into the current project state."""
        path = os.path.abspath(path)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load project from %s: %s", path, exc)
            raise
        version = data.get("maw_version", 0)
        if version > MAW_VERSION:
            logger.warning("File version %d is newer than supported %d",
                           version, MAW_VERSION)
        self._state = _project_from_dict(data)
        self._state.file_path = path
        self._state.modified = False
        self.add_to_recent(path)
        self.project_changed.emit()
        logger.info("Project loaded: %s", path)
        return self._state

    # -- MIDI import / export ------------------------------------------------

    def import_midi(self, path: str) -> ProjectState:
        """Import a standard MIDI file into a new ProjectState."""
        import mido  # deferred so the module loads without mido installed

        path = os.path.abspath(path)
        mid = mido.MidiFile(path)
        tpb = mid.ticks_per_beat or TICKS_PER_BEAT

        self._state = ProjectState(
            name=Path(path).stem,
            ticks_per_beat=tpb,
        )
        for idx, midi_track in enumerate(mid.tracks):
            notes: list[Note] = []
            active: dict[int, tuple[int, int]] = {}  # pitch -> (tick, vel)
            instrument = 0  # Default: Acoustic Grand Piano
            tick = 0
            for msg in midi_track:
                tick += msg.time
                if msg.type == "program_change":
                    instrument = msg.program
                elif msg.type == "note_on" and msg.velocity > 0:
                    active[msg.note] = (tick, msg.velocity)
                elif msg.type in ("note_off", "note_on"):
                    start_info = active.pop(msg.note, None)
                    if start_info is not None:
                        st, vel = start_info
                        notes.append(Note(pitch=msg.note, velocity=vel,
                                          start_tick=st,
                                          duration_ticks=max(tick - st, 1),
                                          channel=getattr(msg, "channel", 0)))
            if notes:
                color = TRACK_COLORS[idx % len(TRACK_COLORS)]
                track_name = midi_track.name or f"Track {idx + 1}"
                # Auto-detect instrument from track name if no program_change
                if instrument == 0:
                    name_lower = track_name.lower()
                    if "bass" in name_lower:
                        instrument = 32  # Acoustic Bass
                    elif "string" in name_lower or "str_" in name_lower:
                        instrument = 48  # String Ensemble
                    elif "guitar" in name_lower:
                        instrument = 24  # Acoustic Guitar
                    elif "drum" in name_lower:
                        instrument = 0  # Channel 9 handles drums
                    elif "pad" in name_lower:
                        instrument = 88  # Pad
                self._state.tracks.append(
                    Track(name=track_name, channel=idx, notes=notes,
                          color=color, instrument=instrument))

        # Detect tempo from first track
        for msg in mid.tracks[0] if mid.tracks else []:
            if msg.type == "set_tempo":
                self._state.bpm = round(mido.tempo2bpm(msg.tempo), 2)
                break

        if not self._state.tracks:
            self._state.tracks.append(self._make_default_track(0))

        self._state.file_path = None
        self._state.modified = True
        self.project_changed.emit()
        logger.info("Imported MIDI: %s (%d tracks)", path,
                    len(self._state.tracks))
        return self._state

    def export_midi(self, path: str) -> None:
        """Export the current project to a standard MIDI file."""
        import mido

        path = os.path.abspath(path)
        mid = mido.MidiFile(ticks_per_beat=self._state.ticks_per_beat)

        # Tempo track
        tempo_track = mido.MidiTrack()
        tempo_track.append(mido.MetaMessage(
            "set_tempo", tempo=mido.bpm2tempo(self._state.bpm), time=0))
        tempo_track.append(mido.MetaMessage(
            "time_signature",
            numerator=self._state.time_signature.numerator,
            denominator=self._state.time_signature.denominator,
            time=0))
        tempo_track.append(mido.MetaMessage("end_of_track", time=0))
        mid.tracks.append(tempo_track)

        for track in self._state.tracks:
            mt = mido.MidiTrack()
            mt.append(mido.MetaMessage("track_name", name=track.name, time=0))
            events: list[tuple[int, mido.Message]] = []
            for n in track.notes:
                events.append((n.start_tick,
                               mido.Message("note_on", note=n.pitch,
                                            velocity=n.velocity,
                                            channel=track.channel)))
                events.append((n.end_tick,
                               mido.Message("note_off", note=n.pitch,
                                            velocity=0,
                                            channel=track.channel)))
            events.sort(key=lambda e: e[0])
            prev = 0
            for abs_tick, msg in events:
                msg.time = abs_tick - prev
                mt.append(msg)
                prev = abs_tick
            mt.append(mido.MetaMessage("end_of_track", time=0))
            mid.tracks.append(mt)

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        mid.save(path)
        logger.info("Exported MIDI: %s", path)

    # -- recent files --------------------------------------------------------

    def get_recent_files(self) -> list[str]:
        """Return the list of recently-opened file paths."""
        raw = self._settings.value("recent_files", [])
        if isinstance(raw, str):
            raw = [raw] if raw else []
        return [p for p in raw if os.path.isfile(p)]

    def add_to_recent(self, path: str) -> None:
        path = os.path.abspath(path)
        recent = self.get_recent_files()
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self._settings.setValue("recent_files", recent[:MAX_RECENT_FILES])

    def clear_recent_files(self) -> None:
        self._settings.setValue("recent_files", [])

    # -- auto-save -----------------------------------------------------------

    def set_autosave_interval(self, minutes: int) -> None:
        """Set auto-save interval. Pass 0 to disable."""
        self._autosave_timer.stop()
        if minutes > 0:
            self._autosave_timer.start(minutes * 60_000)

    def _on_autosave(self) -> None:
        if not self._state.modified:
            return
        stamp = int(time.time())
        name = self._state.name.replace(" ", "_") or "untitled"
        filename = f"{name}_autosave_{stamp}.maw"
        path = str(self._autosave_dir / filename)
        try:
            data = _project_to_dict(self._state)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            self.auto_saved.emit(path)
            logger.info("Auto-saved: %s", path)
        except OSError as exc:
            logger.warning("Auto-save failed: %s", exc)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _make_default_track(index: int = 0) -> Track:
        return Track(name=f"Track {index + 1}", channel=index,
                     color=TRACK_COLORS[index % len(TRACK_COLORS)])

    def _make_default_project(self) -> ProjectState:
        return ProjectState(
            name="Untitled",
            tracks=[self._make_default_track(0)],
            bpm=120.0,
            time_signature=TimeSignature(4, 4),
        )
