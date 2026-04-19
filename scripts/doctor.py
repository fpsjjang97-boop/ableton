r"""MidiGPT Doctor — 한 번에 모든 준비 상태 점검 + 자동 수정 가이드.

Sprint 37 — 4개 예상 이슈를 한 스크립트로 검진:
  1) 추론 서버 기동 여부 (http://127.0.0.1:8765/health)
  2) Audio2MIDI 의존성 (demucs / basic-pitch / librosa / pretty_midi 등)
  3) Tier 1 체크포인트 (Onsets & Frames / ADTOF)
  4) VST3 시스템 등록 (%ProgramFiles%\Common Files\VST3\MidiGPT.vst3)

실행: python scripts/doctor.py
종료 코드: 0 = 전부 OK, 1 = 하나 이상 실패 (문제가 있으면 fix 명령을 알려줌)

색상 없는 ASCII 출력 — Windows cmd 기본 환경에서도 읽기 좋게.
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Check primitives
# ---------------------------------------------------------------------------
class Check:
    def __init__(self, name: str):
        self.name = name
        self.ok = False
        self.detail = ""
        self.fix = ""

    def set(self, ok: bool, detail: str = "", fix: str = ""):
        self.ok = ok
        self.detail = detail
        self.fix = fix
        return self

    def print(self):
        mark = "[OK]  " if self.ok else "[FAIL]"
        print(f"  {mark} {self.name}")
        if self.detail:
            print(f"         {self.detail}")
        if not self.ok and self.fix:
            print(f"         fix: {self.fix}")


# ---------------------------------------------------------------------------
# 1. Inference server
# ---------------------------------------------------------------------------
def check_server() -> Check:
    c = Check("추론 서버 (http://127.0.0.1:8765/health)")
    try:
        with urlopen("http://127.0.0.1:8765/health", timeout=2) as r:
            data = json.load(r)
    except URLError:
        return c.set(False, "서버 연결 불가",
                     "python -m midigpt.inference_server --model ./checkpoints/midigpt_best.pt")
    except Exception as e:
        return c.set(False, f"예외: {e}",
                     "서버 로그 확인 + /health 엔드포인트 응답 검증")
    model_loaded = bool(data.get("model_loaded"))
    c.set(model_loaded,
          f"status={data.get('status')}  model_loaded={model_loaded}",
          "모델 경로 확인: --model 인자로 .pt 파일 지정")
    return c


# ---------------------------------------------------------------------------
# 2. Audio2MIDI deps
# ---------------------------------------------------------------------------
def check_a2m_deps() -> Check:
    c = Check("Audio2MIDI 의존성")
    required = ["demucs", "basic_pitch", "librosa", "pretty_midi", "mido", "numpy"]
    missing = [p for p in required if importlib.util.find_spec(p) is None]
    if missing:
        return c.set(
            False, f"누락: {', '.join(missing)}",
            "scripts/setup_audio2midi.bat   (Windows) / .sh (Linux/macOS)")
    return c.set(True, f"모두 설치됨: {', '.join(required)}")


# ---------------------------------------------------------------------------
# 3. Tier 1 checkpoints (optional)
# ---------------------------------------------------------------------------
def check_tier1_ckpt() -> list[Check]:
    checks: list[Check] = []

    # Sprint 37.4: piano backend preference order =
    #   piano_transcription_inference (pip, auto weights)
    #   -> magenta O&F (manual)
    #   -> Basic Pitch fallback
    # 둘 중 하나라도 있으면 OK. 둘 다 없으면 Basic Pitch fallback 안내.
    pti_ok = importlib.util.find_spec("piano_transcription_inference") is not None
    oaf_dir = Path(os.environ.get("MAGENTA_OAF_CHECKPOINT",
                                  REPO_ROOT / "checkpoints" / "onsets_frames"))
    oaf_ok = oaf_dir.exists() and any(oaf_dir.iterdir())

    piano = Check("Tier 1 — 피아노 전사 (PTI or O&F)")
    if pti_ok:
        piano.set(True, "piano_transcription_inference 설치됨 (PyTorch, F1 ~96%)")
    elif oaf_ok:
        piano.set(True, f"magenta O&F checkpoint: {oaf_dir}")
    else:
        piano.set(False, "PTI / O&F 둘 다 없음 (Basic Pitch ~70% fallback 사용)",
                  "python scripts/download_checkpoints.py --piano")
    checks.append(piano)

    adtof = Check("Tier 1 — ADTOF 체크포인트 (드럼)")
    adtof_dir = Path(os.environ.get("ADTOF_MODEL",
                                    REPO_ROOT / "checkpoints" / "adtof"))
    if adtof_dir.exists() and any(adtof_dir.iterdir()):
        adtof.set(True, f"{adtof_dir} — 존재")
    else:
        adtof.set(False, f"{adtof_dir} — 없음 (librosa 로 fallback)",
                  "python scripts/download_checkpoints.py --adtof  (optional ~20MB)")
    checks.append(adtof)

    return checks


# ---------------------------------------------------------------------------
# 4. VST3 system install
# ---------------------------------------------------------------------------
def check_vst3_install() -> Check:
    c = Check("VST3 시스템 등록")
    sys_plat = platform.system()
    if sys_plat == "Windows":
        target = Path(os.environ.get("ProgramFiles", "C:/Program Files"))  \
                    / "Common Files" / "VST3" / "MidiGPT.vst3"
    elif sys_plat == "Darwin":
        target = Path.home() / "Library" / "Audio" / "Plug-Ins" / "VST3" / "MidiGPT.vst3"
    else:
        target = Path.home() / ".vst3" / "MidiGPT.vst3"

    if target.exists():
        return c.set(True, f"{target}")
    return c.set(False, f"{target} — 없음",
                 "juce_daw_clean\\build.bat --install  (Windows, 관리자 권한 필요)")


# ---------------------------------------------------------------------------
# 5. Meta: model checkpoint
# ---------------------------------------------------------------------------
def check_model_ckpt() -> Check:
    c = Check("MidiGPT 모델 체크포인트")
    for name in ("midigpt_best.pt", "midigpt_latest.pt", "midigpt_ema.pt"):
        p = REPO_ROOT / "checkpoints" / name
        if p.exists():
            return c.set(True, f"{p} ({p.stat().st_size/1e6:.0f} MB)")
    return c.set(False, "checkpoints/ 에 .pt 없음",
                 "재학습 (python -m midigpt.pipeline) 또는 협업자에게 체크포인트 요청")


# ---------------------------------------------------------------------------
# 6. Checkpoint <-> VOCAB 호환성 (Sprint 41 EEE4, ref Sprint 40 DDD2)
# ---------------------------------------------------------------------------
def check_vocab_compat() -> Check:
    c = Check("체크포인트-VOCAB vocab_size 호환성")
    # torch 는 무거운 import 이므로 필요 시에만 로드
    try:
        import torch  # noqa
    except ImportError:
        return c.set(True, "torch 미설치 — 검사 skip")
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from midigpt.tokenizer.vocab import VOCAB
    except Exception as e:
        return c.set(False, f"VOCAB 로드 실패: {e}",
                     "midigpt/tokenizer/vocab.py 확인")

    best = REPO_ROOT / "checkpoints" / "midigpt_best.pt"
    if not best.exists():
        return c.set(True, "midigpt_best.pt 없음 — 검사 skip",
                     "")
    try:
        ck = torch.load(str(best), map_location="cpu", weights_only=True)
    except Exception as e:
        return c.set(False, f"체크포인트 읽기 실패: {type(e).__name__}",
                     "checkpoints/midigpt_best.pt 파일 확인")
    cfg = ck.get("config", {})
    ckpt_vs = cfg.get("vocab_size")
    if ckpt_vs is None:
        return c.set(True, "config.vocab_size 없음 — 구버전 체크포인트, 검사 skip")

    if ckpt_vs == VOCAB.size:
        return c.set(True, f"일치 — {VOCAB.size} tokens")
    diff = VOCAB.size - ckpt_vs
    return c.set(
        False,
        f"vocab 불일치 — ckpt={ckpt_vs}, current={VOCAB.size} ({diff:+d} 토큰)",
        f"python scripts/verify_checkpoint_vocab.py --ckpt {best.as_posix()}"
        f"   (v1.x → v2.0 migration 필요시 재학습 또는 migration plan)"
    )


# ---------------------------------------------------------------------------
# 7. SFT 데이터 정제 상태 (Sprint 41 EEE4, ref Sprint 40 DDD1)
# ---------------------------------------------------------------------------
def check_sft_clean() -> Check:
    c = Check("SFT 페어 정제 상태 (sft_clean/)")
    sft_clean = REPO_ROOT / "midigpt_pipeline" / "sft_clean"
    sft_raw = REPO_ROOT / "midigpt_pipeline" / "sft"
    if not sft_raw.exists():
        return c.set(True, "midigpt_pipeline/sft/ 없음 — 파이프라인 미실행, 검사 skip")

    if not sft_clean.exists():
        return c.set(
            False,
            "sft_clean/ 없음 — 재학습 전 페어 정제 권장",
            "python scripts/clean_sft_pairs.py --src ./midigpt_pipeline/sft "
            "--dst ./midigpt_pipeline/sft_clean --block_size 2048"
        )

    raw_count = len(list(sft_raw.glob("sft_*.json")))
    clean_count = len(list(sft_clean.glob("sft_*.json")))
    summary = sft_clean / "_summary_clean.json"
    detail = f"sft/={raw_count}  sft_clean/={clean_count}"
    if summary.exists():
        try:
            s = json.loads(summary.read_text(encoding="utf-8"))
            detail += f"  (trimmed={s.get('trimmed', '?')}  "
            detail += f"dup_removed={s.get('skipped', {}).get('duplicate', '?')})"
        except Exception:
            pass
    return c.set(clean_count > 0, detail,
                 "sft_clean/ 비어있음 — clean_sft_pairs.py 재실행")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 60)
    print("  MidiGPT Doctor — 실행 전 준비 상태 점검")
    print(f"  Python: {sys.version.split()[0]}   Platform: {platform.platform()}")
    print("=" * 60)

    all_checks: list[Check] = []

    print("\n[1/7] 추론 서버")
    c = check_server(); c.print(); all_checks.append(c)

    print("\n[2/7] Audio2MIDI 의존성")
    c = check_a2m_deps(); c.print(); all_checks.append(c)

    print("\n[3/7] Tier 1 체크포인트 (optional)")
    for c in check_tier1_ckpt():
        c.print(); all_checks.append(c)

    print("\n[4/7] VST3 설치")
    c = check_vst3_install(); c.print(); all_checks.append(c)

    print("\n[5/7] MidiGPT 모델 체크포인트")
    c = check_model_ckpt(); c.print(); all_checks.append(c)

    print("\n[6/7] 체크포인트-VOCAB 호환성 (Sprint 40 DDD2)")
    c = check_vocab_compat(); c.print(); all_checks.append(c)

    print("\n[7/7] SFT 페어 정제 상태 (Sprint 40 DDD1)")
    c = check_sft_clean(); c.print(); all_checks.append(c)

    # --- Summary ---
    failed = [c for c in all_checks if not c.ok]
    print()
    print("=" * 60)
    if not failed:
        print("  ✅ 전부 OK — 플러그인 실행 가능.")
        sys.exit(0)

    print(f"  ❌ {len(failed)}개 실패:")
    for c in failed:
        print(f"     • {c.name}")
        if c.fix:
            print(f"         → {c.fix}")
    print()
    print("Tier 1 체크포인트는 optional — 없어도 MVP 동작. 필수는 [1][2][5].")
    sys.exit(1)


if __name__ == "__main__":
    main()
