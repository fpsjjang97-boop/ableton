# 재학습 실행 가이드 (Python 3.11.9 + torch 환경에서)

> 작성: 2026-04-09
> 실행 환경: 본인의 RTX 4080 + Python 3.11.9 + torch 2.5.1+cu121 환경
> 전제: `_classify_track` 수정 + audit 통과 + round-trip 40/40 통과 완료

---

## 왜 재학습이 필요한가

2026-04-09 에 `midigpt/tokenizer/encoder.py::_classify_track` 을 수정했습니다:
- 이전: guitar/strings/brass/woodwind/vocal 카테고리가 거의 사용되지 않음 (대부분 `accomp` / `pad` 로 collapse)
- 이후: 14개 카테고리 전체가 올바르게 사용됨
- 40곡 audit 결과: 12개 카테고리 활성, accomp 10.7%, strings 25.6%, guitar 11.2%

이 변경으로 **토큰 시퀀스의 분포가 근본적으로 달라졌습니다**. 기존 `checkpoints/midigpt_ema.pt` 는 잘못된 분포 위에서 학습됐으므로 쓸모가 없습니다. 새로 학습해야 합니다.

---

## 실행 순서

### 1. Git pull (최신 상태 받기)

```bash
cd C:\Users\USER\ableton    # 또는 본인의 clone 경로
git pull origin main
```

확인: `git log -1 --oneline` 결과에 2026-04-09 Day 1 커밋이 보여야 함.

### 2. 현재 pipeline 캐시 비우기

```bash
# Windows (cmd)
rmdir /s /q midigpt_pipeline
rmdir /s /q reviews
rmdir /s /q output

# 또는 Git Bash
rm -rf midigpt_pipeline reviews output
```

**⚠️ `checkpoints/` 는 지우지 마세요**. 이전 모델 비교용으로 보존.

### 3. 검증 테스트 먼저 실행 (약 1분)

```bash
# 분류기 회귀 테스트
python test_classifier.py
# 기대: 53 passed, 0 failed

# 분류 분포 감사
python tools/audit_track_classification.py --csv audit_after_fix.csv
# 기대: [PASS] Track classification looks healthy

# Round-trip 테스트
python test_roundtrip.py --all
# 기대: 40 PASS / 0 FAIL
```

이 3개가 모두 통과하지 않으면 재학습 진행하지 마세요. 먼저 원인 파악 필요.

### 4. 재토큰화 + 사전학습 (약 18-30분)

```bash
python -m midigpt.pipeline --midi_dir ./midi_data --epochs 10
```

이 명령은 다음을 자동 수행합니다:
1. 증강 (`midigpt/augment_dataset.py`): 40곡 → ~480 파일
2. 토큰화 (`midigpt/tokenize_dataset.py`): MIDI → `.npy`
3. 학습 (`midigpt/training/train_pretrain.py`): 10 epoch

학습 도중 출력 예상:
```
Device: cuda
GPU: NVIDIA GeForce RTX 4080
VRAM: 17.2 GB
...
Epoch 1:  train_loss=1.234  val_loss=2.456  ...
Epoch 2:  train_loss=0.987  val_loss=2.123  ...
...
```

### 5. 학습 결과 확인

학습 종료 시점의 로그에서 다음을 체크:

```
최종 Train Loss: ???
최종 Val Loss:   ???
Train/Val Gap:   ???
```

**기대 결과** (가설):

| 시나리오 | gap | 해석 |
|---------|-----|------|
| **A. 분류기가 주병목이었음** | 1.0 - 1.5 | 매우 긍정. 데이터 수집 없이도 의미 있는 출력 가능 |
| **B. 분류기 + 데이터 부족 모두** | 1.5 - 2.0 | 긍정. 데이터 추가하면 더 개선 |
| **C. 데이터 부족이 주병목** | 2.0 - 2.5 | 분류기 수정 효과 부분적. 데이터 1500곡 수집 필요 |
| **D. 다른 숨은 원인** | > 2.5 | 추가 진단 필요 (토크나이저 / 학습 루프) |

이전: **Train 0.117 / Val 2.755 / Gap 2.638**

### 6. 생성 결과 청취 비교

```bash
python test_generate3.py
# 또는
python -c "
from midigpt.inference.engine import MidiGPTInference, InferenceConfig
from midigpt.tokenizer.encoder import SongMeta

inf = MidiGPTInference(InferenceConfig(model_path='./checkpoints/midigpt_ema.pt'))
variations = inf.generate_variation(
    midi_path='midi_data/CITY POP 105 4-4 ALL.mid',
    meta=SongMeta(key='C', style='pop', section='chorus', tempo=105),
    num_return_sequences=3,
    min_new_tokens=256,
    temperature=0.9,
)
print(f'Got {len(variations)} variations')
for i, v in enumerate(variations):
    print(f'  Variation {i+1}: {len(v)} notes')
"
```

DAW 에서 `output/` 폴더의 결과물을 열어서 청취:
- 파일 크기 비교 (이전 ~2KB → 개선 후 목표 5KB+)
- 트랙 다양성 (이전 대부분 accomp → 이후 guitar/strings/bass/drums 다양하게)
- 음악적 구조 (이전 노트 몇 개 → 이후 멜로디/화성 있음)

### 7. 결과 저에게 공유

재학습 완료 후 저에게 다음을 공유해 주세요:

1. **학습 로그 마지막 10줄** (train_loss, val_loss, gap, epoch 수)
2. **생성 결과 1개 샘플의 DAW 스크린샷** 또는 `.mid` 파일 전체 크기 + 노트 수
3. **본인의 청취 평가** (1-5 스케일: 1=소음, 5=완전 음악)

이 결과에 따라 Sprint 다음 단계가 결정됩니다:
- 시나리오 A/B → Week 2 본격 진입 (JUCE + LoRA 학습 + 외부 패널)
- 시나리오 C → 데이터 수집 우선순위 상향 (Lakh 통합 가속)
- 시나리오 D → 제가 추가 코드 진단

---

## 문제 해결

### "No module named 'torch'"
→ 본인의 Python 3.11.9 venv 가 활성화되지 않음. venv activate 먼저.

### "CUDA out of memory"
→ `--batch_size 8` 로 낮춰서 재시도.
```bash
python -m midigpt.training.train_pretrain --batch_size 8 --grad_accum 8 --ema
```

### "FileNotFoundError: midigpt_pipeline/tokenized/tokens"
→ pipeline 의 증강/토큰화 단계가 실패. 개별 실행:
```bash
python -m midigpt.augment_dataset --input_dir ./midi_data --output_dir ./midigpt_pipeline/augmented
python -m midigpt.tokenize_dataset --input_dir ./midigpt_pipeline/augmented --output_dir ./midigpt_pipeline/tokenized
```

### 생성 결과가 여전히 이상함
→ 저에게 즉시 알려주세요. 분류기 수정이 부분 효과만 냈다는 뜻이고, 토크나이저 내부를 추가 점검해야 합니다.

---

## 시간 예상

| 단계 | 소요 시간 |
|------|-----------|
| git pull | 10초 |
| 캐시 정리 | 10초 |
| 검증 테스트 3개 | 1분 |
| 증강 + 토큰화 | 2-5분 |
| 학습 10 epoch | 15-25분 |
| 결과 청취 | 5분 |
| **총** | **약 25-35분** |

---

## 재학습 완료 후 Week 1 나머지 작업

(본인이 동시 진행 가능)

1. **CMake 설치** (5분) — VS2022 Installer → "C++ CMake tools for Windows" 컴포넌트, 또는 https://cmake.org/download/
2. **JUCE 확인**: `juce_daw_clean/external/JUCE/CMakeLists.txt` 존재 (이미 clone 됨, 110MB)
3. **빌드 시도**: `cd juce_daw_clean && build.bat`
4. **Cubase 에 로드**: Studio → VST Plug-in Manager → Update → "MidiGPT" 확인

이 4개가 모두 통과하면 **Week 1 게이트 통과 조건 달성**.

---

## 변경 이력

- 2026-04-09: 초판. 분류기 수정 후 재학습용 가이드.
