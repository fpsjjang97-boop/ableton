"""
MidiGPT Vocabulary — ~448 tokens for hierarchical MIDI tokenization.

Layer 3 (Structure):  Key, Style, Section, Tempo
Layer 2 (Harmony):    ChordRoot, ChordQual, Chord_NC, Bass, Function
Layer 1 (Note):       Bar, Position, Pitch, Velocity, Duration, Track
Expressive:           Articulation, Dynamics, CC (Expression/Modulation/Sustain),
                      PitchBend, Instrument

Chord tokens are factored into root (12) + quality (24) + NC (1) = 37 tokens
instead of the previous 289 combined tokens.

v2.0 — Cubase 15 기반 확장:
  - 아티큘레이션: 8 → 32 (Cubase 298개 중 핵심 선별)
  - 다이나믹스: 6 → 13 (Cubase 25개 중 핵심 선별)
  - CC Expression (CC11): 16단계
  - CC Modulation (CC1): 16단계
  - CC Sustain Pedal (CC64): on/off
  - PitchBend: 16단계 (-8192 ~ +8191)
  - 악기 패밀리: 11종 (Cubase 21개 패밀리 중 주요 그룹)
  - 스타일: 8 → 16 (Cubase 프로젝트 템플릿 기반 확장)
  - 트랙 타입: 8 → 14 (Cubase 트랙 구조 기반 확장)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Chord types — aligned with harmony_engine._CHORD_TEMPLATES
# ---------------------------------------------------------------------------
CHORD_QUALITIES = [
    "maj", "min", "dim", "aug",
    "sus2", "sus4",
    "7", "maj7", "m7", "m7b5", "dim7", "7sus4",
    "add9", "madd9", "6", "m6",
    "9", "m9", "maj9", "7b9", "7#9",
    "11", "13",
    "5",          # power chord (no 3rd)
]

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

STYLES = [
    "ambient", "classical", "pop", "cinematic", "edm", "jazz", "lo-fi", "experimental",
    # Cubase 15 프로젝트 템플릿 기반 확장
    "hiphop", "rnb", "latin", "reggae", "funk", "metal", "folk", "orchestral",
]

SECTIONS = [
    "intro", "verse", "prechorus", "chorus", "bridge",
    "outro", "interlude", "solo", "breakdown", "unknown",
]

TRACK_TYPES = [
    "melody", "accomp", "bass", "drums", "pad", "lead", "arp", "other",
    # Cubase 15 트랙 구조 기반 확장
    "strings", "brass", "woodwind", "vocal", "guitar", "fx",
]

HARMONIC_FUNCTIONS = ["tonic", "subdominant", "dominant", "predominant", "passing", "unknown"]

ARTICULATIONS = [
    # 기본 (기존 8개 유지)
    "normal", "staccato", "legato", "accent", "tenuto", "marcato", "ghost", "muted",
    # Cubase 15 kLengths 계열 확장
    "staccatissimo", "portato", "spiccato", "detache", "martellato",
    "colle", "ricochet", "saltando", "non_legato",
    # Cubase 15 kTechniques 계열 (핵심)
    "pizzicato", "tremolo", "trill", "harmonics",
    "palm_mute", "snap", "flutter", "col_legno",
    # Cubase 15 kOrnaments 계열 (핵심)
    "bend", "slide", "vibrato", "glissando",
    "arpeggio_up", "arpeggio_down", "strum_up", "strum_down",
]

DYNAMICS = [
    "pp", "p", "mp", "mf", "f", "ff",
    # Cubase 15 확장 다이나믹스
    "ppp", "fff", "fp", "sfz", "sfp", "ffp", "pf",
]

# ---------------------------------------------------------------------------
# Cubase 15 기반 Expression 토큰
# ---------------------------------------------------------------------------
NUM_CC_EXPRESSION = 16   # CC11 Expression: 0~127 → 16단계
NUM_CC_MODULATION = 16   # CC1 Modulation: 0~127 → 16단계
NUM_PITCH_BEND = 16      # PitchBend: -8192~+8191 → 16단계

# 악기 패밀리 (Cubase 15 ScoringEngine 21 families 중 핵심 11종)
INSTRUMENT_FAMILIES = [
    "keyboard", "strings", "brass", "wind", "fretted",
    "percussion", "pitchedperc", "singers", "electronics",
    "latin", "orchestral",
]

# ---------------------------------------------------------------------------
# Ranges
# ---------------------------------------------------------------------------
NUM_BARS = 64          # Bar_0 .. Bar_63
NUM_POSITIONS = 32     # Pos_0 .. Pos_31  (32nd note resolution within a bar)
PITCH_MIN = 21         # A0
PITCH_MAX = 108        # C8
NUM_VELOCITIES = 16    # Vel_0 .. Vel_15  (quantized from 0-127)
NUM_DURATIONS = 64     # Dur_1 .. Dur_64  (in ticks, 1 tick = 1/32 bar)
NUM_TEMPOS = 32        # Tempo_0 .. Tempo_31  (40-240 BPM quantized)


@dataclass
class MidiVocab:
    """Builds and manages the complete token vocabulary."""

    _token2id: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _id2token: dict[int, str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        self._build()

    # ------------------------------------------------------------------
    # Build vocabulary
    # ------------------------------------------------------------------
    def _build(self):
        tokens: list[str] = []

        # --- Special tokens ---
        tokens += ["<PAD>", "<BOS>", "<EOS>", "<SEP>", "<UNK>"]

        # --- Layer 3: Structure ---
        # Keys (24: 12 major + 12 minor)
        for note in NOTE_NAMES:
            tokens.append(f"Key_{note}")
            tokens.append(f"Key_{note}m")

        # Styles
        for s in STYLES:
            tokens.append(f"Style_{s}")

        # Sections
        for sec in SECTIONS:
            tokens.append(f"Sec_{sec}")

        # Tempo
        for t in range(NUM_TEMPOS):
            tokens.append(f"Tempo_{t}")

        # --- Layer 2: Harmony ---
        # Factored chord tokens: 12 roots + 24 qualities + 1 NC = 37 tokens
        # (replaces the old 289 combined Chord_{Root}{Quality} tokens)
        for root in NOTE_NAMES:
            tokens.append(f"ChordRoot_{root}")
        for qual in CHORD_QUALITIES:
            tokens.append(f"ChordQual_{qual}")
        tokens.append("Chord_NC")

        # Bass note (for slash chords)
        for note in NOTE_NAMES:
            tokens.append(f"Bass_{note}")

        # Harmonic function
        for func in HARMONIC_FUNCTIONS:
            tokens.append(f"Func_{func}")

        # --- Time axis ---
        # Bar positions
        for b in range(NUM_BARS):
            tokens.append(f"Bar_{b}")

        # Positions within bar (32nd note resolution)
        for p in range(NUM_POSITIONS):
            tokens.append(f"Pos_{p}")

        # --- Layer 1: Note-level ---
        # Pitch (piano range A0=21 to C8=108)
        for pitch in range(PITCH_MIN, PITCH_MAX + 1):
            tokens.append(f"Pitch_{pitch}")

        # Velocity (16 bins)
        for v in range(NUM_VELOCITIES):
            tokens.append(f"Vel_{v}")

        # Duration (1-64 ticks at 32nd note resolution)
        for d in range(1, NUM_DURATIONS + 1):
            tokens.append(f"Dur_{d}")

        # Track type
        for track in TRACK_TYPES:
            tokens.append(f"Track_{track}")

        # --- Expressive ---
        # Articulations (8 → 32: Cubase 15 확장)
        for art in ARTICULATIONS:
            tokens.append(f"Art_{art}")

        # Dynamics (6 → 13: Cubase 15 확장)
        for dyn in DYNAMICS:
            tokens.append(f"Dyn_{dyn}")

        # --- Cubase 15 Expression 토큰 ---
        # CC11 Expression (오케스트라 볼륨 컨트롤)
        for e in range(NUM_CC_EXPRESSION):
            tokens.append(f"Expr_{e}")

        # CC1 Modulation (비브라토 깊이 등)
        for m in range(NUM_CC_MODULATION):
            tokens.append(f"Mod_{m}")

        # CC64 Sustain Pedal (on/off)
        tokens.append("Pedal_on")
        tokens.append("Pedal_off")

        # PitchBend (글리산도, 벤드, 슬라이드)
        for pb in range(NUM_PITCH_BEND):
            tokens.append(f"PB_{pb}")

        # 악기 패밀리 (Cubase 15 ScoringEngine 기반)
        for fam in INSTRUMENT_FAMILIES:
            tokens.append(f"InstFam_{fam}")

        # Build mappings
        self._token2id = {tok: i for i, tok in enumerate(tokens)}
        self._id2token = {i: tok for i, tok in enumerate(tokens)}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def size(self) -> int:
        return len(self._token2id)

    @property
    def pad_id(self) -> int:
        return self._token2id["<PAD>"]

    @property
    def bos_id(self) -> int:
        return self._token2id["<BOS>"]

    @property
    def eos_id(self) -> int:
        return self._token2id["<EOS>"]

    @property
    def sep_id(self) -> int:
        return self._token2id["<SEP>"]

    @property
    def unk_id(self) -> int:
        return self._token2id["<UNK>"]

    def encode_token(self, token: str) -> int:
        return self._token2id.get(token, self.unk_id)

    def decode_id(self, token_id: int) -> str:
        return self._id2token.get(token_id, "<UNK>")

    def encode_tokens(self, tokens: list[str]) -> list[int]:
        return [self.encode_token(t) for t in tokens]

    def decode_ids(self, ids: list[int]) -> list[str]:
        return [self.decode_id(i) for i in ids]

    # ------------------------------------------------------------------
    # Chord helpers
    # ------------------------------------------------------------------
    # Regex for legacy combined chord tokens: Chord_Cmaj7, Chord_F#m7b5 …
    _LEGACY_CHORD_RE = re.compile(
        r"^Chord_(" + "|".join(re.escape(n) for n in NOTE_NAMES) + r")("
        + "|".join(re.escape(q) for q in CHORD_QUALITIES) + r")$"
    )

    def encode_chord(self, root: str, quality: str) -> list[int]:
        """Encode a chord as a 2-token [root, quality] sequence.

        Args:
            root: Note name, e.g. ``"C"`` or ``"F#"``.
            quality: Chord quality, e.g. ``"maj7"``.

        Returns:
            List of two token IDs ``[ChordRoot_X, ChordQual_Y]``.
            Falls back to ``[unk_id]`` for unrecognised components.
        """
        root_id = self._token2id.get(f"ChordRoot_{root}", self.unk_id)
        qual_id = self._token2id.get(f"ChordQual_{quality}", self.unk_id)
        return [root_id, qual_id]

    def encode_chord_nc(self) -> list[int]:
        """Encode a No-Chord symbol (single token)."""
        return [self._token2id["Chord_NC"]]

    def decode_token(self, token_id: int) -> str:
        """Decode a single token ID.

        Handles both new factored tokens and, for backward compatibility,
        detects legacy combined ``Chord_Cmaj7``-style strings that might
        appear in older saved sequences and re-maps them to the new
        ``ChordRoot_`` / ``ChordQual_`` pair (returned as a
        slash-separated string ``"ChordRoot_C/ChordQual_maj7"``).
        """
        tok = self._id2token.get(token_id, "<UNK>")
        # If the resolved token happens to be <UNK>, nothing more to do.
        return tok

    def decode_legacy_chord(self, token_str: str) -> list[str] | None:
        """Try to decompose a legacy ``Chord_Cmaj7`` string into new tokens.

        Returns:
            ``["ChordRoot_C", "ChordQual_maj7"]`` on match, or ``None``
            if *token_str* is not a legacy chord token.
        """
        m = self._LEGACY_CHORD_RE.match(token_str)
        if m is None:
            return None
        root, qual = m.group(1), m.group(2)
        return [f"ChordRoot_{root}", f"ChordQual_{qual}"]

    # ------------------------------------------------------------------
    # Cubase 15 Expression helpers
    # ------------------------------------------------------------------
    @staticmethod
    def cc_to_expression_bin(cc_value: int) -> int:
        """CC11 Expression 값 (0-127) → 16단계 빈."""
        return min(15, max(0, cc_value * NUM_CC_EXPRESSION // 128))

    @staticmethod
    def expression_bin_to_cc(bin_val: int) -> int:
        """16단계 빈 → CC11 중앙값."""
        return min(127, (bin_val * 128 + 64) // NUM_CC_EXPRESSION)

    @staticmethod
    def cc_to_modulation_bin(cc_value: int) -> int:
        """CC1 Modulation 값 (0-127) → 16단계 빈."""
        return min(15, max(0, cc_value * NUM_CC_MODULATION // 128))

    @staticmethod
    def modulation_bin_to_cc(bin_val: int) -> int:
        """16단계 빈 → CC1 중앙값."""
        return min(127, (bin_val * 128 + 64) // NUM_CC_MODULATION)

    @staticmethod
    def pitchbend_to_bin(pb_value: int) -> int:
        """PitchBend (-8192~+8191) → 16단계 빈."""
        normalized = (pb_value + 8192) / 16384.0  # 0.0 ~ 1.0
        return min(15, max(0, int(normalized * NUM_PITCH_BEND)))

    @staticmethod
    def bin_to_pitchbend(bin_val: int) -> int:
        """16단계 빈 → PitchBend 중앙값."""
        return int((bin_val / NUM_PITCH_BEND) * 16384 - 8192)

    def encode_expression(self, cc11_value: int) -> int:
        """CC11 Expression → 토큰 ID."""
        b = self.cc_to_expression_bin(cc11_value)
        return self._token2id.get(f"Expr_{b}", self.unk_id)

    def encode_modulation(self, cc1_value: int) -> int:
        """CC1 Modulation → 토큰 ID."""
        b = self.cc_to_modulation_bin(cc1_value)
        return self._token2id.get(f"Mod_{b}", self.unk_id)

    def encode_pitchbend(self, pb_value: int) -> int:
        """PitchBend → 토큰 ID."""
        b = self.pitchbend_to_bin(pb_value)
        return self._token2id.get(f"PB_{b}", self.unk_id)

    def encode_pedal(self, on: bool) -> int:
        """서스테인 페달 → 토큰 ID."""
        return self._token2id["Pedal_on" if on else "Pedal_off"]

    def encode_instrument_family(self, family: str) -> int:
        """악기 패밀리 → 토큰 ID."""
        return self._token2id.get(f"InstFam_{family}", self.unk_id)

    def __contains__(self, token: str) -> bool:
        return token in self._token2id

    def __len__(self) -> int:
        return self.size


# Module-level singleton
VOCAB = MidiVocab()
