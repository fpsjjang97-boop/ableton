"""Launch the app with Midnight Reverie MIDI pre-loaded."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import faulthandler
faulthandler.enable()

from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)

# Apply theme
from ui.styles import get_stylesheet
from PyQt6.QtGui import QFont, QPalette, QColor
from config import COLORS, APP_NAME, APP_VERSION

app.setStyleSheet(get_stylesheet())
p = QPalette()
for role, color_key in [
    (QPalette.ColorRole.Window, "bg_darkest"),
    (QPalette.ColorRole.WindowText, "text_primary"),
    (QPalette.ColorRole.Base, "bg_input"),
    (QPalette.ColorRole.Text, "text_primary"),
    (QPalette.ColorRole.Button, "bg_mid"),
    (QPalette.ColorRole.ButtonText, "text_primary"),
    (QPalette.ColorRole.Highlight, "bg_selected"),
    (QPalette.ColorRole.HighlightedText, "text_primary"),
]:
    p.setColor(role, QColor(COLORS[color_key]))
app.setPalette(p)
app.setFont(QFont("Segoe UI", 10))

# Build window
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QVBoxLayout, QSplitter,
    QLabel, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from core.midi_engine import MidiEngine
from core.audio_engine import AudioEngine
from core.project import ProjectManager
from core.ai_engine import AIEngine
from core.models import (
    Note, Track, ProjectState, UndoManager, TICKS_PER_BEAT, TRACK_COLORS,
)
from ui.transport import TransportWidget
from ui.session_view import SessionView
from ui.detail_view import DetailView
from ui.file_browser import FileBrowser
import copy, random

w = QMainWindow()
w.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
w.setMinimumSize(1280, 720)
w.resize(1600, 900)
w.setDockNestingEnabled(True)

# Engines
midi_engine = MidiEngine(w)
audio_engine = AudioEngine()
project_mgr = ProjectManager(w)
ai_engine = AIEngine()
undo_mgr = UndoManager()
selected_track = [0]

# Widgets
transport = TransportWidget()
transport.setFixedHeight(36)
session_view = SessionView()
detail_view = DetailView()
file_browser = FileBrowser(root_path="E:/Ableton/repo")

# Layout
splitter = QSplitter(Qt.Orientation.Vertical)
splitter.setHandleWidth(3)
splitter.addWidget(session_view)
splitter.addWidget(detail_view)
splitter.setStretchFactor(0, 3)
splitter.setStretchFactor(1, 1)
splitter.setSizes([600, 280])

central = QWidget()
cl = QVBoxLayout(central)
cl.setContentsMargins(0, 0, 0, 0)
cl.setSpacing(0)
cl.addWidget(transport)
cl.addWidget(splitter, 1)
w.setCentralWidget(central)

dock = QDockWidget("Browser", w)
dock.setWidget(file_browser)
dock.setMinimumWidth(220)
dock.setFeatures(
    QDockWidget.DockWidgetFeature.DockWidgetClosable
    | QDockWidget.DockWidgetFeature.DockWidgetMovable
    | QDockWidget.DockWidgetFeature.DockWidgetFloatable
)
w.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

# Status bar
status_left = QLabel(f"  {APP_NAME}")
status_center = QLabel("")
status_right = QLabel("MIDI Engine: Ready  ")
sb = w.statusBar()
sb.addWidget(status_left, 1)
sb.addWidget(status_center, 1)
sb.addPermanentWidget(status_right)


# --- Helpers ---
def project():
    return project_mgr.state

def update_title():
    name = project().name or "Untitled"
    mod = " *" if project().modified else ""
    w.setWindowTitle(f"{name}{mod} - {APP_NAME} v{APP_VERSION}")

def update_status():
    proj = project()
    tn = len(proj.tracks)
    nn = sum(len(t.notes) for t in proj.tracks)
    dur = proj.total_seconds
    status_center.setText(f"{tn} tracks | {nn} notes | {int(dur//60)}:{int(dur%60):02d}")

def apply_project(proj):
    midi_engine.project = proj
    transport.set_project(proj)
    session_view.set_project(proj)
    detail_view.set_project(proj)
    if proj.tracks:
        selected_track[0] = 0
        detail_view.set_track(proj.tracks[0], 0)
        detail_view.show_tab("notes")
    undo_mgr.clear()
    update_title()
    update_status()

def mark_modified():
    project().modified = True
    update_title()
    update_status()


# --- Load MIDI ---
midi_path = "E:/Ableton/repo/app/output/midnight_reverie_75bpm_Am.mid"
if os.path.exists(midi_path):
    project_mgr.import_midi(midi_path)
    proj = project_mgr.state
    proj.name = "Midnight Reverie"
    proj.key = "A"
    proj.scale = "minor"
    proj.bpm = 75.0
    print(f"Loaded: {proj.name}")
    print(f"Tracks: {len(proj.tracks)}")
    for t in proj.tracks:
        print(f"  {t.name}: {len(t.notes)} notes")
    print(f"Duration: {int(proj.total_seconds//60)}:{int(proj.total_seconds%60):02d}")
else:
    print(f"MIDI not found: {midi_path}")


# --- Signals ---
transport.play_clicked.connect(midi_engine.toggle_playback)
transport.stop_clicked.connect(midi_engine.stop)
transport.rewind_clicked.connect(lambda: midi_engine.seek(0))

def on_bpm(v):
    project().bpm = v
    mark_modified()
transport.bpm_changed.connect(on_bpm)

def on_key(k):
    project().key = k
    mark_modified()
transport.key_changed.connect(on_key)

def on_scale(s):
    project().scale = s
    mark_modified()
transport.scale_changed.connect(on_scale)

def on_position(tick):
    transport.update_position(tick, project())
    detail_view.update_playhead(tick)
midi_engine.position_changed.connect(on_position)
midi_engine.playback_state_changed.connect(lambda s: transport.set_playing(s == "playing"))

def on_track_selected(idx):
    selected_track[0] = idx
    proj = project()
    if 0 <= idx < len(proj.tracks):
        detail_view.set_track(proj.tracks[idx], idx)
session_view.track_selected.connect(on_track_selected)

def on_clip_opened(t_idx, s_idx):
    detail_view.show_tab("notes")
    proj = project()
    if 0 <= t_idx < len(proj.tracks):
        detail_view.set_track(proj.tracks[t_idx], t_idx)
session_view.clip_opened.connect(on_clip_opened)

def on_file_activated(path):
    if path.endswith(".maw"):
        project_mgr.load_project(path)
        apply_project(project_mgr.state)
    elif path.endswith((".mid", ".midi")):
        project_mgr.import_midi(path)
        apply_project(project_mgr.state)
file_browser.file_double_clicked.connect(on_file_activated)

# AI signals
def on_generate(params):
    proj = project()
    kind = params.get("type", "melody").lower()
    if kind == "chords":
        t = ai_engine.generate_chords(proj.key, proj.scale, 32, "pop")
    elif kind == "bass":
        t = ai_engine.generate_bass(proj.key, proj.scale, 32, "pop")
    else:
        t = ai_engine.generate_melody(proj.key, proj.scale, 32, "pop", 0.7)
    t.color = TRACK_COLORS[len(proj.tracks) % len(TRACK_COLORS)]
    proj.tracks.append(t)
    mark_modified()
    session_view.refresh()
    detail_view.set_track(t, len(proj.tracks) - 1)
detail_view.generate_requested.connect(on_generate)

def on_variation(params):
    proj = project()
    idx = selected_track[0]
    if 0 <= idx < len(proj.tracks):
        var = ai_engine.generate_variation(proj.tracks[idx], "mixed", 0.5, proj.key, proj.scale)
        var.name = f"{proj.tracks[idx].name} (var)"
        var.color = TRACK_COLORS[len(proj.tracks) % len(TRACK_COLORS)]
        proj.tracks.append(var)
        mark_modified()
        session_view.refresh()
detail_view.variation_requested.connect(on_variation)

def on_humanize(timing, velocity):
    proj = project()
    idx = selected_track[0]
    if 0 <= idx < len(proj.tracks):
        result = ai_engine.humanize(proj.tracks[idx], timing, velocity)
        proj.tracks[idx].notes = result.notes
        mark_modified()
        detail_view.set_track(proj.tracks[idx], idx)
detail_view.humanize_requested.connect(on_humanize)

def analyze_track_fn():
    proj = project()
    idx = selected_track[0]
    if 0 <= idx < len(proj.tracks):
        analysis = ai_engine.analyze_track(proj.tracks[idx], proj.key, proj.scale)
        detail_view.show_tab("analysis")
        rp = detail_view._review_panel
        if hasattr(rp, "show_review"):
            rp.show_review(analysis)
detail_view.analyze_requested.connect(analyze_track_fn)

if hasattr(detail_view, "note_added"):
    detail_view.note_added.connect(lambda n: update_status())
if hasattr(detail_view, "note_removed"):
    detail_view.note_removed.connect(lambda n: update_status())
if hasattr(detail_view, "note_modified"):
    detail_view.note_modified.connect(lambda n: update_status())

# Mixer signals
if hasattr(session_view, "mixer_volume_changed"):
    def _vol(i, v):
        proj = project()
        if 0 <= i < len(proj.tracks):
            proj.tracks[i].volume = v
    session_view.mixer_volume_changed.connect(_vol)

if hasattr(session_view, "mixer_mute_toggled"):
    def _mute(i):
        proj = project()
        if 0 <= i < len(proj.tracks):
            proj.tracks[i].muted = not proj.tracks[i].muted
    session_view.mixer_mute_toggled.connect(_mute)

if hasattr(session_view, "mixer_solo_toggled"):
    def _solo(i):
        proj = project()
        if 0 <= i < len(proj.tracks):
            proj.tracks[i].solo = not proj.tracks[i].solo
    session_view.mixer_solo_toggled.connect(_solo)

if hasattr(session_view, "mixer_pan_changed"):
    def _pan(i, v):
        proj = project()
        if 0 <= i < len(proj.tracks):
            proj.tracks[i].pan = v
    session_view.mixer_pan_changed.connect(_pan)

# VU meter
def simulate_meters():
    proj = project()
    if midi_engine.state != "playing":
        session_view.update_meters([0.0] * len(proj.tracks))
        return
    levels = [
        (t.volume / 127.0) * 0.7 + random.uniform(0.0, 0.25) if not t.muted else 0.0
        for t in proj.tracks
    ]
    session_view.update_meters(levels)

meter_timer = QTimer(w)
meter_timer.timeout.connect(simulate_meters)
meter_timer.start(80)

# Menus
menubar = w.menuBar()
file_menu = menubar.addMenu("&File")
file_menu.addAction("&New Project", lambda: (project_mgr.new_project(), apply_project(project_mgr.state)))

def _import_midi():
    path, _ = QFileDialog.getOpenFileName(w, "Import MIDI", "", "MIDI Files (*.mid *.midi);;All (*)")
    if path:
        project_mgr.import_midi(path)
        apply_project(project_mgr.state)
file_menu.addAction("&Import MIDI...", _import_midi)

def _export_midi():
    path, _ = QFileDialog.getSaveFileName(w, "Export MIDI", "", "MIDI Files (*.mid);;All (*)")
    if path:
        midi_engine.save_midi_file(path)
        sb.showMessage(f"Exported: {path}", 4000)
file_menu.addAction("&Export MIDI...", _export_midi)
file_menu.addSeparator()
file_menu.addAction("&Quit", w.close)

create_menu = menubar.addMenu("&Create")
create_menu.addAction("Add &MIDI Track", lambda: (
    project().tracks.append(Track(
        name=f"Track {len(project().tracks)+1}",
        channel=min(len(project().tracks), 15),
        color=TRACK_COLORS[len(project().tracks) % len(TRACK_COLORS)],
    )),
    mark_modified(),
    session_view.refresh(),
))

ai_menu = menubar.addMenu("&AI")
ai_menu.addAction("Generate &Melody", lambda: on_generate({"type": "melody"}))
ai_menu.addAction("Generate &Chords", lambda: on_generate({"type": "chords"}))
ai_menu.addAction("Generate &Bass", lambda: on_generate({"type": "bass"}))
ai_menu.addSeparator()
ai_menu.addAction("Generate &Variation", lambda: on_variation({}))
ai_menu.addSeparator()
ai_menu.addAction("&Analyze Track", analyze_track_fn)

view_menu = menubar.addMenu("&View")
view_menu.addAction("Toggle &Browser", lambda: dock.setVisible(not dock.isVisible()))
view_menu.addAction("Toggle &Detail", detail_view.toggle_collapse)

help_menu = menubar.addMenu("&Help")
help_menu.addAction("&About", lambda: QMessageBox.about(
    w, "About", f"{APP_NAME} v{APP_VERSION}\n\nAI-powered MIDI Workstation\n\nMidnight Reverie demo loaded."
))

# Apply and show
apply_project(project_mgr.state)
w.show()
sb.showMessage("Midnight Reverie loaded - Click tracks to view notes, use AI menu to generate", 8000)

sys.exit(app.exec())
