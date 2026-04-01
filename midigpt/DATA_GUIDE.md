# MidiGPT 학습 데이터 수집 가이드

## 동업자분들께

MidiGPT 학습을 위해 MIDI 파일이 필요합니다.
아래 기준에 맞는 MIDI 파일을 `midi_data/` 폴더에 넣어주세요.

---

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

폴더 구분 없이 그냥 넣어도 전부 처리됩니다.
단, 폴더별로 정리하면 나중에 **스타일별 LoRA 학습** 시 유리합니다.

---

## FAQ — 자주 묻는 질문

### Q1. 멜로디가 꼭 포함되어야 하나요?

**아닙니다.** 멜로디 없는 MIDI도 학습 가치가 있습니다.

- 반주만 있는 MIDI → 화성 진행 패턴 학습
- 베이스라인만 → 베이스 무빙 패턴 학습
- 리듬 섹션만 → 그루브 패턴 학습
- 패드/현악만 → 보이싱/텍스처 학습
- 멜로디+반주 → 가장 이상적이지만 필수는 아님

오히려 다양한 조합(풀 편곡, 반주만, 솔로 등)이 섞여 있는 게 좋습니다.

### Q2. 악기별로 라벨링을 해줘야 하나요?

**수동 라벨링 불필요합니다.** DAW에서 MIDI Export만 하면 자동 처리됩니다.

MIDI 파일에 이미 포함된 정보로 자동 분류:
- Channel 번호
- Program Number (GM 악기 번호)
- Track Name

우리 시스템이 자동으로 분류하는 방식:
```
Program 0-7     → keys (피아노/오르간)
Program 24-31   → guitar
Program 32-39   → bass
Program 40-55   → strings (현악/앙상블)
Program 56-63   → brass (금관)
Program 64-79   → woodwind (목관)
Program 80-87   → synth_lead
Program 88-95   → synth_pad
is_drum = true  → drums
```

**단, DAW에서 Export할 때 주의사항:**
```
⭐ Type 1 MIDI (멀티 트랙)로 Export — 트랙 분리 유지됨
❌ Type 0 MIDI (싱글 트랙)으로 Export하지 마세요 — 전부 합쳐져서 분리 불가
```

### Q3. 악기군 묶기 vs 개별 파일?

**하나의 MIDI 파일 안에 모든 트랙을 포함해주세요.**

좋은 예 (하나의 .mid 파일 안에):
```
Track 1: Violin 1      (Program 40, Channel 1)
Track 2: Violin 2      (Program 40, Channel 2)
Track 3: Viola          (Program 41, Channel 3)
Track 4: Cello          (Program 42, Channel 4)
Track 5: Contrabass     (Program 43, Channel 5)
```

나쁜 예 (개별 파일로 분리):
```
violin1.mid
violin2.mid
viola.mid
cello.mid
→ 악기 간 타이밍 관계가 소실됨
→ "바이올린이 이렇게 움직일 때 첼로가 어떻게 받치는지" 학습 불가
```

우리 시스템은 같은 악기군(Violin 1, 2 + Viola 등)을 자동으로 "strings" 그룹으로 묶어서 분석합니다.

### Q4. CC 데이터 (서스테인/익스프레션/모듈레이션 등)도 포함해야 하나요?

**포함해서 Export해주세요.** 지금 당장은 노트+벨로시티만 사용하지만, 나중에 활용합니다.

현재 사용하는 데이터:
```
✅ Note On/Off (피치)
✅ Velocity (세기)
✅ Duration (길이)
✅ Timing (위치)
```

현재 무시되지만 보존해야 할 데이터:
```
⏳ CC1   Modulation (모듈레이션)
⏳ CC7   Volume (볼륨)
⏳ CC11  Expression (익스프레션)
⏳ CC64  Sustain Pedal (서스테인 페달)
⏳ Pitch Bend (피치벤드)
⏳ Key Switch (키스위치)
⏳ Aftertouch (애프터터치)
```

Phase 3에서 이 데이터를 학습에 추가할 예정입니다.
MIDI 파일에 포함시켜도 용량 차이 거의 없으니 **빼지 말고 그대로 Export** 해주세요.

### Q5. 드럼 MIDI — 가상악기마다 매핑이 다른 경우?

**GM (General MIDI) 표준 매핑으로 통일해주세요.**

문제:
```
A사 드럼 가상악기: MIDI 38 = 스네어
B사 드럼 가상악기: MIDI 38 = 킥
→ 같은 노트인데 다른 소리 = 학습 오염
```

GM 표준 드럼 매핑:
```
MIDI 35 = Acoustic Bass Drum
MIDI 36 = Bass Drum 1 (킥)
MIDI 38 = Acoustic Snare (스네어)
MIDI 42 = Closed Hi-Hat (하이햇)
MIDI 46 = Open Hi-Hat
MIDI 49 = Crash Cymbal
MIDI 51 = Ride Cymbal
MIDI 47-50 = Toms
```

해결 방법 (택 1):
```
방법 1: DAW의 Drum Map 기능으로 GM 매핑 변환 후 Export (가장 확실)
방법 2: GM 호환 드럼 가상악기 사용 (EZDrummer, Addictive Drums 등)
방법 3: 매핑 정보 메모와 함께 제출 → 변환 스크립트로 처리
```

---

## 좋은 데이터 기준

### 포함해야 할 것
- 코드 진행이 있는 MIDI (화성 학습에 핵심)
- 다양한 장르 (jazz, pop, classical, lo-fi, edm 등)
- 다양한 키 (C major만 있으면 편향됨)
- 다양한 템포 (60~200 BPM)
- 멀티 트랙 MIDI (트랙 분리 학습)

### 피해야 할 것
- 드럼만 있는 MIDI (화성 정보 없음, 가치 낮음)
- 1마디 미만의 너무 짧은 파일
- 손상된 MIDI 파일
- 저작권 문제가 있는 상업 음원의 완전 복제 MIDI

### 가장 가치 있는 데이터 (순서)
1. **직접 작곡/편곡한 MIDI** (저작권 깨끗 + 우리 스타일)
2. **코드 진행이 명확한 곡** (화성 학습 핵심)
3. **멀티 트랙 MIDI** (악기 간 관계 학습)
4. **원본-변주 쌍** (SFT 학습에 직접 사용, 가장 귀한 데이터)

---

## DAW Export 체크리스트

MIDI 파일 내보내기 전 확인사항:

```
☑ Type 1 MIDI (멀티 트랙)로 Export
☑ 각 트랙의 Program Number(악기 번호) 올바르게 설정
☑ 드럼 트랙은 GM 매핑으로 통일
☑ CC 데이터 (서스테인, 익스프레션 등) 포함
☑ 트랙별 채널 분리 (전부 Channel 1에 합치지 않기)
☑ 악기군은 하나의 파일에 통합 (개별 파일 분리 ✗)
```

---

## 무료 MIDI 데이터셋

| 데이터셋 | 곡 수 | 장르 | 링크 |
|---------|-------|------|------|
| MAESTRO v3 | 1,276곡 | 클래식 피아노 | https://magenta.tensorflow.org/datasets/maestro |
| Lakh MIDI | 176,581곡 | 다양 | https://colinraffel.com/projects/lmd/ |
| POP909 | 909곡 | 팝 | https://github.com/music-x-lab/POP909-Dataset |
| ADL Piano MIDI | 11,086곡 | 다양 | https://github.com/lucasnfe/adl-piano-midi |

---

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

---

## 올리는 방법

```bash
git add midi_data/
git commit -m "data: MIDI 학습 데이터 추가"
git push
```

---

## 이후 진행

1. MIDI 파일이 쌓이면 토큰화 + Pre-training 실행
2. 학습된 모델로 변주 생성 시작
3. 동업자분들이 결과 리뷰
4. 리뷰 데이터로 모델 개선 (DPO)
5. 반복 → 모델 체급 상승
