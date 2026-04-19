"""체크포인트 vocab 호환성 검증 + snapshot 생성.

Sprint 40 DDD2 발견: checkpoint `midigpt_best.pt` 의 `config.vocab_size=420`
반면 현재 `VOCAB.size=527`. v1.x / v2.0 vocab 불일치가 조용히 누적되어
SFT 재학습 후 "v2.0 토큰은 절대 생성되지 않는" 상태.

본 유틸은 재발 방지 목적:

    [verify]  체크포인트 config.vocab_size vs 현재 VOCAB.size 비교
              불일치 시 vocab-diff 리포트 (추가/제거 토큰 문자열 목록)
    [snapshot] 학습 직후 호출 → 현재 VOCAB 의 token→id 맵을
              <ckpt>_vocab.json 으로 저장. 나중에 로드 시 당시 vocab 재구성 가능.

사용:
    # 현재 체크포인트 검증
    python scripts/verify_checkpoint_vocab.py --ckpt checkpoints/midigpt_best.pt

    # 학습 종료 후 vocab 스냅샷 생성
    python scripts/verify_checkpoint_vocab.py --ckpt checkpoints/midigpt_best.pt --snapshot

    # 스냅샷과 대조 (snapshot JSON 이 있을 때)
    python scripts/verify_checkpoint_vocab.py --ckpt checkpoints/midigpt_best.pt \\
        --against-snapshot checkpoints/midigpt_best_vocab.json

종료 코드:
    0 = 일치 / 스냅샷 성공
    1 = 불일치 (재학습 또는 vocab migration 필요)
    2 = 체크포인트 읽기 실패
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from midigpt.tokenizer.vocab import VOCAB

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _load_ckpt_config(ckpt: Path) -> dict | None:
    try:
        c = torch.load(str(ckpt), map_location="cpu", weights_only=True)
    except Exception as e:
        print(f"[ERROR] 체크포인트 로드 실패: {type(e).__name__}: {e}")
        return None
    return c.get("config")


def _current_vocab_map() -> dict[str, int]:
    # MidiVocab 의 internal 맵 접근 — vocab.py 에 공개 API 없어 private 사용.
    return dict(VOCAB._token2id)


def verify(ckpt: Path, against_snapshot: Path | None) -> int:
    config = _load_ckpt_config(ckpt)
    if config is None:
        return 2
    ckpt_vocab = config.get("vocab_size")
    print(f"체크포인트:  {ckpt}")
    print(f"  vocab_size: {ckpt_vocab}")
    print(f"  n_layer:    {config.get('n_layer')}  n_head: {config.get('n_head')}  "
          f"n_embd: {config.get('n_embd')}  block_size: {config.get('block_size')}")
    print(f"현재 VOCAB:  size={VOCAB.size}")
    print("=" * 60)

    # 기본 검증: vocab_size 숫자
    if ckpt_vocab == VOCAB.size:
        print(f"[OK] vocab_size 일치 ({VOCAB.size})")
        return 0

    diff = VOCAB.size - (ckpt_vocab or 0)
    print(f"[ALERT] vocab_size 불일치 — {abs(diff)} 토큰 차이")

    # 상세 diff (현재 맵 기준)
    cur_map = _current_vocab_map()
    # 현재 vocab 에서 ID >= ckpt_vocab 인 토큰 = v2.0 추가분 (체크포인트가 모름)
    v20_only = sorted(
        [(tid, tok) for tok, tid in cur_map.items()
         if ckpt_vocab is not None and tid >= ckpt_vocab],
        key=lambda x: x[0],
    )
    if v20_only:
        print(f"[INFO] 현재 VOCAB 에만 있고 체크포인트에는 없는 토큰 {len(v20_only)}개:")
        sample = v20_only[:20]
        for tid, tok in sample:
            print(f"    {tid:>4}: {tok}")
        if len(v20_only) > 20:
            print(f"    ... (+{len(v20_only) - 20}개 더)")

    # against-snapshot 상세 비교
    if against_snapshot:
        if not against_snapshot.exists():
            print(f"[WARN] snapshot 파일 없음: {against_snapshot}")
        else:
            with open(against_snapshot, "r", encoding="utf-8") as fp:
                snap = json.load(fp)
            snap_map = snap.get("token_to_id", {})
            missing_now = [t for t in snap_map if t not in cur_map]
            added_now = [t for t in cur_map if t not in snap_map]
            renamed_id = [
                (t, snap_map[t], cur_map[t])
                for t in snap_map if t in cur_map and snap_map[t] != cur_map[t]
            ]
            print("=" * 60)
            print(f"Snapshot 비교 ({against_snapshot.name}):")
            print(f"  snapshot 에만 있음: {len(missing_now)}")
            print(f"  현재 에만 추가됨:   {len(added_now)}")
            print(f"  ID 재배정:          {len(renamed_id)} — 치명적 (체크포인트 비호환)")
            if renamed_id[:5]:
                for t, old, new in renamed_id[:5]:
                    print(f"    {t}: {old} -> {new}")

    print()
    print("권장 조치 (Sprint 41 EEE3):")
    print("  1. 현재 체크포인트는 config.vocab_size=420 기반으로 재학습됨")
    print("  2. 새 vocab 엔트리를 사용하려면 vocab_size=527 로 embedding 확장 후 재학습 필수")
    print("  3. 또는 v2.0 vocab 을 쓰는 신 체크포인트를 생성 후 --base_model 교체")
    return 1


def snapshot(ckpt: Path) -> int:
    cur_map = _current_vocab_map()
    config = _load_ckpt_config(ckpt) or {}
    out = ckpt.with_name(ckpt.stem + "_vocab.json")
    snap = {
        "checkpoint": ckpt.name,
        "ckpt_vocab_size": config.get("vocab_size"),
        "vocab_size": VOCAB.size,
        "token_to_id": cur_map,
        "note": "Vocab snapshot at time of training — VOCAB 구조가 바뀌면 대조에 사용",
    }
    with open(out, "w", encoding="utf-8") as fp:
        json.dump(snap, fp, ensure_ascii=False, indent=2)
    print(f"[OK] snapshot 저장: {out}  ({len(cur_map)} tokens)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--snapshot", action="store_true",
                    help="현재 VOCAB 을 <ckpt>_vocab.json 으로 저장")
    ap.add_argument("--against-snapshot", type=str, default=None,
                    help="snapshot JSON 과 대조 (어느 토큰이 재배정/삭제/추가됐는지)")
    args = ap.parse_args()
    ckpt = Path(args.ckpt)
    if args.snapshot:
        sys.exit(snapshot(ckpt))
    sys.exit(verify(
        ckpt,
        Path(args.against_snapshot) if args.against_snapshot else None,
    ))


if __name__ == "__main__":
    main()
