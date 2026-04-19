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


# ---------------------------------------------------------------------------
# Sprint 43 GGG1 — hot-swap 지원 helper
# ---------------------------------------------------------------------------
def load_lora_weights_only(path: str | Path) -> dict[str, torch.Tensor]:
    """Load LoRA state dict from disk without touching any model.

    Sprint 43 GGG1: register/activate 분리를 위해 단순 '파일 → 메모리' 만 담당.
    반환: `{"<layer.name>.lora_A": Tensor, "<layer.name>.lora_B": Tensor, ...}`

    `load_lora()` 와 호환 (동일 key 규칙 — save_lora 가 기록한 그대로).
    """
    state = torch.load(str(path), map_location="cpu", weights_only=True)
    if not isinstance(state, dict):
        raise ValueError(f"LoRA checkpoint 스키마 비정상: {type(state).__name__}")
    # 허용 키: *.lora_A, *.lora_B, *.r, *.alpha (메타)
    return state


def copy_weights_into_model(
    model: nn.Module,
    weights: dict[str, torch.Tensor],
) -> int:
    """Copy preloaded LoRA weights into existing LoRALinear layers.

    LoRA 구조(적용)는 이미 되어 있다고 가정(`apply_lora` 선행 필요).
    tensor 는 live 레이어의 device/dtype 으로 자동 변환. Returns the number
    of (lora_A, lora_B) pairs written.

    패턴 D 방어: Parameter.data 로 in-place 복사 — device 불일치 시 명시 error.
    """
    copied = 0
    for name, module in model.named_modules():
        if not isinstance(module, LoRALinear):
            continue
        a_key = f"{name}.lora_A"
        b_key = f"{name}.lora_B"
        if a_key in weights:
            w = weights[a_key].to(module.lora_A.device, module.lora_A.dtype)
            if w.shape != module.lora_A.shape:
                raise ValueError(
                    f"LoRA shape 불일치 {a_key}: "
                    f"파일 {tuple(w.shape)} vs 모델 {tuple(module.lora_A.shape)} "
                    f"— r 값 또는 target_modules 다른 LoRA 를 register 시도?"
                )
            module.lora_A.data.copy_(w)
            copied += 1
        if b_key in weights:
            w = weights[b_key].to(module.lora_B.device, module.lora_B.dtype)
            module.lora_B.data.copy_(w)
    return copied


def zero_lora_weights(model: nn.Module) -> int:
    """Zero out all LoRA A/B tensors → identity (base model forward only).

    Sprint 43 GGG2 deactivate 경로. LoRALinear 구조는 유지되므로 재활성화는
    copy_weights_into_model 한 번으로 즉시 복원 (파일 I/O 없음).
    """
    n = 0
    for module in model.modules():
        if isinstance(module, LoRALinear):
            module.lora_A.data.zero_()
            module.lora_B.data.zero_()
            n += 1
    return n
