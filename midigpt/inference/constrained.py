"""MIDI grammar FSM for constrained decoding.

Inspired by ACE-Step v1.5 ``constrained_logits_processor.py`` (Apache 2.0).
Port adapted for MidiGPT's hierarchical REMI tokenizer. ACE-Step uses
prefix-tree based state transitions to enforce multi-token structured
output (BPM / key / duration). We apply the same *idea* — a small state
machine that masks grammar-violating tokens — but with MIDI-specific
states and constraints.

Why this exists (rules/05-bug-history.md 대조):
  Pre-training and SFT alone cannot guarantee that generated sequences
  follow the ``Bar_N Pos_M (Track_X)? Pitch_P Vel_V Dur_D`` schema.
  When the model emits a stray token in the middle of that sequence
  (e.g. a second Pos_M right after Pitch_P without Vel/Dur), the
  decoder silently drops the incomplete note → DAW 상 무음 구간.
  Same for duplicate (Bar, Pos, Pitch) emissions → Cubase 두 겹.

  Hard-masking at logit time is the single source of truth for these
  invariants (패턴 C — 정책 단일화): the decoder can stop being defensive
  because the grammar never let the bad token through in the first place.

Usage (see inference/engine.py ``_generate_with_harmony``):

    grammar = MidiGrammarFSM(vocab=VOCAB)
    for step in range(max_tokens):
        ...
        # After harmonic mask, before top-k/top-p:
        for b in range(logits.size(0)):
            logits[b] = grammar.apply(logits[b], step=step, batch=b)
        ...
        # After sample:
        for b in range(logits.size(0)):
            grammar.observe(next_token[b].item(), batch=b)

The FSM is *per batch element*; ``apply`` and ``observe`` take a batch
index so a single instance tracks state across parallel sequences.

Reference:
  ACE-Step GitHub (Apache 2.0):
    https://github.com/ace-step/ACE-Step-1.5/blob/main/acestep/constrained_logits_processor.py
  This file ports the *concept* only; no source copy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import torch

from ..tokenizer.vocab import (
    MidiVocab, VOCAB,
    NUM_BARS, NUM_POSITIONS, PITCH_MIN, PITCH_MAX,
    NUM_VELOCITIES, NUM_DURATIONS,
)


class GrammarState(Enum):
    """Where we are in the Pitch→Vel→Dur micro-sequence.

    ANY         — any valid top-level token (Bar/Pos/Track/Chord/Pitch/…)
    EXPECT_VEL  — just emitted Pitch_P; only Vel_* is allowed next
    EXPECT_DUR  — just emitted Vel_V; only Dur_* is allowed next
    """
    ANY = "any"
    EXPECT_VEL = "expect_vel"
    EXPECT_DUR = "expect_dur"


@dataclass
class BatchState:
    """Per-sequence grammar state."""
    state: GrammarState = GrammarState.ANY
    current_bar: int = -1          # -1 = no Bar emitted yet
    current_pos: int = -1
    current_track: str = ""
    # Pitches already emitted at the current (bar, pos, track). Reset on
    # any of those changing. This blocks duplicate (Bar, Pos, Track, Pitch)
    # emissions at the logit stage (6차 리포트 중복 노트 근본 차단).
    pitches_this_slot: set[int] = field(default_factory=set)


class MidiGrammarFSM:
    """Logit-level grammar for MidiGPT's REMI-style vocab."""

    def __init__(
        self,
        vocab: MidiVocab | None = None,
        allow_forward_bar_jump: int = 1,
        dedup_pitches: bool = True,
    ):
        """Build a grammar FSM bound to ``vocab``.

        Args:
            vocab: vocabulary instance (default: module-level ``VOCAB``).
            allow_forward_bar_jump: Maximum Bar_{N→M} forward jump allowed
                in one step. ``1`` = only Bar_N or Bar_{N+1}. ``0`` forbids
                any Bar token once we're in a bar (never desirable). Large
                values degrade to "no constraint" (default: 1).
            dedup_pitches: When True, mask Pitch_P tokens that were already
                emitted at the current (Bar, Pos, Track) slot. Default True.
        """
        self.vocab = vocab or VOCAB
        self.allow_forward_bar_jump = max(0, int(allow_forward_bar_jump))
        self.dedup_pitches = bool(dedup_pitches)

        # Pre-compute token-id ranges once. Contiguous per vocab._build().
        self._bar_ids = self._range_ids("Bar_", NUM_BARS)
        self._pos_ids = self._range_ids("Pos_", NUM_POSITIONS)
        self._pitch_ids = self._pitch_range_ids()
        self._vel_ids = self._range_ids("Vel_", NUM_VELOCITIES)
        self._dur_ids = [
            self.vocab.encode_token(f"Dur_{d}")
            for d in range(1, NUM_DURATIONS + 1)
            if self.vocab.encode_token(f"Dur_{d}") != self.vocab.unk_id
        ]
        # Track_* ids (14 categories from vocab.TRACK_TYPES)
        from ..tokenizer.vocab import TRACK_TYPES
        self._track_ids = [
            self.vocab.encode_token(f"Track_{t}") for t in TRACK_TYPES
            if self.vocab.encode_token(f"Track_{t}") != self.vocab.unk_id
        ]

        # Per-batch state. Allocated lazily when ``apply`` sees a new batch idx.
        self._states: dict[int, BatchState] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def reset(self, batch: int | None = None):
        """Reset FSM state (call before each new generation)."""
        if batch is None:
            self._states.clear()
        else:
            self._states.pop(batch, None)

    def current_bar(self, batch: int = 0) -> int:
        """Return the highest Bar_N index seen on this batch, or -1 if none.

        Used by engine.py's EOS suppression to enforce a minimum bar count
        on generated sequences (8차 리포트: "초반 몇 마디에만 뭉침" 방어).
        """
        st = self._states.get(batch)
        return st.current_bar if st is not None else -1

    def apply(self, logits_row: torch.Tensor, batch: int = 0) -> torch.Tensor:
        """Mask logits that would violate the grammar.

        Args:
            logits_row: 1D tensor of shape (vocab_size,).
            batch: batch index into per-sequence state.

        Returns:
            Modified logits_row (in-place safe — we also return the tensor).
        """
        st = self._states.setdefault(batch, BatchState())

        if st.state == GrammarState.EXPECT_VEL:
            # Only Vel_* allowed. Everything else → -inf.
            mask = torch.ones_like(logits_row, dtype=torch.bool)
            mask[self._vel_ids] = False
            logits_row.masked_fill_(mask, float("-inf"))
            return logits_row

        if st.state == GrammarState.EXPECT_DUR:
            # Only Dur_* allowed.
            mask = torch.ones_like(logits_row, dtype=torch.bool)
            mask[self._dur_ids] = False
            logits_row.masked_fill_(mask, float("-inf"))
            return logits_row

        # --- GrammarState.ANY ---
        # Bar monotonicity: disallow Bar_M with M < current_bar (no going back).
        # Also cap forward jump.
        if st.current_bar >= 0:
            cap = st.current_bar + self.allow_forward_bar_jump
            for bar_n, tid in enumerate(self._bar_ids):
                if bar_n < st.current_bar or bar_n > cap:
                    logits_row[tid] = float("-inf")

        # Pitch dedup at current (bar, pos, track) slot.
        if self.dedup_pitches and st.pitches_this_slot:
            for pitch in st.pitches_this_slot:
                tid = self._pitch_to_id(pitch)
                if tid is not None:
                    logits_row[tid] = float("-inf")

        return logits_row

    def observe(self, token_id: int, batch: int = 0):
        """Update state after a token has been sampled. Call AFTER sampling.

        Any token emitted (even grammar-irrelevant control tokens) counts
        for state transitions — the FSM is stateful per step.
        """
        st = self._states.setdefault(batch, BatchState())

        # State transitions for the Pitch→Vel→Dur micro-sequence.
        if st.state == GrammarState.EXPECT_VEL:
            # A Vel_* was emitted (forced by mask) → next must be Dur.
            st.state = GrammarState.EXPECT_DUR
            return
        if st.state == GrammarState.EXPECT_DUR:
            # A Dur_* was emitted (forced by mask) → back to ANY.
            st.state = GrammarState.ANY
            return

        # state == ANY — inspect the token for context updates.
        tok = self.vocab.decode_id(token_id)
        if tok.startswith("Bar_"):
            try:
                bar_n = int(tok.split("_", 1)[1])
            except ValueError:
                return
            if bar_n != st.current_bar:
                st.current_bar = bar_n
                st.current_pos = -1
                st.pitches_this_slot = set()
            return
        if tok.startswith("Pos_"):
            try:
                pos_n = int(tok.split("_", 1)[1])
            except ValueError:
                return
            if pos_n != st.current_pos:
                st.current_pos = pos_n
                st.pitches_this_slot = set()
            return
        if tok.startswith("Track_"):
            new_track = tok.split("_", 1)[1]
            if new_track != st.current_track:
                st.current_track = new_track
                # Track change within same (bar, pos) → reset pitch set
                # because dedup is keyed by (bar, pos, track).
                st.pitches_this_slot = set()
            return
        if tok.startswith("Pitch_"):
            try:
                pitch = int(tok.split("_", 1)[1])
            except ValueError:
                return
            st.pitches_this_slot.add(pitch)
            st.state = GrammarState.EXPECT_VEL
            return

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _range_ids(self, prefix: str, count: int) -> list[int]:
        """Get contiguous token ids for a ``prefix_{0..count-1}`` group."""
        ids = []
        for i in range(count):
            tid = self.vocab.encode_token(f"{prefix}{i}")
            if tid != self.vocab.unk_id:
                ids.append(tid)
        return ids

    def _pitch_range_ids(self) -> list[int]:
        """Pitch_* token ids (PITCH_MIN..PITCH_MAX)."""
        ids = []
        for p in range(PITCH_MIN, PITCH_MAX + 1):
            tid = self.vocab.encode_token(f"Pitch_{p}")
            if tid != self.vocab.unk_id:
                ids.append(tid)
        return ids

    def _pitch_to_id(self, pitch: int) -> Optional[int]:
        """Pitch value (MIDI 0-127) → token id, or None if out of range."""
        if pitch < PITCH_MIN or pitch > PITCH_MAX:
            return None
        tid = self.vocab.encode_token(f"Pitch_{pitch}")
        return tid if tid != self.vocab.unk_id else None
