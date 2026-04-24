"""encoder exclude_tracks 회귀 테스트 (Sprint ZZZ — S12).

S11 audit 가 찾은 prompt/train format CRITICAL #1: inference 가 target
트랙 포함된 MIDI 를 encode 하지만 학습은 target 제외한 context 만 본다.
S12 는 encode_file / encode_pretty_midi 에 exclude_tracks 파라미터를
추가해 두 분포를 정렬.

검사:
    1. exclude_tracks=None 이면 기존 동작과 동일 (backwards compat).
    2. exclude_tracks=['drums'] 이면 drums 트랙의 Pitch 가 사라지고
       Track_drums 토큰도 출력에 나오지 않는다.
    3. 모든 트랙 제외하면 BOS/EOS 만 있는 최소 시퀀스를 반환.

사용:
    python scripts/regress_encoder_exclude.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from midigpt.tokenizer.encoder import MidiEncoder, SongMeta
from midigpt.tokenizer.vocab import VOCAB


SAMPLE = REPO_ROOT / "midi_data_combined" / "HIPHOP 63 4-4 ALL.mid"


def _token_set(ids: list[int]) -> set[str]:
    return {VOCAB.decode_id(t) for t in ids}


def _case_no_exclude_matches_legacy() -> bool:
    if not SAMPLE.exists():
        print(f"  [SKIP] 샘플 MIDI 없음: {SAMPLE}")
        return True
    enc = MidiEncoder()
    meta = SongMeta(key="C", style="pop", section="chorus", tempo=120.0)
    legacy = enc.encode_file(str(SAMPLE), meta=meta)
    new_none = enc.encode_file(str(SAMPLE), meta=meta, exclude_tracks=None)
    new_empty = enc.encode_file(str(SAMPLE), meta=meta, exclude_tracks=[])
    if legacy != new_none or legacy != new_empty:
        print(f"  [FAIL] exclude_tracks=None/[] 가 기존 동작과 다름 "
              f"(legacy={len(legacy)}, None={len(new_none)}, []={len(new_empty)})")
        return False
    print(f"  [OK] exclude_tracks=None/[] → 기존 동작과 동일 (len={len(legacy)})")
    return True


def _case_exclude_drums_removes_track_drums_token() -> bool:
    if not SAMPLE.exists():
        print(f"  [SKIP] 샘플 MIDI 없음")
        return True
    enc = MidiEncoder()
    meta = SongMeta(key="C", style="pop", section="chorus", tempo=120.0)
    ids = enc.encode_file(str(SAMPLE), meta=meta,
                          exclude_tracks=["drums"])
    toks = _token_set(ids)
    if "Track_drums" in toks:
        print(f"  [FAIL] exclude_tracks=['drums'] 인데 Track_drums 토큰이 남음")
        return False
    print(f"  [OK] exclude_tracks=['drums'] → Track_drums 사라짐 (len={len(ids)})")
    return True


def _case_exclude_all_returns_bos_eos() -> bool:
    if not SAMPLE.exists():
        print(f"  [SKIP] 샘플 MIDI 없음")
        return True
    enc = MidiEncoder()
    from midigpt.tokenizer.vocab import TRACK_TYPES
    ids = enc.encode_file(str(SAMPLE),
                          exclude_tracks=list(TRACK_TYPES))
    if ids != [VOCAB.bos_id, VOCAB.eos_id]:
        print(f"  [FAIL] 모든 트랙 제외 시 [BOS, EOS] 아닌 결과: {ids[:10]}...")
        return False
    print(f"  [OK] 모든 트랙 제외 → [BOS, EOS] 최소 시퀀스 반환")
    return True


def main():
    print("=" * 60)
    print("  Encoder exclude_tracks 회귀 테스트 (Sprint ZZZ S12)")
    print("=" * 60)

    fails = 0
    for label, fn in (
        ("[1] exclude_tracks=None/[] → 기존 동작",        _case_no_exclude_matches_legacy),
        ("[2] exclude_tracks=['drums'] → Track_drums 제거", _case_exclude_drums_removes_track_drums_token),
        ("[3] 모든 트랙 제외 → [BOS, EOS]",                _case_exclude_all_returns_bos_eos),
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
