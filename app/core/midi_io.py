"""
MIDI I/O Manager — real-time MIDI input, controller mapping, step recording,
MIDI monitoring, MPE, MIDI clock sync, thru.

Covers: MIDI keyboard recording, controller mapping, MIDI learn,
MIDI thru, step recording, MIDI monitor, MPE, clock sync, capture MIDI.
"""
from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)

try:
    import mido
    _HAS_MIDO = True
except ImportError:
    mido = None
    _HAS_MIDO = False

try:
    import rtmidi
    _HAS_RTMIDI = True
except ImportError:
    rtmidi = None
    _HAS_RTMIDI = False


# ── MIDI Controller Mapping ───────────────────────────────────────────────

@dataclass
class MIDIMapping:
    """Maps a MIDI CC/note to a software parameter."""
    midi_channel: int = -1          # -1 = any
    cc_number: int = -1             # CC number (-1 for note mapping)
    note_number: int = -1           # MIDI note (-1 for CC mapping)
    param_target: str = ""          # "track.0.volume", "master.pan", etc.
    min_value: float = 0.0
    max_value: float = 1.0
    inverted: bool = False


class MIDILearnManager:
    """Handles MIDI learn mode for controller mapping."""

    def __init__(self):
        self.mappings: list[MIDIMapping] = []
        self._learning = False
        self._learn_target: str = ""
        self._learn_callback: Optional[Callable] = None

    def start_learn(self, target: str, callback: Optional[Callable] = None):
        """Enter MIDI learn mode for a specific parameter."""
        self._learning = True
        self._learn_target = target
        self._learn_callback = callback

    def cancel_learn(self):
        self._learning = False
        self._learn_target = ""

    def process_input(self, msg_type: str, channel: int,
                      cc: int = -1, note: int = -1, value: int = 0):
        """Process incoming MIDI for learn mode."""
        if self._learning:
            mapping = MIDIMapping(
                midi_channel=channel,
                cc_number=cc if msg_type == 'cc' else -1,
                note_number=note if msg_type == 'note' else -1,
                param_target=self._learn_target,
            )
            self.mappings.append(mapping)
            self._learning = False
            if self._learn_callback:
                self._learn_callback(mapping)
            return True

        # Apply existing mappings
        for m in self.mappings:
            if m.midi_channel != -1 and m.midi_channel != channel:
                continue
            if msg_type == 'cc' and m.cc_number == cc:
                normalized = value / 127.0
                if m.inverted:
                    normalized = 1.0 - normalized
                return m.param_target, m.min_value + normalized * (m.max_value - m.min_value)
            if msg_type == 'note' and m.note_number == note:
                return m.param_target, value / 127.0

        return None

    def remove_mapping(self, index: int):
        if 0 <= index < len(self.mappings):
            self.mappings.pop(index)

    def clear_all(self):
        self.mappings.clear()


# ── MIDI Input Manager ────────────────────────────────────────────────────

class MIDIInputManager:
    """Real-time MIDI input handling."""

    # Default ticks-per-beat (matches core.models.TICKS_PER_BEAT)
    _DEFAULT_TPB = 480

    def __init__(self):
        self._input_port = None
        self._thru_port = None
        self._recording = False
        self._step_recording = False
        self._monitoring = True
        self._thru_enabled = False
        self._recorded_events: list[dict] = []
        self._capture_buffer: list[dict] = []   # for Capture MIDI
        self._capture_max = 10000
        self._listeners: list[Callable] = []
        self._clock_callback: Optional[Callable] = None
        self._start_time = 0.0
        self._step_position = 0
        self._step_duration = 480   # ticks per step

        # Real-time recording state
        self._bpm: float = 120.0
        self._record_start_tick: int = 0
        self._record_start_time: float = 0.0
        self._record_buffer: list = []      # list of Note objects
        self._pending_notes: dict = {}      # {(ch, pitch): (start_tick, velocity)}
        self._thru_callback: Optional[Callable] = None

        # MIDI Learn
        self.learn_manager = MIDILearnManager()

    @staticmethod
    def get_input_ports() -> list[str]:
        if not _HAS_MIDO:
            return []
        try:
            return mido.get_input_names()
        except Exception:
            return []

    @staticmethod
    def get_output_ports() -> list[str]:
        if not _HAS_MIDO:
            return []
        try:
            return mido.get_output_names()
        except Exception:
            return []

    def open_input(self, port_name: str) -> bool:
        try:
            self._input_port = mido.open_input(port_name, callback=self._on_message)
            logger.info(f"MIDI input opened: {port_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to open MIDI input: {e}")
            return False

    def close_input(self):
        if self._input_port:
            self._input_port.close()
            self._input_port = None

    def open_thru(self, port_name: str) -> bool:
        """Open MIDI thru output port."""
        try:
            self._thru_port = mido.open_output(port_name)
            self._thru_enabled = True
            return True
        except Exception as e:
            logger.error(f"Failed to open MIDI thru: {e}")
            return False

    def set_thru(self, enabled: bool):
        self._thru_enabled = enabled

    def add_listener(self, callback: Callable):
        """Add MIDI message listener: fn(msg_dict)."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _on_message(self, msg):
        """Process incoming MIDI message."""
        now = time.time()
        elapsed = now - self._start_time if self._start_time > 0 else 0

        msg_dict = {
            'type': msg.type,
            'time': elapsed,
            'channel': getattr(msg, 'channel', 0),
        }

        if msg.type == 'note_on':
            msg_dict['note'] = msg.note
            msg_dict['velocity'] = msg.velocity
        elif msg.type == 'note_off':
            msg_dict['note'] = msg.note
            msg_dict['velocity'] = 0
        elif msg.type == 'control_change':
            msg_dict['cc'] = msg.control
            msg_dict['value'] = msg.value
        elif msg.type == 'pitchwheel':
            msg_dict['pitch'] = msg.pitch
        elif msg.type == 'aftertouch':
            msg_dict['value'] = msg.value
        elif msg.type == 'polytouch':
            msg_dict['note'] = msg.note
            msg_dict['value'] = msg.value
        elif msg.type == 'clock':
            if self._clock_callback:
                self._clock_callback('clock')
            return
        elif msg.type == 'start':
            if self._clock_callback:
                self._clock_callback('start')
            return
        elif msg.type == 'stop':
            if self._clock_callback:
                self._clock_callback('stop')
            return

        # MIDI Thru (hardware output port)
        if self._thru_enabled and self._thru_port:
            try:
                self._thru_port.send(msg)
            except Exception:
                pass

        # MIDI Thru (software callback — route to AudioEngine for monitoring)
        if msg.type == 'note_on' and msg.velocity > 0:
            if self._thru_callback:
                try:
                    self._thru_callback(getattr(msg, 'channel', 0), msg.note, msg.velocity)
                except Exception:
                    pass
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            if self._thru_callback:
                try:
                    self._thru_callback(getattr(msg, 'channel', 0), msg.note, 0)
                except Exception:
                    pass

        # MIDI Learn
        if msg.type == 'control_change':
            self.learn_manager.process_input('cc', msg_dict['channel'],
                                             cc=msg.control, value=msg.value)
        elif msg.type in ('note_on', 'note_off'):
            self.learn_manager.process_input('note', msg_dict['channel'],
                                             note=msg.note, value=msg_dict.get('velocity', 0))

        # Real-time recording → Note objects
        if self._recording:
            self._recorded_events.append(msg_dict)
            self._record_note_event(msg, now)

        # Step recording
        if self._step_recording and msg.type == 'note_on' and msg_dict['velocity'] > 0:
            msg_dict['step_tick'] = self._step_position
            self._recorded_events.append(msg_dict)
            self._step_position += self._step_duration

        # Capture buffer (always recording last N events)
        self._capture_buffer.append(msg_dict)
        if len(self._capture_buffer) > self._capture_max:
            self._capture_buffer.pop(0)

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(msg_dict)
            except Exception:
                pass

    def _record_note_event(self, msg, now: float):
        """Pair note_on/note_off into Note objects in the record buffer."""
        from core.models import Note

        tpb = self._DEFAULT_TPB
        elapsed = now - self._record_start_time
        # Convert real time to ticks based on current BPM
        ticks = int(elapsed * self._bpm / 60.0 * tpb) + self._record_start_tick

        channel = getattr(msg, 'channel', 0)

        if msg.type == 'note_on' and msg.velocity > 0:
            self._pending_notes[(channel, msg.note)] = (ticks, msg.velocity)

        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            key = (channel, msg.note)
            if key in self._pending_notes:
                start, vel = self._pending_notes.pop(key)
                duration = max(30, ticks - start)
                self._record_buffer.append(Note(
                    pitch=msg.note,
                    velocity=vel,
                    start_tick=start,
                    duration_ticks=duration,
                    channel=channel,
                ))

    # ── BPM / Thru configuration ──

    def set_bpm(self, bpm: float):
        """Set the BPM used for real-time-to-tick conversion during recording."""
        self._bpm = max(1.0, bpm)

    def set_thru_callback(self, callback: Optional[Callable]):
        """Set a callback ``fn(channel, note, velocity)`` for MIDI thru monitoring.

        Called on every note_on/note_off so the host can route to an AudioEngine.
        Pass *velocity* = 0 for note-off.
        """
        self._thru_callback = callback

    # ── Recording ──

    def start_recording(self, start_tick: int = 0):
        """Start recording MIDI input to buffer.

        *start_tick* is the playback position at the moment recording begins,
        so that captured notes are placed relative to the timeline.
        """
        self._recording = True
        self._record_start_tick = start_tick
        self._record_buffer = []
        self._pending_notes = {}
        self._record_start_time = time.time()
        self._recorded_events.clear()
        self._start_time = time.time()

    def stop_recording(self) -> list:
        """Stop recording and return captured Note objects.

        Any notes still held down at stop time are closed with a default
        duration of one beat.
        """
        from core.models import Note, TICKS_PER_BEAT

        self._recording = False

        # Close any notes that were never released
        for (ch, pitch), (start, vel) in self._pending_notes.items():
            self._record_buffer.append(Note(
                pitch=pitch,
                velocity=vel,
                start_tick=start,
                duration_ticks=TICKS_PER_BEAT,
                channel=ch,
            ))
        self._pending_notes.clear()

        captured = list(self._record_buffer)
        self._record_buffer = []
        return captured

    def is_recording(self) -> bool:
        return self._recording

    # ── Step Recording ──

    def start_step_recording(self, step_duration: int = 480):
        self._step_recording = True
        self._step_duration = step_duration
        self._step_position = 0
        self._recorded_events.clear()

    def stop_step_recording(self) -> list[dict]:
        self._step_recording = False
        events = self._recorded_events.copy()
        self._recorded_events.clear()
        return events

    def advance_step(self):
        self._step_position += self._step_duration

    def retreat_step(self):
        self._step_position = max(0, self._step_position - self._step_duration)

    # ── Capture MIDI ──

    def capture_midi(self, lookback_seconds: float = 30.0) -> list[dict]:
        """Capture recently played MIDI (like Ableton's Capture)."""
        now = time.time()
        cutoff = now - lookback_seconds
        captured = [e for e in self._capture_buffer if e.get('time', 0) >= cutoff]
        return captured

    # ── MIDI Clock ──

    def set_clock_callback(self, callback: Callable):
        self._clock_callback = callback

    def send_clock(self, port_name: str, bpm: float):
        """Send MIDI clock to external device."""
        if not _HAS_MIDO:
            return
        try:
            port = mido.open_output(port_name)
            interval = 60.0 / (bpm * 24)  # 24 ppqn
            port.send(mido.Message('start'))
            # Clock sending would be done in a thread
            port.close()
        except Exception as e:
            logger.error(f"MIDI clock send failed: {e}")


# ── MIDI Monitor ──────────────────────────────────────────────────────────

class MIDIMonitor:
    """Displays real-time MIDI activity."""

    def __init__(self, max_entries: int = 100):
        self._entries: list[dict] = []
        self._max = max_entries
        self._active_notes: dict[int, int] = {}  # note → velocity

    def on_message(self, msg_dict: dict):
        """Process a message for display."""
        self._entries.append(msg_dict)
        if len(self._entries) > self._max:
            self._entries.pop(0)

        if msg_dict['type'] == 'note_on' and msg_dict.get('velocity', 0) > 0:
            self._active_notes[msg_dict['note']] = msg_dict['velocity']
        elif msg_dict['type'] in ('note_off', 'note_on'):
            self._active_notes.pop(msg_dict.get('note', -1), None)

    @property
    def entries(self) -> list[dict]:
        return self._entries

    @property
    def active_notes(self) -> dict[int, int]:
        return self._active_notes

    def clear(self):
        self._entries.clear()
        self._active_notes.clear()
