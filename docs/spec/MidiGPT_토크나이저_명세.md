# MidiGPT — 토크나이저 명세

> MIDI ↔ 토큰 시퀀스 양방향 변환의 표준 명세
> 분류: LLM / 모델 영역
> 코드: `midigpt/tokenizer/`

---

## 개요

MidiGPT는 **계층적 REMI (REvamped MIDI)** 토큰 어휘를 사용한다.
3개 계층(구조 / 화성 / 노트) + 표현(Expression) + Cubase 15 기반 확장 토큰으로
구성되며, 총 약 **448개 토큰**을 갖는다.

### 핵심 흐름
```
MIDI 파일 → pretty_midi 파싱 → 메타 추출 → 코드 분석 → 토큰 시퀀스
                                                          ↓
                                                  .npy로 저장 (학습용)
                                                          ↑
                                          토큰 시퀀스 ← 모델 추론
                                                ↓
                                       MidiDecoder → MIDI 파일
```

---

## 1. 어휘 구성 (vocab_size = 448)

**코드 위치**: `midigpt/tokenizer/vocab.py:33-219`

### 특수 토큰 (5)
| 토큰 | ID | 용도 |
|------|----|----|
| `<PAD>` | 0 | 패딩 (loss ignore) |
| `<BOS>` | 1 | 시퀀스 시작 |
| `<EOS>` | 2 | 시퀀스 종료 |
| `<SEP>` | 3 | 변주 트리거 (입력 ↔ 출력 경계) |
| `<UNK>` | 4 | 미지 토큰 |

### Layer 3: 구조 (Structure) ~82 토큰
| 그룹 | 수 | 예 |
|------|----|----|
| Key | 24 | `Key_C`, `Key_Cm`, `Key_C#`, ... |
| Style | 16 | `Style_pop`, `Style_jazz`, `Style_orchestral`, ... |
| Section | 10 | `Sec_intro`, `Sec_verse`, `Sec_chorus`, ... |
| Tempo | 32 | `Tempo_0`~`Tempo_31` (40~240 BPM 양자화) |

### Layer 2: 화성 (Harmony) ~55 토큰
| 그룹 | 수 | 예 |
|------|----|----|
| ChordRoot | 12 | `ChordRoot_C`, `ChordRoot_C#`, ... |
| ChordQual | 24 | `ChordQual_maj`, `ChordQual_m7`, `ChordQual_7b9`, ... |
| Chord_NC | 1 | 무화성 (No Chord) |
| Bass | 12 | `Bass_C`, ... (슬래시 코드용) |
| Func | 6 | `Func_tonic`, `Func_dominant`, ... |

> **팩터화**: 기존 289개 결합 토큰 (`Chord_Cmaj7`)을 root + quality 분리로 압축. 어휘 크기 ↓, 일반화 ↑

### 시간축 (96)
| 그룹 | 수 | 예 |
|------|----|----|
| Bar | 64 | `Bar_0`~`Bar_63` |
| Position | 32 | `Pos_0`~`Pos_31` (32분음표 해상도) |

### Layer 1: 노트 (Note) ~182 토큰
| 그룹 | 수 | 비고 |
|------|----|----|
| Pitch | 88 | A0(21)~C8(108), 피아노 음역 |
| Velocity | 16 | `Vel_0`~`Vel_15` (0~127 양자화) |
| Duration | 64 | `Dur_1`~`Dur_64` (32분음표 단위) |
| Track | 14 | melody/accomp/bass/drums/pad/lead/arp/strings/brass/woodwind/vocal/guitar/fx/other |

### 표현 (Expressive) ~106 토큰
| 그룹 | 수 | 비고 |
|------|----|----|
| Articulation | 32 | Cubase 15 kLengths/kTechniques/kOrnaments 기반 |
| Dynamics | 13 | ppp~fff + sfz/sfp/fp/ffp/pf |
| Expression (CC11) | 16 | 오케스트라 볼륨 컨트롤 |
| Modulation (CC1) | 16 | 비브라토 깊이 |
| Sustain (CC64) | 2 | `Pedal_on`, `Pedal_off` |
| PitchBend | 16 | -8192~+8191 양자화 |
| Instrument Family | 11 | keyboard/strings/brass/wind/fretted/percussion/... |

---

## 2. 인코더 (MIDI → 토큰)

**코드 위치**: `midigpt/tokenizer/encoder.py`

### 입력
- MIDI 파일 경로 또는 노트 dict 리스트
- `SongMeta`: key, style, section, tempo
- `ChordEvent` 리스트: root, quality, bass, function, start_beat, end_beat

### 동작 규칙
1. `<BOS>` 추가
2. 메타 토큰 삽입: `Key_X`, `Style_X`, `Sec_X`, `Tempo_X`
3. Bar 단위 순회:
   - `Bar_n` 토큰 삽입
   - 코드 변화 시 `ChordRoot_X` + `ChordQual_X` 삽입
   - Bar 내 노트 정렬:
     - `Pos_n` (절대 위치)
     - `Track_X`
     - `Pitch_n`, `Vel_n`, `Dur_n`
     - 표현 토큰 (있으면)
4. `<EOS>` 추가

### 출력
- `list[int]` 토큰 ID 시퀀스
- 학습 시 `.npy`로 저장 (`tokenize_dataset.py`)

---

## 3. 디코더 (토큰 → MIDI)

**코드 위치**: `midigpt/tokenizer/decoder.py`

### 동작 규칙
- 토큰 순회 → 상태 머신:
  - 현재 Bar, Position, Track 추적
  - Pitch + Vel + Dur 한 노트 완성 시 `Note(pitch, velocity, start_tick, duration_tick, track_type)` 생성
- `decode_to_notes()` → 노트 객체 리스트
- `decode_to_midi(path, tempo)` → SMF 파일

### 검증 항목
- [x] encoder → decoder roundtrip 시 노트 ≥ 95% 보존 (양자화 손실 허용)
- [x] 잘못된 토큰 순서 graceful 처리 (UNK 무시)

---

## 4. 의존성 / 호환성

### 라이브러리
- `pretty_midi` — MIDI 파싱
- `numpy` — 토큰 배열 저장

### 호환성 영향

| 변경 | 등급 | 영향 |
|------|------|------|
| 새 토큰을 vocab **마지막에 append** | 🟠 | 기존 모델에 추가 토큰만 학습 시 fine-tune 가능 |
| 새 토큰을 **중간에 삽입** | 🔴 | 모든 ID shift → 모든 .npy 폐기, 모든 모델 폐기 |
| Articulation/Dynamics 항목 추가 | 🟠 | append 방식이면 안전 |
| 토큰 순서 규칙 변경 | 🔴 | 디코더 로직 변경 + 데이터 재토큰화 |
| `NUM_BARS`, `NUM_POSITIONS` 변경 | 🔴 | 시간 해상도 바뀜, 전체 재토큰화 |

> ⚠️ **절대 규칙**: 새 토큰은 무조건 vocab 마지막에 append. 중간 삽입은 기존 자산을 전부 무효화한다.

---

## 5. 검증 항목

### 단위 테스트
- [x] `vocab.size == 448` (현 시점)
- [x] 모든 토큰 ID 유일 (`token2id` invariant)
- [x] `encode_token(unknown) == unk_id`
- [x] roundtrip: `decode_id(encode_token(t)) == t`

### 데이터셋 검증
- [ ] 토큰 분포 통계 출력 (각 그룹별 빈도)
- [ ] outlier 시퀀스(길이 > block_size, 토큰 < 50) 보고

---

## 6. 향후 확장 후보

| 항목 | 등급 | 비고 |
|------|------|------|
| Chord Inversion 토큰 | 🔴 | append 방식 가능, 재토큰화 필수 |
| Tempo Curve / Rubato | 🔴 | 곡 내부 템포 변화 |
| Time Signature 변화 토큰 | 🔴 | 5/4, 7/8 |
| Microtonal 음계 | 🔴 | non-12TET |
| MPE per-note CC | 🔴 | 차세대 표현력 |
| Tension Notes (9/11/13) | 🟠 | append 가능 |
| Phrase Boundary | 🟠 | append 가능 |

상세 우선순위 → [MidiGPT_개선로드맵_명세.md](MidiGPT_개선로드맵_명세.md)
