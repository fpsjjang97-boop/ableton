"""
Build SFT Training Pairs from MIDI Files
==========================================
Generates input→output pairs for Supervised Fine-Tuning.
Each pair is stored as JSON: {"input": [token_ids], "output": [token_ids]}

The SEP token (id=3) is inserted between input and output during training
(see dataset.py _get_sft), so we do NOT include it here.

SFT Strategies:
  1. **Continuation**: Split a song at a bar boundary.
     Input = first N bars, Output = remaining bars.
     Teaches the model to continue music given a prompt.

  2. **Variation**: Original = input, augmented version = output.
     Teaches the model to produce stylistic variations.

  3. **Track Completion**: Subset of tracks = input, full = output.
     Teaches the model to fill in missing instrument parts.

Usage:
    python -m midigpt.build_sft_pairs \
        --midi_dir ./midi_data \
        --augmented_dir ./midigpt_pipeline/augmented \
        --output_dir ./midigpt_data/sft \
        --strategies continuation,variation

    # Or use the pipeline (recommended):
    python -m midigpt.pipeline --midi_dir ./midi_data --epochs 10
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    import pretty_midi
except ImportError:
    print("Error: pretty_midi required. Run: pip install pretty_midi")
    sys.exit(1)

from midigpt.tokenizer.encoder import MidiEncoder, SongMeta
from midigpt.tokenizer.vocab import VOCAB


# ---------------------------------------------------------------------------
# Strategy 1: Continuation — split at bar boundary
# ---------------------------------------------------------------------------
def _build_continuation_pairs(
    midi_path: Path,
    encoder: MidiEncoder,
    split_ratios: list[float] = [0.25, 0.50, 0.75],
    min_input_bars: int = 4,
    min_output_bars: int = 4,
) -> list[dict]:
    """Split a MIDI file at bar boundaries to create continuation pairs.

    For each split_ratio, create a pair where:
      input  = first  (ratio * total_bars) bars
      output = remaining bars
    """
    pairs = []

    try:
        pm = pretty_midi.PrettyMIDI(str(midi_path))
    except Exception as e:
        print(f"  [WARN] Cannot load {midi_path.name}: {e}")
        return []

    meta = encoder._estimate_meta(pm)
    tempo = meta.tempo if meta.tempo > 0 else 120.0
    beat_duration = 60.0 / tempo
    bar_duration = beat_duration * 4

    # Find total bars
    max_end = 0.0
    for inst in pm.instruments:
        for note in inst.notes:
            max_end = max(max_end, note.end)
    total_bars = int(max_end / bar_duration) + 1

    if total_bars < min_input_bars + min_output_bars:
        return []

    for ratio in split_ratios:
        split_bar = max(min_input_bars, int(total_bars * ratio))
        if total_bars - split_bar < min_output_bars:
            continue

        split_time = split_bar * bar_duration

        # Build input MIDI (first half)
        pm_input = copy.deepcopy(pm)
        for inst in pm_input.instruments:
            inst.notes = [n for n in inst.notes if n.start < split_time]
            # Trim notes that extend past the split
            for n in inst.notes:
                n.end = min(n.end, split_time)

        # Build output MIDI (second half, time-shifted to start at 0)
        pm_output = copy.deepcopy(pm)
        for inst in pm_output.instruments:
            inst.notes = [n for n in inst.notes if n.end > split_time]
            for n in inst.notes:
                n.start = max(0.0, n.start - split_time)
                n.end = n.end - split_time

        # Tokenize both halves
        try:
            input_ids = encoder.encode_pretty_midi(
                pm_input, meta=meta, max_bars=split_bar,
            )
            output_ids = encoder.encode_pretty_midi(
                pm_output, meta=meta, max_bars=total_bars - split_bar,
            )
        except Exception as e:
            print(f"  [WARN] Tokenization failed for {midi_path.name} at ratio {ratio}: {e}")
            continue

        # Validate: both sides need meaningful content
        if len(input_ids) < 10 or len(output_ids) < 10:
            continue

        # Strip BOS/EOS from output (dataset.py adds SEP between input and output,
        # and the combined sequence already has BOS from input)
        if output_ids and output_ids[0] == VOCAB.bos_id:
            output_ids = output_ids[1:]
        # Keep EOS at the end of output (marks end of generation)

        # Strip EOS from input (SEP will replace it)
        if input_ids and input_ids[-1] == VOCAB.eos_id:
            input_ids = input_ids[:-1]

        pairs.append({
            "input": input_ids,
            "output": output_ids,
            "metadata": {
                "strategy": "continuation",
                "source": midi_path.name,
                "split_ratio": ratio,
                "split_bar": split_bar,
                "total_bars": total_bars,
                "input_tokens": len(input_ids),
                "output_tokens": len(output_ids),
            }
        })

    return pairs


# ---------------------------------------------------------------------------
# Strategy 2: Variation — original → augmented
# ---------------------------------------------------------------------------
def _build_variation_pairs(
    original_path: Path,
    augmented_dir: Path,
    encoder: MidiEncoder,
    max_variations: int = 3,
    rng: random.Random | None = None,
) -> list[dict]:
    """Pair original MIDI with its augmented versions.

    Looks for augmented files matching the pattern: {stem}_trans+*.mid,
    {stem}_veljit.mid, {stem}_tstretch.mid, etc.
    """
    if rng is None:
        rng = random.Random(42)

    pairs = []
    stem = original_path.stem

    if not augmented_dir.exists():
        return []

    # Find augmented versions of this file
    augmented_files = sorted(augmented_dir.glob(f"{stem}_*.mid"))
    if not augmented_files:
        return []

    # Prefer transpositions and velocity jitter (most musically meaningful)
    trans_files = [f for f in augmented_files if "_trans+" in f.name]
    other_files = [f for f in augmented_files if "_trans+" not in f.name]

    # Select a diverse subset
    selected = []
    if trans_files:
        selected.extend(rng.sample(trans_files, min(2, len(trans_files))))
    if other_files:
        selected.extend(rng.sample(other_files, min(1, len(other_files))))
    selected = selected[:max_variations]

    # Tokenize original
    try:
        input_ids = encoder.encode_file(str(original_path))
    except Exception as e:
        print(f"  [WARN] Cannot tokenize original {original_path.name}: {e}")
        return []

    if len(input_ids) < 10:
        return []

    for aug_path in selected:
        try:
            output_ids = encoder.encode_file(str(aug_path))
        except Exception as e:
            continue

        if len(output_ids) < 10:
            continue

        # Strip BOS from output, EOS from input
        clean_input = input_ids[:]
        clean_output = output_ids[:]

        if clean_output and clean_output[0] == VOCAB.bos_id:
            clean_output = clean_output[1:]
        if clean_input and clean_input[-1] == VOCAB.eos_id:
            clean_input = clean_input[:-1]

        pairs.append({
            "input": clean_input,
            "output": clean_output,
            "metadata": {
                "strategy": "variation",
                "source": original_path.name,
                "augmented": aug_path.name,
                "input_tokens": len(clean_input),
                "output_tokens": len(clean_output),
            }
        })

    return pairs


# ---------------------------------------------------------------------------
# Strategy 3: Track Completion — partial tracks → full
# ---------------------------------------------------------------------------
def _build_track_completion_pairs(
    midi_path: Path,
    encoder: MidiEncoder,
    rng: random.Random | None = None,
    max_pairs: int = 2,
) -> list[dict]:
    """Create pairs where input has fewer tracks than output.

    Input = subset of tracks (e.g., just melody+drums),
    Output = full arrangement.
    """
    if rng is None:
        rng = random.Random(42)

    pairs = []

    try:
        pm = pretty_midi.PrettyMIDI(str(midi_path))
    except Exception:
        return []

    if len(pm.instruments) < 3:
        return []  # Need at least 3 tracks for meaningful completion

    # Tokenize full arrangement (= output)
    try:
        full_ids = encoder.encode_file(str(midi_path))
    except Exception:
        return []

    if len(full_ids) < 10:
        return []

    for _ in range(max_pairs):
        # Keep 1-2 tracks for input, rest is what model should generate
        n_keep = rng.randint(1, max(1, len(pm.instruments) // 2))
        keep_indices = set(rng.sample(range(len(pm.instruments)), n_keep))

        pm_partial = copy.deepcopy(pm)
        pm_partial.instruments = [
            inst for idx, inst in enumerate(pm_partial.instruments)
            if idx in keep_indices
        ]

        # Check that partial still has notes
        if not any(inst.notes for inst in pm_partial.instruments):
            continue

        try:
            partial_ids = encoder.encode_pretty_midi(pm_partial)
        except Exception:
            continue

        if len(partial_ids) < 10:
            continue

        # Strip BOS from output, EOS from input
        clean_input = partial_ids[:]
        clean_output = full_ids[:]

        if clean_output and clean_output[0] == VOCAB.bos_id:
            clean_output = clean_output[1:]
        if clean_input and clean_input[-1] == VOCAB.eos_id:
            clean_input = clean_input[:-1]

        kept_names = [pm.instruments[i].name or f"track_{i}" for i in sorted(keep_indices)]

        pairs.append({
            "input": clean_input,
            "output": clean_output,
            "metadata": {
                "strategy": "track_completion",
                "source": midi_path.name,
                "kept_tracks": kept_names,
                "kept_count": n_keep,
                "total_tracks": len(pm.instruments),
                "input_tokens": len(clean_input),
                "output_tokens": len(clean_output),
            }
        })

    return pairs


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def build_sft_pairs(
    midi_dir: Path,
    output_dir: Path,
    augmented_dir: Path | None = None,
    strategies: list[str] | None = None,
    seed: int = 42,
) -> dict:
    """Build all SFT pairs from MIDI files.

    Args:
        midi_dir: Directory with original MIDI files.
        output_dir: Where to save SFT JSON pairs.
        augmented_dir: Directory with augmented MIDI files (for variation strategy).
        strategies: List of strategies to use. Default: all.
        seed: Random seed.

    Returns:
        Summary dict with counts.
    """
    if strategies is None:
        strategies = ["continuation", "variation", "track_completion"]

    rng = random.Random(seed)
    encoder = MidiEncoder()
    output_dir.mkdir(parents=True, exist_ok=True)

    midi_files = sorted(
        list(midi_dir.rglob("*.mid")) + list(midi_dir.rglob("*.midi"))
    )

    # Filter out augmented files if midi_dir contains them
    original_files = [f for f in midi_files if not any(
        tag in f.name for tag in ("_trans+", "_drop_", "_veljit", "_tstretch",
                                   "_tshuffle", "_original")
    )]
    if not original_files:
        original_files = midi_files  # fallback: use all files

    print(f"Found {len(original_files)} original MIDI files")
    print(f"Strategies: {', '.join(strategies)}")
    print(f"Output: {output_dir}")
    print("=" * 60)

    all_pairs: list[dict] = []
    strategy_counts = {s: 0 for s in strategies}

    for idx, midi_path in enumerate(original_files):
        file_rng = random.Random(seed + idx)
        file_pairs = []

        if "continuation" in strategies:
            pairs = _build_continuation_pairs(midi_path, encoder)
            file_pairs.extend(pairs)
            strategy_counts["continuation"] += len(pairs)

        if "variation" in strategies and augmented_dir:
            pairs = _build_variation_pairs(
                midi_path, augmented_dir, encoder, rng=file_rng,
            )
            file_pairs.extend(pairs)
            strategy_counts["variation"] += len(pairs)

        if "track_completion" in strategies:
            pairs = _build_track_completion_pairs(
                midi_path, encoder, rng=file_rng,
            )
            file_pairs.extend(pairs)
            strategy_counts["track_completion"] += len(pairs)

        all_pairs.extend(file_pairs)
        status = f"{len(file_pairs)} pairs" if file_pairs else "skipped"
        print(f"  [{idx+1}/{len(original_files)}] {midi_path.name} → {status}")

    # Save pairs
    print(f"\nSaving {len(all_pairs)} SFT pairs...")
    for pair_idx, pair in enumerate(all_pairs):
        out_path = output_dir / f"sft_{pair_idx:04d}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(pair, f, ensure_ascii=False)

    # Summary
    summary = {
        "total_pairs": len(all_pairs),
        "strategy_counts": strategy_counts,
        "source_files": len(original_files),
        "output_dir": str(output_dir),
    }

    summary_path = output_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print(f"Total SFT pairs: {len(all_pairs)}")
    for strategy, count in strategy_counts.items():
        print(f"  {strategy}: {count}")
    print(f"Saved to: {output_dir}")

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Build SFT training pairs from MIDI files"
    )
    parser.add_argument("--midi_dir", type=str, required=True,
                        help="Directory containing original MIDI files")
    parser.add_argument("--augmented_dir", type=str, default=None,
                        help="Directory with augmented files (for variation strategy)")
    parser.add_argument("--output_dir", type=str, default="./midigpt_data/sft",
                        help="Output directory for SFT JSON pairs")
    parser.add_argument("--strategies", type=str,
                        default="continuation,variation,track_completion",
                        help="Comma-separated strategies to use")
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    strategies = [s.strip() for s in args.strategies.split(",")]
    aug_dir = Path(args.augmented_dir) if args.augmented_dir else None

    build_sft_pairs(
        midi_dir=Path(args.midi_dir),
        output_dir=Path(args.output_dir),
        augmented_dir=aug_dir,
        strategies=strategies,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
