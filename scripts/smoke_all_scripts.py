"""전체 scripts/*.py `--help` 스모크 + 핵심 도구 소스 validation.

Sprint 42 FFF4 — Sprint 40~41 로 신규 도구가 10개 이상 추가됨. 각각 import
실패 / argparse typo / 모듈 경로 오류 등을 리포지토리 전반에 대해 한 번에
탐지한다. 개별 기능 검증이 아니라 **엔트리 포인트가 뜨는지** 만 확인.

동작:
    1. scripts/ 하위 모든 .py 를 수집 (본 스크립트 자신 제외)
    2. 각 파일에 `--help` 로 20s 타임아웃 실행
    3. stdout 에 usage 또는 description 이 나오면 PASS
    4. ImportError / ModuleNotFoundError 를 stderr 에서 잡으면 상세 리포트

제외:
    • .bat / .sh 파일 — argparse 없음, 별도 smoke 필요
    • 테스트 자체는 pytest 로 — 본 스모크는 단순 "뜨는지만"

사용:
    python scripts/smoke_all_scripts.py
    python scripts/smoke_all_scripts.py --verbose   # 실패 시 stderr 전체

종료 코드:
    0 = 전부 PASS
    1 = 하나 이상 실패
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SELF = Path(__file__).name

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# 자동 수집 (.py, 자기 자신 제외, __pycache__ 하위 제외)
def _collect() -> list[Path]:
    return sorted(
        p for p in SCRIPTS_DIR.glob("*.py")
        if p.name != SELF and "__pycache__" not in str(p)
    )


def _run_help(script: Path) -> tuple[bool, str]:
    """True/False + 실패 시 stderr 일부.

    Windows cp949 디폴트 locale 에서 stdout 이 UTF-8 한글을 포함하면
    text=True 가 decode 실패. encoding="utf-8", errors="replace" 로 명시.
    """
    res = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        timeout=30,
    )
    out = (res.stdout or "") + (res.stderr or "")
    ok = (res.returncode == 0) and ("usage:" in out.lower() or "--" in out)
    return ok, out[-400:] if not ok else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    files = _collect()
    print(f"scripts/ 하위 {len(files)}개 (본 스크립트 제외)")
    print("=" * 72)

    failed: list[tuple[Path, str]] = []
    for p in files:
        try:
            ok, err = _run_help(p)
        except subprocess.TimeoutExpired:
            print(f"  [TIMEOUT] {p.name}")
            failed.append((p, "--help timed out > 20s"))
            continue
        except Exception as e:
            print(f"  [ERR]     {p.name}: {e}")
            failed.append((p, str(e)))
            continue

        mark = "[OK]     " if ok else "[FAIL]   "
        print(f"  {mark} {p.name}")
        if not ok:
            failed.append((p, err))

    print("=" * 72)
    if not failed:
        print(f"  ALL PASS ({len(files)}/{len(files)})")
        return 0

    print(f"  FAIL {len(failed)}/{len(files)}:")
    for p, err in failed:
        print(f"    • {p.name}")
        if args.verbose:
            for line in err.splitlines()[-10:]:
                print(f"        {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
