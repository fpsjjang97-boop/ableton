"""
Groove / Drum Engine — swing, groove templates, groove extraction,
drum-specific note operations, step sequencer data model.

Covers: swing/shuffle, groove templates, groove extraction from MIDI,
drum pattern editor model, flam/roll/ruff, step sequencer.
Also: note split/merge, note mute, legato, note repeat/strum,
MIDI effects (arpeggiator), ghost notes display, scale highlight,
chord stamp, stretch/compress selection.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from core.models import Note, Track, TICKS_PER_BEAT, SCALE_INTERVALS, key_name_to_root


# ── Groove Template ────────────────────────────────────────────────────────

@dataclass
class GrooveTemplate:
    """Timing + velocity groove pattern."""
    name: str = "Straight"
    # Per-step timing offset (fraction of step, -0.5 to 0.5)
    timing_offsets: list[float] = field(default_factory=lambda: [0.0] * 16)
    # Per-step velocity multiplier (0-2)
    velocity_mults: list[float] = field(default_factory=lambda: [1.0] * 16)
    steps: int = 16
    base_division: int = 4     # steps per beat (4 = 16th notes, 2 = 8th notes)

    def copy(self) -> GrooveTemplate:
        g = copy.copy(self)
        g.timing_offsets = list(self.timing_offsets)
        g.velocity_mults = list(self.velocity_mults)
        return g


# Preset grooves
GROOVE_PRESETS = {
    "Straight": GrooveTemplate("Straight"),
    "MPC Swing 50%": GrooveTemplate(
        "MPC Swing 50%",
        timing_offsets=[0, 0, 0.08, 0, 0, 0, 0.08, 0, 0, 0, 0.08, 0, 0, 0, 0.08, 0],
    ),
    "MPC Swing 60%": GrooveTemplate(
        "MPC Swing 60%",
        timing_offsets=[0, 0, 0.12, 0, 0, 0, 0.12, 0, 0, 0, 0.12, 0, 0, 0, 0.12, 0],
    ),
    "MPC Swing 70%": GrooveTemplate(
        "MPC Swing 70%",
        timing_offsets=[0, 0, 0.17, 0, 0, 0, 0.17, 0, 0, 0, 0.17, 0, 0, 0, 0.17, 0],
    ),
    "Shuffle Light": GrooveTemplate(
        "Shuffle Light",
        timing_offsets=[0, 0, 0.1, 0, 0, 0, 0.1, 0, 0, 0, 0.1, 0, 0, 0, 0.1, 0],
        velocity_mults=[1.1, 0.8, 0.9, 0.7, 1.0, 0.8, 0.9, 0.7, 1.1, 0.8, 0.9, 0.7, 1.0, 0.8, 0.9, 0.7],
    ),
    "Shuffle Heavy": GrooveTemplate(
        "Shuffle Heavy",
        timing_offsets=[0, 0, 0.22, 0, 0, 0, 0.22, 0, 0, 0, 0.22, 0, 0, 0, 0.22, 0],
        velocity_mults=[1.2, 0.6, 1.0, 0.6, 1.1, 0.6, 1.0, 0.6, 1.2, 0.6, 1.0, 0.6, 1.1, 0.6, 1.0, 0.6],
    ),
    "Funk": GrooveTemplate(
        "Funk",
        timing_offsets=[0, 0.02, -0.02, 0.05, 0, 0.02, -0.02, 0.05, 0, 0.02, -0.02, 0.05, 0, 0.02, -0.02, 0.05],
        velocity_mults=[1.2, 0.7, 1.0, 0.9, 0.8, 0.7, 1.1, 0.9, 1.2, 0.7, 1.0, 0.9, 0.8, 0.7, 1.1, 0.9],
    ),
    "Bossa Nova": GrooveTemplate(
        "Bossa Nova",
        timing_offsets=[0, 0, 0.05, 0, 0, 0.05, 0, 0, 0, 0, 0.05, 0, 0, 0.05, 0, 0],
        velocity_mults=[1.0, 0.7, 0.9, 0.7, 0.8, 0.9, 0.7, 0.8, 1.0, 0.7, 0.9, 0.7, 0.8, 0.9, 0.7, 0.8],
    ),
}


# ── Groove Operations ──────────────────────────────────────────────────────

def apply_groove(notes: list[Note], groove: GrooveTemplate,
                 amount: float = 1.0, tpb: int = TICKS_PER_BEAT) -> list[Note]:
    """Apply groove template to notes."""
    step_ticks = tpb // groove.base_division
    result = []
    for note in notes:
        n = note.copy()
        step = (note.start_tick // step_ticks) % groove.steps
        # Timing
        offset = groove.timing_offsets[step] * step_ticks * amount
        n.start_tick = max(0, int(note.start_tick + offset))
        # Velocity
        vel_mult = 1.0 + (groove.velocity_mults[step] - 1.0) * amount
        n.velocity = max(1, min(127, int(note.velocity * vel_mult)))
        result.append(n)
    return result


def extract_groove(notes: list[Note], tpb: int = TICKS_PER_BEAT,
                   steps: int = 16, base_division: int = 4) -> GrooveTemplate:
    """Extract groove template from existing MIDI notes."""
    step_ticks = tpb // base_division
    timing_sums = [0.0] * steps
    velocity_sums = [0.0] * steps
    counts = [0] * steps

    for note in notes:
        step = (note.start_tick // step_ticks) % steps
        expected_tick = (note.start_tick // step_ticks) * step_ticks
        offset = (note.start_tick - expected_tick) / step_ticks
        timing_sums[step] += offset
        velocity_sums[step] += note.velocity
        counts[step] += 1

    avg_velocity = sum(velocity_sums) / max(sum(counts), 1)
    timing_offsets = [timing_sums[i] / max(counts[i], 1) for i in range(steps)]
    velocity_mults = [(velocity_sums[i] / max(counts[i], 1)) / max(avg_velocity, 1)
                      if counts[i] > 0 else 1.0 for i in range(steps)]

    return GrooveTemplate(
        name="Extracted",
        timing_offsets=timing_offsets,
        velocity_mults=velocity_mults,
        steps=steps,
        base_division=base_division,
    )


# ── Drum Articulations ────────────────────────────────────────────────────

def create_flam(note: Note, offset_ticks: int = 15, grace_velocity: float = 0.6) -> list[Note]:
    """Create a flam: grace note before main note."""
    grace = note.copy()
    grace.start_tick = max(0, note.start_tick - offset_ticks)
    grace.velocity = max(1, int(note.velocity * grace_velocity))
    grace.duration_ticks = offset_ticks
    grace.transition = "grace"
    return [grace, note.copy()]


def create_roll(note: Note, num_strokes: int = 4, tpb: int = TICKS_PER_BEAT) -> list[Note]:
    """Create a drum roll: rapid repeated strokes."""
    stroke_duration = note.duration_ticks // num_strokes
    result = []
    for i in range(num_strokes):
        n = note.copy()
        n.start_tick = note.start_tick + i * stroke_duration
        n.duration_ticks = stroke_duration
        n.velocity = max(1, int(note.velocity * (0.7 + 0.3 * (i / num_strokes))))
        result.append(n)
    return result


def create_ruff(note: Note, num_grace: int = 2, offset_ticks: int = 30) -> list[Note]:
    """Create a ruff: multiple grace notes before main note."""
    result = []
    for i in range(num_grace):
        grace = note.copy()
        grace.start_tick = max(0, note.start_tick - offset_ticks + i * (offset_ticks // num_grace))
        grace.velocity = max(1, int(note.velocity * 0.5))
        grace.duration_ticks = offset_ticks // num_grace
        grace.transition = "grace"
        result.append(grace)
    result.append(note.copy())
    return result


# ── Step Sequencer Model ──────────────────────────────────────────────────

@dataclass
class StepSequencerRow:
    """One row (one drum sound) in the step sequencer."""
    name: str = "Kick"
    pitch: int = 36
    steps: list[int] = field(default_factory=lambda: [0] * 16)  # 0=off, 1-127=velocity
    muted: bool = False


@dataclass
class StepSequencer:
    """16-step drum sequencer."""
    rows: list[StepSequencerRow] = field(default_factory=list)
    steps_per_beat: int = 4
    swing: float = 0.0         # 0-1

    def to_notes(self, tpb: int = TICKS_PER_BEAT) -> list[Note]:
        """Convert step grid to Note list."""
        step_ticks = tpb // self.steps_per_beat
        notes = []
        for row in self.rows:
            if row.muted:
                continue
            for i, vel in enumerate(row.steps):
                if vel > 0:
                    tick = i * step_ticks
                    # Apply swing to off-beat steps
                    if i % 2 == 1 and self.swing > 0:
                        tick += int(self.swing * step_ticks * 0.5)
                    notes.append(Note(
                        pitch=row.pitch, velocity=vel,
                        start_tick=tick, duration_ticks=step_ticks // 2,
                        channel=9,
                    ))
        return sorted(notes, key=lambda n: n.start_tick)

    @staticmethod
    def default() -> StepSequencer:
        rows = [
            StepSequencerRow("Kick", 36, [127, 0, 0, 0, 127, 0, 0, 0, 127, 0, 0, 0, 127, 0, 0, 0]),
            StepSequencerRow("Snare", 38, [0, 0, 0, 0, 127, 0, 0, 0, 0, 0, 0, 0, 127, 0, 0, 0]),
            StepSequencerRow("HiHat", 42, [100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0]),
            StepSequencerRow("Open HH", 46, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 80, 0]),
        ]
        return StepSequencer(rows=rows)


# ── Piano Roll Extensions ─────────────────────────────────────────────────

def split_note(note: Note, tick: int) -> tuple[Note, Note]:
    """Split a note at the given tick."""
    if tick <= note.start_tick or tick >= note.end_tick:
        return note.copy(), Note()
    left = note.copy()
    left.duration_ticks = tick - note.start_tick
    right = note.copy()
    right.start_tick = tick
    right.duration_ticks = note.end_tick - tick
    return left, right


def merge_notes(notes: list[Note]) -> Note:
    """Merge consecutive notes of same pitch into one."""
    if not notes:
        return Note()
    notes = sorted(notes, key=lambda n: n.start_tick)
    merged = notes[0].copy()
    for n in notes[1:]:
        if n.pitch == merged.pitch:
            merged.duration_ticks = n.end_tick - merged.start_tick
    return merged


def legato_notes(notes: list[Note]) -> list[Note]:
    """Extend each note to connect to the next."""
    if len(notes) < 2:
        return [n.copy() for n in notes]
    sorted_notes = sorted(notes, key=lambda n: n.start_tick)
    result = []
    for i in range(len(sorted_notes)):
        n = sorted_notes[i].copy()
        if i < len(sorted_notes) - 1:
            n.duration_ticks = sorted_notes[i + 1].start_tick - n.start_tick
        result.append(n)
    return result


def note_repeat(note: Note, count: int, interval_ticks: int) -> list[Note]:
    """Repeat a note at regular intervals."""
    result = []
    for i in range(count):
        n = note.copy()
        n.start_tick = note.start_tick + i * interval_ticks
        n.duration_ticks = min(note.duration_ticks, interval_ticks)
        result.append(n)
    return result


def strum_chord(notes: list[Note], spread_ticks: int = 15,
                direction: str = "down") -> list[Note]:
    """Apply strum effect to simultaneous notes."""
    sorted_by_pitch = sorted(notes, key=lambda n: n.pitch,
                             reverse=(direction == "down"))
    result = []
    for i, note in enumerate(sorted_by_pitch):
        n = note.copy()
        n.start_tick += i * spread_ticks
        result.append(n)
    return result


def stretch_selection(notes: list[Note], time_ratio: float = 1.0,
                      pitch_offset: int = 0) -> list[Note]:
    """Stretch/compress selected notes in time and/or pitch."""
    if not notes:
        return []
    anchor = notes[0].start_tick
    result = []
    for note in notes:
        n = note.copy()
        offset = note.start_tick - anchor
        n.start_tick = anchor + int(offset * time_ratio)
        n.duration_ticks = max(1, int(note.duration_ticks * time_ratio))
        n.pitch = max(0, min(127, note.pitch + pitch_offset))
        result.append(n)
    return result


# ── MIDI Effects ──────────────────────────────────────────────────────────

def arpeggiator(notes: list[Note], pattern: str = "up",
                rate_ticks: int = TICKS_PER_BEAT // 4,
                gate: float = 0.8, octaves: int = 1) -> list[Note]:
    """Apply arpeggiator effect to chord notes."""
    if not notes:
        return []
    # Get unique pitches
    pitches = sorted(set(n.pitch for n in notes))
    if not pitches:
        return []

    # Extend with octaves
    all_pitches = list(pitches)
    for oct in range(1, octaves):
        all_pitches.extend(p + 12 * oct for p in pitches)

    # Pattern order
    if pattern == "up":
        sequence = all_pitches
    elif pattern == "down":
        sequence = list(reversed(all_pitches))
    elif pattern == "up_down":
        sequence = all_pitches + list(reversed(all_pitches[1:-1]))
    elif pattern == "random":
        rng = np.random.default_rng()
        sequence = list(rng.permutation(all_pitches))
    elif pattern == "order":
        sequence = [n.pitch for n in sorted(notes, key=lambda n: n.start_tick)]
    else:
        sequence = all_pitches

    # Total duration
    total_dur = max(n.end_tick for n in notes) - min(n.start_tick for n in notes)
    start = min(n.start_tick for n in notes)
    velocity = int(np.mean([n.velocity for n in notes]))
    channel = notes[0].channel

    result = []
    step = 0
    while step * rate_ticks < total_dur:
        idx = step % len(sequence)
        pitch = sequence[idx]
        if 0 <= pitch <= 127:
            result.append(Note(
                pitch=pitch, velocity=velocity,
                start_tick=start + step * rate_ticks,
                duration_ticks=int(rate_ticks * gate),
                channel=channel,
            ))
        step += 1

    return result


def chord_stamp(root: int, quality: str, octave: int = 4,
                start_tick: int = 0, duration_ticks: int = TICKS_PER_BEAT * 4,
                velocity: int = 80) -> list[Note]:
    """Create notes for a chord by name."""
    intervals = {
        "major": [0, 4, 7],
        "minor": [0, 3, 7],
        "dim": [0, 3, 6],
        "aug": [0, 4, 8],
        "sus2": [0, 2, 7],
        "sus4": [0, 5, 7],
        "7": [0, 4, 7, 10],
        "maj7": [0, 4, 7, 11],
        "m7": [0, 3, 7, 10],
        "dim7": [0, 3, 6, 9],
        "m7b5": [0, 3, 6, 10],
        "add9": [0, 4, 7, 14],
        "6": [0, 4, 7, 9],
        "m6": [0, 3, 7, 9],
        "9": [0, 4, 7, 10, 14],
    }
    ivs = intervals.get(quality, [0, 4, 7])
    base = root + (octave + 1) * 12
    return [
        Note(pitch=min(127, base + iv), velocity=velocity,
             start_tick=start_tick, duration_ticks=duration_ticks)
        for iv in ivs
    ]
