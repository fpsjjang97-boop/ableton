"""
MIDI AI Workstation — MIDI 파일을 자동으로 로드하여 실행
사용법: python launch_with_midi.py [midi_file_path]
"""
import sys
import os

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor

from config import APP_NAME, APP_VERSION, APP_ORG, COLORS


def main():
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    app.setApplicationVersion(APP_VERSION)

    # Dark palette
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg_darkest"]))
    p.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text_primary"]))
    p.setColor(QPalette.ColorRole.Base, QColor(COLORS["bg_input"]))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["bg_mid"]))
    p.setColor(QPalette.ColorRole.Text, QColor(COLORS["text_primary"]))
    p.setColor(QPalette.ColorRole.Button, QColor(COLORS["bg_mid"]))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text_primary"]))
    p.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["bg_selected"]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(COLORS["text_primary"]))
    app.setPalette(p)

    from ui.styles import get_stylesheet
    app.setStyleSheet(get_stylesheet())
    app.setFont(QFont("Segoe UI", 10))

    from PyQt6.QtWidgets import (
        QMainWindow, QDockWidget, QWidget, QVBoxLayout, QSplitter,
        QLabel, QFileDialog,
    )
    from PyQt6.QtGui import QAction, QKeySequence

    from core.midi_engine import MidiEngine
    from core.audio_engine import AudioEngine
    from core.project import ProjectManager
    from core.ai_engine import AIEngine
    from core.models import (
        Note, Track, ProjectState, UndoManager, TICKS_PER_BEAT,
        TRACK_COLORS, key_name_to_root,
    )
    from ui.transport import TransportWidget
    from ui.session_view import SessionView
    from ui.detail_view import DetailView
    from ui.file_browser import FileBrowser
    import copy

    # --- Main window ---
    w = QMainWindow()
    w.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
    w.setMinimumSize(1280, 720)
    w.resize(1600, 900)

    # --- Engines ---
    midi_engine = MidiEngine(w)
    audio_engine = AudioEngine()
    midi_engine.set_audio_engine(audio_engine)  # FluidSynth 연동
    if audio_engine.available and hasattr(audio_engine, '_synth') and audio_engine._synth:
        try:
            audio_engine._synth.start(driver='dsound')
        except Exception:
            pass
    project_mgr = ProjectManager(w)
    ai_engine = AIEngine()
    undo_mgr = UndoManager()
    selected_track = [0]

    # --- Widgets ---
    transport = TransportWidget()
    transport.setFixedHeight(36)
    session_view = SessionView()
    detail_view = DetailView()
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_browser = FileBrowser(root_path=_repo_root)

    # --- Layout ---
    splitter = QSplitter(Qt.Orientation.Vertical)
    splitter.addWidget(session_view)
    splitter.addWidget(detail_view)
    splitter.setStretchFactor(0, 3)
    splitter.setStretchFactor(1, 1)

    central = QWidget()
    cl = QVBoxLayout(central)
    cl.setContentsMargins(0, 0, 0, 0)
    cl.setSpacing(0)
    cl.addWidget(transport)
    cl.addWidget(splitter, 1)
    w.setCentralWidget(central)

    dock_browser = QDockWidget("Browser", w)
    dock_browser.setWidget(file_browser)
    dock_browser.setMinimumWidth(220)
    w.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_browser)

    # Status bar
    status = QLabel("  Ready")
    w.statusBar().addWidget(status, 1)

    # --- Helpers ---
    def project():
        return project_mgr.state

    def apply_project(proj):
        midi_engine.project = proj
        transport.set_project(proj)
        session_view.set_project(proj)
        detail_view.set_project(proj)
        if proj.tracks:
            selected_track[0] = 0
            detail_view.set_track(proj.tracks[0], 0)
        undo_mgr.clear()
        tn = len(proj.tracks)
        nn = sum(len(t.notes) for t in proj.tracks)
        name = proj.name or "Untitled"
        w.setWindowTitle(f"{name} - {APP_NAME} v{APP_VERSION}")
        status.setText(f"  {tn} tracks | {nn} notes | {proj.bpm} BPM | {proj.key} {proj.scale}")

    # --- Menu ---
    menubar = w.menuBar()

    file_menu = menubar.addMenu("&File")
    act_import = file_menu.addAction("&Import MIDI...")
    act_import.setShortcut(QKeySequence("Ctrl+I"))

    act_export = file_menu.addAction("&Export MIDI...")
    act_export.setShortcut(QKeySequence("Ctrl+E"))

    file_menu.addSeparator()
    act_quit = file_menu.addAction("&Quit")
    act_quit.setShortcut(QKeySequence("Ctrl+Q"))

    ai_menu = menubar.addMenu("&AI")
    act_gen_melody = ai_menu.addAction("Generate &Melody")
    act_gen_chords = ai_menu.addAction("Generate &Chords")
    act_gen_bass = ai_menu.addAction("Generate &Bass")

    def import_midi():
        path, _ = QFileDialog.getOpenFileName(w, "Import MIDI", "", "MIDI (*.mid *.midi)")
        if path:
            project_mgr.import_midi(path)
            apply_project(project_mgr.state)

    def export_midi():
        path, _ = QFileDialog.getSaveFileName(w, "Export MIDI", "", "MIDI (*.mid)")
        if path:
            midi_engine.save_midi_file(path)

    def generate_track(kind):
        p = project()
        if kind == "melody":
            t = ai_engine.generate_melody(p.key, p.scale, 32, "pop", 0.7)
        elif kind == "chords":
            t = ai_engine.generate_chords(p.key, p.scale, 32, "pop")
        else:
            t = ai_engine.generate_bass(p.key, p.scale, 32, "pop")
        t.color = TRACK_COLORS[len(p.tracks) % len(TRACK_COLORS)]
        p.tracks.append(t)
        apply_project(p)

    act_import.triggered.connect(import_midi)
    act_export.triggered.connect(export_midi)
    act_quit.triggered.connect(w.close)
    act_gen_melody.triggered.connect(lambda: generate_track("melody"))
    act_gen_chords.triggered.connect(lambda: generate_track("chords"))
    act_gen_bass.triggered.connect(lambda: generate_track("bass"))

    # Transport signals
    transport.play_clicked.connect(midi_engine.toggle_playback)
    transport.stop_clicked.connect(midi_engine.stop)
    transport.rewind_clicked.connect(lambda: midi_engine.seek(0))

    def on_bpm(val):
        project().bpm = val
    transport.bpm_changed.connect(on_bpm)

    def on_position(tick):
        transport.update_position(tick, project())
        detail_view.update_playhead(tick)
    midi_engine.position_changed.connect(on_position)

    def on_playback_state(state):
        transport.set_playing(state == "playing")
    midi_engine.playback_state_changed.connect(on_playback_state)

    # Session/Detail signals
    def on_track_selected(idx):
        selected_track[0] = idx
        p = project()
        if 0 <= idx < len(p.tracks):
            detail_view.set_track(p.tracks[idx], idx)
    session_view.track_selected.connect(on_track_selected)

    def on_file_activated(path):
        if path.endswith((".mid", ".midi")):
            project_mgr.import_midi(path)
            apply_project(project_mgr.state)
    file_browser.file_double_clicked.connect(on_file_activated)

    # --- Auto-load MIDI file ---
    midi_path = None
    if len(sys.argv) > 1:
        midi_path = sys.argv[1]
    else:
        # 가장 최근 생성된 MIDI 파일 자동 로드
        output_dir = os.path.join(_repo_root, "output")
        if os.path.isdir(output_dir):
            mid_files = sorted(
                [f for f in os.listdir(output_dir) if f.endswith(".mid")],
                key=lambda f: os.path.getmtime(os.path.join(output_dir, f)),
                reverse=True,
            )
            if mid_files:
                midi_path = os.path.join(output_dir, mid_files[0])

    if midi_path and os.path.isfile(midi_path):
        print(f"Loading: {midi_path}")
        project_mgr.import_midi(midi_path)
        apply_project(project_mgr.state)

    # --- Show ---
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
