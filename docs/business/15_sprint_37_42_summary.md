# Sprint 37~42 통합 리포트 — 0.9.0-beta 준비 완료

**기간**: 2026-04-초 → 2026-04-19
**상태**: 6월 MVP 데모까지 **잔여 블로커 3건** (동업자 재학습 / vocab migration 결정 / GUI 재빌드)
**핵심 성과**: SFT 재학습 준비물(sft_clean 7,913 페어) + FSM 중복 노트 근본 차단 + preflight 자동화

---

## 스프린트별 요약 (1줄)

| Sprint | 코드 | 테마 | 핵심 산출 |
|---|---|---|---|
| 37 | - | ops 인프라 | doctor / setup / download 체크포인트 스크립트 |
| 37.1~37.4 | - | 실행 중 발견 버그 | PTI 통합, BPM=0 ZeroDiv, mkdir/tmp/6-stem |
| 38 | BBB | audio2midi + 배포 | pYIN 베이스, madmom 비트, QA 자동화, release bundle |
| 39 | CCC | 0.9.0-beta 출시 인프라 | make_release.bat, tag_release.bat, CHANGELOG |
| 40 | DDD | LLM 오류 진단 + 견고성 | **sft/lora audit, ADTOF 자동 설치, SHA256 manifest** |
| 41 | EEE | FSM 정책 단일화 + 재학습 준비 | **FSM 회귀 수정, sft_clean 7,913, vocab 호환성** |
| 42 | FFF | 서버 노출 + 통합 smoke | **use_grammar API, scripts smoke 15/15, demo_preflight** |

---

## 현재 가용한 도구 일람 (scripts/)

### 진단/감사 (Sprint 40~41)
| 스크립트 | 용도 |
|---|---|
| `audit_sft_tokens.py` | SFT 페어 토큰 범위·길이·중복·특수토큰 검사. `--ckpt_vocab_size` 로 체크포인트 기준 |
| `audit_lora_dtype.py` | base_model + LoRA 런타임 dtype/device, vocab_size, forward NaN 검사 |
| `verify_checkpoint_vocab.py` | config.vocab_size vs 현재 VOCAB.size. snapshot 생성/대조 |

### 정제/준비 (Sprint 41)
| 스크립트 | 용도 |
|---|---|
| `clean_sft_pairs.py` | block_size 정합 + dedup + 특수토큰 필터. **sft_clean/** 생성 |
| `download_checkpoints.py` | PTI (Zenodo 자동) + **ADTOF (git clone + TF2 weight 자동 복사)** |

### 테스트/회귀 (Sprint 40~42)
| 스크립트 | 용도 |
|---|---|
| `audio2midi_edge_cases.py` | detect_bpm, clean_notes, quantize_notes 유닛 + 엣지 (14/14) |
| `regress_fsm_dedup.py` | FSM 단위 + generate_to_midi 파라미터 존재 회귀 |
| `measure_generation_quality.py` | 노트 밀도 0.5~1.5x + FSM 위반 카운트 (오프라인) |
| `e2e_test.py` | 실행 중인 서버의 /health /preflight /generate_json /audio_to_midi |
| `smoke_all_scripts.py` | scripts/*.py 전체 `--help` 스모크 (15/15) |

### 배포/릴리스 (Sprint 38~40)
| 스크립트 | 용도 |
|---|---|
| `make_release.bat` | VST3 + exe + scripts + docs 번들 zip |
| `make_release_manifest.py` | MANIFEST.sha256 + RELEASE_INFO.txt + 필수 파일 sanity |
| `tag_release.bat` | 태그 + push |

### 최종 게이트 (Sprint 42)
| 스크립트 | 용도 |
|---|---|
| `demo_preflight.py` | **6월 MVP 데모 30분 전 단일 실행** → 6종 체크 그린 확인 |

---

## 잔여 블로커 (2026-04-19)

### 🔴 1. SFT LoRA 재학습 (동업자)
- 준비물 완료: `midigpt_pipeline/sft_clean/` 7,913 페어, 감사 0건
- 명령: `python -m midigpt.training.train_sft_lora --base_model checkpoints/midigpt_best.pt --data_dir midigpt_pipeline/sft_clean`
- 검증: Avg Loss != nan, valid_batches 증가, `lora_sft_best.bin` 저장

### 🟡 2. Vocab v1.x → v2.0 Migration 결정
- 현재 ckpt=420, VOCAB=527. 107 v2.0 토큰(Art_*/Dyn_*/Expr_*/Mod_*/Pedal_*/PB_*/InstFam_* + 확장 styles/tracks) 체크포인트 부재
- **권장**: 6월 MVP 는 v1.x 420 고정. Sprint 43+ 에서 pre-training 재수행

### 🟡 3. GUI 재빌드
- 현재 `C:\Program Files\Common Files\VST3\MidiGPT.vst3` 시스템 등록 확인 (doctor [4/7] OK)
- Sprint 32~36 변경 반영 실행파일 필요 — CMake/VS2022 있는 빌드 머신에서 `build.bat --install` 또는 `make_release.bat` 이후 아티팩트 재배포

---

## 남은 이연 항목 (Sprint 43+)

- Tier 2 Audio2MIDI: Mel-Roformer ensemble, MT3 cross-check (`docs/business/10_audio2midi_roadmap.md` Phase B)
- DPO training Phase 4 (13-rule DB)
- 다중 LoRA 스타일 (jazz/pop/classical) 동시 핫스왑
- 3~5 외부 작곡가 피드백 사이클 (SFT 재학습 후)
- v2.0 vocab 으로 pre-training 재학습 (Option B)

---

## 변경 로그 (Git)

| 커밋 | Sprint | 주요 내용 |
|---|---|---|
| `61366fc` | 40 | chore(ops) DDD1~6 — audit/ADTOF/edge-case/manifest |
| `55d0b21` | 41 | fix(inference) EEE1~6 — FSM 단일화 + sft_clean + vocab verify + doctor 확장 |
| (pending) | 42 | FFF1~6 — use_grammar API + sft_clean 재감사 + scripts smoke + demo_preflight + 본 리포트 |

---

## 파일 레퍼런스

- 상세 감사: `docs/business/14_sft_audit_report.md`
- 출시 체크리스트: `docs/business/12_release_checklist.md`
- 버그 히스토리: `.claude/rules/05-bug-history.md`
- Audio2MIDI 로드맵: `docs/business/10_audio2midi_roadmap.md`
