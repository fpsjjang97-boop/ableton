"""
AudioToMIDI EXE 빌드 스크립트

사용법:
    python build_exe.py

출력:
    dist/AudioToMIDI/AudioToMIDI.exe

동업자가 Python 설치 없이 실행 가능:
    AudioToMIDI.exe "노래.mp3"
    AudioToMIDI.exe ./music_folder --batch
"""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable


def build():
    print("=" * 60)
    print("  Building AudioToMIDI.exe")
    print("=" * 60)

    cmd = [
        PYTHON, "-m", "PyInstaller",
        "--name", "AudioToMIDI",
        "--onedir",
        "--console",           # CLI 도구이므로 콘솔 모드
        "--noconfirm",

        # ── Hidden imports (PyInstaller가 자동 감지 못하는 것들) ──
        # Demucs
        "--hidden-import", "demucs",
        "--hidden-import", "demucs.api",
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
        # TensorFlow Lite (basic-pitch backend)
        "--hidden-import", "tensorflow",
        "--hidden-import", "tensorflow.lite",
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

        # ── Collect submodules ──
        "--collect-submodules", "demucs",
        "--collect-submodules", "basic_pitch",

        # ── Collect data files (모델 가중치 등) ──
        "--collect-data", "demucs",
        "--collect-data", "basic_pitch",

        # ── Entry point ──
        os.path.join(SCRIPT_DIR, "convert.py"),
    ]

    try:
        subprocess.run(cmd, cwd=SCRIPT_DIR, check=True)
        print("\n" + "=" * 60)
        print("  빌드 성공!")
        print(f"  EXE: {SCRIPT_DIR}/dist/AudioToMIDI/AudioToMIDI.exe")
        print("=" * 60)
        print("\n사용법:")
        print('  AudioToMIDI.exe "노래.mp3"')
        print('  AudioToMIDI.exe ./music_folder --batch')
        print('  AudioToMIDI.exe "노래.mp3" --keep_vocals')
        print('  AudioToMIDI.exe "노래.mp3" --demucs_model htdemucs_ft')
    except subprocess.CalledProcessError as e:
        print(f"\n빌드 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    build()
