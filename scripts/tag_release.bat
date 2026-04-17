@echo off
REM MidiGPT — release tagging helper (Sprint 39 CCC5)
REM
REM git working tree 가 깨끗한지 확인 → tag 생성 → make_release.bat 호출.
REM 원격 push 는 사용자가 수동 (`git push origin <tag>`). 자동 푸시를 안
REM 하는 이유: 실수 방지.
REM
REM Usage:
REM   scripts\tag_release.bat 0.9.0-beta        - 태그 생성 + zip 번들
REM   scripts\tag_release.bat 0.9.0-beta --dry  - 검증만, 실제 태그 안 찍음

setlocal
cd /d "%~dp0\.."

set "VERSION=%~1"
if "%VERSION%"=="" (
    echo [ERROR] usage: scripts\tag_release.bat ^<version^> [--dry]
    echo         example: scripts\tag_release.bat 0.9.0-beta
    exit /b 1
)

set "DRY=0"
if /i "%~2"=="--dry" set "DRY=1"

set "TAG=v%VERSION%"

echo ============================================================
echo   MidiGPT Release Tagger  tag=%TAG%  dry=%DRY%
echo ============================================================

REM --- 1. git 작업 트리 clean? ---
for /f %%i in ('git status --porcelain') do (
    echo [ERROR] git working tree 가 dirty 합니다. commit 또는 stash 후 재시도.
    git status --short
    exit /b 1
)
echo [OK] git working tree clean

REM --- 2. 태그 중복 체크 ---
git rev-parse "%TAG%" >nul 2>&1
if not errorlevel 1 (
    echo [ERROR] 태그 %TAG% 이미 존재합니다.
    exit /b 1
)
echo [OK] tag %TAG% is new

REM --- 3. E2E + doctor 선행 확인 ---
echo [check] running doctor.py + e2e_test.py (--skip-audio) ...
py -3.10 scripts\doctor.py >nul 2>&1
if errorlevel 1 (
    echo [WARN] doctor.py 에 실패 항목 있음. 체크리스트 확인 권장.
    if "%DRY%"=="0" (
        set /p CONTINUE="그래도 태그를 찍을까요? [y/N] "
        if /i not "!CONTINUE!"=="y" exit /b 1
    )
) else (
    echo [OK] doctor.py passed
)

py -3.10 scripts\e2e_test.py --skip-audio >nul 2>&1
if errorlevel 1 (
    echo [WARN] e2e_test 실패. 서버가 기동 중인지 확인.
) else (
    echo [OK] e2e_test passed
)

if "%DRY%"=="1" (
    echo.
    echo [DRY RUN] 실제 태그/번들 안 만들고 종료.
    exit /b 0
)

REM --- 4. 태그 생성 ---
echo [tag] git tag -a %TAG%
git tag -a "%TAG%" -m "MidiGPT %TAG% - see CHANGELOG.md"
if errorlevel 1 (
    echo [ERROR] git tag 실패
    exit /b 1
)
echo [OK] tag created (locally). 원격 푸시는 수동:
echo      git push origin %TAG%

REM --- 5. zip 번들 ---
echo [bundle] make_release.bat %VERSION%
call "%~dp0\..\juce_daw_clean\..\scripts\make_release.bat" %VERSION%
if errorlevel 1 (
    echo [WARN] 번들 실패. 태그는 로컬에 찍혔으니 필요시 `git tag -d %TAG%`.
)

echo.
echo ============================================================
echo   완료. 다음:
echo     1. git push origin %TAG%
echo     2. GitHub Release 페이지에 zip 업로드
echo     3. CHANGELOG.md 의 [Unreleased] 섹션을 [%VERSION%] 로 확정
echo ============================================================
endlocal
