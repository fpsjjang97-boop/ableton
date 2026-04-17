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

from midigpt.tokenizer.vocab import VOCAB


# Minimum number of output-region label tokens that must survive truncation
# for an SFT pair to be usable. Pairs below this threshold would produce a
# loss computed from 0-3 tokens, which is both high-variance and (at 0) a
# NaN (cross_entropy with all targets == ignore_index returns nan — 6차
# 리포트 NaN 근본 원인). Conservative floor.
MIN_SFT_OUTPUT_LABELS = 4


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
        pad_id: int | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.mode = mode
        self.block_size = block_size
        # Single source of truth: vocab.pad_id (rules/05 패턴 H).
        # Accepts an override for tests; None → use vocab.
        self.pad_id = VOCAB.pad_id if pad_id is None else pad_id
        self.sep_id = VOCAB.sep_id

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
        """Load all .npy token files and concatenate into one big sequence.

        Resolves the token directory in this priority order:
            1. ``{data_dir}/tokens/``                  (canonical layout)
            2. ``{data_dir}/``                         (if user already pointed at the tokens dir)
            3. ``{data_dir}/tokenized/tokens/``        (pipeline.py work_dir layout)

        This makes ``train_pretrain.py --data_dir ./midigpt_pipeline/tokenized``
        and ``--data_dir ./midigpt_pipeline/tokenized/tokens`` and the legacy
        ``--data_dir ./midigpt_data`` (if it contains a tokens subdir) all work.
        """
        self.sequences: list[np.ndarray] = []

        candidates = [
            self.data_dir / "tokens",                    # canonical
            self.data_dir,                               # data_dir IS tokens dir
            self.data_dir / "tokenized" / "tokens",      # pipeline work_dir
        ]
        token_dir = next(
            (p for p in candidates if p.exists() and any(p.glob("*.npy"))),
            None,
        )

        if token_dir is None:
            tried = "\n  ".join(str(p) for p in candidates)
            raise FileNotFoundError(
                f"No token .npy files found. Looked in:\n  {tried}\n"
                f"Run 'python -m midigpt.pipeline --midi_dir ./midi_data' first, "
                f"or pass --data_dir pointing at the directory that contains "
                f"the .npy token files (or its parent)."
            )

        for npy_file in sorted(token_dir.glob("*.npy")):
            tokens = np.load(npy_file).astype(np.int64)
            if len(tokens) >= 10:  # skip too-short sequences
                self.sequences.append(tokens)

        if not self.sequences:
            raise FileNotFoundError(
                f"All .npy files in {token_dir} were too short (<10 tokens)."
            )

        # Build index: (file_idx, start_pos) for each block_size chunk
        self.chunks: list[tuple[int, int]] = []
        for file_idx, seq in enumerate(self.sequences):
            for start in range(0, max(1, len(seq) - 1), self.block_size):
                self.chunks.append((file_idx, start))

    def _load_sft(self):
        """Load SFT paired data from JSON files.

        Three-layer defense (rules/05-bug-history.md — 패턴 A, 패턴 G):
          1. Glob pattern restricted to ``sft_*.json`` (producer convention).
          2. Schema validation: entries missing "input"/"output" are skipped
             with a warning rather than raising KeyError downstream.
          3. Label-viability pre-filter (6차 리포트 NaN 대응):
             If ``len(input_ids) >= block_size`` (or within
             ``MIN_SFT_OUTPUT_LABELS`` of it), all output tokens are truncated
             at __getitem__ time and every label position becomes ignore_index.
             cross_entropy(..., ignore_index=pad_id) with zero surviving
             targets returns NaN (0/0). Skip such pairs up front so the
             DataLoader never yields a guaranteed-NaN batch.
        """
        self.sft_pairs: list[dict] = []
        sft_dir = self.data_dir / "sft"

        if not sft_dir.exists():
            raise FileNotFoundError(f"SFT directory not found: {sft_dir}")

        skipped_schema = 0
        skipped_parse = 0
        skipped_labels = 0
        for json_file in sorted(sft_dir.glob("sft_*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    pair = json.load(f)
            except json.JSONDecodeError as e:
                skipped_parse += 1
                print(f"  [WARN] SFT skip (malformed JSON) {json_file.name}: {e}")
                continue

            if not (isinstance(pair, dict)
                    and "input" in pair and "output" in pair):
                skipped_schema += 1
                print(f"  [WARN] SFT skip (missing input/output) {json_file.name}")
                continue

            # Labels are tokens[1:] of length block_size. Positions
            # 0..len(input_ids)-1 are masked (input-region). The output
            # region has at most `block_size - len(input_ids)` slots, and
            # holds at most `len(output_ids)` real tokens.
            effective_output_labels = max(
                0,
                min(len(pair["output"]), self.block_size - len(pair["input"]))
            )
            if effective_output_labels < MIN_SFT_OUTPUT_LABELS:
                skipped_labels += 1
                print(f"  [WARN] SFT skip (labels<{MIN_SFT_OUTPUT_LABELS}) "
                      f"{json_file.name}: "
                      f"input={len(pair['input'])} output={len(pair['output'])} "
                      f"effective={effective_output_labels}")
                continue

            self.sft_pairs.append(pair)

        if skipped_schema or skipped_parse or skipped_labels:
            print(f"  [INFO] SFT load: {len(self.sft_pairs)} ok, "
                  f"{skipped_schema} schema-invalid, "
                  f"{skipped_parse} malformed, "
                  f"{skipped_labels} truncated-too-much")

    def _load_dpo(self):
        """Load DPO preference data from JSON files.

        Same defense as _load_sft (rules/05-bug-history.md — 패턴 A).
        """
        self.dpo_triples: list[dict] = []
        dpo_dir = self.data_dir / "dpo"

        if not dpo_dir.exists():
            raise FileNotFoundError(f"DPO directory not found: {dpo_dir}")

        required = ("prompt", "chosen", "rejected")
        skipped_schema = 0
        skipped_parse = 0
        for json_file in sorted(dpo_dir.glob("dpo_*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    triple = json.load(f)
            except json.JSONDecodeError as e:
                skipped_parse += 1
                print(f"  [WARN] DPO skip (malformed JSON) {json_file.name}: {e}")
                continue

            if not (isinstance(triple, dict)
                    and all(k in triple for k in required)):
                skipped_schema += 1
                print(f"  [WARN] DPO skip (missing {required}) {json_file.name}")
                continue

            self.dpo_triples.append(triple)

        if skipped_schema or skipped_parse:
            print(f"  [INFO] DPO load: {len(self.dpo_triples)} ok, "
                  f"{skipped_schema} schema-invalid, {skipped_parse} malformed")

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
        """Get an SFT sample: condition + original → variation.

        Label masking: positions 0..len(input_ids)-1 predict the input/SEP
        region and are set to pad_id so cross_entropy(ignore_index=pad_id)
        skips them. The output region (labels[len(input_ids):]) is trained.

        Pre-filter in _load_sft guarantees at least MIN_SFT_OUTPUT_LABELS
        unmasked labels survive — so this sample can never produce the
        0-valid-target NaN (6차 리포트 근본 원인).
        """
        pair = self.sft_pairs[idx]
        # Expected format: {"input": [token_ids], "output": [token_ids]}
        input_ids = pair["input"]
        output_ids = pair["output"]

        # Concatenate: input <SEP> output (SEP from single-source vocab —
        # 패턴 H; prior hardcode of literal `3` was a latent bug waiting
        # for vocab reorder.)
        combined = input_ids + [self.sep_id] + output_ids
        combined = combined[:self.block_size + 1]

        # Pad
        if len(combined) < self.block_size + 1:
            combined += [self.pad_id] * (self.block_size + 1 - len(combined))

        tokens = torch.tensor(combined, dtype=torch.long)
        input_tensor = tokens[:-1]
        labels = tokens[1:].clone()

        # Mask loss for input portion (only train on output).
        # Masked positions set to pad_id → cross_entropy ignore_index.
        input_len = len(input_ids) + 1  # +1 for SEP
        labels[:input_len - 1] = self.pad_id

        return {"input_ids": input_tensor, "labels": labels}

    def _get_dpo(self, idx: int) -> dict:
        """Get a DPO sample: prompt, chosen, rejected."""
        triple = self.dpo_triples[idx]
        # Expected format: {"prompt": [...], "chosen": [...], "rejected": [...]}
        prompt = triple["prompt"]
        chosen = triple["chosen"]
        rejected = triple["rejected"]

        def _build_seq(response: list[int]) -> torch.Tensor:
            combined = prompt + [self.sep_id] + response
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
