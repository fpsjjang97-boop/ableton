"""
MidiEncoder — Converts MIDI files to hierarchical REMI token sequences.

Pipeline:
  MIDI file → pretty_midi → note extraction → harmony analysis → token sequence
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    import pretty_midi
except ImportError:
    pretty_midi = None

try:
    import mido
except ImportError:
    mido = None

from .vocab import (
    MidiVocab, VOCAB, NOTE_NAMES, CHORD_QUALITIES,
    NUM_POSITIONS, NUM_VELOCITIES, NUM_DURATIONS, NUM_TEMPOS,
    PITCH_MIN, PITCH_MAX,
)


@dataclass
class NoteEvent:
    """A single note extracted from MIDI."""
    pitch: int
    velocity: int
    start: float      # in seconds
    end: float         # in seconds
    track_type: str    # melody / accomp / bass / drums / ...
    program: int = 0   # MIDI program number


@dataclass
class ChordEvent:
    """A chord segment from harmony analysis."""
    root: str          # e.g. "C"
    quality: str       # e.g. "maj7"
    bass: Optional[str] = None   # slash chord bass, e.g. "E"
    start_beat: float = 0.0
    end_beat: float = 0.0
    function: str = "unknown"


@dataclass
class SongMeta:
    """Global metadata for a song."""
    key: str = "C"           # e.g. "C" or "Am"
    style: str = "unknown"
    section: str = "unknown"
    tempo: float = 120.0


class MidiEncoder:
    """Encodes MIDI files into token ID sequences."""

    def __init__(self, vocab: MidiVocab | None = None):
        self.vocab = vocab or VOCAB

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def encode_file(
        self,
        midi_path: str,
        meta: SongMeta | None = None,
        chords: list[ChordEvent] | None = None,
        max_bars: int = 64,
    ) -> list[int]:
        """Encode a MIDI file to a token ID sequence.

        Args:
            midi_path: Path to .mid file.
            meta: Optional song metadata. If None, estimated from MIDI.
            chords: Optional pre-analyzed chord events. If None, basic
                    estimation is performed.
            max_bars: Maximum number of bars to encode.

        Returns:
            List of token IDs.
        """
        if pretty_midi is None:
            raise ImportError("pretty_midi is required for encoding MIDI files")

        pm = pretty_midi.PrettyMIDI(midi_path)
        return self.encode_pretty_midi(pm, meta=meta, chords=chords, max_bars=max_bars)

    def encode_pretty_midi(
        self,
        pm: "pretty_midi.PrettyMIDI",
        meta: SongMeta | None = None,
        chords: list[ChordEvent] | None = None,
        max_bars: int = 64,
    ) -> list[int]:
        """Encode a PrettyMIDI object to token IDs."""
        # Estimate metadata if not provided
        if meta is None:
            meta = self._estimate_meta(pm)

        # Extract notes
        notes = self._extract_notes(pm)
        if not notes:
            return [self.vocab.bos_id, self.vocab.eos_id]

        # Estimate tempo for beat conversion
        tempo = meta.tempo if meta.tempo > 0 else 120.0
        beat_duration = 60.0 / tempo  # seconds per beat
        bar_duration = beat_duration * 4  # seconds per bar (4/4 time)

        # Build token sequence
        tokens: list[str] = []

        # --- BOS ---
        tokens.append("<BOS>")

        # --- Layer 3: Global conditions ---
        key_token = f"Key_{meta.key}" if f"Key_{meta.key}" in self.vocab else "Key_C"
        tokens.append(key_token)

        if meta.style != "unknown":
            style_token = f"Style_{meta.style}"
            if style_token in self.vocab:
                tokens.append(style_token)

        if meta.section != "unknown":
            sec_token = f"Sec_{meta.section}"
            if sec_token in self.vocab:
                tokens.append(sec_token)

        # Tempo token (quantize to 32 bins: 40-240 BPM)
        tempo_bin = self._quantize_tempo(tempo)
        tokens.append(f"Tempo_{tempo_bin}")

        # --- Sort notes by time ---
        notes.sort(key=lambda n: (n.start, n.pitch))

        # --- Build chord timeline ---
        chord_map = self._build_chord_map(chords, bar_duration, max_bars)

        # --- Encode bar by bar ---
        current_chord = None
        current_track = None

        for bar_idx in range(max_bars):
            bar_start = bar_idx * bar_duration
            bar_end = bar_start + bar_duration

            # Get notes in this bar
            bar_notes = [n for n in notes if n.start < bar_end and n.end > bar_start]
            if not bar_notes and bar_idx > 0:
                # Check if we've passed the end of the song
                if all(n.end <= bar_start for n in notes):
                    break
                continue

            # Bar marker
            tokens.append(f"Bar_{bar_idx}")

            # Chord for this bar (if changed)
            if bar_idx in chord_map:
                chord = chord_map[bar_idx]
                chord_key = (chord.root, chord.quality)
                if chord_key != current_chord:
                    root_token = f"ChordRoot_{chord.root}"
                    qual_token = f"ChordQual_{chord.quality}"
                    if root_token in self.vocab and qual_token in self.vocab:
                        tokens.append(root_token)
                        tokens.append(qual_token)
                        current_chord = chord_key

                        # Slash bass
                        if chord.bass and chord.bass != chord.root:
                            bass_token = f"Bass_{chord.bass}"
                            if bass_token in self.vocab:
                                tokens.append(bass_token)

                        # Harmonic function
                        func_token = f"Func_{chord.function}"
                        if func_token in self.vocab:
                            tokens.append(func_token)

            # Encode notes within bar
            for note in bar_notes:
                # Track type (only emit on change)
                if note.track_type != current_track:
                    track_token = f"Track_{note.track_type}"
                    if track_token in self.vocab:
                        tokens.append(track_token)
                        current_track = note.track_type

                # Position within bar (0-31, 32nd note resolution)
                rel_start = max(0.0, note.start - bar_start)
                pos = self._time_to_position(rel_start, bar_duration)
                tokens.append(f"Pos_{pos}")

                # Pitch
                pitch = max(PITCH_MIN, min(PITCH_MAX, note.pitch))
                tokens.append(f"Pitch_{pitch}")

                # Velocity (quantize to 16 bins)
                vel_bin = self._quantize_velocity(note.velocity)
                tokens.append(f"Vel_{vel_bin}")

                # Duration (in 32nd note units, capped at 64)
                dur_seconds = note.end - note.start
                dur_ticks = self._time_to_duration(dur_seconds, bar_duration)
                tokens.append(f"Dur_{dur_ticks}")

        # --- EOS ---
        tokens.append("<EOS>")

        return self.vocab.encode_tokens(tokens)

    # ------------------------------------------------------------------
    # Encode from raw note list (for variation pairs, no file needed)
    # ------------------------------------------------------------------
    def encode_notes(
        self,
        notes: list[dict],
        meta: SongMeta | None = None,
        chords: list[ChordEvent] | None = None,
        ticks_per_beat: int = 480,
    ) -> list[int]:
        """Encode a list of note dicts (from our internal format).

        Each note dict: {pitch, velocity, start_tick, duration_tick, track_type}
        """
        if meta is None:
            meta = SongMeta()

        tempo = meta.tempo if meta.tempo > 0 else 120.0
        beat_duration = 60.0 / tempo
        tick_duration = beat_duration / ticks_per_beat

        note_events = []
        for n in notes:
            start_sec = n["start_tick"] * tick_duration
            dur_sec = n["duration_tick"] * tick_duration
            note_events.append(NoteEvent(
                pitch=n["pitch"],
                velocity=n["velocity"],
                start=start_sec,
                end=start_sec + dur_sec,
                track_type=n.get("track_type", "accomp"),
            ))

        bar_duration = beat_duration * 4
        max_bars = min(64, int(max(n.end for n in note_events) / bar_duration) + 2)

        # Reuse pretty_midi path with NoteEvent objects
        tokens: list[str] = ["<BOS>"]

        key_token = f"Key_{meta.key}" if f"Key_{meta.key}" in self.vocab else "Key_C"
        tokens.append(key_token)
        if meta.style != "unknown" and f"Style_{meta.style}" in self.vocab:
            tokens.append(f"Style_{meta.style}")
        if meta.section != "unknown" and f"Sec_{meta.section}" in self.vocab:
            tokens.append(f"Sec_{meta.section}")
        tokens.append(f"Tempo_{self._quantize_tempo(tempo)}")

        chord_map = self._build_chord_map(chords, bar_duration, max_bars)
        note_events.sort(key=lambda n: (n.start, n.pitch))

        current_chord = None
        current_track = None

        for bar_idx in range(max_bars):
            bar_start = bar_idx * bar_duration
            bar_end = bar_start + bar_duration
            bar_notes = [n for n in note_events if n.start < bar_end and n.end > bar_start]

            if not bar_notes and all(n.end <= bar_start for n in note_events):
                break
            if not bar_notes:
                continue

            tokens.append(f"Bar_{bar_idx}")

            if bar_idx in chord_map:
                chord = chord_map[bar_idx]
                chord_key = (chord.root, chord.quality)
                if chord_key != current_chord:
                    root_token = f"ChordRoot_{chord.root}"
                    qual_token = f"ChordQual_{chord.quality}"
                    if root_token in self.vocab and qual_token in self.vocab:
                        tokens.append(root_token)
                        tokens.append(qual_token)
                        current_chord = chord_key
                        if chord.bass and chord.bass != chord.root:
                            bass_token = f"Bass_{chord.bass}"
                            if bass_token in self.vocab:
                                tokens.append(bass_token)

            for note in bar_notes:
                if note.track_type != current_track:
                    track_token = f"Track_{note.track_type}"
                    if track_token in self.vocab:
                        tokens.append(track_token)
                        current_track = note.track_type

                rel_start = max(0.0, note.start - bar_start)
                pos = self._time_to_position(rel_start, bar_duration)
                tokens.append(f"Pos_{pos}")
                tokens.append(f"Pitch_{max(PITCH_MIN, min(PITCH_MAX, note.pitch))}")
                tokens.append(f"Vel_{self._quantize_velocity(note.velocity)}")
                dur_ticks = self._time_to_duration(note.end - note.start, bar_duration)
                tokens.append(f"Dur_{dur_ticks}")

        tokens.append("<EOS>")
        return self.vocab.encode_tokens(tokens)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _extract_notes(self, pm: "pretty_midi.PrettyMIDI") -> list[NoteEvent]:
        """Extract all notes from a PrettyMIDI object."""
        notes = []
        for inst in pm.instruments:
            if inst.is_drum:
                track_type = "drums"
            else:
                track_type = self._classify_track(inst)

            for note in inst.notes:
                notes.append(NoteEvent(
                    pitch=note.pitch,
                    velocity=note.velocity,
                    start=note.start,
                    end=note.end,
                    track_type=track_type,
                    program=inst.program,
                ))
        return notes

    def _classify_track(self, inst: "pretty_midi.Instrument") -> str:
        """Classify instrument track type based on program number and register."""
        name_lower = inst.name.lower() if inst.name else ""

        # Name-based detection
        if "melody" in name_lower or "lead" in name_lower:
            return "melody"
        if "bass" in name_lower:
            return "bass"
        if "drum" in name_lower or "perc" in name_lower:
            return "drums"
        if "pad" in name_lower:
            return "pad"
        if "arp" in name_lower:
            return "arp"

        # Program-based detection
        prog = inst.program
        if 0 <= prog <= 7:     # Piano family
            return "accomp"
        if 24 <= prog <= 31:   # Guitar family
            return "accomp"
        if 32 <= prog <= 39:   # Bass family
            return "bass"
        if 48 <= prog <= 55:   # Strings
            return "pad"
        if 56 <= prog <= 63:   # Brass
            return "lead"
        if 64 <= prog <= 79:   # Reed/Pipe
            return "melody"

        # Register-based: if average pitch is low, likely bass
        if inst.notes:
            avg_pitch = sum(n.pitch for n in inst.notes) / len(inst.notes)
            if avg_pitch < 48:
                return "bass"
            if avg_pitch > 72:
                return "melody"

        return "accomp"

    def _estimate_meta(self, pm: "pretty_midi.PrettyMIDI") -> SongMeta:
        """Estimate song metadata from MIDI."""
        # Tempo
        tempos = pm.get_tempo_changes()
        tempo = tempos[1][0] if len(tempos[1]) > 0 else 120.0

        # Key estimation (simple pitch-class histogram)
        key = self._estimate_key(pm)

        return SongMeta(key=key, tempo=tempo)

    def _estimate_key(self, pm: "pretty_midi.PrettyMIDI") -> str:
        """Estimate key from pitch class distribution (Krumhansl-Schmuckler)."""
        # Major and minor profiles
        major_profile = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
        minor_profile = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

        # Build pitch class histogram weighted by duration
        pc_hist = np.zeros(12)
        for inst in pm.instruments:
            if inst.is_drum:
                continue
            for note in inst.notes:
                pc = note.pitch % 12
                dur = note.end - note.start
                pc_hist[pc] += dur

        if pc_hist.sum() == 0:
            return "C"

        pc_hist = pc_hist / pc_hist.sum()

        # Correlate with all keys
        best_key = "C"
        best_corr = -1.0
        for root in range(12):
            rotated = np.roll(pc_hist, -root)
            # Major
            corr_maj = float(np.corrcoef(rotated, major_profile)[0, 1])
            if corr_maj > best_corr:
                best_corr = corr_maj
                best_key = NOTE_NAMES[root]
            # Minor
            corr_min = float(np.corrcoef(rotated, minor_profile)[0, 1])
            if corr_min > best_corr:
                best_corr = corr_min
                best_key = f"{NOTE_NAMES[root]}m"

        return best_key

    def _build_chord_map(
        self,
        chords: list[ChordEvent] | None,
        bar_duration: float,
        max_bars: int,
    ) -> dict[int, ChordEvent]:
        """Map bar indices to chord events."""
        if not chords:
            return {}

        chord_map: dict[int, ChordEvent] = {}
        for chord in chords:
            bar_idx = int(chord.start_beat / 4)  # 4 beats per bar
            if 0 <= bar_idx < max_bars:
                chord_map[bar_idx] = chord
        return chord_map

    def _time_to_position(self, rel_seconds: float, bar_duration: float) -> int:
        """Convert relative time within bar to position (0-31)."""
        frac = rel_seconds / bar_duration if bar_duration > 0 else 0.0
        pos = int(frac * NUM_POSITIONS)
        return max(0, min(NUM_POSITIONS - 1, pos))

    def _time_to_duration(self, dur_seconds: float, bar_duration: float) -> int:
        """Convert duration in seconds to ticks (1-64 at 32nd note resolution)."""
        if bar_duration <= 0:
            return 1
        frac = dur_seconds / bar_duration
        ticks = int(round(frac * NUM_POSITIONS))
        return max(1, min(NUM_DURATIONS, ticks))

    @staticmethod
    def _quantize_velocity(velocity: int) -> int:
        """Quantize MIDI velocity (0-127) to 16 bins."""
        return max(0, min(15, velocity // 8))

    @staticmethod
    def _quantize_tempo(bpm: float) -> int:
        """Quantize BPM (40-240) to 32 bins."""
        clamped = max(40.0, min(240.0, bpm))
        return int((clamped - 40.0) / (200.0 / 31))
