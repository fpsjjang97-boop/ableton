"""
Sheet → MIDI Agent (SMT++ integration)
======================================

Converts sheet music images / PDF pages into MIDI by wrapping the
state-of-the-art open-source OMR model **Sheet Music Transformer ++**
(SMT++, antoniorv6/SMT-plusplus, MIT licence).

End-to-end flow:

    image / pdf  ─►  SMT++         ─►  bekern text
                                          │
                                          ▼
                                       music21
                                          │
                                          ▼
                                       MIDI file
                                          │
                                          ▼ (optional)
                                MidiGPTInference.generate_variation
                                          │
                                          ▼
                                   variation MIDI

The agent loads SMT and music21 lazily so the rest of the project
keeps working even when those optional dependencies are missing.

Installation
------------
SMT++ is *not* on PyPI as a regular package; you must install it from
source.  music21 is a normal pip package.

    # 1. PyTorch (GPU build) — see REMOTE_TRAINING_GUIDE.md
    pip install torch --index-url https://download.pytorch.org/whl/cu121

    # 2. SMT++ from source
    git clone https://github.com/antoniorv6/SMT-plusplus.git
    cd SMT-plusplus
    pip install -e .

    # 3. kern → MIDI converter
    pip install music21

    # 4. Image I/O
    pip install opencv-python

The default checkpoint is ``antoniorv6/smt-camera-grandstaff`` (21.4M
params, MIT licence, piano-only).  Pass ``model_name=`` to override.

CLI
---
    python -m agents.sheet2midi \
        --image score.png \
        --output ./output/score.mid

    python -m agents.sheet2midi \
        --image score.png \
        --output ./output/score_var.mid \
        --vary \
        --base_model ./checkpoints/midigpt_ema.pt
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class TranscriptionResult:
    """Result of one OMR pass."""
    image_path: str
    bekern_raw: str          # exactly what SMT produced (with <b>/<s>/<t>)
    kern_text: str           # human-readable kern (line breaks/tabs restored)
    inference_sec: float


# ---------------------------------------------------------------------------
# Sheet → MIDI agent
# ---------------------------------------------------------------------------
class Sheet2MidiAgent:
    """Wraps SMT++ + music21 to turn a sheet image into a playable MIDI."""

    DEFAULT_MODEL = "antoniorv6/smt-camera-grandstaff"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str = "auto",
    ):
        self.model_name = model_name
        self._device_pref = device

        # Lazy state
        self._smt_model = None
        self._convert_img_to_tensor = None
        self._cv2 = None
        self._torch = None
        self._music21 = None
        self._device: Optional[str] = None

    # ------------------------------------------------------------------
    # Lazy import helpers — keep the rest of the project usable even
    # when SMT / music21 / opencv are not installed.
    # ------------------------------------------------------------------
    def _load_smt(self) -> None:
        if self._smt_model is not None:
            return

        try:
            import torch
            import cv2
        except ImportError as e:
            raise RuntimeError(
                "Sheet2MidiAgent needs torch + opencv-python. "
                "Install with: pip install torch opencv-python"
            ) from e

        try:
            from data_augmentation.data_augmentation import convert_img_to_tensor
            from smt_model import SMTModelForCausalLM
        except ImportError as e:
            raise RuntimeError(
                "SMT++ is not installed.  Install from source:\n"
                "    git clone https://github.com/antoniorv6/SMT-plusplus.git\n"
                "    cd SMT-plusplus && pip install -e .\n"
                "(SMT is not on PyPI as a regular package.)"
            ) from e

        # Device resolution
        if self._device_pref == "auto":
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device = self._device_pref
        print(f"[sheet2midi] loading SMT '{self.model_name}' on {self._device}")

        t0 = time.time()
        model = SMTModelForCausalLM.from_pretrained(self.model_name).to(self._device)
        model.eval()
        print(f"[sheet2midi] SMT ready in {time.time() - t0:.1f}s")

        self._torch = torch
        self._cv2 = cv2
        self._convert_img_to_tensor = convert_img_to_tensor
        self._smt_model = model

    def _load_music21(self) -> None:
        if self._music21 is not None:
            return
        try:
            import music21
        except ImportError as e:
            raise RuntimeError(
                "music21 is not installed.  Install with:\n"
                "    pip install music21\n"
                "It is needed to convert SMT's kern output to MIDI."
            ) from e
        self._music21 = music21

    # ------------------------------------------------------------------
    # 1. Image → kern text  (the actual OMR step)
    # ------------------------------------------------------------------
    def transcribe(self, image_path: str | Path) -> TranscriptionResult:
        """Run SMT++ on a single image and return the kern transcription."""
        self._load_smt()

        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(image_path)

        image = self._cv2.imread(str(path))
        if image is None:
            raise ValueError(f"cv2 failed to read {path}")

        tensor = self._convert_img_to_tensor(image).unsqueeze(0).to(self._device)

        t0 = time.time()
        with self._torch.no_grad():
            predictions, _ = self._smt_model.predict(tensor, convert_to_str=True)
        elapsed = time.time() - t0

        bekern_raw = "".join(predictions)
        kern_text = (
            bekern_raw
            .replace("<b>", "\n")
            .replace("<s>", " ")
            .replace("<t>", "\t")
        )

        return TranscriptionResult(
            image_path=str(path),
            bekern_raw=bekern_raw,
            kern_text=kern_text,
            inference_sec=round(elapsed, 2),
        )

    # ------------------------------------------------------------------
    # 2. kern text → MIDI file (via music21)
    # ------------------------------------------------------------------
    def kern_to_midi(self, kern_text: str, output_path: str | Path) -> str:
        """Parse a kern string with music21 and write a Standard MIDI File."""
        self._load_music21()
        m21 = self._music21

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        try:
            score = m21.converter.parseData(kern_text, format="humdrum")
        except Exception as e:
            raise RuntimeError(
                f"music21 failed to parse SMT output as humdrum/kern.  "
                f"This usually means the OMR result was malformed; try a "
                f"cleaner / higher-resolution scan.  Underlying error: {e}"
            ) from e

        score.write("midi", fp=str(out))
        return str(out)

    # ------------------------------------------------------------------
    # 3. Convenience: image → MIDI in one call
    # ------------------------------------------------------------------
    def transcribe_to_midi(
        self,
        image_path: str | Path,
        output_path: str | Path,
    ) -> tuple[str, TranscriptionResult]:
        """Image → kern → MIDI file.  Returns (midi_path, transcription)."""
        result = self.transcribe(image_path)
        midi_path = self.kern_to_midi(result.kern_text, output_path)
        print(
            f"[sheet2midi] {Path(image_path).name} → {Path(midi_path).name} "
            f"({result.inference_sec}s)"
        )
        return midi_path, result

    # ------------------------------------------------------------------
    # 4. Image → MIDI → MidiGPT variation (full creative pipeline)
    # ------------------------------------------------------------------
    def transcribe_and_vary(
        self,
        image_path: str | Path,
        midi_output_path: str | Path,
        variation_output_path: str | Path,
        midigpt_base_model: str,
        meta_key: str = "C",
        meta_style: str = "pop",
        meta_section: str = "verse",
        meta_tempo: float = 120.0,
        max_tokens: int = 512,
        temperature: float = 0.9,
        repetition_penalty: float = 1.1,
        no_repeat_ngram_size: int = 4,
    ) -> dict:
        """Full pipeline: image → MIDI → MidiGPT variation MIDI.

        Returns a dict with both intermediate and final paths plus the
        original SMT transcription.
        """
        # Step 1+2: image → MIDI
        midi_path, transcription = self.transcribe_to_midi(
            image_path, midi_output_path
        )

        # Step 3: MidiGPT variation (lazy import so this file works without
        # the model checkpoint being present).
        from midigpt.inference.engine import InferenceConfig, MidiGPTInference
        from midigpt.tokenizer.encoder import SongMeta

        inf = MidiGPTInference(InferenceConfig(model_path=midigpt_base_model))
        if not inf.is_loaded:
            raise RuntimeError(
                f"MidiGPT base model failed to load: {midigpt_base_model}"
            )

        var_path = inf.generate_to_midi(
            midi_path=midi_path,
            output_path=str(variation_output_path),
            meta=SongMeta(
                key=meta_key,
                style=meta_style,
                section=meta_section,
                tempo=meta_tempo,
            ),
            max_tokens=max_tokens,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
            no_repeat_ngram_size=no_repeat_ngram_size,
            use_kv_cache=True,
        )

        return {
            "image": str(image_path),
            "midi": midi_path,
            "variation": var_path,
            "transcription": transcription,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sheet music image → MIDI (via SMT++), with optional MidiGPT variation."
    )
    parser.add_argument("--image", required=True, help="Path to sheet music image (PNG/JPG).")
    parser.add_argument("--output", required=True, help="Output MIDI file path.")
    parser.add_argument(
        "--model",
        default=Sheet2MidiAgent.DEFAULT_MODEL,
        help="HuggingFace SMT model id (default: smt-camera-grandstaff, piano-only).",
    )
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])

    # Optional MidiGPT variation
    parser.add_argument(
        "--vary",
        action="store_true",
        help="After OMR, also generate a MidiGPT variation of the transcribed MIDI.",
    )
    parser.add_argument("--base_model", default="./checkpoints/midigpt_ema.pt")
    parser.add_argument("--variation_output", default=None,
                        help="Where to save the variation MIDI (default: <output>_var.mid)")
    parser.add_argument("--key", default="C")
    parser.add_argument("--style", default="pop")
    parser.add_argument("--section", default="verse")
    parser.add_argument("--tempo", type=float, default=120.0)
    parser.add_argument("--max_tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.9)
    parser.add_argument("--repetition_penalty", type=float, default=1.1)
    parser.add_argument("--no_repeat_ngram_size", type=int, default=4)

    args = parser.parse_args()

    agent = Sheet2MidiAgent(model_name=args.model, device=args.device)

    if not args.vary:
        agent.transcribe_to_midi(args.image, args.output)
        return 0

    var_out = args.variation_output or str(
        Path(args.output).with_name(Path(args.output).stem + "_var.mid")
    )
    result = agent.transcribe_and_vary(
        image_path=args.image,
        midi_output_path=args.output,
        variation_output_path=var_out,
        midigpt_base_model=args.base_model,
        meta_key=args.key,
        meta_style=args.style,
        meta_section=args.section,
        meta_tempo=args.tempo,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        repetition_penalty=args.repetition_penalty,
        no_repeat_ngram_size=args.no_repeat_ngram_size,
    )
    print()
    print("=== sheet2midi pipeline complete ===")
    print(f"  image     : {result['image']}")
    print(f"  midi      : {result['midi']}")
    print(f"  variation : {result['variation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
