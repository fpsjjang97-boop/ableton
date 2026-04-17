@echo off
REM MidiGPT — Windows release bundler (Sprint 38 BBB5)
REM
REM 사용자에게 내보낼 압축 파일 한 개를 만든다:
REM   MidiGPT-<version>-win64.zip
REM     ├── MidiGPT.vst3/              ← 호스트용 VST3 번들
REM     ├── MidiGPT-Standalone.exe     ← 호스트 없이 독립 실행
REM     ├── scripts/                   ← doctor / setup / download / e2e / build_env
REM     ├── docs/                      ← business / samples / README
REM     ├── requirements-audio2midi.txt
REM     ├── LICENSE (있으면)
REM     └── README.md
REM
REM 체크포인트 (.pt, ~577MB) 와 midi_data_combined 은 포함하지 않음 — 별도 배포.
REM
REM Usage:
REM   scripts\make_release.bat          - 기본 Release 빌드 번들링
REM   scripts\make_release.bat v0.9.0   - 버전명 지정 (zip 파일명에 반영)
REM
REM 전제: juce_daw_clean\build.bat 이 이미 성공적으로 실행된 상태.

setlocal enabledelayedexpansion
cd /d "%~dp0\.."

set "VERSION=%~1"
if "%VERSION%"=="" set "VERSION=dev"

set "STAGING=build\release\MidiGPT-%VERSION%-win64"
set "ZIPFILE=build\release\MidiGPT-%VERSION%-win64.zip"

echo ============================================================
echo   MidiGPT Release Bundler  version=%VERSION%
echo ============================================================

REM --- Preflight: 필수 아티팩트 존재 ---
set "VST3=juce_daw_clean\build\MidiGPTPlugin_artefacts\Release\VST3\MidiGPT.vst3"
set "SA_EXE=juce_daw_clean\build\MidiGPTPlugin_artefacts\Release\Standalone\MidiGPT.exe"

if not exist "%VST3%" (
    echo [ERROR] VST3 번들 없음: %VST3%
    echo         먼저 juce_daw_clean\build.bat 실행.
    exit /b 1
)
if not exist "%SA_EXE%" (
    echo [ERROR] Standalone EXE 없음: %SA_EXE%
    exit /b 1
)

REM --- Clean staging ---
if exist "%STAGING%" rmdir /s /q "%STAGING%"
mkdir "%STAGING%"
mkdir "%STAGING%\scripts"
mkdir "%STAGING%\docs"

REM --- Copy artifacts ---
echo [1/6] VST3 bundle...
xcopy /E /I /Y "%VST3%" "%STAGING%\MidiGPT.vst3" >nul

echo [2/6] Standalone EXE...
copy /Y "%SA_EXE%" "%STAGING%\MidiGPT-Standalone.exe" >nul

echo [3/6] Scripts (doctor / setup / e2e / build_env)...
copy /Y "scripts\doctor.py" "%STAGING%\scripts\" >nul
copy /Y "scripts\setup_audio2midi.bat" "%STAGING%\scripts\" >nul
copy /Y "scripts\setup_audio2midi.sh" "%STAGING%\scripts\" >nul
copy /Y "scripts\download_checkpoints.py" "%STAGING%\scripts\" >nul
copy /Y "scripts\setup_build_env.bat" "%STAGING%\scripts\" >nul
copy /Y "scripts\e2e_test.py" "%STAGING%\scripts\" >nul

echo [4/6] Docs...
xcopy /E /I /Y "docs\business" "%STAGING%\docs\business" >nul
xcopy /E /I /Y "docs\samples" "%STAGING%\docs\samples" >nul 2>&1

echo [5/6] Root files...
copy /Y "requirements-audio2midi.txt" "%STAGING%\" >nul
if exist "README.md" copy /Y "README.md" "%STAGING%\" >nul
if exist "LICENSE"   copy /Y "LICENSE"   "%STAGING%\" >nul

REM --- Zip ---
echo [6/6] Compressing...
if exist "%ZIPFILE%" del "%ZIPFILE%"
REM PowerShell Compress-Archive (Win10+ 기본)
powershell -NoProfile -Command "Compress-Archive -Path '%STAGING%\*' -DestinationPath '%ZIPFILE%' -Force"
if errorlevel 1 (
    echo [ERROR] zip 생성 실패.
    exit /b 1
)

for %%F in ("%ZIPFILE%") do set "SZ=%%~zF"
set /a "SZMB=SZ/1048576"
echo.
echo ============================================================
echo   Release bundle ready:
echo     %ZIPFILE%
echo     size: %SZMB% MB
echo.
echo   다음:
echo     - 서버 / 체크포인트는 별도 배포 ^(553 MB 초과^)
echo     - 사용자 플로우: 압축 해제 → scripts\setup_audio2midi.bat →
echo                     python scripts\doctor.py → 실행
echo ============================================================
endlocal
