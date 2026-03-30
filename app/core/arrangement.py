"""
Arrangement Engine — timeline, clips, scenes, markers, track groups,
time signature changes, key changes, session view clip launching.

Covers: arrangement view, session clips, scene launching, follow actions,
markers, track groups, time/key changes mid-song, chord track,
global time selection, clip operations.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional, Callable

import numpy as np

from core.models import Note, Track, TICKS_PER_BEAT


# ── Clip ───────────────────────────────────────────────────────────────────

@dataclass
class Clip:
    """A clip containing MIDI notes or audio reference, placeable on timeline."""
    name: str = ""
    color: str = "#B0B0B0"
    # MIDI content
    notes: list[Note] = field(default_factory=list)
    # Timing
    start_tick: int = 0
    length_ticks: int = TICKS_PER_BEAT * 4   # default 1 bar
    # Loop
    loop_enabled: bool = False
    loop_start: int = 0
    loop_length: int = TICKS_PER_BEAT * 4
    # Audio reference
    audio_clip_id: str = ""     # reference to AudioClip
    # Playback state
    playing: bool = False
    queued: bool = False
    # Follow action
    follow_action: str = "none"    # none, next, previous, first, last, random, stop
    follow_time_bars: int = 1

    @property
    def end_tick(self) -> int:
        return self.start_tick + self.length_ticks

    def copy(self) -> Clip:
        c = copy.copy(self)
        c.notes = [n.copy() for n in self.notes]
        return c

    def split_at(self, tick: int) -> tuple[Clip, Clip]:
        """Split clip at absolute tick position."""
        rel = tick - self.start_tick
        if rel <= 0 or rel >= self.length_ticks:
            return self, Clip()
        left = self.copy()
        left.length_ticks = rel
        left.notes = [n for n in left.notes if n.start_tick < rel]
        right = self.copy()
        right.start_tick = tick
        right.length_ticks = self.length_ticks - rel
        right.notes = [Note(
            pitch=n.pitch, velocity=n.velocity,
            start_tick=n.start_tick - rel, duration_ticks=n.duration_ticks,
            channel=n.channel, articulation=n.articulation,
            role=n.role, transition=n.transition
        ) for n in self.notes if n.start_tick >= rel]
        return left, right

    def merge_with(self, other: Clip) -> Clip:
        """Merge another clip into this one."""
        merged = self.copy()
        offset = other.start_tick - self.start_tick
        for n in other.notes:
            new_note = n.copy()
            new_note.start_tick += offset
            merged.notes.append(new_note)
        merged.length_ticks = max(self.length_ticks, offset + other.length_ticks)
        merged.notes.sort(key=lambda n: n.start_tick)
        return merged


# ── Clip Slot (Session View) ──────────────────────────────────────────────

@dataclass
class ClipSlot:
    """A slot in the session view grid."""
    clip: Optional[Clip] = None
    track_index: int = 0
    scene_index: int = 0
    playing: bool = False
    queued: bool = False
    recording: bool = False


# ── Scene ──────────────────────────────────────────────────────────────────

@dataclass
class Scene:
    """A horizontal row of clip slots (one per track)."""
    name: str = ""
    tempo: Optional[float] = None           # scene-specific tempo
    time_signature: Optional[tuple[int, int]] = None
    color: str = "#1E1E1E"

    def copy(self) -> Scene:
        return copy.copy(self)


# ── Marker ─────────────────────────────────────────────────────────────────

@dataclass
class Marker:
    """Timeline marker/locator."""
    name: str = ""
    tick: int = 0
    color: str = "#C0C0C0"
    marker_type: str = "marker"   # marker, cue, loop_start, loop_end, punch_in, punch_out

    def copy(self) -> Marker:
        return copy.copy(self)


# ── Time Signature Change ─────────────────────────────────────────────────

@dataclass
class TimeSignatureEvent:
    """Time signature change at a specific tick."""
    tick: int = 0
    numerator: int = 4
    denominator: int = 4

    @property
    def beats_per_bar(self) -> int:
        return self.numerator


# ── Key Change ─────────────────────────────────────────────────────────────

@dataclass
class KeyChangeEvent:
    """Key/scale change at a specific tick."""
    tick: int = 0
    key: str = "C"
    scale: str = "major"


# ── Chord Event (Chord Track) ─────────────────────────────────────────────

@dataclass
class ChordEvent:
    """A chord displayed on the chord track."""
    tick: int = 0
    duration_ticks: int = TICKS_PER_BEAT * 4
    chord_name: str = "C"        # e.g. "Am7", "Dm/F", "G7sus4"
    voicing: str = ""            # optional voicing description

    @property
    def end_tick(self) -> int:
        return self.tick + self.duration_ticks

    def copy(self) -> ChordEvent:
        return copy.copy(self)


# ── Track Group ────────────────────────────────────────────────────────────

@dataclass
class TrackGroup:
    """A group of tracks that can be folded/expanded."""
    name: str = "Group"
    track_indices: list[int] = field(default_factory=list)
    color: str = "#707070"
    folded: bool = False
    muted: bool = False
    solo: bool = False
    volume: float = 1.0
    pan: float = 0.5

    def copy(self) -> TrackGroup:
        g = copy.copy(self)
        g.track_indices = list(self.track_indices)
        return g


# ── Arrangement Manager ───────────────────────────────────────────────────

class ArrangementManager:
    """Manages the full arrangement: clips, scenes, markers, groups, events."""

    def __init__(self):
        # Session view
        self.clip_slots: list[list[ClipSlot]] = []    # [track_idx][scene_idx]
        self.scenes: list[Scene] = []
        self.num_scenes = 8

        # Arrangement view
        self.arrangement_clips: dict[int, list[Clip]] = {}  # track_idx → clips

        # Timeline events
        self.markers: list[Marker] = []
        self.time_sig_events: list[TimeSignatureEvent] = [TimeSignatureEvent()]
        self.key_changes: list[KeyChangeEvent] = [KeyChangeEvent(0, "C", "minor")]
        self.chord_track: list[ChordEvent] = []

        # Track organization
        self.track_groups: list[TrackGroup] = []
        self.track_order: list[int] = []          # display order
        self.track_heights: dict[int, int] = {}   # track_idx → pixel height

        # Selection
        self.selection_start: int = -1
        self.selection_end: int = -1

        # Initialize scenes
        for i in range(self.num_scenes):
            self.scenes.append(Scene(name=f"Scene {i + 1}"))

    # ── Session View ──

    def ensure_slots(self, num_tracks: int):
        """Ensure clip_slots grid matches track count."""
        while len(self.clip_slots) < num_tracks:
            row = [ClipSlot(track_index=len(self.clip_slots), scene_index=j)
                   for j in range(self.num_scenes)]
            self.clip_slots.append(row)

    def set_clip(self, track_idx: int, scene_idx: int, clip: Clip):
        self.ensure_slots(track_idx + 1)
        if scene_idx < len(self.clip_slots[track_idx]):
            self.clip_slots[track_idx][scene_idx].clip = clip

    def launch_clip(self, track_idx: int, scene_idx: int):
        """Launch a clip in the session view."""
        self.ensure_slots(track_idx + 1)
        # Stop all other clips on this track
        for slot in self.clip_slots[track_idx]:
            slot.playing = False
            slot.queued = False
        slot = self.clip_slots[track_idx][scene_idx]
        if slot.clip:
            slot.playing = True
            slot.clip.playing = True

    def launch_scene(self, scene_idx: int):
        """Launch all clips in a scene."""
        for track_slots in self.clip_slots:
            if scene_idx < len(track_slots):
                for s in track_slots:
                    s.playing = False
                track_slots[scene_idx].playing = True
                if track_slots[scene_idx].clip:
                    track_slots[scene_idx].clip.playing = True

    def stop_all_clips(self):
        for track_slots in self.clip_slots:
            for slot in track_slots:
                slot.playing = False
                slot.queued = False
                if slot.clip:
                    slot.clip.playing = False

    # ── Arrangement View ──

    def add_arrangement_clip(self, track_idx: int, clip: Clip):
        if track_idx not in self.arrangement_clips:
            self.arrangement_clips[track_idx] = []
        self.arrangement_clips[track_idx].append(clip)
        self.arrangement_clips[track_idx].sort(key=lambda c: c.start_tick)

    def remove_arrangement_clip(self, track_idx: int, clip: Clip):
        if track_idx in self.arrangement_clips:
            clips = self.arrangement_clips[track_idx]
            if clip in clips:
                clips.remove(clip)

    def get_clips_in_range(self, track_idx: int, start: int, end: int) -> list[Clip]:
        clips = self.arrangement_clips.get(track_idx, [])
        return [c for c in clips if c.end_tick > start and c.start_tick < end]

    def split_clip(self, track_idx: int, clip: Clip, tick: int):
        """Split a clip at the given tick."""
        left, right = clip.split_at(tick)
        if track_idx in self.arrangement_clips:
            clips = self.arrangement_clips[track_idx]
            if clip in clips:
                idx = clips.index(clip)
                clips[idx] = left
                if right.length_ticks > 0:
                    clips.insert(idx + 1, right)

    def merge_clips(self, track_idx: int, clip1: Clip, clip2: Clip):
        """Merge two adjacent clips."""
        merged = clip1.merge_with(clip2)
        if track_idx in self.arrangement_clips:
            clips = self.arrangement_clips[track_idx]
            if clip1 in clips:
                clips.remove(clip1)
            if clip2 in clips:
                clips.remove(clip2)
            clips.append(merged)
            clips.sort(key=lambda c: c.start_tick)

    # ── Markers ──

    def add_marker(self, name: str, tick: int, marker_type: str = "marker",
                   color: str = "#C0C0C0"):
        self.markers.append(Marker(name, tick, color, marker_type))
        self.markers.sort(key=lambda m: m.tick)

    def remove_marker(self, tick: int, tolerance: int = 100):
        self.markers = [m for m in self.markers if abs(m.tick - tick) > tolerance]

    def get_markers_in_range(self, start: int, end: int) -> list[Marker]:
        return [m for m in self.markers if start <= m.tick <= end]

    # ── Time Signature ──

    def add_time_sig_change(self, tick: int, numerator: int, denominator: int):
        self.time_sig_events.append(TimeSignatureEvent(tick, numerator, denominator))
        self.time_sig_events.sort(key=lambda e: e.tick)

    def get_time_sig_at(self, tick: int) -> TimeSignatureEvent:
        result = self.time_sig_events[0]
        for ev in self.time_sig_events:
            if ev.tick <= tick:
                result = ev
            else:
                break
        return result

    # ── Key Changes ──

    def add_key_change(self, tick: int, key: str, scale: str):
        self.key_changes.append(KeyChangeEvent(tick, key, scale))
        self.key_changes.sort(key=lambda e: e.tick)

    def get_key_at(self, tick: int) -> KeyChangeEvent:
        result = self.key_changes[0] if self.key_changes else KeyChangeEvent()
        for ev in self.key_changes:
            if ev.tick <= tick:
                result = ev
            else:
                break
        return result

    # ── Chord Track ──

    def add_chord(self, tick: int, chord_name: str, duration: int = TICKS_PER_BEAT * 4):
        self.chord_track.append(ChordEvent(tick, duration, chord_name))
        self.chord_track.sort(key=lambda c: c.tick)

    def get_chord_at(self, tick: int) -> Optional[ChordEvent]:
        for c in reversed(self.chord_track):
            if c.tick <= tick < c.end_tick:
                return c
        return None

    # ── Track Groups ──

    def create_group(self, name: str, track_indices: list[int]) -> TrackGroup:
        group = TrackGroup(name=name, track_indices=track_indices)
        self.track_groups.append(group)
        return group

    def remove_group(self, index: int):
        if 0 <= index < len(self.track_groups):
            self.track_groups.pop(index)

    def get_group_for_track(self, track_idx: int) -> Optional[TrackGroup]:
        for g in self.track_groups:
            if track_idx in g.track_indices:
                return g
        return None

    # ── Selection ──

    def set_selection(self, start: int, end: int):
        self.selection_start = min(start, end)
        self.selection_end = max(start, end)

    def clear_selection(self):
        self.selection_start = -1
        self.selection_end = -1

    def delete_selection(self, track_indices: list[int]):
        """Delete all clip content in the selected range."""
        if self.selection_start < 0:
            return
        for idx in track_indices:
            clips = self.arrangement_clips.get(idx, [])
            self.arrangement_clips[idx] = [
                c for c in clips
                if c.end_tick <= self.selection_start or c.start_tick >= self.selection_end
            ]

    # ── Track Order ──

    def move_track(self, from_idx: int, to_idx: int):
        if from_idx in self.track_order and to_idx <= len(self.track_order):
            self.track_order.remove(from_idx)
            self.track_order.insert(to_idx, from_idx)

    def set_track_height(self, track_idx: int, height: int):
        self.track_heights[track_idx] = max(40, min(height, 200))

    def copy(self) -> ArrangementManager:
        mgr = ArrangementManager()
        mgr.markers = [m.copy() for m in self.markers]
        mgr.time_sig_events = [copy.copy(e) for e in self.time_sig_events]
        mgr.key_changes = [copy.copy(e) for e in self.key_changes]
        mgr.chord_track = [c.copy() for c in self.chord_track]
        mgr.track_groups = [g.copy() for g in self.track_groups]
        mgr.track_order = list(self.track_order)
        mgr.scenes = [s.copy() for s in self.scenes]
        return mgr
