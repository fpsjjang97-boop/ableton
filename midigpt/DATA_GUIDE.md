# MidiGPT 학습 데이터 수집 가이드

## 동업자분들께

MidiGPT 학습을 위해 MIDI 파일이 필요합니다.
아래 기준에 맞는 MIDI 파일을 `midi_data/` 폴더에 넣어주세요.

## MIDI 파일 넣는 곳

```
repo/
  midi_data/          ← 이 폴더에 넣어주세요
    classical/        ← 장르별로 분류하면 좋음 (필수 아님)
    jazz/
    pop/
    original/         ← 직접 만든 MIDI
    기타.mid           ← 분류 없이 넣어도 됨
```

## 좋은 데이터 기준

### 포함해야 할 것
- 코드 진행이 있는 MIDI (화성 학습에 필수)
- 멜로디 + 반주가 분리된 트랙 (트랙 분리 학습)
- 다양한 장르 (jazz, pop, classical, lo-fi 등)
- 다양한 키 (C major만 있으면 편향됨)
- 다양한 템포 (60~200 BPM)

### 피해야 할 것
- 드럼만 있는 MIDI (화성 정보 없음)
- 1마디 미만의 너무 짧은 파일
- 손상된 MIDI 파일
- 저작권 문제가 있는 상업 음원의 완전 복제 MIDI

### 가장 가치 있는 데이터
- **직접 작곡/편곡한 MIDI** (원본 데이터, 저작권 문제 없음)
- **변주를 만든 원본-변주 쌍** (SFT 학습에 직접 사용)

## 무료 MIDI 데이터셋

| 데이터셋 | 곡 수 | 장르 | 링크 |
|---------|-------|------|------|
| MAESTRO v3 | 1,276곡 | 클래식 피아노 | https://magenta.tensorflow.org/datasets/maestro |
| Lakh MIDI | 176,581곡 | 다양 | https://colinraffel.com/projects/lmd/ |
| POP909 | 909곡 | 팝 | https://github.com/music-x-lab/POP909-Dataset |
| ADL Piano MIDI | 11,086곡 | 다양 | https://github.com/lucasnfe/adl-piano-midi |

## 원본-변주 쌍 만드는 방법

가장 가치 있는 데이터입니다. 앱이나 DAW에서:

1. 원본 MIDI 로드
2. 화성/멜로디/리듬 변주 만들기
3. 원본과 변주를 함께 저장

```
midi_data/pairs/
  song01_original.mid
  song01_variation.mid
  song02_original.mid
  song02_variation.mid
```

## 올리는 방법

```bash
git add midi_data/
git commit -m "data: MIDI 학습 데이터 추가"
git push
```

## 이후 진행

1. MIDI 파일이 쌓이면 토큰화 + Pre-training 실행
2. 학습된 모델로 변주 생성 시작
3. 동업자분들이 결과 리뷰 (👍👎)
4. 리뷰 데이터로 모델 개선 (DPO)
5. 반복 → 모델 체급 상승
