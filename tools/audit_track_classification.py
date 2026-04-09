"""
Track Classification Audit
==========================

Runs :meth:`MidiEncoder._classify_track` against every MIDI file in
``midi_data/`` (or a user-specified directory) and reports the resulting
category distribution + a per-file per-track table.

Usage:
    python tools/audit_track_classification.py                     # default: ./midi_data
    python tools/audit_track_classification.py --dir ./midi_data   # explicit
    python tools/audit_track_classification.py --dir ./midi_data --verbose
    python tools/audit_track_classification.py --csv report.csv    # save table

What this is for
----------------
The 2026-04-09 BUG 6 investigation showed that the original
``_classify_track`` collapsed guitar / strings / brass / woodwind / vocal
tracks into 2-3 categories (mostly ``accomp`` and ``pad``), starving the
model of track diversity. After applying the classifier fix, this tool
verifies that the training data now maps to a realistic category spread.

Target distribution (rough guide for the user's 54-song seed):
    accomp (keys/piano)  ≥ 15%
    bass                 ≥ 10%
    drums                ≥ 10%
    guitar               ≥ 10%
    strings              ≥  8%
    pad / lead / brass / woodwind / vocal / melody / arp / fx   variable
    other                ≤  5%        ← high 'other' = classifier still leaking
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    import pretty_midi
except ImportError:
    print("ERROR: pretty_midi required.  pip install pretty_midi")
    sys.exit(1)

from midigpt.tokenizer.vocab import VOCAB
from midigpt.tokenizer.encoder import MidiEncoder


def audit_directory(midi_dir: Path, verbose: bool = False, csv_path: Path | None = None):
    encoder = MidiEncoder(VOCAB)

    midi_files = sorted(midi_dir.glob("*.mid")) + sorted(midi_dir.glob("*.midi"))
    if not midi_files:
        print(f"[!] No MIDI files found in {midi_dir}")
        return

    print(f"[audit] Scanning {len(midi_files)} MIDI files in {midi_dir}")
    print()

    category_counts: Counter[str] = Counter()
    per_file: dict[str, list[tuple[str, str, int, int]]] = defaultdict(list)
    #         file_name → [(track_name, category, program, num_notes), ...]
    total_tracks = 0

    for mf in midi_files:
        try:
            pm = pretty_midi.PrettyMIDI(str(mf))
        except Exception as e:
            print(f"[skip] {mf.name}: {e}")
            continue

        for inst in pm.instruments:
            if inst.is_drum:
                category = "drums"
            else:
                category = encoder._classify_track(inst)

            category_counts[category] += 1
            total_tracks += 1
            per_file[mf.name].append(
                (inst.name or "<unnamed>", category, inst.program, len(inst.notes))
            )

    # ---- Summary ----
    print("=" * 70)
    print("CATEGORY DISTRIBUTION")
    print("=" * 70)
    print(f"{'category':<12} {'count':>8} {'percent':>10}")
    print("-" * 70)
    for cat, count in category_counts.most_common():
        pct = 100.0 * count / total_tracks if total_tracks else 0
        print(f"{cat:<12} {count:>8} {pct:>9.1f}%")
    print("-" * 70)
    print(f"{'TOTAL':<12} {total_tracks:>8} {100.0:>9.1f}%")
    print()

    # ---- Sanity checks ----
    accomp_pct = 100.0 * category_counts.get("accomp", 0) / total_tracks if total_tracks else 0
    other_pct  = 100.0 * category_counts.get("other", 0)  / total_tracks if total_tracks else 0
    distinct_cats = sum(1 for v in category_counts.values() if v > 0)

    print("=" * 70)
    print("SANITY CHECKS")
    print("=" * 70)

    # ASCII-only flags so Windows CP949 console does not crash on Unicode
    flag = lambda ok: "[OK] " if ok else "[FAIL]"

    ok1 = accomp_pct < 60
    print(f"  {flag(ok1)} accomp < 60%      currently {accomp_pct:.1f}% "
          f"(high = classifier fallback leaking)")

    ok2 = other_pct < 10
    print(f"  {flag(ok2)} other  < 10%      currently {other_pct:.1f}% "
          f"(high = unknown instruments escaping table)")

    ok3 = distinct_cats >= 6
    print(f"  {flag(ok3)} >= 6 distinct     currently {distinct_cats} categories used "
          f"(too few = no track diversity signal for model)")

    if ok1 and ok2 and ok3:
        print("\n  [PASS] Track classification looks healthy. Safe to re-tokenise.")
    else:
        print("\n  [FAIL] Distribution still unhealthy. Inspect per-file details.")

    # ---- Per-file detail ----
    if verbose:
        print()
        print("=" * 70)
        print("PER-FILE DETAIL")
        print("=" * 70)
        for fname, tracks in per_file.items():
            print(f"\n{fname}")
            for tname, cat, prog, nnotes in tracks:
                print(f"    [{cat:<10}] prog={prog:>3}  notes={nnotes:>5}  {tname}")

    # ---- CSV export ----
    if csv_path is not None:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["file", "track_name", "category", "program", "num_notes"])
            for fname, tracks in per_file.items():
                for tname, cat, prog, nnotes in tracks:
                    writer.writerow([fname, tname, cat, prog, nnotes])
        print(f"\n[ok] CSV written: {csv_path}")


def main():
    ap = argparse.ArgumentParser(description="Audit MIDI track classification")
    ap.add_argument("--dir", type=str, default="./midi_data",
                    help="Directory of MIDI files (default: ./midi_data)")
    ap.add_argument("--verbose", action="store_true",
                    help="Print per-file track details")
    ap.add_argument("--csv", type=str, default=None,
                    help="Write full table to CSV file")
    args = ap.parse_args()

    midi_dir = Path(args.dir)
    if not midi_dir.exists():
        print(f"[!] Directory not found: {midi_dir}")
        sys.exit(1)

    audit_directory(
        midi_dir,
        verbose=args.verbose,
        csv_path=Path(args.csv) if args.csv else None,
    )


if __name__ == "__main__":
    main()
