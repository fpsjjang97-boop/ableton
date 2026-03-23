# Ableton MIDI AI — 변주 자동화 프로젝트

> MIDI 데이터 임베딩 → 사람 검수 DB 구축 → Transformer 학습 → 변주 자동 생성

![Python](https://img.shields.io/badge/Python-3.13-blue)
![Ableton](https://img.shields.io/badge/DAW-Ableton_Live-black)
![MIDI](https://img.shields.io/badge/Data-MIDI-green)

---

## 프로젝트 구조

```
├── Ableton/midi_raw/          # MAESTRO 2018 MIDI 원본 (93곡)
│   ├── chamber/               # 실내악 (7곡)
│   ├── recital/               # 독주회 (74곡)
│   └── schubert/              # 슈베르트 (12곡)
├── embeddings/                # MIDI 임베딩 결과
│   ├── embedding_matrix.npy   # 93x128 임베딩 매트릭스
│   ├── catalog.json           # 조성/템포/난이도별 분류 인덱스
│   ├── CATALOG.md             # 93곡 전체 분류표
│   ├── README.md              # 임베딩 구조 + 활용법
│   └── individual/            # 곡별 전체 노트 데이터
│       ├── chamber/
│       ├── recital/
│       └── schubert/
├── reviewed/                  # 사람 검수 데이터 (Phase 1)
│   ├── originals/             # 검수된 원본 프레이즈
│   ├── variations/            # 사람이 만든 변주
│   ├── metadata/              # JSON 메타데이터
│   └── progress.md            # 진행 현황
├── output/                    # AI 생성 결과물
│   └── 2026-03-23_variation_classic_piano.mid
├── tools/                     # 파이프라인 도구
│   ├── midi_embedding.py      # MIDI → 128차원 임베딩
│   ├── build_catalog.py       # 분류 카탈로그 생성
│   ├── generate_variation.py  # 변주 생성기
│   └── compare_midi.py        # 원본 vs 변주 비교 분석
├── docs/                      # 문서
│   └── review-guide.md        # 검수 가이드라인
├── agents/                    # 멀티 에이전트 시스템
├── reviews/                   # 에이전트 리뷰 결과
├── 11.mid                     # 원본 MIDI (Bb minor, 앰비언트)
├── 원신_output.mid             # 원신 OST MIDI 변환 결과
├── settings.json              # 에이전트 설정
└── start_agents.sh            # 에이전트 실행 스크립트
```

---

## 로드맵

### Phase 1: 사람 검수 DB 구축 ← **현재 단계**
- 93곡 MIDI를 프레이즈 단위로 분리
- 코드/구조/스타일 태깅
- 원본-변주 쌍 **200개** 목표
- [검수 가이드라인](docs/review-guide.md) 참조

### Phase 2: 토크나이징
- MidiTok(REMI 방식)으로 MIDI → 토큰 변환
- 학습 데이터셋 구성

### Phase 3: Transformer 학습
- 사전학습: 검수 MIDI 전체로 음악 언어 학습
- 파인튜닝: 원본-변주 쌍으로 변주 생성 학습
- 조건부 생성: 스타일/변주유형 제어

### Phase 4: 자동화
- AI 생성 → 사람 검수 → DB 축적 → 재학습 루프
- 사람 개입 100% → 5~10%로 감소

---

## 현재 데이터

| 항목 | 수치 |
|------|------|
| MIDI 파일 | 93곡 (MAESTRO 2018) |
| 총 노트 수 | 873,158개 |
| 임베딩 | 93 x 128차원 |
| 카테고리 | chamber(7) / recital(74) / schubert(12) |
| 검수 완료 | 0 / 200쌍 (목표) |

---

## 도구 사용법

```bash
# MIDI 임베딩 생성/갱신
python tools/midi_embedding.py

# 분류 카탈로그 생성
python tools/build_catalog.py

# 변주 생성 (11.mid 기반)
python tools/generate_variation.py

# 원본 vs 변주 비교
python tools/compare_midi.py
```

---

## 라이선스

MIT License
