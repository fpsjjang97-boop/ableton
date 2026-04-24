"""FSM bar-coverage 회귀 테스트 (Sprint YYY — S3).

S3 가 MidiGrammarFSM 에 ``min_notes_per_bar`` guard 를 추가했다. 이 테스트는
실제 모델을 로드하지 않고, FSM 단위로 "현재 bar 에 노트가 없으면 다음
Bar_* 전환이 막히는지" 를 검증한다 — 10차 테스트(2026-04-21) empty_ratio
0.875 재발 방지용 단위 테스트.

검사:
    1. Bar_0 emit 직후 Bar_1 logit 이 mask 된다 (노트 0 → 전환 금지)
    2. Bar_0 → Pitch_60/Vel/Dur 후 Bar_1 logit 이 허용된다 (노트 1 → 전환 가능)
    3. min_notes_per_bar=0 이면 guard 비활성, 즉시 Bar_1 허용

사용:
    python scripts/regress_fsm_bar_coverage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from midigpt.inference.constrained import MidiGrammarFSM
from midigpt.tokenizer.vocab import VOCAB

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _tid(tok: str) -> int:
    return VOCAB.encode_token(tok)


def _bar1_logit(g: MidiGrammarFSM) -> float:
    logits = torch.zeros(VOCAB.size)
    g.apply(logits, batch=0)
    return logits[_tid("Bar_1")].item()


def _case_empty_bar_blocked() -> bool:
    g = MidiGrammarFSM(vocab=VOCAB, min_notes_per_bar=1)
    g.observe(_tid("Bar_0"), batch=0)
    v = _bar1_logit(g)
    if v > -1e9:
        print(f"  [FAIL] 노트 없는 Bar_0 뒤에 Bar_1 허용됨 (logit={v})")
        return False
    print(f"  [OK] Bar_0 → Bar_1 차단 (empty bar guard)")
    return True


def _case_non_empty_bar_allowed() -> bool:
    g = MidiGrammarFSM(vocab=VOCAB, min_notes_per_bar=1)
    for tok in ("Bar_0", "Pos_0", "Pitch_60", "Vel_8", "Dur_4"):
        g.observe(_tid(tok), batch=0)
    v = _bar1_logit(g)
    if v <= -1e9:
        print(f"  [FAIL] 노트 1개 있는 Bar_0 뒤 Bar_1 이 잘못 차단됨")
        return False
    print(f"  [OK] 노트 1 emit 후 Bar_0 → Bar_1 허용")
    return True


def _case_guard_disabled() -> bool:
    g = MidiGrammarFSM(vocab=VOCAB, min_notes_per_bar=0)
    g.observe(_tid("Bar_0"), batch=0)
    v = _bar1_logit(g)
    if v <= -1e9:
        print(f"  [FAIL] min_notes_per_bar=0 인데 Bar_1 이 차단됨")
        return False
    print(f"  [OK] min_notes_per_bar=0 이면 guard 비활성")
    return True


def _case_eight_bar_full_sequence() -> bool:
    """S3 실동작 검증 — 10차 재학습 결과의 [25, 0, 0, 0, 0, 0, 0, 0] 패턴
    이 FSM 수준에서 정말 차단되는지 end-to-end 시뮬레이션.

    시나리오: Bar_0 에 25 개 Pitch 를 emit 한 뒤 Bar_1 emit (허용), 이후
    Bar_1 에 Pitch 없이 Bar_2 시도 → 반드시 차단되어야 함.
    """
    g = MidiGrammarFSM(vocab=VOCAB, min_notes_per_bar=1)
    # Open Bar_0 and splat 25 pitches (+ vel/dur for each to complete the
    # Pitch → Vel → Dur micro-sequence so the FSM stays in ANY state).
    g.observe(_tid("Bar_0"), batch=0)
    g.observe(_tid("Pos_0"), batch=0)
    for i in range(25):
        pitch = 60 + (i % 12)
        g.observe(_tid(f"Pitch_{pitch}"), batch=0)
        g.observe(_tid("Vel_8"), batch=0)
        g.observe(_tid("Dur_4"), batch=0)
    # Now Bar_1 should be allowed (Bar_0 had >= 1 pitch).
    v = _bar1_logit(g)
    if v <= -1e9:
        print(f"  [FAIL] Bar_0 에 25 노트 찍었는데 Bar_1 로 못 감")
        return False

    # Transition to Bar_1 with NO pitches.
    g.observe(_tid("Bar_1"), batch=0)
    # Try to jump straight to Bar_2 — must be blocked because Bar_1 has
    # 0 notes. This is the exact failure shape from 10차 결과.
    logits = torch.zeros(VOCAB.size)
    g.apply(logits, batch=0)
    v2 = logits[_tid("Bar_2")].item()
    if v2 > -1e9:
        print(f"  [FAIL] Bar_1 에 노트 0 개인데 Bar_2 전환 허용 (logit={v2}) "
              f"— 10차 [25,0,0,0...] 패턴이 FSM 를 우회함")
        return False
    print(f"  [OK] Bar_1 에 노트 없으면 Bar_2 전환 차단 "
          f"(10차 [25,0,0,0,0,0,0,0] 패턴 FSM 레벨 방어)")
    return True


def _case_consecutive_bar_tokens_blocked() -> bool:
    """같은 Bar_N 을 두 번 내는 것과 next-bar 전환을 구분하는지 확인."""
    g = MidiGrammarFSM(vocab=VOCAB, min_notes_per_bar=1)
    g.observe(_tid("Bar_0"), batch=0)
    # Bar_0 을 한 번 더 내는 것은 (bar 이름 중복) FSM 의 다른 가드(bar
    # monotonicity) 에 걸리지 않지만 — allow_forward_bar_jump=1 에 의해
    # Bar_0, Bar_1 만 허용 상태. 여기서 Bar_0 을 다시 쓰는 건 허용되어도
    # 노트 카운트 0 은 유지되므로 Bar_1 으로는 여전히 못 간다.
    g.observe(_tid("Bar_0"), batch=0)  # same bar — counter stays 0
    logits = torch.zeros(VOCAB.size)
    g.apply(logits, batch=0)
    v = logits[_tid("Bar_1")].item()
    if v > -1e9:
        print(f"  [FAIL] 같은 Bar_0 재등장 후 Bar_1 허용됨")
        return False
    print(f"  [OK] 같은 bar 재등장은 counter 유지 → 여전히 전환 차단")
    return True


def main():
    print("=" * 60)
    print("  FSM Bar-Coverage 회귀 테스트 (Sprint YYY S3)")
    print("=" * 60)

    fails = 0
    for label, fn in (
        ("[1] 빈 bar 차단", _case_empty_bar_blocked),
        ("[2] 노트 있는 bar 전환 허용", _case_non_empty_bar_allowed),
        ("[3] guard 비활성 (min=0)", _case_guard_disabled),
        ("[4] 8-bar 시나리오 (10차 [25,0,0,...] 방어)", _case_eight_bar_full_sequence),
        ("[5] 같은 bar 재등장 시 counter 유지", _case_consecutive_bar_tokens_blocked),
    ):
        print(f"\n{label}")
        if not fn():
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
