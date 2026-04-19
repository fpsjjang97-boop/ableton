"""SFT 페어 정제 — block_size 정합 + dedup + 길이 트리밍.

Sprint 40 DDD1 발견 (docs/business/14_sft_audit_report.md):
    • 14,622 페어 중 60.4% (8,832) 가 effective output labels < 4 → loader skip
    • 중복 페어 hash 그룹 3,086

원인: build_sft_pairs.py 가 output 길이를 block_size 기준으로 제한하지 않음.
해결: 기존 sft/ 디렉토리를 input 으로 받아 정제된 sft_clean/ 을 출력.
      동업자가 train_sft_lora.py --data_dir <새 경로> 로 바로 재학습 가능.

정제 규칙:
    1. 개별 페어: input + 1(SEP) + output ≤ block_size
       초과 시 output 을 뒷부분부터 자름 (앞부분 = 화성/마디 head 유지)
    2. 자른 뒤 effective_output_labels < MIN_SFT_OUTPUT_LABELS (기본 4) → skip
    3. 동일 (input, output) 해시 중복 → 첫 번째만 유지
    4. 특수 토큰이 허용 위치 외에 있는 페어 → skip (Sprint 40 에서 0건 확인)
    5. 토큰 ID 범위 [0, vocab_size) 외 → skip (Sprint 40 에서 0건 확인)

사용:
    python scripts/clean_sft_pairs.py \\
        --src ./midigpt_pipeline/sft \\
        --dst ./midigpt_pipeline/sft_clean \\
        --block_size 2048

    # ckpt vocab 기준 OOR 검사
    python scripts/clean_sft_pairs.py --src ./midigpt_pipeline/sft \\
        --dst ./midigpt_pipeline/sft_clean --ckpt_vocab_size 420
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from midigpt.tokenizer.vocab import VOCAB

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


MIN_SFT_OUTPUT_LABELS = 4


def _hash(seq: list[int]) -> str:
    h = hashlib.sha1()
    h.update(bytes(repr(seq), "ascii"))
    return h.hexdigest()[:16]


def _trim_to_block(inp: list[int], out: list[int], block_size: int
                   ) -> tuple[list[int], list[int]]:
    """input + SEP + output 가 block_size 를 넘으면 output 을 뒷부분부터 잘라냄.

    input 은 유지 (화성/마디 context 이므로). 단 input 자체가 block_size 를
    넘으면 input 을 앞부분부터 자르고 output 공간 최소 확보.
    """
    budget = block_size - 1  # -1 for SEP
    if len(inp) >= budget - MIN_SFT_OUTPUT_LABELS:
        # input 이 너무 길어 output 공간이 부족 — input 을 trim
        inp = inp[: max(1, budget - MIN_SFT_OUTPUT_LABELS)]
    max_out = budget - len(inp)
    if len(out) > max_out:
        out = out[:max_out]
    return inp, out


def clean(src: Path, dst: Path, block_size: int,
          ckpt_vocab_size: int | None, preserve_meta: bool) -> int:
    if not src.exists():
        print(f"[ERROR] src 없음: {src}")
        return 2
    dst.mkdir(parents=True, exist_ok=True)

    vocab_size = VOCAB.size
    effective_vocab = ckpt_vocab_size or vocab_size
    pad_id = VOCAB.pad_id
    sep_id = VOCAB.sep_id
    bos_id = VOCAB.bos_id
    eos_id = VOCAB.eos_id

    print(f"src:             {src}")
    print(f"dst:             {dst}")
    print(f"block_size:      {block_size}")
    print(f"vocab (current): {vocab_size}")
    if ckpt_vocab_size:
        print(f"vocab (ckpt):    {ckpt_vocab_size}")
    print("=" * 60)

    files = sorted(src.glob("sft_*.json"))
    if not files:
        print(f"[ERROR] sft_*.json 없음: {src}")
        return 2

    skipped_parse = 0
    skipped_schema = 0
    skipped_oor = 0
    skipped_short = 0
    skipped_special = 0
    skipped_dup = 0
    trimmed = 0
    kept = 0
    seen: set[str] = set()

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                pair = json.load(fp)
        except json.JSONDecodeError as e:
            skipped_parse += 1
            continue

        if not (isinstance(pair, dict) and "input" in pair and "output" in pair
                and isinstance(pair["input"], list)
                and isinstance(pair["output"], list)):
            skipped_schema += 1
            continue

        inp: list[int] = list(pair["input"])
        out: list[int] = list(pair["output"])

        # OOR 검사 (ckpt 기준)
        if any((not isinstance(t, int)) or t < 0 or t >= effective_vocab
               for t in inp + out):
            skipped_oor += 1
            continue

        # 특수 토큰 이상 위치
        def _bad_special(ids: list[int], region: str) -> bool:
            for pos, t in enumerate(ids):
                if t == sep_id or t == pad_id:
                    return True
                if t == bos_id and not (region == "input" and pos == 0):
                    return True
                if t == eos_id and not (region == "output" and pos == len(ids) - 1):
                    return True
            return False
        if _bad_special(inp, "input") or _bad_special(out, "output"):
            skipped_special += 1
            continue

        # block_size trim
        orig_lens = (len(inp), len(out))
        inp, out = _trim_to_block(inp, out, block_size)
        if (len(inp), len(out)) != orig_lens:
            trimmed += 1

        # Effective labels
        effective = max(0, min(len(out), block_size - len(inp)))
        if effective < MIN_SFT_OUTPUT_LABELS:
            skipped_short += 1
            continue

        # Dedup
        sig = _hash(inp + [-1] + out)
        if sig in seen:
            skipped_dup += 1
            continue
        seen.add(sig)

        # Write
        new_pair = {"input": inp, "output": out}
        if preserve_meta and "metadata" in pair:
            new_pair["metadata"] = pair["metadata"]
        out_path = dst / f"sft_{kept:05d}.json"
        with open(out_path, "w", encoding="utf-8") as fp:
            json.dump(new_pair, fp, ensure_ascii=False)
        kept += 1

    # Summary
    print(f"Input pairs:          {len(files):>6}")
    print(f"Kept (clean):         {kept:>6}")
    print(f"Trimmed to block:     {trimmed:>6}")
    print(f"Skipped malformed:    {skipped_parse:>6}")
    print(f"Skipped schema:       {skipped_schema:>6}")
    print(f"Skipped OOR:          {skipped_oor:>6}")
    print(f"Skipped short labels: {skipped_short:>6}")
    print(f"Skipped special:      {skipped_special:>6}")
    print(f"Skipped duplicate:    {skipped_dup:>6}")
    print(f"Output:               {dst}")

    # Write summary (glob pattern 으로 loader 가 건드리지 않도록 summary 명명)
    summary = {
        "src": str(src), "dst": str(dst),
        "block_size": block_size, "vocab_size": vocab_size,
        "ckpt_vocab_size": ckpt_vocab_size,
        "input_count": len(files), "kept": kept, "trimmed": trimmed,
        "skipped": {
            "parse": skipped_parse, "schema": skipped_schema,
            "oor": skipped_oor, "short": skipped_short,
            "special": skipped_special, "duplicate": skipped_dup,
        },
    }
    with open(dst / "_summary_clean.json", "w", encoding="utf-8") as fp:
        json.dump(summary, fp, ensure_ascii=False, indent=2)

    return 0 if kept > 0 else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", default="./midigpt_pipeline/sft")
    ap.add_argument("--dst", default="./midigpt_pipeline/sft_clean")
    ap.add_argument("--block_size", type=int, default=2048)
    ap.add_argument("--ckpt_vocab_size", type=int, default=None)
    ap.add_argument("--no_preserve_meta", action="store_true",
                    help="원본 metadata 필드 버리기 (저장 용량 절약)")
    args = ap.parse_args()

    sys.exit(clean(Path(args.src), Path(args.dst), args.block_size,
                   args.ckpt_vocab_size, not args.no_preserve_meta))


if __name__ == "__main__":
    main()
