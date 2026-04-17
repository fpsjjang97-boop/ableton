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


@app.get("/preflight")
def preflight():
    """Detailed capability check. The VST plugin calls this once before
    offering Audio2MIDI so it can show a specific "missing X" message
    rather than a generic 503 when the user drops an audio file.

    Keys:
      model_loaded          — MidiGPT weights loaded (generation path)
      audio2midi_available  — convert.py imports succeeded
      onsets_frames         — Google Magenta O&F piano transcription available
      adtof                 — ADTOF drum transcription available
      missing               — list of pip packages that would fix audio2midi_available
    """
    info = {
        "model_loaded": _inference is not None and _inference.is_loaded,
        "audio2midi_available": False,
        "onsets_frames": False,
        "adtof": False,
        "missing": [],
    }
    try:
        sys.path.insert(0, str(REPO_ROOT / "tools" / "audio_to_midi"))
        import convert as a2m_convert  # type: ignore
        info["audio2midi_available"] = not bool(a2m_convert.MISSING)
        info["missing"] = list(a2m_convert.MISSING)
        info["onsets_frames"] = getattr(a2m_convert, "_OAF_AVAILABLE", False)
        info["adtof"] = getattr(a2m_convert, "_ADTOF_AVAILABLE", False)
    except ImportError as e:
        info["missing"] = ["convert.py import failed: " + str(e)]
    return info


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
# Sprint 35 ZZ1 — Audio → MIDI endpoint
# ---------------------------------------------------------------------------
class AudioToMidiRequest(BaseModel):
    """Base64 audio blob + format hint. Result is base64 Type-1 MIDI.

    The file extension is needed because some decoders (pydub/librosa) peek
    at the suffix; we re-use it when writing a temp file.
    """
    audio_base64: str
    filename: str = "input.wav"     # hint for format sniffing (.mp3, .wav, .flac, ...)
    keep_vocals: bool = False
    rerank_with_midigpt: bool = True   # ZZ1d — enable score_loglik reranking


@app.post("/audio_to_midi")
def audio_to_midi(req: AudioToMidiRequest):
    """Convert an uploaded audio clip to a Type-1 MIDI using the
    tools/audio_to_midi/convert.py pipeline (Demucs + Basic Pitch + librosa).

    ⚠ Beta. Accuracy varies 50-85% depending on source material — see
    docs/business/10_audio2midi_roadmap.md for the improvement plan.

    Current pipeline:
      1. Source separation: Demucs htdemucs_6s → vocals/drums/bass/guitar/piano/other
      2. Per-stem transcription: Basic Pitch (melodic) + librosa onset (drums)
      3. Optional: MidiGPT score_loglik reranking (ZZ1d)

    Future (Tier 1, Sprint 36+):
      - Onsets & Frames for piano stem (+20% F1)
      - ADTOF for drums (+15% F1)
      - pYIN for bass (+10% F1)
    """
    # convert.py is a heavy import (demucs, basic_pitch, librosa) — only
    # pulled in on first call to keep the server startup light when users
    # don't need this feature.
    try:
        sys.path.insert(0, str(REPO_ROOT / "tools" / "audio_to_midi"))
        import convert as a2m_convert  # type: ignore
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Audio2MIDI 모듈 import 실패: {e}. "
                f"`python scripts/doctor.py` 로 의존성 상태 확인 + "
                f"`scripts/setup_audio2midi.bat` (Windows) / .sh (Linux) 로 자동 설치 가능."
            ),
        )
    if a2m_convert.MISSING:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Audio2MIDI 의존성 누락: {', '.join(a2m_convert.MISSING)}. "
                f"`pip install {' '.join(a2m_convert.MISSING)}` 또는 "
                f"scripts/setup_audio2midi.bat 실행."
            ),
        )

    import tempfile as _tmpmod
    suffix = Path(req.filename).suffix or ".wav"
    tmp_audio = Path(_tmpmod.mktemp(suffix=suffix, dir=str(REPO_ROOT)))
    tmp_out_dir = Path(_tmpmod.mkdtemp(prefix="a2m_", dir=str(REPO_ROOT)))

    try:
        try:
            audio_bytes = _b64.b64decode(req.audio_base64)
        except Exception as e:
            raise HTTPException(status_code=400,
                                detail=f"Invalid base64 audio: {e}")
        tmp_audio.write_bytes(audio_bytes)

        # Run the pipeline end-to-end (separation + transcription + merge).
        result_midi_path = a2m_convert.convert_single(
            audio_path=tmp_audio,
            output_dir=tmp_out_dir,
            keep_vocals=req.keep_vocals,
            no_merge=False,
        )
        if result_midi_path is None or not Path(result_midi_path).exists():
            raise HTTPException(status_code=500,
                                detail="Audio2MIDI 파이프라인이 MIDI 를 생성하지 못했습니다.")

        midi_bytes = Path(result_midi_path).read_bytes()

        # ZZ1d — optional reranking. Tokenise the result and score it; in
        # the current single-path implementation this is diagnostic rather
        # than a pick-from-K. When the pipeline grows to produce multiple
        # candidates (Sprint 36), this becomes the selection mechanism.
        loglik = None
        if req.rerank_with_midigpt and _inference is not None and _inference.is_loaded:
            try:
                tok_ids = _inference.encoder.encode_file(str(result_midi_path))
                loglik = _inference.score_loglik(tok_ids)
            except Exception as e:
                # Non-fatal: return the MIDI anyway, just without the score.
                print(f"[WARN] score_loglik 실패 (생성 결과는 유지): {e}")

        return {
            "ok": True,
            "midi_base64": _b64.b64encode(midi_bytes).decode("ascii"),
            "bytes": len(midi_bytes),
            "loglik": loglik,            # None when scoring skipped/failed
            "beta_warning": (
                "⚠ Audio2MIDI 는 베타 기능입니다. 정확도는 곡 복잡도에 따라 "
                "50-85% 범위이며 수동 편집이 필요합니다."
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio2MIDI 실패: {e}")
    finally:
        for p in (tmp_audio,):
            try:
                if p.exists(): p.unlink()
            except Exception:
                pass
        try:
            import shutil as _sh
            _sh.rmtree(tmp_out_dir, ignore_errors=True)
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
