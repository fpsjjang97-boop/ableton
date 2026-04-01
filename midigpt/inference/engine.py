"""
MidiGPT Inference Engine — Runtime for the MIDI AI Workstation app.

Features:
  - Auto device detection (CUDA GPU / CPU)
  - PyTorch or ONNX Runtime backend
  - LoRA hot-swap at runtime
  - Quantized model support (FP16/INT8)
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import torch

from ..model import MidiGPTConfig, MidiGPT
from ..tokenizer import MidiVocab, MidiEncoder, MidiDecoder
from ..tokenizer.vocab import VOCAB
from ..tokenizer.encoder import SongMeta, ChordEvent
from ..training.lora import LoRAConfig, apply_lora, load_lora, merge_lora


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

        # Generate
        start_time = time.time()
        input_tensor = torch.tensor([input_ids], dtype=torch.long, device=self.device)

        with torch.no_grad():
            output = self.model.generate(
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
            output = self.model.generate(
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
