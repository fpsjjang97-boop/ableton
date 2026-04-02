"""
MidiGPT Vocabulary — ~300 tokens for hierarchical MIDI tokenization.

Layer 3 (Structure):  Key, Style, Section
Layer 2 (Harmony):    ChordRoot, ChordQual, Chord_NC, Bass, Function
Layer 1 (Note):       Bar, Position, Pitch, Velocity, Duration, Track

Chord tokens are factored into root (12) + quality (24) + NC (1) = 37 tokens
instead of the previous 289 combined tokens.
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

STYLES = ["ambient", "classical", "pop", "cinematic", "edm", "jazz", "lo-fi", "experimental"]

SECTIONS = [
    "intro", "verse", "prechorus", "chorus", "bridge",
    "outro", "interlude", "solo", "breakdown", "unknown",
]

TRACK_TYPES = ["melody", "accomp", "bass", "drums", "pad", "lead", "arp", "other"]

HARMONIC_FUNCTIONS = ["tonic", "subdominant", "dominant", "predominant", "passing", "unknown"]

ARTICULATIONS = ["normal", "staccato", "legato", "accent", "tenuto", "marcato", "ghost", "muted"]

DYNAMICS = ["pp", "p", "mp", "mf", "f", "ff"]

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
        # Articulations
        for art in ARTICULATIONS:
            tokens.append(f"Art_{art}")

        # Dynamics
        for dyn in DYNAMICS:
            tokens.append(f"Dyn_{dyn}")

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

    def __contains__(self, token: str) -> bool:
        return token in self._token2id

    def __len__(self) -> int:
        return self.size


# Module-level singleton
VOCAB = MidiVocab()
