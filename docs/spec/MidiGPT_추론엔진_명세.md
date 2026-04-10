# MidiGPT — 추론 엔진 명세

> 학습된 모델로부터 MIDI 변주를 생성하는 런타임 엔진의 표준 명세
> 분류: LLM / 모델 영역
> 코드: `midigpt/inference/engine.py`

---

## 개요

`MidiGPTInference`는 학습된 MidiGPT 모델을 앱에서 호출 가능한 형태로 래핑한 클래스다.
입력 MIDI/노트 → 토큰 → 모델 → 토큰 → 디코더 → 변주 MIDI/노트 dict 까지 한 번에 처리한다.

### 핵심 흐름
```
MIDI 입력 → MidiEncoder → 토큰 시퀀스 → <SEP> → 모델 generation
                                                      ↓
                                            (KV 캐시 + 화성 마스킹)
                                                      ↓
                                          MidiDecoder → 변주 노트
```

---

## 1. 구성

**코드 위치**: `midigpt/inference/engine.py:160-489`

### 클래스: `MidiGPTInference`

#### 초기화
```python
inference = MidiGPTInference(InferenceConfig(
    model_path="./checkpoints/midigpt_base.pt",
    lora_paths={"jazz": "./loras/jazz.pt", "lo-fi": "./loras/lofi.pt"},
    device="auto",          # auto / cuda / cpu
    quantize="auto",        # auto / fp16 / fp32
))
```

#### 디바이스 자동 감지
- `cuda` 사용 가능 시 GPU 우선
- VRAM 표시
- 미사용 시 CPU 폴백

#### 양자화
- `auto` + CUDA → FP16 (`model.half()`)
- 그 외 → FP32

---

## 2. 화성 마스킹 (Harmonic Constraint)

**코드 위치**: `midigpt/inference/engine.py:34-148, 249-284`

### 동작 규칙
1. 생성 중 매 step마다 컨텍스트의 가장 최근 코드 토큰 검색
   - `ChordRoot_X` + `ChordQual_X` 페어 (신규 팩터화)
   - `Chord_Cmaj7` 결합 토큰 (레거시)
2. 해당 코드의 스케일 산출 (`_SCALE_INTERVALS`)
3. 스케일 외 pitch 토큰 logit → `-inf`
4. 그 위에서 sampling

### 지원 스케일 매핑
| 코드 종류 | 스케일 |
|----------|--------|
| maj, maj7, maj9, add9, 6 | Ionian (장조) |
| min, m7, m9, madd9, m6 | Aeolian (자연단음계) |
| 7, 9, 13, 7sus4, 11 | Mixolydian |
| 7b9 | Half-Whole Diminished |
| 7#9 | Dominant #9 (블루스 인접) |
| dim, dim7 | Diminished (Half-Whole) |
| m7b5 | Locrian |
| aug | Whole Tone |
| sus2, sus4 | 부모 장조 |
| 5 (power chord) | 무제약 (12음 전부) |

### 무화성 (Chord_NC)
- 스케일 미적용 → 무제약

---

## 3. 샘플링 (Sampling)

### 기본 샘플러
- **Top-K** (k≤vocab_size): 상위 K개만 보존
- **Top-P (Nucleus)** (p∈(0,1]): 누적확률 p 이내만 보존
- **Temperature**: 로짓 스케일링

### Phase 1 추가 ✅

#### 최소 생성 길이 (min_new_tokens) — 2026-04-08 추가
**코드 위치**: `engine.py:_generate_with_harmony`

EOS 토큰 조기 종료를 방지하기 위해 도입. 과적합된 모델이 학습 시퀀스 끝의
EOS 패턴을 외워서 5~10 토큰 만에 종료하는 문제를 해결한다.

**동작 규칙**:
- `step < min_new_tokens` 동안 EOS 토큰의 logit을 `-inf`로 강제
- HuggingFace transformers의 동일 패턴 적용
- 지정된 step 이후부터는 정상적으로 EOS 샘플링 허용

| 파라미터 | 기본 | 권장 범위 |
|---------|------|---------|
| `min_new_tokens` | 256 | 128~512 |
| `max_tokens` | 1024 (기존 512) | 512~2048 |

**효과**: 생성 결과물이 최소 256 토큰 이상 보장. 1KB/5초 → 5~15KB/30초~1분으로 복구.

⚠️ `min_new_tokens=0`으로 설정하면 이전 동작과 동일 (EOS 즉시 종료).

#### 반복 패널티 (Repetition Penalty)
**코드 위치**: `engine.py:154-185`

CTRL (Keskar et al., 2019) 스타일:
```
seen_tokens에 대해:
  if logit > 0:  logit /= penalty
  else:          logit *= penalty
```

| 파라미터 | 기본 | 권장 범위 |
|---------|------|---------|
| `repetition_penalty` | 1.0 (off) | 1.05~1.2 |

⚠️ 1.5 초과 시 chorus/모티프 반복 깨짐.

#### N-gram 차단 (No-Repeat N-gram)
**코드 위치**: `engine.py:188-221`

생성 직전, n-1 prefix가 일치하는 모든 과거 n-gram의 마지막 토큰을 banned 처리.

| 파라미터 | 기본 | 권장 |
|---------|------|------|
| `no_repeat_ngram_size` | 0 (off) | 3~5 |

#### KV 캐시 (KV-Cache Decoding)
**코드 위치**: `engine.py:298-350` + `transformer.py:89-171, 335-427`

- 첫 step: prefill (전체 컨텍스트)
- 이후: T=1 (마지막 토큰만) + past_kv 재사용
- O(N²) → O(N) 추론 비용

| 파라미터 | 기본 |
|---------|------|
| `use_kv_cache` | True |

#### 다중 후보 (Multi-Sample)
**코드 위치**: `engine.py:439-480`

`num_return_sequences > 1`일 때 같은 입력으로 N개 독립 변주 생성. 반환 타입이 `list[list[dict]]`로 변경.

---

## 4. API

### `generate_variation()`
```python
result = inference.generate_variation(
    midi_path="input.mid",            # 또는 notes=[...]
    meta=SongMeta(key="C", style="jazz", section="chorus", tempo=120),
    chords=[ChordEvent("C", "maj7", ...), ...],
    max_tokens=1024,                    # 기본값 512→1024 (2026-04-08)
    min_new_tokens=256,                  # ✅ EOS 조기종료 방지 (2026-04-08)
    temperature=0.9,
    top_k=50,
    top_p=0.95,

    # ✅ Phase 1 추가
    repetition_penalty=1.1,
    no_repeat_ngram_size=4,
    num_return_sequences=3,         # 3개 변주 후보
    use_kv_cache=True,
)
# num_return_sequences == 1 → list[dict]
# num_return_sequences > 1  → list[list[dict]]
```

### `generate_to_midi()`
파일 직접 저장 버전. 동일한 Phase 1 옵션 지원.

### `load_lora(name, path)`
런타임 LoRA hot-swap. 이미 로드된 base 모델 위에 어댑터 적용.

---

## 5. 출력 형식

### `note_dict`
```python
{
    "pitch": int,           # MIDI 노트 번호 (21~108)
    "velocity": int,        # 0~127
    "start_tick": int,      # 시작 tick
    "duration_tick": int,   # 길이 tick
    "track_type": str,      # melody / accomp / bass / drums / ...
}
```

---

## 6. 의존성

### 필수
- PyTorch 2.0+ (`F.scaled_dot_product_attention` for FlashAttention)
- 학습된 base 체크포인트 (`midigpt_base.pt` 또는 `midigpt_ema.pt`)

### 선택
- LoRA 어댑터 파일 (스타일별)
- `pretty_midi`, `numpy` (encoder/decoder가 사용)

---

## 7. 검증 항목

### 단위
- [x] 모델 미로드 시 `RuntimeError("Model not loaded")`
- [x] `midi_path`/`notes` 둘 다 미제공 시 `ValueError`
- [x] EOS 자동 stop
- [x] min_new_tokens 미달 시 EOS logit 억제 (2026-04-08)
- [x] block_size 초과 시 cache 재초기화 (overflow 회복)

### 출력
- [x] 화성 마스킹 활성 시 모든 pitch가 active chord 스케일 내
- [x] `repetition_penalty=1.0`, `no_repeat_ngram_size=0`, `use_kv_cache=False` → 기존 동작과 동일
- [x] `num_return_sequences=N` → 정확히 N개 결과 반환

### 성능
- [x] KV cache 활성 시 max_tokens=512 생성 시간 30~50% 단축 (RTX 4090 기준)
- [x] FP16 vs FP32 출력 perceptual 차이 미미

---

## 8. 호환성

| 변경 | 등급 |
|------|------|
| 새 샘플러 옵션 추가 (Phase 1) | 🟢 안전 |
| min_new_tokens / max_tokens 기본값 변경 | 🟢 안전 (0 으로 복원 가능) |
| KV cache on/off | 🟢 안전 |
| 화성 마스킹 on/off | 🟢 안전 |
| Vocab 변경 | 🔴 모델 + 데이터 폐기 |
| Chord 매핑 추가 | 🟢 안전 (스케일 fallback) |

---

## 9. 향후 개선 후보

| 항목 | 등급 | 비고 |
|------|------|------|
| Beam Search / Diverse Beam | 🟢 | 후처리만, 안전 |
| Classifier-Free Guidance | 🟠 | 학습 시 cond drop 필요 |
| Constrained Decoding (FSM) | 🟡 | 너무 빡빡하면 창의성↓ |
| Speculative Decoding | 🟡 | draft 모델 필요 |
| Streaming Generation | 🟢 | 슬라이딩 윈도우 |
| Adapter Ensemble | 🟢 | LoRA 합치기 |
| Self-Consistency Scoring | 🟢 | 음악 이론 기반 후처리 |

상세 → [MidiGPT_개선로드맵_명세.md](MidiGPT_개선로드맵_명세.md)
