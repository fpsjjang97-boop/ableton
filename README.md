# MidiGPT — MIDI AI Workstation

> 자체 MIDI 전용 LLM(MidiGPT 50M) + Cubase 15 표현력 + JUCE 통합 워크스테이션

[English README](README.en.md)

![Python](https://img.shields.io/badge/Python-3.13-blue)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-red)
![Model](https://img.shields.io/badge/Model-MidiGPT_50M-orange)
![Vocab](https://img.shields.io/badge/Vocab-448_tokens-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## 한 줄 요약

**MIDI 입력 → 자체 LLM이 음악 이론을 알고 변주를 생성 → DAW로 바로 사용**

- 50M 파라미터 자체 LLM (RoPE + RMSNorm + SwiGLU + KV cache)
- Cubase 15 표현력 (32 articulation, CC11/CC1/CC64, pitchbend, MPE-ready)
- 화성 마스킹 (생성 중 코드 스케일 외 음 자동 차단)
- LoRA 핫스왑 (스타일별 어댑터 교체)
- 멀티 에이전트 백엔드 + JUCE C++ 프론트엔드

---

## 표준 명세 문서

전체 설계는 [docs/spec/](docs/spec/) 폴더의 표준 명세를 참조하세요.

| 영역 | 문서 |
|------|------|
| 🧠 LLM | [아키텍처](docs/spec/MidiGPT_LLM_아키텍처_명세.md) · [토크나이저](docs/spec/MidiGPT_토크나이저_명세.md) · [학습](docs/spec/MidiGPT_학습파이프라인_명세.md) · [추론](docs/spec/MidiGPT_추론엔진_명세.md) |
| 🎵 음악 기능 | [화성 엔진](docs/spec/MidiGPT_화성엔진_명세.md) · [그루브 엔진](docs/spec/MidiGPT_그루브엔진_명세.md) · [AI 엔진](docs/spec/MidiGPT_AI엔진_명세.md) |
| 📊 데이터 | [데이터 파이프라인](docs/spec/MidiGPT_데이터파이프라인_명세.md) |
| 🎛️ 통합 | [앱 / 통합](docs/spec/MidiGPT_앱통합_명세.md) |
| 🚀 로드맵 | [개선 로드맵](docs/spec/MidiGPT_개선로드맵_명세.md) |
| 📑 INDEX | [표준 명세 INDEX](docs/spec/MidiGPT_표준명세_INDEX.md) |

---

## 모델 사양

| 항목 | 값 |
|------|----|
| 파라미터 | ~50M |
| 레이어 | 12 (decoder-only) |
| Head | 12 (head_dim 48) |
| 임베딩 | 576 |
| FFN | 2304 (SwiGLU) |
| 컨텍스트 | 2048 토큰 |
| Vocab | 448 토큰 (계층적 REMI) |
| 위치 인코딩 | RoPE (theta=10000) |
| 정규화 | RMSNorm |
| LoRA rank | 32 (q/k/v/o + gate/up/down) |

---

## 주요 기능

### 🧠 LLM (MidiGPT)
- ✅ 50M Decoder-Only Transformer
- ✅ KV 캐시 가속 추론 (Phase 1)
- ✅ Repetition Penalty (Phase 1)
- ✅ No-Repeat N-gram Block (Phase 1)
- ✅ Multi-Sample (`num_return_sequences`) (Phase 1)
- ✅ 화성 제약 마스킹 (코드 스케일 외 음 차단)
- ✅ LoRA 핫스왑
- ✅ EMA 체크포인트 (Phase 1)

### 🎵 음악 기능
- ✅ 코드 분석 (24개 quality, 슬래시 코드, 함수 라벨)
- ✅ 송 폼 감지 (intro/verse/chorus/bridge/outro 등 10개)
- ✅ 그루브 추출 + 7개 스윙 프리셋
- ✅ 14개 트랙 타입 (멜로디/베이스/드럼/현/금관/...)
- ✅ 32개 아티큘레이션 (Cubase 15 기반)
- ✅ 13개 다이나믹스 (ppp~fff + sfz/sfp 등)
- ✅ CC11 Expression / CC1 Modulation / CC64 Sustain / PitchBend

### 🎛️ 앱 / 통합
- ✅ Python core 엔진 (MIDI/하모니/그루브/AI/효과/신스)
- ✅ 멀티 에이전트 (Composer, Manager, Reviewer, Orchestrator)
- ✅ Audio2MIDI (Demucs + Basic Pitch)
- ✅ **Sheet2MIDI (악보 이미지 → MIDI, SMT++ 통합)** — `agents/sheet2midi.py`
- ✅ JUCE C++ 프론트엔드
- 🔶 부분: VST3/CLAP 호스팅 (계획됨)

---

## 빠른 시작

### 음악가
```bash
# MIDI 파일을 추가하고
git add "TEST MIDI/"
git commit -m "data: MIDI 학습 데이터 추가"
git push
```

### 개발자 — 학습
```bash
# 올인원 파이프라인 (증강 → 토큰화 → 학습)
python -m midigpt.pipeline --midi_dir "./TEST MIDI" --epochs 10

# EMA 활성화 (Phase 1, 권장)
python -m midigpt.training.train_pretrain \
    --data_dir ./midigpt_data \
    --epochs 10 \
    --ema --ema_decay 0.999
```

### 개발자 — 추론
```python
from midigpt.inference.engine import MidiGPTInference, InferenceConfig
from midigpt.tokenizer.encoder import SongMeta

inf = MidiGPTInference(InferenceConfig(
    model_path="./checkpoints/midigpt_ema.pt",   # EMA 권장
    lora_paths={"jazz": "./loras/jazz.pt"},
))

# Phase 1 추가 옵션
variations = inf.generate_variation(
    midi_path="input.mid",
    meta=SongMeta(key="C", style="jazz", section="chorus", tempo=120),
    num_return_sequences=3,         # 3개 후보 생성
    repetition_penalty=1.1,         # 모티프 무한 반복 방지
    no_repeat_ngram_size=4,         # 4-gram 차단
    use_kv_cache=True,              # O(N) 추론
)
```

---

## 프로젝트 구조

```
repo/
├── midigpt/                       # 자체 LLM
│   ├── model/
│   │   ├── config.py              # 50M 모델 설정
│   │   └── transformer.py         # RoPE + RMSNorm + SwiGLU + KV cache
│   ├── tokenizer/
│   │   ├── vocab.py               # 448 토큰 어휘 (Cubase 15 확장)
│   │   ├── encoder.py             # MIDI → 토큰
│   │   └── decoder.py             # 토큰 → MIDI
│   ├── training/
│   │   ├── train_pretrain.py      # 사전학습 (+ EMA, Phase 1)
│   │   ├── train_sft_lora.py      # LoRA SFT
│   │   ├── train_dpo.py           # DPO 선호도 학습
│   │   ├── lora.py                # LoRA 구현
│   │   └── ema.py                 # ✅ Phase 1: EMA
│   ├── inference/
│   │   └── engine.py              # 추론 엔진 (KV cache, 화성 마스킹, Phase 1)
│   ├── data/
│   │   └── dataset.py             # MidiDataset, MidiCollator
│   ├── augment_dataset.py         # 증강 (전조 + 트랙 드롭아웃)
│   ├── tokenize_dataset.py        # 토큰화
│   ├── pipeline.py                # 올인원
│   └── DATA_GUIDE.md              # 데이터 수집 가이드
├── app/
│   ├── core/                      # MIDI / 화성 / 그루브 / AI 엔진 등
│   └── ...
├── agents/
│   ├── composer.py
│   ├── manager.py
│   ├── reviewer.py
│   ├── orchestrator.py
│   ├── audio2midi.py              # Demucs + Basic Pitch
│   └── ableton_bridge.py
├── juce_app/                      # JUCE C++ 프론트엔드
├── docs/spec/                     # ✅ 표준 명세 문서 (BalloonFlow 양식)
├── tools/                         # 유틸리티 스크립트
├── TEST MIDI/                     # 동업자 업로드 영역
├── midi_data/                     # 학습용 MIDI
├── checkpoints/                   # 학습된 체크포인트
└── README.md (this file)
```

---

## 데이터 현황

| 항목 | 수치 |
|------|------|
| MAESTRO 2018 | 93곡 (클래식 피아노) |
| 동업자 업로드 | 11+ 곡 (J-POP, City Pop, Latin, Hiphop, Metal, House 등) |
| 총 원본 | 104+ 곡 |
| 증강 후 (x15) | ~1,560 곡 |
| **목표** | **2,000+ 원본** |

---

## 역할 분담

### 🎹 음악가 (동업자)
- DAW에서 곡 작업 → Type 1 MIDI export → Git push
- 장르 다양성 (팝, 재즈, 클래식, 라틴, 메탈 등)
- 드럼은 GM 매핑 준수
- CC 데이터 (서스테인/익스프레션) 포함 권장
- [DATA_GUIDE.md](midigpt/DATA_GUIDE.md) 참조

### 💻 개발자
- MidiGPT 아키텍처/학습/추론 파이프라인 운영
- 데이터 증강 → 토큰화 → 학습 → 모델 업데이트
- 앱 통합 및 배포

### 협업 흐름
```
음악가: MIDI 제작 → Git Push
                         ↓
개발자: 증강 → 토큰화 → 학습 → 모델 업데이트
                         ↓
음악가: 변주 결과 청취 → 피드백 (좋다/나쁘다)
                         ↓
개발자: DPO 학습에 반영 → 모델 개선
                         ↓
                      반복 (체급 상승)
```

---

## 진행 상황

### Phase 1 — 인퍼런스 / 학습 안정화 ✅
- ✅ 50M Transformer (KV cache 지원)
- ✅ 448 토큰 어휘 (Cubase 15 확장)
- ✅ KV cache 가속 추론
- ✅ Repetition Penalty / No-Repeat N-gram
- ✅ Multi-Sample (`num_return_sequences`)
- ✅ EMA 체크포인트
- ✅ 화성 제약 마스킹
- ✅ LoRA 핫스왑

### Phase 2 — 데이터 수집 ← **현재**
- 104곡 → 목표 2,000곡+
- 자동 품질 필터 계획
- Lakh MIDI 통합 검토 중 (필터링 필수)

### Phase 3 — Fine-tune로 신기능
- CFG (Classifier-Free Guidance)
- Multi-task Pretraining
- GRPO + Voice Leading reward

### Phase 4 — 메이저 재학습 (분기 단위)
- Vocab 확장 (Inversion, MPE, Tempo Curve, ...)
- GQA + Hierarchical / Mamba
- 텍스트 컨디셔닝 (CLAP-style)

상세 로드맵 → [docs/spec/MidiGPT_개선로드맵_명세.md](docs/spec/MidiGPT_개선로드맵_명세.md)

---

## 라이선스

MIT License
