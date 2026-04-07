# MidiGPT — 그루브 엔진 명세

> 스윙/셔플, 그루브 추출, 드럼 패턴 에디터의 표준 명세
> 분류: 음악 기능 영역
> 코드: `app/core/groove_engine.py`

---

## 개요

`GrooveEngine`은 박자의 미세 타이밍(microtiming)과 드럼 패턴을 다루는 모듈이다.
정량 그리드에서 벗어난 인간적 그루브를 부여하거나, 기존 곡에서 그루브를 추출해
다른 트랙에 적용할 수 있다.

### 핵심 흐름
```
정량 노트 → 그루브 템플릿 적용 → 미세 타이밍 부여 → 사람다운 연주
                  ↑
            (직접 추출 or 프리셋)
```

---

## 1. 스윙 / 셔플 템플릿

**코드 위치**: `app/core/groove_engine.py`

### 프리셋 (7종)
| 이름 | 설명 |
|------|------|
| MPC Swing 50% | 정량 그리드 (no swing) |
| MPC Swing 58% | 약한 스윙 |
| MPC Swing 62% | 중간 스윙 |
| MPC Swing 66% | 강한 스윙 (재즈 스윙) |
| MPC Swing 70% | 극단 스윙 |
| Funk Pocket | 16분음표 마이크로 슬립 |
| Bossa Nova | 라틴 클라베 |

### 동작 규칙
- 짝수 16분음표(2nd, 4th, ...)를 뒤로 미는 비율
- 50% = 정량, 66% = 트리플렛 스윙, 75% = 셔플

---

## 2. 그루브 추출 (Groove Extraction)

### 동작 규칙
1. 입력 노트의 onset 시간과 정량 그리드의 차이 계산
2. 각 16분음표 위치별 평균 offset 산출
3. 결과를 `GrooveTemplate(velocities, offsets)` 객체로 저장
4. 다른 트랙에 적용 가능

### 사용처
- 좋아하는 곡의 그루브를 자기 비트에 적용
- 사람 연주 → 학습 데이터 증강

---

## 3. 드럼 패턴 에디터 (Step Sequencer)

### 동작 규칙
- 16/32 step grid
- GM 드럼 매핑 준수 (kick=36, snare=38, hihat=42, ...)
- 셀: pitch + velocity + accent 플래그

### 드럼 테크닉
| 종류 | 설명 |
|------|------|
| Flam | 본음 직전 미세 작은 음 |
| Roll | 빠른 연속 타격 |
| Ruff | 본음 직전 2~3개 작은 음 |
| Ghost note | 매우 약한 보조음 |

### 구현 상태
- ✅ 기본 step sequencer
- ✅ Flam, Roll, Ruff 생성
- 🔶 부분: ghost note 분류는 토큰 레벨에서만

---

## 4. API

```python
from app.core.groove_engine import GrooveEngine

engine = GrooveEngine()

# 스윙 적용
swung_notes = engine.apply_swing(notes, ratio=0.66)

# 그루브 추출
template = engine.extract_groove(reference_notes)
applied = engine.apply_template(target_notes, template)

# 드럼 패턴 생성
pattern = engine.create_drum_pattern(steps=16, kick=[0,4,8,12], snare=[4,12])
```

---

## 5. 의존성

- numpy (타이밍 계산)
- 표준 GM 드럼 매핑

---

## 6. 검증 항목

- [x] 정량 노트 + 50% 스윙 = 입력과 동일
- [x] 그루브 추출 → 적용 roundtrip 시 평균 offset 일치
- [x] Flam/Roll 노트 수 정확

---

## 7. 호환성

| 변경 | 등급 |
|------|------|
| 새 프리셋 추가 | 🟢 안전 |
| GM 매핑 변경 | 🟡 외부 호환성 깨질 수 있음 |
| Velocity 양자화 변경 | 🟠 토큰화 결과 영향 |

---

## 8. 향후 개선 후보

| 항목 | 비고 |
|------|------|
| 장르별 그루브 프리셋 확장 | Reggae one-drop, Latin tumbao, Trap hi-hat roll |
| Drum Fill 자동 생성 | 4/8/16마디 끝 |
| 사람다움 점수 (humanization metric) | 그루브 품질 평가 |
| Swing curve (시간에 따라 변화) | 정적 비율 → 동적 |
| Velocity 변동 자동 | 약박/강박 자연 |
