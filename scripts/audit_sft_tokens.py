"""SFT 페어 토큰 범위 감사 — LLM NaN 원인 진단.

6차 리포트 NaN 원인 후보 중 **데이터 측** 만 검사한다. 재학습 실행은
동업자가 수행 — 이 스크립트는 진단/리포트만 생성한다.

검사 항목:
    1. 토큰 ID 가 [0, VOCAB.size) 범위 밖인 페어
    2. input/output 길이 분포 (0-길이, 비정상 장)
    3. effective_output_labels < MIN_SFT_OUTPUT_LABELS (이중 확인; loader 이미 pre-filter)
    4. SEP / PAD / BOS / EOS 특수 토큰 혼입 위치 이상
    5. 중복 페어 (hash 기반)

검사 제외 (코드/학습 측):
    - fp16 autocast overflow (학습 루프에서만 재현)
    - LoRA dtype/device 상속 (DDD2 에서 정적 감사)
    - gradient clipping 설정 (train_sft_lora.py 에 이미 적용됨)

출력:
    stdout — 요약 표
    {out} JSON — 페어별 상세 (동업자가 재학습 전 배제할 목록)

사용:
    python scripts/audit_sft_tokens.py \\
        --data_dir ./midigpt_pipeline \\
        --out ./midigpt_pipeline/sft_audit.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from midigpt.tokenizer.vocab import VOCAB

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


MIN_SFT_OUTPUT_LABELS = 4  # midigpt/data/dataset.py 와 동일


def _hash_seq(seq: list[int]) -> str:
    h = hashlib.sha1()
    h.update(bytes(repr(seq), "ascii"))
    return h.hexdigest()[:16]


def audit(data_dir: Path, block_size: int, out: Path,
          ckpt_vocab_size: int | None = None) -> int:
    # data_dir 가 이미 sft_*.json 을 포함하면 직접 사용 (sft_clean/ 등),
    # 아니면 관례대로 {data_dir}/sft 로 내려간다.
    if any(data_dir.glob("sft_*.json")):
        sft_dir = data_dir
    else:
        sft_dir = data_dir / "sft"
    if not sft_dir.exists():
        print(f"[ERROR] SFT 디렉토리 없음: {sft_dir}")
        return 2

    vocab_size = VOCAB.size
    pad_id = VOCAB.pad_id
    sep_id = VOCAB.sep_id
    bos_id = VOCAB.bos_id
    eos_id = VOCAB.eos_id

    # 체크포인트 기준 vocab (재학습 시 사용될 embedding 크기) 검사용
    # 현재 VOCAB.size 와 다르면 ckpt embedding 범위 초과 토큰이 있는지 확인
    effective_vocab = ckpt_vocab_size if ckpt_vocab_size else vocab_size

    print(f"Vocab size (current VOCAB): {vocab_size}")
    if ckpt_vocab_size:
        print(f"Vocab size (checkpoint):    {ckpt_vocab_size}")
        if ckpt_vocab_size != vocab_size:
            print(f"[ALERT] 체크포인트와 VOCAB 불일치 — {abs(vocab_size-ckpt_vocab_size)} 토큰 차이. "
                  f"체크포인트 범위 [0, {ckpt_vocab_size}) 초과 토큰은 재학습 시 embedding OOB → NaN")
    print(f"Block size: {block_size}")
    print(f"SFT dir:    {sft_dir}")
    print("=" * 60)

    pair_files = sorted(sft_dir.glob("sft_*.json"))
    total = len(pair_files)
    print(f"Scanned pair files: {total}")

    if total == 0:
        print("[WARN] sft_*.json 0개 — 파이프라인이 생성물을 내지 않았거나 접두사 규약 위반")
        return 1

    ok = 0
    skipped_parse = 0
    skipped_schema = 0
    oor_pairs: list[dict] = []        # out-of-range token id
    short_labels: list[dict] = []     # effective_output_labels < MIN_SFT_OUTPUT_LABELS
    empty_pairs: list[dict] = []      # input 또는 output 길이 0
    suspicious_special: list[dict] = []  # input/output 에 SEP/BOS/EOS 혼입
    hashes: dict[str, list[str]] = {}
    length_hist_input = Counter()
    length_hist_output = Counter()

    for f in pair_files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                pair = json.load(fp)
        except json.JSONDecodeError as e:
            skipped_parse += 1
            print(f"  [WARN] malformed JSON: {f.name} — {e}")
            continue

        if not (isinstance(pair, dict) and "input" in pair and "output" in pair):
            skipped_schema += 1
            print(f"  [WARN] schema invalid: {f.name}")
            continue

        inp = pair["input"]
        out_ids = pair["output"]
        if not isinstance(inp, list) or not isinstance(out_ids, list):
            skipped_schema += 1
            print(f"  [WARN] input/output not list: {f.name}")
            continue

        # 범위 검사 — effective_vocab (ckpt 크기) 기준
        # ckpt 기준 검사가 핵심: 재학습 시 embedding 실제 크기
        all_ids = inp + out_ids
        oor = [t for t in all_ids
               if not isinstance(t, int) or t < 0 or t >= effective_vocab]
        if oor:
            oor_pairs.append({
                "file": f.name,
                "count_oor": len(oor),
                "sample_oor": oor[:8],
                "max_token": max((t for t in all_ids if isinstance(t, int)),
                                 default=-1),
                "input_len": len(inp),
                "output_len": len(out_ids),
            })

        # 빈 시퀀스
        if len(inp) == 0 or len(out_ids) == 0:
            empty_pairs.append({
                "file": f.name,
                "input_len": len(inp),
                "output_len": len(out_ids),
            })

        # effective labels (dataset.py 계산식 재현)
        effective = max(0, min(len(out_ids), block_size - len(inp)))
        if effective < MIN_SFT_OUTPUT_LABELS:
            short_labels.append({
                "file": f.name,
                "input_len": len(inp),
                "output_len": len(out_ids),
                "effective": effective,
            })

        # 특수 토큰 혼입 검사 — 의도된 편성 제외:
        #   • BOS 는 input[0] 에 허용 (시퀀스 시작)
        #   • EOS 는 output[-1] 에 허용 (시퀀스 끝)
        #   • SEP / PAD 는 어디에도 존재 금지 (concat/padding 단계에서 추가되므로)
        #   • BOS/EOS 가 허용 위치 외에 등장하면 이상
        def _check_special(ids, region):
            for pos, t in enumerate(ids):
                if t == sep_id:
                    return ("SEP", pos)
                if t == pad_id:
                    return ("PAD", pos)
                if t == bos_id and not (region == "input" and pos == 0):
                    return ("BOS_mid", pos)
                if t == eos_id and not (region == "output" and pos == len(ids) - 1):
                    return ("EOS_mid", pos)
            return None

        for region, ids in (("input", inp), ("output", out_ids)):
            bad = _check_special(ids, region)
            if bad is not None:
                name, pos = bad
                suspicious_special.append({
                    "file": f.name,
                    "region": region,
                    "special": name,
                    "position": pos,
                })

        # 중복 감지
        h = _hash_seq(inp + [-1] + out_ids)
        hashes.setdefault(h, []).append(f.name)

        # 길이 히스토그램 (20 단위 bucket)
        length_hist_input[(len(inp) // 20) * 20] += 1
        length_hist_output[(len(out_ids) // 20) * 20] += 1

        ok += 1

    dupes = {h: files for h, files in hashes.items() if len(files) > 1}

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("=" * 60)
    print(f"OK pairs:              {ok:>6}")
    print(f"Malformed JSON:        {skipped_parse:>6}")
    print(f"Schema invalid:        {skipped_schema:>6}")
    print(f"Out-of-range tokens:   {len(oor_pairs):>6}  (토큰 ID >= vocab_size 또는 < 0)")
    print(f"Empty pairs:           {len(empty_pairs):>6}")
    print(f"Short effective:       {len(short_labels):>6}  (< {MIN_SFT_OUTPUT_LABELS} labels)")
    print(f"Suspicious special:    {len(suspicious_special):>6}  (input/output 에 SEP/BOS/EOS/PAD 혼입)")
    print(f"Duplicate pair groups: {len(dupes):>6}")
    print()
    print("Input length histogram (bucket=20):")
    for b in sorted(length_hist_input):
        print(f"  [{b:>4} .. {b+19:>4}]: {length_hist_input[b]}")
    print("Output length histogram (bucket=20):")
    for b in sorted(length_hist_output):
        print(f"  [{b:>4} .. {b+19:>4}]: {length_hist_output[b]}")

    # ------------------------------------------------------------------
    # JSON report (handoff to colleague)
    # ------------------------------------------------------------------
    report = {
        "vocab_size": vocab_size,
        "block_size": block_size,
        "sft_dir": str(sft_dir),
        "total_files": total,
        "ok": ok,
        "skipped_parse": skipped_parse,
        "skipped_schema": skipped_schema,
        "oor_pairs": oor_pairs,
        "empty_pairs": empty_pairs,
        "short_labels": short_labels,
        "suspicious_special": suspicious_special,
        "duplicates": dupes,
        "length_hist_input": dict(length_hist_input),
        "length_hist_output": dict(length_hist_output),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print(f"\nReport saved: {out}")

    # exit code: 0 = 모든 체크 통과, 1 = 이상 발견 (비차단 경고)
    if oor_pairs or empty_pairs or suspicious_special:
        print("[ALERT] 데이터 측 NaN 유발 가능성 있음 — 위 항목 확인 후 동업자 재학습 전 정리 권장")
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data_dir", type=str, default="./midigpt_pipeline")
    ap.add_argument("--block_size", type=int, default=2048)
    ap.add_argument("--out", type=str, default="./midigpt_pipeline/sft_audit.json")
    ap.add_argument("--ckpt_vocab_size", type=int, default=None,
                    help="체크포인트 embedding 크기. 현재 VOCAB 와 다를 때 체크포인트 "
                         "기준으로 OOR 검사 (재학습 시 실제 embedding 범위)")
    args = ap.parse_args()

    rc = audit(Path(args.data_dir), args.block_size, Path(args.out),
               ckpt_vocab_size=args.ckpt_vocab_size)
    sys.exit(rc)


if __name__ == "__main__":
    main()
