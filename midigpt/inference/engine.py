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

import copy
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
from ..tokenizer.encoder import SongMeta, ChordEvent, SongContext, TrackRole
from ..training.lora import (
    LoRAConfig, apply_lora, load_lora, merge_lora,
    load_lora_weights_only, copy_weights_into_model, zero_lora_weights,
)
from .constrained import MidiGrammarFSM


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


# Chord-tone intervals — the *strong* tones of each chord (root / 3rd / 5th /
# 7th). Used by _apply_harmonic_mask to BOOST these pitches on top of the
# scale mask, answering defect #3 of 2026-04-21 결함리스트: the old mask
# was a binary scale filter so `D, F, A, B` were just as likely as chord
# tones on a C maj chord. Boosting chord tones makes the generated line
# actually sound like "the chord" instead of "some scale".
_CHORD_TONE_INTERVALS: dict[str, list[int]] = {
    "maj":    [0, 4, 7],
    "maj7":   [0, 4, 7, 11],
    "maj9":   [0, 4, 7, 11],
    "add9":   [0, 4, 7],
    "6":      [0, 4, 7, 9],
    "min":    [0, 3, 7],
    "m7":     [0, 3, 7, 10],
    "m9":     [0, 3, 7, 10],
    "madd9":  [0, 3, 7],
    "m6":     [0, 3, 7, 9],
    "7":      [0, 4, 7, 10],
    "9":      [0, 4, 7, 10],
    "13":     [0, 4, 7, 10],
    "7sus4":  [0, 5, 7, 10],
    "sus4":   [0, 5, 7],
    "sus2":   [0, 2, 7],
    "dim":    [0, 3, 6],
    "dim7":   [0, 3, 6, 9],
    "m7b5":   [0, 3, 6, 10],
    "aug":    [0, 4, 8],
    "aug7":   [0, 4, 8, 10],
}


def _chord_tone_pitch_classes(root_pc: int, quality: str) -> set[int]:
    """Return the strong-tone pitch classes (root/3rd/5th/7th) for this chord."""
    intervals = _CHORD_TONE_INTERVALS.get(quality)
    if intervals is None:
        # Unknown quality — fall back to a plain triad so at least the root
        # and fifth are boosted. Safer than an empty set (no boost at all).
        intervals = [0, 4, 7]
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

        # Sprint 43 GGG2 — 다중 LoRA 레지스트리.
        # register_lora 가 파일 → dict preload, activate_lora 가 dict → live 복사.
        # 기존 load_lora 는 register + activate 조합으로 호환 유지.
        self._lora_registry: dict[str, dict[str, torch.Tensor]] = {}
        self._lora_structure_applied: bool = False  # apply_lora 한 번만 호출

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
                print(f"MidiGPT: Using GPU - {gpu_name} ({vram_gb:.1f}GB)")
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

    def _ensure_lora_structure(self, reference_path: str) -> None:
        """apply_lora 를 한 번만 호출해 LoRALinear 레이어를 주입.

        LoRA 파일에서 r/alpha 를 읽어 모델 기본값과 병합. 구조 주입 후에는
        _lora_structure_applied=True 로 잠금 — 이후 LoRA 는 weight 만 교체.
        (다른 r/alpha LoRA 섞어 로드 금지 — copy_weights_into_model 에서 shape 검증.)
        """
        if self._lora_structure_applied:
            return
        checkpoint = torch.load(reference_path, map_location=self.device,
                                weights_only=False)
        if isinstance(checkpoint, dict) and "lora_config" in checkpoint:
            saved_cfg = checkpoint["lora_config"]
            lora_config = LoRAConfig(
                r=saved_cfg.get("r", self.model_config.lora_rank),
                alpha=saved_cfg.get("alpha", saved_cfg.get("r", 32) * 2),
                target_modules=saved_cfg.get("target_modules",
                                             self.model_config.lora_target_modules),
            )
        else:
            lora_config = LoRAConfig(
                r=self.model_config.lora_rank,
                alpha=self.model_config.lora_rank * 2,
                target_modules=self.model_config.lora_target_modules,
            )
        apply_lora(self.model, lora_config)
        # 방금 apply 한 LoRA 는 random 초기화 — activate 되기 전까지 zero 로 하여
        # base 모델 forward 결과와 동일하게 유지.
        zero_lora_weights(self.model)
        self._lora_structure_applied = True
        print(f"MidiGPT: LoRA 구조 주입 (r={lora_config.r})")

    def register_lora(self, name: str, path: str | None = None) -> None:
        """파일에서 LoRA weights 만 메모리로 로드 (모델은 unchanged).

        Sprint 43 GGG2. 여러 LoRA 를 미리 등록해 두고 `activate_lora(name)` 로
        빠르게 전환할 수 있다. 첫 register 에서만 apply_lora 호출.
        """
        if self.model is None:
            raise RuntimeError("Base model not loaded")
        if path is None and self.config.lora_paths:
            path = self.config.lora_paths.get(name)
        if path is None or not Path(path).exists():
            print(f"MidiGPT: LoRA '{name}' not found at {path}")
            return

        self._ensure_lora_structure(path)
        self._lora_registry[name] = load_lora_weights_only(path)
        print(f"MidiGPT: LoRA '{name}' registered (메모리 preload)")

    def activate_lora(self, name: str | None) -> None:
        """등록된 LoRA 로 live weights 교체. name=None 이면 deactivate (zero)."""
        if self.model is None:
            raise RuntimeError("Base model not loaded")
        if name is None:
            if self._lora_structure_applied:
                zero_lora_weights(self.model)
            self._active_lora = None
            print("MidiGPT: LoRA deactivated (identity)")
            return
        if name not in self._lora_registry:
            raise KeyError(f"LoRA '{name}' 등록 안 됨 — register_lora 선행 필요")
        copied = copy_weights_into_model(self.model, self._lora_registry[name])
        self._active_lora = name
        self.model.eval()
        print(f"MidiGPT: LoRA '{name}' activated ({copied} layer pairs)")

    def registered_loras(self) -> list[str]:
        return sorted(self._lora_registry.keys())

    def blend_loras(self, weights: dict[str, float]) -> None:
        """Sprint 44 HHH2 — 여러 등록된 LoRA 의 가중 평균으로 활성화.

        weights 합이 1.0 이어야 할 필요는 없음 (over/under-drive 허용).
        미등록 이름 → KeyError. 빈 dict → deactivate.
        active_lora = "blend:(jazz:0.7|classical:0.3)" 형식으로 표기.
        """
        if self.model is None:
            raise RuntimeError("Base model not loaded")
        if not weights:
            self.activate_lora(None)
            return
        unknown = [n for n in weights if n not in self._lora_registry]
        if unknown:
            raise KeyError(f"LoRA '{unknown}' 등록 안 됨 — register_lora 선행")
        if not self._lora_structure_applied:
            raise RuntimeError("LoRA 구조 미주입 — register_lora 를 먼저 호출해야 함")

        from ..training.lora import LoRALinear
        # 가중합 dict 만들기: 각 key 는 state_dict 의 "<layer>.lora_A/B"
        blended: dict[str, torch.Tensor] = {}
        for name, w in weights.items():
            for k, v in self._lora_registry[name].items():
                if not (k.endswith(".lora_A") or k.endswith(".lora_B")):
                    continue
                if k in blended:
                    blended[k] = blended[k] + float(w) * v.float()
                else:
                    blended[k] = float(w) * v.float()

        # live 모델에 복사 — copy_weights_into_model 사용 (shape 검증 재사용)
        copied = copy_weights_into_model(self.model, blended)
        self.model.eval()
        tag = "|".join(f"{n}:{w:g}" for n, w in weights.items())
        self._active_lora = f"blend:({tag})"
        print(f"MidiGPT: LoRA blend activated ({copied} layer pairs) — {tag}")

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
        self, logits: torch.Tensor, context_ids: list[int],
        chord_tone_boost: float = 1.5,
    ) -> torch.Tensor:
        """Mask off-scale pitches + boost chord-tone pitches.

        2026-04-21 결함리스트 #3 대응: 이전 버전은 scale 외부만 -inf 로
        자르는 binary 마스크라 C maj 화음에서도 D/F/A/B 가 chord-tone 과
        동등한 확률로 뽑혔다. 결과적으로 "같은 조성 안에서 헤매는 음"이
        나오고 "해당 코드가 들리는 반주"가 안 됨.

        이번 구현은 두 단계 —
          (1) off-scale → -inf (기존 동작 유지)
          (2) chord tone (root/3rd/5th/7th) 의 양수 logit 에 배수 가산
              점수를 더해 샘플링 확률을 끌어올림. chord_tone_boost=1.5 는
              softmax 후 대략 chord tone 의 상대 확률을 50% 정도 높이는
              수준으로 과도한 지배(1.0 확률)를 피하면서 조성감 확보.
              0 이하는 boost 없음과 동치.

        Args:
            logits: Raw logits for the next token, shape (vocab_size,)
            context_ids: All token IDs generated so far (used to find active chord)
            chord_tone_boost: multiplier applied to positive logits at chord-
                tone pitches. 1.0 = 기존 동작. 1.3~1.8 권장.

        Returns:
            logits with off-scale Pitch tokens set to -inf and chord tones
            biased upward.
        """
        chord_info = self._find_active_chord(context_ids)
        if chord_info is None:
            return logits  # no chord context — no constraint

        root_pc, quality = chord_info
        allowed_pcs = _allowed_pitch_classes(root_pc, quality)
        chord_pcs   = _chord_tone_pitch_classes(root_pc, quality) \
                      if chord_tone_boost > 1.0 else set()

        for token_id, midi_pitch in self._pitch_token_ids.items():
            pc = midi_pitch % 12
            if pc not in allowed_pcs:
                logits[token_id] = float("-inf")
            elif pc in chord_pcs:
                v = logits[token_id].item()
                # Only upscale positive evidence; leaving negatives alone
                # avoids "rescuing" pitches the model already didn't want.
                if v > 0:
                    logits[token_id] = v * chord_tone_boost

        return logits

    def _generate_with_harmony(
        self,
        idx: torch.Tensor,
        max_new_tokens: int = 512,
        min_new_tokens: int = 0,
        min_bars: int = 0,                 # 8차 대응 — bar-count 기반 EOS suppression
        temperature: float = 0.9,
        top_k: int = 50,
        top_p: float = 0.95,
        eos_id: int = 2,
        repetition_penalty: float = 1.0,
        no_repeat_ngram_size: int = 0,
        use_kv_cache: bool = True,
        grammar: Optional[MidiGrammarFSM] = None,
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

            # 8차 리포트 대응 — min_bars 기반 EOS suppression.
            # min_new_tokens 는 "토큰 개수" 만 보장하므로, 모델이 Pos/Pitch/Vel/
            # Dur 를 한 자리에 도배해서 토큰 쿼터를 채우고도 실제 bar 수가
            # 2~3 에 그치는 경우가 존재했음 ("초반 몇 마디에만 뭉침"). Bar_N
            # 토큰 방출 횟수를 FSM 으로 추적해 목표 bar 수 이하면 EOS 금지.
            if min_bars > 0 and grammar is not None:
                # current_bar 는 방출된 최고 Bar 인덱스 (0-based). 예를 들어
                # Bar_7 까지 나왔다면 8 bar 생성됐다는 뜻. batch 0 기준.
                cur_bar = grammar.current_bar(batch=0)
                if cur_bar < (min_bars - 1):
                    logits[:, eos_id] = float("-inf")

            # ----- Always suppress PAD token during generation -----
            # PAD (id=0) is a training artifact (sequence padding). The model
            # should never emit it during inference. Without this, the model
            # can fill min_new_tokens quota with PAD tokens that decode to
            # nothing, producing nearly-empty MIDI output.
            logits[:, self.vocab.pad_id] = float("-inf")

            # Apply temperature
            logits = logits / temperature

            # ----- Harmonic constraint (per batch element) -----
            for b in range(logits.size(0)):
                context = idx[b].tolist()
                logits[b] = self._apply_harmonic_mask(logits[b], context)

            # ----- Grammar FSM (Pitch→Vel→Dur, Bar mono, pitch dedup) -----
            # Inspired by ACE-Step constrained_logits_processor (Apache 2.0).
            # Hard-mask structural violations before top-k/top-p so that
            # sampling cannot produce "incomplete note" sequences that the
            # decoder would silently drop (6차 리포트 무음 갭 근본 차단).
            if grammar is not None:
                for b in range(logits.size(0)):
                    logits[b] = grammar.apply(logits[b], batch=b)

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

            # ----- Grammar FSM state update -----
            # Must run AFTER sampling so the FSM sees what was actually
            # emitted (transitions Pitch→EXPECT_VEL→EXPECT_DUR→ANY).
            if grammar is not None:
                for b in range(logits.size(0)):
                    grammar.observe(next_token[b, 0].item(), batch=b)

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
        grammar: Optional[MidiGrammarFSM] = None,
        repetition_penalty: float = 1.0,
        no_repeat_ngram_size: int = 0,
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
            grammar: Optional ``MidiGrammarFSM`` already warmed with the
                prompt. If provided, the same grammar is cloned per beam so
                each beam carries independent Bar/Pos/Track/Pitch state.
                This closes the prior gap where the sampling path used the
                FSM (bar monotonicity, pitch dedup) but the beam path did
                not — a rules/05 패턴 C violation.
            repetition_penalty: CTRL-style penalty applied per beam before
                topk (1.0 = disabled).
            no_repeat_ngram_size: HuggingFace-style n-gram blocking per
                beam (0 = disabled).

        Returns:
            List of ``(token_ids, score)`` tuples sorted by descending score.
        """
        assert self.model is not None
        self.model.eval()

        eos_id = self.vocab.eos_id
        prompt_len = input_ids.size(1)

        # Each beam: (token_id_list, cumulative_log_prob, grammar_or_none).
        # Grammar state is per-beam because beams diverge — sharing one FSM
        # instance across beams would corrupt Bar/Pos/Pitch dedup state.
        root_grammar = copy.deepcopy(grammar) if grammar is not None else None
        active_beams: list[tuple[list[int], float, Optional[MidiGrammarFSM]]] = [
            (input_ids[0].tolist(), 0.0, root_grammar),
        ]
        finished_beams: list[tuple[list[int], float]] = []

        for step in range(max_tokens):
            all_candidates: list[
                tuple[list[int], float, Optional[MidiGrammarFSM]]
            ] = []

            for seq, cum_log_prob, beam_grammar in active_beams:
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

                # Grammar FSM (Bar monotonicity, pitch dedup, Pitch→Vel→Dur)
                if beam_grammar is not None:
                    logits[0] = beam_grammar.apply(logits[0], batch=0)

                # Repetition guards — same policy as sampling path so the
                # bar-loop symptom (Type 2) cannot silently re-emerge when
                # a caller flips use_beam_search=True.
                if repetition_penalty != 1.0 or no_repeat_ngram_size > 0:
                    seq_ctx = seq_tensor if seq_tensor.size(1) <= block_size \
                        else seq_tensor[:, -block_size:]
                    if repetition_penalty != 1.0:
                        logits = self._apply_repetition_penalty(
                            logits, seq_ctx, repetition_penalty,
                        )
                    if no_repeat_ngram_size > 0:
                        logits = self._block_repeat_ngrams(
                            logits, seq_ctx, no_repeat_ngram_size,
                        )

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
                        # Clone the parent beam's grammar and observe the
                        # new token so the child beam enters the next step
                        # with correctly advanced state.
                        child_grammar = (
                            copy.deepcopy(beam_grammar)
                            if beam_grammar is not None else None
                        )
                        if child_grammar is not None:
                            child_grammar.observe(token_id, batch=0)
                        all_candidates.append((new_seq, new_cum, child_grammar))

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
        for seq, cum_log_prob, _g in active_beams:
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

    @torch.no_grad()
    def score_loglik(self, token_ids: list[int]) -> float:
        """Mean log-likelihood of ``token_ids`` under the current model.

        Inspired by ACE-Step v1.5 ``lm_score.py`` (Apache 2.0). Used as
        a self-consistency signal for Best-of-N reranking — a sequence
        the model itself finds "plausible" tends to beat a low-probability
        outlier even when heuristic scores agree.

        The value is the mean per-token log-prob over positions 1..N-1
        (position 0 has no context). Higher = more plausible. Range is
        unbounded negative; typical music sequences fall in roughly
        [-4.0, -0.5] depending on model temperature.

        Returns ``-inf`` if the sequence is too short (< 2 tokens).
        """
        if self.model is None or len(token_ids) < 2:
            return float("-inf")
        self.model.eval()

        block = self.model.config.block_size
        seq = token_ids[-block:]  # clip to model window
        ids = torch.tensor([seq], dtype=torch.long, device=self.device)
        # Next-token loss with pad ignored gives mean negative log-likelihood
        # over non-pad positions, exactly what we want (but negated).
        input_ids = ids[:, :-1]
        targets = ids[:, 1:]
        _, loss, _ = self.model(input_ids, targets=targets)
        if loss is None:
            return float("-inf")
        # model loss = mean NLL; loglik = -NLL
        return float(-loss.item())

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
        min_bars: int = 8,                 # 8차 — bar-count 기반 EOS 바닥.
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
        use_grammar: bool = True,
        grammar_forward_bar_jump: int = 1,
        grammar_dedup_pitches: bool = True,
        rank_by_loglik: bool = False,
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

        # When a LoRA adapter is active (SFT-trained), the model has learned
        # the ``input <SEP> output`` format.  For a bare pre-trained model
        # the SEP token was never seen during training, so we simply let it
        # continue the sequence (autoregressive continuation).
        if self._active_lora is not None:
            input_ids.append(self.vocab.sep_id)
        sep_pos = len(input_ids)

        start_time = time.time()
        variations: list[list[dict]] = []

        if use_beam_search:
            # --- Beam search path ---
            # Construct the FSM once and warm it with the prompt; beam_search
            # clones it per beam so state does not leak between beams.
            beam_grammar: Optional[MidiGrammarFSM] = None
            if use_grammar:
                beam_grammar = MidiGrammarFSM(
                    vocab=self.vocab,
                    allow_forward_bar_jump=grammar_forward_bar_jump,
                    dedup_pitches=grammar_dedup_pitches,
                )
                for tid in input_ids:
                    beam_grammar.observe(tid, batch=0)

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
                grammar=beam_grammar,
                repetition_penalty=repetition_penalty,
                no_repeat_ngram_size=no_repeat_ngram_size,
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
                # Fresh grammar per sample (ACE-1): state resets between
                # candidates so dedup / bar-monotonicity don't leak across runs.
                grammar = None
                if use_grammar:
                    grammar = MidiGrammarFSM(
                        vocab=self.vocab,
                        allow_forward_bar_jump=grammar_forward_bar_jump,
                        dedup_pitches=grammar_dedup_pitches,
                    )
                    # Warm up with the prompt so Bar/Pos/Track context
                    # carries over into the generated region.
                    for tid in input_ids:
                        grammar.observe(tid, batch=0)
                with torch.no_grad():
                    output = self._generate_with_harmony(
                        input_tensor,
                        max_new_tokens=max_tokens,
                        min_new_tokens=min_new_tokens,
                        min_bars=min_bars,
                        temperature=temperature,
                        top_k=top_k,
                        top_p=top_p,
                        eos_id=self.vocab.eos_id,
                        repetition_penalty=repetition_penalty,
                        no_repeat_ngram_size=no_repeat_ngram_size,
                        use_kv_cache=use_kv_cache,
                        grammar=grammar,
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
        if (score_and_rank or rank_by_loglik) and len(variations) > 1:
            scored: list[tuple[list[dict], float]] = []
            for var_notes in variations:
                # Re-encode notes to token IDs for scoring
                var_token_ids = self.encoder.encode_notes(var_notes, meta=meta, chords=chords)
                if rank_by_loglik:
                    # ACE-2: LM self-loglik — the model's own confidence.
                    # Complements heuristic scores; use this when diversity
                    # was high (temperature > 1.0) and heuristic metrics
                    # cluster too tightly to discriminate.
                    score = self.score_loglik(var_token_ids)
                else:
                    score = self.score_sequence(var_token_ids)["total"]
                scored.append((var_notes, score))
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
        min_bars: int = 8,                 # 8차 — bar-count 기반 EOS 바닥.
        temperature: float = 0.9,
        top_k: int = 50,
        top_p: float = 0.95,
        repetition_penalty: float = 1.0,
        no_repeat_ngram_size: int = 0,
        use_kv_cache: bool = True,
        use_grammar: bool = True,
        grammar_forward_bar_jump: int = 1,
        grammar_dedup_pitches: bool = True,
        grammar_min_notes_per_bar: int = 1,  # S3 — FSM refuses Bar_* transition until current bar has this many pitches
        task: str = "variation",           # UUU — variation|continuation|bar_infill|track_completion
        start_bar: int = 0,                 # UUU — target bar range start (inclusive)
        end_bar: int = 0,                   # UUU — target bar range end (exclusive). 0 = unused
        target_track: str = "",             # UUU — category name ("drums", "bass", …)
        regenerate_on_empty_bars: int = 4,  # VVV — retry budget if reviewer flags sparse output (10차 테스트 empty_ratio 0.875 대응, 2→4)
        context: "SongContext | None" = None,  # WWW — elevated generation condition
    ) -> str:
        """Generate variation and save as MIDI file.

        See :meth:`generate_variation` for parameter documentation.

        Grammar (Sprint 41 EEE1): mirrors ``generate_variation`` — FSM 을 생성
        하고 프롬프트로 워밍 후 ``_generate_with_harmony`` 에 전달.  이전에는
        이 경로에서 FSM 이 누락되어 중복 노트가 디코드되고 있었다(패턴 C).
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        # Sprint WWW — SongContext overrides. When a SongContext is
        # supplied, its explicit fields win over the loose keyword args
        # so callers can pass either the old (flat kwargs) or new
        # (SongContext object) shape. Loose kwargs still work as defaults.
        if context is not None:
            if context.target_task:        task = context.target_task
            if context.target_track:       target_track = context.target_track
            if context.end_bar > context.start_bar:
                start_bar = context.start_bar
                end_bar   = context.end_bar
            # Density → min_bars heuristic: denser requests tolerate the
            # same range, sparse ones might need a longer window, but the
            # engine can't *extend* a user range, so leave it.

        # Sprint UUU — range ↔ min_bars coupling. If caller asks for an
        # explicit end_bar, tighten min_bars so the model keeps generating
        # until it actually covers the range. Absent range → caller's
        # min_bars stays as-is.
        if end_bar > start_bar:
            min_bars = max(min_bars, end_bar - start_bar)

        # Sprint UUU — diagnostic log per request so partner's §5-4 "빈
        # 마디" debugging has the task/range/target that produced it.
        try:
            print(f"[engine] task={task} start_bar={start_bar} "
                  f"end_bar={end_bar} target_track={target_track or '-'} "
                  f"min_bars={min_bars} active_lora={self._active_lora}",
                  flush=True)
        except Exception:
            pass

        input_ids = self.encoder.encode_file(midi_path, meta=meta, chords=chords)
        if input_ids and input_ids[-1] == self.vocab.eos_id:
            input_ids = input_ids[:-1]

        # Only add SEP when SFT-trained LoRA is active (see generate_variation)
        if self._active_lora is not None:
            input_ids.append(self.vocab.sep_id)

        # Sprint UUU — target track identity seed. If the caller names a
        # TRACK_TYPES category, append Track_<cat> right after SEP so the
        # decoder's "default accomp fallback" (partner §7-3 / §20-3) doesn't
        # absorb tokens that should carry the target track's identity.
        if target_track:
            track_tok = f"Track_{target_track}"
            tid = self.vocab.encode_token(track_tok)
            if tid != self.vocab.unk_id:
                input_ids.append(tid)

        input_tensor = torch.tensor([input_ids], dtype=torch.long, device=self.device)
        tempo = meta.tempo if meta else 120.0

        # Sprint VVV — empty-bar reviewer loop (종합리뷰 §20-4).
        # Generate → decode → reviewer.check_bar_density. If the bar
        # coverage in the target range is unacceptable, regenerate with
        # a bumped temperature (small nudge, not full randomness) up to
        # `regenerate_on_empty_bars` times.
        try:
            from agents.reviewer import check_bar_density  # lazy import
        except Exception:
            check_bar_density = None  # reviewer optional; fall through

        attempt = 0
        current_temp = temperature
        while True:
            # Fresh grammar per call; warm with the prompt so Bar/Pos/Track
            # state carries into generation.
            grammar: Optional[MidiGrammarFSM] = None
            if use_grammar:
                grammar = MidiGrammarFSM(
                    vocab=self.vocab,
                    allow_forward_bar_jump=grammar_forward_bar_jump,
                    dedup_pitches=grammar_dedup_pitches,
                    min_notes_per_bar=grammar_min_notes_per_bar,
                )
                for tid in input_ids:
                    grammar.observe(tid, batch=0)

            with torch.no_grad():
                output = self._generate_with_harmony(
                    input_tensor,
                    max_new_tokens=max_tokens,
                    min_new_tokens=min_new_tokens,
                    min_bars=min_bars,
                    temperature=current_temp,
                    top_k=top_k,
                    top_p=top_p,
                    eos_id=self.vocab.eos_id,
                    repetition_penalty=repetition_penalty,
                    no_repeat_ngram_size=no_repeat_ngram_size,
                    use_kv_cache=use_kv_cache,
                    grammar=grammar,
                )

            variation_ids = output[0].tolist()[len(input_ids):]

            # Reviewer gate — skip if disabled or reviewer unavailable.
            if (check_bar_density is None
                    or regenerate_on_empty_bars <= 0
                    or attempt >= regenerate_on_empty_bars):
                break

            # Decode to (pitch, start_beat) pairs in-memory for the gate.
            notes = self.decoder.decode_to_notes(
                variation_ids, initial_track=target_track or None)
            # DecodedNote.start_tick is in ticks; normalize to beats
            # assuming standard 480-tick division (matches _write_midi).
            TPQ = 480
            notes_with_beat = [(n.pitch, n.start_tick / TPQ) for n in notes]

            target_bars = (end_bar - start_bar) if end_bar > start_bar else None
            gate = check_bar_density(
                notes_with_beat,
                start_bar=start_bar if end_bar > start_bar else 0,
                end_bar=end_bar if end_bar > start_bar else None,
                min_notes_per_bar=1,
            )
            try:
                print(f"[engine] VVV gate attempt={attempt} "
                      f"empty={gate.get('empty_bars')} "
                      f"longest_empty_run={gate.get('longest_empty_run')} "
                      f"pass={gate.get('pass')}", flush=True)
            except Exception:
                pass

            if gate.get("pass"):
                break

            attempt += 1
            # Temperature nudge so the retry doesn't clone the bad pass.
            # 10차 테스트(2026-04-21)에서 +0.07 × 2회로는 동일 분포 샘플링에
            # 머물러 empty_ratio 0.875 가 유지됨 → +0.12 로 상향.
            current_temp = min(1.5, current_temp + 0.12)

        # VVV — pass target_track as the decoder's initial-track hint so
        # un-prefixed notes in the output don't collapse to accomp.
        self.decoder.decode_to_midi(
            variation_ids, output_path, tempo=tempo,
            initial_track=target_track or None,
        )
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
