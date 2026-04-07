# MidiGPT — 원격 학습 가이드 (친구 디바이스용)

> 이 문서는 친구/협력자의 GPU 머신에서 MidiGPT를 처음부터 학습하고
> 자가 강화학습 사이클까지 돌리는 전체 절차를 한국어로 정리한 것입니다.
>
> 작성: 2026-04-07
> 대상 독자: GPU 있는 친구 (Python 경험 있음)

---

## 0. 개요 — 학습 흐름 두 단계

```
[1차: 사전학습 (1번만)]
midi_data/  →  CLM (next-token prediction)  →  midigpt_base.pt
                                                midigpt_ema.pt   ⭐ 배포 권장

[2차: 강화학습 사이클 (반복 가능)]
midigpt_ema.pt
       ↓
   변주 생성  →  output/*.mid
       ↓
   자동 리뷰  →  reviews/*.json   (스케일/벨로시티/리듬/엔트로피 룰 기반)
       ↓
   DPO 페어 빌드 → midigpt/dpo_pairs/*.json   (chosen ≥80, rejected <60)
       ↓
   DPO 학습  →  lora_checkpoints/   (강화된 LoRA 어댑터)
       ↓
   ↩  다시 변주 생성... (3~5 사이클 후 사람 청취 검증)
```

| 단계 | 라벨/평가 | 자동? | 1번만? |
|------|----------|-------|-------|
| 1차 사전학습 | 불필요 (self-supervised) | ✅ 완전 자동 | ⭐ 1번만 (또는 새 데이터 추가 시) |
| 2차 강화 | reviewer 자동 평가 | ✅ 완전 자동 | ⚠️ 사이클 반복 가능 |

⚠️ **중요**: 자동 reviewer는 **룰 기반**이라 음악적 깊이 한계가 있습니다.
3~5 사이클마다 사람이 직접 들어보고 판단해야 합니다.

---

## 1. 친구 디바이스 — 환경 세팅 (1회만)

### 1.1 하드웨어 권장

| GPU | batch_size | grad_accum | 10 epoch 학습 시간 |
|-----|-----------|-----------|----|
| RTX 4090 (24GB) | 32 | 2 | ~12-24h |
| RTX 3090 (24GB) | 24 | 2 | ~16-30h |
| RTX 4070 (12GB) | 12 | 4 | ~24-48h |
| RTX 3060 (12GB) | 8 | 4 | ~36-72h |
| RTX 3050 (8GB) | 4 | 8 | ~72h+ |
| CPU only | 2 | 8 | 비현실적 |

### 1.2 Python 환경

```bash
# Python 3.10 이상 (3.13 권장)
python --version          # 확인

# repo 클론
git clone https://github.com/fpsjjang97-boop/ableton.git
cd ableton

# 가상환경
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
# source venv/bin/activate
```

### 1.3 PyTorch (GPU 빌드 — 중요)

**먼저 PyTorch를 GPU 빌드로 설치**한 다음 나머지 의존성을 설치하세요.

```bash
# CUDA 12.1 (최신 RTX 시리즈)
pip install torch --index-url https://download.pytorch.org/whl/cu121

# 또는 CUDA 11.8 (구버전)
pip install torch --index-url https://download.pytorch.org/whl/cu118

# CPU only (비권장)
pip install torch
```

### 1.4 나머지 의존성

```bash
pip install -r requirements.txt
```

⚠️ requirements.txt의 `torch`는 이미 설치되어 있으면 건너뜁니다.

### 1.5 sanity check

```bash
python scripts/setup_check.py
```

8개 항목이 모두 ✅ 또는 ⚠ 으로 나오면 OK. ❌ 가 있으면 그것부터 해결하세요.

---

## 2. 데이터 받기

```bash
git pull origin main
```

확인:
```bash
ls midi_data/
ls "TEST MIDI/"
```

50+ MIDI가 보이면 됩니다. 더 늘어날 수 있어요 (동업자가 계속 push).

---

## 3. 1차 — 사전학습

**가장 간단한 올인원 (권장):**
```bash
python -m midigpt.training.train_pretrain \
    --data_dir ./midigpt_data \
    --epochs 10 \
    --batch_size 16 \
    --ema --ema_decay 0.999
```

> ⚠️ `midigpt_data/` 가 없으면 먼저 augment + tokenize 부터:
> ```bash
> python -m midigpt.pipeline --midi_dir ./midi_data --epochs 10
> ```
> 이게 augment → tokenize → train 까지 다 합니다.

### 진행 상황 모니터링

다른 터미널에서:
```bash
# Linux/Mac
tail -f checkpoints/train_log.jsonl

# Windows PowerShell
Get-Content checkpoints/train_log.jsonl -Wait -Tail 20
```

목표 지표:
- Train loss: 5.0 → **1.5 이하** 목표
- Val loss: train loss × 1.5 이내 (이 값을 넘으면 overfit, early stop이 자동 종료)

### 결과 파일

```
checkpoints/
├── midigpt_latest.pt    # 최근 epoch
├── midigpt_best.pt      # val loss 최소
├── midigpt_base.pt      # 학습 종료 (배포)
├── midigpt_ema.pt       # ⭐ EMA 가중치 (배포 권장)
└── train_log.jsonl      # 학습 로그
```

---

## 4. 2차 — 강화학습 사이클 (자동)

1차가 끝나면 자가 강화학습 루프 스크립트 한 번으로 2차 시작:

```bash
python scripts/run_self_improvement_loop.py \
    --base_model ./checkpoints/midigpt_ema.pt \
    --cycles 3 \
    --variants_per_song 3
```

이 한 줄이 사이클당 다음을 자동 수행:

1. **변주 생성**: `midi_data/` 의 모든 MIDI에 대해 3개씩 변주 → `output/`
2. **자동 리뷰**: reviewer가 각 변주를 채점 → `reviews/*.json`
3. **DPO 페어 빌드**: 점수≥80=chosen, <60=rejected → `midigpt/dpo_pairs/*.json`
4. **DPO 학습**: chosen/rejected 페어로 LoRA fine-tune → `lora_checkpoints/`

3 사이클 = 위 4단계가 3번 반복.

### 옵션 조절

```bash
# 사이클 수 (기본 3)
--cycles 5

# 곡당 변주 개수 (기본 3, 더 많을수록 페어 풍부)
--variants_per_song 5

# 디버깅 — 처음 N개 곡만
--limit 10

# 샘플링 옵션 (Phase 1 추가)
--temperature 0.9
--repetition_penalty 1.1
--no_repeat_ngram_size 4

# DPO 학습 옵션
--dpo_epochs 3
--dpo_batch_size 4

# 페어가 이만큼 모이기 전엔 DPO 스킵 (기본 10)
--min_pairs 20
```

### 로그

`self_improvement_log.jsonl` 에 사이클별 결과가 기록됩니다.

```bash
# Linux/Mac
cat self_improvement_log.jsonl | python -m json.tool

# Windows
type self_improvement_log.jsonl
```

---

## 5. 사람 청취 검증 (3~5 사이클마다 필수)

### 들어볼 파일

```
output/cycle3_*.mid       # 가장 최근 사이클의 변주
```

### 검사 포인트
- [ ] 자동 점수 80+가 진짜 좋은가?
- [ ] 자동 점수 60-가 진짜 나쁜가?
- [ ] 룰에 끼워 맞춰진 "교과서적이지만 재미없는" 패턴이 늘었나?
- [ ] 음악적 다양성이 줄었나?

### 사람이 직접 페어 만들기 (옵션, 권장)

자동 reviewer 외에 사람이 직접 평가한 페어를 추가하면 품질이 훨씬 올라갑니다.
방법은 `midigpt/build_dpo_pairs.py`를 참고해 직접 JSON 작성:

```json
{
    "prompt": [<메타 토큰 IDs>],
    "chosen": [<좋은 변주 토큰 IDs>],
    "rejected": [<나쁜 변주 토큰 IDs>],
    "metadata": {"source": "human", "rater": "친구이름"}
}
```

이걸 `midigpt/dpo_pairs/human_*.json` 로 저장 후 다시 DPO 학습을 돌리면 됩니다.

---

## 6. 학습한 모델 공유 방법

⚠️ git에는 모델 weights(`*.pt`)를 push할 수 없습니다 (`.gitignore` 차단).

### 권장 방법: Hugging Face Hub

```bash
pip install huggingface_hub
huggingface-cli login    # access token 입력

# 업로드
huggingface-cli upload <user>/midigpt-checkpoints \
    checkpoints/midigpt_ema.pt \
    midigpt_ema.pt
```

다운로드 (다른 사람):
```bash
huggingface-cli download <user>/midigpt-checkpoints midigpt_ema.pt \
    --local-dir ./checkpoints
```

### 대안

| 방법 | 장점 | 단점 |
|------|------|------|
| Hugging Face Hub | 무료, 버전 관리 | 계정 필요 |
| Google Drive 공유 링크 | 가장 쉬움 | 버전 관리 없음 |
| AWS S3 / GCS | 안정적 | 유료 |
| Git LFS | git 통합 | GitHub 무료 1GB |
| WeTransfer | 빠름 | 만료됨 |

---

## 7. 자주 묻는 질문

### Q1. CUDA OOM (Out of Memory) 에러
```bash
# batch_size 줄이고 grad_accum을 그만큼 늘리기
python -m midigpt.training.train_pretrain \
    --batch_size 4 --grad_accum 16 \
    --epochs 10 --ema
```

### Q2. Loss가 발산함 (NaN, inf)
- `--max_lr` 1e-4로 낮추기
- `--grad_clip 0.5` 강화
- `--fp16` 끄고 fp32로 돌리기

### Q3. DPO 학습 시 페어가 0개
- `output/`에 변주가 충분히 있는지
- reviewer 점수가 모두 60~80 사이에 몰려 있으면 페어 분리 안 됨
- `--variants_per_song`을 5~10으로 늘려서 다양한 결과 만들기
- 또는 `midigpt/build_dpo_pairs.py` 의 `CHOSEN_THRESHOLD`/`REJECTED_THRESHOLD` 조정

### Q4. reviewer가 느림
- 반복문이라 멀티프로세스 추가 가능 (TODO). 현재는 그냥 기다리세요.

### Q5. 학습이 너무 오래 걸림
- 데이터 양에 비례. 1500곡 기준 RTX 3060 36시간, RTX 4090 12시간
- 사이클 도는 데는 더 짧음 (DPO는 페어 100개 기준 1~2시간)

---

## 8. 절대 하지 말 것 ⚠️

1. **`midigpt/tokenizer/vocab.py` 수정 절대 금지** → 모든 학습 데이터/모델 무효화
2. **vocab에 토큰 중간 삽입 금지** → 새 토큰은 무조건 마지막에 append
3. **체크포인트(`*.pt`) git push 금지** → 저장소 폭발
4. **`midigpt_pipeline/augmented`, `midigpt_pipeline/tokenized` push 금지** → 54MB+ 폭발 (이미 .gitignore 처리됨)
5. **자동 reviewer만으로 10+ 사이클 무한 반복 금지** → 룰에 과적합되어 음악성 저하

---

## 9. 빠른 실행 예시 (전체 흐름)

친구가 받은 다음, 한 번에:

```bash
# 1) 환경
git clone https://github.com/fpsjjang97-boop/ableton.git
cd ableton
python -m venv venv && venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt

# 2) 점검
python scripts/setup_check.py

# 3) 1차 사전학습 (올인원, EMA 활성)
python -m midigpt.pipeline --midi_dir ./midi_data --epochs 10

# 4) 2차 강화학습 사이클 (3 사이클)
python scripts/run_self_improvement_loop.py \
    --base_model ./checkpoints/midigpt_ema.pt \
    --cycles 3 --variants_per_song 3

# 5) 결과 청취
ls output/cycle3_*.mid

# 6) 모델 공유
huggingface-cli upload <user>/midigpt-checkpoints \
    checkpoints/midigpt_ema.pt
```

---

## 9.5 보너스 — 악보 이미지로도 입력하기 (sheet2midi)

`agents/sheet2midi.py` 는 SOTA 오픈소스 OMR 모델인 **SMT++** (Sheet Music
Transformer ++, MIT, antoniorv6/SMT-plusplus, 21.4M params) 를 래핑한
에이전트입니다. 악보 사진/PDF 페이지를 받아서 MIDI로 변환하고, 그 자리에서
바로 MidiGPT 변주까지 만들 수 있습니다.

### 9.5.1 추가 설치 (선택)

기본 학습 파이프라인에는 **불필요**합니다. 악보 입력 기능을 쓸 때만 설치:

```bash
# 1) SMT++ (PyPI에 없음, 소스에서 설치)
git clone https://github.com/antoniorv6/SMT-plusplus.git
cd SMT-plusplus
pip install -e .
cd ..

# 2) kern → MIDI 변환기
pip install music21

# 3) 이미지 로드
pip install opencv-python
```

> ⚠️ 첫 실행 시 HuggingFace에서 `antoniorv6/smt-camera-grandstaff` 가중치
> (~85MB) 를 자동 다운로드합니다. 인터넷 필요.

### 9.5.2 사용법 — 악보 → MIDI

```bash
python -m agents.sheet2midi \
    --image score.png \
    --output ./output/score.mid
```

### 9.5.3 사용법 — 악보 → MIDI → MidiGPT 변주 (한 번에)

```bash
python -m agents.sheet2midi \
    --image score.png \
    --output ./output/score.mid \
    --vary \
    --base_model ./checkpoints/midigpt_ema.pt \
    --variation_output ./output/score_var.mid \
    --style jazz \
    --tempo 120
```

### 9.5.4 사용법 — Python API

```python
from agents.sheet2midi import Sheet2MidiAgent

agent = Sheet2MidiAgent()  # 기본: piano-only checkpoint

# 악보 → MIDI만
midi_path, transcription = agent.transcribe_to_midi(
    "score.png", "output/score.mid"
)
print("OMR text:\n", transcription.kern_text)

# 악보 → MIDI → MidiGPT 변주
result = agent.transcribe_and_vary(
    image_path="score.png",
    midi_output_path="output/score.mid",
    variation_output_path="output/score_var.mid",
    midigpt_base_model="./checkpoints/midigpt_ema.pt",
    meta_style="jazz",
    repetition_penalty=1.1,
    no_repeat_ngram_size=4,
)
```

### 9.5.5 한계
- 기본 체크포인트는 **피아노 악보 전용** (smt-camera-grandstaff). 오케스트라/멀티 악기 악보는 인식률 낮음
- 손글씨 / 저해상도 / 비뚤어진 사진은 OMR 결과가 깨질 수 있음 (`music21` parse 실패 → 명확한 에러 메시지)
- 다른 SMT 체크포인트는 `--model antoniorv6/<other-name>` 으로 교체 가능

---

## 10. 참고 문서

- 표준 명세 INDEX: [`docs/spec/MidiGPT_표준명세_INDEX.md`](spec/MidiGPT_표준명세_INDEX.md)
- 학습 파이프라인: [`docs/spec/MidiGPT_학습파이프라인_명세.md`](spec/MidiGPT_학습파이프라인_명세.md)
- 추론 엔진: [`docs/spec/MidiGPT_추론엔진_명세.md`](spec/MidiGPT_추론엔진_명세.md)
- 데이터 파이프라인: [`docs/spec/MidiGPT_데이터파이프라인_명세.md`](spec/MidiGPT_데이터파이프라인_명세.md)
- 개선 로드맵: [`docs/spec/MidiGPT_개선로드맵_명세.md`](spec/MidiGPT_개선로드맵_명세.md)

---

질문 있으면 아래로:
- GitHub Issues: https://github.com/fpsjjang97-boop/ableton/issues
