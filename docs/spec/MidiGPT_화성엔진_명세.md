# MidiGPT — 화성 엔진 명세

> 코드 분석 / 보이싱 생성 / 송 폼 감지 등 화성 처리의 표준 명세
> 분류: 음악 기능 영역
> 코드: `app/core/harmony_engine.py`

---

## 개요

`HarmonyEngine`은 MIDI 노트 시퀀스로부터 코드를 자동 추출하고, 멜로디 인식형
보이싱을 만들고, intro/verse/chorus 등 송 폼을 감지하는 모듈이다. 이 결과는
토크나이저의 `ChordEvent`, `SongMeta`로 전달되어 학습/추론에 컨디션으로 사용된다.

### 핵심 흐름
```
MIDI 노트 → 윈도우 분할 → 코사인 유사도 코드 매칭 → 코드 라벨 시퀀스
                                     ↓
                          멜로디-인식 보이싱 생성
                                     ↓
                            송 폼 감지 (섹션 라벨)
```

---

## 1. 코드 분석 (Chord Labeling)

**코드 위치**: `app/core/harmony_engine.py`

### 동작 규칙
1. 시간 윈도우 단위(보통 1박)로 노트 슬라이스
2. 각 윈도우의 pitch class 분포 추출 (12차원 chroma)
3. 사전 정의 코드 템플릿(chroma 벡터) 들과 코사인 유사도 계산
4. 최댓값 코드를 라벨로 부여
5. 인접 윈도우 동일 코드 → 하나로 머지

### 지원 코드 종류 (24)
[MidiGPT_토크나이저_명세.md](MidiGPT_토크나이저_명세.md#layer-2-화성-harmony-55-토큰)의 `CHORD_QUALITIES`와 정렬:
- maj, min, dim, aug
- sus2, sus4
- 7, maj7, m7, m7b5, dim7, 7sus4
- add9, madd9, 6, m6
- 9, m9, maj9, 7b9, 7#9
- 11, 13, 5

### 출력
```python
ChordEvent(
    root="C",          # str (NOTE_NAMES 중 하나)
    quality="maj7",    # str (CHORD_QUALITIES 중 하나)
    bass="E",          # 슬래시 코드 (없으면 root와 동일)
    function="tonic",  # tonic/subdominant/dominant/predominant/passing/unknown
    start_beat=0.0,
    end_beat=4.0,
)
```

---

## 2. 멜로디 인식형 보이싱

### 동작 규칙
- 멜로디 트랙의 노트와 충돌하지 않는 보이싱 선택
- 음역대 (range) 제약: bass / mid / high 분할
- 4성부 (SATB) 또는 3성부 (피아노 RH) 모드

### 사용처
- AI 변주 생성 시 코드 트랙 보강
- 사용자가 직접 코드만 입력 → 풀 보이싱 자동

---

## 3. 송 폼 감지 (Section Detection)

### 동작 규칙
- 자기 유사도 행렬(self-similarity matrix) 기반
- 반복 구간 검출 → verse/chorus 후보
- 시작/끝 → intro/outro
- 변화점 → bridge/breakdown

### 출력 섹션 (10)
`intro / verse / prechorus / chorus / bridge / outro / interlude / solo / breakdown / unknown`

### 토큰화 연계
검출된 섹션 → `Sec_X` 토큰 → 학습 컨디션

---

## 4. API

```python
from app.core.harmony_engine import HarmonyEngine

engine = HarmonyEngine()
chords = engine.analyze_chords(notes, beats_per_bar=4)
voicings = engine.generate_voicing(chord, melody_notes, mode="piano_rh")
sections = engine.detect_song_form(notes, total_bars=32)
```

---

## 5. 의존성

- numpy (chroma 벡터, 코사인 유사도)
- pretty_midi (노트 데이터 구조)

---

## 6. 검증 항목

- [x] 표준 진행(I-V-vi-IV) 정확히 라벨링
- [x] 슬래시 코드(C/E) bass 노트 별도 인식
- [x] 무화성 구간 → `Chord_NC`
- [ ] verse/chorus 정확도 (테스트 데이터셋 필요)

---

## 7. 호환성

| 변경 | 등급 |
|------|------|
| 새 코드 quality 추가 | 🟠 vocab 토큰도 추가 필요 |
| 윈도우 크기 변경 | 🟡 라벨링 결과 변동 |
| 보이싱 알고리즘 교체 | 🟢 출력 형식만 유지하면 안전 |

---

## 8. 향후 개선 후보

| 항목 | 비고 |
|------|------|
| Voice Leading 엔진 | common-tone 연결, parallel 5ths/8ves 회피 |
| Counterpoint (대위법) | Fux 1~5종 |
| Cadence 분류 | authentic/plagal/half/deceptive |
| Modulation 감지 | 전조 자동 표시 |
| Reharmonization | 멜로디 유지, 코드 재배치 |
| Borrowed Chord 감지 | modal interchange 마커 |
| Tension Notes 표시 | 9th/11th/13th |
