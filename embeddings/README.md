# MIDI Embeddings — MAESTRO 2018 피아노 데이터셋

## 데이터 출처

| 항목 | 내용 |
|------|------|
| **원본** | MAESTRO (MIDI and Audio Edited for Synchronous TRacks and Organization) 2018 |
| **장르** | 클래식 피아노 (Chamber, Recital, Schubert) |
| **파일 수** | 93개 MIDI |
| **총 노트 수** | 873,158개 |
| **생성일** | 2026-03-23 |
| **생성 도구** | `tools/midi_embedding.py` + pretty_midi |

---

## 파일 구조 및 용도

```
embeddings/
├── README.md                  # 이 파일 — 전체 설명
├── embedding_matrix.npy       # [용도 1] 유사도 검색 / 클러스터링 / 변주 생성
├── metadata.json              # 파일명 ↔ 인덱스 매핑
├── summary.json               # 93개 파일 전체 통계 요약
└── individual/                # [용도 2] 개별 곡 노트 데이터 (변주/학습용)
    ├── {filename}.json        # 곡별 전체 노트 + 히스토그램 + 임베딩
    └── ...                    # (93개 파일)
```

---

## 임베딩 벡터 구조 (128차원)

`embedding_matrix.npy`의 각 행은 하나의 MIDI 파일을 128차원 벡터로 표현합니다.

| 차원 | 범위 | 내용 | 용도 |
|------|------|------|------|
| `[0:12]` | 0~11 | **피치 클래스 히스토그램** (C, C#, D, ... B) | 조성 분석, 키 매칭 |
| `[12:37]` | 12~36 | **인터벌 히스토그램** (-12 ~ +12 반음) | 멜로디 패턴, 도약/순차 비율 |
| `[37:45]` | 37~44 | **벨로시티 히스토그램** (8구간: 0-15, 16-31, ... 112-127) | 다이나믹 스타일 |
| `[45:55]` | 45~54 | **듀레이션 히스토그램** (10구간: ~0.1s ~ 32s+) | 리듬 패턴, 빠르기 |
| `[55]` | 55 | 평균 피치 / 127 | 음역대 |
| `[56]` | 56 | 피치 표준편차 / 40 | 음역 넓이 |
| `[57]` | 57 | 평균 벨로시티 / 127 | 전체 세기 |
| `[58]` | 58 | 벨로시티 표준편차 / 40 | 다이나믹 변화폭 |
| `[59]` | 59 | 평균 듀레이션 / 10 | 평균 음 길이 |
| `[60]` | 60 | 듀레이션 표준편차 / 10 | 리듬 다양성 |
| `[61]` | 61 | 평균 BPM / 200 | 템포 |
| `[62]` | 62 | 총 재생시간 / 600 | 곡 길이 |
| `[63:128]` | 63~127 | **피치 분포 상위 65개** (정규화) | 세밀한 음높이 특성 |

> 모든 값은 0~1 범위로 정규화되어 있어 코사인 유사도/유클리드 거리 바로 사용 가능

---

## 개별 파일 JSON 구조 (`individual/*.json`)

```json
{
  "stats": {
    "filename": "...",
    "total_notes": 4991,
    "total_duration_sec": 582.25,
    "avg_tempo": 120.0,
    "pitch_range": [31, 89],
    "pitch_mean": 69.3,
    "pitch_std": 11.1,
    "velocity_range": [6, 100],
    "velocity_mean": 61.7,
    "velocity_std": 14.8,
    "duration_mean": 0.1696,
    "duration_std": 0.1923,
    "estimated_key": "A",
    "num_instruments": 1,
    "time_signatures": ["4/4"]
  },
  "notes": [
    {
      "pitch": 65,
      "start": 0.1234,
      "end": 0.5678,
      "duration": 0.4444,
      "velocity": 72,
      "instrument": 0,
      "instrument_name": "Acoustic Grand Piano",
      "is_drum": false
    }
  ],
  "embedding": [0.08, 0.12, ...],
  "pitch_histogram": [...],
  "pitch_class_histogram": [...],
  "interval_histogram": [...],
  "velocity_histogram": [...],
  "duration_histogram": [...]
}
```

---

## 활용 방법

### 1. 유사 곡 검색 — "이 MIDI와 비슷한 곡 찾기"

```python
import numpy as np, json

matrix = np.load('embeddings/embedding_matrix.npy')
meta = json.load(open('embeddings/metadata.json'))

# 입력 MIDI의 임베딩 (tools/midi_embedding.py의 analyze_midi 사용)
query = matrix[0]  # 또는 새 MIDI 분석 결과

# 코사인 유사도로 Top-5
sims = matrix @ query / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(query))
top5 = np.argsort(sims)[::-1][:5]
for idx in top5:
    print(f"{meta['files'][idx]}: {sims[idx]:.3f}")
```

### 2. 변주 생성 — "입력 MIDI + DB에서 스타일 믹싱"

```python
import json, random
import pretty_midi

# 입력 MIDI 분석
input_data = json.load(open('embeddings/individual/입력파일.json'))

# 유사 곡에서 리듬 패턴 차용
similar = json.load(open('embeddings/individual/유사곡.json'))

# 입력의 피치 + 유사곡의 리듬/벨로시티 조합
new_midi = pretty_midi.PrettyMIDI()
piano = pretty_midi.Instrument(program=0)
for note_in, note_ref in zip(input_data['notes'], similar['notes']):
    piano.notes.append(pretty_midi.Note(
        velocity=note_ref['velocity'],      # 유사곡의 다이나믹
        pitch=note_in['pitch'],             # 입력곡의 멜로디
        start=note_ref['start'],            # 유사곡의 리듬
        end=note_ref['start'] + note_in['duration']
    ))
new_midi.instruments.append(piano)
new_midi.write('variation_output.mid')
```

### 3. 클러스터링 — "곡 분류/그룹핑"

```python
from sklearn.cluster import KMeans

matrix = np.load('embeddings/embedding_matrix.npy')
clusters = KMeans(n_clusters=5).fit_predict(matrix)
# → Chamber/Recital/Schubert 자동 분류 가능
```

### 4. 조성 분석 — "키 분포 확인"

```python
# pitch_class_histogram[0:12] = [C, C#, D, D#, E, F, F#, G, G#, A, A#, B]
data = json.load(open('embeddings/individual/파일명.json'))
keys = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
for k, v in zip(keys, data['pitch_class_histogram']):
    print(f"{k}: {'█' * int(v*50)} {v:.3f}")
```

---

## 히스토그램 해석 가이드

| 히스토그램 | 차원 | 해석 |
|-----------|------|------|
| `pitch_class_histogram` | 12 | 값이 높은 피치 = 해당 곡의 주요 음. 가장 높은 값 = 추정 조성의 으뜸음 |
| `interval_histogram` | 25 | 중앙(idx=12, 인터벌=0) 높으면 반복음 많음. 양 끝 높으면 도약 진행 |
| `velocity_histogram` | 8 | 왼쪽 집중 = 부드러운 곡, 오른쪽 집중 = 강한 곡, 고른 분포 = 다이나믹 풍부 |
| `duration_histogram` | 10 | 왼쪽 집중 = 빠른 패시지, 오른쪽 집중 = 긴 음표/페달 사용 |

---

## 데이터셋 구성

| 카테고리 | 파일 수 | 특징 |
|----------|---------|------|
| Chamber (실내악) | 7 | 앙상블 피아노, 긴 곡 |
| Recital (독주회) | 74 | 다양한 레퍼토리, 기교적 |
| Schubert (슈베르트) | 12 | 슈베르트 소나타, 낭만파 스타일 |

---

## 재생성 방법

임베딩을 다시 생성하거나 새 MIDI를 추가하려면:

```bash
# 새 MIDI 파일을 Ableton/midi_raw/에 추가 후
python tools/midi_embedding.py
```
