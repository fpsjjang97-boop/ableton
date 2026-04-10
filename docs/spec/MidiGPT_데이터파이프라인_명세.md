# MidiGPT — 데이터 파이프라인 명세

> 데이터 수집/증강/토큰화/저장의 표준 명세
> 분류: 데이터 파이프라인 영역
> 코드: `midigpt/augment_dataset.py`, `midigpt/tokenize_dataset.py`, `midigpt/pipeline.py`

---

## 개요

학습 데이터는 4단계를 거쳐 모델 학습용 텐서로 변환된다.

```
원본 MIDI → 증강 (전조 + 트랙 드롭아웃) → 토큰화 → .npy 저장 → 학습
```

---

## 1. 데이터 수집

### 소스
| 소스 | 곡 수 | 내용 |
|------|------|------|
| MAESTRO 2018 | 93 | 클래식 피아노 (CC BY-NC-SA 4.0) |
| 동업자 직접 업로드 | 11 | J-POP, City Pop, Latin, Waltz, Hiphop, Metal, House, Color 등 |
| **총** | **104** | (Phase 2 기준) |
| 목표 | 2,000+ | (장기) |

### 폴더 구조
```
midi_data/         # 학습용 MIDI 저장소
TEST MIDI/         # 동업자 업로드 영역
Ableton/midi_raw/  # MAESTRO 등 외부 데이터셋
```

### 데이터 가이드
- Type 1 MIDI 권장 (Type 0 자동 변환)
- 드럼은 채널 10 + GM 매핑
- CC 데이터(서스테인, 익스프레션) 포함 권장
- 자세한 기준: `midigpt/DATA_GUIDE.md`

---

## 2. 데이터 증강 (Augmentation)

**코드 위치**: `midigpt/augment_dataset.py`

### 동작 규칙

#### 키 전조 (Pitch Transposition)
- 1~11 반음 전조 (총 12개 키)
- 드럼 트랙 제외 (GM 매핑 보존)

#### 트랙 드롭아웃 (Track Dropout)
- 멀티 트랙 곡에서 임의 트랙 부분집합 학습
- 화성 트랙은 항상 1개 이상 보존
- 비조화 트랙(드럼/SFX)도 보존

### 증강 비율
- 원본 1곡 → 약 15곡 (12 transpose + 3 dropout 변형)
- 104곡 × 15 = ~1560곡

### 위험 요소
- 🟡 너무 강한 jitter → augmentation artifact 학습
- 🟡 transpose 12 전체 적용 시 rare key 분포 왜곡

---

## 3. 토큰화 (Tokenization)

**코드 위치**: `midigpt/tokenize_dataset.py`

### 동작 규칙
1. 증강된 MIDI 폴더 순회
2. `pretty_midi`로 파싱
3. 화성 분석 → `ChordEvent` 리스트 생성
4. 메타 추출 → `SongMeta`
5. `MidiEncoder.encode_file()` → 토큰 시퀀스
6. `.npy` 파일로 저장 (배치 효율적)

### 출력 구조
```
midigpt_pipeline/          # pipeline.py 기본 work_dir
├── tokenized/
│   ├── tokens/            # 실제 .npy 저장 위치
│   │   ├── song_001.npy
│   │   ├── song_002.npy
│   │   └── ...
│   └── metadata.json
└── augmented/             # 증강 중간 결과
```

> ⚠️ `train_pretrain.py`의 `--data_dir` 기본값이 `./midigpt_pipeline/tokenized`로 설정되어 있어
> pipeline 실행 후 별도 경로 지정 없이 바로 학습 가능 (2026-04-08)

### 메타데이터
```python
SongMeta(key="C", style="pop", section="verse", tempo=120)
ChordEvent(root="C", quality="maj7", bass="C", function="tonic", start_beat=0.0, end_beat=4.0)
```

---

## 4. Dataset 클래스

**코드 위치**: `midigpt/data/dataset.py`

### `MidiDataset(mode="pretrain", block_size=2048)`
- `.npy` 파일 자동 로드
- **자동 경로 탐색** (2026-04-08): `_load_pretrain`이 다음 3개 경로를 순서대로 탐색
  1. `{data_dir}/tokens/` — 정상 레이아웃
  2. `{data_dir}/` — data_dir이 토큰 폴더 자체일 때
  3. `{data_dir}/tokenized/tokens/` — pipeline work_dir 직접 패스
- 못 찾으면 탐색한 경로 + 해결 방법을 포함한 에러 메시지 출력
- 시퀀스 → block_size 슬라이딩 청크 분할
- `__getitem__` → `{"input_ids", "labels"}` 딕셔너리

### `MidiCollator`
- 배치 패딩 (PAD=0)
- 90/10 train/val split 외부에서 처리

---

## 5. 올인원 파이프라인

**코드 위치**: `midigpt/pipeline.py`

```bash
python -m midigpt.pipeline --midi_dir "./TEST MIDI" --epochs 10
```

순차 실행:
1. augment_dataset
2. tokenize_dataset
3. train_pretrain

---

## 6. 검증 항목

- [x] 증강 후 곡 수 = 원본 × 12 (transpose) 이상
- [x] 토큰 시퀀스 길이 분포 확인 (block_size 초과 비율 < 5%)
- [x] 토큰 vocab coverage (모든 그룹별 등장 빈도)
- [ ] 키 분포 균등성 (rare key oversampling 필요 여부)

---

## 7. 호환성

| 변경 | 등급 |
|------|------|
| 새 데이터셋 추가 | 🟢 안전 (포맷 동일하면) |
| 새 증강 방식 추가 | 🟡 분포 변화 주의 |
| 토큰 vocab 변경 | 🔴 모든 .npy 재생성 필요 |
| `block_size` 변경 | 🟠 청크 분할 결과 변동 |

---

## 8. 향후 개선 후보

| 항목 | 등급 | 비고 |
|------|------|------|
| Velocity Jitter (±10%) | 🟡 안전선 | 표현력 다양화 |
| Time Stretch (±5%) | 🟡 안전선 | 템포 다양성 |
| Track Shuffle | 🟢 | 악기 순서 무관 학습 |
| Chord Inversion 증강 | 🟠 | vocab 추가 필요 |
| Lakh MIDI 통합 | 🟠 | 품질 필터링 필수 |
| MetaMIDI 통합 | 🟠 | 약 430K곡 |
| GiantMIDI-Piano | 🟢 | ~10K곡, 피아노 전용 |
| Slakh2100 | 🟢 | 멀티 stem |
| 합성 데이터 (코드 진행 자동) | 🟡 | 비율 ≤15% |
| 자동 품질 필터 | 🟢 | 노이즈/박자 안정성/노트 밀도 |

⚠️ **Lakh MIDI 통합 시 필수 필터**:
- 트랙 수 ≥ 4
- 박자표 일관성
- 노트 밀도 정상 (너무 sparse/dense 제거)
- 키 일관성

상세 → [MidiGPT_개선로드맵_명세.md](MidiGPT_개선로드맵_명세.md)
