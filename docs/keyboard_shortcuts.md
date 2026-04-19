# MidiGPT DAW 키보드 단축키 — 사용자 매뉴얼

**버전**: 0.9.1-beta (Sprint 46 JJJ3 기준)
**대상**: Standalone DAW + VST3 플러그인 에디터

---

## 전역 / 트랜스포트

| 단축키 | 동작 |
|---|---|
| Space | 재생 / 일시정지 |
| Ctrl+. | 정지 + 맨 앞으로 |
| Enter | 루프 설정 토글 |
| Home | 재생 헤드 맨 앞 |
| End | 재생 헤드 끝 |
| Ctrl+M | 메트로놈 on/off |
| Ctrl+Shift+M | Count-in 사이클 (0/1/2/4 bars) |
| R | 녹음 arm / start |

## 편집

| 단축키 | 동작 |
|---|---|
| Ctrl+Z | 실행 취소 (Undo) |
| Ctrl+Y / Ctrl+Shift+Z | 다시 실행 (Redo) |
| Ctrl+X | 잘라내기 |
| Ctrl+C | 복사 |
| Ctrl+V | 붙여넣기 |
| Ctrl+A | 모두 선택 |
| Delete / Backspace | 선택 삭제 |
| Q | 퀀타이즈 (현재 grid) |
| Shift+Q | 퀀타이즈 다이얼로그 |

## 프로젝트 I/O

| 단축키 | 동작 |
|---|---|
| Ctrl+N | 새 프로젝트 |
| Ctrl+O | 프로젝트 열기 |
| Ctrl+S | 저장 |
| Ctrl+Shift+S | 다른 이름으로 저장 |
| Ctrl+E | 내보내기 (MIDI + 오디오) |
| Ctrl+Shift+E | MIDI stems 내보내기 |

## 뷰

| 단축키 | 동작 |
|---|---|
| F1 | 퀀타이즈 그리드 토글 |
| F2 | Plugin Browser |
| F3 | FX Chain 에디터 |
| F5 | Audio clip import |
| F8 | CC Lane 에디터 |
| F9 | Step Sequencer |
| Ctrl++ / Ctrl+- | 줌 in/out |
| Ctrl+0 | 줌 리셋 (fit) |

---

## Piano Roll (클립 더블클릭으로 진입)

| 단축키 | 동작 |
|---|---|
| Ctrl+A | 모든 노트 선택 |
| 드래그 | 노트 이동 |
| Alt+드래그 | 복제 |
| Shift+드래그 | 배수 제약 이동 |
| 마우스 휠 | 세로 스크롤 |
| Ctrl+마우스 휠 | 줌 |
| V | 벨로시티 드래그 모드 |
| E | Erase 모드 (클릭 삭제) |

---

## Step Sequencer (F9)

| 단축키 | 동작 |
|---|---|
| 1~8 | 행 토글 |
| Shift+클릭 | 벨로시티 조정 |
| +/- | step 개수 증감 (계획, Sprint 47+) |

---

## VST3 플러그인 에디터 (MidiGPT Plugin)

| 단축키 | 동작 |
|---|---|
| Ctrl+R | Re-generate (마지막 파라미터로) |
| Ctrl+U | Undo — 이전 variation 으로 복원 (Sprint 34) |
| Ctrl+Shift+U | Redo |
| Ctrl+P | Preset 저장 (Sprint 34) |
| Ctrl+Shift+P | Preset 불러오기 |
| Ctrl+T | 튜토리얼 토글 (Sprint 36) |
| Ctrl+E | 현재 output MIDI export |
| Ctrl+L | 로그 패널 토글 |
| Ctrl+1 | Input/Output 싱글 패널 |
| Ctrl+2 | Dual 패널 |
| Esc | 에디터 뒤로 |

---

## MIDI 입력 녹음

| 단축키 | 동작 |
|---|---|
| R | 녹음 arm |
| Space | 녹음 start/stop |
| Ctrl+Shift+K | 녹음 중 오버레이 토글 |

---

## 서버 / 진단 (CLI)

DAW 내 단축키 아님. 별도 터미널:

```bash
# 환경 점검 (Sprint 40 DDD)
python scripts/doctor.py

# 데모 직전 단일 체크 (Sprint 42 FFF5)
python scripts/demo_preflight.py

# LoRA 핫스왑 클라이언트 예시 (Sprint 45 III2)
python examples/lora_hotswap_client.py --dry_run

# E2E 파이프라인 (Sprint 44 HHH5)
python scripts/e2e_pipeline.py --audio input.wav --out report.json
```

---

## 커스터마이즈

현재 버전은 키 매핑 변경 UI 없음 (Sprint 47+ 로드맵). 코드 위치:
`juce_daw_clean/src/KeyboardShortcuts.cpp` (참고).

---

## 버전 이력

- **0.9.1-beta** (2026-04-19): Sprint 42~45 단축키 정리 + VST3 plugin 에디터 항목 추가.
- **0.9.0-beta** (2026-04-17): 첫 공개 — Sprint 32~36 VST3 단축키 포함.
