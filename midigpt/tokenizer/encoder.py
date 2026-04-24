"""
MidiEncoder — Converts MIDI files to hierarchical REMI token sequences.

Pipeline:
  MIDI file → pretty_midi → note extraction → harmony analysis → token sequence
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
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
    """Global metadata for a song.

    Sprint WWW (종합리뷰 §8-2, §20-7) — SongMeta 는 기존 key/style/section/
    tempo 4 필드 그대로 유지하고, 새로운 contextual 필드들은 아래
    SongContext 로 분리한다. 이유:
      1) 기존 호출부 / 체크포인트 / 커밋 이력이 SongMeta 를 4-field
         dataclass 로 가정하고 있다 (BREAKING 회피).
      2) SongContext 는 "generation conditioning" 용 풍부한 객체로,
         메타데이터와 개념적 층위가 다르다 — 섞으면 혼동.
      3) 단계적 승격 (generation path 에서 실제로 쓰는 서브셋 만큼
         점진 수용) 이 쉬워진다.
    """
    key: str = "C"           # e.g. "C" or "Am"
    style: str = "unknown"
    section: str = "unknown"
    tempo: float = 120.0


@dataclass
class TrackRole:
    """Partner §8-3 / §20-8 — "이 트랙이 곡 안에서 무슨 역할을 하는가"
    를 데이터 구조에 명시. 단순 악기 카테고리(TRACK_TYPES) 보다 한 단계
    상위의 음악적 기능 태그.

    Fields:
        name: 악기 카테고리 (TRACK_TYPES 의 원소, 예: "strings")
        role: 역할 태그 (MELODY / COUNTER / ACCOMP / BASS_FOUNDATION /
              RHYTHMIC_HOOK / PAD_SUSTAIN / LEAD / FILL / 기타)
        human_playable: 사람 연주감을 보존해야 하는지
        main:           메인 트랙 (True) vs 보조 트랙 (False)
    """
    name: str = "other"
    role: str = "accomp"
    human_playable: bool = False
    main: bool = True


@dataclass
class SongContext:
    """Partner §20-7 — metadata 수준을 넘어 실제 generation condition 으로
    승격된 곡 문맥. generate_to_midi 가 받아들이는 "full context" 객체.

    모든 필드는 선택적이라 기존 경로와 호환된다. 채워진 필드만 condition
    으로 쓰인다 (None / 빈 컨테이너 = "정보 없음"으로 해석).

    관계:
      - SongMeta 는 key/style/section/tempo 의 minimum-set 로 유지.
      - SongContext 는 그 위에 target task / range / role map /
        chord map / groove / density / register 를 얹는다.
      - 요청 한 건은 (meta, context) 쌍으로 엔진에 전달된다.
    """
    # Scope of the current generation call — target section in the song.
    target_task: str = "variation"   # variation|continuation|bar_infill|track_completion|…
    target_track: str = ""           # TRACK_TYPES category name
    start_bar: int = 0
    end_bar: int = 0                  # 0 = unused / open-ended

    # Other tracks' roles (for multi-track conditioning).
    tracks: list[TrackRole] = field(default_factory=list)

    # Section boundaries (앞/뒤 섹션 문맥). list of (start_bar, section_name).
    section_map: list[tuple[int, str]] = field(default_factory=list)

    # Chord map at bar granularity — subset of ChordEvent for lightweight
    # transport. Full chords[] remains the engine-side structure.
    chord_map: list[tuple[int, str]] = field(default_factory=list)
    # (bar, chord_symbol) e.g. (0, "Cmaj7"), (4, "Am")

    # Dynamics / groove profile (coarse 0..1 each).
    groove:  float = 0.5              # 0=straight, 1=heavy swing
    density: float = 0.5              # 0=sparse, 1=dense
    energy:  float = 0.5              # 0=soft, 1=loud

    # Register budget — midi note range the output should respect.
    register_low:  int = 21
    register_high: int = 108

    # Melodic anchor — optional pitch(es) that should be prominent.
    melodic_anchor: list[int] = field(default_factory=list)

    # Free-form user hint (LLM planner output, user note, etc.).
    user_hint: str = ""


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
        exclude_tracks: list[str] | None = None,
    ) -> list[int]:
        """Encode a MIDI file to a token ID sequence.

        Args:
            midi_path: Path to .mid file.
            meta: Optional song metadata. If None, estimated from MIDI.
            chords: Optional pre-analyzed chord events. If None, basic
                    estimation is performed.
            max_bars: Maximum number of bars to encode.
            exclude_tracks: S12 — track categories to drop before
                encoding. Passed through to ``encode_pretty_midi``; see
                that method for rationale.

        Returns:
            List of token IDs.
        """
        if pretty_midi is None:
            raise ImportError("pretty_midi is required for encoding MIDI files")

        pm = pretty_midi.PrettyMIDI(midi_path)
        return self.encode_pretty_midi(
            pm, meta=meta, chords=chords, max_bars=max_bars,
            exclude_tracks=exclude_tracks,
        )

    def encode_pretty_midi(
        self,
        pm: "pretty_midi.PrettyMIDI",
        meta: SongMeta | None = None,
        chords: list[ChordEvent] | None = None,
        max_bars: int = 64,
        exclude_tracks: list[str] | None = None,
    ) -> list[int]:
        """Encode a PrettyMIDI object to token IDs.

        Args:
            exclude_tracks: S12 — list of track-type category names
                (e.g. ["drums"]) to remove before tokenisation. This
                aligns the inference prompt with the SFT training
                distribution: ``build_task_pairs`` drops the target
                track from the context side, so the inference path
                needs the same filter when the caller knows which
                track the model is supposed to produce. Default None =
                no filtering (backwards compat).
        """
        # Estimate metadata if not provided
        if meta is None:
            meta = self._estimate_meta(pm)

        # Extract notes
        notes = self._extract_notes(pm, exclude_tracks=exclude_tracks)
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
    def _extract_notes(
        self,
        pm: "pretty_midi.PrettyMIDI",
        exclude_tracks: list[str] | None = None,
    ) -> list[NoteEvent]:
        """Extract all notes from a PrettyMIDI object.

        Args:
            pm: PrettyMIDI to read.
            exclude_tracks: S12 — if set, instruments whose
                ``_classify_track`` result is in this list are dropped.
                Used by the inference path (engine.generate_to_midi) to
                match the training distribution — SFT task pairs never
                see the target track in their input context.
        """
        drop = set(exclude_tracks) if exclude_tracks else set()
        notes = []
        for inst in pm.instruments:
            if inst.is_drum:
                track_type = "drums"
            else:
                track_type = self._classify_track(inst)

            if track_type in drop:
                continue

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
        """Classify a MIDI instrument into one of the fixed track-type
        categories defined in ``vocab.TRACK_TYPES``.

        The model does not see original instrument names like ``E.PIANO``
        or ``VIOLIN_LEGATO``; each track is collapsed into one of the 14
        categories below before tokenisation, and the decoder writes that
        category as the output MIDI track name.

        Categories (vocab.TRACK_TYPES, all 14):
            melody / accomp / bass / drums / pad / lead / arp / other
            strings / brass / woodwind / vocal / guitar / fx

        Resolution order:
            1. Substring match on the original track name — expanded to
               cover real-world DAW naming conventions (E.PIANO, VIOLIN_*,
               E.GUITAR*, SYNTHBASS, SYNTHPAD, etc.)
            2. GM program number range → the semantically closest
               ``TRACK_TYPES`` entry (not all GM families collapse to
               ``accomp`` any more; guitar/strings/brass/woodwind now get
               their own categories).
            3. Average pitch register fallback (bass / melody).
            4. Default ``other``.

        History:
            2026-04-09 (BUG 6 correction):
              Guitar → accomp, Strings → pad, Brass → lead, Reed/Pipe → melody
              were collapsed to 2-3 categories; remapped to native categories.

            2026-04-15 (5차 리포트 Bug 3, rules/05 패턴 B):
              1) "BASSOON" → ``bass`` (substring of "bass"). Fixed: bass
                 substring check excludes both "brass" and "bassoon".
              2) "STRING" (singular) failed name match because only "strings"
                 was listed. Fixed: added "string" singular keyword.
              3) "TIMPANI" had no percussion keyword. Fixed: added timpani,
                 mallet.
              4) Root cause of accomp 쏠림: MIDI files without explicit
                 program numbers get inst.program == 0, which previously
                 matched ``0-7 → accomp`` (Piano family). Tester MIDI had
                 explicit track names but no program numbers, so any name
                 that missed the keyword table silently drifted to accomp.
                 Fixed: when program == 0 AND name is non-empty, treat
                 program as "unspecified" and skip program-based fallback;
                 go straight to register-based fallback.

            2026-04-17 (6차 리포트 확인 사항):
              C.BASS (C_BASS / CBASS) = 콘트라베이스(오케스트라 더블베이스)
              abbreviation. 기존에는 "bass" substring 에 걸려 ``bass`` 로
              분류되었으나, 의도는 strings family. bass-check 앞단에 전용
              abbreviation 분기를 추가. E.BASS (일렉베이스) 등 일반 bass
              표기는 계속 ``bass`` 로 분류됨.

            BREAKING: retokenize + retrain required after this change
            (rules/04-commit-discipline.md, rules/05 패턴 F).
        """
        name_lower = inst.name.lower() if inst.name else ""

        # -------------------------------------------------------------
        # 1. Name-based detection (priority 1) — most specific first
        # -------------------------------------------------------------
        # Drums (defensive — caller already short-circuits inst.is_drum)
        if any(k in name_lower for k in
               ("drum", "perc", "kick", "snare", "hihat", "cymbal", "tom",
                "timpani", "mallet")):
            return "drums"

        # Contrabass abbreviation (C.BASS, C_BASS, CBASS) — route to strings
        # BEFORE the bass check, because "bass" substring would otherwise
        # win. Orchestral double bass belongs to the strings family.
        # 6차 리포트 2026-04-17: 테스터 확인 — C.BASS = 콘트라베이스.
        if any(k in name_lower for k in ("c.bass", "c_bass", "cbass")):
            return "strings"

        # Bass — must guard substring collisions with "brass", "bassoon",
        # and the contrabass abbreviations handled above.
        if ("bass" in name_lower
                and "brass" not in name_lower
                and "bassoon" not in name_lower):
            return "bass"

        # Vocal
        if any(k in name_lower for k in ("vocal", "voice", "vox", "choir")):
            return "vocal"

        # Strings family (accept both singular "string" and plural "strings";
        # "string_" kept for legacy track names with an underscore suffix)
        if any(k in name_lower for k in
               ("violin", "viola", "cello", "contrabass",
                "strings", "string", "string_")):
            return "strings"

        # Brass family
        if any(k in name_lower for k in
               ("trumpet", "trombone", "french_horn", "horn", "tuba", "brass")):
            return "brass"

        # Woodwind family
        if any(k in name_lower for k in
               ("flute", "clarinet", "oboe", "bassoon", "sax", "saxophone",
                "woodwind", "pipe", "reed", "piccolo")):
            return "woodwind"

        # Guitar family (electric / acoustic / muted)
        if any(k in name_lower for k in ("guitar", "e.guitar", "gtr", "e_guitar")):
            return "guitar"

        # Keys family → accomp (closest vocab entry; there is no "keys")
        if any(k in name_lower for k in
               ("piano", "e.piano", "epiano", "rhodes", "wurl", "keys",
                "organ", "harpsichord", "clav")):
            return "accomp"

        # Pad
        if "pad" in name_lower:
            return "pad"

        # Arp / arpeggio
        if "arp" in name_lower:
            return "arp"

        # Lead / pluck
        if any(k in name_lower for k in ("lead", "synth_lead", "pluck")):
            return "lead"

        # Melody
        if "melody" in name_lower:
            return "melody"

        # FX / atmosphere
        if any(k in name_lower for k in ("fx", "effect", "atmo", "sfx")):
            return "fx"

        # -------------------------------------------------------------
        # 2. GM program-number detection (priority 2)
        #    General MIDI program ranges → semantically closest TRACK_TYPE.
        #
        #    IMPORTANT (rules/02-fallback-policy.md, 패턴 B):
        #    program == 0 is the MIDI default, often meaning "unspecified"
        #    rather than "Acoustic Grand Piano". If the track name is
        #    non-empty and did not match any keyword above, treating
        #    program=0 as Piano family silently drifts every such track to
        #    ``accomp`` — the 5차 accomp 쏠림 symptom. So when a name is
        #    present, skip program-based fallback on program=0 and let
        #    register-based fallback take over.
        # -------------------------------------------------------------
        prog = inst.program
        name_present = bool(name_lower)
        if not (name_present and prog == 0):
            if 0 <= prog <= 7:      return "accomp"    # Piano family
            if 8 <= prog <= 15:     return "accomp"    # Chromatic perc (celesta, vibes, marimba)
            if 16 <= prog <= 23:    return "accomp"    # Organ family
            if 24 <= prog <= 31:    return "guitar"    # Guitar family
            if 32 <= prog <= 39:    return "bass"      # Bass family
            if 40 <= prog <= 47:    return "strings"   # Solo strings
            if 48 <= prog <= 55:    return "strings"   # Ensemble strings
            if 56 <= prog <= 63:    return "brass"     # Brass family
            if 64 <= prog <= 71:    return "woodwind"  # Reed
            if 72 <= prog <= 79:    return "woodwind"  # Pipe / flute
            if 80 <= prog <= 87:    return "lead"      # Synth lead
            if 88 <= prog <= 95:    return "pad"       # Synth pad
            if 96 <= prog <= 103:   return "fx"        # Synth effects
            if 104 <= prog <= 111:  return "strings"   # Ethnic (sitar, banjo, koto → closest)
            if 112 <= prog <= 119:  return "drums"     # Percussive
            if 120 <= prog <= 127:  return "fx"        # Sound effects

        # -------------------------------------------------------------
        # 3. Register-based fallback (priority 3)
        # -------------------------------------------------------------
        if inst.notes:
            avg_pitch = sum(n.pitch for n in inst.notes) / len(inst.notes)
            if avg_pitch < 48:
                return "bass"
            if avg_pitch > 72:
                return "melody"

        # -------------------------------------------------------------
        # 4. Final fallback — use 'other' (was: 'accomp', which caused
        #    silent drift of unknown tracks into the accomp category).
        # -------------------------------------------------------------
        return "other"

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
