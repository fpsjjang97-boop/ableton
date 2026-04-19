# Sprint 43~44 리포트 — inference 품질 + audio2midi Tier 2 진입

**기간**: 2026-04-19 (Sprint 42 종료) → 2026-04-19 (Sprint 44 종료, 동일 세션)
**전제**: 동업자 SFT 재학습 대기 중. LLM 학습 무관 항목만 진행.
**커밋**: Sprint 43 `2dfe310`, Sprint 44 (pending)

---

## 성과 한눈에

| 항목 | 이전 | 이후 |
|---|---|---|
| LoRA 전환 비용 | ~50-200ms 파일 I/O 매 회 | <5ms (registry 재사용) |
| LoRA 블렌딩 | 불가 | `blend_loras({"jazz":0.7,"classical":0.3})` |
| 서버 LoRA API | `/load_lora` 1개 | `/load_lora /register_lora /activate_lora /blend_loras /loras` 5개 |
| Audio2MIDI post-step | 없음 | source-filter refine (ghost 제거 + 미검출 재채보) |
| "other" 스템 분류 | 없음 | strings / brass / woodwind 간이 분류 |
| 통합 E2E 스크립트 | 없음 | `e2e_pipeline.py` (오디오→MIDI→refine→리포트) |
| demo preflight | 6 체크 | 8 체크 (LoRA swap + refine smoke 추가) |

---

## Sprint 43 (GGG1~GGG6) — 다중 LoRA 핫스왑 + Audio2MIDI Tier 2

### GGG1 — `midigpt/training/lora.py` 레지스트리 helper
- `load_lora_weights_only(path)`: 파일 → dict (모델 unchanged)
- `copy_weights_into_model(model, weights)`: dict → LoRALinear, device/dtype 변환 + shape 검증
- `zero_lora_weights(model)`: identity deactivate

### GGG2 — `engine.py` multi-LoRA API
- `_lora_registry: dict[name, state_dict]`, `_lora_structure_applied: bool`
- `register_lora(name, path)` / `activate_lora(name|None)` / `registered_loras()`
- `load_lora(기존)` 은 register+activate 조합으로 호환 유지

### GGG3 — `inference_server.py` 4 신규 엔드포인트
- `POST /register_lora`, `POST /activate_lora`, `GET /loras`, (+ `/blend_loras` HHH2)

### GGG4 — `tools/audio_to_midi/refine.py` source-filter
- pyfluidsynth OR 사인파 fallback → mel diff → hot frame → ghost 제거
- 검증: sine 440Hz + ghost MIDI → diff 10.58→9.38, ghost 1건 제거

### GGG5 — `convert.py --refine` 옵션 (opt-in Stage E)
- 실패 시 silent skip — 원본 merged MIDI 유지 (회귀 없음)

### GGG6 — 회귀 테스트 2종
- `regress_lora_swap.py`: 5 체크 → 8 체크 (blend 포함) → ALL PASS
- `regress_audio2midi_refine.py`: 4 체크 ALL PASS

---

## Sprint 44 (HHH1~HHH6) — refine 확장 + 블렌딩 + 분류기 + E2E

### HHH1 — `refine.py` 재채보 경로
- 기존 ghost 제거에 **미검출 영역 재채보** 추가
- hot frame 내 노트 0건 + 지속 ≥0.2s → basic_pitch 낮은 threshold 재실행
- basic_pitch 없으면 silent skip
- 회계 불변량: before − removed + added = after

### HHH2 — LoRA blending 활성화
- `blend_loras({name: weight, ...})` — registered LoRA 가중합
- `active_lora = "blend:(A:0.7|B:0.3)"` 형식 표기
- 미등록 이름 → KeyError (verify 반영)
- `/blend_loras` HTTP 엔드포인트 추가
- 회귀: A(0.5)+B(0.5) 결과가 개별 가중합 일치 확인 (fp16 atol 1e-3)

### HHH3 — 톤 분류기 간이 (`tools/audio_to_midi/tone_classify.py`)
- librosa 기본 피처만 (OpenL3/PANNs 무거운 dep 없이)
- strings / brass / woodwind 3-class, 규칙 기반
- 1000Hz 사인 → strings (conf 0.30)
- API: `classify_other(audio_path)` → (family, conf, info)

### HHH4 — `demo_preflight.py` 확장 (6 → 8 체크)
- LoRA swap 회귀 (warn, base_model 필요)
- Audio2MIDI refine 스모크 (fatal)
- 새 체크 모두 통과, fatal fail 0

### HHH5 — 통합 E2E 파이프라인 (`scripts/e2e_pipeline.py`)
- 오디오 → convert(refine) → quality measure → tone classify (옵션)
- JSON 리포트 단일 파일 출력
- 서버 불필요 (완전 오프라인)

### HHH6 — 본 리포트 + memory 갱신

---

## 테스트 결과 (2026-04-19)

| 테스트 | 결과 |
|---|---|
| `regress_fsm_dedup.py` | ALL PASS (3/3) |
| `regress_lora_swap.py` (blend 포함) | ALL PASS (8/8) |
| `regress_audio2midi_refine.py` | ALL PASS (4/4) |
| `audio2midi_edge_cases.py` | ALL PASS (14/14) |
| `smoke_all_scripts.py` | ALL PASS (18/18) |
| `demo_preflight.py` | 6 OK + 2 WARN + 0 FATAL |

---

## 남은 블로커 (2026-04-19 Sprint 44 종료)

### 🔴 1. SFT LoRA 재학습 (동업자 대기)
- 준비물: `midigpt_pipeline/sft_clean/` 7,913 페어 (그린)
- 재학습 후 `lora_sft_best.bin` 를 `register_lora("base", "<path>")` 로 등록
- 이제는 여러 스타일 LoRA 가 생성되면 `/activate_lora` 또는 `/blend_loras` 로 즉시 전환

### 🟡 2. Vocab v1.x → v2.0 Migration
- 상태 동일. MVP 는 420 유지 권장.

### 🟡 3. GUI 재빌드
- 상태 동일. `make_release.bat` + `make_release_manifest.py` 로 빌드 머신에서 실행.

---

## 파일 리스트 (Sprint 43~44 신규/수정)

**신규 (8)**:
- `docs/business/16_sprint_43_design.md`
- `docs/business/17_sprint_43_44_report.md` (본 문서)
- `scripts/regress_lora_swap.py`
- `scripts/regress_audio2midi_refine.py`
- `scripts/e2e_pipeline.py`
- `tools/audio_to_midi/refine.py`
- `tools/audio_to_midi/tone_classify.py`

**수정 (5)**:
- `midigpt/training/lora.py` (+3 helper 함수)
- `midigpt/inference/engine.py` (register/activate/blend API)
- `midigpt/inference_server.py` (/register /activate /loras /blend_loras)
- `tools/audio_to_midi/convert.py` (--refine opt-in)
- `scripts/demo_preflight.py` (2 체크 추가)
