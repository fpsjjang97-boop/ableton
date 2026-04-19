# MidiGPT DAW — UI 스타일 가이드

**Sprint 47 KKK5 (2026-04-19)** — 신규 / 리팩터링 컴포넌트는 이 규약을 따른다.
단일 출처: `juce_daw_clean/Source/UI/LookAndFeel.h` (const + helper 메서드).

---

## 1. 색상 (MetallicLookAndFeel::*)

### 배경 / 표면 (어두운 순)
| 토큰 | 사용처 |
|---|---|
| `bgDarkest` (0xFF0E0E0E) | Window 루트 |
| `bgDark` (0xFF161616) | 비활성 패널, 슬라이더 트랙 바닥 |
| `bgMid` (0xFF1E1E1E) | 버튼/콤보 기본 |
| `bgPanel` (0xFF1A1A1A) | 섹션 컨테이너 (drawPanelBackground 로) |
| `bgHeader` (0xFF1C1C1C) | 섹션 헤더 바 (drawSectionHeader 로) |
| `bgSelected` (0xFF3A3A3A) | 선택/활성 상태 |
| `bgHover` (0xFF2A2A2A) | 마우스 오버 |

### 텍스트
| 토큰 | 사용처 |
|---|---|
| `textPrimary` | 레이블, 버튼 텍스트 |
| `textSecondary` | 부가 정보 (BPM 단위, 탭 비활성) |
| `textDim` | placeholder, disabled |

### Accent (메탈 중성)
| 토큰 | 사용처 |
|---|---|
| `accent` (0xFFC0C0C0) | 슬라이더 트랙 filled, knob pointer |
| `accentLight` (0xFFE0E0E0) | 강조 텍스트, 버튼 on |
| `border` (0xFF2A2A2A) | 외곽선 — 항상 `0.5f` 두께 권장 |

### 의미 색상 (Sprint 47 KKK1 추가)
**용도 엄격 — 아무 버튼에나 색 입히는 용도 아님**.

| 토큰 | 권장 사용처 | 금지 |
|---|---|---|
| `warning` (주황) | 되돌릴 수 있는 주의 (unsaved 표시, beta 라벨) | 일반 안내 버튼 |
| `danger` (빨강) | 파괴적 확정 (Delete, 포맷, 종료 dialog) | record 버튼 (이미 진한 빨강 별도) |
| `success` (초록) | 완료 확인 (Save OK toast, checkmark) | play 버튼 |
| `infoBlue` (clipColour) | 선택/강조, MIDI clip, 정보 hint | 기본 배경 |
| `infoLight` | hover/active blue | 배경 전체 |

### 미터 / velocity (기존)
`meterGreen/Yellow/Red`, `velocityHigh/Low` — 기능별 색 고정, 변경 금지.

---

## 2. 여백 스케일 (정수 상수)

모든 내부 여백/gap 은 이 5 단계만 사용:

| 토큰 | px | 용도 |
|---|---:|---|
| `spacingXS` | 2 | 아이콘 내부, 인라인 구분 |
| `spacingS` | 4 | 아이콘 ↔ 텍스트 |
| `spacingM` | 8 | 섹션 내 위젯간 |
| `spacingL` | 16 | 섹션간 (예: TransportBar ↔ ArrangementView) |
| `spacingXL` | 24 | 주요 블록 외곽 (MainWindow 외곽) |

**금지**: 리터럴 `3`, `6`, `10`, `12` 등. `spacingS` 또는 `spacingM` 으로 맞춤.

---

## 3. 폰트 스케일

| 토큰 | pt | 용도 |
|---|---:|---|
| `fontXS` | 9 | 캡션, dB 레이블, 미세 표시 |
| `fontS` | 11 | 일반 레이블 |
| `fontM` | 13 | 본문 텍스트 (버튼 기본) |
| `fontL` | 16 | 섹션 헤더 (drawSectionHeader 기본) |
| `fontXL` | 20 | 앱 타이틀 |

`juce::Font::getDefaultMonospacedFontName()` 은 **숫자 표시** (position/time/BPM)
에 한함. 일반 레이블은 기본 폰트.

---

## 4. 코너 라디우스

| 토큰 | px | 용도 |
|---|---:|---|
| `radiusS` | 2 | 얇은 요소 (fader thumb, track 헤더) |
| `radiusM` | 3 | 버튼, 콤보 (기본) |
| `radiusL` | 6 | 큰 패널, dialog |

---

## 5. Paint helper (Sprint 47 KKK4 추가)

```cpp
// 섹션 배경
MetallicLookAndFeel::drawPanelBackground(g, bounds.toFloat());

// 섹션 헤더 바
auto headerArea = bounds.removeFromTop(28);
MetallicLookAndFeel::drawSectionHeader(g, headerArea, "Mixer");

// 분할선
auto dividerArea = bounds.removeFromBottom(1);
MetallicLookAndFeel::drawDivider(g, dividerArea);
```

기존 컴포넌트는 **migration 의무 아님** — 새 컴포넌트에 권장.

---

## 6. 툴팁 작성 원칙 (Sprint 47 KKK2/KKK3 적용)

1. **한 문장**, 25 자 내외. 마침표 권장.
2. **동작 + 단축키** 형식: `"재생 (Space). 정지 상태에서는 맨 앞에서 시작"`
3. 값 범위 있으면 포함: `"BPM — 20~300, 0.1 단위"`
4. 파괴적 동작이면 명시: `"프로젝트 삭제 (되돌릴 수 없음)"`
5. **금지**: "이 버튼은 ~" 같은 중언부언, "(버튼)" 접미사, 영어만

적용된 예 (Sprint 47):
- TransportBar: play/stop/rec/loop/metro/tempo/key/scale/snap/countIn/tap — 13 위젯
- MixerPanel: pan/mute/solo/fader/fxBypass — 채널당 5 위젯

---

## 7. 빌드 검증 체크 (빌드 머신에서)

Sprint 47 C++ 변경 후 빌드 머신에서 확인:

- [ ] `build.bat --install` 성공
- [ ] Standalone 실행 후 TransportBar 위젯에 마우스 오버 시 툴팁 노출
- [ ] MixerPanel 채널 스트립 M/S/Pan/Fader 툴팁 노출
- [ ] `MetallicLookAndFeel::drawPanelBackground` 호출부 없어도 링킹 OK
  (현재 unused, 추후 리팩터링용)
- [ ] 헤더 상수 추가로 인한 ABI 영향 없음 확인

변경 범위:
- `Source/UI/LookAndFeel.h` — constexpr 추가 + 메서드 선언 3
- `Source/UI/LookAndFeel.cpp` — 메서드 정의 3 (기존 함수 앞에 삽입)
- `Source/UI/TransportBar.cpp` — 생성자에 setTooltip 13 줄 추가
- `Source/UI/MixerPanel.cpp` — 2 곳 (bus + track 스트립) 5 setTooltip 씩

---

## 8. 관련 문서

- `docs/keyboard_shortcuts.md` — 단축키 전수 (Sprint 46 JJJ3)
- `juce_daw_clean/Source/UI/LookAndFeel.h` — 토큰/상수 단일 출처
- `.claude/rules/` — 전체 규약
