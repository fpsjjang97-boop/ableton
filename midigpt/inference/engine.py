"""
MidiGPT Inference Engine — Runtime for the MIDI AI Workstation app.

Features:
  - Auto device detection (CUDA GPU / CPU)
  - PyTorch or ONNX Runtime backend
  - LoRA hot-swap at runtime
  - Quantized model support (FP16/INT8)
  - Harmonic constraint: masks off-scale pitches during generation
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
        temperature: float = 0.9,
        top_k: int = 50,
        top_p: float = 0.95,
        eos_id: int = 2,
    ) -> torch.Tensor:
        """Autoregressive generation with harmonic constraint.

        Mirrors model.generate() but applies a scale-aware mask on pitch tokens
        before sampling, preventing notes outside the current chord's scale.
        """
        assert self.model is not None
        self.model.eval()
        block_size = self.model.config.block_size

        for _ in range(max_new_tokens):
            # Crop to block_size
            idx_cond = idx if idx.size(1) <= block_size else idx[:, -block_size:]

            # Forward pass
            logits, _, _ = self.model(idx_cond)
            logits = logits[:, -1, :] / temperature  # (B, V)

            # --- Harmonic constraint (per batch element) ---
            for b in range(logits.size(0)):
                context = idx[b].tolist()
                logits[b] = self._apply_harmonic_mask(logits[b], context)

            # Top-K filtering
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float("-inf")

            # Top-P (nucleus) filtering
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

            # Sample
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Append
            idx = torch.cat([idx, next_token], dim=1)

            # Stop on EOS
            if (next_token == eos_id).all():
                break

        return idx

    # ------------------------------------------------------------------
    # Generation API
    # ------------------------------------------------------------------
    def generate_variation(
        self,
        midi_path: str | None = None,
        notes: list[dict] | None = None,
        meta: SongMeta | None = None,
        chords: list[ChordEvent] | None = None,
        max_tokens: int = 512,
        temperature: float = 0.9,
        top_k: int = 50,
        top_p: float = 0.95,
    ) -> list[dict]:
        """Generate a MIDI variation.

        Args:
            midi_path: Input MIDI file path (alternative to notes)
            notes: Input note list [{pitch, velocity, start_tick, duration_tick, track_type}]
            meta: Song metadata (key, style, section, tempo)
            chords: Chord analysis results
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k: Top-K sampling
            top_p: Nucleus sampling

        Returns:
            List of note dicts [{pitch, velocity, start_tick, duration_tick, track_type}]
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

        # Generate with harmonic constraint
        start_time = time.time()
        input_tensor = torch.tensor([input_ids], dtype=torch.long, device=self.device)

        with torch.no_grad():
            output = self._generate_with_harmony(
                input_tensor,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                eos_id=self.vocab.eos_id,
            )

        elapsed = time.time() - start_time

        # Extract generated tokens (after SEP)
        generated_ids = output[0].tolist()
        sep_pos = len(input_ids)
        variation_ids = generated_ids[sep_pos:]

        # Decode to notes
        decoded_notes = self.decoder.decode_to_notes(variation_ids)

        # Convert to dict format
        result = []
        for note in decoded_notes:
            result.append({
                "pitch": note.pitch,
                "velocity": note.velocity,
                "start_tick": note.start_tick,
                "duration_tick": note.duration_tick,
                "track_type": note.track_type,
            })

        print(f"MidiGPT: Generated {len(result)} notes in {elapsed:.2f}s")
        return result

    def generate_to_midi(
        self,
        midi_path: str,
        output_path: str,
        meta: SongMeta | None = None,
        chords: list[ChordEvent] | None = None,
        max_tokens: int = 512,
        temperature: float = 0.9,
    ) -> str:
        """Generate variation and save as MIDI file."""
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
                temperature=temperature,
                eos_id=self.vocab.eos_id,
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
