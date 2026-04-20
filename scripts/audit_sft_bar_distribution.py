"""SFT 페어의 bar 분포 감사 (8차 리포트 EOS 조기 종료 원인 추적용).

동업자 8차 리포트 증상: 회귀 테스트 PASS 지만 실제 생성 결과는 초반
몇 마디에만 노트가 뭉치고 나머지는 빈 채로 EOS. 가설: SFT 페어의
output 구간 자체가 대부분 2~4 bar 짜리 짧은 조각이라 모델이
"짧게 끝내는 것" 을 학습한 것.

이 스크립트는 GPU 없이 midigpt_pipeline/sft/*.json 을 읽어서:
  1. 각 페어의 output 토큰 시퀀스에서 Bar_N 토큰을 모두 추출
  2. output 범위 (min Bar_N, max Bar_N, span = max - min + 1) 계산
  3. 전체 데이터셋 span 분포 + 분위수 + 히스토그램
  4. 결과를 midigpt_pipeline/training_diag.jsonl 에 한 줄로 append

출력을 보면:
  - avg output span < 4 bar 면 모델이 짧은 생성만 학습 → 8차 증상 확정
  - p95 < 8 bar 면 window_bars=16 로도 실효 학습 범위가 좁음
  - min=max=0 인 페어가 많으면 페어 빌드에 버그

Usage:
    python scripts/audit_sft_bar_distribution.py ./midigpt_pipeline/sft
    python scripts/audit_sft_bar_distribution.py ./midigpt_pipeline/sft --json report.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from collections import Counter

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from midigpt.tokenizer.vocab import VOCAB, NUM_BARS

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def bar_indices_in_token_list(tokens: list[int]) -> list[int]:
    """Return the list of bar indices (0..NUM_BARS-1) present in tokens."""
    out = []
    for tid in tokens:
        tok = VOCAB.decode_id(tid)
        if tok.startswith("Bar_"):
            try:
                out.append(int(tok.split("_", 1)[1]))
            except ValueError:
                continue
    return out


def analyze_pair(pair: dict) -> dict | None:
    """Compute per-pair bar stats.  Returns None if the pair is invalid."""
    if not (isinstance(pair, dict)
            and "input" in pair and "output" in pair):
        return None
    in_bars = bar_indices_in_token_list(pair["input"])
    out_bars = bar_indices_in_token_list(pair["output"])
    result = {
        "input_tokens":  len(pair["input"]),
        "output_tokens": len(pair["output"]),
        "input_bar_count":  len(in_bars),
        "output_bar_count": len(out_bars),
    }
    if out_bars:
        result["output_min_bar"]  = min(out_bars)
        result["output_max_bar"]  = max(out_bars)
        result["output_bar_span"] = max(out_bars) - min(out_bars) + 1
    else:
        result["output_min_bar"]  = -1
        result["output_max_bar"]  = -1
        result["output_bar_span"] = 0
    return result


def percentile(sorted_vals: list[int], pct: float) -> float:
    if not sorted_vals: return 0.0
    k = int(round((pct / 100.0) * (len(sorted_vals) - 1)))
    return float(sorted_vals[k])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sft_dir", type=str,
                    help="Directory containing sft_*.json pairs")
    ap.add_argument("--json", type=str, default=None,
                    help="Write detailed per-pair + aggregate JSON here")
    ap.add_argument("--diag-log", type=str,
                    default="midigpt_pipeline/training_diag.jsonl",
                    help="Append one JSONL summary line to this file")
    args = ap.parse_args()

    sft_dir = Path(args.sft_dir)
    if not sft_dir.exists():
        print(f"SFT dir not found: {sft_dir}")
        return 2
    files = sorted(sft_dir.glob("sft_*.json"))
    if not files:
        print(f"No sft_*.json files under {sft_dir}")
        return 2

    print(f"Analyzing {len(files)} SFT pair files...")

    per_pair: list[dict] = []
    skipped = 0
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                pair = json.load(fh)
        except (OSError, json.JSONDecodeError):
            skipped += 1
            continue
        r = analyze_pair(pair)
        if r is None:
            skipped += 1
            continue
        r["file"] = f.name
        per_pair.append(r)

    if not per_pair:
        print("All pairs invalid.")
        return 2

    # Aggregates
    spans = sorted(p["output_bar_span"] for p in per_pair)
    out_tokens = sorted(p["output_tokens"] for p in per_pair)

    agg = {
        "pair_count":          len(per_pair),
        "skipped":             skipped,
        "span_mean":           round(sum(spans) / len(spans), 2),
        "span_median":         percentile(spans, 50),
        "span_p25":            percentile(spans, 25),
        "span_p75":            percentile(spans, 75),
        "span_p95":            percentile(spans, 95),
        "span_min":            spans[0],
        "span_max":            spans[-1],
        "output_tok_mean":     round(sum(out_tokens) / len(out_tokens), 1),
        "output_tok_median":   percentile(out_tokens, 50),
        "output_tok_p95":      percentile(out_tokens, 95),
        "empty_output_count":  sum(1 for p in per_pair if p["output_bar_span"] == 0),
        "span_histogram":      dict(Counter(min(s, 32) for s in spans)),  # cap at 32 for display
    }

    print("=" * 64)
    print(f"SFT pair bar-span distribution  ({len(per_pair)} pairs)")
    print("=" * 64)
    print(f"  mean span        : {agg['span_mean']:.2f} bars")
    print(f"  median           : {agg['span_median']:.0f}")
    print(f"  p25 / p75 / p95  : {agg['span_p25']:.0f} / {agg['span_p75']:.0f} / {agg['span_p95']:.0f}")
    print(f"  min / max        : {agg['span_min']} / {agg['span_max']}")
    print(f"  empty outputs    : {agg['empty_output_count']}")
    print(f"  output tokens    : mean={agg['output_tok_mean']}, p95={agg['output_tok_p95']:.0f}")
    print()
    print("Histogram (span → count, capped 32):")
    for span in sorted(agg["span_histogram"].keys()):
        bar = "#" * min(60, agg["span_histogram"][span])
        print(f"  {span:>3}: {agg['span_histogram'][span]:>5}  {bar}")
    print("=" * 64)

    # Diagnosis hints — 8차 리포트 EOS 원인 추적
    diagnosis = []
    if agg["span_mean"] < 4.0:
        diagnosis.append("MEAN SPAN < 4 — 모델이 짧은 생성만 학습. EOS 조기 종료 가능성 ↑")
    if agg["span_p95"] < 8:
        diagnosis.append("P95 < 8 — 상위 5% 페어도 8 bar 이하. window_bars 설정 재검토")
    if agg["empty_output_count"] / len(per_pair) > 0.05:
        diagnosis.append(f"EMPTY OUTPUT {agg['empty_output_count']} 건 — 페어 빌드 로직 점검")
    if agg["span_median"] <= 2:
        diagnosis.append("MEDIAN <= 2 — 훈련 데이터 대부분이 2 bar 이하의 짧은 조각")

    if diagnosis:
        print()
        print("⚠  진단 힌트 (8차 원인 추정):")
        for d in diagnosis:
            print(f"   - {d}")
        print()
    else:
        print()
        print("✓  분포 정상 범위 — EOS 원인은 다른 곳에서 탐색 필요")
        print()

    # Append to training_diag.jsonl (one line per run, timestamped).
    diag_path = Path(args.diag_log)
    diag_path.parent.mkdir(parents=True, exist_ok=True)
    diag_entry = {
        "kind": "sft_pair_bar_distribution",
        "ts":   time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "sft_dir": str(sft_dir),
        "aggregate": agg,
        "diagnosis": diagnosis,
    }
    with open(diag_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(diag_entry, ensure_ascii=False) + "\n")
    print(f"[diag] appended to {diag_path}")

    if args.json:
        full = {"aggregate": agg, "per_pair": per_pair, "diagnosis": diagnosis}
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(full, fh, indent=2, ensure_ascii=False)
        print(f"[full report] {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
