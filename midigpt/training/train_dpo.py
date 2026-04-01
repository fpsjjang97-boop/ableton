"""
MidiGPT DPO Training — Direct Preference Optimization from human reviews.

Usage:
    python -m midigpt.training.train_dpo \
        --base_model ./checkpoints/midigpt_base.pt \
        --lora_model ./lora_checkpoints/lora_sft_best.bin \
        --data_dir ./midigpt_data \
        --output_dir ./lora_checkpoints

DPO learns from (chosen, rejected) pairs without a reward model.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from midigpt.model import MidiGPTConfig, MidiGPT
from midigpt.data.dataset import MidiDataset, MidiCollator
from midigpt.tokenizer.vocab import VOCAB
from midigpt.training.lora import apply_lora, LoRAConfig, save_lora, load_lora


def compute_logprobs(model, input_ids, prompt_len):
    """Compute per-token log probabilities for the response portion."""
    logits, _ = model(input_ids)
    # Shift: predict token t from tokens 0..t-1
    shift_logits = logits[:, :-1, :]
    shift_labels = input_ids[:, 1:]

    log_probs = F.log_softmax(shift_logits, dim=-1)
    per_token_logp = log_probs.gather(-1, shift_labels.unsqueeze(-1)).squeeze(-1)

    # Only count response tokens (after prompt)
    mask = torch.zeros_like(per_token_logp)
    for i in range(mask.shape[0]):
        mask[i, prompt_len - 1:] = 1.0
    # Also mask padding (label == 0)
    mask = mask * (shift_labels != 0).float()

    return (per_token_logp * mask).sum(dim=-1)


def dpo_loss(
    policy_chosen_logps: torch.Tensor,
    policy_rejected_logps: torch.Tensor,
    ref_chosen_logps: torch.Tensor,
    ref_rejected_logps: torch.Tensor,
    beta: float = 0.1,
) -> torch.Tensor:
    """Compute DPO loss.

    L = -log(sigmoid(beta * (log(pi(chosen)/ref(chosen)) - log(pi(rejected)/ref(rejected)))))
    """
    chosen_rewards = beta * (policy_chosen_logps - ref_chosen_logps)
    rejected_rewards = beta * (policy_rejected_logps - ref_rejected_logps)
    return -F.logsigmoid(chosen_rewards - rejected_rewards).mean()


def train_dpo(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Load base model
    print("Loading base model...")
    checkpoint = torch.load(args.base_model, map_location=device, weights_only=True)
    if "config" in checkpoint:
        config = MidiGPTConfig(**checkpoint["config"])
    else:
        config = MidiGPTConfig(vocab_size=VOCAB.size)

    # Policy model (will be trained)
    policy = MidiGPT(config).to(device)
    if "model_state_dict" in checkpoint:
        policy.load_state_dict(checkpoint["model_state_dict"])
    else:
        policy.load_state_dict(checkpoint)

    # Reference model (frozen copy)
    ref_model = MidiGPT(config).to(device)
    if "model_state_dict" in checkpoint:
        ref_model.load_state_dict(checkpoint["model_state_dict"])
    else:
        ref_model.load_state_dict(checkpoint)
    ref_model.eval()
    for p in ref_model.parameters():
        p.requires_grad = False

    # Apply LoRA to policy model
    lora_config = LoRAConfig(
        r=args.lora_r,
        alpha=args.lora_alpha,
        dropout=args.lora_dropout,
        target_modules=["q_proj", "v_proj", "o_proj"],
    )
    lora_params = apply_lora(policy, lora_config)

    # Load SFT LoRA as starting point (if provided)
    if args.lora_model and Path(args.lora_model).exists():
        print(f"Loading SFT LoRA: {args.lora_model}")
        load_lora(policy, args.lora_model)

    # Freeze base, train LoRA only
    for name, param in policy.named_parameters():
        if "lora_" not in name:
            param.requires_grad = False

    trainable = sum(p.numel() for p in lora_params)
    print(f"LoRA trainable: {trainable:,} parameters")

    # Dataset
    dataset = MidiDataset(args.data_dir, mode="dpo", block_size=config.block_size)
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
    print(f"DPO Dataset: {len(dataset)} preference pairs")

    # Optimizer
    optimizer = torch.optim.AdamW(lora_params, lr=args.lr, weight_decay=0.01)

    # Training
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    best_loss = float("inf")
    start_time = time.time()

    print(f"\nDPO Training: {args.epochs} epochs, beta={args.beta}")
    print("=" * 60)

    for epoch in range(args.epochs):
        policy.train()
        epoch_loss = 0.0
        epoch_chosen_reward = 0.0
        epoch_rejected_reward = 0.0

        for batch_idx, batch in enumerate(loader):
            chosen_ids = batch["chosen_ids"].to(device)
            rejected_ids = batch["rejected_ids"].to(device)
            prompt_len = batch["prompt_len"]
            # Use first item's prompt_len (batch items may vary)
            pl = prompt_len[0].item() if isinstance(prompt_len, torch.Tensor) else prompt_len[0]

            # Policy log-probs
            policy_chosen_logps = compute_logprobs(policy, chosen_ids, pl)
            policy_rejected_logps = compute_logprobs(policy, rejected_ids, pl)

            # Reference log-probs (no grad)
            with torch.no_grad():
                ref_chosen_logps = compute_logprobs(ref_model, chosen_ids, pl)
                ref_rejected_logps = compute_logprobs(ref_model, rejected_ids, pl)

            # DPO loss
            loss = dpo_loss(
                policy_chosen_logps, policy_rejected_logps,
                ref_chosen_logps, ref_rejected_logps,
                beta=args.beta,
            )

            loss.backward()

            if (batch_idx + 1) % args.grad_accum == 0 or (batch_idx + 1) == len(loader):
                nn.utils.clip_grad_norm_(lora_params, 1.0)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)

            epoch_loss += loss.item()

            # Track reward margins
            with torch.no_grad():
                chosen_r = (policy_chosen_logps - ref_chosen_logps).mean().item()
                rejected_r = (policy_rejected_logps - ref_rejected_logps).mean().item()
                epoch_chosen_reward += chosen_r
                epoch_rejected_reward += rejected_r

            if (batch_idx + 1) % 5 == 0:
                print(
                    f"  Epoch {epoch+1} | Batch {batch_idx+1}/{len(loader)} | "
                    f"Loss {loss.item():.4f} | "
                    f"Margin {chosen_r - rejected_r:.3f}"
                )

        n_batches = max(len(loader), 1)
        avg_loss = epoch_loss / n_batches
        avg_margin = (epoch_chosen_reward - epoch_rejected_reward) / n_batches
        elapsed = time.time() - start_time

        print(
            f"Epoch {epoch+1} | Loss: {avg_loss:.4f} | "
            f"Reward margin: {avg_margin:.3f} | "
            f"Time: {elapsed/60:.1f}min"
        )

        if avg_loss < best_loss:
            best_loss = avg_loss
            save_lora(policy, output_dir / "lora_dpo_best.bin")
            print(f"  Best DPO LoRA saved (loss: {best_loss:.4f})")

    save_lora(policy, output_dir / "lora_dpo_latest.bin")
    total_time = time.time() - start_time
    print("=" * 60)
    print(f"DPO training complete! Time: {total_time/60:.1f}min")
    print(f"Best loss: {best_loss:.4f}")


def main():
    parser = argparse.ArgumentParser(description="MidiGPT DPO Training")
    parser.add_argument("--base_model", type=str, required=True)
    parser.add_argument("--lora_model", type=str, default=None, help="SFT LoRA to start from")
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--output_dir", type=str, default="./lora_checkpoints")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch_size", type=int, default=2)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--beta", type=float, default=0.1, help="DPO temperature")
    parser.add_argument("--grad_accum", type=int, default=4)
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)

    args = parser.parse_args()
    train_dpo(args)


if __name__ == "__main__":
    main()
