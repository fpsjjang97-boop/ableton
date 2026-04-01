"""
MidiDataset — PyTorch Dataset/DataLoader for pre-training and fine-tuning.

Handles:
  1. Pre-training: next-token prediction on tokenized MIDI sequences
  2. SFT: condition + original → variation pairs
  3. DPO: chosen/rejected pairs for preference learning
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader


class MidiDataset(Dataset):
    """Dataset for tokenized MIDI sequences.

    Modes:
        pretrain — loads .npy token arrays for next-token prediction
        sft      — loads paired (input, output) sequences
        dpo      — loads (prompt, chosen, rejected) triples
    """

    def __init__(
        self,
        data_dir: str,
        mode: str = "pretrain",
        block_size: int = 2048,
        pad_id: int = 0,
    ):
        self.data_dir = Path(data_dir)
        self.mode = mode
        self.block_size = block_size
        self.pad_id = pad_id

        if mode == "pretrain":
            self._load_pretrain()
        elif mode == "sft":
            self._load_sft()
        elif mode == "dpo":
            self._load_dpo()
        else:
            raise ValueError(f"Unknown mode: {mode}")

    # ------------------------------------------------------------------
    # Pre-training mode
    # ------------------------------------------------------------------
    def _load_pretrain(self):
        """Load all .npy token files and concatenate into one big sequence."""
        self.sequences: list[np.ndarray] = []
        token_dir = self.data_dir / "tokens"

        if not token_dir.exists():
            raise FileNotFoundError(f"Token directory not found: {token_dir}")

        for npy_file in sorted(token_dir.glob("*.npy")):
            tokens = np.load(npy_file).astype(np.int64)
            if len(tokens) >= 10:  # skip too-short sequences
                self.sequences.append(tokens)

        if not self.sequences:
            raise FileNotFoundError(f"No .npy files found in {token_dir}")

        # Build index: (file_idx, start_pos) for each block_size chunk
        self.chunks: list[tuple[int, int]] = []
        for file_idx, seq in enumerate(self.sequences):
            for start in range(0, max(1, len(seq) - 1), self.block_size):
                self.chunks.append((file_idx, start))

    def _load_sft(self):
        """Load SFT paired data from JSON files."""
        self.sft_pairs: list[dict] = []
        sft_dir = self.data_dir / "sft"

        if not sft_dir.exists():
            raise FileNotFoundError(f"SFT directory not found: {sft_dir}")

        for json_file in sorted(sft_dir.glob("*.json")):
            with open(json_file, "r", encoding="utf-8") as f:
                pair = json.load(f)
                self.sft_pairs.append(pair)

    def _load_dpo(self):
        """Load DPO preference data from JSON files."""
        self.dpo_triples: list[dict] = []
        dpo_dir = self.data_dir / "dpo"

        if not dpo_dir.exists():
            raise FileNotFoundError(f"DPO directory not found: {dpo_dir}")

        for json_file in sorted(dpo_dir.glob("*.json")):
            with open(json_file, "r", encoding="utf-8") as f:
                triple = json.load(f)
                self.dpo_triples.append(triple)

    # ------------------------------------------------------------------
    # Dataset interface
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        if self.mode == "pretrain":
            return len(self.chunks)
        elif self.mode == "sft":
            return len(self.sft_pairs)
        elif self.mode == "dpo":
            return len(self.dpo_triples)
        return 0

    def __getitem__(self, idx: int) -> dict:
        if self.mode == "pretrain":
            return self._get_pretrain(idx)
        elif self.mode == "sft":
            return self._get_sft(idx)
        elif self.mode == "dpo":
            return self._get_dpo(idx)
        raise ValueError(f"Unknown mode: {self.mode}")

    def _get_pretrain(self, idx: int) -> dict:
        """Get a pre-training sample: input_ids and labels for next-token prediction."""
        file_idx, start = self.chunks[idx]
        seq = self.sequences[file_idx]

        end = min(start + self.block_size + 1, len(seq))
        chunk = seq[start:end]

        # Pad if needed
        if len(chunk) < self.block_size + 1:
            padding = np.full(self.block_size + 1 - len(chunk), self.pad_id, dtype=np.int64)
            chunk = np.concatenate([chunk, padding])

        input_ids = torch.tensor(chunk[:-1], dtype=torch.long)
        labels = torch.tensor(chunk[1:], dtype=torch.long)

        return {"input_ids": input_ids, "labels": labels}

    def _get_sft(self, idx: int) -> dict:
        """Get an SFT sample: condition + original → variation."""
        pair = self.sft_pairs[idx]
        # Expected format: {"input": [token_ids], "output": [token_ids]}
        input_ids = pair["input"]
        output_ids = pair["output"]

        # Concatenate: input <SEP> output
        # SEP token id = 3
        combined = input_ids + [3] + output_ids
        combined = combined[:self.block_size + 1]

        # Pad
        if len(combined) < self.block_size + 1:
            combined += [self.pad_id] * (self.block_size + 1 - len(combined))

        tokens = torch.tensor(combined, dtype=torch.long)
        input_tensor = tokens[:-1]
        labels = tokens[1:].clone()

        # Mask loss for input portion (only train on output)
        input_len = len(input_ids) + 1  # +1 for SEP
        labels[:input_len - 1] = 0  # pad_id = 0, ignored in loss

        return {"input_ids": input_tensor, "labels": labels}

    def _get_dpo(self, idx: int) -> dict:
        """Get a DPO sample: prompt, chosen, rejected."""
        triple = self.dpo_triples[idx]
        # Expected format: {"prompt": [...], "chosen": [...], "rejected": [...]}
        prompt = triple["prompt"]
        chosen = triple["chosen"]
        rejected = triple["rejected"]

        def _build_seq(response: list[int]) -> torch.Tensor:
            combined = prompt + [3] + response  # SEP=3
            combined = combined[:self.block_size]
            if len(combined) < self.block_size:
                combined += [self.pad_id] * (self.block_size - len(combined))
            return torch.tensor(combined, dtype=torch.long)

        return {
            "chosen_ids": _build_seq(chosen),
            "rejected_ids": _build_seq(rejected),
            "prompt_len": len(prompt) + 1,
        }


class MidiCollator:
    """Collate function for DataLoader."""

    def __call__(self, batch: list[dict]) -> dict:
        keys = batch[0].keys()
        collated = {}
        for key in keys:
            values = [item[key] for item in batch]
            if isinstance(values[0], torch.Tensor):
                collated[key] = torch.stack(values)
            elif isinstance(values[0], (int, float)):
                collated[key] = torch.tensor(values)
            else:
                collated[key] = values
        return collated


def create_dataloader(
    data_dir: str,
    mode: str = "pretrain",
    block_size: int = 2048,
    batch_size: int = 8,
    num_workers: int = 2,
    shuffle: bool = True,
) -> DataLoader:
    """Create a DataLoader for the specified mode."""
    dataset = MidiDataset(data_dir, mode=mode, block_size=block_size)
    collator = MidiCollator()
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        collate_fn=collator,
        pin_memory=True,
        drop_last=True,
    )
