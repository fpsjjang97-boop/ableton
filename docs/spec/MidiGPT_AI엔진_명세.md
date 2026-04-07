# MidiGPT — AI 엔진 명세

> 코드 진행 자동 생성, 스케일 스냅, 변주 도구의 표준 명세
> 분류: 음악 기능 영역
> 코드: `app/core/ai_engine.py`

---

## 개요

`AIEngine`은 사용자 친화적인 고수준 작곡 보조 기능을 제공한다.
LLM(MidiGPT)을 호출하기 전 단계의 규칙 기반 보조 도구이며, 빠르고 결정적이다.

### 핵심 흐름
```
사용자 입력 (장르/키/길이) → AI 엔진 → 코드 진행 / 스케일 스냅 / 변주
                                ↓
                       MidiGPT 추론 (선택)
```

---

## 1. 코드 진행 생성 (Chord Progression)

**코드 위치**: `app/core/ai_engine.py`

### 동작 규칙
- 장르별 코드 진행 템플릿 사전 정의
- 사용자가 키와 장르 선택 → 템플릿 → 키 전조

### 지원 장르 템플릿
| 장르 | 진행 예시 |
|------|----------|
| Pop | I-V-vi-IV (4-5-6-1) |
| Pop ballad | vi-IV-I-V |
| Jazz | ii-V-I, ii-V-I-vi |
| Blues | 12-bar blues |
| EDM | i-VI-III-VII |
| Lo-fi | iim7-V7-Imaj7-VImaj7 |

### 출력
```python
[
    ChordEvent("C", "maj", ...),
    ChordEvent("G", "maj", ...),
    ChordEvent("A", "min", ...),
    ChordEvent("F", "maj", ...),
]
```

---

## 2. 스케일 스냅 (Scale Snap)

### 동작 규칙
- 입력 노트 중 키/모드에 맞지 않는 음을 가장 가까운 적합한 음으로 이동
- 멜로디 라인의 윤곽 유지
- 옵션: 위로/아래로/가까운쪽

### 사용처
- AI 변주가 잘못된 음을 만들었을 때 후처리
- 사용자 직접 입력의 실수 보정

---

## 3. 변주 도구 (Variation Tools)

### 음역대 조절
- 옥타브 이동 (±1, ±2)
- 압축 / 확장 (음 사이 거리 조정)

### 리듬 조정
- 양자화 (1/4, 1/8, 1/16, 1/32)
- 스윙 비율 적용 (Groove 엔진 연계)
- 노트 길이 균등화

### 다이내믹스
- velocity 정규화
- crescendo / decrescendo 커브 적용

---

## 4. API

```python
from app.core.ai_engine import AIEngine

engine = AIEngine()

# 코드 진행 생성
progression = engine.generate_chord_progression(
    key="C", style="pop_ballad", length_bars=8
)

# 스케일 스냅
snapped = engine.snap_to_scale(notes, key="C", mode="major", direction="nearest")

# 옥타브 이동
shifted = engine.shift_octave(notes, octaves=+1)

# 양자화
quantized = engine.quantize(notes, grid="1/16", strength=0.8)
```

---

## 5. MidiGPT 연계

`AIEngine`은 LLM 추론 전후 단계로 사용된다:
1. AIEngine으로 초기 코드 진행 생성
2. MidiGPT로 멜로디/베이스 변주 생성
3. AIEngine으로 스케일 스냅 후처리

---

## 6. 검증 항목

- [x] 코드 진행 length가 요청한 bar 수와 일치
- [x] 스케일 스냅 결과가 모든 노트 in-key
- [x] 양자화 strength=0 → 변경 없음

---

## 7. 호환성

| 변경 | 등급 |
|------|------|
| 새 장르 템플릿 추가 | 🟢 안전 |
| 스케일 매핑 변경 | 🟡 출력 변동 |
| 양자화 알고리즘 교체 | 🟢 안전 |

---

## 8. 향후 개선 후보

| 항목 | 비고 |
|------|------|
| 장르별 진행 확장 | Reggae, Latin, K-pop, J-pop |
| Walking Bass 자동 생성 | 재즈 |
| Comping 패턴 자동 | 재즈 피아노/기타 |
| Strumming 패턴 | 어쿠스틱 기타 |
| Auto-arrangement | 멜로디 → 풀밴드 |
| Reharmonization | AI 엔진에서 후보 제시 |
