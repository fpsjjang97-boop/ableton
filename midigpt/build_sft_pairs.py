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
from midigpt.tokenizer.vocab import VOCAB, NUM_BARS


# ---------------------------------------------------------------------------
# Pair length guard (7차 리포트 대응)
# ---------------------------------------------------------------------------
# Upper bound on (input + SEP + output) token count. Pairs above this are
# skipped at generation time instead of being produced and then dropped by
# dataset.py's ``truncated-too-much`` filter (which silently throws away
# 66% of 7차 pairs because the encoder emits full-song token sequences
# longer than block_size=2048).
#
# Default = 2040: block_size(2048) - SEP(1) - safety margin(7).
DEFAULT_MAX_PAIR_TOKENS = 2040

# Bar-window chunking defaults for the continuation strategy.
# Windowed pairs replace "split the whole song at 25/50/75%" which
# guaranteed truncation for any MIDI whose full tokenisation exceeded
# block_size.
DEFAULT_WINDOW_BARS = 16
DEFAULT_STRIDE_BARS = 8
DEFAULT_MIN_WINDOW_BARS = 8
DEFAULT_MAX_PAIRS_PER_FILE = 50


def _pair_fits(
    input_ids: list[int],
    output_ids: list[int],
    max_pair_tokens: int,
) -> bool:
    """Return True iff the concatenated pair (input + SEP + output) fits."""
    return len(input_ids) + 1 + len(output_ids) <= max_pair_tokens


# ---------------------------------------------------------------------------
# Strategy 1: Continuation — bar-window sliding + in-window split
# ---------------------------------------------------------------------------
def _build_continuation_pairs(
    midi_path: Path,
    encoder: MidiEncoder,
    window_bars: int = DEFAULT_WINDOW_BARS,
    stride_bars: int = DEFAULT_STRIDE_BARS,
    split_ratios: list[float] = [0.25, 0.50, 0.75],
    min_window_bars: int = DEFAULT_MIN_WINDOW_BARS,
    max_pair_tokens: int = DEFAULT_MAX_PAIR_TOKENS,
    max_pairs_per_file: int = DEFAULT_MAX_PAIRS_PER_FILE,
    skip_counter: dict | None = None,
) -> list[dict]:
    """Slide a bar-window over the MIDI and split each window into a pair.

    Replaces the pre-7차 "split the whole song at 25/50/75%" which for any
    long MIDI (>~32 bars of dense tracks) produced pairs whose combined
    token length exceeded ``block_size``, causing dataset.py to silently
    drop 66% of them as ``truncated-too-much`` (7차 SFT load:
    171 ok / 336 dropped).

    Design notes:
    - **Absolute Bar numbers are preserved in the output half.** The output
      PrettyMIDI is NOT time-rebased to 0 — so tokenization emits
      ``Bar_{split_bar}`` right after SEP, which matches what the inference
      FSM's ``current_bar`` tracker expects (monotonic forward progression
      across the SEP boundary). This removes a training/inference
      distribution mismatch that was a secondary contributor to the
      bar-jump gap symptom.
    - Windowed pairs are short by construction (at most ``window_bars``
      bars ≈ a few hundred to ~2k tokens), so they fit in block_size.
    - Each skip reason is counted in ``skip_counter`` so pipeline summary
      can show *why* pairs were dropped — rules/05 패턴 G (no silent drops).

    Args:
        window_bars:        Upper bound on window size in bars.
        stride_bars:        Step between windows (50% overlap default).
        split_ratios:       Split points inside each window (relative).
        min_window_bars:    Minimum window size; shorter songs fall through.
        max_pair_tokens:    Reject pairs whose (input+SEP+output) exceeds.
        max_pairs_per_file: Hard cap per source MIDI.
        skip_counter:       Dict to accumulate {length, empty, tokenize}
                            skip counts. Created if None.
    """
    if skip_counter is None:
        skip_counter = {"length": 0, "empty": 0, "tokenize": 0}

    pairs: list[dict] = []

    try:
        pm = pretty_midi.PrettyMIDI(str(midi_path))
    except (OSError, ValueError, IndexError) as e:
        print(f"  [WARN] Cannot load {midi_path.name}: {e}")
        return []

    meta = encoder._estimate_meta(pm)
    tempo = meta.tempo if meta.tempo > 0 else 120.0
    bar_duration = (60.0 / tempo) * 4

    # Total bars in the piece, clamped to vocab limit (Bar_0..Bar_63).
    max_end = max(
        (note.end for inst in pm.instruments for note in inst.notes),
        default=0.0,
    )
    total_bars = min(int(max_end / bar_duration) + 1, NUM_BARS)

    if total_bars < min_window_bars:
        return []

    # Sliding windows over [0, total_bars).
    w_start = 0
    while w_start < total_bars:
        if len(pairs) >= max_pairs_per_file:
            break

        w_end = min(w_start + window_bars, total_bars, NUM_BARS)
        if w_end - w_start < min_window_bars:
            break

        for ratio in split_ratios:
            if len(pairs) >= max_pairs_per_file:
                break

            split_bar = w_start + max(1, int((w_end - w_start) * ratio))
            if split_bar <= w_start or split_bar >= w_end:
                continue

            split_time = split_bar * bar_duration
            w_start_time = w_start * bar_duration
            w_end_time = w_end * bar_duration

            # Input: notes in [w_start, split_bar). NO time rebase.
            pm_input = copy.deepcopy(pm)
            for inst in pm_input.instruments:
                inst.notes = [
                    n for n in inst.notes
                    if n.start < split_time and n.end > w_start_time
                ]
                for n in inst.notes:
                    n.start = max(n.start, w_start_time)
                    n.end = min(n.end, split_time)

            # Output: notes in [split_bar, w_end). NO time rebase —
            # encoder emits Bar_{split_bar}.. absolute bar tokens, which
            # matches the inference FSM's expected continuous progression.
            pm_output = copy.deepcopy(pm)
            for inst in pm_output.instruments:
                inst.notes = [
                    n for n in inst.notes
                    if n.start < w_end_time and n.end > split_time
                ]
                for n in inst.notes:
                    n.start = max(n.start, split_time)
                    n.end = min(n.end, w_end_time)

            if not any(inst.notes for inst in pm_input.instruments):
                skip_counter["empty"] += 1
                continue
            if not any(inst.notes for inst in pm_output.instruments):
                skip_counter["empty"] += 1
                continue

            # Tokenize with max_bars=w_end so Bar_{w_start}..Bar_{w_end-1}
            # are the only Bar tokens emitted (earlier bars have no notes
            # after the window filter and are skipped by the encoder).
            try:
                input_ids = encoder.encode_pretty_midi(
                    pm_input, meta=meta, max_bars=w_end,
                )
                output_ids = encoder.encode_pretty_midi(
                    pm_output, meta=meta, max_bars=w_end,
                )
            except (IndexError, ValueError, KeyError) as e:
                skip_counter["tokenize"] += 1
                continue

            if len(input_ids) < 10 or len(output_ids) < 10:
                skip_counter["empty"] += 1
                continue

            # Strip BOS from output; EOS from input (SEP replaces it).
            if output_ids and output_ids[0] == VOCAB.bos_id:
                output_ids = output_ids[1:]
            if input_ids and input_ids[-1] == VOCAB.eos_id:
                input_ids = input_ids[:-1]

            if not _pair_fits(input_ids, output_ids, max_pair_tokens):
                skip_counter["length"] += 1
                continue

            pairs.append({
                "input": input_ids,
                "output": output_ids,
                "metadata": {
                    "strategy": "continuation",
                    "source": midi_path.name,
                    "window_start_bar": w_start,
                    "window_end_bar": w_end,
                    "split_bar": split_bar,
                    "split_ratio": ratio,
                    "input_tokens": len(input_ids),
                    "output_tokens": len(output_ids),
                }
            })

        w_start += stride_bars

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
    max_pair_tokens: int = DEFAULT_MAX_PAIR_TOKENS,
    skip_counter: dict | None = None,
) -> list[dict]:
    """Pair original MIDI with its augmented versions.

    Looks for augmented files matching the pattern: {stem}_trans+*.mid,
    {stem}_veljit.mid, {stem}_tstretch.mid, etc.
    """
    if rng is None:
        rng = random.Random(42)
    if skip_counter is None:
        skip_counter = {"length": 0, "empty": 0, "tokenize": 0}

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
    except (OSError, ValueError, IndexError, KeyError) as e:
        print(f"  [WARN] Cannot tokenize original {original_path.name}: {e}")
        skip_counter["tokenize"] += 1
        return []

    if len(input_ids) < 10:
        return []

    for aug_path in selected:
        try:
            output_ids = encoder.encode_file(str(aug_path))
        except (OSError, ValueError, IndexError, KeyError):
            skip_counter["tokenize"] += 1
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

        if not _pair_fits(clean_input, clean_output, max_pair_tokens):
            skip_counter["length"] += 1
            continue

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
    max_pair_tokens: int = DEFAULT_MAX_PAIR_TOKENS,
    skip_counter: dict | None = None,
) -> list[dict]:
    """Create pairs where input has fewer tracks than output.

    Input = subset of tracks (e.g., just melody+drums),
    Output = full arrangement.
    """
    if rng is None:
        rng = random.Random(42)
    if skip_counter is None:
        skip_counter = {"length": 0, "empty": 0, "tokenize": 0}

    pairs = []

    try:
        pm = pretty_midi.PrettyMIDI(str(midi_path))
    except (OSError, ValueError, IndexError):
        return []

    if len(pm.instruments) < 3:
        return []  # Need at least 3 tracks for meaningful completion

    # Tokenize full arrangement (= output)
    try:
        full_ids = encoder.encode_file(str(midi_path))
    except (OSError, ValueError, IndexError, KeyError):
        skip_counter["tokenize"] += 1
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
        except (IndexError, ValueError, KeyError):
            skip_counter["tokenize"] += 1
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

        if not _pair_fits(clean_input, clean_output, max_pair_tokens):
            skip_counter["length"] += 1
            continue

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
    window_bars: int = DEFAULT_WINDOW_BARS,
    stride_bars: int = DEFAULT_STRIDE_BARS,
    max_pair_tokens: int = DEFAULT_MAX_PAIR_TOKENS,
    max_pairs_per_file: int = DEFAULT_MAX_PAIRS_PER_FILE,
) -> dict:
    """Build all SFT pairs from MIDI files.

    Args:
        midi_dir: Directory with original MIDI files.
        output_dir: Where to save SFT JSON pairs.
        augmented_dir: Directory with augmented MIDI files (for variation strategy).
        strategies: List of strategies to use. Default: all.
        seed: Random seed.
        window_bars: Bar-window size for continuation strategy chunking.
        stride_bars: Step between continuation windows.
        max_pair_tokens: Reject any pair whose (input+SEP+output) exceeds this.
        max_pairs_per_file: Hard cap on continuation pairs per source MIDI.

    Returns:
        Summary dict with counts and drop-reason breakdown.
    """
    if strategies is None:
        strategies = ["continuation", "variation", "track_completion"]

    rng = random.Random(seed)
    encoder = MidiEncoder()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Aggregate skip counters across all strategies — surfaced in summary so
    # we never silently drop pairs (rules/05 패턴 G).
    skip_counter = {"length": 0, "empty": 0, "tokenize": 0}

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
            pairs = _build_continuation_pairs(
                midi_path, encoder,
                window_bars=window_bars,
                stride_bars=stride_bars,
                max_pair_tokens=max_pair_tokens,
                max_pairs_per_file=max_pairs_per_file,
                skip_counter=skip_counter,
            )
            file_pairs.extend(pairs)
            strategy_counts["continuation"] += len(pairs)

        if "variation" in strategies and augmented_dir:
            pairs = _build_variation_pairs(
                midi_path, augmented_dir, encoder, rng=file_rng,
                max_pair_tokens=max_pair_tokens,
                skip_counter=skip_counter,
            )
            file_pairs.extend(pairs)
            strategy_counts["variation"] += len(pairs)

        if "track_completion" in strategies:
            pairs = _build_track_completion_pairs(
                midi_path, encoder, rng=file_rng,
                max_pair_tokens=max_pair_tokens,
                skip_counter=skip_counter,
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

    # Summary — include drop-reason breakdown so the partner can tell why
    # a given configuration produced fewer pairs than expected (rules/05 G).
    summary = {
        "total_pairs": len(all_pairs),
        "strategy_counts": strategy_counts,
        "source_files": len(original_files),
        "output_dir": str(output_dir),
        "skip_counts": skip_counter,
        "config": {
            "window_bars": window_bars,
            "stride_bars": stride_bars,
            "max_pair_tokens": max_pair_tokens,
            "max_pairs_per_file": max_pairs_per_file,
        },
    }

    summary_path = output_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print(f"Total SFT pairs: {len(all_pairs)}")
    for strategy, count in strategy_counts.items():
        print(f"  {strategy}: {count}")
    total_skips = sum(skip_counter.values())
    if total_skips:
        print(f"Skipped at build time: {total_skips} "
              f"(length={skip_counter['length']}, "
              f"empty={skip_counter['empty']}, "
              f"tokenize={skip_counter['tokenize']})")
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
    parser.add_argument("--window_bars", type=int, default=DEFAULT_WINDOW_BARS,
                        help="Bar-window size for continuation strategy")
    parser.add_argument("--stride_bars", type=int, default=DEFAULT_STRIDE_BARS,
                        help="Stride between continuation windows")
    parser.add_argument("--max_pair_tokens", type=int,
                        default=DEFAULT_MAX_PAIR_TOKENS,
                        help="Drop pairs whose (input+SEP+output) exceeds this")
    parser.add_argument("--max_pairs_per_file", type=int,
                        default=DEFAULT_MAX_PAIRS_PER_FILE,
                        help="Hard cap on continuation pairs per source MIDI")

    args = parser.parse_args()

    strategies = [s.strip() for s in args.strategies.split(",")]
    aug_dir = Path(args.augmented_dir) if args.augmented_dir else None

    build_sft_pairs(
        midi_dir=Path(args.midi_dir),
        output_dir=Path(args.output_dir),
        augmented_dir=aug_dir,
        strategies=strategies,
        seed=args.seed,
        window_bars=args.window_bars,
        stride_bars=args.stride_bars,
        max_pair_tokens=args.max_pair_tokens,
        max_pairs_per_file=args.max_pairs_per_file,
    )


if __name__ == "__main__":
    main()
