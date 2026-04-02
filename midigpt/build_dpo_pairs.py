"""
Build DPO Training Pairs from Reviewer Scores
================================================
Scans reviewed MIDI files, categorises them by reviewer score into
"chosen" (grade A, avg_score >= 80) and "rejected" (grade C/D, avg_score < 60),
then pairs them by similar musical characteristics (key, tempo range) and
tokenises each pair into the DPO format expected by MidiDataset.

Output format (per JSON file in midigpt/dpo_pairs/):
    {
        "prompt":   [<metadata token IDs>],
        "chosen":   [<token IDs for high-score MIDI>],
        "rejected": [<token IDs for low-score MIDI>],
        "metadata": { ... pairing details ... }
    }

Usage:
    python -m midigpt.build_dpo_pairs            # scan + build all
    python -m midigpt.build_dpo_pairs --dry-run   # report only, no file writes
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent        # D:/Ableton
REVIEW_DIR = REPO_ROOT / "reviews"
REVIEWED_DIR = REPO_ROOT / "reviewed"
OUTPUT_DIR = REPO_ROOT / "output"
DPO_OUTPUT_DIR = Path(__file__).resolve().parent / "dpo_pairs"

# Ensure imports work regardless of CWD
sys.path.insert(0, str(REPO_ROOT))

from midigpt.tokenizer.encoder import MidiEncoder, SongMeta
from midigpt.tokenizer.vocab import VOCAB

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
CHOSEN_THRESHOLD = 80       # avg_score >= 80 -> grade A (chosen)
REJECTED_THRESHOLD = 60     # avg_score <  60 -> grade C/D (rejected)
TEMPO_TOLERANCE = 30        # BPM range for "similar tempo"


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------
@dataclass
class ReviewedMidi:
    """Holds a review record plus the resolved path to its MIDI file."""
    review_path: str
    review: dict
    midi_path: Optional[str] = None
    avg_score: float = 0.0
    key: str = "C"
    tempo: float = 120.0
    category: str = ""          # "chosen" | "rejected" | "neutral"

    @property
    def filename(self) -> str:
        return self.review.get("file", "")


# ---------------------------------------------------------------------------
# 1. Scan & collect reviews
# ---------------------------------------------------------------------------
def _resolve_midi_path(review: dict) -> Optional[str]:
    """Try to locate the actual .mid file referenced by a review JSON.

    Search order:
      1. output/<filename>
      2. reviewed/originals/<filename>
      3. reviewed/variations/<filename>
    """
    filename = review.get("file", "")
    if not filename:
        return None

    candidates = [
        OUTPUT_DIR / filename,
        REVIEWED_DIR / "originals" / filename,
        REVIEWED_DIR / "variations" / filename,
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def _estimate_key_from_review(review: dict) -> str:
    """Best-effort extraction of the musical key from review data or filename."""
    filename = review.get("file", "")

    # Try to pull the key from the filename (e.g. "composed_A#_minor_...")
    match = re.search(r"composed_([A-G]#?)_", filename)
    if match:
        return match.group(1)

    # Fallback: look inside any associated metadata
    return "C"


def _estimate_tempo_from_review(review: dict) -> float:
    """Best-effort extraction of tempo from review data or filename."""
    filename = review.get("file", "")

    # Filename convention:  ..._120bpm_...
    match = re.search(r"(\d+)bpm", filename)
    if match:
        return float(match.group(1))

    # Compute a rough proxy from duration & total notes if possible
    dur = review.get("duration", 0)
    total_notes = review.get("total_notes", 0)
    if dur > 0 and total_notes > 10:
        # Very rough: notes per second -> guess BPM
        nps = total_notes / dur
        # Assume ~4 notes per beat on average
        return max(40.0, min(240.0, nps * 60 / 4))

    return 120.0


def collect_reviews() -> list[ReviewedMidi]:
    """Scan reviews/ and reviewed/metadata/ directories and collect all review records."""
    items: list[ReviewedMidi] = []

    # --- reviews/ directory (produced by reviewer.py) ---
    if REVIEW_DIR.exists():
        for jf in sorted(REVIEW_DIR.glob("*.json")):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    review = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  [WARN] skipping {jf.name}: {exc}")
                continue

            midi_path = _resolve_midi_path(review)
            avg_score = review.get("avg_score", 0.0)
            key = _estimate_key_from_review(review)
            tempo = _estimate_tempo_from_review(review)

            if avg_score >= CHOSEN_THRESHOLD:
                category = "chosen"
            elif avg_score < REJECTED_THRESHOLD:
                category = "rejected"
            else:
                category = "neutral"

            items.append(ReviewedMidi(
                review_path=str(jf),
                review=review,
                midi_path=midi_path,
                avg_score=avg_score,
                key=key,
                tempo=tempo,
                category=category,
            ))

    # --- reviewed/metadata/ (pair metadata with quality_score) ---
    meta_dir = REVIEWED_DIR / "metadata"
    if meta_dir.exists():
        for jf in sorted(meta_dir.glob("*.json")):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  [WARN] skipping {jf.name}: {exc}")
                continue

            # These metadata files describe original/variation pairs.
            # Extract each sub-entry that has a quality_score.
            for sub_key in ("original", "variation"):
                sub = meta.get(sub_key)
                if not sub or sub.get("quality_score") is None:
                    continue

                midi_rel = sub.get("midi_file", "")
                midi_abs = REVIEWED_DIR / midi_rel if midi_rel else None
                midi_path = str(midi_abs) if midi_abs and midi_abs.exists() else None

                score = float(sub["quality_score"])
                mkey = sub.get("key", "C")
                mtempo = sub.get("tempo", 120.0)

                if score >= CHOSEN_THRESHOLD:
                    cat = "chosen"
                elif score < REJECTED_THRESHOLD:
                    cat = "rejected"
                else:
                    cat = "neutral"

                items.append(ReviewedMidi(
                    review_path=str(jf),
                    review={"file": os.path.basename(midi_rel), "avg_score": score},
                    midi_path=midi_path,
                    avg_score=score,
                    key=mkey,
                    tempo=mtempo,
                    category=cat,
                ))

    return items


# ---------------------------------------------------------------------------
# 2. Pair chosen + rejected by similar characteristics
# ---------------------------------------------------------------------------
def _keys_compatible(k1: str, k2: str) -> bool:
    """Check if two keys are the same root (ignoring major/minor suffix)."""
    # Normalise: strip trailing 'm' to compare roots
    root1 = k1.rstrip("m")
    root2 = k2.rstrip("m")
    return root1 == root2


def build_pairs(
    items: list[ReviewedMidi],
) -> list[tuple[ReviewedMidi, ReviewedMidi]]:
    """Pair chosen and rejected MIDIs that share similar characteristics.

    Matching criteria (in priority order):
      1. Same key root
      2. Tempo within TEMPO_TOLERANCE BPM

    Each MIDI file is used in at most one pair to avoid data leakage.
    """
    chosen = [r for r in items if r.category == "chosen" and r.midi_path]
    rejected = [r for r in items if r.category == "rejected" and r.midi_path]

    if not chosen:
        print("[INFO] No chosen candidates (avg_score >= 80 with valid MIDI path).")
        return []
    if not rejected:
        print("[INFO] No rejected candidates (avg_score < 60 with valid MIDI path).")
        return []

    # Sort by score descending / ascending for best pairing
    chosen.sort(key=lambda r: -r.avg_score)
    rejected.sort(key=lambda r: r.avg_score)

    pairs: list[tuple[ReviewedMidi, ReviewedMidi]] = []
    used_rejected: set[str] = set()

    for c in chosen:
        best_rej: Optional[ReviewedMidi] = None
        best_distance: float = float("inf")

        for r in rejected:
            if r.review_path in used_rejected:
                continue
            # Same key preferred
            if not _keys_compatible(c.key, r.key):
                continue
            # Tempo within tolerance
            tempo_diff = abs(c.tempo - r.tempo)
            if tempo_diff > TEMPO_TOLERANCE:
                continue
            if tempo_diff < best_distance:
                best_distance = tempo_diff
                best_rej = r

        # Second pass: relax key constraint if no match found
        if best_rej is None:
            for r in rejected:
                if r.review_path in used_rejected:
                    continue
                tempo_diff = abs(c.tempo - r.tempo)
                if tempo_diff > TEMPO_TOLERANCE * 2:
                    continue
                if tempo_diff < best_distance:
                    best_distance = tempo_diff
                    best_rej = r

        if best_rej is not None:
            pairs.append((c, best_rej))
            used_rejected.add(best_rej.review_path)

    return pairs


# ---------------------------------------------------------------------------
# 3. Tokenize and produce DPO JSON files
# ---------------------------------------------------------------------------
def _build_prompt_tokens(chosen: ReviewedMidi, rejected: ReviewedMidi) -> list[int]:
    """Build shared prompt (metadata) tokens for a DPO pair.

    The prompt encodes the shared musical context that both chosen and rejected
    MIDIs were generated under.
    """
    key = chosen.key or "C"
    tempo = chosen.tempo or 120.0

    tokens: list[str] = ["<BOS>"]

    key_token = f"Key_{key}" if f"Key_{key}" in VOCAB else "Key_C"
    tokens.append(key_token)

    tempo_bin = MidiEncoder._quantize_tempo(tempo)
    tokens.append(f"Tempo_{tempo_bin}")

    return VOCAB.encode_tokens(tokens)


def tokenize_midi(midi_path: str, encoder: MidiEncoder) -> Optional[list[int]]:
    """Tokenize a MIDI file, returning None on failure."""
    try:
        token_ids = encoder.encode_file(midi_path)
        if len(token_ids) < 3:
            print(f"  [WARN] Tokenization too short ({len(token_ids)} tokens): {midi_path}")
            return None
        return token_ids
    except Exception as exc:
        print(f"  [ERR]  Tokenization failed for {midi_path}: {exc}")
        return None


def save_dpo_pairs(
    pairs: list[tuple[ReviewedMidi, ReviewedMidi]],
    dry_run: bool = False,
) -> int:
    """Tokenize each pair and write DPO JSON files.

    Returns:
        Number of pairs successfully saved.
    """
    encoder = MidiEncoder()

    if not dry_run:
        DPO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    saved = 0
    for idx, (chosen_item, rejected_item) in enumerate(pairs):
        print(f"\n  Pair {idx + 1}/{len(pairs)}: "
              f"chosen={chosen_item.filename} (score={chosen_item.avg_score:.1f}) | "
              f"rejected={rejected_item.filename} (score={rejected_item.avg_score:.1f})")

        chosen_tokens = tokenize_midi(chosen_item.midi_path, encoder)
        if chosen_tokens is None:
            continue

        rejected_tokens = tokenize_midi(rejected_item.midi_path, encoder)
        if rejected_tokens is None:
            continue

        prompt_tokens = _build_prompt_tokens(chosen_item, rejected_item)

        dpo_record = {
            "prompt": prompt_tokens,
            "chosen": chosen_tokens,
            "rejected": rejected_tokens,
            "metadata": {
                "pair_id": f"dpo_{idx:04d}",
                "chosen_file": chosen_item.filename,
                "chosen_score": chosen_item.avg_score,
                "chosen_key": chosen_item.key,
                "chosen_tempo": chosen_item.tempo,
                "rejected_file": rejected_item.filename,
                "rejected_score": rejected_item.avg_score,
                "rejected_key": rejected_item.key,
                "rejected_tempo": rejected_item.tempo,
                "created_at": datetime.now().isoformat(),
            },
        }

        if not dry_run:
            out_path = DPO_OUTPUT_DIR / f"dpo_{idx:04d}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(dpo_record, f, indent=2, ensure_ascii=False)
            print(f"    -> saved {out_path.name}")

        saved += 1

    return saved


# ---------------------------------------------------------------------------
# 4. Summary report
# ---------------------------------------------------------------------------
def print_summary(
    items: list[ReviewedMidi],
    pairs: list[tuple[ReviewedMidi, ReviewedMidi]],
    saved_count: int,
):
    """Print a summary of the DPO pair building process."""
    chosen = [r for r in items if r.category == "chosen"]
    rejected = [r for r in items if r.category == "rejected"]
    neutral = [r for r in items if r.category == "neutral"]

    chosen_with_midi = [r for r in chosen if r.midi_path]
    rejected_with_midi = [r for r in rejected if r.midi_path]

    print("\n" + "=" * 60)
    print("DPO Pair Building Summary")
    print("=" * 60)
    print(f"\nTotal reviews scanned:    {len(items)}")
    print(f"  Chosen  (score >= {CHOSEN_THRESHOLD}): {len(chosen):3d}  "
          f"(with MIDI: {len(chosen_with_midi)})")
    print(f"  Rejected (score < {REJECTED_THRESHOLD}): {len(rejected):3d}  "
          f"(with MIDI: {len(rejected_with_midi)})")
    print(f"  Neutral ({REJECTED_THRESHOLD} <= score < {CHOSEN_THRESHOLD}): "
          f"{len(neutral):3d}")

    print(f"\nPairs matched:            {len(pairs)}")
    print(f"Pairs saved (tokenized):  {saved_count}")

    if items:
        scores = [r.avg_score for r in items]
        print(f"\nScore distribution:")
        print(f"  Min:    {min(scores):.1f}")
        print(f"  Max:    {max(scores):.1f}")
        print(f"  Mean:   {sum(scores) / len(scores):.1f}")

        # Histogram buckets
        buckets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
        for s in scores:
            if s < 20:
                buckets["0-20"] += 1
            elif s < 40:
                buckets["20-40"] += 1
            elif s < 60:
                buckets["40-60"] += 1
            elif s < 80:
                buckets["60-80"] += 1
            else:
                buckets["80-100"] += 1

        print(f"  Buckets:")
        for label, count in buckets.items():
            bar = "#" * count
            print(f"    {label:>6s}: {bar} ({count})")

    # Save summary JSON alongside the pairs
    summary = {
        "created_at": datetime.now().isoformat(),
        "total_reviews": len(items),
        "chosen_count": len(chosen),
        "rejected_count": len(rejected),
        "neutral_count": len(neutral),
        "pairs_matched": len(pairs),
        "pairs_saved": saved_count,
        "chosen_threshold": CHOSEN_THRESHOLD,
        "rejected_threshold": REJECTED_THRESHOLD,
        "tempo_tolerance": TEMPO_TOLERANCE,
        "score_distribution": {
            "min": min((r.avg_score for r in items), default=0),
            "max": max((r.avg_score for r in items), default=0),
            "mean": (sum(r.avg_score for r in items) / len(items)) if items else 0,
        },
    }
    if DPO_OUTPUT_DIR.exists():
        summary_path = DPO_OUTPUT_DIR / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\nSummary saved to {summary_path}")

    print("=" * 60)
    return summary


# ---------------------------------------------------------------------------
# 5. Main entry point (also used by reviewer.export_for_dpo)
# ---------------------------------------------------------------------------
def run(dry_run: bool = False) -> dict:
    """Full pipeline: collect -> pair -> tokenize -> save.

    Returns:
        Summary dict with counts.
    """
    print("=" * 60)
    print("DPO Pair Builder")
    print("=" * 60)

    # Step 1: Collect all reviews
    print("\n[1/4] Scanning reviews...")
    items = collect_reviews()
    print(f"  Found {len(items)} review records.")

    if not items:
        print("  No reviews found. Nothing to do.")
        return {"total_reviews": 0, "pairs_matched": 0, "pairs_saved": 0}

    for item in items:
        midi_status = "OK" if item.midi_path else "MISSING"
        print(f"    {item.category:>8s}  score={item.avg_score:5.1f}  "
              f"key={item.key:<3s}  tempo={item.tempo:5.1f}  "
              f"midi={midi_status}  {item.filename}")

    # Step 2: Build pairs
    print("\n[2/4] Building chosen/rejected pairs...")
    pairs = build_pairs(items)
    print(f"  Matched {len(pairs)} pairs.")

    if not pairs:
        print("  Cannot create DPO pairs. Check that you have both chosen and "
              "rejected MIDIs with valid file paths.")
        summary = print_summary(items, pairs, 0)
        return summary

    # Step 3: Tokenize & save
    print(f"\n[3/4] Tokenizing and saving pairs{' (dry run)' if dry_run else ''}...")
    saved = save_dpo_pairs(pairs, dry_run=dry_run)

    # Step 4: Summary
    print("\n[4/4] Summary")
    summary = print_summary(items, pairs, saved)

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Build DPO training pairs from reviewer scores"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only, do not write DPO JSON files",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
