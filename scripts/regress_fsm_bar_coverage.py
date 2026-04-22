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


def main():
    print("=" * 60)
    print("  FSM Bar-Coverage 회귀 테스트 (Sprint YYY S3)")
    print("=" * 60)

    fails = 0
    for label, fn in (
        ("[1] 빈 bar 차단", _case_empty_bar_blocked),
        ("[2] 노트 있는 bar 전환 허용", _case_non_empty_bar_allowed),
        ("[3] guard 비활성 (min=0)", _case_guard_disabled),
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
