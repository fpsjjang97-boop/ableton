"""
Build script for MIDI AI Workstation executables.

Creates three EXE files:
1. MidiAIWorkstation.exe — Main application
2. MidiIngest.exe — Auto-ingest tool for adding MIDI to DB
3. PatternExtractor.exe — GUI tool for pattern extraction (v2.09 Rule DB)

Usage:
    python build_exe.py
"""
import subprocess
import sys
import os

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable


def build_main_app():
    """Build the main MIDI AI Workstation application."""
    print("=" * 60)
    print("Building MIDI AI Workstation...")
    print("=" * 60)

    cmd = [
        PYTHON, "-m", "PyInstaller",
        "--name", "MidiAIWorkstation",
        "--onedir",
        "--windowed",
        "--noconfirm",
        # Add data files
        "--add-data", f"{REPO_ROOT}/260327_최종본_v2.07_song_form_added.json;.",
        "--add-data", f"{REPO_ROOT}/settings.json;.",
        "--add-data", f"{REPO_ROOT}/pattern_library;pattern_library",
        "--add-data", f"{REPO_ROOT}/embeddings;embeddings",
        "--add-data", f"{REPO_ROOT}/analyzed_chords;analyzed_chords",
        # Hidden imports
        "--hidden-import", "numpy",
        "--hidden-import", "mido",
        "--hidden-import", "PyQt6",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        # Paths
        "--paths", f"{REPO_ROOT}/app",
        # Entry point
        f"{REPO_ROOT}/app/main.py",
    ]

    subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    print("\nMain app built: dist/MidiAIWorkstation/MidiAIWorkstation.exe")


def build_ingest_tool():
    """Build the auto-ingest CLI tool."""
    print("=" * 60)
    print("Building MIDI Ingest Tool...")
    print("=" * 60)

    cmd = [
        PYTHON, "-m", "PyInstaller",
        "--name", "MidiIngest",
        "--onefile",
        "--console",
        "--noconfirm",
        # Add data files
        "--add-data", f"{REPO_ROOT}/260327_최종본_v2.07_song_form_added.json;.",
        "--add-data", f"{REPO_ROOT}/pattern_library;pattern_library",
        "--add-data", f"{REPO_ROOT}/analyzed_chords;analyzed_chords",
        # Hidden imports
        "--hidden-import", "numpy",
        "--hidden-import", "mido",
        # Paths
        "--paths", f"{REPO_ROOT}/app",
        "--paths", f"{REPO_ROOT}/tools",
        # Entry point
        f"{REPO_ROOT}/tools/auto_ingest.py",
    ]

    subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    print("\nIngest tool built: dist/MidiIngest.exe")


def build_pattern_extractor():
    """Build the Pattern Extractor GUI tool."""
    print("=" * 60)
    print("Building MIDI Pattern Extractor...")
    print("=" * 60)

    rule_db_v209 = "260329_최종본_v2.09_analysis_no_unobserved_7th_guardrail.json"

    cmd = [
        PYTHON, "-m", "PyInstaller",
        "--name", "PatternExtractor",
        "--onefile",
        "--windowed",
        "--noconfirm",
        # Add data files — v2.09 Rule DB
        "--add-data", f"{REPO_ROOT}/{rule_db_v209};.",
        # Also include v2.07 for HarmonyEngine fallback
        "--add-data", f"{REPO_ROOT}/260327_최종본_v2.07_song_form_added.json;.",
        "--add-data", f"{REPO_ROOT}/pattern_library;pattern_library",
        "--add-data", f"{REPO_ROOT}/analyzed_chords;analyzed_chords",
        # Hidden imports
        "--hidden-import", "numpy",
        "--hidden-import", "mido",
        "--hidden-import", "pretty_midi",
        "--hidden-import", "PyQt6",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        # Paths
        "--paths", f"{REPO_ROOT}/app",
        "--paths", f"{REPO_ROOT}/tools",
        # Entry point
        f"{REPO_ROOT}/tools/pattern_extractor_app.py",
    ]

    subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    print("\nPattern Extractor built: dist/PatternExtractor.exe")


if __name__ == "__main__":
    build_main_app()
    print()
    build_ingest_tool()
    print()
    build_pattern_extractor()
    print()
    print("=" * 60)
    print("BUILD COMPLETE")
    print(f"  Main app:           {REPO_ROOT}/dist/MidiAIWorkstation/MidiAIWorkstation.exe")
    print(f"  Ingest tool:        {REPO_ROOT}/dist/MidiIngest.exe")
    print(f"  Pattern Extractor:  {REPO_ROOT}/dist/PatternExtractor.exe")
    print("=" * 60)
