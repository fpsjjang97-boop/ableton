# Audio → MIDI 변환 보조 도구

> 음원(MP3/WAV)에서 보컬 제거 → 악기별 분리 → MIDI 자동 변환

## 목적

동업자들의 MIDI 데이터 제작 부담을 줄이기 위한 보조 도구.
자동 변환(~80-90%) 후 DAW에서 사람이 보정하여 98%+ 품질 확보.

## 파이프라인

```
MP3/WAV 입력
    ↓
[1] 보컬 제거 + 악기 분리 (Demucs)
    → vocals.wav (버림)
    → drums.wav
    → bass.wav
    → other.wav (피아노/기타/현악 등)
    ↓
[2] Audio → MIDI 변환 (Basic Pitch / MT3)
    → drums.mid
    → bass.mid
    → other.mid
    ↓
[3] 트랙 합치기 → Type 1 MIDI 출력
    ↓
[4] 동업자가 DAW에서 보정 (→ 98%+ 정확도)
```

## 예상 작업 시간 비교

| 방법 | 곡당 소요 시간 |
|------|---------------|
| 처음부터 MIDI 직접 제작 | 3~5시간 |
| 자동 변환 + 사람 보정 | 30분~1시간 |

## 필요 라이브러리

```bash
pip install demucs basic-pitch pretty_midi
```

## 상태: 🔜 개발 예정

구현 파일:
- `convert.py` — 메인 변환 스크립트 (예정)
- `merge_tracks.py` — 분리된 MIDI 트랙 합치기 (예정)
