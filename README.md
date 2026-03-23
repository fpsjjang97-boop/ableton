# SUNO & Ableton - 음악 제작 통합 프로젝트

> Suno AI 음악 커뮤니티 플랫폼, Chrome 확장 프로그램, 그리고 Ableton 음악 제작 리소스를 하나로 통합한 프로젝트입니다.
>
> Unified music production project — Suno AI community platform, Chrome Extension, and Ableton production resources.

![Chrome](https://img.shields.io/badge/Chrome-Extension-blue?logo=googlechrome)
![JavaScript](https://img.shields.io/badge/Language-JavaScript-yellow)
![Manifest](https://img.shields.io/badge/Manifest-V3-green)
![PHP](https://img.shields.io/badge/Backend-PHP-purple)
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
└── README.md
```

---

## 1. Suno Helper - Chrome 확장 프로그램 | Chrome Extension

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

## 2. Homepage - 웹 애플리케이션 | Web Application

PHP + SQLite 기반의 **음악 커뮤니티 플랫폼**.

A full-featured **music community platform** built with PHP + SQLite.

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

## 3. Ableton - 음악 제작 리소스 | Production Resources

Ableton Live 관련 음악 제작 파일 모음입니다.

| 파일 | 설명 |
|------|------|
| 11.mid | MIDI 시퀀스 파일 (악기 연주 데이터) |
| 2018.zip | Ableton 프로젝트 또는 샘플 팩 (~8.4MB) |
| TEST_Beat_01.mp3 | 테스트용 비트 트랙 (~2.5MB) |
| 원신mp3.mp3 | 오디오 파일 (~5.8MB) |

### 활용 방법
- MIDI 파일은 Ableton Live 또는 기타 DAW에서 임포트하여 편집 가능
- MP3 파일은 샘플링 또는 레퍼런스 트랙으로 활용 가능
- Suno AI로 생성한 음악과 Ableton에서 제작한 음악을 결합하여 작업 가능

---

## 통합 워크플로우 | Unified Workflow

```
[suhbway.kr 프롬프트 작성] → [Suno Helper로 자동 세팅] → [Suno AI 음악 생성]
                                                              ↓
[GitHub 저장] ← [Save to Git] ← [곡 선택 + 점수 입력]
                                                              ↓
[Ableton Live에서 후처리/믹싱] ← [생성된 음악 다운로드]
```

---

## 기술 스택 | Tech Stack

| 구성요소 | 기술 |
|----------|------|
| **확장 프로그램** | JavaScript (ES2020+), Chrome Extension (Manifest V3) |
| **API 연동** | Chrome Storage/Tabs/Cookies/Scripting, GitHub REST API, Suno Studio API |
| **웹사이트** | PHP 8+, SQLite, Tailwind CSS, 다크 테마 |
| **음악 제작** | Ableton Live, Suno AI |
| **버전 관리** | Git, GitHub API |

---

## 버전 히스토리 | Version History

| 버전 | 날짜 | 변경사항 |
|------|------|----------|
| v3.0.0 | 2026-03-23 | 프로젝트 통합: Suno Helper + Homepage + Ableton 리소스 |
| v2.1.0 | 2026-03-11 | React 18+ 호환성, 필드 감지 개선, 중복 입력 방지 |
| v2.0.0 | 2026-03 | Manifest V3 마이그레이션, 다중 전략 데이터 수집 |

---

## 라이선스 | License

MIT License
