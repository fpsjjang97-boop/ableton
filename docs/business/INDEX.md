# docs/business ToC — 외부인 진입 가이드

**작성**: 2026-04-19 (Sprint 45 III6)
**용도**: 새로 합류하는 엔지니어/작곡가가 어느 문서부터 봐야 하는지 한눈에.

---

## 읽는 순서 (추천)

1. **[01_사업기획서.md](01_사업기획서.md)** — 제품 비전, 타겟, 경쟁 구도
2. **[07_상품_설명서.md](07_상품_설명서.md)** — MidiGPT 가 무엇을 하는가 (사용자용)
3. **[06_출시_로드맵.md](06_출시_로드맵.md)** — 전체 8주 일정 (6월 MVP)
4. **[12_release_checklist.md](12_release_checklist.md)** — 출시 전 확인 항목
5. **[11_demo_storyboard.md](11_demo_storyboard.md)** — 데모 시연 스크립트

---

## 카테고리별

### 제품 기획 (1~7)
| # | 문서 | 요약 |
|---|---|---|
| 01 | 사업기획서 | 제품 포지셔닝, 수익 모델 |
| 02 | PDR | 제품 요구사항 정의 (Product Definition Report) |
| 03 | 3페르소나 라운드테이블 | 작곡가/프로듀서/학생 관점 검증 |
| 04 | 5대 평가 | 음악성/UX/가격/경쟁/신뢰 5축 |
| 05 | 데이터 오염 회수 | 학습 데이터 리스크 + 대응 |
| 06 | 출시 로드맵 | 8주 Sprint 캘린더 |
| 07 | 상품 설명서 | 기능 카탈로그 (사용자 언어) |

### 기술 기획 (8~10)
| # | 문서 | 요약 |
|---|---|---|
| 08 | DAW 벤치마크 프레임워크 | Live/FL/Cubase/Pro Tools 비교 |
| 09 | 8주 Sprint 6월 데드라인 | Sprint 일정 상세 |
| 10 | Audio2MIDI 로드맵 | Tier 1/2/3 정밀화 계획 |

### 운영 / 출시 (11~13)
| # | 문서 | 요약 |
|---|---|---|
| 11 | 데모 스토리보드 | 시연 순서/스크립트 |
| 12 | 릴리스 체크리스트 | 출시 직전 자동/수동 확인 |
| 13 | 포스트 릴리스 운영 | 버그 대응, 패치 주기 |

### Sprint 리포트 (14~17)
| # | 문서 | 요약 |
|---|---|---|
| 14 | SFT audit report | Sprint 40 DDD1 + 41 EEE2 + 42 FFF2. 14,622→7,913 정제 |
| 15 | Sprint 37~42 요약 | ops 인프라 → audio2midi → release → 진단 → 정책 |
| 16 | Sprint 43 설계 | 다중 LoRA 핫스왑 + audio2midi Tier 2 진입 |
| 17 | Sprint 43~44 리포트 | 구현 결과 + 테스트 + 남은 블로커 |

---

## 관련 코드/도구 빠른 참조

### 진단 / 감사
- `scripts/audit_sft_tokens.py` — SFT 데이터 품질 (→ 14_sft_audit_report)
- `scripts/audit_lora_dtype.py` — LoRA runtime dtype/device + forward NaN
- `scripts/verify_checkpoint_vocab.py` — vocab 불일치 탐지

### 데이터 준비
- `scripts/clean_sft_pairs.py` — block_size trim + dedup
- `scripts/download_checkpoints.py` — PTI/ADTOF/SF2 자동
- `scripts/download_datasets.py` — Lakh/GiantMIDI 외부 데이터

### Audio2MIDI
- `tools/audio_to_midi/convert.py` — 메인 파이프라인 (`--refine` 옵션)
- `tools/audio_to_midi/refine.py` — Tier 2 source-filter (→ 16_design §B)
- `tools/audio_to_midi/tone_classify.py` — strings/brass/woodwind

### Inference / 서버
- `midigpt/inference/engine.py` — register/activate/blend LoRA API
- `midigpt/inference_server.py` — HTTP `/register_lora`, `/activate_lora`,
  `/blend_loras`, `/loras`
- `examples/lora_hotswap_client.py` + `examples/lora_hotswap.sh` — 클라이언트 예시

### 테스트 / 게이트
- `scripts/demo_preflight.py` — 8 체크 집합 (데모 직전 단일 진입)
- `scripts/smoke_all_scripts.py` — 전체 scripts --help 스모크
- `scripts/regress_fsm_dedup.py` — FSM 단위 + engine wiring
- `scripts/regress_lora_swap.py` — LoRA swap/blend 8 체크
- `scripts/regress_audio2midi_refine.py` — refine smoke
- `scripts/e2e_pipeline.py` — audio → MIDI → report 단일 호출

### 릴리스
- `scripts/make_release.bat` — VST3 + exe + scripts + docs zip
- `scripts/make_release_manifest.py` — SHA256 + RELEASE_INFO

---

## Sprint 코드 ↔ 커밋 매핑

| Sprint | 코드 | 커밋 |
|---|---|---|
| 37 | 37.1~37.4 | `e14a079 fix(audio2midi)` 외 |
| 38 | BBB | `76b487a`, `9b100aa` |
| 39 | CCC | `1946daf chore(release)` |
| 40 | DDD | `61366fc chore(ops)` |
| 41 | EEE | `55d0b21 fix(inference)` |
| 42 | FFF | `82a54f0 feat(ops)` |
| 43 | GGG | `2dfe310 feat(inference)` |
| 44 | HHH | `024283a feat(inference)` |
| 45 | III | (pending) |

---

## 규약 문서 (`.claude/rules/`)

- `01-contracts.md` — 파일·데이터 계약 (SFT JSON, vocab, checkpoint)
- `02-fallback-policy.md` — unknown vs error 구분
- `03-windows-compat.md` — UTF-8 / pathlib / subprocess
- `04-commit-discipline.md` — 커밋 메시지, BREAKING 표기
- `05-bug-history.md` — 회귀 금지 8 패턴 (A~H)
