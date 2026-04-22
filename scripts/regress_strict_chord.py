"""Strict chord mode 회귀 테스트 (Sprint YYY — S4).

커서형정리 §7-1 "강박에서는 chord tone 만 허용" 규약이 실제 mask 로 동작
하는지 검증한다. 모델 로드 없이 ``_apply_harmonic_mask`` 단위로.

검사:
    1. C maj 컨텍스트 + Pos_0 (downbeat) + strict=True 에서
       - Pitch_62 (D, scale 내 non-chord-tone) → -inf
       - Pitch_60 (C, root) / Pitch_64 (E, 3rd) / Pitch_67 (G, 5th) → 유지
    2. 같은 chord + Pos_4 (weak beat) + strict=True → Pitch_62 허용
       (약박에는 기존 scale mask 만)
    3. strict=False 면 Pos_0 이어도 Pitch_62 허용 (기존 동작 보존)
    4. beat_strength() 의 기본 분류 확인

사용:
    python scripts/regress_strict_chord.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from midigpt.inference.constrained import MidiGrammarFSM
from midigpt.inference.harmony import BeatStrength, beat_strength
from midigpt.tokenizer.vocab import VOCAB

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _tid(tok: str) -> int:
    return VOCAB.encode_token(tok)


def _prepare_cmaj_context(pos: int, strict: bool):
    """Return (engine_fn, context_ids, grammar, logits) for harmonic mask test."""
    from midigpt.inference.engine import MidiGPTInference

    # Build a minimal inference object without loading a model — we only
    # need _apply_harmonic_mask and its _pitch_token_ids lookup.
    inst = MidiGPTInference.__new__(MidiGPTInference)
    inst.vocab = VOCAB
    from midigpt.inference.engine import _build_pitch_token_ids
    inst._pitch_token_ids = _build_pitch_token_ids(VOCAB)

    # Prime FSM with Bar_0 + Pos_{pos} (plus a placeholder pitch so the
    # bar-coverage guard does not mask further pitches — we only care
    # about harmonic mask here).
    g = MidiGrammarFSM(vocab=VOCAB)
    g.observe(_tid("ChordRoot_C"), batch=0)
    g.observe(_tid("ChordQual_maj"), batch=0)
    g.observe(_tid("Bar_0"), batch=0)
    g.observe(_tid("Pos_0"), batch=0)
    g.observe(_tid("Pitch_60"), batch=0)
    g.observe(_tid("Vel_8"), batch=0)
    g.observe(_tid("Dur_4"), batch=0)
    # Now move to the target Pos for the test.
    g.observe(_tid(f"Pos_{pos}"), batch=0)

    context_ids = [
        _tid("ChordRoot_C"), _tid("ChordQual_maj"),
        _tid("Bar_0"), _tid(f"Pos_{pos}"),
    ]
    # Fresh logits — all zero so any -inf is observable.
    logits = torch.zeros(VOCAB.size)
    return inst, context_ids, g, logits


def _case_downbeat_blocks_non_chord_tone() -> bool:
    inst, ctx, g, logits = _prepare_cmaj_context(pos=0, strict=True)
    out = inst._apply_harmonic_mask(
        logits, ctx,
        chord_tone_boost=1.0,  # disable boost so we only see mask behaviour
        strict_chord_mode=True,
        grammar=g,
        batch=0,
    )
    ok = True
    if out[_tid("Pitch_62")].item() > -1e9:  # D — scale, not chord tone
        print(f"  [FAIL] Pos_0 strict=True: Pitch_62 (D) 허용됨 → 강박 차단 실패")
        ok = False
    for tok in ("Pitch_60", "Pitch_64", "Pitch_67"):
        if out[_tid(tok)].item() <= -1e9:
            print(f"  [FAIL] Pos_0 strict=True: {tok} (chord tone) 이 잘못 차단됨")
            ok = False
    if ok:
        print("  [OK] downbeat(Pos_0) 에서 chord tone(C/E/G) 만 허용, D 차단")
    return ok


def _case_weakbeat_allows_scale_tone() -> bool:
    inst, ctx, g, logits = _prepare_cmaj_context(pos=4, strict=True)
    out = inst._apply_harmonic_mask(
        logits, ctx,
        chord_tone_boost=1.0,
        strict_chord_mode=True,
        grammar=g,
        batch=0,
    )
    if out[_tid("Pitch_62")].item() <= -1e9:
        print(f"  [FAIL] Pos_4 (weak beat): scale 내 non-chord-tone D 가 잘못 차단됨")
        return False
    # Off-scale 은 여전히 차단되어야 함 — C maj scale 외부인 C# (Pitch_61) 확인.
    if out[_tid("Pitch_61")].item() > -1e9:
        print(f"  [FAIL] Pos_4: off-scale Pitch_61 (C#) 가 허용됨 → scale mask 누락")
        return False
    print("  [OK] weak beat(Pos_4) 에서 D 허용, off-scale 은 여전히 차단")
    return True


def _case_strict_off_preserves_legacy() -> bool:
    inst, ctx, g, logits = _prepare_cmaj_context(pos=0, strict=False)
    out = inst._apply_harmonic_mask(
        logits, ctx,
        chord_tone_boost=1.0,
        strict_chord_mode=False,
        grammar=None,
        batch=0,
    )
    if out[_tid("Pitch_62")].item() <= -1e9:
        print(f"  [FAIL] strict=False: Pitch_62 가 차단됨 → 기존 동작 깨짐")
        return False
    print("  [OK] strict=False 일 때 기존 동작 유지")
    return True


def _case_beat_strength_classification() -> bool:
    expect = {
        0: BeatStrength.STRONG,  16: BeatStrength.STRONG,
        8: BeatStrength.UPBEAT,  24: BeatStrength.UPBEAT,
        4: BeatStrength.WEAK,    12: BeatStrength.WEAK,
        20: BeatStrength.WEAK,   28: BeatStrength.WEAK,
        1: BeatStrength.VERY_WEAK, 31: BeatStrength.VERY_WEAK,
        -1: BeatStrength.VERY_WEAK, 99: BeatStrength.VERY_WEAK,
    }
    ok = True
    for pos, want in expect.items():
        got = beat_strength(pos)
        if got != want:
            print(f"  [FAIL] beat_strength({pos}) = {got} (want {want})")
            ok = False
    if ok:
        print(f"  [OK] {len(expect)} 개 beat strength 분류 모두 일치")
    return ok


def main():
    print("=" * 60)
    print("  Strict Chord Mode 회귀 테스트 (Sprint YYY S4)")
    print("=" * 60)

    fails = 0
    for label, fn in (
        ("[1] downbeat 에서 non-chord-tone 차단",     _case_downbeat_blocks_non_chord_tone),
        ("[2] weak beat 에서 scale tone 허용",         _case_weakbeat_allows_scale_tone),
        ("[3] strict=False 면 기존 동작 보존",         _case_strict_off_preserves_legacy),
        ("[4] beat_strength() 분류 정확성",            _case_beat_strength_classification),
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
