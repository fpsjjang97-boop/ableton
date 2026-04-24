"""check_bar_density collapse 감지 회귀 테스트 (Sprint ZZZ — S8).

10차 재학습 결과(2026-04-23)에서 FSM bar-coverage guard(S3) 가 정상
동작함에도 per_bar_note_starts = [25, 0, 0, 0, 0, 0, 0, 0] 패턴이 반복
됐다. S8 는 reviewer 수준에서 이 패턴을 명시적으로 감지해 engine 재생성
루프가 온도·top_k 를 공격적으로 흔들도록 한다.

검사:
    1. [25, 0, 0, 0, 0, 0, 0, 0] — collapse_to_first_bar True (10차 실측)
    2. [4, 3, 4, 3, 4, 3, 4, 3] — False (균등 분포)
    3. [0, 0, 0, 0, 0, 0, 0, 0] — False (완전 빈 bar, 다른 문제)
    4. [10, 0, 0] — False (total_bars < 3 이면 collapse 개념 약하므로 안 잡음)
    5. [25, 1, 0, 1, 0, 0, 0, 0] — False (tail 평균 >= 1 이면 sparse 로 처리)

사용:
    python scripts/regress_reviewer_collapse.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from agents.reviewer import check_bar_density

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _notes_from_histogram(hist: list[int]) -> list[tuple[int, float]]:
    """Synthesize (pitch, start_beat) tuples matching a per-bar histogram.

    Pitches are arbitrary (reviewer only looks at start_beat); beats are
    spread inside each bar at 0.5-beat intervals to avoid collisions.
    beats_per_bar default is 4.0.
    """
    out: list[tuple[int, float]] = []
    for bar_idx, count in enumerate(hist):
        for i in range(count):
            beat = bar_idx * 4.0 + min(i * 0.25, 3.9)
            out.append((60 + (i % 12), beat))
    return out


def _case(hist: list[int], expect_collapse: bool, label: str) -> bool:
    notes = _notes_from_histogram(hist)
    gate = check_bar_density(notes, start_bar=0, end_bar=len(hist),
                             min_notes_per_bar=1)
    got = gate.get("collapse_to_first_bar")
    if got != expect_collapse:
        print(f"  [FAIL] {label}: collapse={got}, want {expect_collapse}, "
              f"histogram={gate.get('histogram')}")
        return False
    print(f"  [OK] {label}: collapse={got}  (histogram={gate.get('histogram')})")
    return True


def main():
    print("=" * 60)
    print("  Reviewer Collapse 감지 회귀 테스트 (Sprint ZZZ S8)")
    print("=" * 60)

    fails = 0
    print("\n[1] 10차 실측 [25, 0, 0, 0, 0, 0, 0, 0]")
    if not _case([25, 0, 0, 0, 0, 0, 0, 0], True,
                 "first-bar collapse"):
        fails += 1

    print("\n[2] 균등 분포 [4, 3, 4, 3, 4, 3, 4, 3]")
    if not _case([4, 3, 4, 3, 4, 3, 4, 3], False,
                 "dense even"):
        fails += 1

    print("\n[3] 완전 빈 [0, 0, 0, 0, 0, 0, 0, 0]")
    if not _case([0, 0, 0, 0, 0, 0, 0, 0], False,
                 "total empty (different failure)"):
        fails += 1

    print("\n[4] 경계 — 2-bar 생성 [10, 0]")
    # total_bars=2 인 경우 collapse 정의(total>=3) 밖이라 잡지 않음.
    if not _case([10, 0], False,
                 "total_bars < 3 → collapse 개념 약함, skip"):
        fails += 1

    print("\n[5] sparse tail [25, 1, 0, 1, 0, 0, 0, 0]  tail avg < 1")
    # tail = [1, 0, 1, 0, 0, 0, 0] → avg = 2/7 ≈ 0.28 < 1 → collapse 판정
    if not _case([25, 1, 0, 1, 0, 0, 0, 0], True,
                 "sparse tail still collapses"):
        fails += 1

    print("\n[6] tail avg > 1 [25, 2, 1, 2, 1, 2, 0, 0]")
    # tail = [2, 1, 2, 1, 2, 0, 0] → avg = 8/7 ≈ 1.14 >= 1 → not collapse
    if not _case([25, 2, 1, 2, 1, 2, 0, 0], False,
                 "tail avg ≥ 1 → regular sparse, not collapse"):
        fails += 1

    print()
    print("=" * 60)
    if fails == 0:
        print("  ALL PASS")
        sys.exit(0)
    print(f"  {fails} failure(s)")
    sys.exit(1)


if __name__ == "__main__":
    main()
