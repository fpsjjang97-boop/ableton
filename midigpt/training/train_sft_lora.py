"""
MidiGPT SFT LoRA Training — Fine-tune with original→variation pairs.

Usage:
    python -m midigpt.training.train_sft_lora \
        --base_model ./checkpoints/midigpt_base.pt \
        --data_dir ./midigpt_data \
        --output_dir ./lora_checkpoints

Hardware: RTX 4090 — 2-4 hours for 200 pairs
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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from midigpt.model import MidiGPTConfig, MidiGPT
from midigpt.data.dataset import MidiDataset, MidiCollator
from midigpt.tokenizer.vocab import VOCAB
from midigpt.training.lora import apply_lora, LoRAConfig, save_lora, load_lora


def train_sft(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Load base model
    print("Loading base model...")
    checkpoint = torch.load(args.base_model, map_location=device, weights_only=True)
    if "config" in checkpoint:
        config = MidiGPTConfig(**checkpoint["config"])
    else:
        config = MidiGPTConfig(vocab_size=VOCAB.size)

    model = MidiGPT(config).to(device)
    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)
    print(f"Base model loaded: {model.count_parameters():,} parameters")

    # Apply LoRA
    lora_config = LoRAConfig(
        r=args.lora_r,
        alpha=args.lora_alpha,
        dropout=args.lora_dropout,
        target_modules=["q_proj", "v_proj", "o_proj"],
    )
    lora_params = apply_lora(model, lora_config)
    trainable = sum(p.numel() for p in lora_params)
    total = model.count_parameters()
    print(f"LoRA applied: {trainable:,} trainable / {total:,} total ({100*trainable/total:.2f}%)")

    # Freeze base model, only train LoRA
    for name, param in model.named_parameters():
        if "lora_" not in name:
            param.requires_grad = False

    # Dataset
    dataset = MidiDataset(args.data_dir, mode="sft", block_size=config.block_size)
    collator = MidiCollator()
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=2,
        collate_fn=collator,
        pin_memory=True,
        drop_last=False,
    )
    print(f"SFT Dataset: {len(dataset)} pairs, {len(loader)} batches/epoch")

    # Optimizer (only LoRA parameters)
    optimizer = torch.optim.AdamW(lora_params, lr=args.lr, weight_decay=0.01)

    # Training
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    best_loss = float("inf")
    start_time = time.time()

    print(f"\nTraining: {args.epochs} epochs")
    print("=" * 60)

    for epoch in range(args.epochs):
        model.train()
        epoch_loss = 0.0

        for batch_idx, batch in enumerate(loader):
            input_ids = batch["input_ids"].to(device)
            labels = batch["labels"].to(device)

            with torch.amp.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
                _, loss = model(input_ids, targets=labels)

            loss.backward()

            if (batch_idx + 1) % args.grad_accum == 0 or (batch_idx + 1) == len(loader):
                nn.utils.clip_grad_norm_(lora_params, 1.0)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)

            epoch_loss += loss.item()

            if (batch_idx + 1) % 10 == 0:
                print(f"  Epoch {epoch+1} | Batch {batch_idx+1}/{len(loader)} | Loss {loss.item():.4f}")

        avg_loss = epoch_loss / max(len(loader), 1)
        elapsed = time.time() - start_time
        print(f"Epoch {epoch+1} | Avg Loss: {avg_loss:.4f} | Time: {elapsed/60:.1f}min")

        if avg_loss < best_loss:
            best_loss = avg_loss
            save_lora(model, output_dir / "lora_sft_best.bin")
            print(f"  Best LoRA saved (loss: {best_loss:.4f})")

    save_lora(model, output_dir / "lora_sft_latest.bin")
    total_time = time.time() - start_time
    print("=" * 60)
    print(f"SFT LoRA training complete! Time: {total_time/60:.1f}min")
    print(f"Best loss: {best_loss:.4f}")
    print(f"LoRA weights: {output_dir / 'lora_sft_best.bin'}")


def main():
    parser = argparse.ArgumentParser(description="MidiGPT SFT LoRA Training")
    parser.add_argument("--base_model", type=str, required=True)
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--output_dir", type=str, default="./lora_checkpoints")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--grad_accum", type=int, default=4)
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)

    args = parser.parse_args()
    train_sft(args)


if __name__ == "__main__":
    main()
