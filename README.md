# SUNO & Ableton - 음악 제작 통합 프로젝트

> MIDI 데이터 임베딩/패턴 생성 + Suno AI 커뮤니티 플랫폼 + Chrome 확장 프로그램 + Ableton 음악 제작을 하나로 통합한 프로젝트입니다.
>
> Unified music production project — MIDI AI pipeline, Suno AI community platform, Chrome Extension, and Ableton production resources.

![Chrome](https://img.shields.io/badge/Chrome-Extension-blue?logo=googlechrome)
![JavaScript](https://img.shields.io/badge/Language-JavaScript-yellow)
![Manifest](https://img.shields.io/badge/Manifest-V3-green)
![PHP](https://img.shields.io/badge/Backend-PHP-purple)
![Python](https://img.shields.io/badge/AI-Python-blue)
![Ableton](https://img.shields.io/badge/DAW-Ableton_Live-black)

---

## 프로젝트 구조 | Project Structure

```
├── Suno/                  # Chrome 확장 프로그램 (Suno Helper)
├── Homepage/              # Suno AI 커뮤니티 웹사이트
│   ├── src/               # PHP 소스 코드 + SQLite DB
│   │   ├── admin/         # 관리자 페이지 (41개)
│   │   ├── *.php          # 프론트엔드 페이지 (58개)
│   │   ├── schema.sql     # DB 스키마
│   │   └── database.sqlite
│   └── homepage.zip       # 배포용 압축 파일
├── Ableton/               # Ableton 음악 제작 리소스
│   ├── 11.mid             # MIDI 시퀀스 파일
│   ├── 2018.zip           # Ableton 프로젝트/샘플 팩
│   ├── TEST_Beat_01.mp3   # 테스트 비트 트랙
│   └── 원신mp3.mp3         # 오디오 파일
├── agents/                # 멀티 에이전트 시스템 (Composer/Manager/Reviewer)
├── tools/                 # audio2midi 파이프라인 + MCP 브릿지
├── output/                # MIDI 변환/생성 결과물
├── reviews/               # 에이전트 리뷰 결과
├── 11.mid                 # 원본 MIDI (Omnisphere, Bb minor)
├── 원신_output.mid         # 원신 OST MIDI 변환 결과
├── settings.json          # 에이전트 설정
├── start_agents.sh        # 에이전트 실행 스크립트
└── README.md
```

---

## 1. MIDI AI 파이프라인 | MIDI AI Pipeline

MIDI 데이터를 임베딩하고 패턴을 생성하여 Ableton으로 음악을 제작합니다.

### 작업 단계

1. MIDI 데이터셋 수집
2. Data 임베딩
3. 패턴 생성 (MCP 서버 연결)
4. Ableton 프로그램 연동
5. 데이터베이스 기반 음악 제작 테스트 및 고도화

### 핵심 도구

| 항목 | 내용 |
|------|------|
| **플랫폼** | Ableton Live |
| **임베딩 자료 구조** | MIDI |
| **MCP** | [ahujasid/ableton-mcp](https://github.com/ahujasid/ableton-mcp) — AI ↔ Ableton Live 연결 |
| **MIDI 분석/생성** | [magenta/magenta](https://github.com/magenta/magenta) — Music Transformer |

### 멀티 에이전트 시스템

| 에이전트 | 역할 |
|----------|------|
| **Composer** | MIDI 생성 및 편집 |
| **Manager** | 작업 오케스트레이션 |
| **Reviewer** | 품질 평가 및 피드백 |

### 11.mid 분석 결과

| 항목 | 값 |
|------|-----|
| 타입 | Type 1 (멀티트랙) |
| 트랙 | 2개 (메타 + Omnisphere 02) |
| BPM | 60 (후반부 리타르단도 43~61) |
| 박자 | 4/4 |
| 재생 시간 | 2분 11초 |
| 악기 | Omnisphere (신스 패드/앰비언트) |
| 노트 수 | 387개 |
| 음역 | G#1 ~ A#6 |
| 추정 조성 | Bb 마이너 / Db 메이저 |
| 스타일 | 앰비언트 / 시네마틱 |

---

## 2. Suno Helper - Chrome 확장 프로그램 | Chrome Extension

### 기능 A: 자동 입력 (suhbway.kr → Suno)

suhbway.kr의 프롬프트 데이터를 Suno.com 생성 페이지에 자동으로 전달합니다.

- **원클릭 전송** — suhbway.kr 프롬프트 페이지에서 "Send to Suno" 버튼 클릭
- **자동 입력 필드** — Style of Music, Lyrics, Exclude Styles, 파라미터 슬라이더
- **스마트 감지** — 7단계 부모 탐색, aria-describedby, name 속성 매칭
- **React 18+ 호환** — Fiber memoizedProps 리셋, focusin/focusout 이벤트 처리
- **재시도 로직** — 필드별 독립 재시도, 30초 타임아웃
- **자동 Custom 모드** — 입력 전 자동으로 Custom 모드 전환

### 기능 B: GitHub 저장 (Suno → GitHub)

Suno.com에서 생성된 음악을 선택하고 메타데이터를 GitHub 저장소에 저장합니다.

- **곡 선택** — 곡 카드 위 체크박스 오버레이
- **선택적 평점** — 저장 전 0-100점 평가
- **마크다운 내보내기** — 전체 메타데이터가 포함된 개별 곡 파일 생성
- **히스토리 추적** — README.md에 히스토리 테이블 자동 업데이트
- **다중 전략 데이터 수집** — Studio API → React Fiber → 백그라운드 탭 렌더링

### 작동 흐름 | How It Works

```
suhbway.kr                    Suno.com                     GitHub
┌──────────┐    클릭      ┌──────────────┐   저장       ┌──────────┐
│  프롬프트 │ ──────────→ │  생성 페이지  │ ──────────→ │  Repo    │
│  상세     │  자동 입력  │  (Custom)    │  메타데이터  │  songs/  │
│  페이지   │            │  ♫ 생성      │             │  README  │
└──────────┘              └──────────────┘             └──────────┘
```

### 설치 | Installation

1. `chrome://extensions` 이동
2. **개발자 모드** 활성화
3. **압축해제된 확장 프로그램을 로드** → `Suno/` 폴더 선택
4. 툴바에 확장 프로그램 아이콘 고정
5. 아이콘 클릭 후 설정:
   - **GitHub Personal Access Token** (repo 권한)
   - **GitHub Username**
   - **Repository Name**

---

## 3. Homepage - 웹 애플리케이션 | Web Application

PHP + SQLite 기반의 **음악 커뮤니티 플랫폼**.

### 주요 기능 | Features

| 기능 | 설명 |
|------|------|
| **사용자 시스템** | 회원가입, 로그인, 프로필, 메시지, 팔로우 |
| **음악 라이브러리** | 업로드, 탐색, 재생, 좋아요, 북마크, 공유 |
| **커뮤니티 게시판** | 게시글, 댓글, 이미지 업로드 |
| **프롬프트 공유** | 음악 생성 프롬프트 작성 및 공유 |
| **검색 & 디스커버리** | 태그 검색, 인기 트랙, 랭킹 |
| **관리자 패널** | 사용자/콘텐츠 관리, 설정, 신고 처리 (41개 관리 페이지) |

### 실행 방법

```bash
cd Homepage/src
php -S localhost:8080
```

---

## 4. Ableton - 음악 제작 리소스 | Production Resources

| 파일 | 설명 |
|------|------|
| Ableton/11.mid | MIDI 시퀀스 파일 (악기 연주 데이터) |
| Ableton/2018.zip | Ableton 프로젝트 또는 샘플 팩 (~8.4MB) |
| Ableton/TEST_Beat_01.mp3 | 테스트용 비트 트랙 (~2.5MB) |
| Ableton/원신mp3.mp3 | 오디오 파일 (~5.8MB) |

---

## 통합 워크플로우 | Unified Workflow

```
[suhbway.kr 프롬프트 작성] → [Suno Helper로 자동 세팅] → [Suno AI 음악 생성]
                                                              ↓
[GitHub 저장] ← [Save to Git] ← [곡 선택 + 점수 입력]
                                                              ↓
[Ableton Live에서 후처리/믹싱] ← [생성된 음악 다운로드]
                                                              ↓
[MIDI AI 파이프라인] → [임베딩 → 패턴 생성 → MCP → Ableton 제어]
```

---

## 기술 스택 | Tech Stack

| 구성요소 | 기술 |
|----------|------|
| **확장 프로그램** | JavaScript (ES2020+), Chrome Extension (Manifest V3) |
| **API 연동** | Chrome Storage/Tabs/Cookies/Scripting, GitHub REST API, Suno Studio API |
| **웹사이트** | PHP 8+, SQLite, Tailwind CSS, 다크 테마 |
| **MIDI AI** | Python, Music Transformer, Magenta, audio2midi |
| **DAW 연동** | Ableton Live, MCP Protocol |
| **버전 관리** | Git, GitHub API |

---

## 오픈소스 MIDI 리소스 리스트

### 1. MIDI 데이터셋

| # | 레포 | Stars | 설명 | MIDI 규모 |
|---|------|-------|------|-----------|
| 1 | [Metacreation-Lab/GigaMIDI-Dataset](https://github.com/Metacreation-Lab/GigaMIDI-Dataset) | ⭐81 | 현존 최대 심볼릭 음악 데이터셋 | **210만+** |
| 2 | [loubbrad/aria-midi](https://github.com/loubbrad/aria-midi) | ⭐78 | 솔로 피아노 녹음 → MIDI 변환 | **118만+** |
| 3 | [jeffreyjohnens/MetaMIDIDataset](https://github.com/jeffreyjohnens/MetaMIDIDataset) | ⭐148 | MIDI + Spotify 매칭 | **43만+** |
| 4 | [craffel/midi-dataset](https://github.com/craffel/midi-dataset) | ⭐170 | Lakh MIDI Dataset | **17만+** |
| 5 | [asigalov61/Tegridy-MIDI-Dataset](https://github.com/asigalov61/Tegridy-MIDI-Dataset) | ⭐261 | Music AI 모델 학습용 | 대규모 |

### 2. MIDI 처리 / 토크나이징

| # | 레포 | Stars | 설명 |
|---|------|-------|------|
| 1 | [craffel/pretty-midi](https://github.com/craffel/pretty-midi) | ⭐1,007 | Python MIDI 처리 표준 |
| 2 | [Natooz/MidiTok](https://github.com/Natooz/MidiTok) | ⭐857 | 딥러닝용 MIDI 토크나이저 |
| 3 | [YatingMusic/miditoolkit](https://github.com/YatingMusic/miditoolkit) | ⭐274 | 고수준 MIDI 처리 툴킷 |

### 3. AI 음악 생성 모델

| # | 레포 | Stars | 설명 |
|---|------|-------|------|
| 1 | [magenta/magenta](https://github.com/magenta/magenta) | ⭐19,772 | Music Transformer, MusicVAE |
| 2 | [salu133445/musegan](https://github.com/salu133445/musegan) | ⭐2,013 | GAN 멀티트랙 음악 생성 |
| 3 | [ElectricAlexis/NotaGen](https://github.com/ElectricAlexis/NotaGen) | ⭐1,173 | LLM 기반 심볼릭 음악 생성 |
| 4 | [SkyTNT/midi-model](https://github.com/SkyTNT/midi-model) | ⭐352 | MIDI 이벤트 Transformer |

### 4. MIDI MCP 서버

| # | 레포 | Stars | 설명 |
|---|------|-------|------|
| 1 | [ahujasid/ableton-mcp](https://github.com/ahujasid/ableton-mcp) | ⭐2,334 | AI ↔ Ableton Live MCP 연결 |
| 2 | [tubone24/midi-mcp-server](https://github.com/tubone24/midi-mcp-server) | ⭐33 | 텍스트→MIDI MCP 서버 |

---

## 버전 히스토리 | Version History

| 버전 | 날짜 | 변경사항 |
|------|------|----------|
| v3.0.0 | 2026-03-23 | SUNO 프로젝트 전체를 Ableton 레포에 머지 통합 |
| v2.1.0 | 2026-03-11 | React 18+ 호환성, 필드 감지 개선, 중복 입력 방지 |
| v2.0.0 | 2026-03 | Manifest V3 마이그레이션, 다중 전략 데이터 수집 |

---

## 라이선스 | License

MIT License
