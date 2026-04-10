"""
MidiGPT Inference Engine — Runtime for the MIDI AI Workstation app.

Features:
  - Auto device detection (CUDA GPU / CPU)
  - PyTorch or ONNX Runtime backend
  - LoRA hot-swap at runtime
  - Quantized model support (FP16/INT8)
  - Harmonic constraint: masks off-scale pitches during generation
  - KV-cache accelerated decoding (Phase 1)
  - Repetition penalty (Phase 1)
  - No-repeat n-gram blocking (Phase 1)
  - Multi-sample (num_return_sequences) candidate browsing (Phase 1)
"""
from __future__ import annotations

import math
import os
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

import torch
import torch.nn.functional as F

from ..model import MidiGPTConfig, MidiGPT
from ..tokenizer import MidiVocab, MidiEncoder, MidiDecoder
from ..tokenizer.vocab import VOCAB, NOTE_NAMES, PITCH_MIN, PITCH_MAX
from ..tokenizer.encoder import SongMeta, ChordEvent
from ..training.lora import LoRAConfig, apply_lora, load_lora, merge_lora


# ---------------------------------------------------------------------------
# Harmonic constraint tables
# ---------------------------------------------------------------------------
# Semitone intervals from root for each chord quality → associated scale
# Each maps to a set of pitch classes (0-11) relative to root.
_SCALE_INTERVALS: dict[str, list[int]] = {
    # Major family → major scale (Ionian)
    "maj":    [0, 2, 4, 5, 7, 9, 11],
    "maj7":   [0, 2, 4, 5, 7, 9, 11],
    "maj9":   [0, 2, 4, 5, 7, 9, 11],
    "add9":   [0, 2, 4, 5, 7, 9, 11],
    "6":      [0, 2, 4, 5, 7, 9, 11],
    # Minor family → natural minor scale (Aeolian)
    "min":    [0, 2, 3, 5, 7, 8, 10],
    "m7":     [0, 2, 3, 5, 7, 8, 10],
    "m9":     [0, 2, 3, 5, 7, 8, 10],
    "madd9":  [0, 2, 3, 5, 7, 8, 10],
    "m6":     [0, 2, 3, 5, 7, 8, 10],
    # Dominant 7th family → Mixolydian
    "7":      [0, 2, 4, 5, 7, 9, 10],
    "9":      [0, 2, 4, 5, 7, 9, 10],
    "13":     [0, 2, 4, 5, 7, 9, 10],
    "7sus4":  [0, 2, 4, 5, 7, 9, 10],
    # Altered dominant
    "7b9":    [0, 1, 3, 4, 6, 7, 9, 10],  # half-whole diminished
    "7#9":    [0, 2, 3, 4, 7, 9, 10],      # dominant with #9 (blues-adjacent)
    # Diminished → diminished scale (half-whole)
    "dim":    [0, 1, 3, 4, 6, 7, 9, 10],
    "dim7":   [0, 1, 3, 4, 6, 7, 9, 10],
    "m7b5":   [0, 1, 3, 5, 6, 8, 10],      # Locrian
    # Augmented → whole tone scale
    "aug":    [0, 2, 4, 6, 8, 10],
    # Suspended — use parent major/mixolydian scale
    "sus2":   [0, 2, 4, 5, 7, 9, 11],
    "sus4":   [0, 2, 4, 5, 7, 9, 11],
    # 11th chord → Mixolydian
    "11":     [0, 2, 4, 5, 7, 9, 10],
    # Power chord — no 3rd, allow all chromatic (no constraint)
    "5":      [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
}

# Root name → pitch class (C=0)
_ROOT_PC: dict[str, int] = {name: i for i, name in enumerate(NOTE_NAMES)}


def _build_pitch_token_ids(vocab: MidiVocab) -> dict[int, int]:
    """Map token IDs of Pitch_N tokens to their MIDI pitch number."""
    mapping: dict[int, int] = {}
    for midi_pitch in range(PITCH_MIN, PITCH_MAX + 1):
        tok = f"Pitch_{midi_pitch}"
        tid = vocab.encode_token(tok)
        if tid != vocab.unk_id:
            mapping[tid] = midi_pitch
    return mapping


def _parse_chord_token(token: str) -> tuple[int, str] | None:
    """Parse a Chord token string into (root_pitch_class, quality).

    Returns None for non-chord tokens or Chord_NC.
    Handles both new ``ChordRoot_X`` tokens and legacy ``Chord_Cmaj7``
    combined tokens.

    Note: For the new factored vocabulary, call ``_parse_chord_from_context``
    instead, which looks for the ``ChordRoot_`` / ``ChordQual_`` pair.
    """
    # New factored tokens are handled in _parse_chord_from_context.
    # Legacy combined tokens:
    if not token.startswith("Chord_") or token == "Chord_NC":
        return None
    body = token[len("Chord_"):]  # e.g. "C#maj7"
    # Try two-char root first (e.g. C#, D#), then one-char
    for rlen in (2, 1):
        root_name = body[:rlen]
        if root_name in _ROOT_PC:
            quality = body[rlen:]
            if quality in _SCALE_INTERVALS:
                return _ROOT_PC[root_name], quality
    return None


def _parse_chord_from_context(tokens_reversed: list[str]) -> tuple[int, str] | None:
    """Scan decoded tokens (in reverse order) for the newest chord.

    Recognises both the new factored ``ChordRoot_`` + ``ChordQual_``
    token pair and legacy ``Chord_Cmaj7`` combined tokens.

    Args:
        tokens_reversed: Token strings in *reverse* order (newest first).

    Returns:
        ``(root_pitch_class, quality)`` or ``None``.
    """
    # New format: look for ChordQual_ followed (earlier in time, later in
    # reversed list) by ChordRoot_.
    found_qual: str | None = None
    for tok in tokens_reversed:
        if tok.startswith("ChordQual_") and found_qual is None:
            found_qual = tok[len("ChordQual_"):]
        elif tok.startswith("ChordRoot_") and found_qual is not None:
            root_name = tok[len("ChordRoot_"):]
            if root_name in _ROOT_PC and found_qual in _SCALE_INTERVALS:
                return _ROOT_PC[root_name], found_qual
            # Reset and keep searching
            found_qual = None
        # Legacy combined token
        parsed = _parse_chord_token(tok)
        if parsed is not None:
            return parsed

    return None


def _allowed_pitch_classes(root_pc: int, quality: str) -> set[int]:
    """Return the set of absolute pitch classes (0-11) allowed by this chord."""
    intervals = _SCALE_INTERVALS.get(quality)
    if intervals is None:
        return set(range(12))  # unknown quality — allow everything
    return {(root_pc + iv) % 12 for iv in intervals}


# ---------------------------------------------------------------------------
# Phase 1 sampling utilities
# ---------------------------------------------------------------------------
def _apply_repetition_penalty(
    logits: torch.Tensor,
    context_ids: torch.Tensor,
    penalty: float,
) -> torch.Tensor:
    """Penalise tokens that already appear in the context.

    Implementation follows Keskar et al. (CTRL, 2019):
        - For tokens already seen, divide positive logits by ``penalty``
          and multiply negative logits by ``penalty``.  This makes the
          token uniformly less likely regardless of its sign.

    Args:
        logits: shape (B, V).  Modified in place and returned.
        context_ids: shape (B, T).  All tokens generated so far in the
            current sequence.
        penalty: 1.0 = no penalty.  Typical range 1.05-1.3.  Values above
            1.5 tend to break musical structure (kills repeated motifs).
    """
    if penalty == 1.0:
        return logits
    for b in range(logits.size(0)):
        seen = torch.unique(context_ids[b])
        seen_logits = logits[b, seen]
        seen_logits = torch.where(
            seen_logits > 0, seen_logits / penalty, seen_logits * penalty
        )
        logits[b, seen] = seen_logits
    return logits


def _block_repeat_ngrams(
    logits: torch.Tensor,
    context_ids: torch.Tensor,
    ngram_size: int,
) -> torch.Tensor:
    """Set logits to -inf for tokens that would create a repeated n-gram.

    Hugging Face style ``no_repeat_ngram_size`` block.  Helps prevent
    pathological loops like "Bar_3 Bar_3 Bar_3 ..." while still allowing
    intended musical repetition at larger scales (e.g. choruses).

    Args:
        logits: shape (B, V).  Modified in place and returned.
        context_ids: shape (B, T).  Generated context.
        ngram_size: n.  0 disables the feature.  Typical: 3-5.
    """
    if ngram_size <= 0:
        return logits

    for b in range(logits.size(0)):
        seq = context_ids[b].tolist()
        if len(seq) < ngram_size:
            continue
        # The (n-1)-token prefix that the next token would extend.
        prefix = tuple(seq[-(ngram_size - 1):]) if ngram_size > 1 else ()
        banned: set[int] = set()
        for i in range(len(seq) - ngram_size + 1):
            ngram = tuple(seq[i:i + ngram_size])
            if ngram[:-1] == prefix:
                banned.add(ngram[-1])
        if banned:
            banned_t = torch.tensor(list(banned), device=logits.device, dtype=torch.long)
            logits[b, banned_t] = float("-inf")
    return logits


@dataclass
class InferenceConfig:
    """Configuration for inference runtime."""
    model_path: str = ""             # path to midigpt_base.pt
    lora_paths: dict[str, str] | None = None  # name → path mapping
    device: str = "auto"             # auto / cuda / cpu
    use_onnx: bool = False           # use ONNX Runtime instead of PyTorch
    quantize: str = "auto"           # auto / fp16 / fp32


class MidiGPTInference:
    """High-level inference API for the MIDI AI Workstation."""

    def __init__(self, config: InferenceConfig):
        self.config = config
        self.vocab = VOCAB
        self.encoder = MidiEncoder(self.vocab)
        self.decoder = MidiDecoder(self.vocab)

        # Pre-compute pitch token ID → MIDI pitch mapping (for harmonic constraint)
        self._pitch_token_ids = _build_pitch_token_ids(self.vocab)

        # Detect device
        self.device = self._detect_device(config.device)

        # Load model
        self.model: MidiGPT | None = None
        self.model_config: MidiGPTConfig | None = None
        self._active_lora: str | None = None

        if config.model_path and Path(config.model_path).exists():
            self.load_model(config.model_path)

    # ------------------------------------------------------------------
    # Device detection
    # ------------------------------------------------------------------
    def _detect_device(self, preference: str) -> torch.device:
        """Auto-detect best available device."""
        if preference == "auto":
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
                print(f"MidiGPT: Using GPU — {gpu_name} ({vram_gb:.1f}GB)")
                return torch.device("cuda")
            else:
                print("MidiGPT: Using CPU (no GPU detected)")
                return torch.device("cpu")
        return torch.device(preference)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------
    def load_model(self, model_path: str):
        """Load base model from checkpoint."""
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=True)

        if "config" in checkpoint:
            self.model_config = MidiGPTConfig(**checkpoint["config"])
        else:
            self.model_config = MidiGPTConfig(vocab_size=self.vocab.size)

        self.model = MidiGPT(self.model_config).to(self.device)

        if "model_state_dict" in checkpoint:
            self.model.load_state_dict(checkpoint["model_state_dict"])
        else:
            self.model.load_state_dict(checkpoint)

        self.model.eval()

        # Auto quantize based on device
        if self.config.quantize == "auto" and self.device.type == "cuda":
            self.model = self.model.half()  # FP16 on GPU
            print("MidiGPT: Model loaded (FP16)")
        else:
            print("MidiGPT: Model loaded (FP32)")

    def load_lora(self, name: str, path: str | None = None):
        """Load and activate a LoRA adapter."""
        if self.model is None:
            raise RuntimeError("Base model not loaded")

        if path is None and self.config.lora_paths:
            path = self.config.lora_paths.get(name)

        if path is None or not Path(path).exists():
            print(f"MidiGPT: LoRA '{name}' not found at {path}")
            return

        lora_config = LoRAConfig(r=16, alpha=32, target_modules=["q_proj", "v_proj", "o_proj"])
        apply_lora(self.model, lora_config)
        load_lora(self.model, path)
        self._active_lora = name
        self.model.eval()
        print(f"MidiGPT: LoRA '{name}' loaded")

    # ------------------------------------------------------------------
    # Harmonic constraint helpers
    # ------------------------------------------------------------------
    def _find_active_chord(self, token_ids: list[int]) -> tuple[int, str] | None:
        """Scan token_ids backwards to find the most recent Chord.

        Handles both new factored ``ChordRoot_``/``ChordQual_`` pairs
        and legacy combined ``Chord_Cmaj7`` tokens.

        Returns (root_pitch_class, quality) or None.
        """
        tokens_reversed = [self.vocab.decode_id(tid) for tid in reversed(token_ids)]
        return _parse_chord_from_context(tokens_reversed)

    def _apply_harmonic_mask(
        self, logits: torch.Tensor, context_ids: list[int]
    ) -> torch.Tensor:
        """Mask pitch tokens that fall outside the active chord's scale.

        Args:
            logits: Raw logits for the next token, shape (vocab_size,)
            context_ids: All token IDs generated so far (used to find active chord)

        Returns:
            logits with disallowed Pitch tokens set to -inf.
        """
        chord_info = self._find_active_chord(context_ids)
        if chord_info is None:
            return logits  # no chord context — no constraint

        root_pc, quality = chord_info
        allowed_pcs = _allowed_pitch_classes(root_pc, quality)

        for token_id, midi_pitch in self._pitch_token_ids.items():
            pc = midi_pitch % 12
            if pc not in allowed_pcs:
                logits[token_id] = float("-inf")

        return logits

    def _generate_with_harmony(
        self,
        idx: torch.Tensor,
        max_new_tokens: int = 512,
        min_new_tokens: int = 0,
        temperature: float = 0.9,
        top_k: int = 50,
        top_p: float = 0.95,
        eos_id: int = 2,
        repetition_penalty: float = 1.0,
        no_repeat_ngram_size: int = 0,
        use_kv_cache: bool = True,
    ) -> torch.Tensor:
        """Autoregressive generation with harmonic constraint.

        Mirrors :meth:`MidiGPT.generate` but applies a scale-aware mask on
        pitch tokens before sampling, preventing notes outside the current
        chord's scale.

        Phase 1 additions:
          * KV-cache acceleration (``use_kv_cache``) — O(1) per step.
          * Repetition penalty (``repetition_penalty``) — CTRL-style.
          * No-repeat n-gram blocking (``no_repeat_ngram_size``).

        Phase 1.1 (BUG 4/5 fix): ``min_new_tokens`` suppresses the EOS
        token until at least that many tokens have been generated. The
        previous behaviour produced ~1KB / 2-5 second MIDIs because the
        overfit base model emits EOS within the first few steps.

        All new options default to backwards-compatible values, so existing
        callers see identical behaviour unless they opt in.
        """
        assert self.model is not None
        self.model.eval()
        block_size = self.model.config.block_size

        past_kv_list: Optional[list[Tuple[torch.Tensor, torch.Tensor]]] = None

        for step in range(max_new_tokens):
            # ----- Forward pass -----
            if use_kv_cache:
                if past_kv_list is None:
                    # Prefill: process the whole prompt once.
                    idx_input = idx if idx.size(1) <= block_size \
                        else idx[:, -block_size:]
                    logits, _, past_kv_list = self.model(idx_input, past_kv_list=None)
                else:
                    cur_len = past_kv_list[0][0].size(2) + 1
                    if cur_len > block_size:
                        # Cache would overflow — re-prefill from the tail.
                        past_kv_list = None
                        idx_input = idx[:, -block_size:]
                        logits, _, past_kv_list = self.model(
                            idx_input, past_kv_list=None
                        )
                    else:
                        logits, _, past_kv_list = self.model(
                            idx[:, -1:], past_kv_list=past_kv_list,
                        )
            else:
                # Legacy path: recompute every step.
                idx_cond = idx if idx.size(1) <= block_size \
                    else idx[:, -block_size:]
                logits, _, _ = self.model(idx_cond)

            logits = logits[:, -1, :]  # (B, V)

            # ----- Repetition penalty (before temperature, before mask) -----
            if repetition_penalty != 1.0:
                logits = _apply_repetition_penalty(logits, idx, repetition_penalty)

            # ----- No-repeat n-gram blocking -----
            if no_repeat_ngram_size > 0:
                logits = _block_repeat_ngrams(logits, idx, no_repeat_ngram_size)

            # ----- Suppress EOS until min_new_tokens reached (BUG 4/5 fix) -----
            # Without this, an overfit base model emits EOS within the first
            # few steps, producing ~1KB / 2-5 second MIDIs. Forcing a floor on
            # the generation length is the standard fix (cf. HF transformers
            # ``min_new_tokens`` / ``min_length`` parameters).
            if min_new_tokens > 0 and step < min_new_tokens:
                logits[:, eos_id] = float("-inf")

            # Apply temperature
            logits = logits / temperature

            # ----- Harmonic constraint (per batch element) -----
            for b in range(logits.size(0)):
                context = idx[b].tolist()
                logits[b] = self._apply_harmonic_mask(logits[b], context)

            # ----- Top-K filtering -----
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float("-inf")

            # ----- Top-P (nucleus) filtering -----
            if top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(logits, descending=True)
                cumulative_probs = torch.cumsum(
                    F.softmax(sorted_logits, dim=-1), dim=-1
                )
                sorted_mask = (
                    cumulative_probs - F.softmax(sorted_logits, dim=-1) > top_p
                )
                sorted_logits[sorted_mask] = float("-inf")
                logits = sorted_logits.scatter(1, sorted_indices, sorted_logits)

            # ----- Sample -----
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Append
            idx = torch.cat([idx, next_token], dim=1)

            # Stop on EOS
            if (next_token == eos_id).all():
                break

        return idx

    # ------------------------------------------------------------------
    # Beam search decoding
    # ------------------------------------------------------------------
    def beam_search(
        self,
        input_ids: torch.Tensor,
        max_tokens: int = 1024,
        min_new_tokens: int = 256,
        beam_width: int = 4,
        length_penalty: float = 1.0,
        chords: list | None = None,
    ) -> list[tuple[list[int], float]]:
        """Return top ``beam_width`` sequences sorted by score (highest first).

        Each entry is ``(token_ids, log_probability_score)``.

        Args:
            input_ids: Prompt token tensor of shape ``(1, T)``.
            max_tokens: Maximum number of new tokens to generate.
            min_new_tokens: Suppress EOS until this many tokens are emitted.
            beam_width: Number of beams to maintain at each step.
            length_penalty: Exponent applied to sequence length in scoring.
                ``>1`` prefers longer sequences, ``<1`` prefers shorter ones.
            chords: Optional chord events for harmonic masking.

        Returns:
            List of ``(token_ids, score)`` tuples sorted by descending score.
        """
        assert self.model is not None
        self.model.eval()

        eos_id = self.vocab.eos_id
        prompt_len = input_ids.size(1)

        # Each beam: (token_id_list, cumulative_log_prob)
        active_beams: list[tuple[list[int], float]] = [
            (input_ids[0].tolist(), 0.0),
        ]
        finished_beams: list[tuple[list[int], float]] = []

        for step in range(max_tokens):
            all_candidates: list[tuple[list[int], float]] = []

            for seq, cum_log_prob in active_beams:
                seq_tensor = torch.tensor(
                    [seq], dtype=torch.long, device=self.device,
                )
                block_size = self.model.config.block_size
                seq_cond = seq_tensor if seq_tensor.size(1) <= block_size \
                    else seq_tensor[:, -block_size:]

                with torch.no_grad():
                    logits, _, _ = self.model(seq_cond)
                logits = logits[:, -1, :]  # (1, V)

                # Suppress EOS until min_new_tokens reached
                new_tokens_so_far = len(seq) - prompt_len
                if min_new_tokens > 0 and new_tokens_so_far < min_new_tokens:
                    logits[:, eos_id] = float("-inf")

                # Harmonic constraint
                context = seq
                logits[0] = self._apply_harmonic_mask(logits[0], context)

                # Convert to log probabilities
                log_probs = F.log_softmax(logits[0], dim=-1)  # (V,)

                # Select top-k candidates (k = beam_width * 2)
                k = min(beam_width * 2, log_probs.size(-1))
                top_log_probs, top_indices = torch.topk(log_probs, k)

                for i in range(k):
                    token_id = top_indices[i].item()
                    token_log_prob = top_log_probs[i].item()
                    new_seq = seq + [token_id]
                    new_cum = cum_log_prob + token_log_prob

                    if token_id == eos_id:
                        # Length-normalised score
                        gen_len = len(new_seq) - prompt_len
                        score = new_cum / (gen_len ** length_penalty)
                        finished_beams.append((new_seq, score))
                    else:
                        all_candidates.append((new_seq, new_cum))

            # If no active candidates remain, stop
            if not all_candidates:
                break

            # Keep only the top beam_width candidates by cumulative log prob
            # (length penalty is applied only to finished beams for ranking)
            all_candidates.sort(key=lambda x: x[1], reverse=True)
            active_beams = all_candidates[:beam_width]

            # Early stop: enough finished beams
            if len(finished_beams) >= beam_width:
                break

        # Move remaining active beams to finished (force-finish)
        for seq, cum_log_prob in active_beams:
            gen_len = len(seq) - prompt_len
            if gen_len > 0:
                score = cum_log_prob / (gen_len ** length_penalty)
            else:
                score = cum_log_prob
            finished_beams.append((seq, score))

        # Sort by score descending and return top beam_width
        finished_beams.sort(key=lambda x: x[1], reverse=True)
        return finished_beams[:beam_width]

    # ------------------------------------------------------------------
    # Self-consistency scoring
    # ------------------------------------------------------------------
    def score_sequence(self, token_ids: list[int]) -> dict:
        """Score a generated token sequence on musical quality metrics.

        Analyses the token stream for scale adherence, rhythmic stability,
        pitch range usage, and repetition patterns.

        Args:
            token_ids: List of token IDs (the generated portion only).

        Returns:
            Dictionary with keys:
                - ``scale_consistency``: float 0-1 (pitch-in-scale ratio)
                - ``rhythm_stability``: float 0-1 (position pattern regularity)
                - ``pitch_range``: float 0-1 (appropriate pitch range usage)
                - ``repetition_score``: float 0-1 (penalises excessive repetition)
                - ``total``: float 0-1 (weighted average)
        """
        tokens = [self.vocab.decode_id(tid) for tid in token_ids]

        scale_consistency = self._score_scale_consistency(tokens)
        rhythm_stability = self._score_rhythm_stability(tokens)
        pitch_range = self._score_pitch_range(tokens)
        repetition_score = self._score_repetition(token_ids)

        total = (
            0.4 * scale_consistency
            + 0.2 * rhythm_stability
            + 0.2 * pitch_range
            + 0.2 * repetition_score
        )

        return {
            "scale_consistency": round(scale_consistency, 4),
            "rhythm_stability": round(rhythm_stability, 4),
            "pitch_range": round(pitch_range, 4),
            "repetition_score": round(repetition_score, 4),
            "total": round(total, 4),
        }

    def _score_scale_consistency(self, tokens: list[str]) -> float:
        """Ratio of pitch tokens that fall within the active chord's scale."""
        total_pitches = 0
        in_scale_pitches = 0
        # Track current chord context (forward scan: ChordRoot_ then ChordQual_)
        current_root_pc: int | None = None
        current_quality: str | None = None
        pending_root: str | None = None

        for tok in tokens:
            # Track chord changes (factored format: Root emitted first, Qual second)
            if tok.startswith("ChordRoot_"):
                pending_root = tok[len("ChordRoot_"):]
            elif tok.startswith("ChordQual_") and pending_root is not None:
                qual = tok[len("ChordQual_"):]
                if pending_root in _ROOT_PC and qual in _SCALE_INTERVALS:
                    current_root_pc = _ROOT_PC[pending_root]
                    current_quality = qual
                pending_root = None
            else:
                # Legacy combined chord token
                parsed = _parse_chord_token(tok)
                if parsed is not None:
                    current_root_pc, current_quality = parsed

            # Score pitch tokens
            if tok.startswith("Pitch_"):
                try:
                    midi_pitch = int(tok[len("Pitch_"):])
                except ValueError:
                    continue
                total_pitches += 1
                if current_root_pc is not None and current_quality is not None:
                    allowed = _allowed_pitch_classes(current_root_pc, current_quality)
                    if midi_pitch % 12 in allowed:
                        in_scale_pitches += 1
                else:
                    # No chord context yet — count as in-scale
                    in_scale_pitches += 1

        if total_pitches == 0:
            return 1.0
        return in_scale_pitches / total_pitches

    def _score_rhythm_stability(self, tokens: list[str]) -> float:
        """Measure how regular the position token distribution is.

        A fully uniform distribution (random) scores low; concentrated
        positions (implying a rhythmic pattern) score high.
        """
        positions: list[int] = []
        for tok in tokens:
            if tok.startswith("Pos_"):
                try:
                    positions.append(int(tok[len("Pos_"):]))
                except ValueError:
                    continue

        if len(positions) < 2:
            return 1.0

        # Use normalised entropy: 0 = one value only (max stability),
        # 1 = uniform distribution (min stability).
        counts = Counter(positions)
        n = len(positions)
        num_distinct = len(counts)
        if num_distinct <= 1:
            return 1.0

        entropy = -sum((c / n) * math.log2(c / n) for c in counts.values())
        max_entropy = math.log2(num_distinct)
        if max_entropy == 0:
            return 1.0

        normalised = entropy / max_entropy
        # Invert: low entropy = high stability
        return 1.0 - normalised * 0.5  # scale so uniform → 0.5, not 0

    def _score_pitch_range(self, tokens: list[str]) -> float:
        """Score based on pitch range used.

        Ideal range: 2-4 octaves (24-48 semitones) → 1.0.
        < 1 octave (12 semitones) → reduced score.
        > 5 octaves (60 semitones) → reduced score.
        """
        pitches: list[int] = []
        for tok in tokens:
            if tok.startswith("Pitch_"):
                try:
                    pitches.append(int(tok[len("Pitch_"):]))
                except ValueError:
                    continue

        if len(pitches) < 2:
            return 1.0

        pitch_range = max(pitches) - min(pitches)

        if pitch_range < 12:
            # Less than 1 octave: linear ramp from 0.3 at range=0 to 0.8 at range=11
            return 0.3 + 0.5 * (pitch_range / 12)
        elif pitch_range <= 48:
            # 1-4 octaves: ideal range
            return 1.0
        elif pitch_range <= 60:
            # 4-5 octaves: slight penalty
            return 1.0 - 0.3 * ((pitch_range - 48) / 12)
        else:
            # > 5 octaves: heavier penalty, floor at 0.3
            return max(0.3, 0.7 - 0.2 * ((pitch_range - 60) / 12))

    def _score_repetition(self, token_ids: list[int]) -> float:
        """Score based on 4-gram repetition ratio.

        0% repetition → 1.0.  50%+ repetition → 0.0.
        Linear interpolation between.
        """
        n = 4
        if len(token_ids) < n:
            return 1.0

        ngrams: list[tuple[int, ...]] = []
        for i in range(len(token_ids) - n + 1):
            ngrams.append(tuple(token_ids[i:i + n]))

        total = len(ngrams)
        unique = len(set(ngrams))
        repetition_ratio = 1.0 - (unique / total)  # 0 = all unique, 1 = all same

        # Map: 0% → 1.0,  50%+ → 0.0
        score = max(0.0, 1.0 - repetition_ratio * 2.0)
        return score

    # ------------------------------------------------------------------
    # Generation API
    # ------------------------------------------------------------------
    def generate_variation(
        self,
        midi_path: str | None = None,
        notes: list[dict] | None = None,
        meta: SongMeta | None = None,
        chords: list[ChordEvent] | None = None,
        max_tokens: int = 1024,
        min_new_tokens: int = 256,
        temperature: float = 0.9,
        top_k: int = 50,
        top_p: float = 0.95,
        repetition_penalty: float = 1.0,
        no_repeat_ngram_size: int = 0,
        num_return_sequences: int = 1,
        use_kv_cache: bool = True,
        use_beam_search: bool = False,
        beam_width: int = 4,
        length_penalty: float = 1.0,
        score_and_rank: bool = False,
    ) -> list[dict] | list[list[dict]]:
        """Generate a MIDI variation.

        Args:
            midi_path: Input MIDI file path (alternative to notes)
            notes: Input note list [{pitch, velocity, start_tick, duration_tick, track_type}]
            meta: Song metadata (key, style, section, tempo)
            chords: Chord analysis results
            max_tokens: Maximum tokens to generate
            min_new_tokens: Suppress EOS until at least this many tokens
                have been emitted. Set ``0`` to disable. Default ``256`` —
                this is the BUG 4/5 fix that prevents the overfit base
                model from terminating after only a handful of tokens.
            temperature: Sampling temperature
            top_k: Top-K sampling
            top_p: Nucleus sampling
            repetition_penalty: CTRL-style penalty for repeated tokens.
                ``1.0`` disables (default).  Recommended range: 1.05-1.2.
                Values > 1.5 break musical motif repetition.
            no_repeat_ngram_size: Block any n-gram of this length from
                repeating.  ``0`` disables (default).  Recommended: 3-5.
            num_return_sequences: Number of independent variations to
                generate in a single call.  When > 1, the return type
                becomes ``list[list[dict]]`` (one note list per variation).
            use_kv_cache: Use KV cache for O(1) per-step decoding.
                Default ``True``; set ``False`` for the legacy recompute
                path (e.g. for debugging).
            use_beam_search: Use beam search decoding instead of sampling.
                Default ``False``.
            beam_width: Number of beams for beam search decoding.
                Only used when ``use_beam_search=True``.  Default ``4``.
            length_penalty: Exponent for beam search length normalisation.
                ``>1`` prefers longer sequences, ``<1`` shorter.  Default ``1.0``.
            score_and_rank: When ``True``, generate ``num_return_sequences``
                candidates via sampling, then rank them by
                :meth:`score_sequence` (highest total score first).
                Default ``False``.

        Returns:
            * ``num_return_sequences == 1``: list of note dicts.
            * ``num_return_sequences > 1``:  list of (list of note dicts).
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        # Encode input
        if midi_path:
            input_ids = self.encoder.encode_file(midi_path, meta=meta, chords=chords)
        elif notes:
            input_ids = self.encoder.encode_notes(notes, meta=meta, chords=chords)
        else:
            raise ValueError("Provide either midi_path or notes")

        # Remove EOS from input (we want the model to continue)
        if input_ids and input_ids[-1] == self.vocab.eos_id:
            input_ids = input_ids[:-1]

        # Add SEP token to signal "now generate variation"
        input_ids.append(self.vocab.sep_id)
        sep_pos = len(input_ids)

        start_time = time.time()
        variations: list[list[dict]] = []

        if use_beam_search:
            # --- Beam search path ---
            input_tensor = torch.tensor(
                [input_ids], dtype=torch.long, device=self.device,
            )
            beam_results = self.beam_search(
                input_tensor,
                max_tokens=max_tokens,
                min_new_tokens=min_new_tokens,
                beam_width=beam_width,
                length_penalty=length_penalty,
                chords=chords,
            )
            for seq, _score in beam_results:
                variation_ids = seq[sep_pos:]
                decoded_notes = self.decoder.decode_to_notes(variation_ids)
                note_dicts = [
                    {
                        "pitch": n.pitch,
                        "velocity": n.velocity,
                        "start_tick": n.start_tick,
                        "duration_tick": n.duration_tick,
                        "track_type": n.track_type,
                    }
                    for n in decoded_notes
                ]
                variations.append(note_dicts)
        else:
            # --- Sampling path (original behaviour) ---
            for seq_idx in range(max(1, num_return_sequences)):
                input_tensor = torch.tensor(
                    [input_ids], dtype=torch.long, device=self.device
                )
                with torch.no_grad():
                    output = self._generate_with_harmony(
                        input_tensor,
                        max_new_tokens=max_tokens,
                        min_new_tokens=min_new_tokens,
                        temperature=temperature,
                        top_k=top_k,
                        top_p=top_p,
                        eos_id=self.vocab.eos_id,
                        repetition_penalty=repetition_penalty,
                        no_repeat_ngram_size=no_repeat_ngram_size,
                        use_kv_cache=use_kv_cache,
                    )

                variation_ids = output[0].tolist()[sep_pos:]
                decoded_notes = self.decoder.decode_to_notes(variation_ids)
                note_dicts = [
                    {
                        "pitch": n.pitch,
                        "velocity": n.velocity,
                        "start_tick": n.start_tick,
                        "duration_tick": n.duration_tick,
                        "track_type": n.track_type,
                    }
                    for n in decoded_notes
                ]
                variations.append(note_dicts)

        # --- Self-consistency scoring & ranking ---
        if score_and_rank and len(variations) > 1:
            scored: list[tuple[list[dict], float]] = []
            for var_notes in variations:
                # Re-encode notes to token IDs for scoring
                var_token_ids = self.encoder.encode_notes(var_notes, meta=meta, chords=chords)
                scores = self.score_sequence(var_token_ids)
                scored.append((var_notes, scores["total"]))
            scored.sort(key=lambda x: x[1], reverse=True)
            variations = [v for v, _s in scored]

        elapsed = time.time() - start_time
        total_notes = sum(len(v) for v in variations)
        print(
            f"MidiGPT: Generated {len(variations)} variation(s), "
            f"{total_notes} notes total in {elapsed:.2f}s"
        )

        if num_return_sequences <= 1 and not use_beam_search:
            return variations[0]
        return variations

    def generate_to_midi(
        self,
        midi_path: str,
        output_path: str,
        meta: SongMeta | None = None,
        chords: list[ChordEvent] | None = None,
        max_tokens: int = 1024,
        min_new_tokens: int = 256,
        temperature: float = 0.9,
        top_k: int = 50,
        top_p: float = 0.95,
        repetition_penalty: float = 1.0,
        no_repeat_ngram_size: int = 0,
        use_kv_cache: bool = True,
    ) -> str:
        """Generate variation and save as MIDI file.

        See :meth:`generate_variation` for parameter documentation.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        input_ids = self.encoder.encode_file(midi_path, meta=meta, chords=chords)
        if input_ids and input_ids[-1] == self.vocab.eos_id:
            input_ids = input_ids[:-1]
        input_ids.append(self.vocab.sep_id)

        input_tensor = torch.tensor([input_ids], dtype=torch.long, device=self.device)

        with torch.no_grad():
            output = self._generate_with_harmony(
                input_tensor,
                max_new_tokens=max_tokens,
                min_new_tokens=min_new_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                eos_id=self.vocab.eos_id,
                repetition_penalty=repetition_penalty,
                no_repeat_ngram_size=no_repeat_ngram_size,
                use_kv_cache=use_kv_cache,
            )

        variation_ids = output[0].tolist()[len(input_ids):]
        tempo = meta.tempo if meta else 120.0
        self.decoder.decode_to_midi(variation_ids, output_path, tempo=tempo)
        return output_path

    # ------------------------------------------------------------------
    # Status / info
    # ------------------------------------------------------------------
    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    @property
    def active_lora(self) -> str | None:
        return self._active_lora

    def get_status(self) -> dict:
        """Get current inference engine status."""
        status = {
            "loaded": self.is_loaded,
            "device": str(self.device),
            "active_lora": self._active_lora,
            "vocab_size": self.vocab.size,
        }
        if self.model_config:
            status["model_params"] = f"{self.model_config.num_params / 1e6:.1f}M"
        if self.device.type == "cuda":
            status["gpu"] = torch.cuda.get_device_name(0)
            status["vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)
        return status
