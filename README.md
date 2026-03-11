# Suno Helper - Chrome Extension

  suhbway.kr의 프롬프트를 Suno에 자동 세팅하고, Suno에서 만든 음악을 GitHub에 저장하는 Chrome 확장 프로그램입니다.

  ---

  ## 기능

  ### 기능 A: suhbway.kr → Suno 자동 세팅
  - suhbway.kr/prompt_detail 페이지에서 "Send to Suno" 버튼 클릭
  - Prompt → Style of Music 필드에 자동 입력
  - Lyrics → 가사 필드에 자동 입력
  - Exclude Styles → Exclude 필드에 자동 입력
  - Parameters (Weirdness, Style Influence, Audio Influence) → 슬라이더에 자동 세팅
  - Custom 모드 자동 전환 후 필드 렌더링 대기 (최대 8초)
  - 필드별 독립 재시도 (이미 입력된 필드는 건너뜀)
  - React 18+ 호환 입력 방식 적용
  - 콘솔 로그 (`[SunoHelper]`)로 디버깅 지원

  ### 기능 B: Suno → GitHub 저장
  - suno.com에서 생성된 곡을 체크박스로 선택
  - 점수(0~100) 입력 가능
  - "Save to Git" 클릭 시 프롬프트, 음악 URL, 점수가 GitHub에 Markdown으로 저장
  - README.md에 히스토리 테이블 자동 업데이트

  각 기능은 독립적으로 사용 가능합니다.

  ---

  ## 설치 방법

  1. Chrome에서 `chrome://extensions` 접속
  2. 오른쪽 위 "개발자 모드" 켜기
  3. "압축해제된 확장 프로그램을 로드합니다" 클릭
  4. Suno 폴더 선택
  5. Chrome 주소창 오른쪽 퍼즐 아이콘 → "Suno Helper" 핀 고정
  6. Suno Helper 아이콘 클릭 후 설정 입력:
     - GitHub Personal Access Token
     - GitHub Username
     - Repository Name
  7. Save 클릭

  ---

  ## 사용 방법

  ### suhbway.kr → Suno

  1. suhbway.kr/prompt_detail.php?id=번호 접속
  2. 오른쪽 하단 주황색 "Send to Suno" 버튼 클릭
  3. suno.com/create가 자동으로 열리고 필드가 채워짐
  4. 확인 후 Suno에서 Create 버튼으로 음악 생성

  ### Suno → GitHub

  1. suno.com 접속
  2. 곡 카드 왼쪽 위 체크박스 클릭으로 곡 선택 (복수 선택 가능)
  3. 오른쪽 하단 패널에서 Score 입력 (선택사항)
  4. "Save to Git" 클릭
  5. GitHub 레포의 songs/ 폴더에 Markdown 파일 생성

  ---

  ## 파일 구조

  | 파일 | 역할 |
  |------|------|
  | manifest.json | 확장 프로그램 설정 |
  | background.js | 탭 간 통신 |
  | content-suno.js | suno.com 기능 (곡 선택, Git 저장, 자동 세팅 수신 - phased fill) |
  | content-suhbway.js | suhbway.kr 기능 (데이터 추출, Send 버튼 - span/label 지원) |
  | styles.css | suno.com 스타일 |
  | styles-suhbway.css | suhbway.kr 스타일 |
  | popup.html | 설정 화면 |
  | popup.js | 설정 로직 |
  | icon48.png | 아이콘 |
  | icon128.png | 아이콘 |

  ---

  ## GitHub 저장 형식

  ### 개별 곡 파일 (songs/날짜_제목_ID.md)

  - 제목, 날짜, URL, Song ID, 점수
  - Prompt / Lyrics (코드 블록)
  - Style 정보

  ### README.md 히스토리 테이블

  | Date | Title | Score | URL |
  |------|-------|-------|-----|
  | 2026-03-10 | 곡제목 | 85 | Listen |

  ---

  ## 변경 이력

  ### v2.1.0 (2026-03-11)
  - **Auto-fill 개선**: Custom 모드 전환 후 최대 8초 대기하여 필드 렌더링 보장
  - **필드 탐지 강화**: `getFieldContext()`로 7레벨 부모까지 탐색, `aria-describedby`, `name` 속성 지원
  - **중복 입력 방지**: 이미 채운 필드는 재시도 시 건너뜀
  - **React 18+ 호환**: Fiber memoizedProps 리셋, `focusin`/`focusout` 이벤트, range 슬라이더 mouse 이벤트
  - **Exclude Styles 추출 수정**: `<span>`, `<label>` 태그의 라벨도 인식 (기존 `h2~h4`, `strong`만 지원)
  - **디버깅**: `[SunoHelper]` 콘솔 로그로 각 필드 입력 상태 확인 가능
