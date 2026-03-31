"""
Automation Engine — parameter automation, MIDI CC editing, tempo/time sig changes.

Covers: MIDI CC lanes, pitch bend, aftertouch, volume/pan automation,
tempo automation, automation curves, recording modes, program change.
"""
from __future__ import annotations

import bisect
import copy
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ── Automation Point ───────────────────────────────────────────────────────

@dataclass
class AutomationPoint:
    """Single automation point with curve type."""
    tick: int = 0
    value: float = 0.0          # normalized 0-1 (mapped to parameter range)
    curve: str = "linear"       # linear, exponential, logarithmic, s_curve, step

    def copy(self) -> AutomationPoint:
        return copy.copy(self)


# ── Automation Lane ────────────────────────────────────────────────────────

@dataclass
class AutomationLane:
    """A single automation parameter lane for a track."""
    name: str = ""                   # display name
    param_type: str = ""             # cc, pitch_bend, aftertouch, volume, pan, tempo, mute, send
    param_id: int = 0                # CC number, or 0 for non-CC params
    track_index: int = -1            # -1 for global (tempo, time_sig)
    points: list[AutomationPoint] = field(default_factory=list)
    min_value: float = 0.0
    max_value: float = 127.0
    default_value: float = 64.0
    visible: bool = True
    armed: bool = False              # for automation recording
    # Recording mode
    record_mode: str = "touch"       # write, read, touch, latch

    def add_point(self, tick: int, value: float, curve: str = "linear"):
        """Add or update a point at the given tick."""
        # Remove existing point at same tick
        self.points = [p for p in self.points if p.tick != tick]
        self.points.append(AutomationPoint(tick, value, curve))
        self.points.sort(key=lambda p: p.tick)

    def remove_point(self, tick: int, tolerance: int = 10):
        """Remove point near the given tick."""
        self.points = [p for p in self.points if abs(p.tick - tick) > tolerance]

    def clear_range(self, start_tick: int, end_tick: int):
        """Remove all points in range."""
        self.points = [p for p in self.points if p.tick < start_tick or p.tick > end_tick]

    def get_value_at(self, tick: int) -> float:
        """Get interpolated value at the given tick."""
        if not self.points:
            return self.default_value

        # Before first point
        if tick <= self.points[0].tick:
            return self.points[0].value

        # After last point
        if tick >= self.points[-1].tick:
            return self.points[-1].value

        # Find surrounding points
        ticks = [p.tick for p in self.points]
        idx = bisect.bisect_right(ticks, tick) - 1
        idx = max(0, min(idx, len(self.points) - 2))

        p1 = self.points[idx]
        p2 = self.points[idx + 1]

        if p1.tick == p2.tick:
            return p2.value

        # Interpolate
        t = (tick - p1.tick) / (p2.tick - p1.tick)
        return _interpolate(p1.value, p2.value, t, p2.curve)

    def get_scaled_value_at(self, tick: int) -> float:
        """Get value scaled to actual parameter range."""
        raw = self.get_value_at(tick)
        return self.min_value + raw * (self.max_value - self.min_value)

    def to_midi_events(self, ticks_per_beat: int = 480,
                       resolution_ticks: int = 24) -> list[tuple[int, int]]:
        """Generate (tick, value) pairs at given resolution for MIDI output."""
        if not self.points:
            return []
        start = self.points[0].tick
        end = self.points[-1].tick
        events = []
        tick = start
        while tick <= end:
            val = int(self.get_scaled_value_at(tick))
            val = max(int(self.min_value), min(int(self.max_value), val))
            events.append((tick, val))
            tick += resolution_ticks
        return events

    def copy(self) -> AutomationLane:
        lane = AutomationLane(
            name=self.name, param_type=self.param_type,
            param_id=self.param_id, track_index=self.track_index,
            min_value=self.min_value, max_value=self.max_value,
            default_value=self.default_value, visible=self.visible,
        )
        lane.points = [p.copy() for p in self.points]
        return lane


def _interpolate(v1: float, v2: float, t: float, curve: str) -> float:
    """Interpolate between v1 and v2 at position t (0-1)."""
    if curve == "step":
        return v1
    elif curve == "exponential":
        t = t * t
    elif curve == "logarithmic":
        t = 1 - (1 - t) ** 2
    elif curve == "s_curve":
        t = t * t * (3 - 2 * t)
    # linear: t unchanged
    return v1 + (v2 - v1) * t


# ── Common CC Automation Presets ───────────────────────────────────────────

CC_PRESETS = {
    "Volume": (7, 0, 127, 100),
    "Pan": (10, 0, 127, 64),
    "Expression": (11, 0, 127, 127),
    "Modulation": (1, 0, 127, 0),
    "Sustain Pedal": (64, 0, 127, 0),
    "Breath": (2, 0, 127, 0),
    "Portamento": (5, 0, 127, 0),
    "Filter Cutoff": (74, 0, 127, 64),
    "Filter Resonance": (71, 0, 127, 0),
    "Release Time": (72, 0, 127, 64),
    "Attack Time": (73, 0, 127, 64),
    "Reverb Send": (91, 0, 127, 0),
    "Chorus Send": (93, 0, 127, 0),
}


def create_cc_lane(cc_name: str, track_index: int = 0) -> AutomationLane:
    """Create an automation lane for a common CC parameter."""
    if cc_name in CC_PRESETS:
        cc_num, min_v, max_v, default = CC_PRESETS[cc_name]
        return AutomationLane(
            name=cc_name, param_type="cc", param_id=cc_num,
            track_index=track_index,
            min_value=min_v, max_value=max_v, default_value=default,
        )
    return AutomationLane(name=cc_name, track_index=track_index)


def create_pitch_bend_lane(track_index: int = 0) -> AutomationLane:
    return AutomationLane(
        name="Pitch Bend", param_type="pitch_bend", param_id=0,
        track_index=track_index,
        min_value=-8192, max_value=8191, default_value=0,
    )


def create_aftertouch_lane(track_index: int = 0) -> AutomationLane:
    return AutomationLane(
        name="Aftertouch", param_type="aftertouch", param_id=0,
        track_index=track_index,
        min_value=0, max_value=127, default_value=0,
    )


def create_tempo_lane(default_bpm: float = 120.0) -> AutomationLane:
    return AutomationLane(
        name="Tempo", param_type="tempo", param_id=0,
        track_index=-1,
        min_value=20, max_value=300, default_value=default_bpm,
    )


def create_program_change_lane(track_index: int = 0) -> AutomationLane:
    return AutomationLane(
        name="Program Change", param_type="program_change", param_id=0,
        track_index=track_index,
        min_value=0, max_value=127, default_value=0,
    )


# ── Automation Manager ─────────────────────────────────────────────────────

class AutomationManager:
    """Manages all automation lanes for a project."""

    def __init__(self):
        self.lanes: list[AutomationLane] = []
        self._recording = False
        self._record_lane: Optional[AutomationLane] = None
        self._last_record_tick = 0

    def add_lane(self, lane: AutomationLane) -> int:
        self.lanes.append(lane)
        return len(self.lanes) - 1

    def remove_lane(self, index: int):
        if 0 <= index < len(self.lanes):
            self.lanes.pop(index)

    def get_lanes_for_track(self, track_index: int) -> list[AutomationLane]:
        return [l for l in self.lanes if l.track_index == track_index]

    def get_global_lanes(self) -> list[AutomationLane]:
        return [l for l in self.lanes if l.track_index == -1]

    def get_cc_value(self, track_index: int, cc_number: int, tick: int) -> Optional[float]:
        for lane in self.lanes:
            if (lane.track_index == track_index and
                    lane.param_type == "cc" and lane.param_id == cc_number):
                return lane.get_scaled_value_at(tick)
        return None

    def get_tempo_at(self, tick: int) -> Optional[float]:
        for lane in self.lanes:
            if lane.param_type == "tempo":
                return lane.get_scaled_value_at(tick)
        return None

    # Recording
    def start_recording(self, lane: AutomationLane):
        self._recording = True
        self._record_lane = lane
        lane.armed = True

    def record_value(self, tick: int, value: float):
        if self._recording and self._record_lane:
            self._record_lane.add_point(tick, value)
            self._last_record_tick = tick

    def stop_recording(self):
        if self._record_lane:
            self._record_lane.armed = False
        self._recording = False
        self._record_lane = None

    def clear_all(self):
        self.lanes.clear()

    def copy(self) -> AutomationManager:
        mgr = AutomationManager()
        mgr.lanes = [l.copy() for l in self.lanes]
        return mgr
