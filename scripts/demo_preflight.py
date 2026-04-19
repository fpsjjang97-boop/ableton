"""6월 MVP 데모 직전 단일 진입 preflight.

docs/business/12_release_checklist.md 의 자동 가능한 항목 전체를 한 스크립트로
묶는다. 데모 시작 30분 전에 한 번 실행해 모든 그린 확인.

포함 체크:
    1. scripts/smoke_all_scripts.py  — 모든 도구 --help 통과
    2. scripts/regress_fsm_dedup.py   — FSM dedup 회귀
    3. scripts/audio2midi_edge_cases.py — BPM/clean/quantize
    4. scripts/audit_sft_tokens.py --data_dir ./midigpt_pipeline/sft_clean  — 정제 데이터 품질
    5. scripts/verify_checkpoint_vocab.py --ckpt checkpoints/midigpt_best.pt
    6. scripts/doctor.py              — 환경 체크 (서버 필수 아님)

제외 (수동 단계):
    • 서버 기동 — 데모 운영자가 별도 실행
    • 실제 생성 품질 측정 — GPU 시간 소요, 별도 세션
    • 외부 작곡가 피드백 — 인력 필요

사용:
    python scripts/demo_preflight.py           # 전 항목 순차 실행
    python scripts/demo_preflight.py --bail    # 첫 실패 시 즉시 중단

종료 코드:
    0 = 전부 OK
    1 = 하나 이상 실패
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


CHECKS: list[tuple[str, list[str], bool, int]] = [
    # (label, argv, fatal_on_fail, timeout_sec)
    ("scripts smoke (--help 전체)",
     ["smoke_all_scripts.py"], True, 300),
    ("FSM dedup 회귀 (Sprint 41 EEE1)",
     ["regress_fsm_dedup.py"], True, 60),
    # audio2midi 는 demucs/basic_pitch/librosa import 로 cold start 30-60s 소요
    ("Audio2MIDI edge case (Sprint 40 DDD4 + 42 FFF3)",
     ["audio2midi_edge_cases.py"], True, 300),
    ("SFT 정제 데이터 감사 (sft_clean/)",
     ["audit_sft_tokens.py", "--data_dir", "./midigpt_pipeline/sft_clean",
      "--ckpt_vocab_size", "420",
      "--out", "./midigpt_pipeline/sft_clean_audit.json"], False, 120),
    ("체크포인트-VOCAB 호환성",
     ["verify_checkpoint_vocab.py",
      "--ckpt", "checkpoints/midigpt_best.pt"], False, 60),
    ("doctor (환경 체크, 서버 없이도 진행)",
     ["doctor.py"], False, 60),
]


def _run(label: str, argv: list[str], timeout: int) -> tuple[bool, float, str]:
    cmd = [sys.executable, str(SCRIPTS / argv[0])] + argv[1:]
    t0 = time.time()
    try:
        res = subprocess.run(
            cmd, cwd=str(REPO_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, time.time() - t0, f"timeout > {timeout}s"
    elapsed = time.time() - t0
    if res.returncode == 0:
        return True, elapsed, ""
    return False, elapsed, (res.stderr or res.stdout or "")[-400:]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bail", action="store_true",
                    help="첫 fatal 실패 시 즉시 중단")
    args = ap.parse_args()

    print("=" * 72)
    print("  MidiGPT Demo Preflight — 6월 MVP 직전 단일 진입점")
    print("=" * 72)

    results: list[tuple[str, bool, float, str, bool]] = []
    for label, argv, fatal, timeout in CHECKS:
        print(f"\n[RUN] {label}")
        ok, elapsed, err = _run(label, argv, timeout)
        mark = "[OK]  " if ok else ("[FAIL]" if fatal else "[WARN]")
        print(f"  {mark} {elapsed:.1f}s")
        if not ok:
            for line in (err or "").splitlines()[-6:]:
                print(f"      {line}")
        results.append((label, ok, elapsed, err, fatal))
        if not ok and fatal and args.bail:
            print(f"\n[BAIL] fatal 실패 — 즉시 중단")
            break

    # Summary
    print("\n" + "=" * 72)
    oks = sum(1 for _, ok, _, _, _ in results if ok)
    total = len(results)
    fatals_failed = sum(1 for _, ok, _, _, fatal in results if not ok and fatal)
    warnings = sum(1 for _, ok, _, _, fatal in results if not ok and not fatal)
    print(f"  PASS: {oks}/{total}   FAIL(fatal): {fatals_failed}   WARN: {warnings}")

    if fatals_failed == 0 and warnings == 0:
        print("  전부 그린 — 데모 시작 가능")
        sys.exit(0)
    print("  항목 상세:")
    for label, ok, elapsed, err, fatal in results:
        mark = "OK   " if ok else ("FAIL " if fatal else "WARN ")
        print(f"    [{mark}] {elapsed:>5.1f}s  {label}")
    sys.exit(1 if fatals_failed > 0 else 0)


if __name__ == "__main__":
    main()
