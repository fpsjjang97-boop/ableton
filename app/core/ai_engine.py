"""
AI Engine for the MIDI AI Workstation.

Self-contained generation and variation engine that provides musically
intelligent MIDI manipulation.  All public methods return new Track objects
and never mutate their inputs.
"""
from __future__ import annotations

import copy
import math
from typing import Optional

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
# Constants
# ---------------------------------------------------------------------------

_BEAT = TICKS_PER_BEAT
_BAR = _BEAT * 4
_PHRASE = _BAR * 4  # 4-bar phrase

# Common chord-progression templates expressed as 1-indexed scale degrees.
_PROGRESSIONS = {
    "major": [
        [1, 5, 6, 4],       # I-V-vi-IV
        [1, 4, 5, 4],       # I-IV-V-IV
        [1, 6, 4, 5],       # I-vi-IV-V
        [1, 4, 6, 5],       # I-IV-vi-V
        [1, 5, 4, 5],       # I-V-IV-V
    ],
    "minor": [
        [1, 4, 7, 3],       # i-iv-VII-III
        [1, 6, 3, 7],       # i-VI-III-VII
        [1, 4, 5, 1],       # i-iv-v-i
        [1, 7, 6, 7],       # i-VII-VI-VII
        [1, 3, 4, 5],       # i-III-iv-v
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snap_to_scale(pitch: int, scale_pitches: list[int]) -> int:
    """Return the nearest pitch that belongs to *scale_pitches*."""
    if pitch in scale_pitches:
        return pitch
    arr = np.asarray(scale_pitches)
    idx = int(np.argmin(np.abs(arr - pitch)))
    return int(arr[idx])


def _clamp_pitch(p: int) -> int:
    return max(0, min(127, p))


def _clamp_vel(v: int) -> int:
    return max(1, min(127, v))


def _scale_degree_to_pitch(
    degree: int,
    root: int,
    scale: str,
    octave: int = 4,
) -> int:
    """Convert 1-indexed scale degree to a MIDI pitch.

    Degrees > len(intervals) wrap into the next octave automatically.
    """
    intervals = SCALE_INTERVALS.get(scale, SCALE_INTERVALS["minor"])
    n = len(intervals)
    idx = (degree - 1) % n
    oct_offset = (degree - 1) // n
    return _clamp_pitch((octave + 1 + oct_offset) * 12 + root + intervals[idx])


def _build_chord_pitches(
    degree: int,
    root: int,
    scale: str,
    octave: int = 3,
    voicing: str = "triad",
) -> list[int]:
    """Build chord pitches for a scale degree with the requested voicing."""
    intervals = SCALE_INTERVALS.get(scale, SCALE_INTERVALS["minor"])
    n = len(intervals)

    def _deg_pitch(d: int) -> int:
        idx = (d - 1) % n
        oc = (d - 1) // n
        return _clamp_pitch((octave + 1 + oc) * 12 + root + intervals[idx])

    pitches = [_deg_pitch(degree)]
    if voicing in ("triad", "seventh", "spread"):
        pitches.append(_deg_pitch(degree + 2))  # 3rd
        pitches.append(_deg_pitch(degree + 4))  # 5th
    if voicing == "seventh":
        pitches.append(_deg_pitch(degree + 6))  # 7th
    if voicing == "spread":
        # Drop the middle note down an octave for open voicing.
        if len(pitches) >= 3:
            pitches[1] = _clamp_pitch(pitches[1] - 12)
    return sorted(pitches)


# ---------------------------------------------------------------------------
# AIEngine
# ---------------------------------------------------------------------------

class AIEngine:
    """High-level, musically-aware MIDI generation and variation engine.

    Every public method returns a **new** ``Track`` and never modifies the
    inputs.  Internally uses numpy for all stochastic operations so results
    are reproducible when a seed is provided.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.default_rng(seed)
        # Harmony engine (rule DB v2.07)
        self._harmony_engine = None
        try:
            from core.harmony_engine import HarmonyEngine
            self._harmony_engine = HarmonyEngine()
        except Exception:
            pass
        # Pattern DB (pattern_library/*.json)
        self._pattern_db = None
        try:
            from core.pattern_db import PatternDB
            self._pattern_db = PatternDB.get()
        except Exception:
            pass
        # Similarity engine (embeddings)
        self._similarity_engine = None
        try:
            from core.similarity_engine import SimilarityEngine
            self._similarity_engine = SimilarityEngine()
        except Exception:
            pass
        # Prompt parser
        self._prompt_parser = None
        try:
            from core.prompt_parser import PromptParser
            self._prompt_parser = PromptParser()
        except Exception:
            pass

    @property
    def harmony_engine(self):
        return self._harmony_engine

    @property
    def pattern_db(self):
        return self._pattern_db

    @property
    def similarity_engine(self):
        return self._similarity_engine

    def parse_prompt(self, prompt: str) -> dict:
        """Parse a natural language prompt into generation parameters."""
        if self._prompt_parser and prompt:
            return self._prompt_parser.parse(prompt)
        return {}

    def generate_from_prompt(
        self,
        params: dict,
        project_key: str = "C",
        project_scale: str = "minor",
    ) -> Track:
        """Generate a track from UI params + optional prompt.

        Merges prompt-parsed params with UI params, queries PatternDB
        for chord progressions, and generates with HarmonyEngine voicing.
        """
        # Parse prompt if present
        if params.get("prompt") and self._prompt_parser:
            prompt_params = self._prompt_parser.parse(params["prompt"])
            merged = self._prompt_parser.merge_with_ui(prompt_params, params)
        else:
            merged = dict(params)

        key = merged.get("key", project_key)
        scale = merged.get("scale", project_scale)
        style = merged.get("style", "pop")
        kind = merged.get("track_type", "melody")
        length_bars = merged.get("length_bars", 8)
        length_beats = length_bars * 4
        density = merged.get("density", 0.6)

        if kind == "chords":
            return self.generate_chords(key, scale, length_beats, style)
        elif kind == "bass":
            return self.generate_bass(key, scale, length_beats, style)
        else:
            return self.generate_melody(key, scale, length_beats, style, density)

    # ------------------------------------------------------------------
    # 1. Variation
    # ------------------------------------------------------------------

    def generate_variation(
        self,
        track: Track,
        variation_type: str = "mixed",
        intensity: float = 0.5,
        key: str = "C",
        scale: str = "minor",
    ) -> Track:
        """Create a variation of *track*.

        Parameters
        ----------
        variation_type : str
            One of ``rhythm``, ``melody``, ``harmony``, ``dynamics``,
            ``ornament``, ``mixed``.
        intensity : float  (0.0 – 1.0)
            How far the variation should deviate from the original.
        """
        intensity = max(0.0, min(1.0, intensity))
        dispatch = {
            "rhythm": self._var_rhythm,
            "melody": self._var_melody,
            "harmony": self._var_harmony,
            "dynamics": self._var_dynamics,
            "ornament": self._var_ornament,
        }
        if variation_type == "mixed":
            result = track.copy()
            types = list(dispatch.keys())
            chosen = self.rng.choice(
                types,
                size=max(2, int(len(types) * intensity)),
                replace=False,
            )
            for vt in chosen:
                result = dispatch[vt](result, intensity, key, scale)
            return result

        fn = dispatch.get(variation_type)
        if fn is None:
            raise ValueError(f"Unknown variation type: {variation_type}")
        return fn(track, intensity, key, scale)

    # -- variation helpers -----------------------------------------------

    def _var_rhythm(
        self, track: Track, intensity: float, key: str, scale: str,
    ) -> Track:
        """Keep pitches; shift start times and tweak durations."""
        out = track.copy()
        max_shift = int(_BEAT * intensity)
        grid = max(1, _BEAT // 4)
        for note in out.notes:
            shift = int(self.rng.integers(-max_shift, max_shift + 1))
            shift = round(shift / grid) * grid
            note.start_tick = max(0, note.start_tick + shift)
            dur_scale = 1.0 + self.rng.uniform(-0.4 * intensity, 0.4 * intensity)
            note.duration_ticks = max(grid, int(note.duration_ticks * dur_scale))
        out.notes.sort(key=lambda n: n.start_tick)
        return out

    def _var_melody(
        self, track: Track, intensity: float, key: str, scale: str,
    ) -> Track:
        """Keep rhythm; shift pitches within the scale."""
        root = key_name_to_root(key)
        sp = get_scale_pitches(root, scale)
        out = track.copy()
        max_steps = max(1, int(7 * intensity))
        for note in out.notes:
            if self.rng.random() < 0.3 + 0.5 * intensity:
                step = int(self.rng.integers(-max_steps, max_steps + 1))
                if note.pitch in sp:
                    idx = sp.index(note.pitch)
                else:
                    idx = int(np.argmin(np.abs(np.asarray(sp) - note.pitch)))
                new_idx = max(0, min(len(sp) - 1, idx + step))
                note.pitch = sp[new_idx]
        return out

    def _var_harmony(
        self, track: Track, intensity: float, key: str, scale: str,
    ) -> Track:
        """Add harmonic notes (3rds, 5ths, octaves) to existing notes."""
        root = key_name_to_root(key)
        sp = get_scale_pitches(root, scale)
        intervals = SCALE_INTERVALS.get(scale, SCALE_INTERVALS["minor"])
        n_iv = len(intervals)
        out = track.copy()
        new_notes: list[Note] = []
        for note in out.notes:
            if self.rng.random() > intensity:
                continue
            choice = self.rng.random()
            if note.pitch in sp:
                idx = sp.index(note.pitch)
            else:
                idx = int(np.argmin(np.abs(np.asarray(sp) - note.pitch)))
            if choice < 0.4:
                # Add a 3rd above
                h_idx = min(idx + 2, len(sp) - 1)
            elif choice < 0.7:
                # Add a 5th above
                h_idx = min(idx + 4, len(sp) - 1)
            else:
                # Octave
                h_idx = min(idx + n_iv, len(sp) - 1)
            h_pitch = sp[h_idx]
            if h_pitch != note.pitch:
                new_notes.append(Note(
                    pitch=h_pitch,
                    velocity=_clamp_vel(note.velocity - 10),
                    start_tick=note.start_tick,
                    duration_ticks=note.duration_ticks,
                    channel=note.channel,
                ))
        out.notes.extend(new_notes)
        out.notes.sort(key=lambda n: n.start_tick)
        return out

    def _var_dynamics(
        self, track: Track, intensity: float, key: str, scale: str,
    ) -> Track:
        """Create velocity curves for musical expression."""
        out = track.copy()
        if not out.notes:
            return out
        total = out.notes[-1].end_tick or 1
        for note in out.notes:
            # Sinusoidal swell across the track
            phase = note.start_tick / total * math.pi * 2
            swell = math.sin(phase) * 30 * intensity
            jitter = int(self.rng.integers(
                int(-20 * intensity), int(20 * intensity) + 1,
            ))
            note.velocity = _clamp_vel(int(note.velocity + swell + jitter))
        return out

    def _var_ornament(
        self, track: Track, intensity: float, key: str, scale: str,
    ) -> Track:
        """Add grace notes, trills and turns."""
        root = key_name_to_root(key)
        sp = get_scale_pitches(root, scale)
        out = track.copy()
        ornaments: list[Note] = []
        grace_dur = max(1, _BEAT // 8)

        for note in out.notes:
            if self.rng.random() > intensity * 0.6:
                continue
            idx = (
                sp.index(note.pitch)
                if note.pitch in sp
                else int(np.argmin(np.abs(np.asarray(sp) - note.pitch)))
            )
            kind = self.rng.random()
            if kind < 0.45:
                # Grace note from below
                g_idx = max(0, idx - 1)
                ornaments.append(Note(
                    pitch=sp[g_idx],
                    velocity=_clamp_vel(note.velocity - 15),
                    start_tick=max(0, note.start_tick - grace_dur),
                    duration_ticks=grace_dur,
                    channel=note.channel,
                ))
            elif kind < 0.75:
                # Trill: two rapid alternations above
                above = min(idx + 1, len(sp) - 1)
                trill_dur = max(1, _BEAT // 6)
                for t in range(3):
                    p = sp[above] if t % 2 == 0 else note.pitch
                    ornaments.append(Note(
                        pitch=p,
                        velocity=_clamp_vel(note.velocity - 20),
                        start_tick=note.start_tick + t * trill_dur,
                        duration_ticks=trill_dur,
                        channel=note.channel,
                    ))
                # Shorten original so it follows the trill
                note.start_tick += 3 * trill_dur
                note.duration_ticks = max(grace_dur, note.duration_ticks - 3 * trill_dur)
            else:
                # Turn: upper-note-main-lower-main
                above = min(idx + 1, len(sp) - 1)
                below = max(0, idx - 1)
                turn_dur = max(1, _BEAT // 8)
                for i, p in enumerate([sp[above], note.pitch, sp[below], note.pitch]):
                    ornaments.append(Note(
                        pitch=p,
                        velocity=_clamp_vel(note.velocity - 10),
                        start_tick=note.start_tick + i * turn_dur,
                        duration_ticks=turn_dur,
                        channel=note.channel,
                    ))
                note.start_tick += 4 * turn_dur
                note.duration_ticks = max(grace_dur, note.duration_ticks - 4 * turn_dur)

        out.notes.extend(ornaments)
        out.notes.sort(key=lambda n: n.start_tick)
        return out

    # ------------------------------------------------------------------
    # 2. Melody generation
    # ------------------------------------------------------------------

    def generate_melody(
        self,
        key: str = "C",
        scale: str = "minor",
        length_beats: int = 16,
        style: str = "pop",
        density: float = 0.6,
        octave: int = 5,
    ) -> Track:
        """Generate a new melody using a weighted random walk.

        Parameters
        ----------
        style : str
            ``ambient`` – sparse, long notes, small intervals.
            ``pop``     – medium density, stepwise motion.
            ``edm``     – dense, repetitive, wider leaps allowed.
        density : float (0.0 – 1.0)
            Probability that a given rhythmic slot contains a note.
        """
        root = key_name_to_root(key)
        sp = get_scale_pitches(root, scale)
        # Restrict to a comfortable range around the target octave.
        lo = (octave + 1) * 12 - 6
        hi = (octave + 1) * 12 + 18
        sp = [p for p in sp if lo <= p <= hi]
        if not sp:
            sp = get_scale_pitches(root, scale)

        style_cfg = self._melody_style(style, density)
        total_ticks = length_beats * _BEAT
        notes: list[Note] = []
        cursor = 0
        idx = len(sp) // 2  # start in the middle of the range
        phrase_len = _PHRASE

        while cursor < total_ticks:
            # Phrase-level tension: ramp up then resolve
            phrase_pos = (cursor % phrase_len) / phrase_len
            tension = math.sin(phrase_pos * math.pi)  # peaks at middle

            # Decide whether to place a note or rest
            note_prob = style_cfg["density"] * (0.7 + 0.3 * tension)
            if self.rng.random() > note_prob:
                cursor += style_cfg["grid"]
                continue

            # Weighted random walk
            max_step = style_cfg["max_step"]
            step = int(self.rng.integers(-max_step, max_step + 1))
            # Bias toward resolution at phrase end
            if phrase_pos > 0.85:
                tonic_idx = self._closest_idx(sp, (octave + 1) * 12 + root)
                step = int(np.sign(tonic_idx - idx)) * max(1, abs(step))
            idx = max(0, min(len(sp) - 1, idx + step))

            # Duration choice (weighted toward style preference)
            dur = int(self.rng.choice(style_cfg["durations"]))
            dur = min(dur, total_ticks - cursor)
            if dur <= 0:
                break

            vel = int(60 + 30 * tension + self.rng.integers(-8, 9))
            notes.append(Note(
                pitch=sp[idx],
                velocity=_clamp_vel(vel),
                start_tick=cursor,
                duration_ticks=dur,
            ))
            cursor += max(style_cfg["grid"], dur)

        track = Track(name="AI Melody", notes=notes, color="#B0B0B0", instrument=0, channel=0)
        return track

    def _melody_style(self, style: str, density: float) -> dict:
        if style == "ambient":
            return {
                "grid": _BEAT,
                "density": max(0.45, density * 0.7),
                "max_step": 2,
                "durations": [_BEAT * 2, _BEAT * 3, _BEAT * 4],
            }
        if style == "edm":
            return {
                "grid": _BEAT // 2,
                "density": min(1.0, density * 1.3),
                "max_step": 4,
                "durations": [_BEAT // 2, _BEAT, _BEAT // 4],
            }
        # pop / default
        return {
            "grid": _BEAT // 2,
            "density": density,
            "max_step": 3,
            "durations": [_BEAT // 2, _BEAT, _BEAT * 2],
        }

    # ------------------------------------------------------------------
    # 3. Chord generation
    # ------------------------------------------------------------------

    def generate_chords(
        self,
        key: str = "C",
        scale: str = "minor",
        length_beats: int = 16,
        style: str = "pop",
        octave: int = 3,
        melody_track: Optional[Track] = None,
    ) -> Track:
        """Generate a chord progression.

        When the harmony engine (rule DB v2.07) is available, uses it for
        melody-aware voicing generation with playability constraints.
        Otherwise falls back to the built-in progression templates.
        """
        # --- Try harmony engine for rule-aware voicing ---
        if self._harmony_engine is not None:
            try:
                return self._generate_chords_with_rules(
                    key, scale, length_beats, style, octave, melody_track
                )
            except Exception:
                pass  # Fall back to basic generation

        # --- Fallback: built-in progression templates ---
        root = key_name_to_root(key)
        family = "minor" if scale in ("minor", "dorian", "minor_penta") else "major"
        progs = _PROGRESSIONS.get(family, _PROGRESSIONS["major"])
        prog = list(progs[int(self.rng.integers(len(progs)))])

        total_ticks = length_beats * _BEAT
        bars = max(1, total_ticks // _BAR)
        # Tile the 4-chord progression to fill the requested length.
        full_prog: list[int] = []
        while len(full_prog) < bars:
            full_prog.extend(prog)
        full_prog = full_prog[:bars]

        voicing = self.rng.choice(["triad", "seventh", "spread"])
        notes: list[Note] = []

        for bar_idx, degree in enumerate(full_prog):
            bar_start = bar_idx * _BAR
            pitches = _build_chord_pitches(degree, root, scale, octave, voicing)

            if style == "ambient":
                # Whole-bar sustained chords
                for p in pitches:
                    notes.append(Note(
                        pitch=p,
                        velocity=_clamp_vel(55 + int(self.rng.integers(-5, 6))),
                        start_tick=bar_start,
                        duration_ticks=_BAR - _BEAT // 4,
                    ))
            elif style == "edm":
                # Pumping quarter-note chords
                for beat in range(4):
                    for p in pitches:
                        notes.append(Note(
                            pitch=p,
                            velocity=_clamp_vel(
                                80 if beat == 0 else 65
                            ),
                            start_tick=bar_start + beat * _BEAT,
                            duration_ticks=_BEAT // 2,
                        ))
            else:
                # Pop/default: half-note strums
                for half in range(2):
                    vel_base = 75 if half == 0 else 65
                    strum_offset = 0
                    for p in pitches:
                        notes.append(Note(
                            pitch=p,
                            velocity=_clamp_vel(vel_base + int(self.rng.integers(-4, 5))),
                            start_tick=bar_start + half * _BEAT * 2 + strum_offset,
                            duration_ticks=_BEAT * 2 - _BEAT // 8,
                        ))
                        strum_offset += int(self.rng.integers(0, _BEAT // 16 + 1))

        track = Track(name="AI Chords", notes=notes, color="#51CF66", instrument=0, channel=1)  # Piano
        return track

    def _generate_chords_with_rules(
        self,
        key: str,
        scale: str,
        length_beats: int,
        style: str,
        octave: int,
        melody_track: Optional[Track] = None,
    ) -> Track:
        """Generate chords using the harmony engine rule DB for voicing.

        Queries PatternDB for real chord progressions when available,
        falls back to built-in templates.
        """
        he = self._harmony_engine
        root = key_name_to_root(key)

        # Try PatternDB first — diatonic-filtered progressions only
        db_chord_labels = None
        if self._pattern_db is not None:
            try:
                candidates = self._pattern_db.query_progressions(
                    key=key, scale=scale, gram_size=4, min_count=2
                )
                if candidates:
                    # Weighted random selection by count
                    weights = np.array([c["count"] for c in candidates], dtype=float)
                    weights /= weights.sum()
                    chosen = candidates[int(self.rng.choice(len(candidates), p=weights))]
                    db_chord_labels = chosen["chords"]
                else:
                    # No diatonic match in DB — generate diatonic progression
                    total_ticks = length_beats * _BEAT
                    bars = max(1, total_ticks // _BAR)
                    db_chord_labels = self._pattern_db.generate_diatonic_progression(
                        key, scale, bars
                    )

                if db_chord_labels:
                    total_ticks = length_beats * _BEAT
                    bars = max(1, total_ticks // _BAR)
                    full_labels = []
                    while len(full_labels) < bars:
                        full_labels.extend(db_chord_labels)
                    full_labels = full_labels[:bars]
                    chord_list = [{"chord": c, "duration": "full"} for c in full_labels]
                    track = he.generate_from_progression(
                        chord_list, key=key, scale=scale,
                        style=style, octave=octave + 1,
                        melody_track=melody_track,
                    )
                    track.name = "AI Chords (Rule DB)"
                    return track
            except Exception:
                pass

        # Fallback: built-in progression templates
        family = "minor" if scale in ("minor", "dorian", "minor_penta") else "major"
        progs = _PROGRESSIONS.get(family, _PROGRESSIONS["major"])
        prog = list(progs[int(self.rng.integers(len(progs)))])

        total_ticks = length_beats * _BEAT
        bars = max(1, total_ticks // _BAR)
        full_prog: list[int] = []
        while len(full_prog) < bars:
            full_prog.extend(prog)
        full_prog = full_prog[:bars]

        # Convert scale degrees to chord labels
        intervals = SCALE_INTERVALS.get(scale, SCALE_INTERVALS["minor"])
        n_int = len(intervals)
        notes: list[Note] = []
        prev_pitches: list[int] = []

        for bar_idx, degree in enumerate(full_prog):
            bar_start = bar_idx * _BAR
            # Determine root pitch class for this degree
            deg_idx = (degree - 1) % n_int
            chord_root_pc = (root + intervals[deg_idx]) % 12
            chord_root_name = NOTE_NAMES[chord_root_pc]

            # Determine chord quality from scale context
            third_idx = (degree + 1) % n_int if degree + 1 <= n_int else (degree + 1 - n_int - 1)
            third_semitones = (intervals[(degree - 1 + 2) % n_int] - intervals[deg_idx]) % 12
            if third_semitones == 3:
                quality = "m7" if self.rng.random() > 0.4 else "min"
            elif third_semitones == 4:
                quality = "maj7" if self.rng.random() > 0.5 else "maj"
            else:
                quality = "maj"

            # Dominant on degree 5
            if degree == 5:
                quality = "7"

            chord_label = f"{chord_root_name}{quality}" if quality != "maj" else chord_root_name

            # Melody protection
            melody_p = None
            if melody_track:
                mel_notes = melody_track.get_notes_in_range(bar_start, bar_start + _BAR)
                if mel_notes:
                    melody_p = max(mel_notes, key=lambda n: n.duration_ticks).pitch

            voicing = he.generate_voicing(
                chord_label,
                bass_octave=octave,
                rh_octave=octave + 1,
                melody_pitch=melody_p,
                style=style,
            )

            if prev_pitches and voicing:
                voicing = he._apply_voice_leading(prev_pitches, voicing)

            # Style-aware note creation
            if style == "ambient":
                for i, p in enumerate(voicing):
                    notes.append(Note(
                        pitch=p,
                        velocity=_clamp_vel(55 + int(self.rng.integers(-5, 6))),
                        start_tick=bar_start,
                        duration_ticks=_BAR - _BEAT // 4,
                        role="bass" if i == 0 else "third",
                    ))
            elif style == "edm":
                for beat in range(4):
                    for i, p in enumerate(voicing):
                        notes.append(Note(
                            pitch=p,
                            velocity=_clamp_vel(80 if beat == 0 else 65),
                            start_tick=bar_start + beat * _BEAT,
                            duration_ticks=_BEAT // 2,
                            role="bass" if i == 0 else "third",
                        ))
            elif style in ("jazz", "lo-fi"):
                for i, p in enumerate(voicing):
                    stagger = i * 10
                    notes.append(Note(
                        pitch=p,
                        velocity=_clamp_vel(65 + int(self.rng.integers(-5, 6))),
                        start_tick=bar_start + stagger,
                        duration_ticks=_BAR - _BEAT // 4,
                        role="bass" if i == 0 else "third",
                    ))
            else:
                for half in range(2):
                    vel_base = 75 if half == 0 else 65
                    strum_offset = 0
                    for i, p in enumerate(voicing):
                        notes.append(Note(
                            pitch=p,
                            velocity=_clamp_vel(vel_base + int(self.rng.integers(-4, 5))),
                            start_tick=bar_start + half * _BEAT * 2 + strum_offset,
                            duration_ticks=_BEAT * 2 - _BEAT // 8,
                            role="bass" if i == 0 else "third",
                        ))
                        strum_offset += int(self.rng.integers(0, _BEAT // 16 + 1))

            prev_pitches = voicing

        track = Track(name="AI Chords (Rule DB)", notes=notes, color="#51CF66", instrument=0, channel=1)  # Piano
        return track

    # ------------------------------------------------------------------
    # 4. Bass-line generation
    # ------------------------------------------------------------------

    def generate_bass(
        self,
        key: str = "C",
        scale: str = "minor",
        length_beats: int = 16,
        style: str = "pop",
        chord_track: Optional[Track] = None,
        octave: int = 2,
    ) -> Track:
        """Generate a bass line, optionally following *chord_track* roots."""
        root = key_name_to_root(key)
        sp = get_scale_pitches(root, scale)
        lo = (octave + 1) * 12 - 2
        hi = (octave + 1) * 12 + 14
        sp_bass = [p for p in sp if lo <= p <= hi]
        if not sp_bass:
            sp_bass = sp

        total_ticks = length_beats * _BEAT
        bars = max(1, total_ticks // _BAR)

        # Determine a root note per bar from chord_track or the scale.
        bar_roots = self._extract_bar_roots(chord_track, bars, sp_bass)

        notes: list[Note] = []
        for bar_idx in range(bars):
            bar_start = bar_idx * _BAR
            br = bar_roots[bar_idx]
            if style == "walking":
                notes.extend(self._bass_walking(br, bar_start, sp_bass))
            elif style == "sustained":
                notes.extend(self._bass_sustained(br, bar_start))
            elif style == "octave":
                notes.extend(self._bass_octave(br, bar_start))
            else:
                # Pop default: root-fifth pattern
                notes.extend(self._bass_pop(br, bar_start, sp_bass))

        track = Track(name="AI Bass", notes=notes, color="#FF922B", instrument=32, channel=2)  # Acoustic Bass
        return track

    def _extract_bar_roots(
        self,
        chord_track: Optional[Track],
        bars: int,
        sp_bass: list[int],
    ) -> list[int]:
        """Get the lowest pitch per bar from *chord_track*, or pick tonic."""
        if chord_track and chord_track.notes:
            roots: list[int] = []
            for b in range(bars):
                bar_start = b * _BAR
                bar_end = bar_start + _BAR
                bar_notes = chord_track.get_notes_in_range(bar_start, bar_end)
                if bar_notes:
                    lowest = min(n.pitch for n in bar_notes)
                    roots.append(_snap_to_scale(lowest % 12 + (sp_bass[0] // 12) * 12, sp_bass))
                else:
                    roots.append(sp_bass[0])
            return roots
        return [sp_bass[0]] * bars

    def _bass_walking(self, root: int, bar_start: int, sp: list[int]) -> list[Note]:
        notes: list[Note] = []
        idx = self._closest_idx(sp, root)
        for beat in range(4):
            notes.append(Note(
                pitch=sp[idx],
                velocity=_clamp_vel(85 + int(self.rng.integers(-6, 7))),
                start_tick=bar_start + beat * _BEAT,
                duration_ticks=_BEAT - _BEAT // 8,
            ))
            step = int(self.rng.choice([-1, 1, 1, 2]))
            idx = max(0, min(len(sp) - 1, idx + step))
        return notes

    def _bass_sustained(self, root: int, bar_start: int) -> list[Note]:
        return [Note(
            pitch=root,
            velocity=80,
            start_tick=bar_start,
            duration_ticks=_BAR - _BEAT // 4,
        )]

    def _bass_octave(self, root: int, bar_start: int) -> list[Note]:
        upper = _clamp_pitch(root + 12)
        notes: list[Note] = []
        pattern = [root, upper, root, upper]
        for i, p in enumerate(pattern):
            notes.append(Note(
                pitch=p,
                velocity=_clamp_vel(80 if i % 2 == 0 else 70),
                start_tick=bar_start + i * _BEAT,
                duration_ticks=_BEAT - _BEAT // 8,
            ))
        return notes

    def _bass_pop(self, root: int, bar_start: int, sp: list[int]) -> list[Note]:
        idx = self._closest_idx(sp, root)
        fifth_idx = min(idx + 4, len(sp) - 1)
        notes: list[Note] = []
        # Beat 1: root
        notes.append(Note(
            pitch=sp[idx], velocity=85,
            start_tick=bar_start, duration_ticks=_BEAT,
        ))
        # Beat 3: fifth
        notes.append(Note(
            pitch=sp[fifth_idx], velocity=75,
            start_tick=bar_start + 2 * _BEAT, duration_ticks=_BEAT,
        ))
        # Optional ghost notes on off-beats
        if self.rng.random() > 0.4:
            notes.append(Note(
                pitch=sp[idx], velocity=55,
                start_tick=bar_start + int(1.5 * _BEAT),
                duration_ticks=_BEAT // 2,
            ))
        return notes

    # ------------------------------------------------------------------
    # 5. Humanize
    # ------------------------------------------------------------------

    def humanize(
        self,
        track: Track,
        timing_amount: float = 0.3,
        velocity_amount: float = 0.3,
    ) -> Track:
        """Add subtle human-feel imperfections to *track*.

        Parameters
        ----------
        timing_amount : float (0.0 – 1.0)
            Maximum timing deviation as a fraction of a beat.
        velocity_amount : float (0.0 – 1.0)
            Maximum velocity deviation (0-20 units).
        """
        out = track.copy()
        max_tick_offset = int(_BEAT * 0.08 * max(0, min(1, timing_amount)) * 10)
        max_vel_offset = int(20 * max(0, min(1, velocity_amount)))

        for note in out.notes:
            if max_tick_offset > 0:
                offset = int(self.rng.integers(-max_tick_offset, max_tick_offset + 1))
                note.start_tick = max(0, note.start_tick + offset)
            if max_vel_offset > 0:
                v_off = int(self.rng.integers(-max_vel_offset, max_vel_offset + 1))
                note.velocity = _clamp_vel(note.velocity + v_off)

        out.notes.sort(key=lambda n: n.start_tick)
        return out

    # ------------------------------------------------------------------
    # 6. Analysis
    # ------------------------------------------------------------------

    def analyze_track(
        self,
        track: Track,
        key: str = "C",
        scale: str = "minor",
    ) -> dict:
        """Return descriptive statistics for *track*.

        Keys returned
        -------------
        note_count, pitch_min, pitch_max, pitch_mean, pitch_std,
        velocity_min, velocity_max, velocity_mean, duration_mean,
        density_notes_per_beat, total_beats, scale_consistency,
        pitch_histogram (dict[str, int]), interval_histogram (dict[int, int]).
        """
        notes = track.notes
        if not notes:
            return {
                "note_count": 0,
                "pitch_min": None,
                "pitch_max": None,
                "pitch_mean": None,
                "pitch_std": None,
                "velocity_min": None,
                "velocity_max": None,
                "velocity_mean": None,
                "duration_mean": None,
                "density_notes_per_beat": 0.0,
                "total_beats": 0.0,
                "scale_consistency": 0,
                "velocity_dynamics": 0,
                "rhythm_regularity": 0,
                "note_diversity": 0,
                "score": 0,
                "issues": ["Track is empty"],
                "pitch_histogram": {},
                "pitch_distribution": {},
                "interval_histogram": {},
            }

        pitches = np.array([n.pitch for n in notes])
        velocities = np.array([n.velocity for n in notes])
        durations = np.array([n.duration_ticks for n in notes])

        total_ticks = max(n.end_tick for n in notes)
        total_beats = total_ticks / _BEAT if total_ticks else 0

        # Scale consistency: fraction of notes that fall in the scale.
        root = key_name_to_root(key)
        sp_set = set(get_scale_pitches(root, scale))
        in_scale = sum(1 for p in pitches if int(p) in sp_set)
        scale_consistency_frac = in_scale / len(pitches)
        scale_consistency = int(round(scale_consistency_frac * 100))

        # Pitch-class histogram
        pitch_hist: dict[str, int] = {}
        for p in pitches:
            name = NOTE_NAMES[int(p) % 12]
            pitch_hist[name] = pitch_hist.get(name, 0) + 1

        # Interval histogram (semitones between successive notes)
        intervals = np.diff(pitches).astype(int)
        interval_hist: dict[int, int] = {}
        for iv in intervals:
            iv_int = int(iv)
            interval_hist[iv_int] = interval_hist.get(iv_int, 0) + 1

        # Velocity dynamics: based on velocity standard deviation and range.
        vel_range = int(velocities.max()) - int(velocities.min())
        vel_std = float(velocities.std())
        # Normalize: std up to ~30 and range up to ~80 are considered full dynamics.
        vel_std_score = min(100, vel_std / 30.0 * 100)
        vel_range_score = min(100, vel_range / 80.0 * 100)
        velocity_dynamics = int(round(vel_std_score * 0.5 + vel_range_score * 0.5))

        # Rhythm regularity: based on how consistent the inter-onset intervals are.
        start_ticks = np.array(sorted(n.start_tick for n in notes))
        if len(start_ticks) > 1:
            onset_intervals = np.diff(start_ticks).astype(float)
            onset_intervals = onset_intervals[onset_intervals > 0]
            if len(onset_intervals) > 1:
                cv = float(onset_intervals.std() / onset_intervals.mean()) if onset_intervals.mean() > 0 else 1.0
                # Lower CV = more regular. CV of 0 -> 100, CV >= 1.5 -> 0
                rhythm_regularity = int(round(max(0, min(100, (1.0 - cv / 1.5) * 100))))
            else:
                rhythm_regularity = 100
        else:
            rhythm_regularity = 100

        # Note diversity: unique pitch classes out of 12.
        unique_pitch_classes = len(set(int(p) % 12 for p in pitches))
        note_diversity = int(round(unique_pitch_classes / 12.0 * 100))

        # Overall score: weighted average of all metrics.
        score = int(round(
            scale_consistency * 0.30
            + velocity_dynamics * 0.20
            + rhythm_regularity * 0.25
            + note_diversity * 0.25
        ))

        # Issues detection
        issues: list[str] = []
        if scale_consistency < 60:
            issues.append("Low scale consistency")
        pitch_range = int(pitches.max()) - int(pitches.min())
        if pitch_range < 12:
            issues.append("Narrow pitch range")
        if velocity_dynamics < 30:
            issues.append("Low velocity dynamics — notes feel flat")
        if note_diversity < 30:
            issues.append("Low note diversity — few distinct pitch classes")
        if rhythm_regularity < 30:
            issues.append("Irregular rhythm — timing is erratic")
        if len(notes) < 4:
            issues.append("Very few notes — track may be too sparse")

        result = {
            "note_count": len(notes),
            "pitch_min": int(pitches.min()),
            "pitch_max": int(pitches.max()),
            "pitch_mean": round(float(pitches.mean()), 2),
            "pitch_std": round(float(pitches.std()), 2),
            "velocity_min": int(velocities.min()),
            "velocity_max": int(velocities.max()),
            "velocity_mean": round(float(velocities.mean()), 2),
            "duration_mean": round(float(durations.mean()), 2),
            "density_notes_per_beat": round(len(notes) / total_beats, 2) if total_beats else 0,
            "total_beats": round(total_beats, 2),
            "scale_consistency": scale_consistency,
            "velocity_dynamics": velocity_dynamics,
            "rhythm_regularity": rhythm_regularity,
            "note_diversity": note_diversity,
            "score": score,
            "issues": issues,
            "pitch_histogram": pitch_hist,
            "pitch_distribution": pitch_hist,
            "interval_histogram": interval_hist,
        }

        # Enrich with harmony analysis from rule DB v2.07
        if self._harmony_engine is not None:
            try:
                harmony = self._harmony_engine.analyze_track_harmony(track, key, scale)
                result["harmony_segments"] = harmony.get("harmony_segments", [])
                result["chord_count"] = harmony.get("chord_count", 0)
                result["playability_score"] = harmony.get("playability_score", 100)
                result["harmony_score"] = harmony.get("overall_score", 0)
                result["rule_db_version"] = harmony.get("rule_db_version", 0)
                # Merge harmony issues
                result["issues"] = result["issues"] + harmony.get("issues", [])
                # Weighted score including harmony
                result["score"] = int(round(
                    score * 0.5 + harmony.get("overall_score", score) * 0.5
                ))
            except Exception:
                pass

        return result

    # ------------------------------------------------------------------
    # Private utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _closest_idx(lst: list[int], value: int) -> int:
        arr = np.asarray(lst)
        return int(np.argmin(np.abs(arr - value)))
