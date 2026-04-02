"""
AudioToMIDI EXE 빌드 스크립트

사용법:
    python build_exe.py

출력:
    dist/AudioToMIDI/AudioToMIDI.exe  (GUI 앱)

동업자가 Python 설치 없이 더블클릭으로 실행 가능.
"""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable


def build():
    print("=" * 60)
    print("  Building AudioToMIDI.exe (GUI)")
    print("=" * 60)

    cmd = [
        PYTHON, "-m", "PyInstaller",
        "--name", "AudioToMIDI",
        "--onedir",
        "--windowed",          # GUI 모드 (콘솔 창 없음)
        "--noconfirm",

        # ── Hidden imports ──
        # Demucs
        "--hidden-import", "demucs",
        "--hidden-import", "demucs.separate",
        "--hidden-import", "demucs.apply",
        "--hidden-import", "demucs.hdemucs",
        "--hidden-import", "demucs.htdemucs",
        "--hidden-import", "demucs.pretrained",
        "--hidden-import", "demucs.states",
        "--hidden-import", "demucs.spec",
        "--hidden-import", "demucs.utils",
        # Basic Pitch
        "--hidden-import", "basic_pitch",
        "--hidden-import", "basic_pitch.inference",
        "--hidden-import", "basic_pitch.note_creation",
        # ONNX Runtime (basic-pitch backend)
        "--hidden-import", "onnxruntime",
        # PyTorch (Demucs backend)
        "--hidden-import", "torch",
        "--hidden-import", "torchaudio",
        "--hidden-import", "torchaudio.transforms",
        # Audio I/O
        "--hidden-import", "soundfile",
        "--hidden-import", "librosa",
        # MIDI
        "--hidden-import", "pretty_midi",
        "--hidden-import", "mido",
        "--hidden-import", "numpy",
        # GUI
        "--hidden-import", "tkinter",

        # ── Collect submodules ──
        "--collect-submodules", "demucs",
        "--collect-submodules", "basic_pitch",

        # ── Collect data files (모델 가중치 등) ──
        "--collect-data", "demucs",
        "--collect-data", "basic_pitch",

        # ── Additional source ──
        "--add-data", os.path.join(SCRIPT_DIR, "convert.py") + ";.",

        # ── Entry point ──
        os.path.join(SCRIPT_DIR, "gui.py"),
    ]

    try:
        subprocess.run(cmd, cwd=SCRIPT_DIR, check=True)
        print("\n" + "=" * 60)
        print("  빌드 성공!")
        print(f"  EXE: {SCRIPT_DIR}/dist/AudioToMIDI/AudioToMIDI.exe")
        print("=" * 60)
        print("\n사용법: AudioToMIDI.exe 더블클릭 → 파일 선택 → 변환 시작")
    except subprocess.CalledProcessError as e:
        print(f"\n빌드 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    build()
