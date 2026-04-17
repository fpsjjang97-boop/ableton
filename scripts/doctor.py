"""MidiGPT Doctor — 한 번에 모든 준비 상태 점검 + 자동 수정 가이드.

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

    oaf = Check("Tier 1 — Onsets & Frames 체크포인트 (피아노)")
    oaf_dir = Path(os.environ.get("MAGENTA_OAF_CHECKPOINT",
                                  REPO_ROOT / "checkpoints" / "onsets_frames"))
    if oaf_dir.exists() and any(oaf_dir.iterdir()):
        oaf.set(True, f"{oaf_dir} — 존재")
    else:
        oaf.set(False, f"{oaf_dir} — 없음 (Basic Pitch 로 fallback)",
                "python scripts/download_checkpoints.py --oaf   (optional ~180MB)")
    checks.append(oaf)

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

    print("\n[1/5] 추론 서버")
    c = check_server(); c.print(); all_checks.append(c)

    print("\n[2/5] Audio2MIDI 의존성")
    c = check_a2m_deps(); c.print(); all_checks.append(c)

    print("\n[3/5] Tier 1 체크포인트 (optional)")
    for c in check_tier1_ckpt():
        c.print(); all_checks.append(c)

    print("\n[4/5] VST3 설치")
    c = check_vst3_install(); c.print(); all_checks.append(c)

    print("\n[5/5] MidiGPT 모델 체크포인트")
    c = check_model_ckpt(); c.print(); all_checks.append(c)

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
