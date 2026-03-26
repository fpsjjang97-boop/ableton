"""
Shared data models for the MIDI AI Workstation.
All modules reference these types for consistency.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import copy


TICKS_PER_BEAT = 480

SCALE_INTERVALS = {
    "major":        [0, 2, 4, 5, 7, 9, 11],
    "minor":        [0, 2, 3, 5, 7, 8, 10],
    "dorian":       [0, 2, 3, 5, 7, 9, 10],
    "mixolydian":   [0, 2, 4, 5, 7, 9, 10],
    "pentatonic":   [0, 2, 4, 7, 9],
    "minor_penta":  [0, 3, 5, 7, 10],
    "blues":        [0, 3, 5, 6, 7, 10],
    "chromatic":    list(range(12)),
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

TRACK_COLORS = [
    "#B0B0B0", "#8C8C8C", "#C8C8C8", "#9A9A9A",
    "#707070", "#D4D4D4", "#A0A0A0", "#787878",
    "#606060", "#E0E0E0", "#888888", "#C0C0C0",
    "#585858", "#CACACA", "#969696", "#B8B8B8",
]


def note_name_to_midi(name: str) -> int:
    """Convert note name like 'C4' or 'A#3' to MIDI number."""
    for i, n in enumerate(NOTE_NAMES):
        if name.upper().startswith(n) and len(n) == len(name) - 1:
            octave = int(name[len(n):])
            return (octave + 1) * 12 + i
    return 60


def midi_to_note_name(midi_num: int) -> str:
    """Convert MIDI number to note name like 'C4'."""
    octave = (midi_num // 12) - 1
    note = NOTE_NAMES[midi_num % 12]
    return f"{note}{octave}"


def key_name_to_root(key: str) -> int:
    """Convert key name to pitch class (0-11). e.g., 'A#' -> 10."""
    key = key.strip().upper()
    if key in NOTE_NAMES:
        return NOTE_NAMES.index(key)
    aliases = {"Bb": "A#", "Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#"}
    key_title = key.title()
    if key_title in aliases:
        return NOTE_NAMES.index(aliases[key_title])
    return 0


def get_scale_pitches(root: int, scale_name: str) -> list[int]:
    """Get all valid MIDI pitches for a scale across all octaves."""
    intervals = SCALE_INTERVALS.get(scale_name, SCALE_INTERVALS["minor"])
    pitches = []
    for octave_base in range(0, 128, 12):
        for iv in intervals:
            p = octave_base + root + iv
            if 0 <= p < 128:
                pitches.append(p)
    return sorted(set(pitches))


@dataclass
class Note:
    """A single MIDI note event."""
    pitch: int = 60
    velocity: int = 80
    start_tick: int = 0
    duration_ticks: int = TICKS_PER_BEAT
    channel: int = 0

    @property
    def end_tick(self) -> int:
        return self.start_tick + self.duration_ticks

    @property
    def name(self) -> str:
        return midi_to_note_name(self.pitch)

    def copy(self) -> Note:
        return copy.copy(self)


@dataclass
class Track:
    """A MIDI track containing notes and metadata."""
    name: str = "Track 1"
    channel: int = 0
    notes: list[Note] = field(default_factory=list)
    muted: bool = False
    solo: bool = False
    volume: int = 100
    pan: int = 64
    color: str = "#B0B0B0"
    instrument: int = 0  # GM program number

    def copy(self) -> Track:
        t = copy.copy(self)
        t.notes = [n.copy() for n in self.notes]
        return t

    def get_notes_in_range(self, start_tick: int, end_tick: int) -> list[Note]:
        return [n for n in self.notes if n.end_tick > start_tick and n.start_tick < end_tick]

    def add_note(self, note: Note) -> None:
        self.notes.append(note)
        self.notes.sort(key=lambda n: n.start_tick)

    def remove_note(self, note: Note) -> None:
        if note in self.notes:
            self.notes.remove(note)

    @property
    def duration_ticks(self) -> int:
        if not self.notes:
            return 0
        return max(n.end_tick for n in self.notes)


@dataclass
class TimeSignature:
    numerator: int = 4
    denominator: int = 4


@dataclass
class ProjectState:
    """Complete state of a project."""
    name: str = "Untitled"
    file_path: Optional[str] = None
    tracks: list[Track] = field(default_factory=list)
    bpm: float = 120.0
    time_signature: TimeSignature = field(default_factory=TimeSignature)
    key: str = "C"
    scale: str = "minor"
    ticks_per_beat: int = TICKS_PER_BEAT
    loop_start: int = 0
    loop_end: int = TICKS_PER_BEAT * 16
    loop_enabled: bool = False
    modified: bool = False

    @property
    def total_ticks(self) -> int:
        if not self.tracks:
            return self.ticks_per_beat * self.time_signature.numerator * 16
        return max((t.duration_ticks for t in self.tracks), default=self.ticks_per_beat * 64)

    @property
    def total_beats(self) -> float:
        return self.total_ticks / self.ticks_per_beat

    @property
    def total_seconds(self) -> float:
        return (self.total_ticks / self.ticks_per_beat) * (60.0 / self.bpm)

    def ticks_to_seconds(self, ticks: int) -> float:
        return (ticks / self.ticks_per_beat) * (60.0 / self.bpm)

    def seconds_to_ticks(self, seconds: float) -> int:
        return int(seconds * (self.bpm / 60.0) * self.ticks_per_beat)

    def ticks_to_beats(self, ticks: int) -> float:
        return ticks / self.ticks_per_beat

    def beats_to_ticks(self, beats: float) -> int:
        return int(beats * self.ticks_per_beat)


@dataclass
class UndoAction:
    """Represents a reversible action for undo/redo."""
    description: str
    old_state: ProjectState
    new_state: ProjectState


class UndoManager:
    """Manages undo/redo history."""

    def __init__(self, max_history: int = 100):
        self._history: list[UndoAction] = []
        self._position: int = -1
        self._max = max_history

    def push(self, description: str, old_state: ProjectState, new_state: ProjectState):
        self._history = self._history[: self._position + 1]
        action = UndoAction(description, old_state, new_state)
        self._history.append(action)
        if len(self._history) > self._max:
            self._history.pop(0)
        self._position = len(self._history) - 1

    def undo(self) -> Optional[ProjectState]:
        if self._position < 0:
            return None
        state = self._history[self._position].old_state
        self._position -= 1
        return state

    def redo(self) -> Optional[ProjectState]:
        if self._position >= len(self._history) - 1:
            return None
        self._position += 1
        return self._history[self._position].new_state

    @property
    def can_undo(self) -> bool:
        return self._position >= 0

    @property
    def can_redo(self) -> bool:
        return self._position < len(self._history) - 1

    def clear(self):
        self._history.clear()
        self._position = -1
