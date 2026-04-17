#!/usr/bin/env bash
# MidiGPT — Audio2MIDI dependency installer (Linux / macOS mirror of the .bat)
# Sprint 37 이슈2.

set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python not found. activate venv first."
    exit 1
fi
PY="${PYTHON:-$(command -v python3 || command -v python)}"

echo "[setup] baseline 의존성 설치..."
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r requirements-audio2midi.txt

if [[ "${1:-}" == "--all" ]]; then
    echo
    echo "[setup] Tier 1 optional (magenta + ADTOF) 설치..."
    "$PY" -m pip install "magenta>=2.1.4" adtof
    echo
    echo "[setup] Tier 1 체크포인트는 scripts/download_checkpoints.py 로 별도 다운로드."
fi

echo
echo "[setup] 완료. 다음 단계: $PY scripts/doctor.py"
