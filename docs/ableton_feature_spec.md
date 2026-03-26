# Ableton Live 12 전체 기능 명세서

> 본 문서는 Ableton Live 12 (Suite Edition 기준)의 모든 기능을 체계적으로 정리한 기술 명세서입니다.
> 클론 프로젝트 구현을 위한 참조 문서로 사용됩니다.

---

## 목차

1. [전체 아키텍처 및 핵심 개념](#1-전체-아키텍처-및-핵심-개념)
2. [Session View (세션 뷰)](#2-session-view-세션-뷰)
3. [Arrangement View (어레인지먼트 뷰)](#3-arrangement-view-어레인지먼트-뷰)
4. [Clip View (클립 뷰)](#4-clip-view-클립-뷰)
5. [MIDI Editor / Piano Roll (MIDI 에디터)](#5-midi-editor--piano-roll)
6. [Audio Editor (오디오 에디터)](#6-audio-editor-오디오-에디터)
7. [Instruments (내장 악기)](#7-instruments-내장-악기)
8. [Audio Effects (오디오 이펙트)](#8-audio-effects-오디오-이펙트)
9. [MIDI Effects (MIDI 이펙트)](#9-midi-effects-midi-이펙트)
10. [MIDI Tools (MIDI 도구)](#10-midi-tools-midi-도구)
11. [Modulators (모듈레이터)](#11-modulators-모듈레이터)
12. [Mixer (믹서)](#12-mixer-믹서)
13. [Browser (브라우저)](#13-browser-브라우저)
14. [Transport (트랜스포트)](#14-transport-트랜스포트)
15. [Automation (오토메이션)](#15-automation-오토메이션)
16. [Routing (라우팅)](#16-routing-라우팅)
17. [Warping (워핑)](#17-warping-워핑)
18. [Sampling (샘플링)](#18-sampling-샘플링)
19. [Recording (녹음)](#19-recording-녹음)
20. [Comping (컴핑)](#20-comping-컴핑)
21. [File Management (파일 관리)](#21-file-management-파일-관리)
22. [Preferences / Settings (환경설정)](#22-preferences--settings-환경설정)
23. [Key / MIDI Mapping (키/MIDI 매핑)](#23-key--midi-mapping)
24. [Grooves (그루브)](#24-grooves-그루브)
25. [Racks (랙)](#25-racks-랙)
26. [Max for Live](#26-max-for-live)
27. [Link / Tempo / Sync (동기화)](#27-link--tempo--sync-동기화)
28. [Video (비디오)](#28-video-비디오)
29. [Control Surfaces (컨트롤 서피스)](#29-control-surfaces-컨트롤-서피스)
30. [Stem Separation (스템 분리)](#30-stem-separation-스템-분리)
31. [Audio-to-MIDI Conversion (오디오→MIDI 변환)](#31-audio-to-midi-conversion)
32. [Tuning Systems (튜닝 시스템)](#32-tuning-systems-튜닝-시스템)
33. [Keys and Scales (키 및 스케일)](#33-keys-and-scales-키-및-스케일)
34. [Accessibility (접근성)](#34-accessibility-접근성)
35. [Keyboard Shortcuts (키보드 단축키)](#35-keyboard-shortcuts-키보드-단축키)

---

## 1. 전체 아키텍처 및 핵심 개념

### 1.1 문서 유형
- **Live Set (.als)**: 프로젝트 파일 (모든 트랙, 디바이스, 클립, 오토메이션 포함)
- **Live Project**: Live Set과 관련 파일(샘플, 프리셋 등)을 포함하는 폴더
- **Live Pack (.alp)**: 압축된 프로젝트 배포 형식
- **Live Clip (.alc)**: 개별 클립 프리셋 파일
- **Live Preset (.adv, .adg, .agr 등)**: 디바이스/그루브 프리셋

### 1.2 트랙 유형
- **Audio Track**: 오디오 클립 재생 및 오디오 녹음
- **MIDI Track**: MIDI 클립 재생 및 MIDI 녹음, 악기 호스팅
- **Return Track**: 센드 이펙트 처리용 보조 트랙
- **Group Track**: 여러 트랙을 서브믹스로 묶는 그룹 트랙
- **Main Track (Master)**: 최종 출력 트랙, 마스터링 이펙트 호스팅

### 1.3 클립 유형
- **Audio Clip**: 오디오 샘플 기반 클립 (워핑, 피치, 게인 제어)
- **MIDI Clip**: MIDI 노트 데이터 기반 클립 (노트, 벨로시티, CC 데이터)

### 1.4 듀얼 뷰 시스템
- **Session View**: 비선형, 즉흥적 클립 런칭 및 실험
- **Arrangement View**: 선형 타임라인 기반 편집 및 작곡
- Tab 키로 두 뷰 간 전환
- 두 번째 창 지원 (Ctrl+Shift+W)으로 동시 표시

### 1.5 오디오 엔진 사양
- 최대 32-bit/192kHz 멀티트랙 녹음
- 무제한 트랙 수 (Standard/Suite)
- Intro 에디션: 최대 16 오디오/MIDI 트랙, 16 씬
- 멀티코어/멀티프로세서 지원
- 자동 플러그인 딜레이 보상 (PDC)
- WAV, AIFF, MP3, Ogg Vorbis, FLAC 파일 지원
- REX 파일 지원
- POW-r 디더링
- VST2, VST3, Audio Unit 플러그인 지원

---

## 2. Session View (세션 뷰)

### 2.1 클립 슬롯 그리드
- 세로 열 = 트랙, 가로 행 = 씬
- 각 트랙은 동시에 하나의 클립만 재생
- 클립 슬롯에 삼각형 런치 버튼 표시
- 빈 슬롯에 정지 버튼 추가/제거 가능 (Edit > Add/Remove Stop Button)
- 클립 이름 변경, 색상 커스터마이징
- 클립 비활성화 (0 키로 토글)
- 드래그 앤 드롭으로 클립 재배치
- Shift+클릭, Ctrl+클릭으로 다중 선택
- Ctrl+드래그로 클립 복사

### 2.2 씬 (Scene)
- 씬 런치 버튼: 한 행의 모든 클립 동시 런칭
- 씬 번호: 위치에 따라 자동 결정, 재배치 시 업데이트
- 씬별 템포/박자표 설정 가능
- 씬 이름, 정보 텍스트, 커스텀 색상 편집
- 씬 런치 시 자동으로 다음 씬 선택 ("Select Next Scene on Launch" 옵션)
- 색상이 있는 런치 버튼은 템포/박자 변경 표시
- 씬 삽입 (Ctrl+I)
- 캡처 및 씬 삽입 (Ctrl+Shift+I): 현재 재생 중인 클립 스냅샷

### 2.3 Scene View (씬 뷰)
- 씬 선택 시 또는 Main 트랙 타이틀 클릭 시 열림
- 템포 및 박자표 슬라이더
- 씬 Follow Action 설정

### 2.4 트랙 상태 표시기
- 루핑 클립: 파이 차트 아이콘 (루프 길이 및 재생 횟수 표시)
- 원샷 클립: 진행 바 아이콘 (남은 시간 표시)
- 입력 모니터링: 마이크(오디오) 또는 키보드(MIDI) 아이콘
- 어레인지먼트 재생: 미니어처 어레인지먼트 표시

### 2.5 클립 런칭
- 마우스 클릭으로 클립 런칭
- 클립 이름 클릭 후 Enter 키로 런칭
- 키보드 방향키로 인접 클립/슬롯 탐색
- 클립 런치 퀀타이제이션 (None, Global, 1/4 bar, 1/2 bar, 1 bar, 2 bars 등)

### 2.6 녹음 기능
- Arrangement Record 버튼: 모든 Session 동작을 Arrangement에 기록
- 기록 대상: 런칭된 클립, 클립 속성 변경, 믹서/디바이스 오토메이션, 템포/박자 변경
- Session과 Arrangement 클립은 상호 배타적
- "Back to Arrangement" 버튼으로 Arrangement 재생 복원

### 2.7 그리드 관리
- "Consolidate Time to New Scene": Arrangement 재료를 Session 클립으로 변환
- Session ↔ Arrangement 간 복사/붙여넣기
- 두 번째 창으로 나란히 편집 가능

---

## 3. Arrangement View (어레인지먼트 뷰)

### 3.1 탐색 및 표시
- **Overview (개요)**: 전체 어레인지먼트 레이아웃 표시, 드래그로 스크롤/줌
- **Beat-Time Ruler**: bars-beats-sixteenths 표시
- **Time Ruler**: minutes-seconds-milliseconds 표시
- 키보드 단축키로 줌 (Ctrl++/-, +/-)
- Z 키: 선택 영역 줌, X 키: 이전 줌 상태 복원
- W 키: 전체 너비에 맞춤, H 키: 전체 높이에 맞춤
- Scroll Display to Follow Playback (Ctrl+Shift+F)

### 3.2 재생 및 트랜스포트
- 깜박이는 삽입 마커에서 재생 시작
- **Scrub Area**: 클릭하여 어느 지점에서든 재생 시작
- 글로벌 런치 값에 맞춰 퀀타이즈된 점프
- 마우스 버튼 유지 시 루프 재생
- Arrangement Position 필드: 숫자로 재생 위치 지정

### 3.3 로케이터 (Locator)
- 섹션 표시용 마커, 비선형 재생 가능
- "Set Locator" 버튼: 재생/녹음 중 마커 추가
- "Previous/Next Locator" 버튼으로 탐색
- 드래그 또는 방향키로 이동, 이름 변경, 정보 텍스트 지정

### 3.4 박자표 관리
- 박자표 마커: beat-time ruler 바로 아래 표시
- Create 메뉴로 박자 변경 삽입
- 불완전한 마디(fragmentary bars) 감지: 빗금 표시
- 불완전 시간 삭제 또는 마디 완성 옵션

### 3.5 클립 조작
- 드래그로 새 위치/트랙으로 이동
- 그리드 라인, 클립 에지, 로케이터, 박자표에 스냅
- 좌/우 에지 드래그로 리사이즈
- Ctrl+Shift (Win) / Shift+Option (Mac): 클립 경계 내에서 내용물 슬라이딩
- Shift+드래그 (타이틀 바): 워핑된 클립 스트레치

### 3.6 오디오 페이드 및 크로스페이드
- 오디오 클립 에지에 조절 가능한 페이드 핸들 (작은 사각형)
- Fade In Start / Fade Out End 핸들: 페이드 피크에 영향 없이 지속 시간 변경
- 인접 클립 간 크로스페이드: 페이드 핸들을 경계 너머로 드래그
- 페이드는 루프 경계를 넘거나 서로 겹칠 수 없음
- F 키: 페이드 핸들 일시 토글
- Ctrl+Alt+F: 페이드/크로스페이드 생성
- Ctrl+Alt+Backspace: 페이드/크로스페이드 삭제

### 3.7 선택 및 편집
- 클립 클릭, 시간 범위 드래그, 배경 클릭으로 시점 선택
- 트랙 펼치기로 클립 레벨 타이밍 세부 편집
- Shift+클릭: 선택 확장

### 3.8 그리드 및 스냅
- 편집 그리드: 박자 세분화에 스냅
- 줌 적응형(Adaptive) 또는 고정(Fixed) 모드
- Ctrl+1: 그리드 좁히기 (라인 2배)
- Ctrl+2: 그리드 넓히기 (라인 1/2)
- Ctrl+3: 삼연음(Triplet) 토글
- Ctrl+4: 스냅 토글
- Ctrl+5: 고정/줌 적응형 전환
- Alt (Win) / Cmd (Mac): 스냅 바이패스

### 3.9 클립 작업
- **Split (Ctrl+E)**: 선택 지점에서 클립 분할
- **Consolidate (Ctrl+J)**: 인접 클립을 하나로 병합
- **Crop (Ctrl+Shift+J)**: 선택 영역으로 클립 자르기
- **시간 명령 (모든 트랙에 동시 적용)**:
  - Cut Time (Ctrl+Shift+X)
  - Paste Time (Ctrl+Shift+V)
  - Duplicate Time (Ctrl+Shift+D)
  - Delete Time (Ctrl+Shift+Delete)
  - Insert Silence (Ctrl+I)

### 3.10 어레인지먼트 루프
- Control Bar에서 루프 토글 (Ctrl+L)
- Loop Start, Loop Length 필드
- 방향키로 루프 브레이스 조절:
  - 좌/우: 넛지
  - 상/하: 루프 길이만큼 위치 이동
  - Ctrl+좌/우: 그리드 설정만큼 축소/확장

### 3.11 링크드 트랙 편집
- 트랙 헤더 컨텍스트 메뉴 > "Link Tracks"
- 링크된 트랙 표시기 버튼
- 링크된 작업: 클립 이동/리사이즈, 분할, 병합, 페이드 생성, 테이크 레인 관리

### 3.12 오토메이션 및 믹서
- Automation Mode 토글: 오토메이션 레인 표시/숨기기
- Lock Envelopes 토글: 오토메이션을 곡 위치에 잠금 (클립이 아닌)
- 믹서 및 트랙 컨트롤: 볼륨, 패닝, I/O, 이펙트 접근

### 3.13 Bounce to Audio
- Bounce to New Track (Ctrl+B): 클립/선택 영역을 처리된 오디오로 변환
- Paste Bounced Audio (Ctrl+Alt+V): 선택 영역을 바운스된 오디오로 붙여넣기
- Bounce Groups: 그룹 트랙 전체 또는 일부를 인플레이스 바운스

---

## 4. Clip View (클립 뷰)

### 4.1 공통 클립 속성

#### 4.1.1 클립 영역 컨트롤
- Start Position, End Position 필드
- Set Start / Set End 버튼: 재생 중 시작/끝 위치 설정
- 퀀타이제이션 적용

#### 4.1.2 루프 컨트롤
- Clip Loop 토글: 루핑 활성화
- Loop Position, Loop Length 필드 (Set 버튼 포함)
- 재생 중 즉흥적 루프 생성 가능

#### 4.1.3 박자표
- 클립별 독립 박자표 설정
- 폴리메트릭 텍스처 가능

#### 4.1.4 그루브 설정
- Clip Groove 선택기 (Groove Pool에서)
- Hot-Swap Groove 버튼
- Commit 버튼: 그루브 설정을 클립에 기록

#### 4.1.5 스케일 설정
- Scale Mode 토글
- Root Note, Scale Name 선택기
- MIDI Note Editor에서 스케일에 해당하는 키 하이라이트

#### 4.1.6 클립 활성화
- Clip Activator 토글: 삭제 없이 클립 재생 비활성화
- 다중 선택 시 모든 클립 동시 비활성화

### 4.2 오디오 클립 전용 설정

#### 4.2.1 워프 컨트롤
- Warp 토글 (루핑 전 반드시 활성화)
- 다양한 워프 모드 선택
- Warp 비활성 시 원본 템포로 재생

#### 4.2.2 샘플 조작
- Reverse 버튼: 역재생 샘플 생성
- Edit 버튼: 외부 샘플 에디터 실행
- 파괴적 편집 가능

#### 4.2.3 클립 페이드
- Clip Fade 토글: 시작/끝 페이드 적용
- 신호 의존적 페이드 길이 (0-4 밀리초)
- "Create Fades on Clip Edges" 설정으로 새 클립 기본 활성화

#### 4.2.4 RAM 모드
- RAM Mode 토글: 오디오를 컴퓨터 메모리에 로드
- 느린 디스크 성능 개선

#### 4.2.5 오디오 품질
- High Quality 토글: 고급 샘플레이트 변환
- 높은 CPU 비용으로 더 나은 사운드

#### 4.2.6 클립 게인 및 피치
- Gain 슬라이더 (dB 단위)
- Pitch 컨트롤: 반음(Semitones) + 센트(Cents)
- 트랜스포즈 및 샘플링 레이트 매칭

#### 4.2.7 샘플 속성 표시
- 샘플 이름, 샘플레이트, 비트 깊이, 채널 수

### 4.3 MIDI 클립 전용 설정

#### 4.3.1 피치 및 시간 유틸리티
- Transpose 슬라이더: 반음 또는 스케일 도수 단위
- Fit to Scale 버튼
- Invert 버튼: 피치 반전
- Interval Size 슬라이더 + Add Interval 버튼

#### 4.3.2 시간 도구
- Stretch 노브: 노트 길이 비례 스케일링
- x2, /2 버튼: 길이 2배/반감
- Duration 선택기 + Set Length 버튼
- Humanize Amount 슬라이더 + 버튼
- Reverse 버튼: 노트 순서 반전
- Legato 버튼: 노트를 다음 노트 시작까지 연장

#### 4.3.3 MIDI Bank/Program 컨트롤
- Bank, Program 체인지 메시지 선택기
- 128 뱅크 x 128 서브뱅크 x 128 프로그램

### 4.4 에디터 뷰 모드
- **오디오 클립**: Sample Editor (파형 보기 및 워핑), Envelope Editor (오토메이션)
- **MIDI 클립**: MIDI Note Editor (노트 편집), Envelope Editor (오토메이션), MPE Editor (폴리포닉 익스프레션)
- Ctrl+Tab으로 탭 전환

### 4.5 런치 속성 (Session 클립 전용)

#### 4.5.1 Launch Mode
- **Trigger**: 누르면 재생 시작, 떼면 무시
- **Gate**: 누르는 동안만 재생
- **Toggle**: 누르면 시작, 다시 누르면 정지
- **Repeat**: 누르는 동안 퀀타이제이션 속도로 반복 트리거

#### 4.5.2 Legato Mode
- 클립 간 끊김 없는 전환, 동기화 유지
- 새 클립이 이전 클립의 재생 위치 상속

#### 4.5.3 Velocity 컨트롤
- 0-100% 범위: MIDI 노트 벨로시티가 클립 볼륨에 미치는 영향

#### 4.5.4 Follow Actions
- 클립 재생 후 자동 트리거되는 동작
- 두 개의 독립 액션 (A, B) 설정 가능
- 각 액션별 확률(Chance) 퍼센트 설정
- **10가지 사용 가능한 액션**:
  - No Action (동작 없음)
  - Stop (정지)
  - Play Again (다시 재생)
  - Previous (위 클립 재생)
  - Next (아래 클립 재생, 마지막에서 첫 번째로 순환)
  - First (첫 번째 클립으로 이동)
  - Last (마지막 클립으로 이동)
  - Any (임의 클립 선택)
  - Other (현재 클립 제외 임의 선택)
  - Jump (특정 클립/씬으로 이동)
- **Linked/Unlinked 모드**:
  - Linked: 클립 끝 또는 Follow Action Multiplier 설정 후 트리거
  - Unlinked: 지정된 시간 후 트리거
- Follow Action Time (bars-beats-sixteenths)
- Jump Target 슬라이더
- Follow Action 전역 활성화/비활성화 버튼

### 4.6 클립 오프셋 및 넛지
- Nudge Backward/Forward 버튼: 글로벌 퀀타이제이션 단위로 점프
- Scrub 컨트롤: MIDI Map Mode에서 로터리 인코더로 연속 위치 조절

### 4.7 Cropping
- 오디오/MIDI 클립 모두 지원
- 마커 사이 또는 시간 선택 영역으로 크롭
- Processed 폴더에 새 짧은 샘플 생성

### 4.8 패널 구성
- 수평 또는 수직 배열, 뷰 높이에 따라 자동 전환
- 타이틀 바 더블 클릭으로 모든 패널 최소화
- Stack Detail Views: 디바이스와 클립 에디터 동시 표시

---

## 5. MIDI Editor / Piano Roll

### 5.1 인터페이스 구성
- **Time Ruler**: 뮤지컬 타임라인상 노트 위치 표시
- **Note Ruler**: 옥타브 C-2 ~ C8 표시
- **Piano Ruler**: 피아노 키보드 표현
- **Velocity Editor**: 노트 아래에 벨로시티 마커 표시
- **Chance Editor**: 확률 마커 표시
- **MPE Expression Lanes**: Pitch Bend, Slide, Pressure 별도 레인

### 5.2 노트 생성
- **Draw Mode (B)**: 클릭+드래그로 노트 추가
  - 프리핸드 멜로디 드로잉
  - 피치 고정(Pitch-locked) 드로잉
- 녹음을 통한 노트 생성 (armed MIDI 트랙)
- "Insert Empty MIDI Clip(s)" 명령
- MIDI Step Recording: 트랜스포트 정지 상태에서 노트 입력
  - 오른쪽 방향키로 삽입 마커 이동 (그리드 설정에 따라)

### 5.3 노트 선택
- 개별 선택: 클릭 또는 Ctrl/Cmd + 방향키
- 범위 선택: 클릭+드래그
- 키보드 선택: Shift + 방향키
- Piano Ruler에서 Shift+클릭: 특정 키의 모든 노트 선택
- **Find and Select**: 피치, 시간, 벨로시티, 길이, 확률, 스케일 등으로 필터링
- 선택 반전 (Ctrl+Shift+A)

### 5.4 노트 편집
- **이동**: 수평(시간) 및 수직(피치) 드래그 또는 방향키
- **길이 조절**: 노트 좌/우 에지 드래그
- **Split (Ctrl+E)**: 특정 위치에서 노트 분할
- **Chop**: 그리드 설정에 따라 여러 부분으로 분할
  - Ctrl+E 드래그 위/아래: 1씩 증분으로 자르기
  - Ctrl+Shift+E 드래그: 2씩 증분으로 자르기
- **Join (Ctrl+J)**: 같은 피치의 노트 합치기
- **Deactivate**: 삭제 없이 노트 음소거
- **Copy Notes**: Ctrl+드래그 (Win) / Option+드래그 (Mac)

### 5.5 피치 및 시간 유틸리티
- **Transpose**: 반음 또는 스케일 도수 단위 이동
- **Fit to Scale**: 활성 스케일에 피치 조정
- **Invert**: 최고 노트↔최저 노트 위치 교환
- **Intervals**: 시프트된 복사본 추가로 코드 생성
- **Stretch**: 노트 길이 비례 스케일링 (x2, /2, 커스텀)
- **Humanize**: 노트 시작 시간에 변동 추가
- **Reverse**: 노트 시퀀스 수평 반전
- **Legato**: 노트를 다음 노트 시작까지 연장

### 5.6 벨로시티 편집
- Velocity Editor: 색상 채도로 벨로시티 표시
- 마커 드래그로 수동 조절
- 랜덤화 (지정 범위)
- 램프 컨트롤: 점진적 벨로시티 변화
- Velocity Deviation: 범위 내 동적 변동
- Draw Mode로 벨로시티 커브 그리기
- **Release Velocity**: Note Off 벨로시티 편집 (별도 에디터 레인)
- 키보드로 벨로시티 직접 입력: 0-127 + Enter
- Ctrl+Up/Down: 벨로시티 조절
- Ctrl+Shift+Up/Down: 벨로시티 편차 조절

### 5.7 확률 (Chance) 편집
- 개별 확률 마커 (0-100%)
- Randomization Amount 슬라이더
- Ctrl+Alt+Up/Down: 확률 조절
- **확률 그룹**:
  - **Play All**: 그룹 내 모든 노트 트리거
  - **Play One**: 그룹에서 랜덤으로 하나만 트리거
- 그룹 생성 (Ctrl+G) / 해제 (Ctrl+Shift+G)

### 5.8 노트 스트레치 마커
- 다중 노트 선택 시 scrub area 아래에 표시
- 마커 수평 드래그: 원본 길이 비례로 스트레치
- 고정 마커 사이의 의사(pseudo) 스트레치 마커: 내부 콘텐츠 독립 압축/스트레치

### 5.9 퀀타이제이션
1. 녹음 중 실시간 퀀타이제이션
2. 그리드 스냅 이동
3. Transform 패널의 "Quantize MIDI Tool": Amount 퍼센트로 세밀 제어
4. Edit 메뉴 Quantize 명령 (Ctrl+U), 설정 (Ctrl+Shift+U)

### 5.10 멀티 클립 편집
- 최대 8개 클립 동시 보기 및 편집
- **Focus Mode**: 여러 클립 보기 중 단일 클립 선택 편집
- 루프 바로 각 클립 표현
- Ctrl/Cmd 수정자로 독립 또는 공동 편집

### 5.11 폴딩 및 스케일
- **Fold to Notes**: 빈 키 트랙 숨기기
- **Fold to Scale**: 스케일 도수 트랙만 표시
- Piano Ruler에서 스케일 하이라이트
- 노트 표기 환경설정: 플랫(b), 샤프(#), 자동
- K 키: 스케일 하이라이트 토글

### 5.12 탐색
- Time/Note Ruler에서 줌
- Page Up/Down: 옥타브 스크롤
- +/-: 줌
- Z: 선택 영역 전체 줌, X: 이전 줌 복원
- W: 콘텐츠 너비에 맞춤, H: 콘텐츠 높이에 맞춤
- 더블 클릭 ruler: 선택 영역 자동 줌

---

## 6. Audio Editor (오디오 에디터)

### 6.1 Sample Editor
- 파형 시각화 (좌/우 채널 또는 모노)
- 클립 영역: Start Marker, End Marker
- 줌 및 스크롤

### 6.2 워프 마커 편집
- 더블 클릭으로 워프 마커 생성
- Ctrl+I: 워프 마커 삽입
- Delete: 워프 마커 삭제
- 방향키로 선택된 워프 마커 이동
- Ctrl+방향키로 워프 마커 선택 전환
- Pseudo-Warp Markers: 트랜지언트에 자동 표시, 실제 마커로 변환 가능

### 6.3 트랜지언트 편집
- Ctrl+Shift+I: 트랜지언트 삽입
- Ctrl+Shift+Delete: 트랜지언트 삭제
- 트랜지언트 기반 슬라이싱

### 6.4 Envelope Editor
- 오토메이션 엔벨로프 편집
- Sample/Envelope 탭 전환

### 6.5 오디오 클립 퀀타이제이션
- Quantize 도구: 그리드 크기 또는 미터 값 선택
- Amount 컨트롤: 워프 마커 이동 비율

---

## 7. Instruments (내장 악기)

### 7.1 Analog
- **유형**: 가상 아날로그 신시사이저 (Physical Modeling 기반, Applied Acoustics Systems 협업)
- **오실레이터**: 2개 오실레이터 + 노이즈 제너레이터
- **필터**: 듀얼 멀티모드 필터
- **앰프**: 앰프리파이어 + 엔벨로프
- **모듈레이션**: 2개 LFO, Vibrato, Unison, Glide
- **MPE 지원**

### 7.2 Bass
- **유형**: 모노포닉 가상 아날로그 베이스 신시사이저
- 베이스 사운드에 최적화된 단순 인터페이스

### 7.3 Collision
- **유형**: 말렛 타악기 물리적 모델링 신시사이저
- **세션**: Mallet 세션 + Noise 세션
- **레조네이터**: 듀얼 스테레오 레조네이터
- **레조넌스 유형**: Beam, Marimba, String, Membrane, Plate, Pipe, Tube
- **모듈레이션**: LFO, MIDI/MPE 컨트롤

### 7.4 Drift
- **유형**: 서브트랙티브 신시사이저 (직관적, 낮은 CPU)
- **오실레이터**: 듀얼 오실레이터
- **필터**: 다이나믹 필터
- **엔벨로프**: 2개
- **LFO**: 1개
- **모듈레이션 매트릭스**
- **보이스 모드**: Poly, Mono, Stereo, Unison (4종)
- **MPE 지원**

### 7.5 Drum Sampler
- **유형**: 원샷 샘플 재생 악기 (드럼 랙용)
- **샘플 조작**: Start, Length, Gain
- **엔벨로프**: AHD (Attack-Hold-Decay)
- **피치 컨트롤**
- **필터 섹션**
- **9가지 재생 이펙트**: Stretch, Loop, Pitch Env, Punch, 8-bit, FM, Ring Mod, Sub Osc, Noise
- **모듈레이션 옵션**

### 7.6 Drum Synths (Max for Live)
- **DS Kick**: 서브 오실레이터, 튜닝(Hz), Attack, Click 토글
- **DS Snare**: Color, Tone, Decay, Tune 파라미터
- **DS Clap**: Tone, Tune, Decay, Tail, Sloppy, Spread 컨트롤
- **DS HH (Hi-Hat)**: 하이햇 합성
- **DS Tom**: 톰 합성
- **DS Clang**: 클랭 합성
- **DS Cymbal**: 심벌 합성
- **DS FM**: FM 기반 드럼 합성

### 7.7 Electric
- **유형**: 물리적 모델링 일렉트릭 피아노 (1970년대 악기 기반)
- **모델링 요소**: Hammer, Fork (Tine + Tone), Pickup, Damper
- **파라미터**: Stiffness, Noise, Color, Decay

### 7.8 External Instrument
- **유형**: 하드웨어 신시사이저 및 멀티팀브랄 플러그인 라우팅 유틸리티
- MIDI 출력 전송, 오디오 반환
- 하드웨어 레이턴시 보상
- 게인 조절

### 7.9 Granulator III (Max for Live)
- **유형**: 그래뉼러 샘플러/신시사이저 (Robert Henke 제작)
- **3가지 재생 모드**:
  - Classic Mode: Granulator II와 동일
  - Loop Mode: 리드미컬 콘텐츠 작업
  - Cloud Mode: 드론 및 실험적 텍스처
- **MPE 지원**: 그레인 크기, 형태, 위치 등 익스프레시브 컨트롤
- **모듈레이션 매트릭스**
- **실시간 캡처**: 외부 디바이스 없이 오디오 소스 직접 녹음
- **모노포닉 모드**

### 7.10 Impulse
- **유형**: 8슬롯 드럼 샘플러
- **복잡한 모듈레이션**: 샘플 스트레칭, 멀티모드 필터, 새츄레이터
- **엔벨로프**: Trigger/Gate 모드
- **컨트롤**: Pan, Volume (슬롯별)
- **개별 슬롯 출력**

### 7.11 Meld
- **유형**: 바이팀브랄 매크로 오실레이터 신시사이저
- **듀얼 엔진**: 독립적 합성 기법 결합
- **전용 필터**, 엔벨로프, LFO
- **모듈레이션 매트릭스**
- **매크로 노브**: 오버톤 모듈레이션 및 특수 이펙트 컨트롤
- **MPE 지원**
- 텍스처, 하모닉/비조성 사운드, 리드미컬 드론에 적합

### 7.12 Operator
- **유형**: FM + 서브트랙티브 + 애디티브 신시사이저
- **오실레이터**: 4개 멀티 웨이브폼 오실레이터 (주파수 변조)
- **웨이브폼**: Sine, Sawtooth, Square, Triangle, Noise + 커스텀 (파셜 에디터)
- **알고리즘**: 11개 사전 정의 알고리즘 (오실레이터 연결 방식)
- **엔벨로프**: 7개 별도 엔벨로프 (오실레이터 4개 + Filter + Pitch + LFO)
- **필터 섹션**
- **LFO**
- **글로벌 컨트롤**
- **최대 보이스**: 32

### 7.13 Poli
- **유형**: 폴리포닉 신시사이저
- Suite 에디션 전용

### 7.14 Sampler
- **유형**: 고급 멀티샘플링 악기
- **무제한 샘플 존 관리**
- **4가지 존 유형**: Key, Velocity, Sample Select, Chain
- **그래피컬 존 에디터**: 키/벨로시티 범위, 크로스페이드
- **심층 모듈레이션 라우팅**
- **고급 필터 옵션**
- **서드파티 포맷 임포트**: EXS24, Kontakt, Aiki
- **Simpler ↔ Sampler 변환** (컨텍스트 메뉴)

### 7.15 Simpler
- **유형**: 단일 샘플 기반 간소화 악기
- **3가지 모드**:
  - **Classic**: 표준 샘플 재생 (폴리포닉/모노포닉)
  - **One-Shot**: 원샷 재생 (드럼/이펙트)
  - **Slicing**: 샘플 자동 분할 후 MIDI 노트에 매핑
    - 비트 해상도, 트랜지언트, 워프 마커 기준 슬라이싱
    - 최대 128 슬라이스
- **이펙트**: 엔벨로프, 필터, LFO
- **Simpler ↔ Sampler 변환**

### 7.16 Tension
- **유형**: 스트링 물리적 모델링 신시사이저
- 현악기 사운드 합성

### 7.17 Wavetable
- **유형**: 웨이브테이블 신시사이저
- **오실레이터**: 2개 메인 오실레이터 + Sub Oscillator
- **오실레이터 이펙트**: FM, Classic, Modern (각 2개 파라미터)
- **필터**: 2개 동일 멀티모드 필터
- **시그널 패스**: Serial, Parallel, Split (3가지)
- **모듈레이션 매트릭스**: 3개 엔벨로프, 2개 LFO, MIDI 소스
- **거의 모든 컨트롤이 모듈레이션 타깃으로 설정 가능**

### 7.18 CV Instrument
- **유형**: CV/Gate 출력 장치 (모듈러 신시 연동)

### 7.19 CV Triggers
- **유형**: CV 트리거 출력 장치 (모듈러 신시 연동)

### 7.20 Instrument Rack
- 악기 + MIDI/오디오 이펙트 조합 컨테이너
- (상세 내용은 Racks 섹션 참조)

### 7.21 Drum Rack
- 드럼 패드 기반 악기 컨테이너
- (상세 내용은 Racks 섹션 참조)

---

## 8. Audio Effects (오디오 이펙트)

### 8.1 다이나믹스

#### Compressor
- 사용자 설정 임계값 이상 신호의 게인 감소
- Ratio, Attack, Release, Knee 컨트롤
- Sidechain 입력 지원

#### Color Limiter (Suite)
- 향상된 리미터, 부드러운 릴리즈
- 업데이트된 미터링
- Mid/Side 라우팅

#### Gate
- 임계값 이하 신호 차단
- Sidechain 입력 지원

#### Glue Compressor (Standard+)
- 버스 컴프레서 에뮬레이션
- Soft Clip 기능

#### Limiter
- 하드 리미팅
- Lookahead, Release 컨트롤

#### Multiband Dynamics (Standard+)
- 멀티밴드 컴프레서/익스팬더/게이트
- 3밴드 크로스오버

#### Drum Buss (Standard+)
- 아날로그 스타일 드럼 프로세서
- 컴프레션 + 디스토션 + 로우엔드 강화

#### Re-Enveloper (Suite)
- 엔벨로프 리셰이핑 이펙트

### 8.2 EQ 및 필터

#### Auto Filter
- 주파수 선택적 필터링
- **10가지 필터 유형** (Comb, Vowel, Resampling, Notch+LP 등 새 필터 포함)
- LFO/엔벨로프 모듈레이션
- 실시간 시각화

#### Channel EQ
- 3밴드 EQ (클래식 믹싱 데스크 영감)
- Low, Mid, High 파라미터 + 하이패스 필터

#### EQ Three
- 3밴드 DJ 스타일 EQ
- 각 밴드별 킬 스위치

#### EQ Eight (Standard+)
- 8밴드 파라메트릭 EQ
- 다양한 필터 타입
- 스펙트럼 분석기 표시

### 8.3 딜레이 / 에코

#### Delay
- 2개 독립 딜레이 라인 (좌/우 채널)
- Sync, Feedback, Transition Mode 옵션

#### Echo (Suite)
- 모듈레이션 딜레이 이펙트
- 독립 딜레이 라인
- 엔벨로프/필터 모듈레이션

#### Filter Delay (Standard+)
- 3개 독립 딜레이 라인 + 필터

#### Grain Delay
- 그래뉼러 딜레이
- Pitch, Spray, 랜덤 파라미터

#### Gated Delay (Suite)
- 게이트가 적용된 딜레이

#### Align Delay (Standard+)
- Time, Samples, Distance 모드
- 멀티마이크 정렬용

### 8.4 리버브

#### Reverb
- 알고리즘 리버브
- Room, Decay, Diffusion 파라미터

#### Convolution Reverb (Suite)
- 임펄스 응답 기반 리버브
- 실제 공간 에뮬레이션

#### Hybrid Reverb (Suite)
- 알고리즘 + 컨볼루션 하이브리드

### 8.5 디스토션 / 새츄레이션

#### Saturator
- 다양한 새츄레이션 커브
- Bass Shaper 커브 (Live 12 신규)

#### Roar (Suite, Live 12 신규)
- 3단계 새츄레이션 스테이지
- Series, Parallel, Mid/Side, Multiband 구성
- 피드백 제너레이터
- 모듈레이션 매트릭스

#### Overdrive (Standard+)
- 오버드라이브 디스토션

#### Dynamic Tube (Standard+)
- 튜브 새츄레이션 에뮬레이션
- 엔벨로프 팔로워 + 3가지 튜브 모델

#### Vinyl Distortion (Standard+)
- 바이닐 레코드 특성 에뮬레이션
- Tracing, Pinch, Crackle 모드

#### Pedal (Suite)
- 기타 이펙트 페달 에뮬레이션

#### Redux
- 비트크러셔 / 다운샘플링
- 비트 감소 및 샘플레이트 감소

#### Erosion
- 노이즈/사인/와이드 노이즈로 신호 침식

### 8.6 모듈레이션

#### Chorus-Ensemble
- 클래식 2-딜레이 라인 코러스 + 옵션 3번째 딜레이
- Classic, Ensemble, Vibrato 모드

#### Phaser-Flanger
- 페이저/플랜저 콤비네이션

#### Auto Pan-Tremolo
- LFO 기반 스테레오 위치/진폭 모듈레이션
- Panning 또는 Tremolo 모드

#### Shifter (Standard+)
- 피치 시프팅 이펙트

#### Auto Shift (Live 12 신규)
- 실시간 피치 추적 및 보정
- 하모나이제이션, 비브라토
- 포먼트 시프팅

### 8.7 스펙트럴 이펙트

#### Spectral Blur (Suite)
- 스펙트럴 블러링

#### Spectral Resonator (Suite)
- 스펙트럴 레조넌스

#### Spectral Time (Suite)
- 스펙트럴 시간 조작

### 8.8 피치

#### Pitch Hack (Suite)
- 피치 해킹 이펙트

#### PitchLoop89 (Suite)
- 피치 루핑 이펙트

#### Tuner
- 크로매틱 튜너 (시각적 피치 감지)

### 8.9 리피트 / 루프

#### Beat Repeat
- 제어/랜덤 반복
- Grid, Variation 컨트롤

#### Looper
- 실시간 루핑 이펙트
- 오버더빙, 반전, 속도 변경

### 8.10 앰프 시뮬레이션

#### Amp (Suite)
- 7가지 클래식 기타 앰프 에뮬레이션
- Gain, Volume, EQ, Presence

#### Cabinet (Suite)
- 5가지 클래식 기타 캐비닛 에뮬레이션
- 스피커 및 마이크 선택

### 8.11 유틸리티

#### Utility
- 게인, 패닝, 위상 반전
- 채널 스왑, 모노/스테레오 변환

#### Spectrum (Standard+)
- 실시간 스펙트럼 분석기

#### Resonators (Standard+)
- 5개 병렬 레조네이터

#### Corpus (Suite)
- 7종 공명 물체의 음향 특성 시뮬레이션 (물리적 모델링)

#### Vocoder (Standard+)
- 보코더 이펙트
- 포먼트 컨트롤, 노이즈 오실레이터

### 8.12 CV 도구 (Suite)

#### CV Clock In / CV Clock Out
- 모듈러 시스템과 클럭 동기화

#### CV Envelope Follower
- CV 엔벨로프 팔로워

#### CV In
- CV 입력 수신

#### CV LFO
- CV LFO 출력

#### CV Shaper
- CV 셰이핑

#### CV Utility
- CV 유틸리티

### 8.13 서라운드

#### Surround Panner (Suite)
- 서라운드 사운드 패닝

### 8.14 라우팅

#### Audio Effect Rack
- 오디오 이펙트 컨테이너 (상세 내용은 Racks 섹션 참조)

#### External Audio Effect (Standard+)
- 하드웨어 이펙트 통합
- 오디오 전송/수신 + 레이턴시 보상

---

## 9. MIDI Effects (MIDI 이펙트)

### 9.1 Arpeggiator
- 코드/노트 입력에서 리드미컬 패턴 생성
- **Style**: Up, Down, Converge, Diverge, Play Order, Chord Trigger, Random 및 변형
- **Rate**: 패턴 속도
- **Distance**: 트랜스포즈 거리
- **Steps**: 트랜스포즈 스텝 수
- **Gate**: 노트 길이 조절
- **Hold**: 유지 기능
- **Pattern Offset**
- **Groove**: 그루브 적용
- **Retrigger**: 리트리거 옵션
- **Repeats**: 반복 횟수
- **Velocity**: Decay, Target 설정

### 9.2 CC Control
- MIDI CC 메시지 전송 (하드웨어 디바이스용)
- 3개 고정 노브 (Mod Wheel, Pitch Bend, Pressure)
- 1개 커스텀 버튼 (Custom A)
- 12개 커스텀 다이얼 (Custom B-M)
- Learn 토글: 수신 MIDI 소스 매핑

### 9.3 Chord
- 수신 노트에서 코드 생성 (최대 6개 추가 피치)
- **Shift 1-6**: ±36 반음 범위
- **Velocity/Chance 토글**
- **Strum**: 최대 400ms 딜레이
- **Tension**, **Crescendo** 조절
- **Learn 모드**: 코드 할당 직접 연주

### 9.4 MIDI Effect Rack
- MIDI 이펙트 컨테이너 (MIDI 트랙 전용)

### 9.5 MIDI Monitor
- MIDI 데이터 모니터링 도구

### 9.6 MPE Control
- MPE (MIDI Polyphonic Expression) 제어 장치

### 9.7 Note Echo (Standard+)
- MIDI 노트 에코/딜레이

### 9.8 Note Length
- MIDI 노트 길이 변경
- Trigger Source 토글 (Note On/Off)
- Gate, Length 컨트롤
- Release Velocity, Decay Time
- Key Scale, Latch 토글

### 9.9 Pitch
- ±128 반음 또는 ±30 스케일 도수 트랜스포즈
- Step Up/Down 버튼
- Step Width 슬라이더
- Lowest, Range 컨트롤
- Mode: Block, Fold, Limit (범위 초과 처리)

### 9.10 Random
- 수신 노트 피치 랜덤화
- **Chance**: 드라이/웻 비율
- **Choices**: 1-24 피치
- **Interval**: 간격
- **Mode**: Random/Alt
- **Sign**: Add/Sub/Bi
- LED 피드백 표시

### 9.11 Rotating Rhythm Generator
- 회전 리듬 생성기

### 9.12 Scale
- 정의된 스케일에 따른 노트 리매핑
- **13x13 Note Matrix**
- **Base**, **Scale Name** 선택기
- **User 스케일 생성**
- **Transpose**: ±36 반음
- **Fold 스위치**
- **Lowest/Range**: 선택적 리매핑

### 9.13 Velocity
- MIDI 벨로시티 값 리매핑
- **Velocity Curve 그리드**
- **Operation**: Note On/Off/both
- **Mode**: Clip/Gate/Fixed
- **Random 모듈레이션**
- **Drive, Compand**: 커브 조작

### 9.14 Melodic Steps (Suite)
- 멜로딕 스텝 시퀀서

---

## 10. MIDI Tools (MIDI 도구)

### 10.1 Transformation Tools (변환 도구)

#### Arpeggiate
- 노트를 아르페지오 시퀀스로 분할
- **Style**: 18가지 아르페지에이션 패턴
- **Distance**: 스케일 도수/반음 트랜스포즈
- **Steps**: 트랜스포즈 스텝 수
- **Rate**: 패턴 템포 및 노트 길이
- **Gate**: 노트 길이 조절 (100% 기준)

#### Chop
- 선택된 노트를 2-64개 부분으로 분할
- **Parts**: 분할 수
- **Gaps**: 패턴 내 간격
- **Pattern Toggles**: 수동 갭 추가/제거
- **Emphasis Toggles**: 강조 요소 선택
- **Stretch Chunk(s)**: 강조 요소 2-8배 확장
- **Variation**: 랜덤 타이밍 조절

#### Connect
- 노트 간 갭을 보간된 피치로 채움
- **Spread**: 최대 랜덤 피치 시프트 범위
- **Density**: 갭 채움 비율
- **Rate**: 생성 노트 길이
- **Tie**: 노트 연장 확률

#### Glissando (MPE)
- 연속 노트를 잇는 피치 벤드 커브 생성
- **Start**: 커브 시작 위치 (%)
- **Curve**: 시각적 브레이크포인트 편집

#### LFO (MPE)
- 저주파 오실레이터로 MPE 파라미터 모듈레이션
- **Target**: Pitch Bend, Slide, Pressure
- **Shape**: Sine, Square, Triangle, Random
- **Attack/Decay**: 엔벨로프 타이밍
- **Rate**: 주기 (1 ~ 1/128)
- **Time Shift, Amount, Amplitude Base**

#### Ornament
- 노트 시작에 플램/그레이스 노트 추가
- **Flam Mode**: Position, Velocity
- **Grace Notes Mode**: Pitch (High/Low/Same), Position, Velocity, Chance, Amount

#### Quantize
- 노트를 그리드 위치로 이동/스트레치
- **Grid Size 또는 Meter**: 퀀타이제이션 세분화
- **Quantize Start/End**: 타이밍 또는 길이 조절
- **Amount**: 퀀타이제이션 적용 비율 (%)

#### Recombine
- 선택 영역 내 노트 파라미터 재배열
- **Dimension**: Position, Pitch, Duration, Velocity
- **Shuffle Toggle**: 랜덤 순열
- **Mirror Toggle**: 역순
- **Rotation Steps**: 순환 오프셋
- **Rotate on Grid Toggle**: 그리드 셀 기준 회전

#### Span
- 아티큘레이션 유형으로 노트 길이 변환
- **Legato**: 다음 노트 시작까지 연장
- **Tenuto**: 원래 길이 유지
- **Staccato**: 노트 시작 간 거리 사용
- **Offset**: 그리드 스텝 조절
- **Variation**: 랜덤 길이 변형

#### Strum
- 코드 노트 시작 시간을 스트럼 패턴으로 조절
- **Strum Low**: 최저 노트 오프셋
- **Strum High**: 최고 노트 오프셋
- **Tension**: 지수 커브 분포

#### Time Warp
- 속도 커브를 사용한 노트 시간 스트레칭
- **Breakpoints**: 1-3개 조절 가능 포인트
- **Breakpoint Time/Speed**: 각 포인트의 위치 및 속도
- **Quantize Toggle**: 워핑된 노트 그리드 맞춤
- **Preserve Time Range**: 원래 선택 범위 유지
- **Include Note End**: 노트 끝 위치 고려

#### Velocity Shaper (Max for Live)
- 조절 가능한 엔벨로프로 벨로시티 셰이핑
- **Envelope Display**: 브레이크포인트 편집
- **Min/Max Velocity**: 벨로시티 범위
- **Loop**: 엔벨로프 반복 횟수
- **Rotate**: 오프셋
- **Division**: 회전 스텝 크기

### 10.2 Generative Tools (생성 도구)

#### Rhythm
- 시간 선택 내 반복 노트 패턴 생성
- **Pitch**: 타깃 피치/드럼 패드
- **Steps**: 1-16 패턴 스텝
- **Pattern**: 노트 배치 형태
- **Density**: 패턴 내 노트 수
- **Step Duration**: 패턴 반복 빈도
- **Split**: 스텝 반으로 나눌 확률
- **Shift**: 패턴 오프셋
- **Velocity, Accent**: 노트 벨로시티 및 악센트
- **Accent Frequency/Offset**: 악센트 간격 및 배치

#### Seed
- 지정 범위 내 랜덤 노트 생성
- **Pitch Range**: Min/Max 피치
- **Duration Range**: 노트 길이 범위 (1/128 ~ 1 note)
- **Velocity Range**: 1-127
- **Voices**: 최대 동시 노트 수
- **Density**: 피치 범위 대비 생성 비율

#### Shape
- 정의된 형태를 따르는 시퀀스 생성
- **Shape Presets**: 사전 정의 또는 커스텀 드로잉
- **Min/Max Pitch**: 노트 범위
- **Rate**: 최소 생성 노트 길이
- **Tie**: 노트 연장 확률
- **Density**: 형태 채움 비율
- **Jitter**: 피치 랜덤화 (0-100%)

#### Stacks
- 활성 스케일 내 코드 진행 생성
- **Chord Selector Pad**: Tonnetz 기반 코드 패턴 선택
- **Custom Chord Banks**: .stacks JSON 파일
- **Add/Delete Chord**: 진행 빌드 컨트롤
- **Chord Root**: 루트 노트 (스케일 제한)
- **Chord Inversion**: 전위 (양수: 높은 옥타브, 음수: 낮은 옥타브)
- **Chord Duration/Offset**: 길이 및 위치 (8분음표 단위)

#### Euclidean Generator (Max for Live)
- 유클리드 리듬 패턴 생성 (최대 4 보이스)
- **Pattern Tab**: Voice Toggles, Rotation Sliders, Randomization
- **Voices Tab**: Pitch/Drum Pad Selection, Velocity Sliders
- **Steps, Density, Division** 파라미터

### 10.3 공통 특성
- 네이티브 MIDI Tools는 편집 불가
- Max for Live 도구 (Velocity Shaper, Euclidean)는 커스터마이즈 가능
- 클립 스케일 설정 존중 (활성 시 스케일 도수 사용)
- MPE 도구 (Glissando, LFO)는 전용 Expression Lane에 표시
- Ctrl+Enter로 현재 MIDI Tool 설정 적용

---

## 11. Modulators (모듈레이터)

### 11.1 Expression Control
- MIDI 익스프레션 데이터를 파라미터에 매핑

### 11.2 LFO
- 저주파 오실레이터 모듈레이션
- 다양한 웨이브폼, Rate, Amount 컨트롤

### 11.3 Envelope Follower
- 오디오 신호의 엔벨로프를 추적하여 파라미터 모듈레이션

### 11.4 Envelope MIDI
- MIDI 입력 기반 엔벨로프 모듈레이션

### 11.5 Shaper
- 커스텀 셰이프 기반 모듈레이션

### 11.6 Shaper MIDI
- MIDI 기반 셰이퍼 모듈레이션

---

## 12. Mixer (믹서)

### 12.1 트랙별 컨트롤
- **미터 (Meter)**: 피크 및 RMS 출력 레벨 표시, 모니터링 시 입력 레벨 표시
- **볼륨 컨트롤**: 트랙 출력 레벨 조절, 다중 선택 시 동시 조절
- **팬 컨트롤**:
  - Stereo Pan Mode: 스테레오 필드 내 위치
  - Split Stereo Pan Mode: 좌/우 채널 개별 조절
- **Track Activator**: 트랙 출력 온/오프 (뮤트)
- **Solo 스위치**: 선택 트랙 솔로, 다른 트랙 뮤트
- **Arm Recording 버튼**: 녹음 활성화

### 12.2 확장 믹서 표시
- 믹서 상단 드래그로 미터 높이 확장
- 눈금 표시, 숫자 볼륨 필드, 리셋 가능한 피크 인디케이터
- 트랙 너비 증가 시 데시벨 스케일 추가

### 12.3 그룹 트랙
- 여러 트랙을 서밍 컨테이너로 조합
- 클립 호스팅 불가
- 포함된 트랙의 출력 자동 라우팅 (커스텀 라우팅 없을 경우)

### 12.4 리턴 트랙
- Send 컨트롤로 여러 트랙의 오디오 처리
- 피드백 라우팅 가능 (자기 입력으로 출력 라우팅)

### 12.5 메인 트랙 (Master)
- 모든 트랙 신호의 기본 도착지
- 마스터링 이펙트 호스팅

### 12.6 센드 컨트롤
- 트랙 출력을 리턴 트랙으로 보내는 양 결정
- **Pre/Post 토글**: 믹서 스테이지 전/후 탭 결정

### 12.7 크로스페이더
- 7가지 크로스페이드 커브
- 트랙별 A/B 할당 버튼
- 페이더 위치에 따른 트랙 감쇠

### 12.8 솔로 및 큐잉

#### Standard Solo
- 다른 트랙 뮤트, 솔로 트랙 패닝 유지

#### Solo in Place
- 솔로 시 리턴 트랙 가청 유지 (옵션)

#### Cueing
- 4개 이상 전용 출력 필요
- Cue Out, Cue Volume 컨트롤
- 별도 헤드폰 모니터링

### 12.9 트랙 딜레이
- 트랙별 밀리초 단위 딜레이 보상
- 인간, 음향, 하드웨어 레이턴시 보상
- 디바이스 딜레이 보상 비활성화 시 사용 불가

### 12.10 모니터링 레이턴시
- "Keep Monitoring Latency in Recording": 녹음 타이밍을 들리는 모니터링에 맞춤
- "In" 또는 "Auto" 모니터링 모드에서 기본 활성화

### 12.11 성능 표시기
- 트랙별 CPU 미터: 6개 사각형이 CPU 영향에 비례하여 점등

### 12.12 Arrangement View 믹서
- Live 12에서 Arrangement View에서도 믹서 접근 가능 (이전 Session View 한정)
- 향상된 비주얼

---

## 13. Browser (브라우저)

### 13.1 기본 구조
- 악기, 이펙트, 샘플, 프리셋, Pack, 커스텀 콘텐츠 접근
- Ctrl+Alt+B로 표시/숨기기

### 13.2 카테고리
- **Sounds**: 악기 프리셋
- **Drums**: 드럼 랙 프리셋
- **Audio Effects**: 오디오 이펙트 프리셋
- **MIDI Effects**: MIDI 이펙트 프리셋
- **Modulators**: 모듈레이터
- **Max for Live**: Max for Live 디바이스
- **Plug-Ins**: VST/AU 플러그인
- **Clips**: 클립 프리셋
- **Samples**: 오디오 샘플
- **Grooves**: 그루브 파일
- **Templates**: 템플릿
- **All Results**: 통합 검색 결과
- **Packs**: 설치된 팩
- **User Library**: 사용자 라이브러리
- **Current Project**: 현재 프로젝트 파일

### 13.3 Collections (컬렉션)
- 최대 7개 색상 코딩된 커스터마이즈 가능 카테고리
- 즐겨찾기 항목 빠른 접근
- 1-7 키로 색상 할당, 0 키로 리셋

### 13.4 검색
- Ctrl+F: 브라우저 내 검색
- 검색 결과로 방향키/Enter로 이동

### 13.5 태깅 시스템 (Live 12 신규)
- **Factory Tags**: 사전 정의된 태그
- **User Tagging**: 사용자 정의 태그
- **Auto Tagging**: 60초 미만 샘플 자동 태깅
- **Custom Browser Labels**: 커스텀 라벨
- **Tag Editor**: Ctrl+Shift+E로 표시/숨기기
- **Filter View**: 필터 그룹 표시/숨기기 (Ctrl+Alt+G)
- **Quick Tags 패널**

### 13.6 Sound Similarity (사운드 유사성, Live 12 신규)
- ML 기반 프리셋/샘플 발견
- Ctrl+Shift+F: 유사한 파일 표시
- **Similar Sample Swapping**:
  - Ctrl+Right/Left: 다음/이전 유사 샘플 스왑
  - Ctrl+Up: 유사성 참조로 저장
  - Ctrl+Down: 참조로 복귀
  - Alt: 유사 샘플 스왑 컨트롤 토글

### 13.7 브라우저 히스토리 (Live 12 신규)
- Ctrl+[: 뒤로
- Ctrl+]: 앞으로

### 13.8 미리보기
- Shift+Enter 또는 Right: 선택 파일 미리듣기

### 13.9 드럼 랙 스와핑
- 유사한 대안으로 샘플 교체

### 13.10 Splice 통합
- Live 내에서 직접 Splice 샘플 탐색 및 오디션
- Search with Sound: 프로젝트 오디오 캡처로 유사 샘플 검색

### 13.11 드래그 앤 드롭
- 브라우저에서 트랙/디바이스/클립 슬롯으로 드래그
- Ctrl+드래그: 씬으로 드롭
- Enter: 선택 항목 로드

---

## 14. Transport (트랜스포트)

### 14.1 Control Bar 컨트롤
- **Play/Stop (Space)**: 시작/정지
- **Shift+Space**: 정지 지점에서 재생 계속
- **Record (F9)**: 녹음 시작
- **Shift+F9**: Arrangement 녹음 Arm
- **Arrangement Loop 토글 (Ctrl+L)**
- **Arrangement Position 필드**: 숫자 재생 위치
- **Tempo 필드**: BPM 설정
- **Time Signature 필드**: 박자표
- **Global Quantization**: 글로벌 퀀타이제이션 값
  - Ctrl+6: 16분음표
  - Ctrl+7: 8분음표
  - Ctrl+8: 4분음표
  - Ctrl+9: 1마디
  - Ctrl+0: 퀀타이제이션 꺼짐

### 14.2 메트로놈
- O 키로 토글
- 믹서의 Preview Volume 노브로 볼륨 조절
- 비트 디비전 리듬 설정 커스터마이즈

### 14.3 카운트인
- None 이외의 값 설정 시 녹음 전 카운트인
- 카운트 값은 Control Bar 위치 필드에 파란색 표시
- Link 활성화 시 사용 불가

### 14.4 Punch-In/Out
- 지정 영역 밖 녹음 방지
- Punch-In: Arrangement Loop 시작 위치
- Punch-Out: Arrangement Loop 끝 위치

### 14.5 Tempo Following (Live 12 신규)
- 수신 오디오 신호의 템포를 실시간 분석
- "Follow" 버튼 (Control Bar)
- 명확한 리듬의 오디오에 최적화
- Link, Tempo Follower, External Sync는 상호 배타적

### 14.6 Tap Tempo
- 탭으로 템포 설정

### 14.7 오디오 엔진
- Ctrl+Alt+Shift+E: 오디오 엔진 온/오프

### 14.8 트랙 활성화
- F1-F8: 트랙 1-8 활성화/비활성화

---

## 15. Automation (오토메이션)

### 15.1 녹음

#### Arrangement View
- Automation Arm 버튼 활성화 후 녹음
- 자동화된 컨트롤에 LED 인디케이터 표시

#### Session View
- 트랙 Arm + Session Record 버튼
- "Session Automation Recording" 환경설정: 노트 녹음 없이 오토메이션만 오버더빙

### 15.2 녹음 모드
- **Touch Mode**: 마우스 버튼 해제 시 녹음 중지
- **Latch Mode**: MIDI 컨트롤러 사용 시 클립 루프 끝까지 계속 녹음

### 15.3 오토메이션 삭제 및 오버라이드
- 우클릭 > "Delete Automation": 모든 오토메이션 데이터 삭제
- 비녹음 중 컨트롤 값 변경: 수동 설정으로 "오버라이드"
- **Re-Enable Automation 버튼**: 모든 오버라이드된 오토메이션 재활성화

### 15.4 엔벨로프 그리기
- **Draw Mode (B)**: 그리드 너비에 맞는 스텝 생성
- **Shift+수직 드래그**: 미세 해상도 조절
- **Alt/Cmd+드래그**: 프리핸드 그리기 (그리드 바이패스)

### 15.5 브레이크포인트 편집
- Draw Mode 비활성 시 브레이크포인트 드래그 가능
- **라인 세그먼트 클릭**: 새 브레이크포인트 생성
- **더블 클릭**: 어디서든 브레이크포인트 추가
- **브레이크포인트 클릭**: 삭제
- **우클릭 브레이크포인트**: 정확한 값 편집 또는 특정 값에 추가
- **클릭+드래그**: 이동; 선택된 브레이크포인트 동시 이동
- **Shift+드래그**: 수평/수직 이동 제한
- **Alt/Cmd+세그먼트 드래그**: 커브 적용; 더블 클릭으로 직선 복원
- **Alt/Cmd+핸들 드래그**: 반대 방향으로 미러 이동

### 15.6 엔벨로프 스트레칭 및 스큐
- 시간 선택 주위에 핸들 표시
- **상/하 중앙 핸들**: 수직 스트레치
- **좌/우 중앙 핸들**: 수평 스트레치
- **코너 핸들**: 스큐
- **Shift 드래그**: 미세 조정

### 15.7 Simplify Envelope
- 시간 범위 선택 후 컨텍스트 메뉴 > "Simplify Envelope"
- 커브 형태 유지하면서 불필요한 브레이크포인트 제거

### 15.8 오토메이션 셰이프
- 시간 선택 영역 우클릭으로 사전 정의된 셰이프 삽입
- **상단 행**: Sine, Triangle, Sawtooth, Inverse Sawtooth, Square
- **하단 행**: Ramp 및 ADSR 셰이프

### 15.9 Lock Envelopes
- 옵션 메뉴 또는 Lock Envelopes 스위치
- 오토메이션을 곡 위치에 잠금 (클립이 아닌)
- 클립 이동 시 엔벨로프 위치 유지

### 15.10 템포 오토메이션
- Device Chooser에서 "Mixer" → "Song Tempo" 선택
- 표시 BPM 범위 조절 가능

### 15.11 편집 메뉴 명령
- Cut, Copy, Duplicate, Delete: 오토메이션 레인에서 선택된 엔벨로프에만 적용

### 15.12 키보드 단축키
- A: Automation Mode 토글
- F: 페이드 컨트롤 일시 토글

---

## 16. Routing (라우팅)

### 16.1 입력/출력 유형

#### 오디오 입력
- "Ext. In" 선택으로 외부 오디오 접근
- 개별 채널 선택기
- 시그널 미터 (존재 및 오버로드 감지)

#### MIDI 입력
- "All Ins": 모든 외부 MIDI 포트 병합
- "All Channels": 개별 포트 채널 결합
- 각 입력 채널 활동 미터

#### 오디오 출력
- "Ext. Out"으로 하드웨어 인터페이스 라우팅

#### MIDI 출력
- 외부 신시사이저/디바이스로 MIDI 전송
- 출력 포트 및 MIDI 채널 선택

### 16.2 내부 라우팅 지점 (3가지)
- **Pre FX**: 디바이스 체인 전 (이펙트 변경이 탭 신호에 영향 없음)
- **Post FX**: 디바이스 처리 후, 믹서 전
- **Post Mixer**: 페이더 및 팬 조절 포함 최종 트랙 출력
- Drum/Instrument Rack: 개별 체인 라우팅 지점 노출

### 16.3 모니터링 모드
- **Auto**: 트랙 armed 시 모니터링 활성, 클립 재생 시 억제
- **In**: 항상 모니터링 (arm/재생 상태 무관), 클립 출력 억제
- **Off**: 모니터링 완전 비활성화
- "Keep Monitoring Latency in Recorded Audio" 옵션

### 16.4 사이드체인 라우팅
- 사이드체인 입력 지원 이펙트 (보코더, 컴프레서 등)
- Output Type/Channel Chooser로 별도 트랙에서 신호 수신
- 디바이스 레벨 라우팅 컨트롤

### 16.5 리샘플링
- Main 출력을 개별 오디오 트랙으로 라우팅하여 실시간 녹음
- 캡처 중 녹음 트랙 출력 억제 (피드백 방지)
- 샘플은 Project 폴더 > Samples/Recorded에 저장

### 16.6 멀티트랙 라우팅 패턴

#### 서브믹싱
- 개별 트랙을 그룹/보조 트랙으로 출력

#### 악기 공유
- 여러 MIDI 트랙이 "Track In"으로 동일 악기에 피딩

#### 멀티팀브랄 설정
- MIDI 채널이 개별 악기 파트 주소 지정
- 별도 오디오 트랙이 이산 출력 탭

#### Post-Effects 녹음
- 기타/소스 트랙이 이펙트 처리
- 추가 녹음 트랙이 Post FX 신호 탭

### 16.7 CV 생성 및 수신
- Pitch, Control, Clock, Trigger CV 생성 또는 수신

---

## 17. Warping (워핑)

### 17.1 핵심 기능
- 오디오를 "탄성적"으로 처리: 피치 변경 없이 타임 스트레칭, 또는 반대로
- 다양한 BPM의 오디오 클립 쉽게 믹스/매치

### 17.2 워프 모드

#### Beats
- 리드미컬 소재 (드럼 루프 등) 최적화
- 트랜지언트 보존
- 루핑 옵션: Loop Off, Loop Forward, Loop Back-and-Forth
- 세그먼트 전환 엔벨로프 컨트롤

#### Tones
- 피치 있는 오디오 (보컬, 모노포닉 악기)
- 조절 가능한 그레인 크기

#### Texture
- 비멜로디 콘텐츠 (오케스트랄 패드, 노이즈, 드론)
- 그레인 크기 + Fluctuation 랜덤 파라미터

#### Re-Pitch
- 턴테이블 속도 변경처럼 재생 속도 조절
- 템포에 비례하여 피치 영향
- 트랜스포즈 컨트롤 비활성화

#### Complex
- 폴리포닉 소재 및 전체 곡에 적합
- 높은 CPU 비용

#### Complex Pro
- Complex보다 잠재적으로 높은 품질
- 포먼트 보존
- 엔벨로프 컨트롤

### 17.3 워프 마커
- 샘플의 특정 지점을 타임라인의 특정 위치에 잠금
- 더블 클릭으로 생성
- 마커 이동으로 타이밍 조절

### 17.4 템포 감지
- 자동 워핑: 오디오 분석 후 원본 템포 추정
- 초기 마커 자동 생성
- x2, /2 버튼: 2배/반감 템포 보정

### 17.5 고급 기능
- 멀티 클립 워핑: 선택된 여러 클립에 마커 변경 동시 적용
- Pseudo-Warp Markers: 트랜지언트에 자동 표시, 실제 마커로 변환
- 퀀타이제이션: 파형을 그리드에 스냅 (가장 가까운 트랜지언트 이동)
- **Lead/Follow 토글**: 클립이 Set 템포를 결정 (Follow가 아닌 Lead)

---

## 18. Sampling (샘플링)

### 18.1 Simpler 샘플링
- Classic Mode: 표준 폴리포닉/모노포닉 재생
- One-Shot Mode: 원샷 재생 (릴리즈 엔벨로프)
- Slicing Mode: 자동 분할 후 MIDI 매핑

### 18.2 Sampler 멀티샘플링
- 무제한 샘플 존
- Key Zone, Velocity Zone, Sample Select Zone, Chain Zone
- 크로스페이드 설정
- 서드파티 포맷 임포트 (EXS24, Kontakt, Aiki)

### 18.3 Drum Rack 샘플링
- 패드에 샘플 드래그: 자동 Simpler 생성
- 멀티 샘플 드롭: 크로매틱 매핑
- Alt/Cmd+드래그: 단일 패드에 레이어링

### 18.4 슬라이싱
- 비트 해상도, 트랜지언트, 워프 마커 기준
- 최대 128 슬라이스
- "Preserve warped timing" 옵션
- 커스텀 슬라이싱 프리셋

---

## 19. Recording (녹음)

### 19.1 오디오 녹음
- 설정된 입력 소스에서 새 클립으로 캡처
- 적절한 게인 스테이징 필요 (프리앰프/오디오 인터페이스)

### 19.2 MIDI 녹음
- 기본: 활성 외부 입력 디바이스의 모든 MIDI 수신
- 컴퓨터 키보드를 의사 MIDI 입력 장치로 활성화 가능 (M 키)

### 19.3 Session 녹음
- 글로벌 퀀타이제이션 설정 → 트랙 Arm → Session Record 클릭
- 즉시 루프 재생으로 전환: Session Record 다시 클릭

### 19.4 Arrangement 녹음
- Arrangement Record 버튼으로 시작
- "Start Playback with Record" 환경설정
- 모든 armed 트랙에 새 클립 생성
- Punch-In/Out 지원

### 19.5 오버더빙
- MIDI Arrangement Overdub 활성: 기존 MIDI와 새 입력 혼합
- Session에서 Session Record 토글로 레이어 패턴

### 19.6 MIDI Step Recording
- 트랜스포트 정지 상태에서 노트 입력
- 오른쪽 방향키: 그리드 설정에 따라 삽입 마커 이동

### 19.7 카운트인
- None 이외 값 설정 시 활성
- 카운트 완료 전까지 녹음 시작 안 함

### 19.8 메트로놈
- Control Bar 스위치로 활성화
- 재생 시작 시 틱
- Preview Volume 노브로 볼륨 조절
- 비트 디비전 리듬 커스터마이즈

### 19.9 Capture MIDI
- 녹음 버튼 누르지 않고 연주한 MIDI 사후 캡처
- Ctrl+Shift+C
- 새 Set에서 사용 시: 템포 자동 감지, 루프 경계 설정, 그리드 맞춤 배치

---

## 20. Comping (컴핑)

### 20.1 기본 개념
- 동일 트랙에 여러 퍼포먼스 녹음 후 최고의 부분 편집
- 오디오 및 MIDI 클립 모두 지원

### 20.2 테이크 레인
- Arrangement View에서 녹음 시 자동으로 take lane 추가
- 루프 녹음 시 각 패스마다 새 take lane
- 마지막 녹음 클립은 항상 main lane에 복사 (즉시 가청)
- 브라우저/파일 탐색기에서 take lane으로 샘플/MIDI 드래그 가능

### 20.3 컴핑 워크플로우
- Take Lane에서 영역 선택 (Draw Mode 사용)
- 선택 영역을 main lane에 포함
- Linked-track editing으로 동시 관리

### 20.4 키보드 단축키
- Ctrl+Alt+U: Take Lane 표시
- Enter: 선택된 Take Lane을 Main Track에 추가
- T: 선택된 Take Lane 오디션
- Shift+Alt+T: Take Lane 추가
- Ctrl+D: 선택된 Take Lane 복제
- Ctrl+Up/Down: Main Take를 다음/이전으로 교체

### 20.5 설정
- 각 테이크에 랜덤 색상 자동 할당 (Theme & Colors > Clip Color > Random)
- "Create Fades on Clip Edges" 활성화 시 인접 클립 간 4ms 크로스페이드 자동 생성

---

## 21. File Management (파일 관리)

### 21.1 Live Set 관리
- File > New Live Set (Ctrl+N)
- File > Open Live Set (Ctrl+O)
- File > Save Live Set (Ctrl+S)
- File > Save Live Set As (Ctrl+Shift+S)
- File > Save a Copy: 현재 작업 파일 변경 없이 복사

### 21.2 Live Project 관리
- Live Set 저장 시 자동 프로젝트 폴더 생성
- 클립, 샘플, 프리셋, 여러 Set 버전 함께 유지
- 고아 파일/깨진 참조 방지

### 21.3 템플릿
- File > Save Live Set As Default Set: 기본 템플릿 설정
- 사전 설정: 멀티채널 I/O, 디바이스, 키 매핑, MIDI 매핑
- File > Save Live Set As Template: 추가 템플릿 생성 (브라우저 Templates 카테고리에 표시)

### 21.4 병합 및 임포트
- 브라우저에서 Set을 다른 Set으로 드래그: 모든 트랙/클립/디바이스/오토메이션 재구성
- Set 펼치기로 개별 트랙 접근
- Session View 클립을 사용자 폴더로 드래그하여 새 Set으로 내보내기

### 21.5 내보내기 기능

#### 오디오/비디오 내보내기 (Ctrl+Shift+R)
- 특정 트랙 렌더링
- 이펙트 적용
- 모노 변환
- 노멀라이즈
- 샘플레이트 및 포맷 선택: WAV, AIFF, FLAC, MP3

#### MIDI 내보내기 (Ctrl+Shift+E)
- MIDI 클립을 Standard MIDI 파일로 내보내기

### 21.6 File Manager (파일 관리자)
- File > Manage Files
- **누락 파일 찾기**: 자동 또는 수동
- **외부 파일 수집**: 프로젝트 폴더로 복사
- **미사용 파일 식별**: 삭제용
- **프로젝트 패킹**: 압축된 .alp 형식

### 21.7 Collect All and Save
- 모든 외부 파일 참조를 프로젝트에 수집
- 프로젝트 이동 시 링크 깨짐 방지

### 21.8 Collect Files on Export
- 클립/프리셋/트랙 저장 시 파일 복사 제어
- Always (기본): 알림 없이 복사
- Ask: 대화상자 표시
- Never: 복사 안 함

---

## 22. Preferences / Settings (환경설정)

### 22.1 Display & Input (표시 및 입력)
- 언어 설정
- 줌 설정
- 키보드 탐색 옵션
- Outline View Focus
- 스크롤바 표시
- Arrangement/Clip Follow 동작
- UI 레이블
- Tab 탐색
- 방향키 기능
- 펜 태블릿 모드
- 경고 대화상자 복원

### 22.2 Theme & Colors (테마 및 색상)
- **테마**: Light/Dark 모드 (OS 설정 연동 가능)
- **톤**: Warm, Cool, Neutral
- **High Contrast**: 고대비 모드
- **Customization 탭**:
  - 그리드 라인 투명도
  - 밝기 레벨
  - 색상 강도 및 색조
- **자동 트랙 색상 할당**
- **Live 12 신규 테마**: Cool, Neutral, Warm, High-Contrast 옵션

### 22.3 Audio (오디오)
- 입력/출력 디바이스 설정
- 샘플레이트 설정
- 레이턴시 설정
- 오디오 인터페이스 캘리브레이션
- macOS 시스템 디바이스 매칭

### 22.4 Link, Tempo & MIDI
- **Ableton Link**: 네트워크 동기화 활성화
- **Tempo Follower**: 오디오 기반 템포 추적
- **MIDI Sync**: MIDI Clock/Timecode
- **MIDI 노트 라우팅**: 입/출력 포트 설정
- **Remote 인터페이스 컨트롤**: Control Surface 선택 (최대 6개)
- **MIDI 포트별 Track/Sync/Remote 활성화**

### 22.5 File & Folder (파일 및 폴더)
- 데이터 처리 설정
- 커스텀 Max for Live 경로
- Live 디코딩 캐시 설정

### 22.6 Library (라이브러리)
- 설치된 파일 기본 위치 지정 (Packs, User Library)
- Self-contained 파일 저장 옵션

### 22.7 Plug-Ins (플러그인)
- 플러그인 폴더 위치 설정
- 플러그인 창 표시 동작

### 22.8 Record, Warp & Launch (녹음, 워프 및 런치)
- 새 Live Set 기본 상태 커스터마이즈
- 새 녹음 옵션
- 기본 워프 모드
- 기본 런치 퀀타이제이션
- Create Fades on Clip Edges 옵션
- Start Playback with Record 옵션

### 22.9 Licenses & Updates (라이선스 및 업데이트)
- 인증 관리
- 자동 업데이트
- 사용 데이터 설정

---

## 23. Key / MIDI Mapping

### 23.1 MIDI Map Mode
- Ctrl+M: MIDI Map Mode 토글
- 활성화 시 매핑 가능 요소 파란색 하이라이트
- Mapping Browser 표시
- **매핑 프로세스**: 파라미터 클릭 → MIDI 컨트롤러 조작 → 매핑 등록
- Mapping Browser에서 모든 매핑 관리
- 매핑 삭제, 범위 조절 가능

### 23.2 Key Map Mode
- Ctrl+K: Key Map Mode 토글
- 활성화 시 매핑 가능 요소 빨간색 하이라이트
- 키보드 키를 Live 파라미터에 할당
- 스위치: 키로 상태 토글
- 라디오 버튼: 키로 옵션 순환

### 23.3 Computer MIDI Keyboard
- M 키: 컴퓨터 MIDI 키보드 활성화
- Z/X 키: 옥타브 범위 조절
- C/V 키: 수신 노트 벨로시티 조절

### 23.4 Macro Control 매핑
- Rack의 Macro Control에 디바이스 파라미터 매핑
- Map Mode 활성화 → 색상 오버레이 → 파라미터 선택 → Macro에 할당
- Min/Max 슬라이더로 값 범위 조절
- 반전 매핑 가능

### 23.5 MIDI 컨트롤러 설정
- Settings > Link, Tempo & MIDI
- 입력 포트: Track, Remote 활성화
- 출력 포트: Remote 활성화

---

## 24. Grooves (그루브)

### 24.1 기본 개념
- 클립 타이밍과 "느낌" 수정
- 오디오 (워핑 필요) 및 MIDI 클립 모두 적용
- .agr 파일 형식

### 24.2 그루브 적용
- 브라우저에서 클립으로 드래그 앤 드롭
- Hot-Swap Mode: 실시간 그루브 오디션

### 24.3 Groove Pool
- Ctrl+Alt+6으로 접근
- **주요 파라미터**:
  - **Base**: 그루브 노트 측정 타이밍 해상도 (1/4, 1/8 등)
  - **Quantize**: 사전 그루브 퀀타이제이션 (0-100%)
  - **Timing**: 그루브 패턴 강도
  - **Random**: 타이밍 변동 (인간화)
  - **Velocity**: 그루브 벨로시티 효과 (-100 ~ +100)
  - **Global Amount**: 전체 Timing/Random/Velocity 스케일링 (최대 130%)

### 24.4 편집 및 추출
- 그루브를 MIDI 트랙으로 드래그하여 클립으로 편집
- 컨텍스트 메뉴 > "Extract Groove": 클립에서 타이밍/볼륨 추출
- **Commit 버튼**: 그루브 파라미터를 클립에 기록 (MIDI 노트 이동 또는 워프 마커 생성)

### 24.5 고급 기법
- **단일 보이스 그루빙**: 개별 드럼 체인 추출 후 독립 그루브 적용
- **비파괴적 퀀타이제이션**: Timing/Random/Velocity=0, Quantize+Base 조절
- **텍스처 생성**: 트랙 복제 후 높은 Random으로 사실적 더블링

### 24.6 그루브 저장
- 디스크 아이콘 클릭: User Library > Grooves 폴더에 저장
- 우클릭으로 그루브 이름 변경

---

## 25. Racks (랙)

### 25.1 랙 유형

#### Instrument Rack
- 악기 + MIDI 이펙트 (시작부) + 오디오 이펙트 (끝부) 포함
- MIDI/오디오 트랙에 배치

#### Audio Effect Rack
- 오디오 이펙트만 포함
- 오디오 트랙 또는 MIDI 트랙 (악기 다운스트림)에 배치

#### MIDI Effect Rack
- MIDI 이펙트만 포함
- MIDI 트랙에만 배치

#### Drum Rack
- 128개 MIDI 노트에 매핑되는 패드
- Pad View: 드럼 랙 고유 기능
- 브라우저에서 샘플/이펙트/악기/프리셋을 패드에 드래그
- 빈 패드에 샘플 드롭 → Simpler 자동 생성
- 멀티 샘플 드롭 → 크로매틱 매핑 Simpler
- Alt/Cmd+드래그 → 단일 패드에 레이어링

### 25.2 Chain List (체인 리스트)
- 병렬 디바이스 체인 분기점
- 체인별 컨트롤:
  - Chain Activator (활성/비활성)
  - Solo 버튼
  - Hot-Swap 버튼
  - Volume, Pan 슬라이더 (Instrument/Drum/Audio Effect Rack)
  - Send Level, MIDI Assignment (Drum Rack)
- 체인 선택, 이름 변경, 드래그 앤 드롭

### 25.3 Zones (존)
- 각 체인 입력의 데이터 필터

#### Key Zones
- MIDI 노트 범위 필터링
- "키보드 스플릿" 설정
- Fade Range로 벨로시티 감쇠

#### Velocity Zones
- MIDI Note On 벨로시티 필터링 (1-127)
- Fade Range

#### Chain Select Zones
- 단일 파라미터 (0-127)로 체인 필터링
- Chain Selector (드래그 가능 인디케이터)

### 25.4 Macro Controls (매크로 컨트롤)
- 최대 **16개** 커스터마이즈 가능 노브
- 기본 8개 표시, 추가 노브는 뷰 선택기로 표시
- Rack 내 모든 디바이스의 파라미터 제어

### 25.5 Map Mode
- 매핑 가능 파라미터에 색상 오버레이
- Macro Control 다이얼 아래 Map 버튼
- 디바이스 파라미터 선택 → Macro에 할당
- Min/Max 슬라이더로 값 범위 조절
- 반전 매핑 가능

### 25.6 Macro Control Variations (Live 12 신규)
- Macro Control의 다른 상태를 프리셋/"스냅샷"으로 저장
- 생성, 이름 변경, 복제, 삭제, 실행, 덮어쓰기
- 개별 Macro를 Variation 변경에서 제외 (컨텍스트 메뉴)

### 25.7 Randomization
- Rand 버튼: 매핑된 모든 Macro Control 값 랜덤화
- 개별 Macro를 랜덤화에서 제외 가능
- 프리셋의 Volume 파라미터는 기본 제외

### 25.8 디바이스 그룹핑
- Ctrl+G: 디바이스 그룹 (랙 생성)
- Ctrl+Shift+G: 디바이스 그룹 해제

---

## 26. Max for Live

### 26.1 핵심 기능
- Live 내에서 커스텀 디바이스 구축으로 확장/커스터마이즈
- Cycling '74와 공동 개발된 Max 프로그래밍 환경 접근

### 26.2 디바이스 유형
- **Instruments**: 커스텀 사운드 제너레이터
- **Audio Effects**: 오디오 신호 프로세싱 도구
- **MIDI Effects**: MIDI 데이터 변환 도구
- **Modulators**: 모듈레이션 신호 컨트롤 디바이스
- **MIDI Tools**: Transformation (기존 MIDI 수정) + Generative (새 MIDI 생성)

### 26.3 API 접근
- Live Set 요소 접근 및 수정
- 하드웨어 컨트롤 서피스 기능 확장 (Live API)

### 26.4 편집 기능
- Max 에디터 (패처) 직접 열기
- 오브젝트 및 가상 케이블 연결 편집
- 변경 저장 시 해당 디바이스의 모든 인스턴스 자동 업데이트
- 내장 프리셋과 함께 커스텀 프리셋 생성

### 26.5 파일 관리
- Max 디바이스: 별도 AMXD 파일로 저장 (Live Set에 포함되지 않음)
- "Freezing": 외부 종속성 (샘플, 패치) 번들링

### 26.6 내장 리소스
- Core Library의 기본 악기, 이펙트, MIDI 도구 컬렉션
- 브라우저에서 Instruments, Audio Effects, MIDI Effects, Modulators 레이블로 접근
- Max Help 메뉴의 Max for Live 전용 문서

---

## 27. Link / Tempo / Sync (동기화)

### 27.1 Ableton Link
- **네트워크 기반 동기화**: 템포 및 글로벌 런치 퀀타이제이션 위치 동기화
- 동일 네트워크의 Link 지원 디바이스 연결
- Settings > Link, Tempo & MIDI에서 "Show Link Toggle" 활성화
- **Start/Stop Sync**: 옵션 - 연결된 앱 간 동기화 명령
- **Control Bar**: 연결된 앱 수 표시
- **템포 제어**: 첫 연결 앱이 초기 템포 설정, 이후 어느 앱이든 변경 가능
- **제한**: Link 활성 시 녹음 카운트인 불가

### 27.2 Tempo Follower (Live 12 신규)
- 수신 오디오 신호 실시간 분석으로 템포 해석
- Settings에서 입력 채널 설정
- "Follow" 버튼 (Control Bar)
- 명확한 리듬의 오디오에 최적화
- Link, Tempo Follower, External Sync는 상호 배타적

### 27.3 MIDI Clock
- 빠른 속도의 메트로놈처럼 동작
- 호스트의 템포 변경이 동기화된 디바이스에 자동 전파
- Song Position 메시지 포함
- 양방향: Live가 호스트 및 디바이스 역할 모두 가능

### 27.4 MIDI Timecode
- SMPTE 표준의 MIDI 버전
- 초와 프레임 단위 시간 지정
- Live는 Timecode를 Arrangement 위치로 해석
- 미터 정보 없음: 수동 템포 조절 필요
- 단방향: Live는 디바이스 역할만 (호스트 불가)

### 27.5 외부 MIDI 동기화
- **동기화 전송**: Settings에서 MIDI 디바이스 설정, 하단 LED 깜박임
- **동기화 수신**: External Sync 활성화, 상단 LED 깜박임
- **Song Position Pointers**: 호스트 점프 시 Live도 따라감, Loop 활성 시 루프 길이에 래핑

### 27.6 Sync Delay
- Live와 외부 시퀀서 간 신호 전송 딜레이 보상

---

## 28. Video (비디오)

### 28.1 비디오 지원
- 비디오를 클립으로 임포트
- 수정된 비디오 및 오디오 내보내기
- Ctrl+Alt+V: 비디오 창 표시/숨기기
- File > Export Audio/Video로 비디오 내보내기

---

## 29. Control Surfaces (컨트롤 서피스)

### 29.1 설정
- Settings > Link, Tempo & MIDI 탭
- **6개 Control Surface 드롭다운 메뉴**: 최대 6개 동시 사용
- 각 서피스별 입력/출력 포트 설정

### 29.2 지원 디바이스
- Ableton Push (1, 2, 3)
- Akai APC40, APC Mini, MPK mini IV
- Novation Launchpad, Launch Control XL 3
- 기타 다수의 서드파티 컨트롤러

### 29.3 커스텀 Control Surface 스크립트
- Python 기반 Control Surface 스크립트 생성 가능
- Live API를 통한 기능 확장

### 29.4 Instant Mapping
- MIDI Remote Control 즉시 매핑
- 선택된 디바이스 파라미터에 자동 매핑

---

## 30. Stem Separation (스템 분리)

### 30.1 기본 기능 (Suite 전용, Live 12.3+)
- 오디오 신호의 스펙트럴/시간적 특성 분석
- 감지된 컴포넌트를 스템으로 추출

### 30.2 4가지 스템
- **Vocals (보컬)**
- **Drums (드럼)**
- **Bass (베이스)**
- **Others (기타)**

### 30.3 사용 방법
- 브라우저에서 오디오 파일 분리
- Session/Arrangement View에서 오디오 클립 분리
- 컨텍스트 메뉴 또는 Create 메뉴 > "Separate Stems to New Audio Tracks"
- 각 스템은 새 Group Track 내 개별 트랙에 렌더링

---

## 31. Audio-to-MIDI Conversion

### 31.1 Slice to New MIDI Track
- 오디오를 시간 기반 청크로 분할하여 MIDI 노트에 할당
- Drum Rack 생성: 슬라이스당 하나의 체인 (Simpler 포함)
- Macro Controls: 엔벨로프 및 루프 파라미터에 사전 할당
- **슬라이싱 옵션**: 비트 해상도, 트랜지언트, 워프 마커 기준
- 최대 128 슬라이스
- "Preserve warped timing" 옵션

### 31.2 Convert Harmony to New MIDI Track
- 폴리포닉 녹음에서 피치 식별
- 피아노 사운드 Instrument Rack으로 MIDI 클립 생성
- 하모닉 악기 (기타, 피아노) 또는 음악 컬렉션에 적합

### 31.3 Convert Melody to New MIDI Track
- 모노포닉 오디오에서 피치 추출
- 신시사이저/일렉트릭 피아노 하이브리드 악기 프리로드
- "Synth to Piano" Macro Control로 음색 조절

### 31.4 Convert Drums to New MIDI Track
- 비피치, 타악 오디오 분석
- 킥, 스네어, 하이햇 식별
- 프리로드된 Drum Rack에 리듬 배치
- 녹음된 브레이크비트 또는 비트박싱에 적합

### 31.5 최적화 팁
- 명확한 어택의 음악 사용
- 격리된 악기 녹음 사용
- 비압축 포맷 (.wav, .aiff) 선호
- 변환 전 트랜지언트 마커 조정

---

## 32. Tuning Systems (튜닝 시스템)

### 32.1 기본 기능 (Live 12 신규)
- 12음 평균율 이외의 대안 튜닝 접근
- MPE 지원
- 클립 및 디바이스에 튜닝 적용

---

## 33. Keys and Scales (키 및 스케일)

### 33.1 기본 기능 (Live 12 신규)
- 클립 스케일 설정
- 디바이스 간 동기화
- Piano Roll에서 하이라이트
- Root Note + Scale Name 선택
- 스케일 도수 기반 트랜스포즈

---

## 34. Accessibility (접근성)

### 34.1 Screen Reader 지원 (Live 12 신규)
- 시각 장애 사용자를 위한 스크린 리더 지원

### 34.2 키보드 탐색
- Use Tab to Move Focus 명령
- 포커스 이동 단축키 (Alt+0~8)
- Wrap Tab Navigation
- Move Clips with Arrow Keys
- Settings 탭 간 Tab/Shift+Tab/방향키 탐색

### 34.3 High Contrast 테마
- 고대비 시각 옵션

---

## 35. Keyboard Shortcuts (키보드 단축키)

### 35.1 뷰 표시/숨기기
| 동작 | Windows | Mac |
|------|---------|-----|
| 전체 화면 토글 | F11 | Cmd+F |
| 두 번째 창 토글 | Ctrl+Shift+W | Cmd+Shift+W |
| Session/Arrangement 전환 | Tab | Tab |
| Device/Clip View 전환 | Shift+Tab / F12 | Shift+Tab / F12 |
| Hot-Swap Mode | Q | Q |
| Info View | Shift+? | Shift+? |
| 비디오 창 | Ctrl+Alt+V | Cmd+Option+V |
| 브라우저 | Ctrl+Alt+B | Cmd+Option+B |
| Overview | Ctrl+Alt+O | Cmd+Option+O |
| In/Out | Ctrl+Alt+I | Cmd+Option+I |
| Sends | Ctrl+Alt+S | Cmd+Option+S |
| Mixer | Ctrl+Alt+M | Cmd+Option+M |
| Clip View | Ctrl+Alt+3 | Cmd+Option+3 |
| Device View | Ctrl+Alt+4 | Cmd+Option+4 |
| Groove Pool | Ctrl+Alt+6 | Cmd+Option+6 |
| Settings | Ctrl+, | Cmd+, |

### 35.2 포커스 이동
| 동작 | Windows | Mac |
|------|---------|-----|
| Control Bar | Alt+0 | Option+0 |
| Session View | Alt+1 | Option+1 |
| Arrangement View | Alt+2 | Option+2 |
| Clip View | Alt+3 | Option+3 |
| Device View | Alt+4 | Option+4 |
| Browser | Alt+5 | Option+5 |
| Groove Pool | Alt+6 | Option+6 |
| Help View | Alt+7 | Option+7 |
| Selected Clip Panel | Alt+8 | Option+8 |

### 35.3 Set 및 프로그램
| 동작 | Windows | Mac |
|------|---------|-----|
| New Live Set | Ctrl+N | Cmd+N |
| Open Live Set | Ctrl+O | Cmd+O |
| Save Live Set | Ctrl+S | Cmd+S |
| Save As | Ctrl+Shift+S | Cmd+Shift+S |
| Quit | Ctrl+Q | Cmd+Q |
| Export Audio/Video | Ctrl+Shift+R | Cmd+Shift+R |
| Export MIDI | Ctrl+Shift+E | Cmd+Shift+E |

### 35.4 디바이스 및 플러그인
| 동작 | Windows | Mac |
|------|---------|-----|
| 디바이스 그룹 | Ctrl+G | Cmd+G |
| 디바이스 그룹 해제 | Ctrl+Shift+G | Cmd+Shift+G |
| 파라미터 리셋 | Delete / 더블 클릭 | Delete / 더블 클릭 |
| 플러그인 창 표시/숨기기 | Ctrl+Alt+P | Cmd+Option+P |
| A/B 비교 전환 | P | P |

### 35.5 편집
| 동작 | Windows | Mac |
|------|---------|-----|
| Cut | Ctrl+X | Cmd+X |
| Copy | Ctrl+C | Cmd+C |
| Paste | Ctrl+V | Cmd+V |
| Duplicate | Ctrl+D | Cmd+D |
| Delete | Delete | Delete |
| Undo | Ctrl+Z | Cmd+Z |
| Redo | Ctrl+Y | Cmd+Shift+Z |
| Rename | Ctrl+R | Cmd+R |
| Select All | Ctrl+A | Cmd+A |

### 35.6 트랜스포트
| 동작 | Windows | Mac |
|------|---------|-----|
| Play/Stop | Space | Space |
| Continue Play | Shift+Space | Shift+Space |
| Record | F9 | F9 |
| Arm Recording | Shift+F9 | Shift+F9 |
| Session Record | Ctrl+Shift+F9 | Cmd+Shift+F9 |
| Back to Arrangement | F10 | F10 |
| Metronome | O | O |
| Home (처음으로) | Home | Home/Fn+Left |

### 35.7 Session View
| 동작 | Windows | Mac |
|------|---------|-----|
| 클립 런치 | Enter | Enter |
| 인접 클립 선택 | 방향키 | 방향키 |
| 정지 버튼 추가/제거 | Ctrl+E | Cmd+E |
| 트랙 내 클립 정지 | Ctrl+Enter | Cmd+Enter |
| MIDI 클립 삽입 | Ctrl+Shift+M | Cmd+Shift+M |
| 씬 삽입 | Ctrl+I | Cmd+I |
| 캡처 씬 삽입 | Ctrl+Shift+I | Cmd+Shift+I |
| Capture MIDI | Ctrl+Shift+C | Cmd+Shift+C |
| 클립 비활성화 | 0 | 0 |

### 35.8 Arrangement View
| 동작 | Windows | Mac |
|------|---------|-----|
| 클립 분할 | Ctrl+E | Cmd+E |
| 클립 병합 | Ctrl+J | Cmd+J |
| 클립 크롭 | Ctrl+Shift+J | Cmd+Shift+J |
| 루프 토글 | Ctrl+L | Cmd+L |
| 침묵 삽입 | Ctrl+I | Cmd+I |
| Cut Time | Ctrl+Shift+X | Cmd+Shift+X |
| Paste Time | Ctrl+Shift+V | Cmd+Shift+V |
| Duplicate Time | Ctrl+Shift+D | Cmd+Shift+D |
| Delete Time | Ctrl+Shift+Delete | Cmd+Shift+Delete |
| 오디오 반전 | R | R |
| 페이드 생성 | Ctrl+Alt+F | Cmd+Option+F |
| Take Lane 표시 | Ctrl+Alt+U | Cmd+Option+U |
| Bounce to New Track | Ctrl+B | Cmd+B |

### 35.9 MIDI Note Editor
| 동작 | Windows | Mac |
|------|---------|-----|
| 노트 Chop | Ctrl+E | Cmd+E |
| 노트 Split | E+클릭 | E+클릭 |
| 노트 Join | Ctrl+J | Cmd+J |
| Quantize | Ctrl+U | Cmd+U |
| 벨로시티 변경 (에디터) | Alt+드래그 | Cmd+드래그 |
| 스케일 하이라이트 | K | K |
| 전체 크기 Clip View | Ctrl+Alt+E | Cmd+Option+E |
| 노트 그룹 (Play All) | Ctrl+G | Cmd+G |
| 그룹 해제 | Ctrl+Shift+G | Cmd+Shift+G |
| MIDI Tool 적용 | Ctrl+Enter | Cmd+Enter |

### 35.10 그리드
| 동작 | Windows | Mac |
|------|---------|-----|
| Draw Mode | B | B |
| 그리드 좁히기 | Ctrl+1 | Cmd+1 |
| 그리드 넓히기 | Ctrl+2 | Cmd+2 |
| 삼연음 | Ctrl+3 | Cmd+3 |
| 스냅 토글 | Ctrl+4 | Cmd+4 |
| 고정/적응형 | Ctrl+5 | Cmd+5 |

### 35.11 트랙
| 동작 | Windows | Mac |
|------|---------|-----|
| Audio Track 삽입 | Ctrl+T | Cmd+T |
| MIDI Track 삽입 | Ctrl+Shift+T | Cmd+Shift+T |
| Return Track 삽입 | Ctrl+Alt+T | Cmd+Option+T |
| 트랙 그룹 | Ctrl+G | Cmd+G |
| 그룹 해제 | Ctrl+Shift+G | Cmd+Shift+G |
| Arm 토글 | C | C |
| Solo 토글 | S | S |
| 비활성화 | 0 | 0 |
| Freeze/Unfreeze | Ctrl+Alt+Shift+F | Cmd+Option+Shift+F |

### 35.12 브라우저
| 동작 | Windows | Mac |
|------|---------|-----|
| 검색 | Ctrl+F | Cmd+F |
| 유사 파일 표시 | Ctrl+Shift+F | Cmd+Shift+F |
| 히스토리 뒤로 | Ctrl+[ | Cmd+[ |
| 히스토리 앞으로 | Ctrl+] | Cmd+] |
| 필터 뷰 | Ctrl+Alt+G | Cmd+Option+G |
| 태그 에디터 | Ctrl+Shift+E | Cmd+Shift+E |

### 35.13 Key/MIDI Map
| 동작 | Windows | Mac |
|------|---------|-----|
| MIDI Map Mode | Ctrl+M | Cmd+M |
| Key Map Mode | Ctrl+K | Cmd+K |
| Computer MIDI Keyboard | M | M |

### 35.14 Momentary Latching (약 500ms 유지 시 일시 토글)
- A: Arrangement 오토메이션 모드
- B: Draw Mode
- S: 선택 트랙 솔로
- Z: Arrangement 선택 줌
- F1-F8: 트랙 활성화 스위치
- Tab: 뷰 전환

---

## 부록: Edition별 기능 비교

### Intro
- 최대 16 오디오/MIDI 트랙, 16 씬
- 8개 소프트웨어 악기, 4개 Pack
- 핵심 워크플로우 기능 포함 (Session/Arrangement View, 비파괴 편집, Capture MIDI, Comping, MPE, Tuning Systems, Screen Reader)

### Standard
- 무제한 트랙/씬
- 13개 악기, 16개 Pack, 42개 이펙트
- Complex 워프 모드
- Audio-to-MIDI 변환
- Audio Slicing
- REX 파일 지원

### Suite
- 무제한 트랙/씬
- 20개 악기, 33개 Pack, 58개 오디오 이펙트
- Max for Live 포함
- Stem Separation
- 모든 이펙트 및 악기 포함
- 71GB+ 샘플

---

## 부록: Sound Packs 전체 목록

1. Chop and Swing
2. Beat Tools
3. Build and Drop
4. Drive and Glow
5. Guitar and Bass
6. Drum Essentials
7. Grand Piano
8. Mood Reel
9. Skitter and Step
10. Electric Keyboards
11. Orchestral Strings
12. Session Drums Club
13. Session Drums Studio
14. Synth Essentials
15. Golden Era Hip-Hop Drums
16. Trap Drums
17. Drone Lab
18. Drum Booth
19. Brass Quartet
20. Glitch and Wash
21. Inspired by Nature
22. Latin Percussion
23. Orchestral Brass
24. Orchestral Mallets
25. Orchestral Woodwinds
26. Punch and Tilt
27. Singularities
28. String Quartet
29. Upright Piano
30. Voice Box
31. Lost and Found
32. Performance Pack
33. MIDI Tools Pack / Sequencer Pack

---

*본 문서는 Ableton 공식 문서, 레퍼런스 매뉴얼, 릴리즈 노트를 기반으로 작성되었습니다.*
*마지막 업데이트: 2026-03-26*
