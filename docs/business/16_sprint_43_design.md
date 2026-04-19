# Sprint 43 설계 — 다중 LoRA 핫스왑 + Audio2MIDI Tier 2 진입

**작성**: 2026-04-19 (Sprint 42 종료 후)
**전제**: 동업자 SFT 재학습 결과 대기 중. 본 스프린트는 **재학습 결과 수령 전후 모두 진행 가능한 독립 작업**으로 한정.
**범위 분담 유지**: LLM 학습은 동업자. 우리는 inference 경로·audio2midi·DAW 기능 개선.

---

## Part A — 다중 LoRA 핫스왑 (Sprint 43 GGG1~GGG3)

### A.1 현재 상태 (repo 실사 2026-04-19)

| 요소 | 위치 | 한계 |
|---|---|---|
| `InferenceEngine.load_lora(name, path)` | engine.py:304 | **one-at-a-time** — 이미 LoRA 적용 시 weight 만 덮어씀 |
| `_active_lora: str \| None` | engine.py:255 | 단일 문자열. 블렌딩/다중 활성 표현 불가 |
| `/load_lora` HTTP | inference_server.py:145 | name + path 1개만 받음 |
| `config.lora_paths: dict[str, str]` | engine.py:231 | 이미 이름→경로 매핑 있음. 로드 시점은 여전히 단일 |
| `apply_lora()` 재호출 | lora.py:107 `isinstance(module, nn.Linear)` | 이미 LoRALinear 래핑된 경우 no-op (safe) |
| `save_lora / load_lora` (free function) | lora.py:129, 144 | 파일↔live weights 왕복 |

**현재 약점**: LoRA 전환 시 파일 I/O 매번 발생 (~50-200ms for ~5MB on NVMe). 이게 치명적이진 않으나, 데모에서 "잠시만요..." 체감.

### A.2 요구 사항

1. **즉시 전환** (< 5ms, 파일 I/O 없이)
2. **여러 LoRA 동시 등록** (메모리에 2~5개 preloaded)
3. **블렌딩** (stretch goal) — 예: jazz 0.7 + classical 0.3
4. **기존 `/load_lora` 호환** — 구 클라이언트 깨지지 않음
5. **MVP 범위** — jazz/pop/classical 3개로 데모

### A.3 API 설계

```python
# engine.py 신규 API (기존 load_lora 유지)
def register_lora(self, name: str, path: str) -> None:
    """Preload LoRA weights into memory. Does NOT mutate model."""
    # 파일 → registry[name] = {"lora.layer.X.A": tensor, "lora.layer.X.B": tensor, ...}
    # 처음 등록 시 apply_lora 를 한 번 호출해 모델에 LoRA 구조 주입
    # (구조는 모든 LoRA 가 공유 — r/alpha/target_modules 동일 가정)

def activate_lora(self, name: str | None) -> None:
    """Swap live LoRA weights to preloaded registry entry.

    name=None 이면 deactivate (lora_A/lora_B 을 zero → identity 동작).
    """

def blend_loras(self, weights: dict[str, float]) -> None:
    """Weighted average of registered LoRAs (stretch).

    weights 합이 1.0 이 아니어도 허용 (over/under-driven 실험).
    활성 LoRA 이름은 "blend:(jazz:0.6|classical:0.4)" 형식.
    """

# 기존 load_lora 는 내부적으로 register + activate 로 리팩토링
def load_lora(self, name: str, path: str | None = None) -> None:
    self.register_lora(name, path)
    self.activate_lora(name)
```

### A.4 HTTP 확장

```
기존 (유지):
  POST /load_lora       {"name": "jazz", "path": "..."}  → activate 포함

신규:
  POST /register_lora   {"name": "jazz", "path": "..."}
  POST /activate_lora   {"name": "jazz"}  or  {"name": null}
  POST /blend_loras     {"weights": {"jazz": 0.7, "classical": 0.3}}
  GET  /loras           → {"registered": ["jazz", "pop"], "active": "jazz"}
```

### A.5 구현 단계

| 단계 | 파일 | 위험도 | 시간 |
|---|---|---|---|
| GGG1 | lora.py — 레지스트리 helper (`load_lora_bytes`, `copy_into_model`) | 낮음 | 0.5일 |
| GGG2 | engine.py — register/activate/blend + `_loras: dict`, `_active` 변경 | 중간 (기존 API 보존) | 1일 |
| GGG3 | inference_server.py — 3 신규 엔드포인트 + pydantic 스키마 | 낮음 | 0.5일 |
| (테스트) | regress_lora_swap.py — register A/B → activate A → swap to B → 값 확인 | 낮음 | 0.5일 |

**총 ~2.5일**. 동업자 재학습 결과 수령 전에 모두 코드 진행 가능.

### A.6 회귀 방지 체크 (Rule 05 대조)

- 패턴 C: `load_lora` 가 내부적으로 register→activate 로 바뀜. **구 호출자에게 동일 결과** 유지 (회귀 없음).
- 패턴 D: 레지스트리 tensor 는 GPU 디바이스 일치해야 함 — `p.to(device, dtype)` 명시.
- 패턴 F: LoRA 구조 변경(r, alpha, target_modules) 없음 — 체크포인트 호환 유지.

---

## Part B — Audio2MIDI Tier 2 진입 (Sprint 43 GGG4~GGG5)

### B.1 Tier 2 후보 ranked by cost/impact

| Tier 2 항목 | 추가 의존 | 복잡도 | 예상 F1 효과 | MVP 기여 |
|---|---|---|---|---|
| 1. Mel-Roformer ensemble 분리 | pretrained ~500MB + librosa 호환 | 🔴 높음 | +3-5% SDR | 보컬/드럼 품질 |
| 2. MT3 병행 채보 | tensorflow (TF2) + large model | 🔴 높음 | +5-8% F1 (교차검증) | 폴리포닉 |
| 3. **Source-filter 반복 정제** | pretty_midi + librosa mel_spec (있음) + 간이 SF2 (~50MB) | 🟢 낮음 | +3-7% F1 | self-contained |
| 4. 톤 분류기 ("other" 세분화) | OpenL3 or PANNs ~200MB | 🟡 중간 | +2-4% F1 (strings 구분) | 악기 다양성 |

**선택**: **항목 3 (source-filter)** — 외부 weight 추가 없고 기존 pretty_midi/librosa 만으로 구현 가능. 실패해도 기존 파이프라인 손상 없음 (optional post-step).

항목 2 (MT3) 는 TF2 + madmom git-install 같은 번거로운 dep 이 이미 ADTOF 에서 경험한 바. **Sprint 44+** 로 이연.

### B.2 Source-filter 반복 정제 설계

```
입력: stem.wav + transcribed.mid (Tier 1 결과)
  │
  ▼
1) synth(mid) using fluidsynth + GeneralUser GS SF2  (기본 무료)
  │
  ▼
2) mel_spec(original_stem) vs mel_spec(synth) — L1 per frame
  │
  ▼
3) diff_hot_frames = top-5% diff frames
  │
  ▼
4) 각 hot frame 의 시간 구간에 해당하는 원본 노트 탐색
   - 노트 없음 → 미검출 영역 → basic_pitch threshold 0.3 재실행
   - 노트 있음 → threshold 0.7 재실행 (유령 노트 제거)
  │
  ▼
5) 수정된 노트로 pm 업데이트, 1 iteration. 최대 2회 반복 수렴
  │
  ▼
출력: refined.mid + diff_report.json
```

### B.3 구현 단계

| 단계 | 파일 | 의존 | 시간 |
|---|---|---|---|
| GGG4 | tools/audio_to_midi/refine.py (신규) — synth + diff + 재채보 | pyfluidsynth (옵션, 없으면 skip), 기존 basic_pitch | 1일 |
| GGG5 | convert.py — Stage E 로 refine 훅 삽입 (opt-in flag) | 없음 | 0.5일 |
| (테스트) | audio2midi_refine_tests.py — 합성 오디오 → 의도적 노이즈 추가 → refine 으로 복원 | 없음 | 0.5일 |

**총 ~2일**.

### B.4 제한 사항 + 대안

- fluidsynth 는 Windows binary 설치가 종종 꼬임. **대안**: pretty_midi.fluidsynth() 는 libfluidsynth 필요하지만 실패 시 silent skip. **더 안전한 대안**: `signal.chirp` 기반 사인파 합성기 자작 (피아노만, 저품질) — 정확한 mel diff 는 아니지만 tempo/onset 위치 검증용으로는 충분.
- SF2 다운로드: `GeneralUser GS.sf2` (무료, ~30MB) — download_checkpoints.py 에 추가 항목.

---

## Part C — Sprint 43 통합 계획

### C.1 작업 순서 제안

**Week 1 (~5일)**: Part A — 다중 LoRA 핫스왑
- GGG1 (lora.py helper) → GGG2 (engine API) → GGG3 (server) → 테스트

**Week 2 (~3일)**: Part B — Tier 2 진입
- GGG4 (refine.py) → GGG5 (convert.py Stage E) → 테스트

**여유**: 2-3일 버퍼 (동업자 재학습 결과 수령 후 통합 검증)

### C.2 결정 필요 항목

1. **Part A 블렌딩 stretch**: 구현할까? MVP 에는 단일 LoRA 활성만으로 충분. 블렌딩은 "자랑 거리" 이지만 테스트 부담 +0.5일.
2. **Part B Tier 2 항목 확장**: GGG4 성공 시 Sprint 43 안에 항목 4 (톤 분류기) 추가 가능. 약 +2일.
3. **MT3 (항목 2)**: **연기**. TF2 dep 부담 + MVP 6월 기한 대비 ROI 낮음.

### C.3 리스크

- **리스크 1**: 동업자 재학습 결과에서 새 문제 발견 → Sprint 43 우선순위 조정
- **리스크 2**: pyfluidsynth Windows 설치 실패 → Part B 가 silent-skip 만 제공. 실제 refine 효과 검증은 Linux GPU 서버에서.
- **리스크 3**: 다중 LoRA 메모리 — 5개 × 5MB = 25MB. GPU 여유 있음 (48M 기본 모델 + LoRA 적재).

### C.4 스프린트 종료 조건

- GGG1~3 + 회귀 테스트 그린
- GGG4 최소 1회 실제 오디오에서 diff 리포트 출력
- docs/business/16_sprint_43_design.md (본 문서) + 17_sprint_43_report.md 작성

---

## 참고

- Sprint 40~42 도구: `scripts/audit_*.py`, `scripts/clean_sft_pairs.py`, `scripts/regress_fsm_dedup.py`, `scripts/demo_preflight.py`
- Tier 2 원본 로드맵: `docs/business/10_audio2midi_roadmap.md` §60-88
- 현재 LoRA 코드: `midigpt/training/lora.py`, `midigpt/inference/engine.py:304-336`
- 서버 API: `midigpt/inference_server.py:145-152`
