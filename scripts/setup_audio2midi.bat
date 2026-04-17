@echo off
REM MidiGPT — Audio2MIDI dependency installer (Windows)
REM
REM Sprint 37 이슈2.  Sprint 37.1 후속: basic-pitch 0.2.5 가 numpy<1.24
REM 를 강제해 Python 3.13 에서 ResolutionImpossible. Python 3.10/3.11 이
REM 실제로 동작하는 범위. 이 스크립트가 Python launcher 를 우선 사용해
REM 3.10/3.11 을 자동 선택한다. 그래도 없으면 시스템 python 으로 fallback.
REM
REM Usage:
REM   scripts\setup_audio2midi.bat         -  baseline
REM   scripts\setup_audio2midi.bat --all   -  baseline + Tier 1 optional

setlocal
cd /d "%~dp0\.."

REM --- Pick a compatible Python ---
REM Preference order: py -3.11, py -3.10, python (if in PATH).
set "PY="
py -3.11 -c "import sys; print(sys.version)" >nul 2>&1 && set "PY=py -3.11"
if not defined PY py -3.10 -c "import sys; print(sys.version)" >nul 2>&1 && set "PY=py -3.10"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [ERROR] 호환 Python 을 찾을 수 없습니다.
    echo         basic-pitch 0.2.5 는 numpy^<1.24 를 강제해 Python 3.13 과 호환되지 않습니다.
    echo         Python 3.10 또는 3.11 을 설치하세요:
    echo             https://www.python.org/downloads/release/python-3119/
    echo         또는 `py -3.10 -m venv venv` 로 가상환경 생성.
    exit /b 1
)

echo [setup] using: %PY%
%PY% -c "import sys; print(f'Python {sys.version.split()[0]} at {sys.executable}')"

echo [setup] baseline 의존성 설치...
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements-audio2midi.txt
if errorlevel 1 (
    echo [ERROR] baseline 설치 실패. 오류 로그 확인 후 재시도.
    echo        Python 3.13 이라면 `py -3.10 -m pip install ...` 로 3.10 강제.
    exit /b 1
)

if /i "%~1"=="--all" (
    echo.
    echo [setup] Tier 1 optional ^(magenta + ADTOF^) 설치...
    %PY% -m pip install "magenta>=2.1.4"
    %PY% -m pip install adtof
    echo.
    echo [setup] Tier 1 체크포인트는 scripts\download_checkpoints.py 로 별도 다운로드.
    echo        실행: %PY% scripts\download_checkpoints.py
)

echo.
echo [setup] 완료. 설치된 버전:
%PY% -c "import demucs, basic_pitch, librosa, pretty_midi; print(f'demucs={demucs.__version__}  basic_pitch={basic_pitch.__version__}  librosa={librosa.__version__}  pretty_midi={pretty_midi.__version__}')" 2>nul

echo.
echo 다음 단계: %PY% scripts\doctor.py 로 전체 준비 상태 확인.
endlocal
