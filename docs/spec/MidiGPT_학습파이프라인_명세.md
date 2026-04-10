# MidiGPT — 학습 파이프라인 명세

> 사전학습 / SFT / DPO 등 모든 학습 단계의 표준 명세
> 분류: LLM / 모델 영역
> 코드: `midigpt/training/`

---

## 개요

MidiGPT의 학습 파이프라인은 3단계 + EMA 안정화로 구성된다.

```
Phase A: Pre-training (CLM)
   ↓
Phase B: SFT (LoRA, 원본↔변주 쌍)
   ↓
Phase C: DPO (선호도 학습, 좋은/나쁜 변주)
```

각 단계는 독립 실행 가능하며, 하위 단계는 상위 단계의 체크포인트를 입력으로 받는다.

---

## 1. 사전학습 (Pre-training, CLM)

**코드 위치**: `midigpt/training/train_pretrain.py`

### 목표
다음 토큰 예측 (Causal Language Modeling)
- Loss: `nn.CrossEntropyLoss(ignore_index=0)` — `<PAD>` 무시
- Loss는 model.forward() 내부에서 계산 (`midigpt/model/transformer.py:321-327`)

### 옵티마이저 / 스케줄러
- **AdamW**: betas=(0.9, 0.95), eps=1e-8, fused=True (CUDA)
- **Weight decay 분리**: dim≥2 파라미터는 0.1, scalar/bias 0.0
- **LR 스케줄**: cosine + warmup
  - max_lr=3e-4, min_lr=3e-5
  - warmup = min(args.warmup_steps, total_steps/10)

### 정밀도
- bf16/fp16 (mixed precision, 기본 fp16 on CUDA)
- `torch.amp.GradScaler` 사용

### 데이터
- 입력: 토큰화된 `.npy` 파일
- `--data_dir` 기본값: `./midigpt_pipeline/tokenized` (pipeline.py 출력 경로와 일치, 2026-04-08)
- 자동 경로 탐색: `{dir}/tokens/` → `{dir}/` → `{dir}/tokenized/tokens/` 순서 (2026-04-08)
- `MidiDataset(mode="pretrain", block_size=2048)`
- 90/10 train/val split (seed=42)
- `MidiCollator`로 배치 패딩

### 학습 파라미터 (기본값)

| 항목 | 기본값 | 비고 |
|------|--------|------|
| `epochs` | 10 | |
| `batch_size` | 16 | RTX 4090: 32, RTX 3060: 8 |
| `block_size` | 2048 | |
| `grad_accum` | 4 | effective batch = batch × 4 |
| `grad_clip` | 1.0 | |
| `dropout` | 0.1 | |
| `weight_decay` | 0.1 | |
| `early_stop_patience` | 5 | val loss 미개선 epoch 수 |

### 체크포인트
- `midigpt_latest.pt` — 최근 epoch
- `midigpt_best.pt` — val loss 최소
- `midigpt_epoch{N}.pt` — `save_every` 주기
- `midigpt_base.pt` — 학습 종료 시 weights only (배포용)
- `midigpt_ema.pt` — EMA 활성 시 EMA copy weights only ✅ Phase 1 추가

### EMA (Exponential Moving Average) ✅ Phase 1
**코드 위치**: `midigpt/training/ema.py`

#### 동작 규칙
- `--ema` 플래그 활성화 시 활성
- 매 optimizer step 후 shadow weight 업데이트:
  `shadow = decay × shadow + (1 - decay) × param`
- Validation 시: `store → copy_to → 평가 → restore` 패턴
- 학습 종료 시 `midigpt_ema.pt` 별도 저장

#### 파라미터
- `--ema_decay` 기본 0.999
- 짧은 학습: 0.99
- 긴 학습 (>10K step): 0.9999

#### 호환성
- 🟢 안전: 기존 체크포인트와 LoRA에 영향 없음
- EMA 미사용 시 동작 100% 동일

---

## 2. SFT (LoRA Supervised Fine-Tuning)

**코드 위치**: `midigpt/training/train_sft_lora.py`, `midigpt/training/lora.py`

### 목표
원본 ↔ 변주 쌍 학습. 입력에 `<SEP>` 토큰 삽입 후 변주 토큰 시퀀스 학습.

### LoRA 구성
- rank: 16~32 (config 기본 32)
- target_modules: `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`
- alpha: 32

### 데이터 요구사항
- 원본 MIDI ↔ 변주 MIDI 쌍 200개+ 권장
- 형식: 같은 곡의 두 가지 해석/연주

### 호환성
- LoRA는 base 모델 vocab/dim/layer 변경 시 모두 폐기

---

## 3. DPO (Direct Preference Optimization)

**코드 위치**: `midigpt/training/train_dpo.py`

### 목표
인간 피드백 기반 선호도 학습. 보상 모델 없이 직접 선호 페어로 학습.

### Loss 공식
```
L_DPO = -log σ(β × (log π(y_w|x) - log π(y_l|x) - log π_ref(y_w|x) + log π_ref(y_l|x)))
```
- y_w: 선택된(좋은) 변주
- y_l: 거부된(나쁜) 변주
- π_ref: 기준 모델 (학습 시작 시 frozen)
- β: KL 정규화 강도

### 데이터 요구사항
- (프롬프트, chosen, rejected) 트리플 100쌍+ 권장
- 사람이 직접 평가한 쌍 권장

### DPO 페어 빌드 — Quantile Fallback ✅ 2026-04-08
**코드 위치**: `midigpt/build_dpo_pairs.py`

고정 임계값(CHOSEN≥80, REJECTED<60) 만으로는 점수가 39~77 구간에 몰릴 때 chosen이 0개가 되어 DPO가 영원히 SKIP되는 문제를 해결.

**동작 규칙**:
1. 고정 임계값(80/60) 우선 시도. 양쪽 3개 이상 모이면 기존 동작 100% 보존
2. 부족 시 **percentile 분할**: 상위 30% → chosen, 하위 30% → rejected
3. chosen 최소값 - rejected 최대값 < 5점이면 "구분 무의미"로 페어 0 반환 (안전장치)

```python
QUANTILE_FALLBACK = 0.30      # top 30% -> chosen, bottom 30% -> rejected
QUANTILE_MIN_GAP = 5.0        # chosen-rejected 점수차 최소 보장
QUANTILE_MIN_PER_BUCKET = 3   # 각 버킷 최소 3개 이상이어야 fallback 활성
```

### 위험 요소
- 🟡 chosen/rejected 페어 품질이 낮으면 모델 혼란
- 🟡 self-distillation (모델 자기 출력으로 페어 생성) 비율 50% 초과 시 distribution 좁아짐

---

## 4. 학습 실행 명령

### 사전학습
```bash
python -m midigpt.training.train_pretrain \
    --epochs 10 \
    --batch_size 16 \
    --ema                  # ✅ Phase 1 옵션
# --data_dir 생략 가능 (기본: ./midigpt_pipeline/tokenized, 2026-04-08)
```

### 올인원 파이프라인
```bash
python -m midigpt.pipeline --midi_dir "./TEST MIDI" --epochs 10
```

### 단계별 실행
```bash
# 1) 증강
python -m midigpt.augment_dataset --input_dir ./midi_data --output_dir ./augmented

# 2) 토큰화
python -m midigpt.tokenize_dataset --input_dir ./augmented --output_dir ./midigpt_data

# 3) 사전학습 (--data_dir 생략 시 ./midigpt_pipeline/tokenized 자동)
python -m midigpt.training.train_pretrain --epochs 10 --ema

# 4) SFT
python -m midigpt.training.train_sft_lora --data_dir ./pairs --base ./checkpoints/midigpt_base.pt

# 5) DPO
python -m midigpt.training.train_dpo --data_dir ./preferences --base ./checkpoints/midigpt_base.pt
```

---

## 5. 검증 항목

### Pre-training
- [x] Loss 곡선이 단조 감소 (warmup 후)
- [x] Val loss < train loss × 1.5 (overfit 감지)
- [x] gradient norm < grad_clip × 2 (exploding 감지)
- [ ] 토큰 perplexity 그룹별 출력 (chord/pitch/duration 분리)

### EMA
- [x] EMA val loss ≤ live val loss (대부분의 경우)
- [x] `midigpt_ema.pt` 저장 확인

### LoRA
- [x] 어댑터 로드 후 base 모델 forward 결과 확인
- [x] LoRA 활성화 전후 출력 차이 검증

---

## 6. 향후 개선 후보

| 항목 | 등급 | 비고 |
|------|------|------|
| Masked Music Modeling 추가 | 🟠 | infilling 능력, 양방향 학습 |
| Curriculum Learning | 🟡 | 짧은→긴 시퀀스 |
| Multi-task Pretraining | 🟠 | chord/key/section 동시 예측 |
| GRPO (DeepSeek-R1) | 🟠 | DPO 대체, 더 안정적 |
| Span Corruption (T5) | 🟠 | 편곡 능력 강화 |
| Loss Masking (메타 토큰) | 🟢 | 노트 예측에 집중 |
| Weighted Sampling | 🟡 | 희귀 장르 oversampling |
| Gradient Checkpointing | 🟢 | VRAM 절약 |
| DeepSpeed ZeRO | 🟢 | 큰 모델 학습 가능 |

상세 우선순위 → [MidiGPT_개선로드맵_명세.md](MidiGPT_개선로드맵_명세.md)
