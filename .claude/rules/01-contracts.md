# Rule 01 — 파일·데이터 계약

모든 컴포넌트 **경계**에서 지켜야 하는 스키마·포맷. 경계 = 한 파일이 쓰고 다른 파일이 읽는 지점.

## 1.1 SFT 페어 JSON

**위치:** `midigpt_pipeline/sft/` 또는 `--output_dir` 지정 경로
**파일명:** `sft_{4자리 인덱스}.json` (예: `sft_0000.json`)
**생산자:** `midigpt/build_sft_pairs.py`
**소비자:** `midigpt/data/dataset.py` (`MidiDataset(mode="sft")`)

### 스키마
```json
{
  "input":  [int, ...],
  "output": [int, ...],
  "metadata": {
    "strategy": "continuation|variation|track_completion",
    "source":   "<원본 MIDI 파일명>",
    "input_tokens":  int,
    "output_tokens": int,
    ...
  }
}
```

### 규약
- **필수 키:** `input`, `output` — 둘 중 하나라도 없으면 그 JSON은 페어가 아니다.
- **Loader 의무:** `sft_*.json` 패턴으로 glob (메타 파일을 배제). 동시에 스키마 검증: `"input" in pair and "output" in pair` 가 아니면 skip + warn.
- **메타 파일 (summary.json 등)은 별도 접미사/접두사로 분리**. 절대 페어 파일과 같은 glob 패턴에 걸리지 않도록 함.

### 과거 사고
- `summary.json` 이 `sft/` 에 함께 저장되고 `glob("*.json")` 로 로드되어 `pair["input"]` KeyError (5차 리포트 Bug 1). → loader 측 스키마 검증 + glob 패턴 둘 다 조여서 **이중 방어**.

---

## 1.2 DPO 트리플 JSON

**위치:** `midigpt_pipeline/dpo/` 또는 `--output_dir`
**파일명:** `dpo_{인덱스}.json`

### 스키마
```json
{
  "prompt":   [int, ...],
  "chosen":   [int, ...],
  "rejected": [int, ...],
  "metadata": {...}
}
```

필수 키: `prompt`, `chosen`, `rejected`. SFT와 동일한 이중 방어 규약 적용.

---

## 1.3 토큰 포맷 (계층적 REMI)

**단일 출처:** `midigpt/tokenizer/vocab.py`

### 특수 토큰 (고정 ID)
| 이름  | ID | 의미 |
|-------|----|------|
| `<PAD>` | 0 | padding / loss ignore |
| `<BOS>` | 1 | sequence begin |
| `<EOS>` | 2 | sequence end |
| `<SEP>` | 3 | SFT input/output 구분 |
| `<UNK>` | 4 | unknown |

**규약:** 특수 토큰 ID는 **하드코딩 금지**. 반드시 `vocab.pad_id / bos_id / eos_id / sep_id` 프로퍼티로 접근.
과거 위반: `dataset.py:178` 에서 SEP을 `3` 으로 하드코딩 — vocab 순서 바뀌면 silent corruption. 고쳐야 함.

### 범위 토큰
- `Bar_{0..63}` — 최대 64 마디
- `Pos_{0..31}` — 마디 내 32분음표 해상도
- `Pitch_{21..108}` — A0..C8
- `Vel_{0..15}` — 0~127을 16단계로 양자화
- `Dur_{1..64}` — 32분음표 단위, 최대 64
- `Tempo_{0..31}` — 40~240 BPM을 32단계로 양자화

### 트랙 카테고리 (14종 고정)
`vocab.TRACK_TYPES`:
```
melody, accomp, bass, drums, pad, lead, arp, other,
strings, brass, woodwind, vocal, guitar, fx
```
**규약:** 새 카테고리 추가 금지 (vocab 크기 변경 = 체크포인트 비호환). 확장이 필요하면 Design Composer 단계에서 마이그레이션 계획 명시.

---

## 1.4 체크포인트

**위치:** `checkpoints/` (예: `midigpt_best.pt`, `midigpt_latest.pt`)
**생산자:** `midigpt/training/train_pretrain.py`, `train_sft_lora.py`
**소비자:** `inference/engine.py`, `test_generate.py`, 후속 학습 스크립트

### 스키마 (pre-train)
```python
{
  "model_state_dict": dict,
  "config": dict,          # MidiGPTConfig 직렬화
  "step": int,
  "val_loss": float,
  ...
}
```

### 규약
- **토크나이저/분류기 변경 시 기존 체크포인트는 비호환**. 변경자의 의무:
  1. 커밋 메시지에 `BREAKING: retrain required` 명시
  2. `vocab.py` / `encoder._classify_track` 변경 이력을 encoder 파일 상단 docstring 의 "History" 섹션에 기재
- `torch.load` 는 `weights_only=True` 를 기본으로 사용 (supply chain).

---

## 1.5 파이프라인 산출물 레이아웃

`midigpt/pipeline.py` 가 가정하는 디렉토리 구조:

```
midigpt_pipeline/
  augmented/    ← 증강된 MIDI (.mid)
  tokenized/
    tokens/     ← 토큰화된 .npy
  sft/          ← SFT 페어 JSON (sft_*.json) + summary.json (별도 이름)
  dpo/          ← DPO 트리플 JSON (dpo_*.json) + summary.json
```

**규약:** 새 스크립트가 이 디렉토리에 파일을 쓸 때는 **기존 loader의 glob 패턴과 충돌하지 않는 이름**을 사용. 의심 시 loader 쪽 glob 패턴을 먼저 좁히고 나서 쓴다.
