"""
Utility functions for MIDI operations used across the MIDI AI Workstation.

Provides conversion, analysis, and transformation helpers that operate
on the shared Note/Track data models and interoperate with the mido library.
"""
from __future__ import annotations

import math
from typing import Optional

import mido
import numpy as np

from core.models import (
    Note,
    Track,
    ProjectState,
    TICKS_PER_BEAT,
    SCALE_INTERVALS,
    NOTE_NAMES,
    key_name_to_root,
    get_scale_pitches,
)

# ---------------------------------------------------------------------------
#  Krumhansl-Schmuckler key profiles
# ---------------------------------------------------------------------------
_MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
_MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)


# ---------------------------------------------------------------------------
#  Tick / time conversions
# ---------------------------------------------------------------------------

def ticks_to_time_string(ticks: int, tpb: int, bpm: float) -> str:
    """Convert a tick position to a human-readable *MM:SS.mmm* string."""
    seconds = (ticks / tpb) * (60.0 / bpm)
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes:02d}:{secs:06.3f}"


def ticks_to_bar_beat_tick(
    ticks: int, tpb: int, time_sig_num: int = 4
) -> tuple[int, int, int]:
    """Convert absolute ticks to 1-indexed *(bar, beat, tick)* tuple."""
    ticks_per_bar = tpb * time_sig_num
    bar = ticks // ticks_per_bar + 1
    remainder = ticks % ticks_per_bar
    beat = remainder // tpb + 1
    tick = remainder % tpb
    return (bar, beat, tick)


def bar_beat_tick_to_ticks(
    bar: int, beat: int, tick: int, tpb: int, time_sig_num: int = 4
) -> int:
    """Convert 1-indexed *(bar, beat, tick)* back to absolute ticks."""
    ticks_per_bar = tpb * time_sig_num
    return (bar - 1) * ticks_per_bar + (beat - 1) * tpb + tick


def snap_to_grid(tick: int, grid_ticks: int) -> int:
    """Snap *tick* to the nearest grid point defined by *grid_ticks*.

    If *grid_ticks* is <= 0 snapping is disabled and the value is returned
    unchanged.
    """
    if grid_ticks <= 0:
        return tick
    return round(tick / grid_ticks) * grid_ticks


# ---------------------------------------------------------------------------
#  mido ↔ Note conversions
# ---------------------------------------------------------------------------

def notes_to_mido_track(
    notes: list[Note], channel: int = 0, tpb: int = TICKS_PER_BEAT
) -> mido.MidiTrack:
    """Build a :class:`mido.MidiTrack` from a list of :class:`Note` objects.

    The resulting track contains properly ordered note_on / note_off messages
    with correct delta times and a trailing end_of_track meta message.
    """
    events: list[tuple[int, mido.Message]] = []
    for n in notes:
        ch = n.channel if n.channel >= 0 else channel
        events.append((n.start_tick, mido.Message("note_on", note=n.pitch,
                                                   velocity=n.velocity, channel=ch)))
        events.append((n.end_tick, mido.Message("note_off", note=n.pitch,
                                                 velocity=0, channel=ch)))
    # Stable sort: note_off before note_on when at the same tick
    events.sort(key=lambda e: (e[0], 0 if e[1].type == "note_off" else 1))

    track = mido.MidiTrack()
    abs_tick = 0
    for tick, msg in events:
        msg.time = tick - abs_tick
        track.append(msg)
        abs_tick = tick
    track.append(mido.MetaMessage("end_of_track", time=0))
    return track


def mido_track_to_notes(track: mido.MidiTrack, tpb: int = TICKS_PER_BEAT) -> list[Note]:
    """Parse a :class:`mido.MidiTrack` into a list of :class:`Note` objects.

    Handles note_on/note_off pairing.  A note_on with velocity 0 is treated
    as note_off (common MIDI convention).
    """
    pending: dict[tuple[int, int], tuple[int, int]] = {}  # (ch, pitch) -> (start, vel)
    notes: list[Note] = []
    abs_tick = 0

    for msg in track:
        abs_tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            pending[(msg.channel, msg.note)] = (abs_tick, msg.velocity)
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            key = (msg.channel, msg.note)
            if key in pending:
                start, vel = pending.pop(key)
                dur = abs_tick - start
                if dur > 0:
                    notes.append(Note(pitch=msg.note, velocity=vel,
                                      start_tick=start, duration_ticks=dur,
                                      channel=msg.channel))
    notes.sort(key=lambda n: n.start_tick)
    return notes


# ---------------------------------------------------------------------------
#  Analysis helpers
# ---------------------------------------------------------------------------

def detect_key(notes: list[Note]) -> tuple[str, str]:
    """Estimate the musical key using pitch-class histogram correlation.

    Returns a tuple *(root_name, mode)* such as ``("C", "major")``.
    Uses the Krumhansl-Schmuckler algorithm with standard profiles.
    """
    if not notes:
        return ("C", "major")

    histogram = np.zeros(12, dtype=float)
    for n in notes:
        histogram[n.pitch % 12] += n.duration_ticks

    if histogram.sum() == 0:
        return ("C", "major")

    best_corr = -2.0
    best_root = 0
    best_mode = "major"

    for root in range(12):
        rotated = np.roll(histogram, -root)
        for profile, mode in [(_MAJOR_PROFILE, "major"), (_MINOR_PROFILE, "minor")]:
            corr = float(np.corrcoef(rotated, profile)[0, 1])
            if corr > best_corr:
                best_corr = corr
                best_root = root
                best_mode = mode

    return (NOTE_NAMES[best_root], best_mode)


def detect_tempo(midi_file: mido.MidiFile) -> float:
    """Extract the first tempo value from a :class:`mido.MidiFile`.

    Falls back to 120.0 BPM if no set_tempo message is found.
    """
    for track in midi_file.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                return mido.tempo2bpm(msg.tempo)
    return 120.0


def notes_stats(notes: list[Note]) -> dict:
    """Compute descriptive statistics for a note list.

    Returned dict keys: *count*, *pitch_min*, *pitch_max*, *pitch_mean*,
    *velocity_min*, *velocity_max*, *velocity_mean*, *total_duration_ticks*,
    *avg_duration_ticks*, *density* (notes per beat at 480 tpb).
    """
    if not notes:
        return {
            "count": 0, "pitch_min": 0, "pitch_max": 0, "pitch_mean": 0.0,
            "velocity_min": 0, "velocity_max": 0, "velocity_mean": 0.0,
            "total_duration_ticks": 0, "avg_duration_ticks": 0.0, "density": 0.0,
        }

    pitches = [n.pitch for n in notes]
    vels = [n.velocity for n in notes]
    durs = [n.duration_ticks for n in notes]
    span = max(n.end_tick for n in notes) - min(n.start_tick for n in notes)
    beats = span / TICKS_PER_BEAT if span > 0 else 1.0

    return {
        "count": len(notes),
        "pitch_min": min(pitches),
        "pitch_max": max(pitches),
        "pitch_mean": round(float(np.mean(pitches)), 2),
        "velocity_min": min(vels),
        "velocity_max": max(vels),
        "velocity_mean": round(float(np.mean(vels)), 2),
        "total_duration_ticks": sum(durs),
        "avg_duration_ticks": round(float(np.mean(durs)), 2),
        "density": round(len(notes) / beats, 3),
    }


# ---------------------------------------------------------------------------
#  Transformations
# ---------------------------------------------------------------------------

def scale_snap(notes: list[Note], key: str, scale: str) -> list[Note]:
    """Return a copy of *notes* with every pitch snapped to the nearest
    degree of the given *key* and *scale*.
    """
    root = key_name_to_root(key)
    valid = get_scale_pitches(root, scale)
    if not valid:
        return [n.copy() for n in notes]

    valid_arr = np.array(valid)
    result: list[Note] = []
    for n in notes:
        idx = int(np.argmin(np.abs(valid_arr - n.pitch)))
        nn = n.copy()
        nn.pitch = valid_arr[idx]
        result.append(nn)
    return result


def transpose_notes(notes: list[Note], semitones: int) -> list[Note]:
    """Return a transposed copy of *notes*, clamping to MIDI range 0–127."""
    result: list[Note] = []
    for n in notes:
        nn = n.copy()
        nn.pitch = max(0, min(127, n.pitch + semitones))
        result.append(nn)
    return result


def merge_overlapping_notes(notes: list[Note]) -> list[Note]:
    """Merge notes that overlap on the same pitch and channel.

    When two notes overlap, they are combined into a single note spanning
    the union of their time ranges.  The higher velocity is preserved.
    """
    if not notes:
        return []

    grouped: dict[tuple[int, int], list[Note]] = {}
    for n in notes:
        grouped.setdefault((n.pitch, n.channel), []).append(n)

    result: list[Note] = []
    for (_pitch, _ch), group in grouped.items():
        group.sort(key=lambda n: n.start_tick)
        merged = group[0].copy()
        for n in group[1:]:
            if n.start_tick <= merged.end_tick:
                new_end = max(merged.end_tick, n.end_tick)
                merged.duration_ticks = new_end - merged.start_tick
                merged.velocity = max(merged.velocity, n.velocity)
            else:
                result.append(merged)
                merged = n.copy()
        result.append(merged)

    result.sort(key=lambda n: n.start_tick)
    return result


def split_by_bars(
    notes: list[Note], tpb: int = TICKS_PER_BEAT, time_sig_num: int = 4
) -> list[list[Note]]:
    """Split *notes* into per-bar groups.

    A note is placed in the bar where its start_tick falls.  Empty bars are
    included so that indices correspond to bar numbers.
    """
    if not notes:
        return []

    ticks_per_bar = tpb * time_sig_num
    max_tick = max(n.end_tick for n in notes)
    num_bars = max_tick // ticks_per_bar + 1
    bars: list[list[Note]] = [[] for _ in range(num_bars)]

    for n in notes:
        bar_idx = n.start_tick // ticks_per_bar
        if bar_idx < num_bars:
            bars[bar_idx].append(n)

    return bars


def velocity_curve(notes: list[Note], curve_type: str = "linear") -> list[Note]:
    """Apply a velocity curve across *notes* ordered by start time.

    Supported *curve_type* values: ``"linear"``, ``"exponential"``,
    ``"logarithmic"``, ``"s-curve"``.  The curve maps position (0→1)
    to a velocity scale factor (0→1) applied multiplicatively.
    """
    if not notes:
        return []

    ordered = sorted(notes, key=lambda n: n.start_tick)
    count = len(ordered)
    result: list[Note] = []

    for i, n in enumerate(ordered):
        t = i / max(count - 1, 1)  # normalised position 0‥1

        if curve_type == "exponential":
            factor = t ** 2
        elif curve_type == "logarithmic":
            factor = math.sqrt(t)
        elif curve_type == "s-curve":
            # Smooth-step (Hermite)
            factor = t * t * (3.0 - 2.0 * t)
        else:  # linear
            factor = t

        nn = n.copy()
        nn.velocity = max(1, min(127, int(n.velocity * factor)))
        result.append(nn)

    return result
