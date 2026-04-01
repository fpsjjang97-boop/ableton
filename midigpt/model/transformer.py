"""
MidiGPT — 50M Decoder-Only Transformer for MIDI generation.

Architecture:
  - 12 layers, 12 heads, 768 dim, 3072 FFN
  - RMSNorm (more stable than LayerNorm)
  - Rotary Position Embeddings (RoPE)
  - SwiGLU activation (better than GELU for this scale)
  - Pre-norm residual connections
  - Optional weight tying
"""
from __future__ import annotations

import math
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import MidiGPTConfig


# ---------------------------------------------------------------------------
# RMSNorm — simpler and more stable than LayerNorm
# ---------------------------------------------------------------------------
class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        norm = x.float().pow(2).mean(-1, keepdim=True).add(self.eps).rsqrt()
        return (x.float() * norm).type_as(x) * self.weight


# ---------------------------------------------------------------------------
# Rotary Position Embeddings (RoPE)
# ---------------------------------------------------------------------------
def precompute_rope_freqs(dim: int, max_seq_len: int, theta: float = 10000.0) -> torch.Tensor:
    """Precompute complex exponential frequencies for RoPE."""
    freqs = 1.0 / (theta ** (torch.arange(0, dim, 2).float() / dim))
    t = torch.arange(max_seq_len).float()
    freqs = torch.outer(t, freqs)
    return torch.polar(torch.ones_like(freqs), freqs)  # complex64


def apply_rope(xq: torch.Tensor, xk: torch.Tensor, freqs: torch.Tensor):
    """Apply rotary embeddings to query and key tensors.

    Args:
        xq: (B, T, n_head, head_dim)
        xk: (B, T, n_head, head_dim)
        freqs: (T, head_dim//2) complex
    """
    # Reshape last dim to pairs → complex: (B, T, n_head, head_dim//2)
    xq_complex = torch.view_as_complex(xq.float().reshape(*xq.shape[:-1], -1, 2))
    xk_complex = torch.view_as_complex(xk.float().reshape(*xk.shape[:-1], -1, 2))

    # Broadcast freqs: (T, head_dim//2) → (1, T, 1, head_dim//2)
    freqs = freqs.unsqueeze(0).unsqueeze(2)

    xq_out = torch.view_as_real(xq_complex * freqs).flatten(-2)
    xk_out = torch.view_as_real(xk_complex * freqs).flatten(-2)
    return xq_out.type_as(xq), xk_out.type_as(xk)


# ---------------------------------------------------------------------------
# Multi-Head Self-Attention with RoPE
# ---------------------------------------------------------------------------
class Attention(nn.Module):
    def __init__(self, config: MidiGPTConfig):
        super().__init__()
        assert config.n_embd % config.n_head == 0

        self.n_head = config.n_head
        self.head_dim = config.n_embd // config.n_head
        self.n_embd = config.n_embd

        self.q_proj = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)
        self.k_proj = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)
        self.v_proj = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)
        self.o_proj = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)

        self.attn_dropout = nn.Dropout(config.attn_dropout)
        self.resid_dropout = nn.Dropout(config.resid_dropout)

    def forward(
        self,
        x: torch.Tensor,
        freqs: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        B, T, C = x.shape

        q = self.q_proj(x).view(B, T, self.n_head, self.head_dim)
        k = self.k_proj(x).view(B, T, self.n_head, self.head_dim)
        v = self.v_proj(x).view(B, T, self.n_head, self.head_dim)

        # Apply RoPE to Q and K
        q, k = apply_rope(q, k, freqs[:T])

        # Transpose for attention: (B, n_head, T, head_dim)
        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)

        # Scaled dot-product attention (PyTorch 2.0+ flash attention)
        if hasattr(F, 'scaled_dot_product_attention'):
            y = F.scaled_dot_product_attention(
                q, k, v,
                attn_mask=mask,
                dropout_p=self.attn_dropout.p if self.training else 0.0,
                is_causal=mask is None,
            )
        else:
            # Manual attention for older PyTorch
            scale = 1.0 / math.sqrt(self.head_dim)
            attn = torch.matmul(q, k.transpose(-2, -1)) * scale
            if mask is None:
                causal = torch.triu(torch.ones(T, T, device=x.device), diagonal=1).bool()
                attn.masked_fill_(causal, float('-inf'))
            else:
                attn = attn + mask
            attn = F.softmax(attn, dim=-1)
            attn = self.attn_dropout(attn)
            y = torch.matmul(attn, v)

        # Reshape and project
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        y = self.resid_dropout(self.o_proj(y))
        return y


# ---------------------------------------------------------------------------
# SwiGLU Feed-Forward Network
# ---------------------------------------------------------------------------
class SwiGLU(nn.Module):
    """SwiGLU activation — better than GELU for language models."""
    def __init__(self, config: MidiGPTConfig):
        super().__init__()
        # SwiGLU uses 2/3 of the inner dim for gate and up projections
        hidden = int(2 * config.n_inner / 3)
        # Round to nearest multiple of 64 for efficiency
        hidden = 64 * ((hidden + 63) // 64)

        self.gate_proj = nn.Linear(config.n_embd, hidden, bias=config.bias)
        self.up_proj = nn.Linear(config.n_embd, hidden, bias=config.bias)
        self.down_proj = nn.Linear(hidden, config.n_embd, bias=config.bias)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        gate = F.silu(self.gate_proj(x))
        up = self.up_proj(x)
        return self.dropout(self.down_proj(gate * up))


# ---------------------------------------------------------------------------
# Transformer Block
# ---------------------------------------------------------------------------
class TransformerBlock(nn.Module):
    def __init__(self, config: MidiGPTConfig):
        super().__init__()
        self.attn_norm = RMSNorm(config.n_embd)
        self.attn = Attention(config)
        self.ffn_norm = RMSNorm(config.n_embd)
        self.ffn = SwiGLU(config)

    def forward(
        self,
        x: torch.Tensor,
        freqs: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        # Pre-norm residual
        x = x + self.attn(self.attn_norm(x), freqs, mask)
        x = x + self.ffn(self.ffn_norm(x))
        return x


# ---------------------------------------------------------------------------
# MidiGPT — Full Model
# ---------------------------------------------------------------------------
class MidiGPT(nn.Module):
    """50M Decoder-Only Transformer for MIDI token sequences."""

    def __init__(self, config: MidiGPTConfig):
        super().__init__()
        self.config = config

        # Token embedding
        self.tok_emb = nn.Embedding(config.vocab_size, config.n_embd)

        # Transformer blocks
        self.blocks = nn.ModuleList([
            TransformerBlock(config) for _ in range(config.n_layer)
        ])

        # Final norm
        self.norm_f = RMSNorm(config.n_embd)

        # Output head
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)

        # Weight tying: share embedding and output weights
        if config.weight_tying:
            self.lm_head.weight = self.tok_emb.weight

        # Precompute RoPE frequencies
        self.register_buffer(
            "rope_freqs",
            precompute_rope_freqs(config.n_embd // config.n_head, config.block_size),
            persistent=False,
        )

        # Initialize weights
        self.apply(self._init_weights)
        # Scale residual projections
        for pn, p in self.named_parameters():
            if pn.endswith("o_proj.weight") or pn.endswith("down_proj.weight"):
                nn.init.normal_(p, mean=0.0, std=0.02 / math.sqrt(2 * config.n_layer))

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(
        self,
        idx: torch.Tensor,
        targets: Optional[torch.Tensor] = None,
    ) -> tuple[torch.Tensor, Optional[torch.Tensor]]:
        """Forward pass.

        Args:
            idx: Input token IDs, shape (B, T)
            targets: Target token IDs for loss computation, shape (B, T)

        Returns:
            (logits, loss) — loss is None if targets not provided
        """
        B, T = idx.shape
        assert T <= self.config.block_size, \
            f"Sequence length {T} exceeds block_size {self.config.block_size}"

        # Token embeddings (RoPE replaces position embeddings)
        x = self.tok_emb(idx)

        # Get RoPE frequencies for this sequence length
        freqs = self.rope_freqs[:T]

        # Transformer blocks
        for block in self.blocks:
            x = block(x, freqs)

        # Final norm
        x = self.norm_f(x)

        # Compute logits
        if targets is not None:
            logits = self.lm_head(x)
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                targets.view(-1),
                ignore_index=0,  # ignore <PAD> token (id=0)
            )
        else:
            # Inference: only compute logits for last position
            logits = self.lm_head(x[:, -1:, :])
            loss = None

        return logits, loss

    @torch.no_grad()
    def generate(
        self,
        idx: torch.Tensor,
        max_new_tokens: int = 512,
        temperature: float = 0.9,
        top_k: int = 50,
        top_p: float = 0.95,
        eos_id: int = 2,
    ) -> torch.Tensor:
        """Autoregressive generation.

        Args:
            idx: Starting token IDs, shape (B, T)
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature (lower = more deterministic)
            top_k: Keep only top K candidates
            top_p: Nucleus sampling threshold
            eos_id: Token ID for <EOS> to stop generation

        Returns:
            Generated token IDs, shape (B, T + generated)
        """
        self.eval()

        for _ in range(max_new_tokens):
            # Crop to block_size if needed
            idx_cond = idx if idx.size(1) <= self.config.block_size \
                else idx[:, -self.config.block_size:]

            # Forward pass
            logits, _ = self(idx_cond)
            logits = logits[:, -1, :] / temperature

            # Top-K filtering
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')

            # Top-P (nucleus) filtering
            if top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(logits, descending=True)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                sorted_mask = cumulative_probs - F.softmax(sorted_logits, dim=-1) > top_p
                sorted_logits[sorted_mask] = float('-inf')
                logits = sorted_logits.scatter(1, sorted_indices, sorted_logits)

            # Sample
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Append
            idx = torch.cat([idx, next_token], dim=1)

            # Stop on EOS
            if (next_token == eos_id).all():
                break

        return idx

    def count_parameters(self) -> int:
        """Count total trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
