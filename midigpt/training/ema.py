"""
Exponential Moving Average (EMA) of model weights.

Phase 1 addition.  Maintaining an EMA copy of the parameters during
training and using the EMA copy for evaluation/inference is one of the
cheapest ways to stabilise generative models — particularly important
for small datasets where individual SGD steps can swing the weights.

Usage:
    ema = EMA(model, decay=0.999)
    for batch in loader:
        loss = model(batch).loss
        loss.backward()
        optimizer.step()
        ema.update(model)            # after each optimiser step
    ema.copy_to(model)               # before saving / evaluating
    torch.save(model.state_dict(), "midigpt_ema.pt")

The implementation is intentionally additive: it stores its own shadow
parameters and never modifies the live model in-place except via the
explicit ``copy_to`` / ``store`` / ``restore`` methods.

Compatible with arbitrary ``nn.Module`` instances; no architecture
assumptions, no checkpoint format changes, and zero impact on existing
training scripts unless EMA is explicitly enabled.
"""
from __future__ import annotations

from typing import Dict

import torch
import torch.nn as nn


class EMA:
    """Exponential moving average of model parameters."""

    def __init__(self, model: nn.Module, decay: float = 0.999):
        """
        Args:
            model: The model whose parameters will be tracked.
            decay: EMA decay factor.  Larger = slower averaging.
                ``0.999`` is a sane default for ~10K-step training runs;
                use ``0.9999`` for very long runs and ``0.99`` for short
                ones.  Effective half-life ≈ ln(2) / (1 - decay).
        """
        if not 0.0 < decay < 1.0:
            raise ValueError(f"decay must be in (0, 1), got {decay}")
        self.decay = decay
        self.shadow: Dict[str, torch.Tensor] = {}
        self.backup: Dict[str, torch.Tensor] = {}

        # Register every trainable parameter
        for name, param in model.named_parameters():
            if param.requires_grad:
                self.shadow[name] = param.detach().clone()

    @torch.no_grad()
    def update(self, model: nn.Module) -> None:
        """Update shadow weights from the current model parameters."""
        for name, param in model.named_parameters():
            if not param.requires_grad:
                continue
            assert name in self.shadow, f"unknown param {name}"
            shadow = self.shadow[name]
            shadow.mul_(self.decay).add_(param.detach(), alpha=1.0 - self.decay)

    @torch.no_grad()
    def copy_to(self, model: nn.Module) -> None:
        """Copy shadow weights into ``model`` (destructive)."""
        for name, param in model.named_parameters():
            if name in self.shadow:
                param.data.copy_(self.shadow[name])

    @torch.no_grad()
    def store(self, model: nn.Module) -> None:
        """Save current model weights so they can be restored later."""
        self.backup = {
            name: param.detach().clone()
            for name, param in model.named_parameters()
            if param.requires_grad
        }

    @torch.no_grad()
    def restore(self, model: nn.Module) -> None:
        """Restore the weights previously saved with :meth:`store`."""
        for name, param in model.named_parameters():
            if name in self.backup:
                param.data.copy_(self.backup[name])
        self.backup = {}

    def state_dict(self) -> Dict[str, torch.Tensor]:
        return {"decay": torch.tensor(self.decay), **self.shadow}

    def load_state_dict(self, state: Dict[str, torch.Tensor]) -> None:
        if "decay" in state:
            self.decay = float(state["decay"].item())
        self.shadow = {k: v for k, v in state.items() if k != "decay"}
