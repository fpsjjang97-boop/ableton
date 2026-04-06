"""
MIDI AI Workstation — main entry point.
"""
from __future__ import annotations

import sys
import os
import traceback
from pathlib import Path

# PyInstaller --windowed sets sys.stderr/stdout to None
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")

import faulthandler
try:
    faulthandler.enable()
except Exception:
    pass

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor

from config import APP_NAME, APP_VERSION, APP_ORG, COLORS


def _build_dark_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(COLORS["bg_darkest"]))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(COLORS["text_primary"]))
    p.setColor(QPalette.ColorRole.Base,            QColor(COLORS["bg_input"]))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(COLORS["bg_mid"]))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(COLORS["bg_panel"]))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(COLORS["text_primary"]))
    p.setColor(QPalette.ColorRole.Text,            QColor(COLORS["text_primary"]))
    p.setColor(QPalette.ColorRole.Button,          QColor(COLORS["bg_mid"]))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(COLORS["text_primary"]))
    p.setColor(QPalette.ColorRole.BrightText,      QColor(COLORS["accent"]))
    p.setColor(QPalette.ColorRole.Link,            QColor(COLORS["accent_secondary"]))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(COLORS["bg_selected"]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(COLORS["text_primary"]))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS["text_dim"]))
    return p


def main() -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    app.setApplicationVersion(APP_VERSION)

    from ui.styles import get_stylesheet
    app.setStyleSheet(get_stylesheet())
    app.setPalette(_build_dark_palette())
    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI", 10))
    elif sys.platform == "darwin":
        app.setFont(QFont("SF Pro", 11))
    else:
        app.setFont(QFont("sans-serif", 10))

    # Build the window using the safe manual approach
    from PyQt6.QtWidgets import (
        QMainWindow, QDockWidget, QWidget, QVBoxLayout, QSplitter,
        QMenuBar, QMenu, QStatusBar, QFileDialog, QMessageBox as MB,
        QInputDialog, QLabel,
    )
    from PyQt6.QtCore import QSettings
    from PyQt6.QtGui import QAction, QKeySequence

    from core.midi_engine import MidiEngine
    from core.audio_engine import AudioEngine
    from core.synth_engine import SynthEngine, PolySynth, SUBTRACTIVE_PRESETS, FM_PRESETS
    from core.effects_engine import Mixer, EffectsChain, EFFECT_PRESETS
    from core.automation import AutomationManager
    from core.arrangement import ArrangementManager
    from core.midi_io import MIDIInputManager, MIDIMonitor
    from core.audio_io import RecordingManager, AudioPlaybackEngine, AudioSettings
    from core.groove_engine import GROOVE_PRESETS, apply_groove, StepSequencer
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
    w.setWindowTitle(f"Untitled - {APP_NAME} v{APP_VERSION}")
    w.setMinimumSize(1280, 720)
    w.resize(1600, 900)
    w.setDockNestingEnabled(True)

    settings = QSettings("MidiAIWorkstation", "MAW")

    # --- Engines ---
    midi_engine = MidiEngine(w)
    audio_engine = AudioEngine()
    midi_engine.set_audio_engine(audio_engine)  # FluidSynth 연동
    # FluidSynth 오디오 드라이버 시작
    if audio_engine.available and hasattr(audio_engine, '_synth') and audio_engine._synth:
        try:
            audio_engine._synth.start(driver='dsound')
        except Exception:
            pass
    project_mgr = ProjectManager(w)
    ai_engine = AIEngine()
    synth_engine = SynthEngine()
    synth_engine.assign_synth(0, PolySynth.SUBTRACTIVE)
    mixer = Mixer()
    automation_mgr = AutomationManager()
    arrangement_mgr = ArrangementManager()
    midi_input = MIDIInputManager()
    midi_monitor = MIDIMonitor()
    midi_input.add_listener(midi_monitor.on_message)
    recording_mgr = RecordingManager()
    audio_playback = AudioPlaybackEngine()
    audio_settings = AudioSettings()
    undo_mgr = UndoManager()
    selected_track = [0]

    # --- Widgets ---
    transport = TransportWidget()
    transport.setFixedHeight(44)

    session_view = SessionView()
    detail_view = DetailView()
    # Set root to repo directory (parent of app/)
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_browser = FileBrowser(root_path=_repo_root)

    from ui.arrangement_view import ArrangementPanel
    arrangement_view = ArrangementPanel()

    # --- Layout ---
    # Top area: session view + arrangement view (tabbed)
    from PyQt6.QtWidgets import QTabWidget
    top_tabs = QTabWidget()
    top_tabs.setTabPosition(QTabWidget.TabPosition.South)
    top_tabs.addTab(session_view, "Session")
    top_tabs.addTab(arrangement_view, "Arrangement")
    top_tabs.setStyleSheet(f"""
        QTabWidget::pane {{ border: none; }}
        QTabBar::tab {{ background: {COLORS['bg_mid']}; color: {COLORS['text_secondary']};
                       padding: 4px 12px; border: 1px solid {COLORS['border']}; border-top: none; }}
        QTabBar::tab:selected {{ background: {COLORS['bg_darkest']}; color: {COLORS['text_primary']}; }}
    """)

    splitter = QSplitter(Qt.Orientation.Vertical)
    splitter.setHandleWidth(3)
    splitter.addWidget(top_tabs)
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

    # File browser dock
    dock_browser = QDockWidget("Browser", w)
    dock_browser.setWidget(file_browser)
    dock_browser.setMinimumWidth(220)
    dock_browser.setFeatures(
        QDockWidget.DockWidgetFeature.DockWidgetClosable
        | QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QDockWidget.DockWidgetFeature.DockWidgetFloatable
    )
    w.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_browser)

    # --- Status bar ---
    status_left = QLabel(f"  {APP_NAME}")
    status_center = QLabel("1 track | 0 notes")
    status_right = QLabel("MIDI Engine: Ready  ")
    sb = w.statusBar()
    sb.addWidget(status_left, 1)
    sb.addWidget(status_center, 1)
    sb.addPermanentWidget(status_right)

    # --- Helper functions ---
    def project():
        return project_mgr.state

    def update_title():
        name = project().name or "Untitled"
        mod = " *" if project().modified else ""
        w.setWindowTitle(f"{name}{mod} - {APP_NAME} v{APP_VERSION}")

    def update_status():
        p = project()
        tn = len(p.tracks)
        nn = sum(len(t.notes) for t in p.tracks)
        status_center.setText(f"{tn} track{'s' if tn != 1 else ''} | {nn} notes")

    def apply_project(proj):
        midi_engine.project = proj
        transport.set_project(proj)
        session_view.set_project(proj)
        detail_view.set_project(proj)
        if hasattr(arrangement_view, 'set_project'):
            arrangement_view.set_project(proj)
        if proj.tracks:
            selected_track[0] = 0
            detail_view.set_track(proj.tracks[0], 0)
        undo_mgr.clear()
        update_title()
        update_status()
        if proj.file_path:
            file_browser.set_root(os.path.dirname(proj.file_path))

    def mark_modified():
        project().modified = True
        update_title()
        update_status()

    def push_undo(desc):
        old = copy.deepcopy(project())
        QTimer.singleShot(0, lambda: undo_mgr.push(desc, old, copy.deepcopy(project())))

    # --- Menu bar ---
    menubar = w.menuBar()

    # File menu
    file_menu = menubar.addMenu("&File")

    act_new = file_menu.addAction("&New Project")
    act_new.setShortcut(QKeySequence("Ctrl+N"))

    act_open = file_menu.addAction("&Open Project...")
    act_open.setShortcut(QKeySequence("Ctrl+O"))

    act_import = file_menu.addAction("&Import MIDI...")
    act_import.setShortcut(QKeySequence("Ctrl+I"))

    file_menu.addSeparator()

    act_save = file_menu.addAction("&Save")
    act_save.setShortcut(QKeySequence("Ctrl+S"))

    act_save_as = file_menu.addAction("Save &As...")
    act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))

    act_export_midi = file_menu.addAction("&Export MIDI...")
    act_export_midi.setShortcut(QKeySequence("Ctrl+E"))

    file_menu.addSeparator()

    act_quit = file_menu.addAction("&Quit")
    act_quit.setShortcut(QKeySequence("Ctrl+Q"))

    # Edit menu
    edit_menu = menubar.addMenu("&Edit")

    act_undo = edit_menu.addAction("&Undo")
    act_undo.setShortcut(QKeySequence("Ctrl+Z"))

    act_redo = edit_menu.addAction("&Redo")
    act_redo.setShortcut(QKeySequence("Ctrl+Shift+Z"))

    edit_menu.addSeparator()

    act_select_all = edit_menu.addAction("Select &All")
    act_select_all.setShortcut(QKeySequence("Ctrl+A"))

    # Create menu
    create_menu = menubar.addMenu("&Create")

    act_add_track = create_menu.addAction("Add &MIDI Track")
    act_add_track.setShortcut(QKeySequence("Ctrl+T"))

    # View menu
    view_menu = menubar.addMenu("&View")

    act_toggle_browser = view_menu.addAction("Toggle &Browser")
    act_toggle_browser.setShortcut(QKeySequence("Ctrl+B"))

    act_toggle_detail = view_menu.addAction("Toggle &Detail View")

    # AI menu
    ai_menu = menubar.addMenu("&AI")

    act_gen_melody = ai_menu.addAction("Generate &Melody")
    act_gen_chords = ai_menu.addAction("Generate &Chords")
    act_gen_bass = ai_menu.addAction("Generate &Bass")
    ai_menu.addSeparator()
    act_gen_variation = ai_menu.addAction("Generate &Variation")
    act_gen_voicing = ai_menu.addAction("Generate &Voicing (Rule DB)")
    ai_menu.addSeparator()
    act_humanize = ai_menu.addAction("&Humanize")
    act_analyze = ai_menu.addAction("&Analyze Track")
    act_analyze_harmony = ai_menu.addAction("Analyze &Harmony")
    act_analyze_form = ai_menu.addAction("Analyze Song &Form")
    ai_menu.addSeparator()
    act_gen_from_settings = ai_menu.addAction("Generate from &Settings")

    # Edit menu additions
    edit_menu = menubar.addMenu("&Preferences")
    act_settings = edit_menu.addAction("&Settings...")
    act_settings.setShortcut("Ctrl+,")

    # Help menu
    help_menu = menubar.addMenu("&Help")
    act_about = help_menu.addAction("&About")

    # --- Menu handlers ---
    def new_project():
        project_mgr.new_project()
        apply_project(project_mgr.state)

    def open_project():
        path, _ = QFileDialog.getOpenFileName(
            w, "Open Project", "", "MAW Projects (*.maw);;MIDI Files (*.mid *.midi);;All (*)"
        )
        if path:
            path = str(Path(path).resolve())
            if path.endswith(".maw"):
                project_mgr.load_project(path)
            else:
                project_mgr.import_midi(path)
            apply_project(project_mgr.state)

    def import_midi():
        path, _ = QFileDialog.getOpenFileName(
            w, "Import MIDI", "", "MIDI Files (*.mid *.midi);;All (*)"
        )
        if path:
            path = str(Path(path).resolve())
            project_mgr.import_midi(path)
            apply_project(project_mgr.state)

    def save_project():
        if project().file_path:
            project_mgr.save_project(project().file_path)
            update_title()
        else:
            save_project_as()

    def save_project_as():
        path, _ = QFileDialog.getSaveFileName(
            w, "Save Project", "", "MAW Projects (*.maw);;All (*)"
        )
        if path:
            path = str(Path(path).resolve())
            if not path.endswith(".maw"):
                path += ".maw"
            project_mgr.save_project(path)
            update_title()

    def export_midi():
        path, _ = QFileDialog.getSaveFileName(
            w, "Export MIDI", "", "MIDI Files (*.mid);;All (*)"
        )
        if path:
            path = str(Path(path).resolve())
            midi_engine.save_midi_file(path)

    def do_undo():
        state = undo_mgr.undo()
        if state:
            project_mgr.state = state
            apply_project(state)

    def do_redo():
        state = undo_mgr.redo()
        if state:
            project_mgr.state = state
            apply_project(state)

    def add_track():
        push_undo("Add Track")
        idx = len(project().tracks)
        color = TRACK_COLORS[idx % len(TRACK_COLORS)]
        t = Track(name=f"Track {idx + 1}", channel=min(idx, 15), color=color)
        project().tracks.append(t)
        mark_modified()
        session_view.refresh()

    def toggle_browser():
        dock_browser.setVisible(not dock_browser.isVisible())

    def toggle_detail():
        detail_view.toggle_collapse()

    def generate_track(kind):
        push_undo(f"Generate {kind}")
        p = project()
        if kind == "melody":
            t = ai_engine.generate_melody(p.key, p.scale, 32, "pop", 0.7)
        elif kind == "chords":
            t = ai_engine.generate_chords(p.key, p.scale, 32, "pop")
        else:
            t = ai_engine.generate_bass(p.key, p.scale, 32, "pop")
        t.color = TRACK_COLORS[len(p.tracks) % len(TRACK_COLORS)]
        p.tracks.append(t)
        mark_modified()
        session_view.refresh()
        detail_view.set_track(t, len(p.tracks) - 1)

    def generate_variation():
        p = project()
        idx = selected_track[0]
        if 0 <= idx < len(p.tracks):
            push_undo("Generate Variation")
            var = ai_engine.generate_variation(p.tracks[idx], "mixed", 0.5, p.key, p.scale)
            var.name = f"{p.tracks[idx].name} (var)"
            var.color = TRACK_COLORS[len(p.tracks) % len(TRACK_COLORS)]
            p.tracks.append(var)
            mark_modified()
            session_view.refresh()

    def humanize_track():
        p = project()
        idx = selected_track[0]
        if 0 <= idx < len(p.tracks):
            push_undo("Humanize")
            result = ai_engine.humanize(p.tracks[idx], 0.3, 0.3)
            p.tracks[idx].notes = result.notes
            mark_modified()
            detail_view.set_track(p.tracks[idx], idx)

    def analyze_track():
        p = project()
        idx = selected_track[0]
        if 0 <= idx < len(p.tracks):
            analysis = ai_engine.analyze_track(p.tracks[idx], p.key, p.scale)
            detail_view.show_tab("analysis")
            rp = detail_view._review_panel
            if hasattr(rp, 'show_review'):
                rp.show_review(analysis)

    def generate_voicing():
        p = project()
        idx = selected_track[0]
        if 0 <= idx < len(p.tracks) and ai_engine.harmony_engine:
            push_undo("Generate Voicing")
            he = ai_engine.harmony_engine
            # Find melody track if available
            melody_t = None
            for t in p.tracks:
                if "melody" in t.name.lower():
                    melody_t = t
                    break
            voicing_track = he.generate_voicing_track(
                p.tracks[idx], p.key, p.scale,
                melody_track=melody_t, style="pop", octave=4,
            )
            voicing_track.color = TRACK_COLORS[len(p.tracks) % len(TRACK_COLORS)]
            p.tracks.append(voicing_track)
            mark_modified()
            session_view.refresh()
            detail_view.set_track(voicing_track, len(p.tracks) - 1)
        elif not ai_engine.harmony_engine:
            MB.warning(w, "Rule DB", "Harmony Rule DB (v2.07) not loaded.")

    def analyze_harmony():
        p = project()
        idx = selected_track[0]
        if 0 <= idx < len(p.tracks) and ai_engine.harmony_engine:
            he = ai_engine.harmony_engine
            result = he.analyze_track_harmony(p.tracks[idx], p.key, p.scale)
            # Show in review panel via the analysis dict
            analysis = ai_engine.analyze_track(p.tracks[idx], p.key, p.scale)
            detail_view.show_tab("analysis")
            rp = detail_view._review_panel
            if hasattr(rp, 'show_review'):
                rp.show_review(analysis)
        elif not ai_engine.harmony_engine:
            MB.warning(w, "Rule DB", "Harmony Rule DB (v2.07) not loaded.")

    def analyze_song_form():
        p = project()
        if ai_engine.harmony_engine:
            he = ai_engine.harmony_engine
            form = he.analyze_song_form(p)
            sections = form.get("sections", [])
            form_type = form.get("form_type", "unknown")
            conf = form.get("confidence", 0)

            lines = [f"Form: {form_type} (confidence: {int(conf * 100)}%)", ""]
            for sec in sections:
                label = sec.get("label", "?")
                bars = f"bar {sec.get('start_bar', '?')}-{sec.get('end_bar', '?')}"
                energy = sec.get("avg_energy", 0)
                lines.append(f"  [{label.upper():12}] {bars}  energy={energy:.2f}")

            MB.information(w, "Song Form Analysis", "\n".join(lines))
        else:
            MB.warning(w, "Rule DB", "Harmony Rule DB (v2.07) not loaded.")

    def generate_from_settings():
        """Generate voicing track from settings.json chord_progression."""
        if not ai_engine.harmony_engine:
            MB.warning(w, "Rule DB", "Harmony Rule DB (v2.07) not loaded.")
            return
        settings_path = os.path.join(_repo_root, "settings.json")
        if not os.path.isfile(settings_path):
            MB.warning(w, "Settings", "settings.json not found.")
            return
        try:
            import json as _json
            with open(settings_path, "r", encoding="utf-8") as f:
                sdata = _json.load(f)
            chord_prog = sdata.get("chord_progression", [])
            if not chord_prog:
                MB.warning(w, "Settings", "No chord_progression in settings.json.")
                return

            push_undo("Generate from Settings")
            p = project()
            p.bpm = sdata.get("bpm", p.bpm)
            p.key = sdata.get("key", p.key)
            p.scale = sdata.get("scale", p.scale)
            transport.set_project(p)

            he = ai_engine.harmony_engine
            # Find melody track if exists
            melody_t = None
            for t in p.tracks:
                if "melody" in t.name.lower():
                    melody_t = t
                    break

            track = he.generate_from_progression(
                chord_prog,
                key=p.key, scale=p.scale,
                style=sdata.get("style", "jazz"),
                octave=4, melody_track=melody_t,
            )
            track.color = TRACK_COLORS[len(p.tracks) % len(TRACK_COLORS)]
            p.tracks.append(track)
            mark_modified()
            session_view.refresh()
            detail_view.set_track(track, len(p.tracks) - 1)
            sb.showMessage(
                f"Generated voicing from settings.json ({len(chord_prog)} chords)", 5000
            )
        except Exception as e:
            MB.critical(w, "Error", f"Failed to generate from settings:\n{e}")

    def about():
        he_status = "loaded" if ai_engine.harmony_engine else "not found"
        ver = ""
        if ai_engine.harmony_engine:
            ver = f" v{ai_engine.harmony_engine.schema_version}"
        MB.about(
            w, "About",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"AI-powered MIDI Workstation\n"
            f"Harmony Rule DB{ver}: {he_status}"
        )

    # Connect menu actions
    act_new.triggered.connect(new_project)
    act_open.triggered.connect(open_project)
    act_import.triggered.connect(import_midi)
    act_save.triggered.connect(save_project)
    act_save_as.triggered.connect(save_project_as)
    act_export_midi.triggered.connect(export_midi)
    act_quit.triggered.connect(w.close)
    act_undo.triggered.connect(do_undo)
    act_redo.triggered.connect(do_redo)
    act_add_track.triggered.connect(add_track)
    act_toggle_browser.triggered.connect(toggle_browser)
    act_toggle_detail.triggered.connect(toggle_detail)
    act_gen_melody.triggered.connect(lambda: generate_track("melody"))
    act_gen_chords.triggered.connect(lambda: generate_track("chords"))
    act_gen_bass.triggered.connect(lambda: generate_track("bass"))
    act_gen_variation.triggered.connect(generate_variation)
    act_humanize.triggered.connect(humanize_track)
    act_analyze.triggered.connect(analyze_track)
    act_gen_voicing.triggered.connect(generate_voicing)
    act_analyze_harmony.triggered.connect(analyze_harmony)
    act_analyze_form.triggered.connect(analyze_song_form)
    act_gen_from_settings.triggered.connect(generate_from_settings)
    act_about.triggered.connect(about)

    def open_settings():
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(w)
        dlg.settings_changed.connect(lambda s: sb.showMessage(f"Settings applied", 2000))
        dlg.exec()
    act_settings.triggered.connect(open_settings)

    # --- Widget signal connections ---
    # Transport
    transport.play_clicked.connect(midi_engine.toggle_playback)
    transport.stop_clicked.connect(midi_engine.stop)
    transport.rewind_clicked.connect(lambda: midi_engine.seek(0))

    def on_bpm(val):
        project().bpm = val
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

    # Playback position
    def on_position(tick):
        transport.update_position(tick, project())
        detail_view.update_playhead(tick)
        if hasattr(arrangement_view, 'update_playhead'):
            arrangement_view.update_playhead(tick)
    midi_engine.position_changed.connect(on_position)

    def on_playback_state(state):
        transport.set_playing(state == "playing")
    midi_engine.playback_state_changed.connect(on_playback_state)

    # --- MIDI Recording ---
    _recording = [False]

    def toggle_recording():
        if _recording[0]:
            # Stop recording
            notes = midi_input.stop_recording()
            _recording[0] = False
            transport.set_recording(False)

            if notes:
                push_undo("MIDI Recording")
                p = project()
                idx = selected_track[0]
                if 0 <= idx < len(p.tracks):
                    p.tracks[idx].notes.extend(notes)
                    mark_modified()
                    detail_view.set_track(p.tracks[idx], idx)
                sb.showMessage(f"Recorded {len(notes)} notes", 3000)
            else:
                sb.showMessage("Recording stopped (no notes captured)", 3000)
        else:
            # Start recording
            _recording[0] = True
            midi_input.set_bpm(project().bpm)
            midi_input.set_thru_callback(
                lambda ch, n, v: audio_engine.note_on(ch, n, v) if v > 0 else audio_engine.note_off(ch, n)
            )
            midi_input.start_recording(midi_engine.current_tick)
            # Start playback when recording begins
            if midi_engine.state != "playing":
                midi_engine.toggle_playback()
            transport.set_recording(True)
            sb.showMessage("Recording...", 0)

    if hasattr(transport, 'record_clicked'):
        transport.record_clicked.connect(toggle_recording)

    # Stop recording when Stop is pressed
    def on_stop_during_recording():
        if _recording[0]:
            toggle_recording()
    transport.stop_clicked.connect(on_stop_during_recording)

    # Arrangement ruler seek
    if hasattr(arrangement_view, '_ruler') and hasattr(arrangement_view._ruler, 'position_clicked'):
        arrangement_view._ruler.position_clicked.connect(lambda tick: midi_engine.seek(max(0, tick)))

    # Session view
    def on_track_selected(idx):
        selected_track[0] = idx
        p = project()
        if 0 <= idx < len(p.tracks):
            detail_view.set_track(p.tracks[idx], idx)
    session_view.track_selected.connect(on_track_selected)

    def on_clip_opened(t_idx, s_idx):
        detail_view.show_tab("notes")
        p = project()
        if 0 <= t_idx < len(p.tracks):
            detail_view.set_track(p.tracks[t_idx], t_idx)
    session_view.clip_opened.connect(on_clip_opened)

    session_view.track_added.connect(lambda: (update_status(), update_title()))
    session_view.track_removed.connect(lambda idx: (update_status(), update_title()))

    # File browser
    def on_file_activated(path):
        if path.endswith(".maw"):
            project_mgr.load_project(path)
            apply_project(project_mgr.state)
        elif path.endswith((".mid", ".midi")):
            project_mgr.import_midi(path)
            apply_project(project_mgr.state)
    file_browser.file_double_clicked.connect(on_file_activated)

    # Detail view AI signals
    def on_generate(params):
        prompt = params.get("prompt", "")
        if prompt or params.get("genre") or params.get("mood"):
            # New path: prompt + dropdown based generation
            push_undo("Generate from Prompt")
            p = project()
            track = ai_engine.generate_from_prompt(params, p.key, p.scale)
            track.color = TRACK_COLORS[len(p.tracks) % len(TRACK_COLORS)]
            p.tracks.append(track)
            mark_modified()
            session_view.refresh()
            detail_view.set_track(track, len(p.tracks) - 1)
            if prompt:
                sb.showMessage(f"Generated from prompt: {prompt[:40]}...", 5000)
        else:
            kind = params.get("track_type", params.get("type", "melody")).lower()
            generate_track(kind)
    detail_view.generate_requested.connect(on_generate)

    def on_variation(params):
        generate_variation()
    detail_view.variation_requested.connect(on_variation)

    def on_humanize(timing, velocity):
        p = project()
        idx = selected_track[0]
        if 0 <= idx < len(p.tracks):
            push_undo("Humanize")
            result = ai_engine.humanize(p.tracks[idx], timing, velocity)
            p.tracks[idx].notes = result.notes
            mark_modified()
            detail_view.set_track(p.tracks[idx], idx)
    detail_view.humanize_requested.connect(on_humanize)

    detail_view.analyze_requested.connect(analyze_track)

    # Ingest handler
    def on_ingest(path):
        try:
            import subprocess
            path = str(Path(path).resolve())
            ingest_script = os.path.join(_repo_root, "tools", "auto_ingest.py")
            python_exe = sys.executable
            subprocess.Popen(
                [python_exe, ingest_script, path],
                cwd=_repo_root,
                creationflags=0x00000008 if sys.platform == "win32" else 0,  # DETACHED
            )
            sb.showMessage(f"Ingesting: {os.path.basename(path)}", 3000)
        except Exception as e:
            sb.showMessage(f"Ingest failed: {e}", 5000)

    if hasattr(detail_view, '_ai_panel') and hasattr(detail_view._ai_panel, 'ingest_requested'):
        detail_view._ai_panel.ingest_requested.connect(on_ingest)

    # Synth panel signals
    if hasattr(detail_view, '_synth_panel'):
        def on_synth_type_changed(stype):
            type_map = {
                "subtractive": PolySynth.SUBTRACTIVE,
                "fm": PolySynth.FM,
                "wavetable": PolySynth.WAVETABLE,
                "granular": PolySynth.GRANULAR,
                "sampler": PolySynth.SAMPLER,
            }
            ch = selected_track[0]
            st = type_map.get(stype, PolySynth.SUBTRACTIVE)
            synth_engine.assign_synth(ch, st)
            sb.showMessage(f"Synth: {stype} assigned to channel {ch}", 2000)

        def on_synth_preset_changed(preset_name):
            ch = selected_track[0]
            synth_engine.load_preset(ch, preset_name)
            sb.showMessage(f"Preset: {preset_name}", 2000)

        def on_synth_pad_hit(note, velocity):
            synth_engine.note_on(synth_engine.drum_channel, note, velocity)
            # Also play via FluidSynth for audio
            audio_engine.note_on(9, note, velocity)

        detail_view._synth_panel.synth_type_changed.connect(on_synth_type_changed)
        detail_view._synth_panel.preset_changed.connect(on_synth_preset_changed)
        detail_view._synth_panel.pad_triggered.connect(on_synth_pad_hit)

    # Scale snap
    def on_scale_snap(key, scale):
        p = project()
        idx = selected_track[0]
        if 0 <= idx < len(p.tracks):
            push_undo("Scale Snap")
            from utils.midi_utils import scale_snap as do_snap
            p.tracks[idx].notes = do_snap(p.tracks[idx].notes, key, scale)
            mark_modified()
            detail_view.set_track(p.tracks[idx], idx)
    detail_view.scale_snap_requested.connect(on_scale_snap)

    # Quantize
    def on_quantize(grid_beats, strength):
        p = project()
        idx = selected_track[0]
        if 0 <= idx < len(p.tracks):
            push_undo("Quantize")
            grid_ticks = int(grid_beats * TICKS_PER_BEAT)
            midi_engine.quantize_track(idx, grid_ticks, strength / 100.0)
            mark_modified()
            detail_view.set_track(p.tracks[idx], idx)
    detail_view.quantize_requested.connect(on_quantize)

    # Note editing signals
    def on_note_change(note):
        mark_modified()
        update_status()
    if hasattr(detail_view, 'note_added'):
        detail_view.note_added.connect(on_note_change)
    if hasattr(detail_view, 'note_removed'):
        detail_view.note_removed.connect(on_note_change)
    if hasattr(detail_view, 'note_modified'):
        detail_view.note_modified.connect(on_note_change)

    # Transport snap -> piano roll
    def on_snap(val):
        pr = detail_view.get_piano_roll()
        if pr and hasattr(pr, 'set_snap'):
            pr.set_snap(val)
    transport.snap_changed.connect(on_snap)

    # --- 가상 MIDI 키보드 (QWERTY + 피아노 클릭) → AudioEngine ---
    pr = detail_view.get_piano_roll()
    if pr:
        _vk_channel = [0]  # 현재 선택된 트랙의 채널

        def on_virtual_note_on(pitch):
            ch = _vk_channel[0]
            audio_engine.note_on(ch, pitch, 100)

        def on_virtual_note_off(pitch):
            ch = _vk_channel[0]
            audio_engine.note_off(ch, pitch)

        if hasattr(pr, 'note_preview_requested'):
            pr.note_preview_requested.connect(on_virtual_note_on)
        if hasattr(pr, 'note_release_requested'):
            pr.note_release_requested.connect(on_virtual_note_off)
        # 피아노 키보드 클릭도 같은 핸들러 사용
        if hasattr(pr, '_keyboard') and hasattr(pr._keyboard, 'note_preview'):
            pr._keyboard.note_preview.connect(lambda pitch: (
                audio_engine.note_on(_vk_channel[0], pitch, 100),
                QTimer.singleShot(500, lambda: audio_engine.note_off(_vk_channel[0], pitch))
            ))

        # 트랙 선택 시 가상 키보드 채널 업데이트
        def _update_vk_channel(idx):
            p = project()
            if 0 <= idx < len(p.tracks):
                _vk_channel[0] = p.tracks[idx].channel
        session_view.track_selected.connect(_update_vk_channel)

    # Session view mixer signals (safe connection with hasattr checks)
    if hasattr(session_view, 'mixer_volume_changed'):
        def on_mixer_volume(track_idx, value):
            p = project()
            if 0 <= track_idx < len(p.tracks):
                p.tracks[track_idx].volume = value
                audio_engine.set_channel_volume(p.tracks[track_idx].channel, value)
                mark_modified()
        session_view.mixer_volume_changed.connect(on_mixer_volume)

    if hasattr(session_view, 'mixer_mute_toggled'):
        def on_mixer_mute(track_idx, muted):
            p = project()
            if 0 <= track_idx < len(p.tracks):
                p.tracks[track_idx].muted = muted
                mark_modified()
        session_view.mixer_mute_toggled.connect(on_mixer_mute)

    if hasattr(session_view, 'mixer_solo_toggled'):
        def on_mixer_solo(track_idx, solo):
            p = project()
            if 0 <= track_idx < len(p.tracks):
                p.tracks[track_idx].solo = solo
                mark_modified()
        session_view.mixer_solo_toggled.connect(on_mixer_solo)

    if hasattr(session_view, 'mixer_pan_changed'):
        def on_mixer_pan(track_idx, value):
            p = project()
            if 0 <= track_idx < len(p.tracks):
                p.tracks[track_idx].pan = value
                audio_engine.set_channel_pan(p.tracks[track_idx].channel, value)
                mark_modified()
        session_view.mixer_pan_changed.connect(on_mixer_pan)

    # VU meter simulation
    def simulate_meters():
        import random
        p = project()
        if midi_engine.state != "playing":
            session_view.update_meters([0.0] * len(p.tracks))
            return
        levels = []
        for t in p.tracks:
            if t.muted:
                levels.append(0.0)
            else:
                levels.append((t.volume / 127.0) * 0.7 + random.uniform(0.0, 0.25))
        session_view.update_meters(levels)

    meter_timer = QTimer(w)
    meter_timer.timeout.connect(simulate_meters)
    meter_timer.start(80)

    # --- Chord Pad playback ---
    if hasattr(detail_view, '_chord_pad_panel') and hasattr(detail_view._chord_pad_panel, 'chord_triggered'):
        _active_chord_notes = []  # track currently sounding chord notes

        def on_chord_triggered(note_events):
            """Play chord through AudioEngine. note_events = list of {pitch, velocity, spread_ms}"""
            nonlocal _active_chord_notes
            # Stop previous chord
            for n in _active_chord_notes:
                audio_engine.note_off(1, n)  # channel 1 for chords
            _active_chord_notes = []

            for evt in note_events:
                pitch = evt.get('pitch', 60)
                vel = evt.get('velocity', 80)
                spread = evt.get('spread_ms', 0)
                if spread > 0:
                    # Simple spread delay (non-blocking approximation)
                    QTimer.singleShot(int(spread), lambda p=pitch, v=vel: audio_engine.note_on(1, p, v))
                else:
                    audio_engine.note_on(1, pitch, vel)
                _active_chord_notes.append(pitch)

            # Auto note-off after 2 seconds
            def stop_chord(notes=list(_active_chord_notes)):
                for n in notes:
                    audio_engine.note_off(1, n)
            QTimer.singleShot(2000, stop_chord)

        detail_view._chord_pad_panel.chord_triggered.connect(on_chord_triggered)

    # --- Step Sequencer → Track ---
    if hasattr(detail_view, '_step_seq_panel'):
        def on_step_pad_hit(row, col):
            """Preview step sequencer hit."""
            # GM drum map
            drum_notes = [36, 38, 42, 46, 49, 51, 45, 39]  # kick, snare, hh, etc.
            if 0 <= row < len(drum_notes):
                note = drum_notes[row]
                audio_engine.note_on(9, note, 100)
                QTimer.singleShot(200, lambda: audio_engine.note_off(9, note))

        if hasattr(detail_view._step_seq_panel, 'step_toggled'):
            detail_view._step_seq_panel.step_toggled.connect(on_step_pad_hit)

        # Convert step pattern to MIDI notes and add to project
        if hasattr(detail_view._step_seq_panel, 'pattern_changed'):
            def on_pattern_changed(pattern_data):
                """Convert 16-step grid pattern to MIDI notes in the drum track."""
                p = project()
                # Find or create drum track
                drum_track = None
                drum_idx = -1
                for i, t in enumerate(p.tracks):
                    if t.channel == 9 or 'drum' in t.name.lower():
                        drum_track = t
                        drum_idx = i
                        break
                if drum_track is None:
                    return

                push_undo("Step Sequencer Edit")
                drum_notes_map = [36, 38, 42, 46, 49, 51, 45, 39]
                ticks_per_step = TICKS_PER_BEAT  # 16th note at 4/4

                # Clear existing drum notes in first 4 bars
                drum_track.notes = [n for n in drum_track.notes if n.start_tick >= ticks_per_step * 16]

                # Add new pattern
                if isinstance(pattern_data, dict):
                    for row_idx, steps in pattern_data.items():
                        if row_idx < len(drum_notes_map):
                            note_num = drum_notes_map[row_idx]
                            for step_idx, vel in enumerate(steps):
                                if vel > 0:
                                    drum_track.notes.append(Note(
                                        pitch=note_num,
                                        velocity=vel,
                                        start_tick=step_idx * ticks_per_step,
                                        duration=ticks_per_step // 2,
                                    ))
                mark_modified()
            detail_view._step_seq_panel.pattern_changed.connect(on_pattern_changed)

    # --- Transport extended controls ---
    # Locators → loop range
    if hasattr(transport, 'left_locator_changed'):
        def on_left_locator(bar_beat_str):
            """Set loop start from locator. Format: 'bar.beat.tick'"""
            try:
                parts = bar_beat_str.split('.')
                bar = int(parts[0]) - 1
                beat = int(parts[1]) - 1 if len(parts) > 1 else 0
                tick = bar * TICKS_PER_BEAT * 4 + beat * TICKS_PER_BEAT
                project().loop_start = tick
            except (ValueError, IndexError):
                pass
        transport.left_locator_changed.connect(on_left_locator)

    if hasattr(transport, 'right_locator_changed'):
        def on_right_locator(bar_beat_str):
            try:
                parts = bar_beat_str.split('.')
                bar = int(parts[0]) - 1
                beat = int(parts[1]) - 1 if len(parts) > 1 else 0
                tick = bar * TICKS_PER_BEAT * 4 + beat * TICKS_PER_BEAT
                project().loop_end = tick
            except (ValueError, IndexError):
                pass
        transport.right_locator_changed.connect(on_right_locator)

    # Punch in/out → recording markers
    if hasattr(transport, 'punch_in_toggled'):
        transport.punch_in_toggled.connect(lambda on: setattr(project(), 'punch_in', on) if hasattr(project(), 'punch_in') else None)

    if hasattr(transport, 'punch_out_toggled'):
        transport.punch_out_toggled.connect(lambda on: setattr(project(), 'punch_out', on) if hasattr(project(), 'punch_out') else None)

    # Marker navigation
    if hasattr(transport, 'prev_marker_clicked'):
        def go_prev_marker():
            p = project()
            if hasattr(p, 'markers') and p.markers:
                current = midi_engine.current_tick
                prev_markers = [m for m in p.markers if m.get('tick', 0) < current - TICKS_PER_BEAT]
                if prev_markers:
                    midi_engine.seek(prev_markers[-1]['tick'])
                else:
                    midi_engine.seek(0)
        transport.prev_marker_clicked.connect(go_prev_marker)

    if hasattr(transport, 'next_marker_clicked'):
        def go_next_marker():
            p = project()
            if hasattr(p, 'markers') and p.markers:
                current = midi_engine.current_tick
                next_markers = [m for m in p.markers if m.get('tick', 0) > current + TICKS_PER_BEAT]
                if next_markers:
                    midi_engine.seek(next_markers[0]['tick'])
        transport.next_marker_clicked.connect(go_next_marker)

    # Cycle/loop toggle (transport uses 'loop_toggled' signal)
    if hasattr(transport, 'loop_toggled'):
        transport.loop_toggled.connect(lambda on: setattr(midi_engine, 'loop_enabled', on))
    elif hasattr(transport, 'cycle_toggled'):
        transport.cycle_toggled.connect(lambda on: setattr(midi_engine, 'loop_enabled', on))

    # --- Expression Map integration ---
    if hasattr(detail_view, '_expr_map_editor'):
        _current_expression_map = {}
        _current_articulation = 'natural'

        if hasattr(detail_view._expr_map_editor, 'articulation_changed'):
            def on_articulation_changed(art_name):
                nonlocal _current_articulation
                _current_articulation = art_name
                sb.showMessage(f"Articulation: {art_name}", 2000)

                # Apply CC changes for the articulation
                try:
                    from midigpt.cubase_data.expression_maps import apply_technique
                    # Get the current track's channel
                    p = project()
                    idx = selected_track[0]
                    if 0 <= idx < len(p.tracks):
                        ch = p.tracks[idx].channel
                        # Apply technique modifiers (velocity/CC/length)
                        mod = apply_technique({}, art_name)
                        if 'cc_events' in mod:
                            for cc_num, cc_val in mod['cc_events']:
                                audio_engine.send_cc(ch, cc_num, cc_val) if hasattr(audio_engine, 'send_cc') else None
                except ImportError:
                    pass

            detail_view._expr_map_editor.articulation_changed.connect(on_articulation_changed)

    # --- Effects panel → Mixer ---
    if hasattr(detail_view, '_effects_panel'):
        if hasattr(detail_view._effects_panel, 'effect_toggled'):
            def on_effect_toggled(slot_idx, enabled):
                idx = selected_track[0]
                if hasattr(mixer, 'set_insert_bypass'):
                    mixer.set_insert_bypass(idx, slot_idx, not enabled)
            detail_view._effects_panel.effect_toggled.connect(on_effect_toggled)

        if hasattr(detail_view._effects_panel, 'dry_wet_changed'):
            def on_dry_wet(slot_idx, value):
                idx = selected_track[0]
                if hasattr(mixer, 'set_insert_mix'):
                    mixer.set_insert_mix(idx, slot_idx, value / 100.0)
            detail_view._effects_panel.dry_wet_changed.connect(on_dry_wet)

        if hasattr(detail_view._effects_panel, 'send_level_changed'):
            def on_send_level(send_idx, value):
                idx = selected_track[0]
                if hasattr(mixer, 'set_send_level'):
                    mixer.set_send_level(idx, send_idx, value / 127.0)
            detail_view._effects_panel.send_level_changed.connect(on_send_level)

    # --- Auto-load latest MIDI or CLI argument ---
    _auto_midi = None
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        _auto_midi = str(Path(sys.argv[1]).resolve())
    else:
        _out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        if os.path.isdir(_out_dir):
            _mids = sorted(
                [f for f in os.listdir(_out_dir) if f.endswith(".mid")],
                key=lambda f: os.path.getmtime(os.path.join(_out_dir, f)),
                reverse=True,
            )
            if _mids:
                _auto_midi = os.path.join(_out_dir, _mids[0])

    if _auto_midi:
        project_mgr.import_midi(_auto_midi)

    apply_project(project_mgr.state)

    # --- Restore window state ---
    geom = settings.value("geometry")
    if geom:
        w.restoreGeometry(geom)

    # Save state on close
    original_close = w.closeEvent

    def on_close(event):
        settings.setValue("geometry", w.saveGeometry())
        settings.setValue("window_state", w.saveState())
        midi_engine.shutdown()
        audio_engine.cleanup()
        event.accept()

    w.closeEvent = on_close

    # --- Show ---
    w.show()
    sb.showMessage("Ready", 3000)

    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        tb = traceback.format_exc()
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(None, f"{APP_NAME} -- Fatal Error", tb)
        else:
            print(tb, file=sys.stderr)
        sys.exit(1)
