# MidiGPT JUCE DAW — 시제품 비교 벤치마크 프레임워크

> 작성: 2026-04-09
> 분류: DAW / 품질 검증 / 비교
> 관련: [02_PDR.md](02_PDR.md), [04_5대_평가.md](04_5대_평가.md)

---

## 0. 문서의 목적

본 문서는 MidiGPT가 제작한 자체 DAW(JUCE 기반)를 **시중에서 사용되는 시제품 DAW**와 정량/정성 비교하기 위한 표준 프레임워크다.

> ✅ **시제품 DAW 확정 (2026-04-09)**: **Steinberg Cubase 15 Pro**. 우리 어휘(`midigpt/tokenizer/vocab.py`)가 이미 Cubase 15 기반이므로, 본 비교는 단순 벤치마크가 아니라 **"의도적 통합 전략의 정합성 검증"** 이다. §3 의 기능 매트릭스와 §5 의 측정값 표는 다음 sprint 에 사람 패널이 채워 넣는다.

비교 목적:
1. **편의성** — 작곡가 입장에서 시제품만큼 자연스럽게 쓸 수 있는가
2. **품질** — 시제품과 동등하거나 우수한 결과를 내는가
3. **차별화** — 시제품에 없고 우리에게만 있는 것은 무엇인가
4. **격차** — 시제품에 있고 우리에게 없는 것은 무엇이고, 어떻게 메울 것인가

---

## 1. 비교 원칙

### 1-1. 공정성
- 같은 OS / 같은 하드웨어에서 측정
- 같은 입력 (동일 MIDI 파일, 동일 길이, 동일 트랙 수)
- 같은 작곡가 (벤치마크 1세션 = 1인 작곡가)

### 1-2. 정량 + 정성 병행
- **정량**: latency, CPU, RAM, 디스크 IO, crash 빈도
- **정성**: UX 평점 (1-10), 워크플로우 인지 부하, "다시 쓰고 싶은가"

### 1-3. 차별화 별도 평가
- 시제품에 없는 우리만의 기능 (LLM 변주, 화성 마스킹, LoRA 핫스왑) 은 별도 카테고리로 평가
- 비교가 아닌 추가 가치로 측정

---

## 2. 시제품 DAW 정보 — Steinberg Cubase 15 Pro

| 항목 | Cubase 15 Pro | MidiGPT JUCE |
|------|---------------|--------------|
| 제품명 | Cubase 15 Pro | MidiGPT Workstation |
| 제조사 | Steinberg Media Technologies (독일, Yamaha 자회사) | MidiGPT 팀 |
| 버전 | 15.x (2024-2025 출시 추정) | alpha |
| 라이선스 | 상용 (영구 라이선스 + 업그레이드) | MIT (베이스), 유료 LoRA (Phase C) |
| 가격 | Pro $580 (Artist $330, Elements $100, AI $50) | $0 (베타) → $15/월 (Pro) |
| 출시 | 정식 출시 (Steinberg 공식 채널) | 미출시 |
| 호스트 시스템 | Windows 10/11, macOS 12+ | Windows 검증, Mac/Linux 미검증 |
| 배포 형식 | 공식 다운로드 (ISO 디스크 이미지 + Steinberg Download Assistant) | GitHub 소스 + 빌드 |

### 2-1. Cubase 15 Pro 의 강점 (시장 평가 기준)

1. **VST3 표준의 본가** — Steinberg가 VST를 발명. Cubase는 VST 호스팅의 reference 구현
2. **Expression Maps** — 단일 트랙에서 articulation을 키 스위치/CC로 자동 전환. Cubase 의 시그니처 기능
3. **Score Editor** — 전문 사보 도구 내장. Sibelius / Finale 수준의 악보 출력
4. **Chord Track** — 코드 진행을 별도 트랙으로 관리, 다른 트랙이 자동으로 따라옴
5. **Logical Editor / Project Logical Editor** — MIDI 데이터를 룰 기반으로 변형
6. **MediaBay** — 샘플/패치/프리셋 통합 검색
7. **MPE / Note Expression** — per-note CC, 차세대 컨트롤러 지원
8. **HALion Sonic SE / Groove Agent SE 번들** — 고품질 내장 신스/드럼

### 2-2. Cubase 15 Pro 의 약점 (시장 불만 기준)

1. **러닝 커브 가파름** — 처음 사용자에게 압도적인 메뉴/기능 수
2. **eLicenser 이슈** — 과거 USB 동글 의무 (최근 Steinberg Activation Manager로 이전)
3. **메모리 사용량 큼** — 빈 프로젝트도 1GB+ RAM
4. **AI/ML 통합 거의 없음** — 변주 / 자동 편곡 / 자동 멜로디 생성 0
5. **CC 오토메이션 UX** — 일부 사용자가 ProTools/Logic 대비 답답하다는 의견

→ **5번이 우리의 핵심 진입점**: Cubase에 없는 LLM AI 동료를 그 안에 꽂는 전략.

### 2-3. 우리가 이미 Cubase 15와 통합한 부분 (vocab.py 기준)

| 영역 | Cubase 15 | MidiGPT vocab.py |
|------|-----------|-----------------|
| Articulation | 298종 (Cubase 15 kLengths/kTechniques/kOrnaments) | **32종 핵심 선별 통합** |
| Dynamics | 25종 | **13종 핵심 통합** |
| CC11 Expression | 0~127 | **16단계 양자화** |
| CC1 Modulation | 0~127 | **16단계 양자화** |
| CC64 Sustain | on/off | **on/off** |
| PitchBend | -8192~+8191 | **16단계** |
| Instrument Family | 21 families (ScoringEngine) | **11종 핵심 통합** |
| Style/Template | 다수 | **16종** (Cubase 프로젝트 템플릿 기반) |
| Track Type | 다수 | **14종** (Cubase 트랙 구조 기반) |

→ **우리 토큰 어휘는 사실상 "Cubase 15의 압축판 + 14 트랙 카테고리"**.
이 통합은 차별화 자산(✅)이자 동시에 IP 리스크 점검 영역(⚠️). §6 참조.

---

## 3. 기능 매트릭스 (Feature Parity)

### 3-1. 기본 DAW 기능

| 카테고리 | 기능 | MidiGPT JUCE | Cubase 15 Pro | 격차 / 차별화 |
|----------|------|--------------|---------------|---------------|
| **MIDI 편집** | 노트 입력 (Key Editor) | ✅ PianoRoll | ✅ Key Editor | 동등 (UX는 Cubase 우위 추정) |
| | 노트 편집 (drag/copy/quantize) | ✅ | ✅ + iQ (interactive quantize) | Cubase 우위 — iQ 미구현 |
| | 벨로시티 편집 | ✅ | ✅ + Velocity Curve presets | Cubase 우위 |
| | CC 편집 (오토메이션 레인) | 🔶 부분 | ✅ + automation panel | Cubase 우위 |
| | MPE / Note Expression | 🔶 vocab 지원, UI 미구현 | ✅ Note Expression (Cubase 시그니처) | Cubase 우위 — 우리 우선순위 P2 |
| | Expression Maps (articulation 자동 전환) | 🔶 vocab 32종 매핑됨, 런타임 전환 미구현 | ✅ **Cubase 시그니처** | Cubase 우위 — 우리 P1 |
| | Logical Editor (룰 기반 변형) | ❌ | ✅ + Project Logical Editor | Cubase 우위 / 우리는 LLM이 대체 |
| **트랙 / 믹서** | 트랙 추가/삭제 | ✅ TrackProcessor | ✅ | 동등 |
| | 믹서 (볼륨/팬/뮤트) | ✅ MixerPanel | ✅ MixConsole (12 종 채널) | Cubase 우위 |
| | 라우팅 | 🔶 부분 | ✅ Direct Routing + Cue Sends | Cubase 우위 |
| | 이펙트 체인 | 🔶 effects_engine.py | ✅ + 80+ 내장 이펙트 | Cubase 압도 |
| | Group / FX 채널 | _(확인 필요)_ | ✅ | Cubase 우위 |
| **재생 / 녹음** | MIDI 재생 | ✅ SynthEngine | ✅ | 동등 |
| | MIDI 녹음 | ✅ MidiEngine | ✅ + Cycle Recording / Stacked | Cubase 우위 |
| | 오디오 녹음 | 🔶 AudioEngine 기본 | ✅ + ARA 통합 (Melodyne 등) | Cubase 압도 |
| | 메트로놈 | _(확인 필요)_ | ✅ + Metronome Setup | Cubase 우위 |
| **프로젝트** | 저장/불러오기 | ✅ ProjectState | ✅ Project File (.cpr) | 동등 |
| | Undo/Redo | _(확인 필요)_ | ✅ + Edit History 윈도우 | Cubase 우위 |
| | 멀티 윈도우 | _(확인 필요)_ | ✅ Workspaces 시스템 | Cubase 우위 |
| | Chord Track | ❌ (LLM이 대체) | ✅ **Cubase 시그니처** | LLM 변주로 보완 |
| | Score Editor (사보) | 🔶 score_engine.py 기본 | ✅ Score Editor (Sibelius급) | Cubase 압도 |

### 3-2. 인스트루먼트 / 신스

| 기능 | MidiGPT JUCE | Cubase 15 Pro | 격차 / 차별화 |
|------|--------------|---------------|---------------|
| 내장 신스 | ✅ SynthEngine (기본) | ✅ HALion Sonic SE 3, Retrologue, Padshop, Groove Agent SE | Cubase 압도 |
| 샘플러 | _(확인 필요)_ | ✅ Sampler Track 2 + HALion | Cubase 우위 |
| VST3 호스팅 | ❌ 미구현 (M4 목표) | ✅ **VST 본가** | **결정적 격차** — M4 우선순위 |
| CLAP 호스팅 | ❌ 미구현 (M4 목표) | 🔶 Cubase 14+ 부분 지원 | 차별화 가능 (CLAP 적극 지원) |
| AU 호스팅 | ❌ Mac 미검증 | ✅ macOS | Cubase 우위 |
| MediaBay (샘플 검색) | ❌ | ✅ MediaBay | Cubase 우위 |

### 3-3. 우리만의 차별화 기능 (시제품 비교 불필요)

| 기능 | 상태 | 비고 |
|------|------|------|
| **LLM 변주 생성** | ✅ AIEngine + 화성 마스킹 | 시제품 거의 없음 |
| **LoRA 핫스왑** | ✅ inference engine | 시제품 0 |
| **Audio2MIDI** | ✅ Demucs + Basic Pitch | 시제품 일부 (외부 도구 연동) |
| **Sheet2MIDI** | ✅ SMT++ OMR | 시제품 0 |
| **화성 마스킹** | ✅ 추론 시 off-scale 차단 | 시제품 0 |
| **Cubase 15 어휘 통합** | ✅ 32 articulation, CC, MPE | 일부 DAW만 |
| **멀티에이전트 백엔드** | ✅ Composer/Manager/Reviewer/Orchestrator | 시제품 0 |

---

## 4. UX 비교 (정성)

### 4-1. 평가 방식
외부 작곡가 5명 패널이 동일 작업을 두 DAW에서 수행하고 평점:

| 작업 | 평가 항목 |
|------|-----------|
| 새 프로젝트 생성 | 단계 수, 직관성 |
| 첫 트랙 추가 + MIDI 노트 입력 | 시간, 인지 부하 |
| 변주 생성 (MidiGPT만) | 결과 만족도 |
| 미디 export → 다른 DAW로 | 호환성 |
| 30분 자유 작업 | "다시 쓰고 싶은가" 평점 |

### 4-2. 평점 매트릭스 (5명 패널 평균, 1-10)

| 영역 | MidiGPT JUCE | 시제품 | 비고 |
|------|--------------|--------|------|
| 첫 인상 (5분) | _(측정)_ | _(측정)_ | _(평점 후 채우기)_ |
| 학습 곡선 (1시간) | _(측정)_ | _(측정)_ | |
| 워크플로우 자연스러움 | _(측정)_ | _(측정)_ | |
| 안정성 (crash 빈도) | _(측정)_ | _(측정)_ | |
| 시각적 디자인 | _(측정)_ | _(측정)_ | |
| 단축키 효율 | _(측정)_ | _(측정)_ | |
| 다시 쓰고 싶음 | _(측정)_ | _(측정)_ | |
| **종합** | _(평균)_ | _(평균)_ | |

### 4-3. 정성 코멘트 양식
패널마다 다음 4문장:
1. "가장 좋았던 것은 ______"
2. "가장 답답했던 것은 ______"
3. "시제품 대비 더 좋은 것은 ______"
4. "시제품 대비 부족한 것은 ______"

---

## 5. 정량 측정 (성능)

### 5-1. 측정 환경
- 기준 머신: Windows 11, RTX 4080, 32GB RAM, NVMe SSD
- 동일 입력 MIDI 파일 (예: `midi_data/CITY POP 105 4-4 ALL.mid`, 30초)

### 5-2. 측정 항목

| 지표 | 단위 | MidiGPT JUCE | 시제품 | 비고 |
|------|------|--------------|--------|------|
| 앱 시작 시간 | 초 | _(측정)_ | _(측정)_ | 더블클릭 → 메인 윈도우 |
| 첫 프로젝트 생성 | 초 | _(측정)_ | _(측정)_ | New → 빈 프로젝트 |
| MIDI import latency | ms | _(측정)_ | _(측정)_ | 30초 곡 |
| MIDI playback start | ms | _(측정)_ | _(측정)_ | 재생 버튼 → 첫 노트 |
| 아이들 CPU | % | _(측정)_ | _(측정)_ | 빈 프로젝트, 1분 |
| 재생 중 CPU | % | _(측정)_ | _(측정)_ | 30초 곡 재생 |
| 아이들 RAM | MB | _(측정)_ | _(측정)_ | 빈 프로젝트 |
| 재생 중 RAM | MB | _(측정)_ | _(측정)_ | 30초 곡 재생 |
| **변주 생성 latency** | 초 | _(측정)_ | N/A | 시제품 미보유 기능 |
| Crash / 1시간 | 회 | _(측정)_ | _(측정)_ | 자유 사용 |

### 5-3. 측정 절차
```bash
# 1. 머신 정리 (cold start)
# 2. MidiGPT JUCE 빌드 실행 → 측정 → 종료
# 3. 시제품 실행 → 동일 작업 → 측정 → 종료
# 4. 5회 반복 → 평균 + 표준편차
```

---

## 6. 라이선스 / IP 리스크 — Steinberg Cubase 15 Pro

### 6-0. ISO 파일 형식에 대한 사실 정리

**ISO는 단지 디스크 이미지 파일 형식이며, 자체로는 합법/불법을 의미하지 않습니다.** Steinberg는 Cubase 정식 설치 파일을 ISO 또는 Steinberg Download Assistant 를 통해 배포합니다. 정식 라이선스 사용자도 ISO를 받습니다.

**핵심 변수**: ISO를 **어디서** 받았는가입니다.

| 출처 | 합법성 | IP 리스크 |
|------|--------|-----------|
| Steinberg 공식 다운로드 (라이선스 보유) | ✅ 합법 | 낮음 |
| 학생/교육 라이선스 | ✅ 합법 (학생 본인 한정) | 낮음 |
| 30일 무료 평가판 | ✅ 합법 (평가 목적) | 낮음 |
| 회사/스튜디오 라이선스 | ✅ 합법 (고용주 한정) | 낮음 |
| 제3자 공유 / 토렌트 / 크랙 | ❌ 라이선스 위반 | 높음 (사업 진행 시) |

> ⚠️ **사업가 페르소나 코멘트**: 출처가 비공식이라면, **참고용 사용은 우리의 직접 IP 침해는 아니지만**, 사업 외부 커뮤니케이션 시 (투자자, 미디어, 법률 검토) 는 반드시 정식 라이선스 보유 상태로 전환해두는 것이 안전합니다. Cubase Pro $580 / Artist $330 / Elements $100 / AI $50 — 우리 사업 단계에서 1카피 정도는 즉시 구입 가능한 비용입니다.

**즉시 액션**: 개발자/작곡가 중 1인이 정식 라이선스 보유 상태로 만들어 두기 (Cubase AI 또는 Elements 도 충분).

### 6-1. Cubase 15 의 라이선스 항목 확인

- [ ] **EULA 준수**: Steinberg EULA 는 "역공학(reverse engineering) 금지" 조항을 명시. 우리 JUCE 코드 작성 시 디컴파일/디스어셈블 결과물 절대 0건 확인 필요
- [ ] **상표(Trademark)**: "Cubase", "VST", "HALion", "Steinberg" 는 등록 상표. 우리 마케팅/문서에서 "Cubase 15 호환" 같은 사실 진술은 OK, "Cubase의 대체품" 같은 표현은 검토 필요
- [ ] **VST3 SDK 라이선스**: VST3 SDK는 GPLv3 (오픈소스) 또는 Steinberg Proprietary License (상용) 중 선택. 우리가 VST3 호스팅 모듈을 만들 때 어느 라이선스를 따르는지 명시 필요. 상용 출시 시 Proprietary License 권장 (GPL 전염성 회피)
- [ ] **VST3 SDK 등록**: 상용 VST3 호스트는 Steinberg 에 등록(무료) 권장
- [ ] **Expression Maps 어휘 차용**: 우리 vocab.py 의 32 articulation 이 Cubase Expression Maps 의 어휘와 일대일 매칭되는지 확인. 어휘 자체(예: "spiccato", "pizzicato") 는 음악 일반 용어이므로 OK, Cubase 의 고유 어휘 (예: "Long+Vibrato Att.") 는 회피 권장
- [ ] **HALion / Groove Agent 사운드 샘플**: 절대 우리 에셋에 포함 금지

### 6-2. 안전 / 위험 가이드 (Cubase 15 특화)

**✅ 안전 (차용 OK)**:
- DAW 일반 워크플로우 (트랙 / 리전 / 클립 / 믹서 / 인스트루먼트)
- 산업 표준 용어 (BPM, MIDI Channel, CC, Velocity, Quantize)
- 음악 이론 용어 (chord, key, scale, articulation 일반 명칭)
- 피아노롤 / 믹서 / 트랙 리스트 같은 일반화된 UI 패턴
- VST3 SDK (라이선스 준수 시)

**⚠️ 주의 (차별화 권장)**:
- Cubase 의 고유 5-zone 레이아웃을 그대로 복제 → 우리는 "5-zone UI" 라는 표현을 사용 중이라 명칭만 변경 권장
- Cubase 의 색상 팔레트 (Steinberg 검정+회색+청록 톤) 직접 차용
- Cubase 의 아이콘 디자인 직접 차용
- Cubase 의 메뉴 구조 (Project / Edit / Audio / MIDI / Score / ...) 동일 순서 차용
- Expression Maps 의 구체 워크플로우 (Slot 시스템) 동일 복제

**❌ 금지 (즉시 제거)**:
- Cubase 소스코드 / 컴파일된 라이브러리 직접 사용
- Cubase 디컴파일 / 디스어셈블 결과물 사용
- HALion / Groove Agent 등 번들 사운드 직접 사용
- "Cubase" / "Steinberg" / "VST" 등록 상표를 우리 제품명에 포함
- Cubase 인증 서버 / DRM 우회

### 6-3. 즉시 권장 조치 (오늘 ~ 이번 주)

| # | 조치 | 책임 | 노력 |
|---|------|------|------|
| 1 | Cubase 정식 라이선스 1카피 확보 (Elements $100 권장) | 사업가 | 30분 |
| 2 | JUCE 소스에 Cubase 디컴파일 결과물 0건 자체 점검 | 개발자 | 1시간 |
| 3 | `juce_app/Source/` 에 Cubase 직접 차용 흔적 점검 (UI 색상, 아이콘, 메뉴 명칭) | 개발자 | 2시간 |
| 4 | `assets/` 폴더 (있다면) 의 모든 사운드/이미지 출처 명시 (`SOURCES.md`) | 개발자 | 1시간 |
| 5 | vocab.py 의 articulation 명칭이 Cubase 고유 표현과 일치하는지 점검 | 개발자 | 30분 |
| 6 | "5-zone UI" 명칭 변경 검토 (예: "5-pane Layout") | 사업가 + 개발자 | 즉시 |
| 7 | VST3 호스팅 시 SDK 라이선스 선택 (GPL vs Proprietary) | 개발자 | M4 진입 전 |
| 8 | Phase C 진입 전 IP 변호사 검토 1회 | 사업가 | $300-500 |

### 6-4. 우리에게 유리한 사실

1. **Cubase 어휘 통합은 "호환성"으로 마케팅 가능** — Steinberg의 등록 상표만 침해하지 않으면, 우리가 Cubase Project 파일이나 Expression Map과 호환된다는 사실은 합법적인 경쟁 우위
2. **VST3 SDK는 공개 표준** — 우리가 Cubase 안에 VST3 플러그인으로 들어가는 전략은 Steinberg가 적극 권장하는 통합 형태
3. **차별화 영역(LLM)은 Cubase에 없음** — 직접 경쟁이 아니라 **보완**이라는 포지션이 IP 분쟁 가능성을 거의 0으로 만듦
4. **Cubase 15 어휘는 "사실상의 산업 표준"** — Cubase는 시장 점유율 1-2위 DAW. 그 어휘를 차용하는 것은 표준화의 일환으로 해석 가능

---

## 7. 차별화 전략 — Cubase 15 와의 관계 정의

### 7-1. 우리가 Cubase 를 따라잡아야 하는 영역 (격차 메우기)
1. **VST3 호스팅** — Cubase는 VST 본가, 우리는 미구현. **M4 최우선순위**
2. **Expression Maps 런타임 전환** — 우리는 vocab만 통합, 런타임 전환 미구현
3. **MixConsole 수준의 믹서** — 우리는 기본 MixerPanel만
4. **Score Editor 사보 품질** — 우리 score_engine.py는 기본 수준
5. **안정성 / crash 빈도** — Cubase는 검증된 상용 제품
6. **macOS / Linux 지원** — Cubase는 Win/Mac, 우리는 Win 위주

### 7-2. 우리가 압도적으로 우월한 영역 (차별화 강화)
1. **LLM 변주 생성** — Cubase 0
2. **화성 마스킹 (off-scale 강제 차단)** — Cubase 0
3. **LoRA 핫스왑 (스타일 어댑터)** — Cubase 0
4. **Audio2MIDI / Sheet2MIDI** — Cubase 0 (외부 도구 ARA 통합만)
5. **CLAP 적극 지원** — Cubase 14+ 는 부분 지원, 우리는 처음부터 우선순위
6. **오픈소스 베이스 + 유료 LoRA 마켓** — Cubase는 클로즈드 상용

### 7-3. 포지셔닝 — **"Cubase 의 대체품이 아니라 Cubase 안의 동료"**

> Cubase 15 의 익숙한 워크플로우 + Cubase 에 없는 LLM AI 동료 = MidiGPT

**3가지 가능한 포지션 중 우리의 선택**:

| 포지션 | 의미 | 채택 |
|--------|------|------|
| Cubase 대체 (Replacement) | 우리 JUCE 앱 단독으로 Cubase 사용자를 빼앗는다 | ❌ 비현실적 (Cubase 35년 + 1-2위 점유율) |
| Cubase 보완 (Companion) | Cubase 안에 VST3 플러그인으로 들어가서 LLM 기능을 제공 | ✅ **채택** |
| Cubase 무관 (Standalone) | Cubase와 별개의 새 워크플로우를 정의 | 🔶 단기는 가능하나 장기적 락인 약함 |

**Companion 포지션의 함의**:
1. JUCE 데스크톱 앱은 **알파/베타 단계의 검증 도구**로 유지하되, **출시 시점의 메인 제품은 VST3 플러그인**
2. 5-zone UI 등 데스크톱 앱의 UI는 그대로 VST3 플러그인 안에 임베드
3. 마케팅 메시지: "Cubase 사용자를 위한 첫 LLM AI 동료" → 직접 경쟁이 아닌 보완
4. Steinberg 와의 관계가 우호적 (잠재적 파트너십 가능)
5. IP 리스크 거의 0 — Cubase 안에서 동작하는 도구이므로 Cubase 자체와 경쟁이 아님

→ **본 포지셔닝이 사업기획서 / PDR / 상품 설명서 모두에 일관 적용되어야 한다.**

---

## 8. 측정 절차 (실행 가이드)

### 8-1. 1차 측정 (1주일)
1. 시제품 DAW 정보 확정 → §2 채우기
2. 기능 매트릭스 §3 채우기 (개발자 단독)
3. 정량 측정 §5 채우기 (개발자 + 자동 측정 스크립트)

### 8-2. 2차 측정 (2-3주차)
4. 외부 작곡가 패널 5명 모집 (M2 마일스톤과 동시)
5. 패널이 동일 작업 수행 → §4 평점
6. 정성 코멘트 4문장 수집 → 정리

### 8-3. 결과 정리 (4주차)
7. 종합 점수 계산
8. 격차 / 차별화 매트릭스 작성
9. 다음 분기 우선순위 plan 도출
10. 본 문서를 사업기획서 부록으로 첨부

---

## 9. 의사결정 시나리오

벤치마크 결과에 따라 다음 액션 :

### 시나리오 A: 정량 측정에서 시제품과 동등 (격차 < 20%)
→ 차별화 기능(LLM)에 자원 집중. M4 (VST3 호스팅) 가속.

### 시나리오 B: 격차 20-50% (느리거나 불안정)
→ JUCE 코드 최적화 sprint 1주. 안정성 우선.

### 시나리오 C: 격차 50%+ (사용 불가 수준)
→ JUCE DAW 자체 개발을 보류하고, **VST3 플러그인 전략으로 전환**. 시제품 안에 우리 LLM을 꽂는 형태로.

### 시나리오 D: 정성 평점 < 5/10
→ UX 디자인 재검토. 외부 디자이너 1명 외주 권장.

### 시나리오 E: 정성 평점 ≥ 7/10
→ 출시 가능 신호. M5 Closed Beta 진행.

---

## 10. 변경 이력

- 2026-04-09: 초판 작성. 시제품 DAW 미확정 상태로 프레임워크만 정의.
- (다음) 시제품 확정 → §2, §3, §5 측정값 채우기
