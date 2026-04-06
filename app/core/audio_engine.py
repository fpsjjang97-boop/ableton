"""
Audio engine wrapping FluidSynth for MIDI-to-audio rendering.

Provides real-time note playback, per-channel mixing controls,
and offline bounce-to-WAV. Falls back gracefully to no-op stubs
when FluidSynth is not installed.
"""
from __future__ import annotations

import logging
import os
import struct
import wave
from pathlib import Path
from typing import Optional

from core.models import Note, Track, ProjectState
from config import DEFAULT_SOUNDFONT, SOUNDFONT_SEARCH_PATHS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FluidSynth DLL path setup (Windows)
# ---------------------------------------------------------------------------
try:
    from config import FLUIDSYNTH_DLL_PATH
    if FLUIDSYNTH_DLL_PATH and os.path.isdir(FLUIDSYNTH_DLL_PATH):
        os.environ["PATH"] = FLUIDSYNTH_DLL_PATH + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(FLUIDSYNTH_DLL_PATH)
except (ImportError, OSError):
    pass

# ---------------------------------------------------------------------------
# FluidSynth availability probe
# ---------------------------------------------------------------------------
try:
    import fluidsynth as _fs

    _FLUIDSYNTH_AVAILABLE = True
except Exception:  # ImportError, DLL-not-found, etc.
    _FLUIDSYNTH_AVAILABLE = False

# MIDI CC numbers
_CC_VOLUME = 7
_CC_PAN = 10
_CC_SUSTAIN = 64
_CC_ALL_NOTES_OFF = 123
_CC_ALL_SOUND_OFF = 120

# Render defaults
_SAMPLE_RATE = 44100
_RENDER_GAIN = 0.5
_RENDER_BLOCK = 1024  # samples per render chunk


def find_soundfont(filename: str = DEFAULT_SOUNDFONT) -> Optional[str]:
    """Search common paths for a SoundFont file.

    Returns the first match as an absolute path, or ``None``.
    """
    for directory in SOUNDFONT_SEARCH_PATHS:
        candidate = Path(directory).expanduser() / filename
        if candidate.is_file():
            return str(candidate.resolve())

    # Also try the filename directly in case it is already an absolute path
    direct = Path(filename)
    if direct.is_file():
        return str(direct.resolve())

    return None


class AudioEngine:
    """FluidSynth wrapper for MIDI playback and offline rendering.

    If FluidSynth cannot be loaded, every public method becomes a
    silent no-op so the rest of the application can still run.
    """

    def __init__(self, soundfont_path: Optional[str] = None):
        self.available: bool = False
        self._synth = None
        self._sfid: int = -1
        self._soundfont_path: Optional[str] = None

        if not _FLUIDSYNTH_AVAILABLE:
            logger.warning(
                "FluidSynth not found – audio engine disabled. "
                "Install pyfluidsynth to enable audio."
            )
            return

        try:
            self._synth = _fs.Synth(gain=_RENDER_GAIN, samplerate=float(_SAMPLE_RATE))
            sf = soundfont_path or find_soundfont()
            if sf is None:
                logger.warning(
                    "No SoundFont found (searched %s for '%s'). "
                    "Audio engine initialised without instruments.",
                    SOUNDFONT_SEARCH_PATHS,
                    DEFAULT_SOUNDFONT,
                )
                self.available = True
                return

            self._sfid = self._synth.sfload(sf)
            self._soundfont_path = sf
            self.available = True
            logger.info("Audio engine ready – SoundFont: %s", sf)
        except Exception:
            logger.exception("Failed to initialise FluidSynth")
            self._safe_cleanup()

    # ------------------------------------------------------------------
    # Real-time note control
    # ------------------------------------------------------------------

    def note_on(self, channel: int, pitch: int, velocity: int) -> None:
        """Send a MIDI note-on message."""
        if not self.available or self._synth is None:
            return
        try:
            self._synth.noteon(channel, pitch, velocity)
        except Exception:
            logger.exception("note_on failed (ch=%d, p=%d)", channel, pitch)

    def note_off(self, channel: int, pitch: int) -> None:
        """Send a MIDI note-off message."""
        if not self.available or self._synth is None:
            return
        try:
            self._synth.noteoff(channel, pitch)
        except Exception:
            logger.exception("note_off failed (ch=%d, p=%d)", channel, pitch)

    # ------------------------------------------------------------------
    # Channel configuration
    # ------------------------------------------------------------------

    def program_change(self, channel: int, program: int) -> None:
        """Select a GM instrument on *channel* (0-127)."""
        if not self.available or self._synth is None:
            return
        try:
            self._synth.program_change(channel, program)
        except Exception:
            logger.exception("program_change failed (ch=%d, pg=%d)", channel, program)

    def set_channel_volume(self, channel: int, volume: int) -> None:
        """Set channel volume via CC 7 (0-127)."""
        if not self.available or self._synth is None:
            return
        try:
            self._synth.cc(channel, _CC_VOLUME, max(0, min(127, volume)))
        except Exception:
            logger.exception("set_channel_volume failed (ch=%d)", channel)

    def set_channel_pan(self, channel: int, pan: int) -> None:
        """Set channel pan via CC 10 (0=left, 64=centre, 127=right)."""
        if not self.available or self._synth is None:
            return
        try:
            self._synth.cc(channel, _CC_PAN, max(0, min(127, pan)))
        except Exception:
            logger.exception("set_channel_pan failed (ch=%d)", channel)

    def sustain(self, channel: int, on: bool) -> None:
        """Press or release the sustain pedal on *channel*."""
        if not self.available or self._synth is None:
            return
        try:
            self._synth.cc(channel, _CC_SUSTAIN, 127 if on else 0)
        except Exception:
            logger.exception("sustain failed (ch=%d)", channel)

    def send_cc(self, channel: int, cc_number: int, value: int) -> None:
        """범용 CC 메시지 전송 — 익스프레션맵/오토메이션용."""
        if not self.available or self._synth is None:
            return
        try:
            self._synth.cc(channel, cc_number, max(0, min(127, value)))
        except Exception:
            logger.exception("send_cc failed (ch=%d, cc=%d)", channel, cc_number)

    def pitch_bend(self, channel: int, value: int) -> None:
        """피치벤드 전송 (-8192 ~ +8191)."""
        if not self.available or self._synth is None:
            return
        try:
            self._synth.pitch_bend(channel, max(0, min(16383, value + 8192)))
        except Exception:
            logger.exception("pitch_bend failed (ch=%d)", channel)

    def all_notes_off(self) -> None:
        """Panic – silence every channel immediately."""
        if not self.available or self._synth is None:
            return
        try:
            for ch in range(16):
                self._synth.cc(ch, _CC_ALL_SOUND_OFF, 0)
                self._synth.cc(ch, _CC_ALL_NOTES_OFF, 0)
                self._synth.cc(ch, _CC_SUSTAIN, 0)
        except Exception:
            logger.exception("all_notes_off failed")

    # ------------------------------------------------------------------
    # Offline render
    # ------------------------------------------------------------------

    def render_to_wav(self, project_state: ProjectState, output_path: str) -> bool:
        """Bounce the full project to a 16-bit stereo WAV file.

        Returns ``True`` on success, ``False`` otherwise.
        """
        if not _FLUIDSYNTH_AVAILABLE:
            logger.warning("Cannot render – FluidSynth unavailable.")
            return False

        sf = self._soundfont_path or find_soundfont()
        if sf is None:
            logger.error("Cannot render – no SoundFont loaded.")
            return False

        # Spin up a dedicated synth for offline rendering so the
        # real-time instance is undisturbed.
        synth = None
        try:
            synth = _fs.Synth(gain=_RENDER_GAIN, samplerate=float(_SAMPLE_RATE))
            sfid = synth.sfload(sf)

            # Build a flat, time-sorted event list from all un-muted tracks.
            events: list[tuple[float, str, int, int, int]] = []
            solo_active = any(t.solo for t in project_state.tracks)

            for track in project_state.tracks:
                if track.muted:
                    continue
                if solo_active and not track.solo:
                    continue

                ch = track.channel
                synth.program_change(ch, track.instrument)
                synth.cc(ch, _CC_VOLUME, max(0, min(127, track.volume)))
                synth.cc(ch, _CC_PAN, max(0, min(127, track.pan)))

                for note in track.notes:
                    t_on = project_state.ticks_to_seconds(note.start_tick)
                    t_off = project_state.ticks_to_seconds(note.end_tick)
                    events.append((t_on, "on", ch, note.pitch, note.velocity))
                    events.append((t_off, "off", ch, note.pitch, 0))

            events.sort(key=lambda e: e[0])

            total_seconds = project_state.total_seconds
            total_samples = int(total_seconds * _SAMPLE_RATE) + _SAMPLE_RATE  # +1 s tail

            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

            with wave.open(output_path, "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(_SAMPLE_RATE)

                rendered = 0
                ev_idx = 0

                while rendered < total_samples:
                    block = min(_RENDER_BLOCK, total_samples - rendered)
                    current_time = rendered / _SAMPLE_RATE

                    # Fire every event whose timestamp falls within this block.
                    while ev_idx < len(events) and events[ev_idx][0] <= current_time:
                        _, kind, ch, pitch, vel = events[ev_idx]
                        if kind == "on":
                            synth.noteon(ch, pitch, vel)
                        else:
                            synth.noteoff(ch, pitch)
                        ev_idx += 1

                    samples = synth.get_samples(block)

                    # FluidSynth returns interleaved float32 stereo.
                    raw = b""
                    for s in samples:
                        clamped = max(-1.0, min(1.0, s))
                        raw += struct.pack("<h", int(clamped * 32767))
                    wf.writeframes(raw)

                    rendered += block

            logger.info("Rendered %s (%.1f s)", output_path, total_seconds)
            return True

        except Exception:
            logger.exception("render_to_wav failed")
            return False
        finally:
            if synth is not None:
                try:
                    synth.delete()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Release FluidSynth resources."""
        self.all_notes_off()
        self._safe_cleanup()
        logger.info("Audio engine shut down.")

    def _safe_cleanup(self) -> None:
        if self._synth is not None:
            try:
                self._synth.delete()
            except Exception:
                pass
            self._synth = None
        self.available = False

    def __del__(self) -> None:
        self._safe_cleanup()
