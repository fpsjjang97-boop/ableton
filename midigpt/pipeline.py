"""
MidiGPT Full Pipeline — Augment → Tokenize → Train in one command.

Usage:
    python -m midigpt.pipeline --midi_dir ./midi_data --epochs 10

Steps:
    1. Augment:  MIDI files → transposed + dropout variants
    2. Tokenize: All MIDI (original + augmented) → .npy token arrays
    3. Train:    Token arrays → MidiGPT pre-training

All intermediate outputs go into --work_dir (default: ./midigpt_pipeline/).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def run_step(name: str, cmd: list[str]) -> bool:
    """Run a subprocess step. Returns True on success."""
    print(f"\n{'='*60}")
    print(f"  STEP: {name}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, cwd=str(REPO_ROOT))

    if result.returncode != 0:
        print(f"\n[ERROR] {name} failed (exit code {result.returncode})")
        return False

    print(f"\n[OK] {name} complete")
    return True


def main():
    parser = argparse.ArgumentParser(description="MidiGPT Full Pipeline")

    # Input
    parser.add_argument("--midi_dir", type=str, required=True,
                        help="Directory containing original MIDI files")

    # Work directory (intermediate files)
    parser.add_argument("--work_dir", type=str, default="./midigpt_pipeline",
                        help="Working directory for intermediate outputs")

    # Augmentation options
    parser.add_argument("--transpose", type=str, default="all",
                        help="Transposition: 'all' (x12), '6' (x6), 'none' (skip)")
    parser.add_argument("--dropout", type=int, default=3,
                        help="Track dropout variations per file (0=skip)")
    parser.add_argument("--no_augment", action="store_true",
                        help="Skip augmentation entirely (use originals only)")

    # Tokenization options
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel workers for tokenization")

    # Training options
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--block_size", type=int, default=2048)
    parser.add_argument("--max_lr", type=float, default=3e-4)
    parser.add_argument("--grad_accum", type=int, default=4)
    parser.add_argument("--checkpoint_dir", type=str, default="./checkpoints")

    # Pipeline control
    parser.add_argument("--skip_to", type=str, default=None,
                        choices=["tokenize", "train"],
                        help="Skip earlier steps (resume from tokenize or train)")

    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    augmented_dir = work_dir / "augmented"
    token_dir = work_dir / "tokenized"
    midi_dir = Path(args.midi_dir)

    python = sys.executable
    start_time = time.time()

    # ──────────────────────────────────────────────────────────
    # Step 1: Augmentation
    # ──────────────────────────────────────────────────────────
    if args.skip_to not in ("tokenize", "train"):
        if args.no_augment:
            print("\n[SKIP] Augmentation disabled, using originals only")
            # Point tokenizer directly at original midi_dir
            tokenize_input = str(midi_dir)
        else:
            augmented_dir.mkdir(parents=True, exist_ok=True)

            cmd = [
                python, "-m", "midigpt.augment_dataset",
                "--input_dir", str(midi_dir),
                "--output_dir", str(augmented_dir),
                "--transpose", args.transpose,
                "--dropout", str(args.dropout),
            ]

            if not run_step("Augmentation (Key Transposition + Track Dropout)", cmd):
                print("\nPipeline stopped at augmentation.")
                sys.exit(1)

            tokenize_input = str(augmented_dir)
    else:
        # Determine input for tokenization
        if augmented_dir.exists() and any(augmented_dir.glob("*.mid")):
            tokenize_input = str(augmented_dir)
        else:
            tokenize_input = str(midi_dir)

    # ──────────────────────────────────────────────────────────
    # Step 2: Tokenization
    # ──────────────────────────────────────────────────────────
    if args.skip_to != "train":
        cmd = [
            python, "-m", "midigpt.tokenize_dataset",
            "--input_dir", tokenize_input,
            "--output_dir", str(token_dir),
            "--workers", str(args.workers),
        ]

        if not run_step("Tokenization (MIDI → Token Arrays)", cmd):
            print("\nPipeline stopped at tokenization.")
            sys.exit(1)

    # ──────────────────────────────────────────────────────────
    # Step 3: Training
    # ──────────────────────────────────────────────────────────
    cmd = [
        python, "-m", "midigpt.training.train_pretrain",
        "--data_dir", str(token_dir),
        "--checkpoint_dir", args.checkpoint_dir,
        "--epochs", str(args.epochs),
        "--batch_size", str(args.batch_size),
        "--block_size", str(args.block_size),
        "--max_lr", str(args.max_lr),
        "--grad_accum", str(args.grad_accum),
    ]

    if not run_step("Pre-training (MidiGPT 50M)", cmd):
        print("\nPipeline stopped at training.")
        sys.exit(1)

    # ──────────────────────────────────────────────────────────
    # Summary
    # ──────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    hours = elapsed / 3600

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Total time:    {hours:.1f} hours ({elapsed:.0f}s)")
    print(f"  MIDI input:    {midi_dir}")
    print(f"  Augmented:     {augmented_dir}")
    print(f"  Tokens:        {token_dir}")
    print(f"  Checkpoints:   {args.checkpoint_dir}")
    print(f"  Best model:    {args.checkpoint_dir}/midigpt_best.pt")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
