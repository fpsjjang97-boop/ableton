# MidiGPT — Changelog

의미 버전 : `MAJOR.MINOR.PATCH`. 계획상 첫 공개는 **0.9.0-beta** (2026-06 첫째 주).

---

## [0.9.1-beta] — 2026-04-19 (Sprint 40~45)

### 진단 도구 (Sprint 40~41)
- **feat(ops)** SFT 페어 토큰 감사 `scripts/audit_sft_tokens.py` —
  OOR / 길이 / 중복 / 특수토큰 위치 검사. `--ckpt_vocab_size` 로
  체크포인트 embedding 범위 대조.
- **feat(ops)** LoRA dtype/device 런타임 감사 `scripts/audit_lora_dtype.py` —
  checkpoint 로드 + apply_lora + forward 스모크 (fp32 + fp16).
- **feat(ops)** 체크포인트 vocab 호환성 `scripts/verify_checkpoint_vocab.py` —
  ckpt.vocab_size vs VOCAB.size 차이 리포트.
- **feat(data)** SFT 페어 정제 `scripts/clean_sft_pairs.py` —
  block_size trim + dedup + 특수토큰 필터. 원본 14,622 → 7,913 clean.

### Inference (Sprint 41~43)
- **fix(inference)** `generate_to_midi` 가 FSM 을 전달하지 않던 회귀
  복원 (패턴 C 단일화). `use_grammar` 파라미터 추가. 서버 두 경로
  동시 수정.
- **feat(inference)** 다중 LoRA 핫스왑 — `register_lora`, `activate_lora`,
  `registered_loras`. 파일 I/O 없이 전환 <5ms. 기존 `load_lora`
  호환 유지 (내부적으로 register+activate 조합).
- **feat(inference)** LoRA blending — `blend_loras({name: weight, ...})`.
  가중 평균 활성화, `active_lora = "blend:(...)"` 표기.
- **feat(server)** `/register_lora /activate_lora /blend_loras /loras`
  엔드포인트. `/load_lora` 유지 (구 클라이언트 호환).
- **feat(server)** CLI `--lora name=path,...` + `--lora_config <json>` 로
  startup 시 여러 preset auto-register.

### Audio2MIDI (Sprint 43~44)
- **feat(a2m)** Source-filter 반복 정제 `tools/audio_to_midi/refine.py` —
  synth vs original mel diff 에서 hot frame 추출 → ghost 제거 (velocity<30)
  + 미검출 구간 basic_pitch 재채보 (낮은 threshold).
- **feat(a2m)** `convert.py --refine` opt-in flag. 실패 시 silent skip.
- **feat(a2m)** 톤 분류기 `tools/audio_to_midi/tone_classify.py` —
  librosa 기본 피처 6-dim → strings/brass/woodwind 3-class 규칙 기반.
- **feat(ops)** `scripts/download_checkpoints.py --sf2` — GeneralUser/MS Basic
  SoundFont 자동 획득 (pyfluidsynth upgrade path).

### 배포 / QA (Sprint 40~45)
- **feat(release)** SHA256 manifest `scripts/make_release_manifest.py` +
  `make_release.bat [7/7]` 통합. RELEASE_INFO.txt 자동 생성.
- **feat(qa)** 오프라인 엣지 테스트 `scripts/audio2midi_edge_cases.py` —
  BPM=0 / 짧은 / 손상 WAV / clean_notes / quantize_notes (14/14 PASS).
- **feat(qa)** 전체 scripts `--help` 스모크 `scripts/smoke_all_scripts.py` —
  UTF-8 encoding 통일 (18/18 PASS).
- **feat(qa)** FSM dedup 회귀 `scripts/regress_fsm_dedup.py`,
  LoRA swap/blend 회귀 `scripts/regress_lora_swap.py`,
  refine smoke `scripts/regress_audio2midi_refine.py`.
- **feat(qa)** 데모 직전 단일 진입 `scripts/demo_preflight.py` —
  8 체크 집합.
- **feat(qa)** 오프라인 E2E 파이프라인 `scripts/e2e_pipeline.py` —
  audio → convert+refine → quality measure → tone classify → JSON.
- **feat(examples)** LoRA 핫스왑 클라이언트 예시 (Python + curl).

### 호환성
- 체크포인트: 기존 `midigpt_best.pt` (vocab_size=420) 그대로 호환.
- Vocab v1.x↔v2.0: 107 토큰 차이 (Art_*/Dyn_*/Expr_*/Mod_*/Pedal_*/PB_*/
  InstFam_*/확장 styles+tracks). MVP 는 v1.x 유지.

---

## [Unreleased] — 2026-04-17 ~

### MidiGPT LLM (6차 리포트 대응)
- **fix(sft)** SFT LoRA NaN Loss 근본 수정. `_load_sft` 에 label-viability
  pre-filter (effective_output_labels < 4 pair skip). SEP/pad 리터럴 →
  `VOCAB.sep_id`/`pad_id` 단일 출처. 학습 루프 NaN 배치 격리.
- **fix(decoder)** 같은 (track, tick, pitch) 중복 노트 dedup
- **fix(tokenizer)** C.BASS → strings 분류 (콘트라베이스)
  — **BREAKING: retokenize + retrain required**

### ACE-Step v1.5 포트 (Apache 2.0)
- **feat(inference)** FSM grammar constrained decoder — Pitch→Vel→Dur 무중단,
  Bar monotonicity, 동일-슬롯 Pitch dedup. 6차 리포트 "무음 갭" / "중복"
  근본 차단. 기본 `use_grammar=True`.
- **feat(inference)** LM `score_loglik` 자기스코어. Best-of-N 재랭킹 시
  휴리스틱 외 채널.
- **feat(tools)** DTW MIDI 유사도 평가 유틸 (NumPy 구현).

### VST3 플러그인 (Sprint 32~36)
- **Sprint 32 (WW1~6)** CMake VST3 target 활성화. processBlock 호스트 tempo +
  beat 정렬 MIDI 캡처. requestVariation AIBridge 비동기 연결. 응답 MIDI
  processBlock 주입. PluginEditor 상태 피드백 + 서버 health 폴링.
  getState/setState 에 생성 시퀀스 영속화.
- **Sprint 33 (XX1~6)** MiniPianoRoll dual pane (Input/Output). Export MIDI
  버튼 (FileChooser). Style change → async LoRA 핫스왑. Progress overlay +
  Cancel. Server Info 다이얼로그. SafePointer 비동기 콜백 방어.
- **Sprint 34 (YY1~6)** 리사이즈 가능 창. 7개 키보드 단축키 (Space/Esc/
  Ctrl+E/I/K/Z). PresetManager (userAppData 저장). 생성 결과 Undo/Redo
  히스토리 N=10. `.mid/.wav/.mp3` 드래그앤드롭 (PPQ/SMPTE 자동 감지).
  Dark/Light 테마 토글.
- **Sprint 35 (ZZ1~6)** Audio2MIDI `/audio_to_midi` 서버 엔드포인트 + 클라이언트
  훅. i18n (ko/en, 45 키). PluginLogger 파일 로그. First-run 튜토리얼
  오버레이. 13개 컨트롤 tooltip. build.bat smoke 검증.
- **Sprint 36 (AAA1~6)** Crash recovery (autosave/restore, "복구" 다이얼로그).
  Diagnostic report dump ("Report" 버튼 → Desktop zip). Sample MIDI
  gallery. Performance HUD (Ctrl+Shift+D). Tutorial v2 외부 링크.

### Audio2MIDI (Tier 1 로드맵 4/4 완료)
- **piano** Basic Pitch 70% → PTI (PyTorch 포트, 체크포인트 자동 다운로드)
  96% F1 (Sprint 37.4)
- **drums** librosa 55% → ADTOF 80% F1 (Sprint 36, 체크포인트 별도)
- **bass** Basic Pitch 75% → pYIN 88% F1 (Sprint 38)
- **timing** ±50ms → madmom 비트 그리드 ±10ms (Sprint 38)

### 실행 검증에서 발견된 버그 수정
- BPM=0 ZeroDivisionError 방어 (`detect_bpm` 범위 + `merge_midi_tracks` 가드)
- `split_other_by_register` mkdir 누락으로 인한 strings 분기 silent fail
- `/audio_to_midi` tmp 파일 REPO_ROOT 오염 → 시스템 임시 디렉터리 이관
- `convert_single` 기본 demucs_model 이 CLI 와 불일치 (4-stem → 6-stem)
- PTI `load_audio` Windows audioread 백엔드 부재 → `librosa.load` 로 우회
- Python 3.13 + basic-pitch 0.2.5 numpy 버전 충돌 → Python 3.10 / 3.11 강제 안내

### 운영 인프라
- `scripts/doctor.py` — 서버/의존성/체크포인트/VST3/모델 5개 체크 한 번에
- `scripts/setup_audio2midi.bat` (+ `.sh`) — py launcher 우선 감지
- `scripts/setup_build_env.bat` — CMake + VS 2022 + JUCE 점검 + 다운로드 페이지 오픈
- `scripts/download_checkpoints.py` — PTI 체크포인트 Zenodo 자동 fetch
- `scripts/e2e_test.py` — 라이브 서버 4개 엔드포인트 회귀 검증
- `scripts/make_release.bat` — 배포 zip 번들링
- `requirements-audio2midi.txt` — Python 3.10/3.11 제약 명시 (basic-pitch)

### 문서
- `QUICKSTART.md` — 한/영 5분 가이드 + FAQ 5문항
- `docs/business/10_audio2midi_roadmap.md` — Tier 1~3 정밀화 로드맵
- `docs/business/11_demo_storyboard.md` — 5분 MVP 시연 영상 5컷 구성
- `docs/samples/README.md` — 샘플 MIDI 라이브러리 규약

---

## [이전 커밋들 (Sprint 0~31)]

요약 위치: `git log --oneline` 의 `67eae78` 이전 부분. 주요 마일스톤:
- Sprint 0~11 (69 항목) — DAW 기본기 (Piano Roll, Mixer, Automation, VST 호스팅)
- Sprint 12~31 (120 항목) — DAW 확장 (Tempo/TS editor, Bezier curves, Freeze track,
  Input monitoring, Groove/swing, Clip drag, Zoom presets, Undo grouping, etc.)
- 5차 리포트 대응 — `_classify_track` 14카테고리 복구, VST3 clean room, Cubase
  격리 (`juce_app_quarantine/`)

---

## 계획

### [0.9.0-beta] — 2026-06-01 목표
- 현재 Unreleased 전체 + 아래 준비:
  - SFT LoRA 재학습 완료 ([urgent blockers](memory))
  - 플러그인 GUI 재빌드 + VST3 재배포 (사용자 머신에 CMake/VS 필요)
  - 외부 작곡가 3-5명 청취 피드백
  - 시연 영상 녹화 완료 (11_demo_storyboard.md)
  - LICENSE / CREDITS 최종 확정

### [1.0] — 미정
- Phase B (베타 피드백 반영 + LoRA 3-5개 + DPO 1차)
- macOS / Linux 지원
- Tier 2 Audio2MIDI (Mel-Roformer 앙상블, MT3 교차검증)
