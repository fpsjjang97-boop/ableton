"""
LoRA (Low-Rank Adaptation) implementation for MidiGPT.

Injects trainable low-rank matrices into attention layers
while keeping the base model frozen.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class LoRAConfig:
    """Configuration for LoRA adaptation."""
    r: int = 16                     # rank
    alpha: int = 32                 # scaling factor
    dropout: float = 0.05
    target_modules: list[str] = field(
        default_factory=lambda: ["q_proj", "v_proj"]
    )


class LoRALinear(nn.Module):
    """Linear layer with LoRA adaptation.

    Computes: y = Wx + (alpha/r) * BAx
    where W is frozen, A and B are trainable low-rank matrices.
    """

    def __init__(
        self,
        original: nn.Linear,
        r: int = 16,
        alpha: int = 32,
        dropout: float = 0.05,
    ):
        super().__init__()
        self.original = original
        self.r = r
        self.alpha = alpha
        self.scaling = alpha / r

        in_features = original.in_features
        out_features = original.out_features

        # Match device/dtype of the (possibly already-moved) base layer so LoRA
        # params don't end up on CPU when the model is on GPU.
        device = original.weight.device
        dtype = original.weight.dtype

        # LoRA matrices
        self.lora_A = nn.Parameter(torch.empty(r, in_features, device=device, dtype=dtype))
        self.lora_B = nn.Parameter(torch.zeros(out_features, r, device=device, dtype=dtype))
        self.lora_dropout = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

        # Initialize A with Kaiming, B with zeros (so LoRA starts as identity)
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))

        # Freeze original weights
        self.original.weight.requires_grad = False
        if self.original.bias is not None:
            self.original.bias.requires_grad = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Original forward
        result = self.original(x)
        # LoRA delta
        lora_out = self.lora_dropout(x) @ self.lora_A.T @ self.lora_B.T
        return result + lora_out * self.scaling

    def merge(self) -> nn.Linear:
        """Merge LoRA weights into original for inference (no overhead)."""
        device = self.original.weight.device
        dtype = self.original.weight.dtype
        merged = nn.Linear(
            self.original.in_features,
            self.original.out_features,
            bias=self.original.bias is not None,
            device=device,
            dtype=dtype,
        )
        merged.weight.data = (
            self.original.weight.data +
            (self.lora_B @ self.lora_A).data * self.scaling
        )
        if self.original.bias is not None:
            merged.bias.data = self.original.bias.data
        return merged


def apply_lora(model: nn.Module, config: LoRAConfig) -> list[nn.Parameter]:
    """Apply LoRA to target modules in the model.

    Returns list of trainable LoRA parameters.
    """
    lora_params: list[nn.Parameter] = []

    for name, module in model.named_modules():
        for target in config.target_modules:
            if name.endswith(target) and isinstance(module, nn.Linear):
                # Get parent module
                parts = name.rsplit(".", 1)
                if len(parts) == 2:
                    parent_name, attr_name = parts
                    parent = dict(model.named_modules())[parent_name]
                else:
                    parent = model
                    attr_name = name

                # Replace with LoRA layer
                lora_layer = LoRALinear(
                    module, r=config.r, alpha=config.alpha, dropout=config.dropout
                )
                setattr(parent, attr_name, lora_layer)

                lora_params.append(lora_layer.lora_A)
                lora_params.append(lora_layer.lora_B)

    return lora_params


def save_lora(model: nn.Module, path: str | Path):
    """Save only LoRA weights (small file ~1-5MB)."""
    lora_state = {}
    for name, module in model.named_modules():
        if isinstance(module, LoRALinear):
            lora_state[f"{name}.lora_A"] = module.lora_A.data.cpu()
            lora_state[f"{name}.lora_B"] = module.lora_B.data.cpu()
            lora_state[f"{name}.r"] = module.r
            lora_state[f"{name}.alpha"] = module.alpha

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(lora_state, path)


def load_lora(model: nn.Module, path: str | Path, config: LoRAConfig | None = None):
    """Load LoRA weights into a model (LoRA layers must already exist)."""
    lora_state = torch.load(path, map_location="cpu", weights_only=True)
    device = next(model.parameters()).device

    # Check if LoRA layers exist; if not, apply them first
    has_lora = any(isinstance(m, LoRALinear) for m in model.modules())
    if not has_lora and config is not None:
        apply_lora(model, config)

    for name, module in model.named_modules():
        if isinstance(module, LoRALinear):
            a_key = f"{name}.lora_A"
            b_key = f"{name}.lora_B"
            if a_key in lora_state:
                module.lora_A.data = lora_state[a_key].to(device)
            if b_key in lora_state:
                module.lora_B.data = lora_state[b_key].to(device)


def merge_lora(model: nn.Module):
    """Merge all LoRA weights into base model (for deployment)."""
    for name, module in list(model.named_modules()):
        if isinstance(module, LoRALinear):
            parts = name.rsplit(".", 1)
            if len(parts) == 2:
                parent_name, attr_name = parts
                parent = dict(model.named_modules())[parent_name]
            else:
                parent = model
                attr_name = name

            merged = module.merge()
            setattr(parent, attr_name, merged)
