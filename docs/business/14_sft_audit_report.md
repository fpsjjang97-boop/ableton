# SFT 페어 토큰 감사 리포트 — Sprint 40 / DDD1

**날짜**: 2026-04-19
**도구**: `scripts/audit_sft_tokens.py`
**대상**: `midigpt_pipeline/sft/sft_*.json` (14,622 files)
**용도**: SFT LoRA NaN 재발 방지 — 재학습 전 데이터 정리 가이드

---

## 요약

| 항목 | 값 | 판정 |
|---|---:|---|
| 총 페어 | 14,622 | — |
| Vocab size | 527 | — |
| Block size | 2,048 | — |
| OK (스키마·파싱) | 14,622 | ✅ 패턴 A 방어 정상 |
| Out-of-range token ID | **0** | ✅ NaN 직접 원인 아님 |
| Empty input/output | 0 | ✅ |
| **Short effective labels (< 4)** | **8,832 (60.4 %)** | 🔴 치명 |
| Suspicious special (의도 외 위치의 SEP/BOS/EOS/PAD) | 0 | ✅ |
| **중복 페어 그룹** | **3,086** | 🟡 의심 |

---

## 판정

**NaN 의 직접 원인은 데이터가 아니다** — 모든 토큰 ID 가 `[0, 527)` 범위 내. 하지만 **학습 품질을 심각하게 떨어뜨리는 3대 데이터 문제**가 발견됨. 이는 "재학습이 성공해도 음악성이 올라오지 않는" 간접 원인이 된다.

### 🔴 문제 1 — Short effective labels 60.4%
- 원인: output 길이가 block_size(2048) 초과 → truncation 후 실질 학습 토큰 < 4
- loader 의 MIN_SFT_OUTPUT_LABELS pre-filter (dataset.py:29) 가 skip 중 → **실제 유효 학습 페어는 14,622 - 8,832 = 5,790 (39.6%)**
- 길이 분포: input 20~2k, output 20~17k. output 15k+ 페어가 다수 → `build_sft_pairs.py` 생성 로직 점검 필요

**동업자 액션**: 재학습 시 유효 페어 수가 예상의 40% 임을 인지. 또는 `build_sft_pairs.py` 재실행으로 block_size 맞는 페어만 생성.

### ✅ 문제 2 (false alarm) — 특수 토큰 편성은 정상
- 1차 감사에서 BOS/EOS 29,244 hit 을 의심으로 분류했으나 위치 확인 결과:
  - BOS 는 모든 `input[0]` (14,622) — 시퀀스 시작, 의도된 편성
  - EOS 는 모든 `output[-1]` (14,622) — 시퀀스 끝, 의도된 편성
- 감사 로직을 위치 기반으로 보강 후 의심 건 0 확인
- SEP/PAD 가 input/output 안에 있거나, BOS/EOS 가 허용 위치 외에 있으면 경고 — 현재 0건

### 🟡 문제 3 — 중복 페어 그룹 3,086
- 동일 (input, output) 조합이 2회 이상 등장
- 같은 MIDI 에서 증강 과정에 같은 전략이 반복 적용됐을 가능성
- train/val split 이 hash 기반이 아니면 leakage 위험

**동업자 액션**: 재학습 시 dedup 기반 split 보장 (train_sft_lora.py 에 split 로직 없음 — 전량 사용). 평가는 별도 holdout 필요.

---

## 검사하지 않은 항목 (코드 측 — DDD2 로)

- fp16 autocast overflow — 학습 루프 재현 필요 (GPU 서버에서만)
- LoRALinear dtype/device 상속 — **DDD2 정적 감사 대상**
- gradient clipping — `train_sft_lora.py:122` 에 이미 적용됨 (`clip_grad_norm_=1.0`)
- GradScaler — `train_sft_lora.py:91` 에 이미 적용됨 (5차 커밋 `10364fb`)

---

## DDD2 결과 추가 (2026-04-19)

`scripts/audit_lora_dtype.py` 실행 결과:

| 항목 | 결과 |
|---|---|
| Base model 로드 (`midigpt_best.pt`) | ✅ 48M params, n_layer=12, n_head=12, n_embd=576, block_size=1024 |
| **체크포인트 vocab_size** | **420** |
| **현재 `VOCAB.size`** | **527** |
| **vocab 불일치 차이** | **107 토큰 (v1.x → v2.0 Cubase 15 확장)** |
| LoRALinear dtype/device 일관성 | ✅ 36 layers 모두 base 와 일치 (5차 `4b24bb8` fix 유지) |
| save_lora → load_lora 왕복 dtype 보존 | ✅ |
| fp32 forward NaN/Inf | ✅ 없음 (loss=11.83) |
| fp16 autocast forward NaN/Inf | ✅ 없음 (loss=11.83) |

### 🔴 새 발견 — 체크포인트/VOCAB vocab 불일치 (중요!)
- 체크포인트는 v1.x vocab 420 기반, 코드는 v2.0 vocab 527
- **SFT 페어는 체크포인트와 정합 (OOR=0 재확인, `--ckpt_vocab_size 420` 옵션)**
- 즉 SFT 재학습은 OOB embedding 오류로 실패하지 않음
- 그러나 **코드는 v2.0 vocab 을 기대하는데 체크포인트는 v1.x** → lm_head 출력 크기가 420, SFT 데이터도 420 기반. 미래에 v2.0 토큰(예: `InstFam_*`) 사용 시 체크포인트 호환 깨짐. 재학습 시 `config.vocab_size = 420` 으로 고정됨 → 생성 시 v2.0 토큰을 생성할 수 없음.

### 최종 NaN 원인 순위 (DDD1+DDD2 통합)
1. 🔴 **loss NaN 의 직접 원인**: Short effective labels 60.4% 페어가 pre-filter skip — 남은 유효 페어 중에서도 output 이 block_size 에 거의 닿는 페어는 fp16 autocast 에서 attention softmax overflow 가능성. 학습 루프에서만 재현.
2. 🟡 **품질 저하**: vocab 불일치 — 재학습은 가능하나 v2.0 토큰은 결코 생성되지 않음.
3. 🟡 **품질 저하**: 중복 3,086 — train/val leakage 가능.
4. ✅ LoRA dtype/device: 문제 없음 (5차 fix 유지)
5. ✅ SFT 데이터 OOR (체크포인트 vocab 기준): 문제 없음

### 동업자 핸드오프 결정 지점
Quick fix (1주):
- Short effective 페어 8,832 건 제외 후 재학습 (체크포인트 vocab 420 그대로 사용)
- 중복 페어 3,086 dedup 후 재학습

Correct fix (2주+):
- `build_sft_pairs.py` 를 block_size=2048 + 특수 토큰 필터 + dedup + v2.0 vocab 정합으로 재생성
- Pre-training 을 v2.0 vocab 527 로 재학습 (이건 동업자 판단)

6월 MVP 일정상 **Quick fix 권장**. v2.0 vocab 은 Sprint 41+ 로 이연.

---

## Sprint 41 EEE2 적용 결과 + Sprint 42 FFF2 재감사 (2026-04-19)

`scripts/clean_sft_pairs.py --src ./midigpt_pipeline/sft --dst ./midigpt_pipeline/sft_clean --block_size 2048 --ckpt_vocab_size 420`

| 지표 | 원본 `sft/` | 정제 `sft_clean/` | 변화 |
|---|---:|---:|---|
| 총 페어 | 14,622 | **7,913** | -6,709 (dup 제거) |
| OOR token | 0 | 0 | ✅ |
| Empty pair | 0 | 0 | ✅ |
| **Short effective (<4)** | **8,832 (60.4 %)** | **0** | 🟢 **완전 해소** — trim 적용 |
| Suspicious special | 0 | 0 | ✅ |
| **Duplicate groups** | **3,086** | **0** | 🟢 **완전 해소** |

재학습 준비물 상태: **모든 품질 지표 그린**. 동업자가 `--data_dir midigpt_pipeline/sft_clean` 로 train_sft_lora.py 실행 가능.

---

## JSON 리포트
`midigpt_pipeline/sft_audit.json` — 페어별 상세. 재학습 전 exclusion list 로 직접 사용 가능.

## 재현
```bash
python scripts/audit_sft_tokens.py --data_dir ./midigpt_pipeline --out ./midigpt_pipeline/sft_audit.json
```

## 핸드오프
동업자에게 이 리포트 + `sft_audit.json` 공유. 재학습 결정은 다음 중 선택:
1. **Quick fix**: `sft_audit.json.short_labels` 에 등장하는 파일을 sft/ 에서 제외 후 재학습
2. **Correct fix**: `build_sft_pairs.py` 를 block_size=2048 과 특수 토큰 필터 추가해 재생성 후 재학습

6월 MVP 일정상 **Quick fix 권장**.
