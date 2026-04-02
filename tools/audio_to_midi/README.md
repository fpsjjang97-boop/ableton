# Audio → MIDI 변환 보조 도구

> 음원(MP3/WAV)에서 보컬 제거 → 악기별 분리 → MIDI 자동 변환

## 목적

동업자들의 MIDI 데이터 제작 부담을 줄이기 위한 보조 도구.
자동 변환(~80-90%) 후 DAW에서 사람이 보정하여 98%+ 품질 확보.

## 설치

```bash
pip install demucs basic-pitch pretty_midi mido numpy
```

> GPU(CUDA)가 있으면 Demucs가 훨씬 빠릅니다.
> PyTorch CUDA 버전: https://pytorch.org/get-started/locally/

## 사용법

```bash
# 단일 파일 변환
python convert.py "노래.mp3"

# 출력 폴더 지정
python convert.py "노래.mp3" --output_dir ./output

# 폴더 일괄 변환
python convert.py ./music_folder --batch

# 보컬 트랙도 MIDI로 변환 (멜로디 추출용)
python convert.py "노래.mp3" --keep_vocals

# 트랙별 개별 MIDI 유지 (합치지 않음)
python convert.py "노래.mp3" --no_merge

# 더 정확한 Demucs 모델 사용 (느리지만 분리 품질 향상)
python convert.py "노래.mp3" --demucs_model htdemucs_ft
```

## 파이프라인

```
MP3/WAV 입력
    ↓
[1] 보컬 제거 + 악기 분리 (Demucs)
    → vocals.wav (기본: 버림, --keep_vocals로 유지)
    → drums.wav
    → bass.wav
    → other.wav (피아노/기타/현악 등)
    ↓
[2] Audio → MIDI 변환 (Basic Pitch)
    → drums.mid   (onset 감도 높게 설정)
    → bass.mid    (저음역 주파수 제한)
    → other.mid   (기본 설정)
    ↓
[3] 트랙 합치기 → Type 1 MIDI 출력
    → 곡이름_converted.mid
    ↓
[4] 동업자가 DAW에서 보정 (→ 98%+ 정확도)
```

## 출력 구조

```
audio_to_midi_output/
  곡이름/
    stems/                    # Demucs 분리 결과
      곡이름_drums.wav
      곡이름_bass.wav
      곡이름_other.wav
      곡이름_vocals.wav
    midi_tracks/              # 개별 MIDI
      곡이름_drums.mid
      곡이름_bass.mid
      곡이름_other.mid
    곡이름_converted.mid      # 합쳐진 최종 MIDI (Type 1)
```

## 트랙별 변환 설정

| 트랙 | onset 감도 | 주파수 범위 | 비고 |
|------|-----------|------------|------|
| drums | 0.6 (높음) | 전체 | 타격음 정밀 감지 |
| bass | 0.5 | 30~300Hz | 저음역만 캡처 |
| other | 0.45 (낮음) | 전체 | 코드/아르페지오 포착 |
| vocals | 0.5 | 80~1200Hz | --keep_vocals 시만 |

## Demucs 모델 비교

| 모델 | 분리 품질 | 속도 | 권장 |
|------|----------|------|------|
| htdemucs | 좋음 | 빠름 | 기본값 |
| htdemucs_ft | 매우 좋음 | 느림 | 최종 결과물용 |
| mdx_extra | 좋음 | 보통 | 대안 |

## 예상 작업 시간 비교

| 방법 | 곡당 소요 시간 |
|------|---------------|
| 처음부터 MIDI 직접 제작 | 3~5시간 |
| 자동 변환 + 사람 보정 | 30분~1시간 |

## 보정 팁 (동업자용)

1. 변환된 MIDI를 DAW에서 열기
2. 확인 포인트:
   - **드럼**: GM 매핑 맞는지 (킥=36, 스네어=38, 하이햇=42)
   - **베이스**: 옥타브 틀린 노트 없는지
   - **other**: 코드 보이싱 정확한지, 유령 노트 제거
3. 보정 완료 후 `midi_data/`에 저장 → Git Push
