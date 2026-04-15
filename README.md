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
- ✅ `min_new_tokens` EOS 조기종료 방지 (2026-04-08)
- ✅ DPO quantile fallback — 점수 쏠림 시 자동 분위 분할 (2026-04-08)

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
    max_tokens=1024,                    # 기본 1024 (Phase 1: 512)
    min_new_tokens=256,                 # ✅ EOS 조기종료 방지
    num_return_sequences=3,             # 3개 후보 생성
    repetition_penalty=1.1,             # 모티프 무한 반복 방지
    no_repeat_ngram_size=4,             # 4-gram 차단
    use_kv_cache=True,                  # O(N) 추론
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

## 🚨 2026-04-09 ~ 04-10 주요 변경 — 동업자 필독

### TL;DR
1. `_classify_track` 에 치명적 버그가 있었음 — guitar/strings/brass/woodwind/vocal 카테고리가 실제로는 사용되지 않아, 모든 트랙이 `accomp` 나 `pad` 로 붕괴되어 학습되고 있었음
2. 수정 후 재학습 결과: **val_loss 2.755 → 0.2624, gap 2.638 → 0.091** (29배 개선)
3. 생성 결과: **1 track → 8 tracks, 5노트 → 218노트, 2초 → 126초**
4. `juce_app/` 는 Cubase 15 Ghidra 파생 코드가 섞여 있어 `juce_app_quarantine/` 로 격리됨
5. 새 DAW 코드는 `juce_daw_clean/` 에 JUCE VST3 Plugin 형태로 처음부터 작성 중
6. 6월 첫째 주 MVP 베타 출시 목표 8주 sprint 진행 중 → [09_8주_Sprint_6월데드라인.md](docs/business/09_8주_Sprint_6월데드라인.md)

### 각자 할 일

#### 🎹 작곡가 (음악가 동업자)

**즉시 (이번 주)**
1. **생성 결과 청취 검증** (가장 중요)
   ```bash
   git pull origin main
   # 아래 서버 기동 후 플러그인 없이 바로 테스트 가능
   python -m midigpt.inference_server --model ./checkpoints/midigpt_best.pt
   # 다른 터미널에서:
   curl -X POST http://127.0.0.1:8765/generate \
        -F "midi=@midi_data/CITY POP 105 4-4 ALL.mid" \
        -F "style=pop" -F "key=C" -F "tempo=105" \
        -F "min_new_tokens=256" -F "max_tokens=768" \
        -o test_gen.mid
   ```
   → `test_gen.mid` 를 Cubase에서 열어서 청취 후 다음 4가지 평가:
   - (a) 음악으로 인지되는가? (1-5)
   - (b) 입력(City Pop)의 장르가 느껴지는가? (1-5)
   - (c) 화성이 어색하지 않은가? (1-5)
   - (d) 8개 트랙(bass/accomp/pad/drums/melody/guitar/strings/brass) 가 독립적으로 들리는가? (1-5)

2. **수동 transposed 파일 금지**
   - `midi_data/` 에 `이름 +1.mid`, `이름 -2.mid` 같은 수동 변조 파일 **절대 넣지 말 것**
   - 파이프라인이 자동으로 12 transposition 증강을 수행함
   - 수동 transposed 파일이 섞이면 해당 곡이 다른 곡 대비 **6-7배 학습 비중**으로 왜곡됨 (2026-04-09 이전 문제의 원인)

3. **새 곡 추가 시**
   - `midi_data/` 에 원본만 드롭
   - 파일명에 BPM, 박자, 장르 키워드 명시 (예: `CITY POP 105 4-4 ALL.mid`)
   - 트랙명을 악기 이름으로 명확히: `E.PIANO`, `VIOLIN_LEGATO`, `E.GUITAR1`, `BASS_FINGER`, `SYNTHPAD`, `DRUM` 등
   - GM program number 는 DAW 기본값(0) 이어도 OK — 이름 기반 분류가 우선됨

4. **장르 우선순위 (부족한 영역)**
   - `python tools/audit_track_classification.py` 결과에서 비중 낮은 카테고리:
     - **melody** 2.8% — 멜로디 단독 트랙이 있는 곡 추가 요망
     - **brass** 2.8% — 재즈/펑크/브라스 섹션 곡 추가 요망
     - **woodwind** 1.4% — 플루트/색소폰 곡 추가 요망
     - **arp** 0.5% — 아르페지오 패턴 곡 추가 요망
   - 클래식/재즈 등 비아시안 팝 장르 다양성 필요

5. **외부 작곡가 패널 모집 (Sprint Week 2-3 목표)**
   - Cubase/Ableton/Logic 사용하는 세미프로 작곡가 3-5명
   - 30분 청취 + A/B 평가 제공 가능한 분
   - 보상 안내: Phase C 에서 LoRA 마켓플레이스 수익 분배 (작곡가 70% / MidiGPT 30%)

#### 💻 개발자 (다른 개발자 동업자)

**즉시 (이번 주)**
1. **환경 셋업**
   ```bash
   git pull origin main
   # Windows + Python 3.13 + RTX GPU 가정
   pip install torch --index-url https://download.pytorch.org/whl/cu124
   pip install -r requirements.txt
   pip install fastapi uvicorn python-multipart  # 서버용
   python scripts/setup_check.py   # 8단계 전부 PASS 확인
   ```

2. **회귀 테스트 3종 실행** (약 1-2분)
   ```bash
   python test_classifier.py                  # 53/0 PASS 기대
   python tools/audit_track_classification.py # [PASS] 12+ 카테고리
   python test_roundtrip.py --all              # 40/0 PASS
   ```

3. **재학습** (RTX 3060 기준 약 1.9시간)
   - `checkpoints/` 가 비어 있거나 재학습 원하는 경우
   ```bash
   rm -rf midigpt_pipeline
   python -m midigpt.pipeline --midi_dir ./midi_data --epochs 10
   ```
   - 목표 지표: train/val gap < 0.2, val_loss < 0.5

4. **Week 2 작업 우선순위**
   - CMake 3.22+ 설치 (Visual Studio Installer 또는 https://cmake.org/download/)
   - `juce_daw_clean/` 빌드 시도 (우선 JUCE clone 필요: `git clone https://github.com/juce-framework/JUCE external/JUCE`)
   - `cd juce_daw_clean && build.bat`
   - 산출물: `build/MidiGPTPlugin_artefacts/Release/VST3/MidiGPT.vst3`
   - Cubase/Ableton Live 에 로드 테스트

5. **금지 사항**
   - ❌ `juce_app_quarantine/` 폴더의 코드를 읽거나 새 clean room 에 복사 금지
   - ❌ `D:/Cubase/` (또는 어디든) Cubase 15 바이너리 디컴파일 결과를 clean 코드에 반영 금지
   - ❌ Cubase 어휘 테이블(`vocab.py`)을 임의 확장하지 말 것 — 구조 변경은 breaking change
   - ❌ `*.pt` (577MB 체크포인트) 는 git 에 commit 하지 말 것 (`.gitignore` 에 이미 등록)

#### 💼 사업가 (사업 담당 동업자)

**즉시 (이번 주)**
1. **사업 문서 9종 회람 및 피드백** — [docs/business/](docs/business/)
   - `01_사업기획서.md` — 정체성, 시장, BM, 정합성
   - `02_PDR.md` — 제품 요구사항
   - `03_3페르소나_라운드테이블.md` — 의사결정 정합성
   - `04_5대_평가.md` — 프로젝트 전반 평가
   - `06_출시_로드맵.md` — 분기 단위 마일스톤
   - `07_상품_설명서.md` — 사용자 매뉴얼
   - `08_DAW_벤치마크_프레임워크.md` — Cubase 15 비교
   - `09_8주_Sprint_6월데드라인.md` — 현재 활성 sprint plan ← 가장 중요

2. **Cubase 15 정식 라이선스 상태 확인**
   - 현재 Cubase 15 ISO 는 `D:/Cubase/` 에 있으며, 본 레포 외부에 격리됨
   - 상용 라이선스 보유 상태가 아니면 Cubase AI ($50) 또는 Elements ($100) 즉시 구매 권장
   - 이유: Sprint Week 4+ 에서 투자/파트너십/외부 커뮤니케이션 시 정식 라이선스 증빙 필요

3. **외부 작곡가 패널 모집 기획** (Week 2-3 마감)
   - 타겟: 세미프로 작곡가 3-5명
   - 채널: 한국/일본 작곡가 커뮤니티, 음악학과, 게임 BGM 프리랜서 네트워크
   - 보상 구조 초안 작성 필요 (LoRA 마켓 수익 분배 or 별도 사례금)

4. **6월 1일 공개 출시 준비**
   - 랜딩 페이지 도메인 후보 3개 선정
   - Press release 초안 (한/영)
   - 베타 배포 채널 (GitHub Releases + Discord 서버)
   - 시연 영상 3편 시나리오 ([09_8주_Sprint](docs/business/09_8주_Sprint_6월데드라인.md) Week 7 참조)

---

## 현재 진행 중인 Sprint (2026-04-10 ~ 2026-06-01)

**상세 plan**: [docs/business/09_8주_Sprint_6월데드라인.md](docs/business/09_8주_Sprint_6월데드라인.md)

| Week | 기간 | 핵심 산출물 |
|------|------|-------------|
| Week 1 ✅ 진행 중 | 04-10 ~ 04-16 | 분류기 수정, 재학습, JUCE 빌드 환경 |
| Week 2 | 04-17 ~ 04-23 | MIDI I/O 파이프라인, HTTP 연결 |
| Week 3 | 04-24 ~ 04-30 | UI 확장, PianoRoll, 상태 저장 |
| Week 4 | 05-01 ~ 05-07 | LoRA 어댑터 3종 (city pop/metal/jazz) |
| Week 5 | 05-08 ~ 05-14 | 외부 청취 패널, DPO 1차 |
| Week 6 | 05-15 ~ 05-21 | 폴리쉬, Audio2MIDI 통합 |
| Week 7 | 05-22 ~ 05-28 | QA, 시연 영상 3편 |
| Week 8 | 05-29 ~ 06-01 | **MVP 베타 릴리즈** 🚀 |

### Week 1 현재 상태 (2026-04-10)

- ✅ 데이터 오염 회수 (수동 transposed 14개 격리)
- ✅ `_classify_track` 분류기 수정 (141줄)
- ✅ 회귀 테스트 3종 (classifier / roundtrip / audit)
- ✅ 재학습 완료 (1.9시간, val_loss 0.2624, gap 0.091)
- ✅ FastAPI 추론 서버 (/health /generate /generate_json /load_lora)
- ✅ 생성 결과 검증 (8 tracks, 218 notes, 126초)
- ✅ `juce_daw_clean/` skeleton (PluginProcessor, PluginEditor, AIBridge, CMake, build.bat)
- ⏳ Cubase 에서 생성 결과 청취 (작곡가 대기)
- ⏳ JUCE 프레임워크 clone + CMake 빌드 (개발자 대기)
- ⏳ 외부 작곡가 패널 모집 시작 (사업가 대기)

### Week 1 게이트 (통과 조건)

- [x] 분류기 audit: 6+ 카테고리, accomp < 60%
- [x] Round-trip 40/40 PASS
- [x] 재학습 val/train gap < 2.0 (목표 달성: 0.091)
- [x] 생성 MIDI 평균 크기 증가 (트랙/노트/길이 기준)
- [ ] 작곡가 청취 평가 (대기)
- [ ] VST3 가 Cubase 에 "MidiGPT" 이름으로 로드 (대기)

---

## 🗂️ 이 레포에서 절대 건드리지 말 것 (Clean Room 원칙)

| 영역 | 이유 |
|------|------|
| `juce_app_quarantine/` | Cubase 15 Ghidra 디컴파일 파생 코드 포함. 법적 오염. `.gitignore` 로 이미 차단 |
| `D:/Cubase/` (본 레포 외부) | Cubase 15 ISO. 참고용 사용자 관찰만 허용, 코드 반영 금지 |
| 과거 `juce_app/` 디렉토리에 있던 코드 | 새 `juce_daw_clean/` 에 복사/리팩토링 금지. 반드시 JUCE 공식 문서 + VST3 SDK 기반으로 처음부터 작성 |

자세한 clean room 원칙 → [juce_daw_clean/README_CLEAN_ROOM.md](juce_daw_clean/README_CLEAN_ROOM.md)

---

## 🤖 AI 서브에이전트 (Claude Code 사용자 전용)

본 레포의 `.claude/agents/` 에 8종 서브에이전트가 등록되어 있음. Claude Code 세션에서 직접 호출 가능:

**의사결정용 (3종)**
- `persona-businessperson` — 사업/시장/수익/정체성 관점
- `persona-composer` — 음악성/워크플로우/DAW 경험 관점
- `persona-developer` — 기술적 가능성/ML/리스크 관점

**코드 작업용 (5종)**
- `dev-juce` — JUCE C++ / VST3 / GUI / 오디오 DSP
- `dev-ml` — PyTorch / LLM / 토크나이저 / LoRA / DPO
- `dev-integration` — Python↔C++ HTTP, Audio2MIDI, Sheet2MIDI
- `dev-test` — pytest / JUCE UnitTest / CI
- `dev-docs` — 사용자 가이드 / README / API 문서

모든 에이전트는 **Clean Room 원칙을 상속** — Cubase 바이너리, `juce_app_quarantine/`, Ghidra 결과물 접근 금지.

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
- ✅ `min_new_tokens` EOS 조기종료 방지 (2026-04-08)
- ✅ DPO quantile fallback (2026-04-08)
- ✅ 토큰 경로 자동 탐색 (2026-04-08)
- ✅ Windows UTF-8 인코딩 강제 (2026-04-08)
- ✅ fp16 GradScaler + grad_accum loss 스케일링 (2026-04-14)
- ✅ LoRALinear base layer device/dtype 상속 (2026-04-14)
- ✅ SFT loader 메타파일 glob 혼입 차단 + 스키마 검증 (2026-04-15)
- ✅ `_classify_track` accomp 쏠림 4건 수정 — BASSOON / STRING 단수 / TIMPANI / program=0 근본 (2026-04-15) `BREAKING: retokenize + retrain`

### 🛡️ 개발 프로세스 구조 (2026-04-15)

반복되는 동종 버그 패턴을 끊기 위해 **작업 단계 역할 축** 도입:

```
Design Composer → Main/Sub Coder → Reviewer
```

- **도메인 agent** (`dev-ml`, `dev-juce`, `dev-integration`, `dev-test`, `dev-docs`, `persona-*`): *어느 코드 영역*
- **역할 agent** (`role-design-composer`, `role-main-coder`, `role-sub-coder`, `role-reviewer`): *어느 작업 단계*

두 축은 직교. 모든 변경은 설계서 → 구현 → 적대적 리뷰를 거친다.

| 산출물 | 위치 | 용도 |
|--------|------|------|
| 루트 규약 | [`CLAUDE.md`](CLAUDE.md) | 프로세스 개요 |
| 계약·정책 | [`.claude/rules/`](.claude/rules/) | 파일 스키마, fallback 정책, Windows 호환, 커밋 규약, **버그 히스토리 (패턴 A~H)** |
| 역할 | [`.claude/agents/role-*.md`](.claude/agents/) | 단계별 에이전트 명세 |
| 체크리스트 | [`.claude/skills/`](.claude/skills/) | pre-change / cross-boundary / bug-regression |

`rules/05-bug-history.md` 는 Reviewer 필수 대조 대상. 새 버그 발견 시 패턴 추가가 의무화되어 문서가 시간에 따라 강화된다.

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
