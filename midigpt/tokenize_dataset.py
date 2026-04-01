"""
Batch MIDI Tokenization Script — Converts a folder of MIDI files to token arrays.

Usage:
    python -m midigpt.tokenize_dataset \
        --input_dir ./midi_data \
        --output_dir ./midigpt_data \
        --workers 4

Output structure:
    output_dir/
        tokens/
            000_filename.npy    # token ID arrays
            001_filename.npy
            ...
        metadata.json           # file list and stats
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def tokenize_single(args_tuple):
    """Tokenize a single MIDI file (runs in subprocess)."""
    midi_path, output_path, idx = args_tuple

    # Import inside subprocess to avoid pickling issues
    from midigpt.tokenizer.encoder import MidiEncoder
    from midigpt.tokenizer.vocab import VOCAB

    encoder = MidiEncoder(VOCAB)

    try:
        token_ids = encoder.encode_file(str(midi_path))

        if len(token_ids) < 10:
            return {
                "status": "skipped",
                "file": str(midi_path),
                "reason": "too few tokens",
            }

        np.save(str(output_path), np.array(token_ids, dtype=np.int64))

        return {
            "status": "ok",
            "file": str(midi_path),
            "output": str(output_path),
            "num_tokens": len(token_ids),
        }

    except Exception as e:
        return {
            "status": "error",
            "file": str(midi_path),
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="Batch MIDI Tokenization")
    parser.add_argument("--input_dir", type=str, required=True, help="Directory containing MIDI files")
    parser.add_argument("--output_dir", type=str, required=True, help="Output directory for token arrays")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--recursive", action="store_true", default=True, help="Search subdirectories")

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    token_dir = output_dir / "tokens"
    token_dir.mkdir(parents=True, exist_ok=True)

    # Find all MIDI files
    if args.recursive:
        midi_files = sorted(list(input_dir.rglob("*.mid")) + list(input_dir.rglob("*.midi")))
    else:
        midi_files = sorted(list(input_dir.glob("*.mid")) + list(input_dir.glob("*.midi")))

    if not midi_files:
        print(f"No MIDI files found in {input_dir}")
        return

    print(f"Found {len(midi_files)} MIDI files in {input_dir}")
    print(f"Output: {token_dir}")
    print(f"Workers: {args.workers}")
    print("=" * 60)

    # Prepare tasks
    tasks = []
    for idx, midi_path in enumerate(midi_files):
        safe_name = midi_path.stem.replace(" ", "_")[:50]
        output_path = token_dir / f"{idx:04d}_{safe_name}.npy"
        tasks.append((midi_path, output_path, idx))

    # Process
    start_time = time.time()
    results = {"ok": 0, "skipped": 0, "error": 0}
    total_tokens = 0
    metadata_entries = []

    if args.workers <= 1:
        # Single-process (easier to debug)
        for task in tasks:
            result = tokenize_single(task)
            results[result["status"]] += 1
            if result["status"] == "ok":
                total_tokens += result["num_tokens"]
                metadata_entries.append(result)
            print(f"  [{results['ok']}/{len(tasks)}] {Path(result['file']).name} → {result['status']}", end="")
            if result["status"] == "ok":
                print(f" ({result['num_tokens']} tokens)")
            elif result["status"] == "error":
                print(f" ({result.get('error', '')})")
            else:
                print()
    else:
        # Multi-process
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(tokenize_single, task): task for task in tasks}
            for future in as_completed(futures):
                result = future.result()
                results[result["status"]] += 1
                if result["status"] == "ok":
                    total_tokens += result["num_tokens"]
                    metadata_entries.append(result)

                done = sum(results.values())
                print(f"  [{done}/{len(tasks)}] {Path(result['file']).name} → {result['status']}", end="")
                if result["status"] == "ok":
                    print(f" ({result['num_tokens']} tokens)")
                elif result["status"] == "error":
                    print(f" ({result.get('error', '')})")
                else:
                    print()

    # Save metadata
    elapsed = time.time() - start_time
    metadata = {
        "total_files": len(midi_files),
        "tokenized": results["ok"],
        "skipped": results["skipped"],
        "errors": results["error"],
        "total_tokens": total_tokens,
        "avg_tokens_per_file": total_tokens // max(results["ok"], 1),
        "elapsed_seconds": round(elapsed, 1),
        "files": metadata_entries,
    }

    with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print(f"Done! {results['ok']}/{len(midi_files)} files tokenized")
    print(f"Total tokens: {total_tokens:,}")
    print(f"Average tokens/file: {total_tokens // max(results['ok'], 1):,}")
    print(f"Time: {elapsed:.1f}s")
    print(f"Metadata: {output_dir / 'metadata.json'}")

    if results["error"] > 0:
        print(f"\nWarning: {results['error']} files had errors")


if __name__ == "__main__":
    main()
