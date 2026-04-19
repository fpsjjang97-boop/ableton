"""
MidiGPT — Self-Improvement Loop
================================

End-to-end automation of the closed-loop reinforcement cycle:

    base model
        ↓
    1. generate variations from midi_data/  (inference engine)
        ↓  output/*.mid + output/*.mid.meta.json
    2. reviewer scores each variation       (rule-based: scale / vel / rhythm / entropy)
        ↓  reviews/*.json
    3. build DPO pairs (chosen ≥80, rejected <60)
        ↓  midigpt/dpo_pairs/*.json
    4. DPO fine-tune                        (preference optimisation)
        ↓
    new LoRA adapter → next cycle

Usage:
    python scripts/run_self_improvement_loop.py \
        --base_model ./checkpoints/midigpt_ema.pt \
        --cycles 3 \
        --variants_per_song 3

After every cycle the script writes a JSON summary to
``self_improvement_log.jsonl`` so you can inspect what happened later.

⚠️  IMPORTANT — when to STOP:
    The reviewer is rule-based. Looping the auto-feedback indefinitely
    over-fits to those rules and degrades real musicality. Run at most
    3-5 cycles between human listening checkpoints.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

OUTPUT_DIR = REPO_ROOT / "output"
REVIEWS_DIR = REPO_ROOT / "reviews"
DPO_PAIRS_DIR = REPO_ROOT / "midigpt" / "dpo_pairs"
LORA_DIR = REPO_ROOT / "lora_checkpoints"
LOG_PATH = REPO_ROOT / "self_improvement_log.jsonl"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def banner(title: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}\n  {title}\n{bar}")


def log_event(payload: dict) -> None:
    payload = {"timestamp": datetime.now().isoformat(), **payload}
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_meta(midi_path: Path, source: str, cycle: int, meta_extra: dict) -> None:
    """Write the .meta.json side-car expected by the reviewer."""
    meta = {
        "file": midi_path.name,
        "status": "pending_review",
        "source": source,
        "cycle": cycle,
        "generated_at": datetime.now().isoformat(),
        **meta_extra,
    }
    with open(str(midi_path) + ".meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Step 1 — Generation
# ---------------------------------------------------------------------------
def step_generate(
    base_model: str,
    midi_dir: Path,
    cycle: int,
    variants_per_song: int,
    max_tokens: int,
    min_new_tokens: int,
    temperature: float,
    repetition_penalty: float,
    no_repeat_ngram_size: int,
    limit: Optional[int],
) -> int:
    """Generate variations from every MIDI in ``midi_dir``.

    Returns the number of files successfully created.
    """
    banner(f"Cycle {cycle} — STEP 1: generate variations")

    from midigpt.inference.engine import InferenceConfig, MidiGPTInference
    from midigpt.tokenizer.encoder import SongMeta

    if not Path(base_model).exists():
        print(f"[FAIL] base model not found: {base_model}")
        return 0

    inf = MidiGPTInference(InferenceConfig(model_path=base_model))
    if not inf.is_loaded:
        print("[FAIL] base model failed to load")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    sources = sorted(list(midi_dir.rglob("*.mid")) + list(midi_dir.rglob("*.midi")))
    if limit is not None:
        sources = sources[:limit]

    if not sources:
        print(f"[FAIL] no MIDI files in {midi_dir}")
        return 0

    print(f"Source MIDIs: {len(sources)}")
    print(f"Variants per song: {variants_per_song}")

    created = 0
    t0 = time.time()
    for src in sources:
        for k in range(variants_per_song):
            stem = f"cycle{cycle}_{src.stem}_v{k}"
            out_path = OUTPUT_DIR / f"{stem}.mid"
            try:
                inf.generate_to_midi(
                    midi_path=str(src),
                    output_path=str(out_path),
                    meta=SongMeta(
                        key="C", style="pop", section="verse", tempo=120
                    ),
                    max_tokens=max_tokens,
                    min_new_tokens=min_new_tokens,
                    temperature=temperature,
                    repetition_penalty=repetition_penalty,
                    no_repeat_ngram_size=no_repeat_ngram_size,
                    use_kv_cache=True,
                )
                write_meta(
                    out_path,
                    source=str(src.relative_to(REPO_ROOT)),
                    cycle=cycle,
                    meta_extra={
                        "variant": k,
                        "max_tokens": max_tokens,
                        "min_new_tokens": min_new_tokens,
                        "temperature": temperature,
                        "repetition_penalty": repetition_penalty,
                        "no_repeat_ngram_size": no_repeat_ngram_size,
                    },
                )
                created += 1
            except Exception as e:
                print(f"  [skip] {src.name} v{k}: {type(e).__name__}: {e}")

    elapsed = time.time() - t0
    print(f"\nCreated {created} variations in {elapsed:.1f}s")
    log_event(
        {
            "step": "generate",
            "cycle": cycle,
            "sources": len(sources),
            "variants_per_song": variants_per_song,
            "created": created,
            "elapsed_sec": round(elapsed, 1),
        }
    )
    return created


# ---------------------------------------------------------------------------
# Step 2 — Review
# ---------------------------------------------------------------------------
def step_review(cycle: int) -> dict:
    """Run the reviewer on every pending MIDI in output/.

    Returns aggregate stats: total, by_grade.
    """
    banner(f"Cycle {cycle} — STEP 2: reviewer auto-scoring")

    from agents import reviewer

    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    pending = reviewer.list_pending()
    if not pending:
        print("[WARN] no pending MIDIs for review")
        return {"total": 0}

    grades = {"A": 0, "B": 0, "C": 0, "D": 0}
    total_score = 0.0
    n = 0

    for fp in pending:
        try:
            review = reviewer.review_midi(fp)
            score = float(review.get("avg_score", 0.0))
            total_score += score
            n += 1
            if score >= 80:
                grades["A"] += 1
            elif score >= 60:
                grades["B"] += 1
            elif score >= 40:
                grades["C"] += 1
            else:
                grades["D"] += 1
        except Exception as e:
            print(f"  [skip review] {fp}: {type(e).__name__}: {e}")

    avg = total_score / n if n else 0.0
    print(f"\nReviewed: {n} files")
    print(f"  Avg score: {avg:.1f}/100")
    print(f"  Grade A (chosen): {grades['A']}")
    print(f"  Grade B: {grades['B']}")
    print(f"  Grade C: {grades['C']}")
    print(f"  Grade D (rejected): {grades['D']}")

    summary = {
        "step": "review",
        "cycle": cycle,
        "total": n,
        "avg_score": round(avg, 1),
        "grades": grades,
    }
    log_event(summary)
    return summary


# ---------------------------------------------------------------------------
# Step 3 — Build DPO pairs
# ---------------------------------------------------------------------------
def step_build_pairs(cycle: int) -> int:
    """Run midigpt.build_dpo_pairs as a subprocess and report pair count."""
    banner(f"Cycle {cycle} — STEP 3: build DPO pairs")

    DPO_PAIRS_DIR.mkdir(parents=True, exist_ok=True)
    before = len(list(DPO_PAIRS_DIR.glob("*.json")))

    cmd = [sys.executable, "-m", "midigpt.build_dpo_pairs"]
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        print(f"[FAIL] build_dpo_pairs exit {result.returncode}")
        log_event({"step": "build_pairs", "cycle": cycle, "status": "fail"})
        return 0

    after = len(list(DPO_PAIRS_DIR.glob("*.json")))
    new_pairs = after - before
    print(f"\nNew DPO pairs: {new_pairs}  (total {after})")
    log_event(
        {
            "step": "build_pairs",
            "cycle": cycle,
            "new_pairs": new_pairs,
            "total_pairs": after,
        }
    )
    return new_pairs


# ---------------------------------------------------------------------------
# Step 4 — DPO training
# ---------------------------------------------------------------------------
def step_train_dpo(
    cycle: int,
    base_model: str,
    epochs: int,
    batch_size: int,
    min_pairs: int,
) -> bool:
    """Run midigpt.training.train_dpo as a subprocess."""
    banner(f"Cycle {cycle} — STEP 4: DPO fine-tune")

    pairs = list(DPO_PAIRS_DIR.glob("*.json"))
    if len(pairs) < min_pairs:
        print(
            f"[SKIP] only {len(pairs)} pairs (need >= {min_pairs}). "
            "Generate more variations or relax the score threshold."
        )
        log_event(
            {
                "step": "train_dpo",
                "cycle": cycle,
                "status": "skipped",
                "reason": "insufficient_pairs",
                "pair_count": len(pairs),
            }
        )
        return False

    LORA_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "midigpt.training.train_dpo",
        "--base_model",
        base_model,
        "--data_dir",
        str(DPO_PAIRS_DIR),
        "--output_dir",
        str(LORA_DIR),
        "--epochs",
        str(epochs),
        "--batch_size",
        str(batch_size),
    ]
    print(" ".join(cmd))
    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    elapsed = time.time() - t0

    ok = result.returncode == 0
    log_event(
        {
            "step": "train_dpo",
            "cycle": cycle,
            "status": "ok" if ok else "fail",
            "elapsed_sec": round(elapsed, 1),
            "epochs": epochs,
            "batch_size": batch_size,
            "pair_count": len(pairs),
        }
    )
    if not ok:
        print(f"[FAIL] train_dpo exit {result.returncode}")
    else:
        print(f"\nDPO done in {elapsed/60:.1f} min")
    return ok


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="MidiGPT self-improvement loop")
    parser.add_argument(
        "--base_model",
        type=str,
        default="./checkpoints/midigpt_ema.pt",
        help="Path to base model checkpoint (EMA recommended).",
    )
    parser.add_argument("--midi_dir", type=str, default="./midi_data")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--variants_per_song", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of source MIDIs per cycle (debugging).")
    parser.add_argument("--max_tokens", type=int, default=1024,
                        help="Hard ceiling on tokens generated per variation.")
    parser.add_argument("--min_new_tokens", type=int, default=256,
                        help="EOS suppression floor (BUG 4/5 fix). Set 0 to "
                             "disable. Default 256 produces ~30s+ MIDIs.")
    parser.add_argument("--temperature", type=float, default=1.2,
                        help="Sampling temperature. Bumped from 0.9 -> 1.2 per "
                             "the BUG 5 report — overfit base models collapse "
                             "to a few tokens at low temperature. Harmonic "
                             "constraint already masks off-scale pitches, so "
                             "1.2 is safe here even though it would be high "
                             "for an unconstrained LM.")
    parser.add_argument("--repetition_penalty", type=float, default=1.1)
    parser.add_argument("--no_repeat_ngram_size", type=int, default=4)
    parser.add_argument("--dpo_epochs", type=int, default=3)
    parser.add_argument("--dpo_batch_size", type=int, default=4)
    parser.add_argument("--min_pairs", type=int, default=10,
                        help="Skip DPO step until this many pairs accumulate.")
    args = parser.parse_args()

    midi_dir = Path(args.midi_dir).resolve()
    if not midi_dir.exists():
        print(f"[FAIL] midi_dir does not exist: {midi_dir}")
        return 1

    print("MidiGPT self-improvement loop")
    print(f"  base_model       : {args.base_model}")
    print(f"  midi_dir         : {midi_dir}")
    print(f"  cycles           : {args.cycles}")
    print(f"  variants_per_song: {args.variants_per_song}")

    log_event({"step": "loop_start", "args": vars(args)})

    for cycle in range(1, args.cycles + 1):
        created = step_generate(
            base_model=args.base_model,
            midi_dir=midi_dir,
            cycle=cycle,
            variants_per_song=args.variants_per_song,
            max_tokens=args.max_tokens,
            min_new_tokens=args.min_new_tokens,
            temperature=args.temperature,
            repetition_penalty=args.repetition_penalty,
            no_repeat_ngram_size=args.no_repeat_ngram_size,
            limit=args.limit,
        )
        if created == 0:
            print("[STOP] no variations created — aborting loop")
            return 1

        step_review(cycle)
        new_pairs = step_build_pairs(cycle)

        if new_pairs == 0:
            print("[WARN] no new pairs this cycle (no clear chosen/rejected split)")

        step_train_dpo(
            cycle=cycle,
            base_model=args.base_model,
            epochs=args.dpo_epochs,
            batch_size=args.dpo_batch_size,
            min_pairs=args.min_pairs,
        )

    banner("loop complete")
    print(f"Log: {LOG_PATH}")
    print()
    print("⚠️  Reminder: the reviewer is rule-based. Run human listening")
    print("   checks before starting another loop. Over-cycling against")
    print("   the auto-reviewer will overfit to its rules.")

    log_event({"step": "loop_end"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
