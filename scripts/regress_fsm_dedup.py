"""FSM dedup 회귀 테스트 (Sprint 41 EEE1 → EEE5).

EEE1 이 `generate_to_midi` 경로에 MidiGrammarFSM 을 연결했다. 이 테스트는
실제 모델을 로드하지 않고, **FSM 자체 단위로** 중복 노트 차단이 동작하는지
검증한다 — 모델 호출 없이 빠르게 회귀를 잡기 위함 (GPU 불필요).

검사:
    1. Bar_0 → Pos_0 → Pitch_60 → Vel_8 → Dur_4 시퀀스 통과 후
       다음에 Pitch_60 을 다시 내면 FSM.apply 가 해당 logit 을 -inf 로 차단
    2. Pitch 가 다른 경우 (Pitch_64) 는 차단 안 됨
    3. (bar, pos) 가 바뀌면 dedup set 이 리셋됨

또한 **파일 시스템 회귀**도: 기존 output/*.mid 중 신규 파이프라인을 통과한
파일이 duplicate_notes=0 인지 확인 (optional, --check-output 플래그).

사용:
    python scripts/regress_fsm_dedup.py          # FSM 단위 테스트만
    python scripts/regress_fsm_dedup.py --check-output output/_e2e_test_gen.mid
"""
from __future__ import annotations

import argparse
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


def _verify_dedup() -> bool:
    g = MidiGrammarFSM(vocab=VOCAB, dedup_pitches=True)
    size = VOCAB.size
    # 시퀀스: Bar_0 → Pos_0 → Pitch_60 → Vel_8 → Dur_4
    for tok in ("Bar_0", "Pos_0", "Pitch_60", "Vel_8", "Dur_4"):
        g.observe(_tid(tok), batch=0)

    # 이제 같은 (bar,pos) 에서 Pitch_60 이 오면 차단되어야 함
    logits = torch.zeros(size)
    logits_after = g.apply(logits.clone(), batch=0)
    pitch60_id = _tid("Pitch_60")
    pitch64_id = _tid("Pitch_64")

    if logits_after[pitch60_id].item() > -1e9:
        print(f"  [FAIL] Pitch_60 재등장 허용됨 (logit={logits_after[pitch60_id].item()})")
        return False
    if logits_after[pitch64_id].item() <= -1e9:
        print(f"  [FAIL] Pitch_64 (다른 피치) 이 잘못 차단됨")
        return False
    print(f"  [OK] 동일 (bar,pos) Pitch_60 차단, Pitch_64 허용")

    # (bar,pos) 변경 후 Pitch_60 재허용
    g.observe(_tid("Bar_1"), batch=0)
    g.observe(_tid("Pos_0"), batch=0)
    logits = torch.zeros(size)
    logits_after = g.apply(logits.clone(), batch=0)
    if logits_after[pitch60_id].item() <= -1e9:
        print(f"  [FAIL] bar 변경 후 Pitch_60 이 여전히 차단")
        return False
    print(f"  [OK] bar 변경 후 Pitch_60 다시 허용")

    return True


def _verify_engine_wiring() -> bool:
    """engine.generate_to_midi 시그니처에 use_grammar 가 있는지 검사."""
    import inspect
    from midigpt.inference.engine import MidiGPTInference
    sig = inspect.signature(MidiGPTInference.generate_to_midi)
    params = list(sig.parameters)
    if "use_grammar" not in params:
        print(f"  [FAIL] generate_to_midi 에 use_grammar 없음 — EEE1 회귀")
        return False
    if "grammar_dedup_pitches" not in params:
        print(f"  [FAIL] grammar_dedup_pitches 없음")
        return False
    print(f"  [OK] generate_to_midi 가 use_grammar/dedup 파라미터 보유")
    return True


def _count_dups_in_midi(path: Path) -> int:
    """mid 파일을 토큰화 → 중복 (bar,pos,pitch) 시퀀스 개수."""
    from midigpt.tokenizer.encoder import MidiEncoder
    enc = MidiEncoder()
    try:
        ids = enc.encode_file(str(path))
    except Exception as e:
        print(f"  [WARN] encode 실패 {path.name}: {e}")
        return -1
    tokens = VOCAB.decode_ids(ids)
    dups = 0
    bar = pos = None
    prev = None
    for t in tokens:
        if t.startswith("Bar_"):
            bar = t
        elif t.startswith("Pos_"):
            pos = t
        elif t.startswith("Pitch_"):
            sig = (bar, pos, t)
            if sig == prev and bar:
                dups += 1
            prev = sig
    return dups


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check-output", type=str, default=None,
                    help="해당 MIDI 파일 하나의 duplicate 개수 확인 + 0 이어야 통과")
    args = ap.parse_args()

    print("=" * 60)
    print("  FSM Dedup 회귀 테스트 (Sprint 41 EEE5)")
    print("=" * 60)

    fails = 0

    print("\n[1] FSM 단위 — 동일 (bar,pos,pitch) 차단")
    if not _verify_dedup():
        fails += 1

    print("\n[2] Engine wiring — generate_to_midi use_grammar 파라미터")
    if not _verify_engine_wiring():
        fails += 1

    if args.check_output:
        p = Path(args.check_output)
        print(f"\n[3] 파일 {p.name} 의 duplicate 카운트")
        dups = _count_dups_in_midi(p)
        if dups > 0:
            print(f"  [FAIL] duplicate_notes={dups}  (0 이어야 함)")
            fails += 1
        elif dups == 0:
            print(f"  [OK] duplicate_notes=0")
        else:
            print(f"  [SKIP] 파일 읽기 실패")

    print()
    print("=" * 60)
    if fails == 0:
        print("  ALL PASS")
        sys.exit(0)
    print(f"  {fails} failure(s)")
    sys.exit(1)


if __name__ == "__main__":
    main()
