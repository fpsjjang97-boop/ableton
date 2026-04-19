# Sprint 45~46 리포트 — preset 자동화 + DAW 주변 도구

**기간**: 2026-04-19 (Sprint 44 종료 당일 연속)
**전제**: 동업자 SFT 재학습 대기, DAW 빌드 머신 부재. Python/docs 위주.

---

## Sprint 45 (III1~III6) 요약

| # | 산출물 | 효과 |
|---|---|---|
| III1 | `inference_server --lora name=path,...` + `--lora_config <json>` | 서버 기동 시 여러 LoRA 자동 register, 첫 항목 auto-activate |
| III2 | `examples/lora_hotswap_client.py` + `lora_hotswap.sh` | 클라이언트가 register/activate/blend 사용법 즉시 확인 |
| III3 | `download_checkpoints.py --sf2` | MuseScore MS Basic SF2 51MB 자동 획득, pyfluidsynth upgrade path |
| III4 | CHANGELOG 0.9.1-beta + RELEASE_INFO 버전 필드 | 릴리스 문서 최신화, 변경 cross-ref |
| III5 | `measure_generation_quality --audio` | tone_classify 결과를 리포트에 덧붙임 |
| III6 | `docs/business/INDEX.md` | 01~17 전수 색인, 외부인 진입점 |

## Sprint 46 (JJJ1~JJJ6) 요약

| # | 산출물 | 효과 |
|---|---|---|
| JJJ1 | `scripts/make_test_midi.py` — 4 preset | 외부 .mid 없어도 회귀/데모 가능 (simple_chord/melody/arp/drum) |
| JJJ2 | `scripts/validate_mgp_project.py` | .mgp 프로젝트 파일 사전 검증, 크래시 방지 |
| JJJ3 | `docs/keyboard_shortcuts.md` | DAW + VST3 에디터 단축키 사용자 매뉴얼 |
| JJJ4 | `scripts/midi_stats.py` | 노트/BPM/key/duration 통계 (배치 CSV) |
| JJJ5 | `scripts/list_vst_presets.py` | OS 표준 preset 위치 스캔 |

테스트 상태: `scripts/smoke_all_scripts.py` **23/23 PASS**.

---

## 누적 테스트 결과 (2026-04-19)

| 테스트 | 결과 |
|---|---|
| FSM dedup 회귀 | 3/3 |
| LoRA swap + blend | 8/8 |
| Audio2MIDI refine smoke | 4/4 |
| Audio2MIDI edge case | 14/14 |
| scripts smoke | **23/23** |
| demo_preflight | 6 OK + 2 WARN + 0 FATAL |

---

## 잔여 블로커 (2026-04-19 Sprint 46 종료)

### 🔴 동업자 의존
- SFT LoRA 재학습 (`midigpt_pipeline/sft_clean/` 준비 완료)
- Vocab v1.x/v2.0 migration 결정

### 🟡 빌드 머신 필요
- VST3 GUI 재빌드 (CMake/VS2022)
- `make_release.bat 0.9.1-beta` 로 배포 패키지 생성

### ✅ 이제 준비된 것
- 서버 startup 시 여러 LoRA 자동 로드 (preset JSON 또는 CLI)
- LoRA 핫스왑/블렌딩 API + 클라이언트 예시
- SoundFont 자동 다운로드 (refine fluidsynth 경로 준비)
- 전체 도구 ToC + 단축키 매뉴얼
- MIDI fixture 라이브러리 (재현 가능한 회귀 테스트)

---

## 남은 Sprint 로드맵 (확정)

| Sprint | 예상 시기 | 전제 | 주요 내용 |
|---|---|---|---|
| **47** | 동업자 재학습 완료 후 | 외부 | 재학습 결과 검증, LoRA preset 등록, 생성 품질 측정 |
| **48** | Sprint 47 직후 | 없음 | 외부 작곡가 피드백 수집 인프라 (설문/리뷰) |
| **49** | GUI 빌드 머신 확보 후 | 외부 | VST3 재빌드, `make_release.bat` 실행, 0.9.1-beta 배포 |
| **50** | 6월 초 | 없음 | MVP 런칭 최종 점검 + 발견 버그 대응 |

우리가 대기 없이 진행할 수 있는 사이드 작업:
- **Audio2MIDI Tier 2 추가 항목** — MT3 또는 Mel-Roformer (Sprint 45 에서 이연)
- **DAW 미완성 항목** — Fade in/out, Step count 가변 (memory DAW inventory 섹션 B)
- **문서 보강** — 동영상 튜토리얼 스크립트, FAQ

---

## 파일 리스트 (Sprint 45~46 신규/수정)

**Sprint 45 신규 (4)**: `docs/business/INDEX.md`, `examples/lora_hotswap.sh`, `examples/lora_hotswap_client.py`, 그 외 수정 4건
**Sprint 46 신규 (5)**: `scripts/make_test_midi.py`, `scripts/validate_mgp_project.py`, `scripts/midi_stats.py`, `scripts/list_vst_presets.py`, `docs/keyboard_shortcuts.md`
