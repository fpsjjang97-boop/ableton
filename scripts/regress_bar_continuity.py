"""Bar-continuity regression test — measures Type 1 (gap) and Type 2 (loop)
symptoms on generated MIDI output.

Non-GPU, non-model regression: runs on already-generated .mid files and
emits a per-file + aggregate report. Intended workflow:

    1. Partner retrains the model with the new SFT pairs.
    2. Partner (or tester) generates N sample .mid files into a directory.
    3. Run this script against that directory → numeric acceptance.

Metrics (per-file):
    - empty_bar_ratio: empty bars / total bar span. Type 1 indicator.
    - bar_jump_max: largest gap between consecutive non-empty bars.
    - bar_loop_notes: max notes emitted in a single bar × track slot.
      Very high value + near-identical positions = Type 2 (bar loop).
    - duplicate_note_count: identical (bar, start, track, pitch) tuples.

Thresholds (defaults chosen from 7차 analysis; tune with --thresh-*):
    - empty_bar_ratio < 0.05      → PASS for Type 1
    - bar_jump_max     <= 1        → PASS for Type 1 (FSM-enforced)
    - bar_loop_notes   < 128       → PASS for Type 2 (heuristic)
    - duplicate_note_count == 0    → PASS for dedup invariant

Usage:
    python scripts/regress_bar_continuity.py ./output/
    python scripts/regress_bar_continuity.py ./output/ --json report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import pretty_midi
except ImportError:
    print("Error: pretty_midi required. Run: pip install pretty_midi")
    sys.exit(1)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


@dataclass
class FileMetrics:
    path: str
    note_count: int
    total_bars: int
    occupied_bars: int
    empty_bars: int
    empty_bar_ratio: float
    bar_jump_max: int
    bar_loop_notes: int
    duplicate_note_count: int


def analyze_midi(midi_path: Path, bar_seconds_fallback: float = 2.0) -> FileMetrics:
    """Compute bar-continuity metrics for one MIDI file.

    A bar is considered "occupied" if at least one note starts within it
    (not merely sustained across it). This matches the tokenizer's Bar_N
    emission rule — the decoder writes a Bar_N token only when notes start
    in bar N — so empty_bar_ratio here is directly comparable to how many
    Bar tokens the model emitted with no following notes.
    """
    pm = pretty_midi.PrettyMIDI(str(midi_path))

    # Resolve bar duration from tempo. PrettyMIDI returns (times, bpms).
    tempos = pm.get_tempo_changes()
    tempo = tempos[1][0] if len(tempos[1]) > 0 else 120.0
    bar_duration = (60.0 / max(tempo, 1e-3)) * 4  # 4/4 assumption (matches encoder)
    if bar_duration <= 0:
        bar_duration = bar_seconds_fallback

    all_notes = []
    for inst in pm.instruments:
        track = inst.name or ("drums" if inst.is_drum else f"prog_{inst.program}")
        for n in inst.notes:
            all_notes.append((n.start, n.pitch, track))

    note_count = len(all_notes)
    if note_count == 0:
        return FileMetrics(
            path=str(midi_path), note_count=0, total_bars=0,
            occupied_bars=0, empty_bars=0, empty_bar_ratio=0.0,
            bar_jump_max=0, bar_loop_notes=0, duplicate_note_count=0,
        )

    # Bar index for each note (by start time).
    bar_of = [int(s / bar_duration) for s, _, _ in all_notes]
    min_bar = min(bar_of)
    max_bar = max(bar_of)
    total_bars = max_bar - min_bar + 1

    occupied = set(bar_of)
    occupied_bars = len(occupied)
    empty_bars = total_bars - occupied_bars
    empty_bar_ratio = empty_bars / total_bars if total_bars > 0 else 0.0

    # Largest gap between consecutive occupied bars (indicates the "Bar_3
    # Bar_5" jump the tester reported).
    sorted_occ = sorted(occupied)
    bar_jump_max = 0
    for a, b in zip(sorted_occ, sorted_occ[1:]):
        bar_jump_max = max(bar_jump_max, b - a - 1)

    # Notes per (bar, track) — very high concentration = likely Type 2 loop.
    slot_notes = Counter((b, t) for b, (_s, _p, t) in zip(bar_of, all_notes))
    bar_loop_notes = max(slot_notes.values()) if slot_notes else 0

    # Duplicate (bar, start, track, pitch) — identical onsets with same
    # pitch on the same track. A quantised perfect duplicate is the
    # 6차 "Cubase 두 겹" symptom.
    keys = Counter(
        (b, round(s, 4), t, p)
        for b, (s, p, t) in zip(bar_of, all_notes)
    )
    duplicate_note_count = sum(c - 1 for c in keys.values() if c > 1)

    return FileMetrics(
        path=str(midi_path),
        note_count=note_count,
        total_bars=total_bars,
        occupied_bars=occupied_bars,
        empty_bars=empty_bars,
        empty_bar_ratio=round(empty_bar_ratio, 4),
        bar_jump_max=bar_jump_max,
        bar_loop_notes=bar_loop_notes,
        duplicate_note_count=duplicate_note_count,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("midi_dir", type=str,
                        help="Directory (or single .mid file) to analyze")
    parser.add_argument("--json", type=str, default=None,
                        help="Write full report to this path")
    parser.add_argument("--thresh-empty", type=float, default=0.05)
    parser.add_argument("--thresh-jump", type=int, default=1)
    parser.add_argument("--thresh-loop", type=int, default=128)
    parser.add_argument("--thresh-dup", type=int, default=0)
    args = parser.parse_args()

    target = Path(args.midi_dir)
    if target.is_file():
        files = [target]
    else:
        files = sorted(
            list(target.rglob("*.mid")) + list(target.rglob("*.midi"))
        )

    if not files:
        print(f"No MIDI files found under {target}")
        return 2

    results: list[FileMetrics] = []
    for f in files:
        try:
            m = analyze_midi(f)
        except (OSError, ValueError, IndexError, KeyError) as e:
            print(f"  [WARN] Cannot analyze {f.name}: {e}")
            continue
        results.append(m)

    # Aggregate
    if not results:
        print("All files failed to parse.")
        return 2

    agg_empty = sum(r.empty_bar_ratio for r in results) / len(results)
    agg_jump = max(r.bar_jump_max for r in results)
    agg_loop = max(r.bar_loop_notes for r in results)
    agg_dup = sum(r.duplicate_note_count for r in results)

    pass_empty = agg_empty <= args.thresh_empty
    pass_jump = agg_jump <= args.thresh_jump
    pass_loop = agg_loop < args.thresh_loop
    pass_dup = agg_dup <= args.thresh_dup
    all_pass = pass_empty and pass_jump and pass_loop and pass_dup

    print("=" * 64)
    print(f"Bar-continuity regression: {len(results)} file(s) analyzed")
    print("=" * 64)
    print(f"  avg empty_bar_ratio    : {agg_empty:.4f}  "
          f"{'PASS' if pass_empty else 'FAIL'}  (thresh <= {args.thresh_empty})")
    print(f"  max bar_jump           : {agg_jump}       "
          f"{'PASS' if pass_jump else 'FAIL'}  (thresh <= {args.thresh_jump})")
    print(f"  max bar_loop_notes     : {agg_loop}       "
          f"{'PASS' if pass_loop else 'FAIL'}  (thresh <  {args.thresh_loop})")
    print(f"  total duplicate_notes  : {agg_dup}       "
          f"{'PASS' if pass_dup else 'FAIL'}  (thresh <= {args.thresh_dup})")
    print("=" * 64)
    print(f"Overall: {'PASS' if all_pass else 'FAIL'}")

    if args.json:
        report = {
            "files": [asdict(r) for r in results],
            "aggregate": {
                "avg_empty_bar_ratio": agg_empty,
                "max_bar_jump": agg_jump,
                "max_bar_loop_notes": agg_loop,
                "total_duplicate_notes": agg_dup,
            },
            "thresholds": {
                "empty": args.thresh_empty,
                "jump": args.thresh_jump,
                "loop": args.thresh_loop,
                "dup": args.thresh_dup,
            },
            "pass": all_pass,
        }
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print(f"Report written to {args.json}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
