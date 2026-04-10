# MidiGPT — 앱 / 통합 명세

> Python 앱, 멀티 에이전트, JUCE C++ 통합의 표준 명세
> 분류: 앱 / 통합 영역
> 코드: `app/`, `agents/`, `juce_app/`

---

## 개요

MidiGPT는 단순 모델이 아니라, MIDI AI Workstation 형태의 통합 앱과 함께 배포된다.
구성:

```
┌─────────────────────────────────────────────┐
│  JUCE C++ Frontend (juce_app/)              │
│   - UI, MIDI I/O, 오디오 엔진                 │
└─────────────────────────────────────────────┘
                    ↕  소켓 / 파일
┌─────────────────────────────────────────────┐
│  Python Backend (app/)                      │
│   - core/   : MIDI/AI/하모니/그루브 엔진     │
│   - agents/ : 멀티 에이전트 (Composer 등)    │
│   - midigpt: LLM 추론 엔진                   │
└─────────────────────────────────────────────┘
```

---

## 1. Python 앱 코어 (`app/core/`)

### 모듈 목록

| 모듈 | 역할 |
|------|------|
| `midi_engine.py` | 실시간 재생, MIDI 입출력 포트, 프로젝트 로드/저장 |
| `ai_engine.py` | 코드 진행, 스케일 스냅, 변주 도구 (→ AI엔진_명세) |
| `harmony_engine.py` | 코드 분석, 보이싱, 송 폼 (→ 화성엔진_명세) |
| `groove_engine.py` | 스윙, 그루브 추출, 드럼 (→ 그루브엔진_명세) |
| `arrangement.py` | 클립/씬, 마커, 루프 |
| `effects_engine.py` | EQ, Compressor, Reverb, Delay, Chorus |
| `synth_engine.py` | ADSR, LFO, biquad filter (단순 신스) |
| `audio_engine.py` / `audio_io.py` | 오디오 처리 / I/O |
| `automation.py` | CC 자동화 |
| `pattern_db.py` | 패턴 라이브러리 |
| `prompt_parser.py` | 자연어 → 구조화 명령 |
| `score_engine.py` | 악보 처리 |
| `similarity_engine.py` | MIDI 유사도 계산 |
| `models.py`, `project.py` | 데이터 모델, 프로젝트 직렬화 |

### MidiEngine
**코드 위치**: `app/core/midi_engine.py`

#### 동작 규칙
- `PlaybackThread` — 백그라운드 재생
- MIDI 입출력 포트 자동 검색/연결
- SMF (Standard MIDI File) 로드/저장
- 트랙/노트 추가/제거/이동 API

---

## 2. 멀티 에이전트 (`agents/`)

### 에이전트 목록

| 에이전트 | 파일 | 역할 |
|---------|------|------|
| Composer | `composer.py` | MIDI 생성 (설정 기반) |
| Manager | `manager.py` | 설정 관리, 파이프라인 조율, 작업 로그 |
| Reviewer | `reviewer.py` | 생성 품질 평가 |
| Orchestrator | `orchestrator.py` | 멀티 에이전트 조정 |
| Audio2MIDI | `audio2midi.py` | 오디오 → MIDI (Demucs + Basic Pitch) |
| **Sheet2MIDI** | **`sheet2midi.py`** | **악보 이미지 → MIDI (SMT++ OMR, MIT, 21.4M)** |
| AbletonBridge | `ableton_bridge.py` | DAW 원격 제어 (소켓) |
| MusicTransformer | `music_transformer.py` | 보조 모델 인터페이스 |

### Sheet2MIDI 파이프라인
**코드 위치**: `agents/sheet2midi.py`

```
악보 이미지(PNG/JPG/PDF)
    ↓ cv2.imread + convert_img_to_tensor
SMT++ (antoniorv6/smt-camera-grandstaff, 21.4M, MIT)
    ↓ ConvNext encoder + Transformer decoder
bekern 텍스트 (`<b>`/`<s>`/`<t>` 특수 토큰)
    ↓ token replacement
humdrum kern 텍스트
    ↓ music21.converter.parseData(format='humdrum')
music21 Score
    ↓ score.write('midi')
MIDI 파일
    ↓ (선택) MidiGPT 변주
변주 MIDI
```

#### 의존성 (선택, 악보 입력 사용 시만)
- `SMT-plusplus` (소스 설치, MIT)
- `music21` (BSD)
- `opencv-python`

#### API
```python
from agents.sheet2midi import Sheet2MidiAgent

agent = Sheet2MidiAgent()
midi_path, transcription = agent.transcribe_to_midi("score.png", "out.mid")

# 또는 한 번에 변주까지
result = agent.transcribe_and_vary(
    image_path="score.png",
    midi_output_path="out.mid",
    variation_output_path="out_var.mid",
    midigpt_base_model="./checkpoints/midigpt_ema.pt",
    meta_style="jazz",
)
```

#### 한계
- 기본 체크포인트는 **피아노 전용**
- 손글씨/저해상도 인식률 낮음
- 다른 악기는 SMT의 다른 체크포인트 필요

### Windows 호환성 — UTF-8 인코딩 강제 ✅ 2026-04-08

한국어 Windows (CP949 기본 코드페이지) 에서 `open()` 호출 시 인코딩 mismatch로
`UnicodeDecodeError` 가 발생하는 문제 일괄 수정.

**적용 파일** (텍스트 모드 `open()` 에 `encoding='utf-8'` 명시):
| 에이전트 | 수정 라인 |
|---------|----------|
| `reviewer.py` | 292, 299, 303, 322 |
| `manager.py` | 49, 55, 67, 108, 118, 274 |
| `orchestrator.py` | 77, 283, 292 |
| `composer.py` | 286 |
| `ableton_bridge.py` | 259 |
| `music_transformer.py` | 38, 256, 323, 406 |
| `tools/generate_sinco.py` | 106, 468 |
| `midigpt/training/train_pretrain.py` | 216, 258 |

### 동작 흐름
```
사용자 요청 → Manager → Orchestrator
                          ↓
                  Composer → MIDI 생성
                          ↓
                  Reviewer → 품질 평가
                          ↓
                Manager → 결과 / 피드백 저장
```

### Audio2MIDI 파이프라인
1. 입력 오디오 → Meta Demucs → stem 분리
2. 각 stem → Spotify Basic Pitch → MIDI
3. 결과 합성 → 멀티트랙 MIDI

---

## 3. JUCE C++ 앱 (`juce_app/`)

### 역할
- 네이티브 UI (Cubase 15 스타일 5-zone 레이아웃)
- 저지연 MIDI 입출력
- 오디오 엔진 (실시간)
- (향후) VST3/CLAP 호스팅

### 통신
- Python 백엔드와 소켓/파일 IPC
- AbletonBridge 에이전트를 통한 DAW 원격 제어

### 의존성
- JUCE 프레임워크 (`E:/Ableton/JUCE`)

---

## 4. MidiGPT 추론 통합

### 호출 경로
```
JUCE UI 버튼
   ↓ (소켓)
Manager 에이전트
   ↓
Composer 에이전트
   ↓
MidiGPTInference.generate_variation()
   ↓
모델 추론 (KV cache + 화성 마스킹)
   ↓
디코드 → 노트 dict
   ↓ (파일/소켓)
JUCE UI에 표시 / 재생
```

### Phase 1 + BUG fix 추가 옵션 노출
사용자 UI에서 직접 조절 가능 (권장):
- `repetition_penalty` (1.0~1.3 슬라이더)
- `no_repeat_ngram_size` (0~6 정수)
- `num_return_sequences` (1~8 후보)
- `min_new_tokens` (0~512 정수, 기본 256) ✅ 2026-04-08
- `max_tokens` (256~2048 정수, 기본 1024) ✅ 2026-04-08
- `temperature` (0.1~2.0, 기본 1.2) ✅ 2026-04-08
- KV cache는 항상 ON (기본값)

---

## 5. 빌드 / 배포

### Python 패키지
```bash
pyinstaller MidiAIWorkstation.spec
pyinstaller MidiIngest.spec
pyinstaller PatternExtractor.spec
```

### JUCE C++
- CMake 또는 Projucer 빌드
- 의존성: JUCE 7+

---

## 6. 검증 항목

### 통합
- [x] MidiGPT 미로드 시 그레이스풀 메시지
- [x] 에이전트 간 메시지 직렬화 호환
- [x] JUCE ↔ Python 소켓 재연결 처리

### 성능
- [x] UI 응답성 (생성 호출이 메인 스레드 블록 안 함)
- [x] 모델 로드 시간 < 5초 (FP16, RTX 4090)

---

## 7. 호환성

| 변경 | 등급 |
|------|------|
| 새 에이전트 추가 | 🟢 안전 |
| Python ↔ JUCE 프로토콜 변경 | 🟡 양쪽 동기화 필요 |
| MidiGPT API 변경 | 🟠 Composer 어댑터 수정 필요 |

---

## 8. 향후 개선 후보

| 항목 | 비고 |
|------|------|
| VST3/CLAP 호스팅 | JUCE AudioPluginHost 또는 CLAP 헤더 |
| Plugin Parameter Automation | CC 매핑 |
| Audio Track 처리 | 현재 MIDI only |
| Audio Warping (Rubber Band) | 시간 스트레칭 |
| Multi-user 협업 (CRDT) | 클라우드 동기화 |
| 자연어 채팅 어시스턴트 | "이 부분 더 슬프게" |
| Variation Browser UI | num_return_sequences > 1 시각화 |
| Diff View | 두 버전 차이 |
| Inpainting UI | 구간 선택 후 재생성 |
| Sysex / MIDI 2.0 / MPE | 차세대 MIDI |
