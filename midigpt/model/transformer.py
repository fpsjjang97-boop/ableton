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
from typing import Optional, Tuple

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
        past_kv: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
    ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """Forward pass with optional KV cache.

        Args:
            x: Input tensor, shape (B, T, C).  When using KV cache for
               incremental decoding, T == 1 (only the new token).
            freqs: RoPE frequencies.  Must cover positions for the *new*
                   tokens.  When past_kv is provided the caller should
                   pass ``freqs[seq_len-T : seq_len]`` so that positions
                   are correct.
            mask: Optional attention mask.
            past_kv: Cached (K, V) from previous steps, each shaped
                     (B, n_head, T_past, head_dim).

        Returns:
            (output, present_kv) where present_kv is the full (K, V) cache
            including the newly computed keys/values.
        """
        B, T, C = x.shape

        q = self.q_proj(x).view(B, T, self.n_head, self.head_dim)
        k = self.k_proj(x).view(B, T, self.n_head, self.head_dim)
        v = self.v_proj(x).view(B, T, self.n_head, self.head_dim)

        # Apply RoPE — freqs should already be sliced to cover only the
        # new positions (length T).
        q, k = apply_rope(q, k, freqs[:T])

        # Transpose for attention: (B, n_head, T, head_dim)
        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)

        # Concatenate with cached K, V if available
        if past_kv is not None:
            past_k, past_v = past_kv
            k = torch.cat([past_k, k], dim=2)  # (B, n_head, T_past + T, head_dim)
            v = torch.cat([past_v, v], dim=2)

        # Store present KV for the cache (full history)
        present_kv = (k, v)

        # Total key/value sequence length (may differ from T when using cache)
        S = k.size(2)

        # Scaled dot-product attention (PyTorch 2.0+ flash attention)
        if hasattr(F, 'scaled_dot_product_attention'):
            # When using KV cache for single-token decode (T==1, S>1),
            # is_causal must be False because Q has 1 row — the causal
            # mask is trivially satisfied.  For the prefill (T==S) we
            # can keep is_causal=True when no explicit mask is given.
            use_causal = (mask is None) and (T == S)
            y = F.scaled_dot_product_attention(
                q, k, v,
                attn_mask=mask,
                dropout_p=self.attn_dropout.p if self.training else 0.0,
                is_causal=use_causal,
            )
        else:
            # Manual attention for older PyTorch
            scale = 1.0 / math.sqrt(self.head_dim)
            attn = torch.matmul(q, k.transpose(-2, -1)) * scale
            if mask is None:
                causal = torch.triu(
                    torch.ones(T, S, device=x.device), diagonal=S - T + 1
                ).bool()
                attn.masked_fill_(causal, float('-inf'))
            else:
                attn = attn + mask
            attn = F.softmax(attn, dim=-1)
            attn = self.attn_dropout(attn)
            y = torch.matmul(attn, v)

        # Reshape and project
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        y = self.resid_dropout(self.o_proj(y))
        return y, present_kv


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
        past_kv: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
    ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        # Pre-norm residual
        attn_out, present_kv = self.attn(self.attn_norm(x), freqs, mask, past_kv=past_kv)
        x = x + attn_out
        x = x + self.ffn(self.ffn_norm(x))
        return x, present_kv


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
        past_kv_list: Optional[list[Tuple[torch.Tensor, torch.Tensor]]] = None,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor], list[Tuple[torch.Tensor, torch.Tensor]]]:
        """Forward pass with optional KV cache.

        Args:
            idx: Input token IDs, shape (B, T).  During cached generation
                 T == 1 (only the newly generated token).
            targets: Target token IDs for loss computation, shape (B, T).
            past_kv_list: Per-layer KV cache from a previous forward call.
                          Length must equal ``n_layer``.

        Returns:
            (logits, loss, present_kv_list)
            *present_kv_list* contains per-layer (K, V) caches that can
            be passed back as *past_kv_list* on the next call.
        """
        B, T = idx.shape

        # When using KV cache, the effective sequence length seen by RoPE
        # is the past length + T.
        past_len = 0
        if past_kv_list is not None:
            past_len = past_kv_list[0][0].size(2)  # T_past from first layer

        total_len = past_len + T
        assert total_len <= self.config.block_size, \
            f"Sequence length {total_len} exceeds block_size {self.config.block_size}"

        # Token embeddings (RoPE replaces position embeddings)
        x = self.tok_emb(idx)

        # Get RoPE frequencies only for the *new* positions
        freqs = self.rope_freqs[past_len:total_len]

        # Transformer blocks
        present_kv_list: list[Tuple[torch.Tensor, torch.Tensor]] = []
        for i, block in enumerate(self.blocks):
            layer_past = past_kv_list[i] if past_kv_list is not None else None
            x, present_kv = block(x, freqs, past_kv=layer_past)
            present_kv_list.append(present_kv)

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

        return logits, loss, present_kv_list

    @torch.no_grad()
    def generate(
        self,
        idx: torch.Tensor,
        max_new_tokens: int = 512,
        temperature: float = 0.9,
        top_k: int = 50,
        top_p: float = 0.95,
        eos_id: int = 2,
        use_kv_cache: bool = True,
    ) -> torch.Tensor:
        """Autoregressive generation with KV cache.

        On the first step the full prompt is processed and the KV cache is
        initialised.  On every subsequent step only the last generated
        token is fed through the model while the cached K/V tensors are
        reused, giving O(1) per-token cost instead of O(T).

        If the sequence would exceed ``block_size`` the cache is
        invalidated and the context is re-processed from the last
        ``block_size`` tokens (graceful degradation).

        Args:
            idx: Starting token IDs, shape (B, T)
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature (lower = more deterministic)
            top_k: Keep only top K candidates
            top_p: Nucleus sampling threshold
            eos_id: Token ID for <EOS> to stop generation
            use_kv_cache: Whether to use KV caching (default True).
                          Set to False to fall back to the original
                          recompute-everything behaviour.

        Returns:
            Generated token IDs, shape (B, T + generated)
        """
        self.eval()

        past_kv_list: Optional[list[Tuple[torch.Tensor, torch.Tensor]]] = None

        for step in range(max_new_tokens):
            if use_kv_cache:
                if past_kv_list is None:
                    # First step — prefill: process the full prompt
                    idx_input = idx if idx.size(1) <= self.config.block_size \
                        else idx[:, -self.config.block_size:]
                    logits, _, past_kv_list = self(idx_input, past_kv_list=None)
                else:
                    # Incremental decode: only feed the last token
                    cur_len = past_kv_list[0][0].size(2) + 1  # past + new
                    if cur_len > self.config.block_size:
                        # Cache would exceed block_size — re-prefill from
                        # the tail of the sequence.
                        past_kv_list = None
                        idx_input = idx[:, -self.config.block_size:]
                        logits, _, past_kv_list = self(idx_input, past_kv_list=None)
                    else:
                        logits, _, past_kv_list = self(
                            idx[:, -1:], past_kv_list=past_kv_list,
                        )
            else:
                # Legacy path: recompute full attention every step
                idx_cond = idx if idx.size(1) <= self.config.block_size \
                    else idx[:, -self.config.block_size:]
                logits, _, _ = self(idx_cond)

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
