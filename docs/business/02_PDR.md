# MidiGPT — Product Definition Requirements (PDR)

> 작성: 2026-04-09 / 업데이트: 2026-04-09
> 분류: 제품 정의 / 요구사항
> 관련: [01_사업기획서.md](01_사업기획서.md), [03_3페르소나_라운드테이블.md](03_3페르소나_라운드테이블.md), [09_8주_Sprint_6월데드라인.md](09_8주_Sprint_6월데드라인.md)
>
> ⚠️ **2026-04-09 업데이트**: 메인 제품 형태가 **VST3 Plugin** (`juce_daw_clean/`) 으로
> 확정됨. Standalone Desktop App 은 같은 JUCE 코드베이스의 부가 타겟. 기존
> `juce_app/` (Cubase 15 Ghidra 파생) 은 `juce_app_quarantine/` 로 격리됨.
> MVP 데드라인: **2026-06-01** (8주 sprint).

---

## 0. 문서 목적

본 문서는 MidiGPT 제품의 **무엇을(What)·왜(Why)·누구를 위해(For Whom)·어떻게 검증할 것인가(How to Validate)** 를 정의한다. 기술 구현 방법(How)은 `docs/spec/` 의 표준 명세를 참조한다.

PDR ↔ 표준 명세 매핑:
- 제품 요구사항 (본 문서) → 어떤 기능이 왜 필요한가
- 표준 명세 (`docs/spec/`) → 어떻게 구현하는가

---

## 1. 제품 정의

### 1-1. 한 줄 정의
**"DAW 안에서 동작하는 음악 이론 인지형 MIDI AI 워크스테이션"**

### 1-2. 정의에 들어가는 단어 해부
| 단어 | 의미 | 측정 가능한 기준 |
|------|------|-------------------|
| DAW 안에서 동작하는 | 작곡가가 DAW를 떠나지 않는다 | VST3/CLAP 플러그인 형태로 호스팅, MIDI in/out 직접 라우팅 |
| 음악 이론 인지형 | 코드/스케일/송폼을 알고 따른다 | 화성 마스킹으로 off-scale pitch 차단, 송폼 토큰 인지 |
| MIDI AI | 오디오가 아닌 MIDI 출력 | 100% MIDI Type 1 출력, CC/Pitchbend/MPE 포함 |
| 워크스테이션 | 단일 기능이 아니라 통합 도구 | 변주/편곡/확장/사보/오디오변환 통합 |

### 1-3. 제품이 아닌 것 (Out of Scope)
- 보컬 합성
- 마스터링/믹싱 자동화
- 실시간 라이브 퍼포먼스 (별도 제품으로 분기 가능)
- 가사 생성
- 영상 편집

---

## 2. 사용자 정의

### 2-1. Primary Persona — "막힌 작곡가"
- 직업: 세미프로 작곡가, 음대 학생, 게임 BGM 프리랜서
- 도구: Cubase / Ableton / Logic Pro
- 페인 포인트:
  - "후렴구까지 만들었는데 브리지가 안 떠오름"
  - "비슷한 변주를 5개 만들어서 클라이언트에게 보여줘야 함"
  - "이 코드 진행 위에 어떤 멜로디가 어울릴지 빠르게 시도하고 싶음"
- 기존 우회로:
  - 다른 곡 듣기 → 영감 → 시간 낭비
  - 친구 작곡가에게 부탁 → 시간/관계 비용
  - ChatGPT에게 텍스트로 묘사 → 음악적 결과물 0
- 우리가 주는 가치:
  - **DAW 안에서 한 번 클릭 → 30초 변주 3개 → 그 자리에서 편집**

### 2-2. Secondary Persona — "BGM 양산 작곡가"
- 직업: 게임/광고/유튜브 BGM 외주
- 페인: 유사 분위기 5-10곡을 짧은 시간에 만들어야 함
- 가치: 기본 곡 → LoRA 스타일 어댑터 → 변주 5개 → 그 중 좋은 것만 다듬기

### 2-3. Tertiary Persona — "음악 이론 학습자"
- 직업: 음대생, 작곡 학원 수강생
- 페인: 화성/송폼을 시각적·청각적으로 동시에 이해하기 어려움
- 가치: 코드 진행 입력 → 다양한 보이싱·변주 즉시 청취

---

## 3. 핵심 사용 사례 (User Stories)

### US-1: 변주 생성 (1차 사용 사례)
> 작곡가는 16마디 코드 진행을 입력하고, 30초 안에 3가지 변주 후보를 받아 그 중 하나를 DAW로 가져온다.

수용 조건:
- [ ] 입력: MIDI 파일 또는 DAW 트랙 선택
- [ ] 출력: MIDI Type 1, 평균 5~15KB, 길이 15초~1분
- [ ] 시간: 30초 이내 (RTX 3060+, FP16)
- [ ] 결과는 입력의 화성을 따른다 (off-scale pitch 0%)
- [ ] 3개 후보 모두 음악적으로 구별 가능 (단순 noise variation 아님)

### US-2: 편곡 확장 (Arrangement Expansion)
> 작곡가는 32마디 코러스를 입력하고, 베이스/드럼/패드/스트링이 추가된 풀 편곡을 받는다.

수용 조건:
- [ ] 입력 트랙 보존
- [ ] 추가 트랙은 14 카테고리 중 선택 가능 (melody/bass/drums/pad/strings/...)
- [ ] 각 트랙은 적절한 카테고리(velocity/range/density)로 출력

### US-3: Audio → MIDI 변환
> 작곡가는 자신의 데모 wav 파일을 드래그하고, MidiGPT가 다룰 수 있는 MIDI로 받는다.

수용 조건:
- [ ] Demucs로 6 stem 분리 (vocal/drums/bass/guitar/piano/other)
- [ ] Basic Pitch로 멜로디 추출
- [ ] MidiGPT 토큰화 가능한 형식으로 출력

### US-4: Sheet → MIDI → 변주
> 작곡가는 PDF 악보를 입력하고, MidiGPT가 변주한 MIDI를 받는다.

수용 조건:
- [ ] sheet2midi 에이전트로 SMT++ OMR 변환
- [ ] 변환 정확도 80%+ (음표 단위)
- [ ] 변환 결과를 LLM 입력으로 즉시 사용 가능

### US-5: LoRA 스타일 핫스왑
> 작곡가는 베이스 모델 위에 "재즈 LoRA"를 올리고, 같은 입력에서 재즈 풍 변주를 얻는다.

수용 조건:
- [ ] LoRA 로드 < 5초
- [ ] 동일 입력에 대한 결과가 명확히 다른 스타일 (장르 사람 청취 식별 70%+)

---

## 4. 기능 요구사항 (FR)

### 4-1. LLM 코어 (FR-LLM)
| ID | 요구사항 | 우선순위 | 상태 |
|----|----------|----------|------|
| FR-LLM-01 | 50M decoder-only 모델 | P0 | ✅ |
| FR-LLM-02 | 448 토큰 vocab (계층적 REMI) | P0 | ✅ |
| FR-LLM-03 | KV cache 가속 추론 | P0 | ✅ |
| FR-LLM-04 | 화성 마스킹 (off-scale 차단) | P0 | ✅ |
| FR-LLM-05 | min_new_tokens 강제 (BUG 4/5) | P0 | ✅ (engine.py:440) |
| FR-LLM-06 | LoRA 핫스왑 | P0 | ✅ |
| FR-LLM-07 | EMA 체크포인트 | P1 | ✅ |
| FR-LLM-08 | num_return_sequences | P1 | ✅ |
| FR-LLM-09 | repetition_penalty / no_repeat_ngram | P1 | ✅ |
| FR-LLM-10 | CFG 학습 (Phase 3) | P2 | 미구현 |
| FR-LLM-11 | Multi-task heads | P3 | 미구현 |
| FR-LLM-12 | Voice Leading reward + GRPO | P3 | 미구현 |

### 4-2. 데이터 파이프라인 (FR-DATA)
| ID | 요구사항 | 우선순위 | 상태 |
|----|----------|----------|------|
| FR-DATA-01 | MIDI → 토큰 변환 | P0 | ✅ |
| FR-DATA-02 | 데이터 증강 (전조 + 트랙 드롭아웃) | P0 | ✅ |
| FR-DATA-03 | 동업자 업로드 워크플로우 | P0 | ✅ |
| FR-DATA-04 | 자동 품질 필터 | P1 | 미구현 |
| FR-DATA-05 | Lakh MIDI 통합 + 필터 | P1 | 미구현 |
| FR-DATA-06 | GiantMIDI-Piano 통합 | P2 | 미구현 |
| FR-DATA-07 | Slakh2100 통합 | P2 | 미구현 |
| FR-DATA-08 | sheet2midi 배치 변환 | P1 | 부분 |
| FR-DATA-09 | 사람 청취 라벨링 인프라 | P1 | 미구현 |

### 4-3. 학습 파이프라인 (FR-TRAIN)
| ID | 요구사항 | 우선순위 | 상태 |
|----|----------|----------|------|
| FR-TRAIN-01 | Pre-training (CLM) | P0 | ✅ |
| FR-TRAIN-02 | LoRA SFT | P0 | ✅ |
| FR-TRAIN-03 | DPO 선호도 학습 | P1 | ✅ (quantile fallback 적용) |
| FR-TRAIN-04 | Self-improvement loop | P1 | ✅ (단, 사람 체크포인트 강제 필요) |
| FR-TRAIN-05 | 사람 청취 페어 50%+ 비율 강제 | P1 | 미구현 |
| FR-TRAIN-06 | Continued pretraining (낮은 LR) | P2 | 미구현 |

### 4-4. DAW 통합 (FR-DAW)
| ID | 요구사항 | 우선순위 | 상태 |
|----|----------|----------|------|
| FR-DAW-01 | Ableton Bridge | P0 | ✅ |
| FR-DAW-02 | Cubase 15 어휘 통합 | P0 | ✅ |
| FR-DAW-03 | JUCE C++ 프론트엔드 | P0 | ✅ (기본) |
| FR-DAW-04 | VST3 호스팅 모듈 | P1 | 미구현 |
| FR-DAW-05 | CLAP 호스팅 모듈 | P2 | 미구현 |
| FR-DAW-06 | Logic Pro 통합 | P2 | 미구현 |
| FR-DAW-07 | FL Studio 통합 | P3 | 미구현 |

### 4-5. 보조 도구 (FR-AUX)
| ID | 요구사항 | 우선순위 | 상태 |
|----|----------|----------|------|
| FR-AUX-01 | Audio2MIDI (Demucs + Basic Pitch) | P1 | ✅ |
| FR-AUX-02 | Sheet2MIDI (SMT++ OMR) | P1 | ✅ |
| FR-AUX-03 | 멀티 에이전트 백엔드 | P1 | ✅ |
| FR-AUX-04 | LoRA 마켓플레이스 (Phase C) | P3 | 미구현 |

---

## 5. 비기능 요구사항 (NFR)

### 5-1. 성능
- **추론 latency**: RTX 3060+ 기준 30초 변주 1개 < 5초
- **VRAM**: FP16 추론 < 4GB, 학습 < 12GB (RTX 3060)
- **스토리지**: 베이스 모델 < 200MB, LoRA 1개 < 30MB

### 5-2. 신뢰성
- **재현성**: 동일 시드 + 동일 LoRA에서 동일 출력 (100%)
- **장애 복구**: 학습 중 crash 시 latest checkpoint에서 재개
- **인코딩 안전**: 모든 텍스트 IO `encoding='utf-8'` 강제 (Windows CP949 회귀 방지)

### 5-3. 호환성
- **OS**: Windows 10/11, macOS 12+, Linux (Ubuntu 22.04+)
- **Python**: 3.11+
- **PyTorch**: 2.0+ (FlashAttention 자동)

### 5-4. 사용성
- **설치**: `pip install -r requirements.txt` 한 번에 통과 (BUG 2 회귀 방지)
- **첫 실행**: `setup_check.py` 8단계 PASS
- **첫 변주 생성**: 신규 사용자가 5분 내 첫 결과물 청취 가능

### 5-5. 보안 / 라이선스
- 학습 데이터 출처 모두 명시 (`midi_data/SOURCES.md`)
- 모든 사용자 업로드 MIDI는 로컬 저장만 (클라우드 미전송, Phase C까지)
- 베이스 모델: MIT 라이선스
- LoRA 어댑터: 작가별 라이선스 선택 가능

---

## 6. MVP 정의 (Minimum Viable Product)

**MVP 출시 조건 (= Phase B 진입 조건)**:

### 기술 조건
- [ ] 데이터 ≥ 1500곡 (현재 54)
- [ ] Pre-training train/val gap < 1.0 (현재 2.6)
- [ ] 생성 MIDI 평균 크기 ≥ 8KB (현재 ~2KB)
- [ ] 생성 MIDI 평균 길이 ≥ 30초 (현재 ~5초)
- [ ] LoRA 어댑터 ≥ 3개 (재즈/시티팝/메탈)
- [ ] VST3 프로토타입 동작 (Cubase에서 호스팅 가능)

### 품질 조건 (사람 청취)
- [ ] 외부 작곡가 5명 패널이 30분 청취 후 평균 평점 ≥ 7/10
- [ ] "음악으로 인지됨" 응답률 ≥ 90%
- [ ] "스타일이 식별됨" 응답률 ≥ 70%

### 제품 조건
- [ ] 데스크톱 앱 첫 실행부터 변주 생성까지 < 5분
- [ ] 인코딩/경로 회귀 버그 0건
- [ ] 한국어 UI

---

## 7. 성공 지표 (Success Metrics)

### 7-1. Pre-launch (현재 ~ MVP)
- 동업자 패널 5-10명 확보
- 데이터 수집 진척률 (월별 +200곡)
- train/val gap 추이 (월별 -0.3)

### 7-2. Closed Beta (MVP 후 6개월)
- 베타 사용자 50명
- 주간 활성 사용자(WAU) 30명
- 사용자당 주간 변주 생성 횟수 평균 10회
- NPS ≥ 30

### 7-3. Public Beta
- 등록 사용자 1000명
- WAU 300명
- 유료 전환율 5%

### 7-4. Commercial
- Pro 구독 100건 (월 매출 $1500)
- LoRA 마켓 거래 월 50건
- 12개월 retention ≥ 40%

---

## 8. 출시 마일스톤

| 마일스톤 | 조건 | 분기 |
|----------|------|------|
| **M0: 안정화** | 회귀 버그 0, min_new_tokens 적용 | 2026 Q2 |
| **M1: 데이터 1k** | 1000곡, 자동 필터 적용 | 2026 Q2 |
| **M2: 데이터 2k+** | 2000곡, train/val gap < 1.0 | 2026 Q3 |
| **M3: CFG 학습** | 스타일 통제력 검증 | 2026 Q3 |
| **M4: VST3 alpha** | Cubase 호스팅 동작 | 2026 Q4 |
| **M5: Closed Beta** | 외부 50명, NPS ≥ 30 | 2027 Q1 |
| **M6: 1.0 출시** | Pro 구독 시작 | 2027 Q2 |

---

## 9. 의존성 / 가정

### 9-1. 가정
- 동업자 작곡가가 월 50-100곡 추가 기여 가능
- Lakh MIDI 데이터셋 라이선스 변동 없음
- RTX 3060 이상 GPU가 타겟 사용자의 50%+ 보유

### 9-2. 외부 의존
- PyTorch 2.0+ (FlashAttention)
- Demucs 4.0+ (Audio2MIDI)
- Basic Pitch (Spotify, Audio2MIDI)
- SMT++ (Sheet2MIDI OMR)
- JUCE 7+ (DAW 플러그인)

---

## 10. 변경 이력

- 2026-04-09: 초판 작성 (3-페르소나 라운드테이블 결과 반영)
