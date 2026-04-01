"""
MidiGPT Pre-training Script — Next-token prediction on MIDI sequences.

Usage:
    python -m midigpt.training.train_pretrain --data_dir ./midigpt_data --epochs 10

Hardware:
    RTX 4090 (24GB):  batch_size=32, ~12-24 hours
    RTX 3060 (12GB):  batch_size=8,  grad_accum=4
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from midigpt.model import MidiGPTConfig, MidiGPT
from midigpt.data.dataset import MidiDataset, MidiCollator
from midigpt.tokenizer.vocab import VOCAB


def get_lr(step: int, warmup_steps: int, max_steps: int, max_lr: float, min_lr: float) -> float:
    """Cosine learning rate schedule with warmup."""
    if step < warmup_steps:
        return max_lr * (step + 1) / warmup_steps
    if step >= max_steps:
        return min_lr
    progress = (step - warmup_steps) / (max_steps - warmup_steps)
    return min_lr + 0.5 * (max_lr - min_lr) * (1 + math.cos(math.pi * progress))


def train(args):
    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name()}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # Model config — uses MidiGPTConfig defaults (50M: n_embd=576, n_inner=2304)
    config = MidiGPTConfig(
        vocab_size=VOCAB.size,
        block_size=args.block_size,
        dropout=args.dropout,
    )
    print(f"\n{config}")

    # Model
    model = MidiGPT(config).to(device)
    params = model.count_parameters()
    print(f"Trainable parameters: {params:,} ({params/1e6:.1f}M)")

    # Dataset
    dataset = MidiDataset(args.data_dir, mode="pretrain", block_size=args.block_size)
    collator = MidiCollator()
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        collate_fn=collator,
        pin_memory=True,
        drop_last=True,
    )
    print(f"Dataset: {len(dataset)} chunks, {len(loader)} batches/epoch")

    # Optimizer
    # Separate weight decay for different parameter groups
    decay_params = []
    nodecay_params = []
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        if param.dim() >= 2:
            decay_params.append(param)
        else:
            nodecay_params.append(param)

    optim_groups = [
        {"params": decay_params, "weight_decay": args.weight_decay},
        {"params": nodecay_params, "weight_decay": 0.0},
    ]
    optimizer = torch.optim.AdamW(
        optim_groups,
        lr=args.max_lr,
        betas=(0.9, 0.95),
        eps=1e-8,
        fused=device.type == "cuda",
    )

    # Mixed precision
    use_amp = device.type == "cuda" and args.fp16
    scaler = torch.amp.GradScaler(enabled=use_amp)
    autocast_dtype = torch.float16 if use_amp else torch.float32

    # Training state
    total_steps = args.epochs * len(loader)
    warmup_steps = min(args.warmup_steps, total_steps // 10)
    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    log_path = checkpoint_dir / "train_log.jsonl"

    print(f"\nTraining: {args.epochs} epochs, {total_steps} total steps")
    print(f"Warmup: {warmup_steps} steps")
    print(f"Gradient accumulation: {args.grad_accum} steps")
    print(f"Effective batch size: {args.batch_size * args.grad_accum}")
    print(f"Checkpoints: {checkpoint_dir}")
    print("=" * 60)

    global_step = 0
    best_loss = float("inf")
    start_time = time.time()

    for epoch in range(args.epochs):
        model.train()
        epoch_loss = 0.0
        epoch_tokens = 0

        for batch_idx, batch in enumerate(loader):
            input_ids = batch["input_ids"].to(device)
            labels = batch["labels"].to(device)

            # Learning rate schedule
            lr = get_lr(global_step, warmup_steps, total_steps, args.max_lr, args.min_lr)
            for param_group in optimizer.param_groups:
                param_group["lr"] = lr

            # Forward pass with mixed precision
            with torch.amp.autocast(device_type=device.type, dtype=autocast_dtype, enabled=use_amp):
                logits, loss = model(input_ids, targets=labels)
                loss = loss / args.grad_accum

            # Backward
            scaler.scale(loss).backward()

            # Gradient accumulation
            if (batch_idx + 1) % args.grad_accum == 0 or (batch_idx + 1) == len(loader):
                # Gradient clipping
                if args.grad_clip > 0:
                    scaler.unscale_(optimizer)
                    nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)

                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)

            # Logging
            batch_loss = loss.item() * args.grad_accum
            epoch_loss += batch_loss
            epoch_tokens += input_ids.numel()
            global_step += 1

            if global_step % args.log_interval == 0:
                elapsed = time.time() - start_time
                tokens_per_sec = epoch_tokens / elapsed if elapsed > 0 else 0
                log_entry = {
                    "step": global_step,
                    "epoch": epoch + 1,
                    "loss": round(batch_loss, 4),
                    "lr": round(lr, 7),
                    "tokens/s": int(tokens_per_sec),
                    "elapsed_min": round(elapsed / 60, 1),
                }
                print(
                    f"Step {global_step:>6d} | "
                    f"Epoch {epoch+1}/{args.epochs} | "
                    f"Loss {batch_loss:.4f} | "
                    f"LR {lr:.2e} | "
                    f"Tok/s {tokens_per_sec:.0f} | "
                    f"{elapsed/60:.1f}min"
                )
                with open(log_path, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")

        # Epoch summary
        avg_loss = epoch_loss / len(loader) if len(loader) > 0 else 0
        print(f"\n--- Epoch {epoch+1} complete | Avg Loss: {avg_loss:.4f} ---\n")

        # Save checkpoint
        checkpoint = {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "config": config.__dict__,
            "epoch": epoch + 1,
            "global_step": global_step,
            "loss": avg_loss,
        }

        # Save latest
        torch.save(checkpoint, checkpoint_dir / "midigpt_latest.pt")

        # Save best
        if avg_loss < best_loss:
            best_loss = avg_loss
            torch.save(checkpoint, checkpoint_dir / "midigpt_best.pt")
            print(f"  New best model saved (loss: {best_loss:.4f})")

        # Periodic checkpoint
        if (epoch + 1) % args.save_every == 0:
            torch.save(checkpoint, checkpoint_dir / f"midigpt_epoch{epoch+1}.pt")

    # Final save
    total_time = time.time() - start_time
    print("=" * 60)
    print(f"Training complete!")
    print(f"Total time: {total_time/3600:.1f} hours")
    print(f"Best loss: {best_loss:.4f}")
    print(f"Final model: {checkpoint_dir / 'midigpt_best.pt'}")

    # Save final model weights only (smaller file for deployment)
    torch.save(model.state_dict(), checkpoint_dir / "midigpt_base.pt")
    print(f"Weights-only: {checkpoint_dir / 'midigpt_base.pt'}")


def main():
    parser = argparse.ArgumentParser(description="MidiGPT Pre-training")
    parser.add_argument("--data_dir", type=str, required=True, help="Path to tokenized data directory")
    parser.add_argument("--checkpoint_dir", type=str, default="./checkpoints", help="Save directory")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--block_size", type=int, default=2048)
    parser.add_argument("--max_lr", type=float, default=3e-4)
    parser.add_argument("--min_lr", type=float, default=3e-5)
    parser.add_argument("--warmup_steps", type=int, default=200)
    parser.add_argument("--weight_decay", type=float, default=0.1)
    parser.add_argument("--grad_clip", type=float, default=1.0)
    parser.add_argument("--grad_accum", type=int, default=4, help="Gradient accumulation steps")
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--fp16", action="store_true", default=True, help="Use mixed precision")
    parser.add_argument("--num_workers", type=int, default=2)
    parser.add_argument("--log_interval", type=int, default=10)
    parser.add_argument("--save_every", type=int, default=2, help="Save checkpoint every N epochs")

    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
