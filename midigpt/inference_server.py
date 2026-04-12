"""
MidiGPT — Local HTTP Inference Server
=====================================

FastAPI wrapper around ``MidiGPTInference`` so the JUCE VST3 plugin can
request variations via HTTP without re-loading the 50M model for every call.

Usage:
    python -m midigpt.inference_server \
        --model ./checkpoints/midigpt_ema.pt \
        --port 8765

Endpoints:
    GET  /health          → {"status": "ok", "model_loaded": bool}
    POST /generate        → generate variation from uploaded MIDI bytes
    POST /load_lora       → hot-swap LoRA adapter by name
    GET  /status          → current model status + active LoRA

Plugin integration (juce_daw_clean):
    - Plugin captures incoming MIDI → POSTs bytes to /generate
    - Server decodes bytes, runs MidiGPTInference, returns generated MIDI bytes
    - Plugin parses response and schedules MIDI output

This file is clean-room: no Cubase dependencies, no Ghidra artefacts.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from typing import Optional

# --- Repo root so midigpt package imports work when run directly ------------
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from fastapi import FastAPI, File, UploadFile, HTTPException
    from fastapi.responses import Response
    from pydantic import BaseModel
    import uvicorn
except ImportError as e:
    print(f"ERROR: FastAPI/uvicorn not installed. Run: pip install fastapi uvicorn")
    print(f"       ({e})")
    sys.exit(1)

try:
    import pretty_midi
except ImportError:
    print("ERROR: pretty_midi required. Run: pip install pretty_midi")
    sys.exit(1)

from midigpt.inference.engine import MidiGPTInference, InferenceConfig
from midigpt.tokenizer.encoder import SongMeta


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------
class GenerateParams(BaseModel):
    style: str = "base"
    key: str = "C"
    section: str = "chorus"
    tempo: float = 120.0
    temperature: float = 0.9
    num_variations: int = 1
    max_tokens: int = 1024
    min_new_tokens: int = 256
    repetition_penalty: float = 1.1
    no_repeat_ngram_size: int = 4


class LoadLoraRequest(BaseModel):
    name: str
    path: Optional[str] = None


# ---------------------------------------------------------------------------
# App + state
# ---------------------------------------------------------------------------
app = FastAPI(title="MidiGPT Inference Server", version="0.1.0")

_inference: Optional[MidiGPTInference] = None


def _ensure_loaded():
    if _inference is None or not _inference.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded yet")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": _inference is not None and _inference.is_loaded,
    }


@app.get("/status")
def status():
    if _inference is None:
        return {"loaded": False}
    return _inference.get_status()


@app.post("/load_lora")
def load_lora(req: LoadLoraRequest):
    _ensure_loaded()
    try:
        _inference.load_lora(req.name, req.path)
        return {"ok": True, "active_lora": _inference.active_lora}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate")
async def generate(
    midi: UploadFile = File(...),
    style: str = "base",
    key: str = "C",
    section: str = "chorus",
    tempo: float = 120.0,
    temperature: float = 0.9,
    num_variations: int = 1,
    max_tokens: int = 1024,
    min_new_tokens: int = 256,
    repetition_penalty: float = 1.1,
    no_repeat_ngram_size: int = 4,
):
    """Generate MIDI variation(s) from an uploaded MIDI file.

    Returns a multipart response (if num_variations>1) or a single MIDI body.
    For the initial skeleton, we return the first variation only as a
    single-file MIDI response.
    """
    _ensure_loaded()

    # --- Save uploaded MIDI to a unique temporary file (thread-safe) -------
    import tempfile as _tmpmod
    tmp_in = Path(_tmpmod.mktemp(suffix="_in.mid", dir=str(REPO_ROOT)))
    tmp_out = Path(_tmpmod.mktemp(suffix="_out.mid", dir=str(REPO_ROOT)))
    try:
        data = await midi.read()
        tmp_in.write_bytes(data)

        # --- Build SongMeta --------------------------------------------------
        meta = SongMeta(key=key, style=style, section=section, tempo=tempo)

        # --- Run inference ---------------------------------------------------
        _inference.generate_to_midi(
            midi_path=str(tmp_in),
            output_path=str(tmp_out),
            meta=meta,
            max_tokens=max_tokens,
            min_new_tokens=min_new_tokens,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
            no_repeat_ngram_size=no_repeat_ngram_size,
            use_kv_cache=True,
        )

        midi_bytes = tmp_out.read_bytes()
        return Response(content=midi_bytes, media_type="audio/midi")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")
    finally:
        # Cleanup temp files
        for f in (tmp_in, tmp_out):
            try:
                if f.exists():
                    f.unlink()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# JSON-only generate endpoint (for the JUCE C++ plugin)
# ---------------------------------------------------------------------------
# The C++ plugin uses this instead of /generate because constructing
# multipart/form-data from JUCE is awkward. Everything arrives as JSON
# with the MIDI bytes base64-encoded, and the response is the same shape
# (base64 MIDI in a JSON object).
# ---------------------------------------------------------------------------
import base64 as _b64


class GenerateJsonRequest(BaseModel):
    midi_base64: str
    style: str = "base"
    key: str = "C"
    section: str = "chorus"
    tempo: float = 120.0
    temperature: float = 0.9
    num_variations: int = 1
    max_tokens: int = 1024
    min_new_tokens: int = 256
    repetition_penalty: float = 1.1
    no_repeat_ngram_size: int = 4


@app.post("/generate_json")
def generate_json(req: GenerateJsonRequest):
    """Clean-room JSON variant of /generate used by the JUCE VST3 plugin.

    Request  : JSON with base64 MIDI bytes + params
    Response : JSON {"midi_base64": "...", "notes": int, "ok": true}
    """
    _ensure_loaded()

    import tempfile as _tmpmod
    tmp_in  = Path(_tmpmod.mktemp(suffix="_in.mid", dir=str(REPO_ROOT)))
    tmp_out = Path(_tmpmod.mktemp(suffix="_out.mid", dir=str(REPO_ROOT)))

    try:
        # Decode base64 MIDI -> write to temp file for pretty_midi
        try:
            midi_bytes = _b64.b64decode(req.midi_base64)
        except Exception as e:
            raise HTTPException(status_code=400,
                                detail=f"Invalid base64 MIDI: {e}")
        tmp_in.write_bytes(midi_bytes)

        meta = SongMeta(key=req.key, style=req.style,
                        section=req.section, tempo=req.tempo)

        _inference.generate_to_midi(
            midi_path=str(tmp_in),
            output_path=str(tmp_out),
            meta=meta,
            max_tokens=req.max_tokens,
            min_new_tokens=req.min_new_tokens,
            temperature=req.temperature,
            repetition_penalty=req.repetition_penalty,
            no_repeat_ngram_size=req.no_repeat_ngram_size,
            use_kv_cache=True,
        )

        out_bytes = tmp_out.read_bytes()
        out_b64 = _b64.b64encode(out_bytes).decode("ascii")

        return {
            "ok": True,
            "midi_base64": out_b64,
            "bytes": len(out_bytes),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")
    finally:
        for f in (tmp_in, tmp_out):
            try:
                if f.exists():
                    f.unlink()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    global _inference

    parser = argparse.ArgumentParser(description="MidiGPT local inference server")
    parser.add_argument("--model", type=str, default="./checkpoints/midigpt_ema.pt",
                        help="Path to base model checkpoint")
    parser.add_argument("--host", type=str, default="127.0.0.1",
                        help="Bind host (default localhost only)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--lora_jazz", type=str, default=None)
    parser.add_argument("--lora_citypop", type=str, default=None)
    parser.add_argument("--lora_metal", type=str, default=None)
    parser.add_argument("--lora_classical", type=str, default=None)
    args = parser.parse_args()

    lora_paths = {}
    if args.lora_jazz:
        lora_paths["jazz"] = args.lora_jazz
    if args.lora_citypop:
        lora_paths["citypop"] = args.lora_citypop
    if args.lora_metal:
        lora_paths["metal"] = args.lora_metal
    if args.lora_classical:
        lora_paths["classical"] = args.lora_classical

    print(f"[MidiGPT Server] Loading model: {args.model}")
    _inference = MidiGPTInference(InferenceConfig(
        model_path=args.model,
        lora_paths=lora_paths if lora_paths else None,
    ))
    print(f"[MidiGPT Server] Loaded. Listening on http://{args.host}:{args.port}")
    print(f"[MidiGPT Server] Endpoints: /health /status /generate /load_lora")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
