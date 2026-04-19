# Sprint 47 리포트 — DAW GUI 퀄리티 증진 (Pre-build)

**기간**: 2026-04-19 (Sprint 46 종료 당일 연속)
**범위**: DAW C++ UI 개선. **빌드 머신 부재로 로컬 검증 불가** — 변경은 additive-only, 빌드 검증은 외부.

---

## 성과

| # | 산출 | 영향 범위 |
|---|---|---|
| KKK1 | `LookAndFeel.h` 색상 토큰 5 + 여백 5 + 폰트 5 + 라디우스 3 constexpr | 헤더만, ABI 변경 없음 |
| KKK2 | `TransportBar.cpp` 13 위젯 툴팁 | 생성자 내 setTooltip 추가만 |
| KKK3 | `MixerPanel.cpp` bus/track 스트립 5 위젯 × 2 × setTooltip | 기존 로직 불변 |
| KKK4 | `LookAndFeel.h/.cpp` drawPanelBackground / drawSectionHeader / drawDivider (static) | 신규 메서드, 현재 호출부 없음 (후속 리팩터링용) |
| KKK5 | `docs/ui_style_guide.md` — 색상/여백/폰트/툴팁 작성 규칙 | 문서 |
| KKK6 | 본 리포트 | 문서 |

---

## 설계 원칙 (Sprint 47 기조)

1. **Additive only** — 기존 코드 이동/삭제 금지. 빌드 검증 없이 회귀 리스크 최소화.
2. **Paint helper 는 unused 상태로 도입** — 기존 컴포넌트 리팩터링 강제하지 않음, 추후 점진 마이그레이션.
3. **Tooltip 은 런타임 TooltipWindow 의존** — MainWindow 레벨에서 이미 active, 신규 위젯 자동 감지.
4. **토큰 기반 스타일** — 매직 넘버 리터럴 금지 규칙을 문서화. 기존 코드의 리터럴은 향후 리팩터링에서 정리.

---

## 빌드 머신에서 검증 필요 (체크리스트)

### 컴파일
- [ ] `juce_daw_clean/build.bat --install` 성공
- [ ] 경고 없음 (특히 unused warning 은 `drawPanel/drawSectionHeader/drawDivider` 에 발생 가능 — 무시 가능)

### 런타임 (Standalone)
- [ ] TransportBar 의 play/stop/rec/loop/metro 버튼 위에 마우스 0.5초 고정 시 툴팁 노출
- [ ] BPM Slider, key/scale/snap/countIn ComboBox 에도 툴팁 노출
- [ ] MixerPanel 의 M/S/Pan/Fader/FX 위젯 모두 툴팁 노출
- [ ] TooltipWindow 가 LookAndFeel 의 색상 규칙(`bgMid` 배경, `textPrimary` 텍스트, `border` 외곽선) 을 반영

### 런타임 (VST3)
- [ ] VST3 플러그인 호스팅 시 DAW 툴팁은 보임 — 호스트 DAW 의 툴팁 처리에 따라 다름
- [ ] LookAndFeel 변경이 플러그인 에디터에도 전파 (공유 인스턴스)

### ABI
- [ ] LookAndFeel.h 에 constexpr 추가만 있었으므로 기존 .cpp 와 호환
- [ ] `.mgp` 저장 포맷 변경 없음 — 프로젝트 파일 하위 호환 유지

---

## 변경 파일

| 파일 | 변경 라인 | 성격 |
|---|---|---|
| `juce_daw_clean/Source/UI/LookAndFeel.h` | +27 | constexpr + 메서드 선언 3 |
| `juce_daw_clean/Source/UI/LookAndFeel.cpp` | +58 | static 메서드 정의 3 |
| `juce_daw_clean/Source/UI/TransportBar.cpp` | +17 | setTooltip 13 |
| `juce_daw_clean/Source/UI/MixerPanel.cpp` | +6 | setTooltip 6 (bus 3 + track 5 를 2 스트립 타입) |
| `docs/ui_style_guide.md` | +신규 | 문서 |
| `docs/business/19_sprint_47_report.md` | +신규 | 문서 |

---

## Sprint 48~50 제안

### Sprint 48 (LLL) — 외부 작곡가 피드백 수집 인프라
- LLL1: 피드백 수집 JSON 스키마 + 입력 유틸 (`scripts/feedback_collect.py`)
- LLL2: 테스터용 사전 설정 프로필 (`daw preset.mgp`, 한글 UI)
- LLL3: 피드백 집계 + 우선순위 산출 (`scripts/feedback_aggregate.py`)
- LLL4: 설치 가이드 최종화 (screenshots 포함)
- LLL5: VST3 플러그인 오류 리포트 자동 전송 옵션 (opt-in)
- LLL6: Sprint 48 리포트

### Sprint 49 — VST3 재빌드 + 0.9.1-beta 배포 (빌드 머신 확보 시)
- `make_release.bat 0.9.1-beta` + `make_release_manifest.py` 실행
- GitHub release 업로드 + SHA256 공지
- 동업자 재학습 결과물 LoRA 번들링

### Sprint 50 — MVP 최종 점검 (6월 초)
- `demo_preflight.py` 모든 체크 그린
- 외부 피드백 반영한 최종 버그픽스
- 런칭 공지문 최종

---

## 누적 통계 (Sprint 37~47, 11 스프린트)

| 항목 | 값 |
|---|---|
| 커밋 | 8 (37~42 이전 + 43~47 이번 세션 5) |
| 신규 scripts/ | 15 (audit/clean/refine/smoke/regress/demo/e2e 등) |
| 신규 tools/audio_to_midi/ | 2 (refine, tone_classify) |
| 신규 docs/business/ | 5 (14~18) + INDEX + style_guide + keyboard_shortcuts |
| 신규 examples/ | 2 (lora_hotswap Python + bash) |
| DAW C++ 수정 | 4 파일 (UI 한정, additive) |
| 테스트 | 23 scripts smoke PASS, FSM 3/3, LoRA 8/8, refine 4/4, edge 14/14 |
