"""
MIDI Dataset Quality Filter — for Lakh MIDI / GiantMIDI / external datasets.

Filters MIDI files based on musical quality heuristics and copies passing
files into an output directory ready for augmentation + training.

Usage:
    python scripts/filter_midi_dataset.py \
        --input_dir ./lakh_midi_clean \
        --output_dir ./midi_data \
        --min_tracks 2 \
        --min_notes 50 \
        --max_notes 50000 \
        --min_duration 10 \
        --max_duration 600 \
        --require_polyphonic

Filters (all configurable):
    1. Track count (default >= 2)
    2. Note count range (too sparse or too dense)
    3. Duration range (too short or too long)
    4. Time signature consistency (reject mixed meters by default)
    5. Polyphonic requirement (reject single-note sequences)
    6. Note density (notes per second within sane range)
    7. Parse-ability (skip corrupt / unreadable MIDI)

2026-04-10 — Phase 2 roadmap item.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field

try:
    import pretty_midi
except ImportError:
    print("Error: pretty_midi required.  pip install pretty_midi")
    sys.exit(1)


@dataclass
class FilterStats:
    total: int = 0
    passed: int = 0
    fail_parse: int = 0
    fail_tracks: int = 0
    fail_notes: int = 0
    fail_duration: int = 0
    fail_density: int = 0
    fail_time_sig: int = 0
    fail_polyphonic: int = 0

    def summary(self) -> str:
        lines = [
            f"Total scanned:    {self.total}",
            f"Passed:           {self.passed} ({self.passed/max(1,self.total)*100:.1f}%)",
            f"---",
            f"Fail parse:       {self.fail_parse}",
            f"Fail tracks:      {self.fail_tracks}",
            f"Fail notes:       {self.fail_notes}",
            f"Fail duration:    {self.fail_duration}",
            f"Fail density:     {self.fail_density}",
            f"Fail time_sig:    {self.fail_time_sig}",
            f"Fail polyphonic:  {self.fail_polyphonic}",
        ]
        return "\n".join(lines)


def check_midi(
    path: Path,
    min_tracks: int,
    min_notes: int,
    max_notes: int,
    min_duration: float,
    max_duration: float,
    min_density: float,
    max_density: float,
    require_consistent_time_sig: bool,
    require_polyphonic: bool,
    stats: FilterStats,
) -> bool:
    """Return True if the MIDI file passes all quality checks."""
    stats.total += 1

    # 1. Parse
    try:
        pm = pretty_midi.PrettyMIDI(str(path))
    except Exception:
        stats.fail_parse += 1
        return False

    # 2. Track count (non-empty instruments only)
    non_empty = [inst for inst in pm.instruments if len(inst.notes) > 0]
    if len(non_empty) < min_tracks:
        stats.fail_tracks += 1
        return False

    # 3. Total note count
    total_notes = sum(len(inst.notes) for inst in pm.instruments)
    if total_notes < min_notes or total_notes > max_notes:
        stats.fail_notes += 1
        return False

    # 4. Duration
    duration = pm.get_end_time()
    if duration < min_duration or duration > max_duration:
        stats.fail_duration += 1
        return False

    # 5. Note density (notes per second)
    density = total_notes / max(0.1, duration)
    if density < min_density or density > max_density:
        stats.fail_density += 1
        return False

    # 6. Time signature consistency
    if require_consistent_time_sig:
        time_sigs = pm.time_signature_changes
        if len(time_sigs) > 1:
            # Check if all time signatures are the same
            first = (time_sigs[0].numerator, time_sigs[0].denominator)
            if any((ts.numerator, ts.denominator) != first for ts in time_sigs[1:]):
                stats.fail_time_sig += 1
                return False

    # 7. Polyphonic check (at least one instrument with overlapping notes)
    if require_polyphonic:
        is_poly = False
        for inst in non_empty:
            if inst.is_drum:
                continue
            sorted_notes = sorted(inst.notes, key=lambda n: n.start)
            for i in range(len(sorted_notes) - 1):
                if sorted_notes[i].end > sorted_notes[i + 1].start:
                    is_poly = True
                    break
            if is_poly:
                break
        if not is_poly and len(non_empty) < 2:
            stats.fail_polyphonic += 1
            return False

    stats.passed += 1
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Filter MIDI dataset by quality heuristics"
    )
    parser.add_argument("--input_dir", type=str, required=True,
                        help="Source directory with MIDI files (searched recursively)")
    parser.add_argument("--output_dir", type=str, required=True,
                        help="Output directory for passing files")

    # Thresholds
    parser.add_argument("--min_tracks", type=int, default=2,
                        help="Minimum non-empty instrument tracks (default: 2)")
    parser.add_argument("--min_notes", type=int, default=50,
                        help="Minimum total notes (default: 50)")
    parser.add_argument("--max_notes", type=int, default=50000,
                        help="Maximum total notes (default: 50000)")
    parser.add_argument("--min_duration", type=float, default=10.0,
                        help="Minimum duration in seconds (default: 10)")
    parser.add_argument("--max_duration", type=float, default=600.0,
                        help="Maximum duration in seconds (default: 600)")
    parser.add_argument("--min_density", type=float, default=0.5,
                        help="Minimum notes/second (default: 0.5)")
    parser.add_argument("--max_density", type=float, default=200.0,
                        help="Maximum notes/second (default: 200)")
    parser.add_argument("--require_consistent_time_sig", action="store_true", default=True,
                        help="Reject files with mixed time signatures (default: True)")
    parser.add_argument("--allow_mixed_time_sig", action="store_true", default=False,
                        help="Allow mixed time signatures")
    parser.add_argument("--require_polyphonic", action="store_true", default=False,
                        help="Require at least one polyphonic track or multiple tracks")

    # Behavior
    parser.add_argument("--copy", action="store_true", default=True,
                        help="Copy files (default). Use --symlink for symlinks")
    parser.add_argument("--symlink", action="store_true", default=False,
                        help="Create symlinks instead of copying")
    parser.add_argument("--dry_run", action="store_true", default=False,
                        help="Only report stats, don't copy")

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"Error: input directory not found: {input_dir}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Find MIDI files
    midi_files = sorted(
        list(input_dir.rglob("*.mid")) + list(input_dir.rglob("*.midi"))
    )
    if not midi_files:
        print(f"No MIDI files found in {input_dir}")
        sys.exit(1)

    consistent_ts = args.require_consistent_time_sig and not args.allow_mixed_time_sig

    print(f"Scanning {len(midi_files)} MIDI files from {input_dir}")
    print(f"Filters: tracks>={args.min_tracks}, notes=[{args.min_notes},{args.max_notes}], "
          f"duration=[{args.min_duration}s,{args.max_duration}s], "
          f"density=[{args.min_density},{args.max_density}] n/s")
    print(f"Consistent time sig: {consistent_ts}, Polyphonic: {args.require_polyphonic}")
    print("=" * 60)

    stats = FilterStats()
    start = time.time()

    for i, path in enumerate(midi_files):
        passed = check_midi(
            path=path,
            min_tracks=args.min_tracks,
            min_notes=args.min_notes,
            max_notes=args.max_notes,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
            min_density=args.min_density,
            max_density=args.max_density,
            require_consistent_time_sig=consistent_ts,
            require_polyphonic=args.require_polyphonic,
            stats=stats,
        )

        if passed and not args.dry_run:
            dest = output_dir / path.name
            # Handle name collisions
            if dest.exists():
                dest = output_dir / f"{path.stem}_{i}{path.suffix}"
            if args.symlink:
                dest.symlink_to(path.resolve())
            else:
                shutil.copy2(path, dest)

        if (i + 1) % 1000 == 0:
            print(f"  [{i+1}/{len(midi_files)}] passed={stats.passed}")

    elapsed = time.time() - start

    print("=" * 60)
    print(stats.summary())
    print(f"\nTime: {elapsed:.1f}s ({len(midi_files)/max(0.1,elapsed):.0f} files/s)")
    if not args.dry_run:
        print(f"Output: {output_dir} ({stats.passed} files)")
    else:
        print("(dry run — no files copied)")


if __name__ == "__main__":
    main()
