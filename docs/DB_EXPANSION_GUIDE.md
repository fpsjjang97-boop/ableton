# DB Expansion Guide — How to Grow the Pattern Database

**Target Audience**: 개발팀 (동업자 포함)
**Last Updated**: 2026-03-29

---

## 현재 DB 구조

```
Rule Layer (있음)
│   260327_최종본_v2.07_song_form_added.json  ← 분석/생성 규칙
│
Data Layer (있음)
│   Ableton/midi_raw/          ← 93 MAESTRO MIDI
│   embeddings/                ← 93개 벡터 + matrix
│
Pattern Layer (구축 중)
│   analyzed_chords/           ← MAESTRO 자동 분석 결과
│   pattern_library/           ← 추출된 패턴 (자동 축적 대상)
```

---

## 1. 수동 추가 방법 (지금부터 가능)

### MIDI 파일 추가
```bash
# 1. MIDI 파일을 midi_raw/ 아래에 장르별로 넣기
cp new_song.mid Ableton/midi_raw/jazz/

# 2. 앱에서 자동 분석 실행 (AI → Analyze Harmony)
#    또는 CLI:
cd app && python -c "
from core.harmony_engine import HarmonyEngine
from core.models import Track, Note
he = HarmonyEngine()
# ... MIDI 파싱 후 analyze_harmony() 호출
"

# 3. 결과 확인 후 git push
git add analyzed_chords/new_song.json
git push
```

### Rule DB 수정
Rule DB JSON을 직접 편집할 때 주의사항:
- `schema_version` 번호를 올릴 것 (2.07 → 2.08)
- `hard_constraints.rules[]`에 추가할 때 `id` 필드 유니크하게
- `developer_notes[]`에 변경 이유 기록
- 변경 후 앱 실행하여 로드 에러 없는지 확인

### settings.json 코드 진행 추가
```json
{
  "chord_progression": [
    {"chord": "CMaj7", "duration": "full"},
    {"chord": "Am7",   "duration": "half"},
    {"chord": "Dm7",   "duration": "half"},
    {"chord": "G7",    "duration": "full"}
  ]
}
```
- `chord`: 코드명 (Maj7, m7, 7, dim, aug, sus4, m7b5 등)
- `duration`: "full" (1마디) 또는 "half" (반마디)

---

## 2. 자동 축적 파이프라인 (Phase별)

### Phase 1: 분석 자동화 (지금)
새 MIDI가 추가되면 자동 분석:
```
Input:  Ableton/midi_raw/**/*.mid
Output: analyzed_chords/{filename}.json
```

각 분석 JSON 구조:
```json
{
  "source_file": "파일명.mid",
  "analysis_date": "2026-03-29",
  "rule_db_version": 2.07,
  "key_estimate": "D",
  "harmony": {
    "segments": [
      {
        "bar": 1,
        "chord": "DMaj7",
        "confidence": 0.85,
        "root": "D",
        "quality": "maj7",
        "alternatives": [{"label": "Bm9", "confidence": 0.6}]
      }
    ],
    "chord_count": 8,
    "overall_score": 75
  },
  "song_form": {
    "form_type": "verse-chorus",
    "sections": [
      {"label": "intro", "start_bar": 1, "end_bar": 4, "avg_energy": 0.3},
      {"label": "verse", "start_bar": 5, "end_bar": 20, "avg_energy": 0.5}
    ]
  },
  "playability": {
    "score": 95,
    "issues": []
  },
  "statistics": {
    "total_notes": 1234,
    "total_bars": 32,
    "density_notes_per_beat": 2.5,
    "unique_chords": 8
  }
}
```

### Phase 2: 패턴 추출 (100곡 이후)
```
analyzed_chords/*.json → pattern_library/ 자동 생성

chord_progressions.json:
  - 빈도수 기준 top-50 코드 진행 n-gram
  - 장르별 통계

voicing_examples.json:
  - 코드 유형별 실제 보이싱 수집
  - 연주 가능성 점수 순 정렬

form_templates.json:
  - 곡 구조 유형별 통계
  - 평균 에너지 프로파일
```

### Phase 3: 자동 분류 (500곡 이후)
새 곡 입력 시 기존 패턴과 자동 비교:
```
1. Embedding 유사도 계산 (cosine similarity)
2. Top-K 유사곡 검색
3. 유사곡의 장르/보이싱/구조를 참고
4. 분석 결과 자동 저장 (confidence > 0.7일 때)
```

### Phase 4: 완전 자동화 (1000곡 이후)
```
MIDI 입력 → 분석 → 패턴 매칭 → 보이싱 생성 → DB 갱신
전 과정 자동. 사람 개입 = 결과 검증 + 예외 수정만.
```

---

## 3. Rule DB 확장 가이드

### 새 코드 퀄리티 추가
`chord_quality_rules[]`에 추가:
```json
{
  "id": "cq_new",
  "chord_quality": "7#11",
  "function_group": "dominant",
  "chord_tones": ["1", "3", "5", "#11", "b7"],
  "priority_tones": [
    {"degree": "3", "score": 1},
    {"degree": "#11", "score": 0.9},
    {"degree": "b7", "score": 0.8}
  ]
}
```

### 새 보이싱 템플릿 추가
`voicing_templates[]`에 추가:
```json
{
  "id": "vt_new",
  "name": "spread_rootless",
  "applies_to": ["maj7", "m7", "7"],
  "hands": {
    "left_hand": ["3_or_b3", "7_or_b7"],
    "right_hand": ["5", "9_or_tension"]
  }
}
```

### 새 스타일 프로파일 추가
`voicing_generation_rules.style_inversion_profiles[]`에 추가:
```json
{
  "style": "bossa_nova",
  "preferred_inversions": ["root", "first"],
  "bass_motion": "chromatic_approach",
  "density": "sparse",
  "typical_voicing_size": 4
}
```

---

## 4. 데이터 소싱 권장

| 소스 | 장르 | 규모 | 라이선스 |
|------|------|------|---------|
| MAESTRO 2018 (현재) | Classical Piano | 93곡 | Apache 2.0 |
| MAESTRO v3 (확장) | Classical Piano | ~1,200곡 | Apache 2.0 |
| Lakh MIDI Dataset | Pop/Rock/Mixed | ~170,000곡 | 연구용 |
| Jazz MIDI (iReal Pro exports) | Jazz Standards | ~1,300곡 | 개인 사용 |
| POP909 | Chinese Pop | 909곡 | 연구용 |
| GiantMIDI-Piano | Classical Piano | ~10,000곡 | CC-BY 4.0 |

---

## 5. 파일 네이밍 규칙

```
analyzed_chords/
  {원본파일명}.json                    — 분석 결과

pattern_library/
  chord_progressions.json              — 코드 진행 패턴 모음
  voicing_examples.json                — 보이싱 사례 모음
  form_templates.json                  — 곡 구조 템플릿
  bass_patterns.json                   — 베이스 패턴
  rhythm_patterns.json                 — 리듬 패턴
  genre_statistics.json                — 장르별 통계

Rule DB:
  YYMMDD_최종본_vX.XX_변경내용.json    — 버전별 Rule DB
```

---

## 6. 품질 관리

### 자동 검증 기준
- 코드 confidence < 0.5 → 수동 검토 필요 표시
- 연주 가능성 score < 70 → 보이싱 재생성
- Song form confidence < 0.4 → "unknown" 라벨 유지

### 주기적 점검
- 월 1회: pattern_library 재생성 (전체 corpus 기반)
- Rule DB 변경 시: 전체 analyzed_chords 재분석
- 새 장르 추가 시: style_profiles 확장 여부 확인
