# MidiGPT — LLM 아키텍처 명세

> MidiGPT 50M Decoder-Only Transformer 모델의 구조 표준 명세
> 분류: LLM / 모델 영역
> 코드: `midigpt/model/`

---

## 개요

MidiGPT는 MIDI 토큰 시퀀스를 next-token prediction으로 학습하는 자체 LLM이다.
GPT 계열 decoder-only 구조이며, 음악 도메인 특성에 맞춰 RoPE/RMSNorm/SwiGLU 등
LLaMA·Mistral 계보의 안정적 컴포넌트를 채택했다.

### 핵심 흐름
```
MIDI 파일 → 토큰 시퀀스 (REMI 계층) → MidiGPT (50M, 12층) → 다음 토큰 → 디코드 → MIDI
```

---

## 1. 파라미터 사양

| 항목 | 값 | 비고 |
|------|----|----|
| 총 파라미터 | ~50M | 실제 ≈ 50.x M (vocab 448 기준) |
| `n_layer` | 12 | Transformer 블록 수 |
| `n_head` | 12 | Attention head 수 |
| `n_embd` | 576 | 임베딩 차원 |
| `head_dim` | 48 | n_embd / n_head |
| `n_inner` | 2304 | FFN 내부 차원 (= 4 × n_embd) |
| `block_size` | 2048 | 최대 컨텍스트 길이 (토큰) |
| `vocab_size` | 448 | (후술 토크나이저 명세 참조) |

**코드 위치**: `midigpt/model/config.py:10-44`

### 정규화 / 활성화
- `RMSNorm` (eps=1e-6) — LayerNorm 대체
- `SwiGLU` — GELU 대체, hidden = 2/3 × n_inner (64 단위 정렬)
- Pre-norm residual 구조

### 임베딩 / 위치 인코딩
- 토큰 임베딩: `nn.Embedding(vocab_size, n_embd)`
- 위치 인코딩: **RoPE (Rotary Position Embeddings)**, theta=10000.0
- 가중치 결합 (`weight_tying=True`): 입력 임베딩과 출력 head가 같은 weight 공유 → 약 250K 파라미터 절약

### 정규화 (Regularization)
| 항목 | 기본값 |
|------|--------|
| `dropout` | 0.1 |
| `attn_dropout` | 0.1 |
| `resid_dropout` | 0.1 |
| `bias` | False (Linear 레이어 bias 제거) |

---

## 2. Attention 구조

**코드 위치**: `midigpt/model/transformer.py:72-171`

### 동작 규칙
- Multi-Head Self-Attention (MHA) — Q/K/V/O 각각 독립 projection
- RoPE를 Q, K에 곡선 방식으로 적용 (`apply_rope`)
- PyTorch 2.0+ `F.scaled_dot_product_attention` 사용 → FlashAttention 자동 활성화
- 구버전 PyTorch fallback: 수동 attention + 인과 마스크

### KV 캐시 ✅
**코드 위치**: `midigpt/model/transformer.py:89-171, 335-427`

- 학습/일반 forward: prefill 모드 (전체 시퀀스 한 번에 처리)
- 추론 incremental decode: T==1, past_kv 재사용
- Cache overflow 시 자동 re-prefill (block_size 제한)

```
past_kv: Tuple[K, V], shape (B, n_head, T_past, head_dim)
new_token → KV 새로 계산 → past와 concat → 새 KV 반환
```

---

## 3. Transformer Block

**코드 위치**: `midigpt/model/transformer.py:200-219`

```
x → RMSNorm → Attention → +residual
  → RMSNorm → SwiGLU FFN → +residual → x'
```

### 초기화 전략
- 모든 Linear: `N(0, 0.02)`
- residual projection (`o_proj`, `down_proj`): `N(0, 0.02 / sqrt(2 * n_layer))` — 잔차 누적 안정화

---

## 4. LoRA 핫스왑

**코드 위치**: `midigpt/training/lora.py`

### 동작 규칙
- LoRA 어댑터: rank=16~32 (config 기본 32)
- Target modules: `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`
- 런타임 hot-swap: `MidiGPTInference.load_lora(name, path)`

### 의존성
- ⚠️ Base model의 vocab_size, n_embd, n_layer, n_head 변경 시 모든 LoRA 폐기 필수

---

## 5. 검증 항목

### Forward 정합성
- [x] `model(idx)` shape: `(B, 1, V)` (마지막 토큰만)
- [x] `model(idx, targets=labels)` 시 loss 반환 (PAD ignored)
- [x] KV cache 사용/미사용 출력 일치 (수치 오차 1e-5 이내)

### 메모리
- `block_size=2048`, `batch=16`, FP16 → VRAM 약 8~10GB
- KV cache full: `12 × 2 × B × 12 × 2048 × 48 × 2바이트 ≈ B × 56MB`

---

## 6. 호환성

| 변경 | 등급 | 영향 |
|------|------|------|
| `n_layer`, `n_head`, `n_embd` 변경 | 🔴 | 체크포인트 폐기, LoRA 폐기 |
| `vocab_size` 변경 | 🔴 | 임베딩 행렬 shape 변경, 데이터 재토큰화 |
| `block_size` 증가 | 🟠 | RoPE 재계산, 짧은 시퀀스는 호환 |
| `dropout` 변경 | 🟢 | 추론 시 영향 없음 |
| `weight_tying` 변경 | 🟠 | 출력 head 별도 학습 필요 |
| KV cache on/off | 🟢 | 출력 동일, 속도만 차이 |

---

## 7. 향후 개선 후보

| 항목 | 등급 | 비고 |
|------|------|------|
| GQA (Grouped Query Attention) | 🟠 | KV 메모리 1/4, 변환 후 fine-tune 필요 |
| Hierarchical / Mamba 하이브리드 | 🔴 | 8K+ 컨텍스트, 처음부터 |
| MoE | 🔴 | 장르별 expert |
| ALiBi 추가 | 🟠 | RoPE 외 길이 외삽 |

상세는 [MidiGPT_개선로드맵_명세.md](MidiGPT_개선로드맵_명세.md) 참조.
