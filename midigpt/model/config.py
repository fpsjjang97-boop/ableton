"""
MidiGPT Model Configuration — 50M Decoder-Only Transformer.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MidiGPTConfig:
    """Configuration for the 50M MidiGPT model.

    Architecture: Decoder-Only Transformer
    Parameters:   ~50M
    """
    # Vocabulary
    vocab_size: int = 527          # v2.0 expanded vocab (Cubase15 확장, 33 articulations)

    # Transformer dimensions (tuned for ~50M parameters)
    n_layer: int = 12              # number of transformer blocks
    n_head: int = 12               # attention heads (head_dim = 48)
    n_embd: int = 576              # embedding dimension
    n_inner: int = 2304            # FFN inner dimension (4 * n_embd)

    # Sequence
    block_size: int = 2048         # max context length in tokens

    # Regularization
    dropout: float = 0.1
    attn_dropout: float = 0.1
    resid_dropout: float = 0.1

    # Training
    bias: bool = False             # use bias in linear layers (False = slightly better)
    weight_tying: bool = True      # tie input embedding and output projection weights

    # LoRA defaults
    lora_rank: int = 32            # low-rank adaptation rank
    lora_target_modules: list[str] = field(
        default_factory=lambda: [
            "q_proj", "k_proj", "v_proj", "o_proj",   # attention projections
            "gate_proj", "up_proj", "down_proj",       # FFN (SwiGLU) projections
        ]
    )

    @property
    def num_params(self) -> int:
        """Estimate total parameter count."""
        # Embedding: vocab_size * n_embd
        emb = self.vocab_size * self.n_embd
        # RoPE: no learnable position embeddings (computed on-the-fly)
        pos = 0

        # Per transformer block:
        #   Attention: 4 * n_embd^2 (Q, K, V, O projections)
        #   SwiGLU FFN: 3 * n_embd * hidden (gate + up + down, hidden ≈ 2/3 * n_inner)
        #   RMSNorms: 2 * n_embd
        attn = 4 * self.n_embd ** 2
        swiglu_hidden = 64 * ((int(2 * self.n_inner / 3) + 63) // 64)
        ffn = 3 * self.n_embd * swiglu_hidden
        ln = 2 * self.n_embd
        per_block = attn + ffn + ln
        blocks = self.n_layer * per_block

        # Final layer norm + output head
        final_ln = 2 * self.n_embd
        # If weight tying, output head shares embedding weights
        head = 0 if self.weight_tying else self.vocab_size * self.n_embd

        return emb + pos + blocks + final_ln + head

    def __repr__(self) -> str:
        params = self.num_params
        if params >= 1_000_000:
            param_str = f"{params / 1_000_000:.1f}M"
        else:
            param_str = f"{params:,}"
        return (
            f"MidiGPTConfig(\n"
            f"  params={param_str},\n"
            f"  n_layer={self.n_layer}, n_head={self.n_head}, n_embd={self.n_embd},\n"
            f"  n_inner={self.n_inner}, block_size={self.block_size},\n"
            f"  vocab_size={self.vocab_size}\n"
            f")"
        )
