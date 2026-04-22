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
import json
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
    # Sprint 41 EEE1 / 42 FFF1: FSM grammar 제어 (기본 True — 중복 노트 억제).
    # 디버깅/비교 목적이 아니면 끄지 말 것.
    use_grammar: bool = True
    grammar_dedup_pitches: bool = True


class LoadLoraRequest(BaseModel):
    name: str
    path: Optional[str] = None


# Sprint 43 GGG3 — 다중 LoRA 핫스왑
class RegisterLoraRequest(BaseModel):
    name: str
    path: Optional[str] = None


class ActivateLoraRequest(BaseModel):
    # None (JSON null) 을 보내면 deactivate (zero LoRA → base forward)
    name: Optional[str] = None


class BlendLorasRequest(BaseModel):
    # {"jazz": 0.7, "classical": 0.3}. 빈 dict 는 deactivate.
    weights: dict[str, float]


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
        "piano_pti": False,        # piano_transcription_inference (Sprint 37.4)
        "onsets_frames": False,    # magenta TF1 path
        "adtof": False,
        "missing": [],
    }
    try:
        sys.path.insert(0, str(REPO_ROOT / "tools" / "audio_to_midi"))
        import convert as a2m_convert  # type: ignore
        info["audio2midi_available"] = not bool(a2m_convert.MISSING)
        info["missing"] = list(a2m_convert.MISSING)
        info["piano_pti"] = getattr(a2m_convert, "_PTI_AVAILABLE", False)
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


# Sprint 43 GGG3 — 다중 LoRA 핫스왑 (load_lora 는 호환용으로 유지)
@app.post("/register_lora")
def register_lora(req: RegisterLoraRequest):
    """파일에서 메모리로 preload. 모델은 unchanged. Activate 는 별도."""
    _ensure_loaded()
    try:
        _inference.register_lora(req.name, req.path)
        return {
            "ok": True,
            "registered": _inference.registered_loras(),
            "active_lora": _inference.active_lora,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/activate_lora")
def activate_lora(req: ActivateLoraRequest):
    """등록된 LoRA 로 즉시 교체. name=null 이면 deactivate."""
    _ensure_loaded()
    try:
        _inference.activate_lora(req.name)
        return {
            "ok": True,
            "active_lora": _inference.active_lora,
            "registered": _inference.registered_loras(),
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/loras")
def list_loras():
    _ensure_loaded()
    return {
        "registered": _inference.registered_loras(),
        "active": _inference.active_lora,
    }


@app.post("/blend_loras")
def blend_loras(req: BlendLorasRequest):
    """Sprint 44 HHH2 — 여러 LoRA 의 가중 평균으로 활성화."""
    _ensure_loaded()
    try:
        _inference.blend_loras(req.weights)
        return {
            "ok": True,
            "active_lora": _inference.active_lora,
            "registered": _inference.registered_loras(),
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
    use_grammar: bool = True,
    grammar_dedup_pitches: bool = True,
):
    """Generate MIDI variation(s) from an uploaded MIDI file.

    Returns a multipart response (if num_variations>1) or a single MIDI body.
    For the initial skeleton, we return the first variation only as a
    single-file MIDI response.
    """
    _ensure_loaded()

    # --- Save uploaded MIDI to a unique temporary file (thread-safe) -------
    # Sprint 37.3: 기존엔 REPO_ROOT 에 mktemp — 프로세스가 크래시하면 .mid
    # 파편이 레포에 남아 git status 를 더럽혔다. 시스템 임시 디렉터리로 이관.
    import tempfile as _tmpmod
    tmp_in = Path(_tmpmod.mktemp(suffix="_in.mid"))
    tmp_out = Path(_tmpmod.mktemp(suffix="_out.mid"))
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
            use_grammar=use_grammar,
            grammar_dedup_pitches=grammar_dedup_pitches,
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


class TrackRoleJson(BaseModel):
    """Sprint XXX — 클라이언트가 다른 트랙들의 역할을 함께 보낼 때 쓴다.
    encoder.TrackRole 와 동일 스키마."""
    name: str = "other"
    role: str = "accomp"
    human_playable: bool = False
    main: bool = True


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
    # Sprint 42 FFF1: FSM grammar (대부분 True 유지 권장; False 는 디버깅용)
    use_grammar: bool = True
    grammar_dedup_pitches: bool = True
    # Sprint UUU — DAW ↔ server task/range plumbing (partner review §20-1).
    # task ∈ {variation, continuation, bar_infill, track_completion}.
    # start_bar / end_bar bound the region of interest. target_track is
    # the category name ("drums", "bass", "piano", "strings", "guitar",
    # "accomp", ...); when set, generation is biased toward that track
    # category's tokens.
    task: str = "variation"
    start_bar: int = 0
    end_bar: int = 8
    min_bars: int = 8
    target_track: str = ""
    # Sprint XXX — §20-7 SongContext 승격. nested 필드는 모두 선택적이라
    # 구 클라이언트도 그대로 동작한다.
    tracks: list[TrackRoleJson] = []
    section_map: list[tuple[int, str]] = []
    chord_map:   list[tuple[int, str]] = []
    groove:      float = 0.5
    density:     float = 0.5
    energy:      float = 0.5
    register_low:  int = 21
    register_high: int = 108
    melodic_anchor: list[int] = []
    user_hint: str = ""
    # Personalization (§20-10). "user:<id>/<profile>" 규약.
    active_lora: str = ""
    # S4 — strict chord mode. downbeat(Pos_0, Pos_16) 에서 chord tone 만
    # 허용해 "코드 진행이 귀에 안 들리는 반주" 증상 (종합리뷰 §5-1,
    # 커서형정리 §7-1) 을 막는다. 서버 default 는 True — JUCE 클라이언트가
    # 필드를 안 보내도 자동 활성화되어 10차 테스트 이후 실측 검증에 바로
    # 반영된다. False 로 두면 legacy scale-only mask 동작.
    strict_chord_mode: bool = True
    chord_tone_boost:  float = 1.5


@app.post("/generate_json")
def generate_json(req: GenerateJsonRequest):
    """Clean-room JSON variant of /generate used by the JUCE VST3 plugin.

    Request  : JSON with base64 MIDI bytes + params
    Response : JSON {"midi_base64": "...", "notes": int, "ok": true}
    """
    _ensure_loaded()

    import tempfile as _tmpmod
    tmp_in  = Path(_tmpmod.mktemp(suffix="_in.mid"))
    tmp_out = Path(_tmpmod.mktemp(suffix="_out.mid"))

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

        # Sprint UUU — derive min_bars from range when caller specifies
        # a bar window. Falls back to the explicit min_bars otherwise.
        effective_min_bars = req.min_bars
        if req.end_bar > req.start_bar:
            effective_min_bars = max(1, req.end_bar - req.start_bar)

        # Sprint XXX — if the client supplied active_lora, activate it
        # (and accept that the user LoRA may already be warmed via
        # personalization.register_standard_adapters at boot).
        if req.active_lora:
            try:
                _inference.activate_lora(req.active_lora)
            except Exception as e:
                # Activation is best-effort; a missing adapter should
                # degrade to base model rather than 500 the request.
                print(f"[server] activate_lora({req.active_lora}) skipped: {e}",
                      flush=True)

        # Sprint WWW — build a SongContext from the nested request fields
        # so the engine's elevated conditioning path sees a single object
        # instead of many loose kwargs.
        from midigpt.tokenizer.encoder import SongContext, TrackRole
        ctx = SongContext(
            target_task=req.task,
            target_track=req.target_track,
            start_bar=req.start_bar,
            end_bar=req.end_bar,
            tracks=[TrackRole(name=t.name, role=t.role,
                              human_playable=t.human_playable,
                              main=t.main) for t in req.tracks],
            section_map=list(req.section_map),
            chord_map=list(req.chord_map),
            groove=req.groove,
            density=req.density,
            energy=req.energy,
            register_low=req.register_low,
            register_high=req.register_high,
            melodic_anchor=list(req.melodic_anchor),
            user_hint=req.user_hint,
        )

        _inference.generate_to_midi(
            midi_path=str(tmp_in),
            output_path=str(tmp_out),
            meta=meta,
            max_tokens=req.max_tokens,
            min_new_tokens=req.min_new_tokens,
            min_bars=effective_min_bars,
            temperature=req.temperature,
            repetition_penalty=req.repetition_penalty,
            no_repeat_ngram_size=req.no_repeat_ngram_size,
            use_kv_cache=True,
            use_grammar=req.use_grammar,
            grammar_dedup_pitches=req.grammar_dedup_pitches,
            strict_chord_mode=req.strict_chord_mode,   # S4/S6
            chord_tone_boost=req.chord_tone_boost,     # S4/S6
            task=req.task,
            start_bar=req.start_bar,
            end_bar=req.end_bar,
            target_track=req.target_track,
            context=ctx,
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
    tmp_audio = Path(_tmpmod.mktemp(suffix=suffix))
    tmp_out_dir = Path(_tmpmod.mkdtemp(prefix="a2m_"))

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
    # Sprint 45 III1 — 일반화된 LoRA preset:
    #   --lora name1=path1,name2=path2        (CLI 콤마 구분)
    #   --lora_config config.json             (JSON: {"name": "path", ...})
    # 기존 --lora_{jazz/citypop/metal/classical} 은 하위호환 유지.
    parser.add_argument("--lora", type=str, default=None,
                        help="name=path 쌍을 콤마로 (예: jazz=a.bin,pop=b.bin)")
    parser.add_argument("--lora_config", type=str, default=None,
                        help="JSON 파일에서 LoRA preset 읽기")
    parser.add_argument("--no_autoactivate", action="store_true",
                        help="preset 자동 register 만 하고 첫 항목 activate 스킵")
    args = parser.parse_args()

    lora_paths: dict[str, str] = {}
    # 기존 4 프리셋
    for name_attr, preset_name in (("lora_jazz", "jazz"),
                                    ("lora_citypop", "citypop"),
                                    ("lora_metal", "metal"),
                                    ("lora_classical", "classical")):
        v = getattr(args, name_attr)
        if v:
            lora_paths[preset_name] = v
    # 일반화된 --lora_config (JSON)
    if args.lora_config:
        try:
            cfg_path = Path(args.lora_config)
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                print(f"[MidiGPT Server] --lora_config 포맷 오류: dict 필요")
            else:
                for k, v in data.items():
                    lora_paths[str(k)] = str(v)
        except Exception as e:
            print(f"[MidiGPT Server] --lora_config 로드 실패: {type(e).__name__}: {e}")
    # CLI 콤마 구분
    if args.lora:
        for pair in args.lora.split(","):
            if "=" not in pair:
                print(f"[MidiGPT Server] --lora 항목 무시 (= 없음): {pair}")
                continue
            n, p = pair.split("=", 1)
            n, p = n.strip(), p.strip()
            if n and p:
                lora_paths[n] = p

    print(f"[MidiGPT Server] Loading model: {args.model}")
    _inference = MidiGPTInference(InferenceConfig(
        model_path=args.model,
        lora_paths=lora_paths if lora_paths else None,
    ))

    # Sprint 45 III1 — 모든 preset 을 startup 시 register (파일 존재 시).
    # Activate 는 첫 항목만 (no_autoactivate 면 skip).
    registered = []
    for name, path in lora_paths.items():
        if not Path(path).exists():
            print(f"[MidiGPT Server] LoRA '{name}' 경로 부재 — skip: {path}")
            continue
        try:
            _inference.register_lora(name, path)
            registered.append(name)
        except Exception as e:
            print(f"[MidiGPT Server] LoRA '{name}' register 실패: {e}")
    if registered and not args.no_autoactivate:
        try:
            _inference.activate_lora(registered[0])
            print(f"[MidiGPT Server] Auto-activated: {registered[0]}")
        except Exception as e:
            print(f"[MidiGPT Server] Auto-activate 실패: {e}")

    print(f"[MidiGPT Server] Loaded. Listening on http://{args.host}:{args.port}")
    print(f"[MidiGPT Server] Registered LoRAs: {registered or 'none'}")
    print(f"[MidiGPT Server] Endpoints: /health /status /generate /load_lora "
          f"/register_lora /activate_lora /blend_loras /loras")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
