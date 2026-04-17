@echo off
REM MidiGPT — Audio2MIDI dependency installer (Windows)
REM
REM Runs `pip install -r requirements-audio2midi.txt` in the current
REM Python environment, plus the optional Tier 1 upgrades (magenta/ADTOF)
REM if the user opts in.
REM
REM Usage:
REM   scripts\setup_audio2midi.bat         -  baseline (Demucs + Basic Pitch)
REM   scripts\setup_audio2midi.bat --all   -  baseline + magenta + ADTOF
REM
REM Sprint 37 이슈2.

setlocal
cd /d "%~dp0\.."

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] python not found in PATH.
    echo         venv 활성화 확인 ^(예: .\venv\Scripts\activate.bat^).
    exit /b 1
)

echo [setup] baseline 의존성 설치...
python -m pip install --upgrade pip
python -m pip install -r requirements-audio2midi.txt
if errorlevel 1 (
    echo [ERROR] baseline 설치 실패. 오류 로그 확인 후 재시도.
    exit /b 1
)

if /i "%~1"=="--all" (
    echo.
    echo [setup] Tier 1 optional ^(magenta + ADTOF^) 설치...
    python -m pip install "magenta>=2.1.4"
    python -m pip install adtof
    echo.
    echo [setup] Tier 1 체크포인트는 scripts\download_checkpoints.py 로 별도 다운로드.
    echo        실행: python scripts\download_checkpoints.py
)

echo.
echo [setup] 완료. 설치된 버전:
python -c "import demucs, basic_pitch, librosa, pretty_midi; print(f'demucs={demucs.__version__}  basic_pitch={basic_pitch.__version__}  librosa={librosa.__version__}  pretty_midi={pretty_midi.__version__}')" 2>nul

echo.
echo 다음 단계: python scripts\doctor.py 로 전체 준비 상태 확인.
endlocal
