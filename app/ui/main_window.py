"""
Main application window for the MIDI AI Workstation.

Integrates all UI panels into an Ableton Live Session View layout:

    ┌──────────────────────────────────────────────────────────────┐
    │  TransportWidget (TOP BAR) — full width, 36px height         │
    ├────────┬─────────────────────────────────────────────────────┤
    │        │                                                     │
    │  File  │  SessionView (center)                               │
    │  Brow  │  - Track headers at top                             │
    │  ser   │  - Clip grid                                        │
    │        │  - Scene launchers on right                         │
    │(~220px)│  - Mixer section at bottom of session               │
    │        │                                                     │
    ├────────┼─────────────────────────────────────────────────────┤
    │        │  DetailView (bottom panel, ~280px)                   │
    │        │  - Piano Roll / AI Generate / AI Variation / Analysis│
    │        │  - Collapsible                                       │
    ├────────┴─────────────────────────────────────────────────────┤
    │  StatusBar                                                    │
    └──────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import copy
import logging
import os
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenuBar, QMenu, QStatusBar, QFileDialog, QMessageBox,
    QApplication, QInputDialog, QLabel, QSizePolicy, QDockWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QTimer, QSize
from PyQt6.QtGui import QAction, QKeySequence, QFont, QCloseEvent

from config import (
    APP_NAME, APP_VERSION, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    COLORS, SNAP_VALUES, ZONE_DEFAULTS,
)
from core.models import (
    Note, Track, ProjectState, UndoManager, TICKS_PER_BEAT,
    TRACK_COLORS, key_name_to_root,
)
from core.midi_engine import MidiEngine
from core.audio_engine import AudioEngine
from core.project import ProjectManager
from core.ai_engine import AIEngine
from ui.session_view import SessionView
from ui.transport import TransportWidget
from ui.detail_view import DetailView
from ui.file_browser import FileBrowser
from ui.track_inspector import TrackInspectorPanel
from ui.styles import get_stylesheet

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SETTINGS_ORG = "MidiAIWorkstation"
_SETTINGS_APP = "MAW"

_FILE_FILTER_PROJECT = "MAW Projects (*.maw);;All Files (*)"
_FILE_FILTER_MIDI = "MIDI Files (*.mid *.midi);;All Files (*)"
_FILE_FILTER_WAV = "WAV Files (*.wav);;All Files (*)"


# ===========================================================================
# MainWindow
# ===========================================================================

class MainWindow(QMainWindow):
    """Top-level application window — Ableton Live Session View layout."""

    project_changed = pyqtSignal()

    # -----------------------------------------------------------------------
    # Initialisation
    # -----------------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)

        # ---- Core engines ------------------------------------------------
        self._midi_engine = MidiEngine(self)
        self._audio_engine = AudioEngine()
        self._project_manager = ProjectManager(self)
        self._ai_engine = AIEngine()
        self._undo_manager = UndoManager()

        # ---- Track selection state ----------------------------------------
        self._selected_track_index: int = 0
        self._last_dir: str = self._settings.value("last_directory", os.getcwd())

        # ---- Build the window ---------------------------------------------
        self._init_window()
        self._create_ui_panels()
        self._create_menus()
        self._create_status_bar()
        try:
            self._connect_signals()
        except Exception as _e:
            logger.warning("Signal connection error: %s", _e)

        # Apply global stylesheet
        self.setStyleSheet(get_stylesheet())

        # ---- Load default project -----------------------------------------
        try:
            self._apply_project(self._project_manager.state)
        except Exception as _e:
            logger.warning("Apply project error: %s", _e)

        # ---- Restore saved geometry ---------------------------------------
        try:
            self._restore_state()
        except Exception as _e:
            logger.warning("Restore state error: %s", _e)

        # ---- Periodic VU meter simulation ---------------------------------
        self._meter_timer = QTimer(self)
        self._meter_timer.timeout.connect(self._simulate_meters)
        self._meter_timer.start(80)

        self._update_title()
        self.statusBar().showMessage("Ready", 3000)

    # ===================================================================
    # Window setup
    # ===================================================================

    def _init_window(self) -> None:
        """Configure basic window properties."""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(1600, 900)
        self.setDockNestingEnabled(True)

    # ===================================================================
    # UI panels — Ableton Session View layout
    # ===================================================================

    def _create_ui_panels(self) -> None:
        """Instantiate and lay out all UI panels.

        Layout:
            Transport (top toolbar, 36px)
            ┌──────────┬───────────────────────────────┐
            │  File    │  vertical splitter:            │
            │  Browser │    top: SessionView            │
            │  (dock)  │    bottom: DetailView (~280px) │
            └──────────┴───────────────────────────────┘
            StatusBar (bottom)
        """

        # ---- Transport bar (fixed at top of window) ----------------------
        self._transport = TransportWidget()
        self._transport.setFixedHeight(36)

        transport_container = QWidget()
        transport_container.setFixedHeight(36)
        tl = QVBoxLayout(transport_container)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        tl.addWidget(self._transport)

        # ---- Right-side vertical splitter: Session + Detail ---------------
        self._session_view = SessionView()
        self._detail_view = DetailView()

        self._right_splitter = QSplitter(Qt.Orientation.Vertical)
        self._right_splitter.setHandleWidth(3)
        self._right_splitter.addWidget(self._session_view)
        self._right_splitter.addWidget(self._detail_view)
        self._right_splitter.setStretchFactor(0, 3)
        self._right_splitter.setStretchFactor(1, 1)
        # Initial sizes: session gets remaining space, detail ~280px
        self._right_splitter.setSizes([600, 280])

        # ---- Assemble central widget: transport on top, content below ----
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(transport_container)
        central_layout.addWidget(self._right_splitter, 1)

        self.setCentralWidget(central)

        # ---- Left dock: file browser (~220px) -----------------------------
        self._file_browser = FileBrowser(root_path=self._last_dir)
        self._dock_browser = QDockWidget("Browser", self)
        self._dock_browser.setWidget(self._file_browser)
        self._dock_browser.setMinimumWidth(220)
        self._dock_browser.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._dock_browser)

        # ---- Cubase 15 스타일 트랙 인스펙터 (Left Zone) -------------------
        self._track_inspector = TrackInspectorPanel()
        self._dock_inspector = QDockWidget("Inspector", self)
        self._dock_inspector.setWidget(self._track_inspector)
        self._dock_inspector.setMinimumWidth(280)
        self._dock_inspector.setMaximumWidth(360)
        self._dock_inspector.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._dock_inspector)
        self._dock_inspector.setVisible(ZONE_DEFAULTS["left_inspector"])

    # ===================================================================
    # Menu bar
    # ===================================================================

    def _create_menus(self) -> None:
        """Build all menus and their actions."""
        menubar = self.menuBar()

        # ---- File menu ---------------------------------------------------
        file_menu = menubar.addMenu("&File")

        self._act_new = file_menu.addAction("&New Project")
        self._act_new.setShortcut(QKeySequence("Ctrl+N"))
        self._act_new.triggered.connect(self._new_project)

        self._act_open = file_menu.addAction("&Open Project...")
        self._act_open.setShortcut(QKeySequence("Ctrl+O"))
        self._act_open.triggered.connect(self._open_project)

        self._recent_menu = file_menu.addMenu("Open &Recent")
        self._rebuild_recent_menu()

        self._act_import_midi = file_menu.addAction("&Import MIDI...")
        self._act_import_midi.setShortcut(QKeySequence("Ctrl+I"))
        self._act_import_midi.triggered.connect(self._import_midi)

        file_menu.addSeparator()

        self._act_save = file_menu.addAction("&Save")
        self._act_save.setShortcut(QKeySequence("Ctrl+S"))
        self._act_save.triggered.connect(self._save_project)

        self._act_save_as = file_menu.addAction("Save &As...")
        self._act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._act_save_as.triggered.connect(self._save_project_as)

        file_menu.addSeparator()

        self._act_export_midi = file_menu.addAction("Export &MIDI...")
        self._act_export_midi.setShortcut(QKeySequence("Ctrl+E"))
        self._act_export_midi.triggered.connect(self._export_midi)

        self._act_export_wav = file_menu.addAction("Export &WAV...")
        self._act_export_wav.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self._act_export_wav.triggered.connect(self._export_wav)

        file_menu.addSeparator()

        self._act_quit = file_menu.addAction("&Quit")
        self._act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self._act_quit.triggered.connect(self.close)

        # ---- Edit menu ---------------------------------------------------
        edit_menu = menubar.addMenu("&Edit")

        self._act_undo = edit_menu.addAction("&Undo")
        self._act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self._act_undo.triggered.connect(self._undo)

        self._act_redo = edit_menu.addAction("&Redo")
        self._act_redo.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        self._act_redo.triggered.connect(self._redo)

        edit_menu.addSeparator()

        self._act_cut = edit_menu.addAction("Cu&t")
        self._act_cut.setShortcut(QKeySequence("Ctrl+X"))
        self._act_cut.triggered.connect(self._cut)

        self._act_copy = edit_menu.addAction("&Copy")
        self._act_copy.setShortcut(QKeySequence("Ctrl+C"))
        self._act_copy.triggered.connect(self._copy)

        self._act_paste = edit_menu.addAction("&Paste")
        self._act_paste.setShortcut(QKeySequence("Ctrl+V"))
        self._act_paste.triggered.connect(self._paste)

        self._act_delete = edit_menu.addAction("&Delete")
        self._act_delete.setShortcut(QKeySequence.StandardKey.Delete)
        self._act_delete.triggered.connect(self._delete_selected)

        self._act_select_all = edit_menu.addAction("Select &All")
        self._act_select_all.setShortcut(QKeySequence("Ctrl+A"))
        self._act_select_all.triggered.connect(self._select_all)

        edit_menu.addSeparator()

        self._act_quantize = edit_menu.addAction("&Quantize")
        self._act_quantize.setShortcut(QKeySequence("Ctrl+U"))
        self._act_quantize.triggered.connect(self._quantize)

        self._act_humanize = edit_menu.addAction("&Humanize")
        self._act_humanize.triggered.connect(lambda: self._humanize_track(0.3, 0.3))

        self._act_transpose_up = edit_menu.addAction("Transpose &Up")
        self._act_transpose_up.setShortcut(QKeySequence("Ctrl+Up"))
        self._act_transpose_up.triggered.connect(lambda: self._transpose(1))

        self._act_transpose_down = edit_menu.addAction("Transpose &Down")
        self._act_transpose_down.setShortcut(QKeySequence("Ctrl+Down"))
        self._act_transpose_down.triggered.connect(lambda: self._transpose(-1))

        # ---- Create menu -------------------------------------------------
        create_menu = menubar.addMenu("&Create")

        self._act_add_midi_track = create_menu.addAction("Add &MIDI Track")
        self._act_add_midi_track.setShortcut(QKeySequence("Ctrl+T"))
        self._act_add_midi_track.triggered.connect(self._add_track)

        self._act_add_audio_track = create_menu.addAction("Add &Audio Track")
        self._act_add_audio_track.setEnabled(False)

        self._act_add_return_track = create_menu.addAction("Add &Return Track")
        self._act_add_return_track.setEnabled(False)

        # ---- View menu ---------------------------------------------------
        view_menu = menubar.addMenu("&View")

        self._act_toggle_inspector = view_menu.addAction("Toggle &Inspector")
        self._act_toggle_inspector.setShortcut(QKeySequence("Ctrl+Shift+I"))
        self._act_toggle_inspector.triggered.connect(
            lambda: self._dock_inspector.setVisible(
                not self._dock_inspector.isVisible()
            )
        )

        self._act_toggle_browser = view_menu.addAction("Toggle File &Browser")
        self._act_toggle_browser.setShortcut(QKeySequence("Ctrl+B"))
        self._act_toggle_browser.triggered.connect(
            lambda: self._dock_browser.setVisible(not self._dock_browser.isVisible())
        )

        self._act_toggle_detail = view_menu.addAction("Toggle &Detail Panel")
        self._act_toggle_detail.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self._act_toggle_detail.triggered.connect(self._toggle_detail)

        view_menu.addSeparator()

        self._act_zoom_in = view_menu.addAction("Zoom &In")
        self._act_zoom_in.setShortcut(QKeySequence("Ctrl+="))
        self._act_zoom_in.triggered.connect(self._zoom_in)

        self._act_zoom_out = view_menu.addAction("Zoom &Out")
        self._act_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        self._act_zoom_out.triggered.connect(self._zoom_out)

        self._act_zoom_fit = view_menu.addAction("Zoom to &Fit")
        self._act_zoom_fit.setShortcut(QKeySequence("Ctrl+0"))
        self._act_zoom_fit.triggered.connect(self._zoom_fit)

        view_menu.addSeparator()

        self._act_session_view = view_menu.addAction("&Session View")
        self._act_session_view.setCheckable(True)
        self._act_session_view.setChecked(True)
        self._act_session_view.setEnabled(True)

        self._act_arrangement_view = view_menu.addAction("&Arrangement View")
        self._act_arrangement_view.setCheckable(True)
        self._act_arrangement_view.setChecked(False)
        self._act_arrangement_view.setEnabled(False)  # Future

        view_menu.addSeparator()

        # ---- Cubase 15 스타일 존 토글 ----
        self._act_toggle_inspector = view_menu.addAction("Toggle &Inspector")
        self._act_toggle_inspector.setShortcut(QKeySequence("Ctrl+Shift+I"))
        self._act_toggle_inspector.triggered.connect(self._toggle_inspector)

        self._act_toggle_chord_pads = view_menu.addAction("Toggle &Chord Pads")
        self._act_toggle_chord_pads.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self._act_toggle_chord_pads.triggered.connect(
            lambda: self._detail_view.show_tab("chord_pads")
        )

        self._act_toggle_expr_map = view_menu.addAction("Toggle &Expression Map")
        self._act_toggle_expr_map.setShortcut(QKeySequence("Ctrl+Shift+X"))
        self._act_toggle_expr_map.triggered.connect(
            lambda: self._detail_view.show_tab("expr_map")
        )

        # ---- AI menu -----------------------------------------------------
        ai_menu = menubar.addMenu("A&I")

        ai_menu.addAction("Generate &Melody").triggered.connect(
            lambda: self._ai_generate("melody")
        )
        ai_menu.addAction("Generate &Chords").triggered.connect(
            lambda: self._ai_generate("chords")
        )
        ai_menu.addAction("Generate &Bass").triggered.connect(
            lambda: self._ai_generate("bass")
        )

        ai_menu.addSeparator()

        ai_menu.addAction("Generate &Variation").triggered.connect(
            self._ai_variation_quick
        )

        ai_menu.addSeparator()

        ai_menu.addAction("&Humanize Track").triggered.connect(
            lambda: self._humanize_track(0.3, 0.3)
        )
        ai_menu.addAction("&Analyze Track").triggered.connect(self._analyze_track)
        ai_menu.addAction("&Scale Snap").triggered.connect(self._scale_snap)

        # ---- Help menu ---------------------------------------------------
        help_menu = menubar.addMenu("&Help")

        help_menu.addAction("&About").triggered.connect(self._about)
        help_menu.addAction("&Keyboard Shortcuts").triggered.connect(
            self._show_shortcuts
        )
        self._act_info_view = help_menu.addAction("&Info View")
        self._act_info_view.setCheckable(True)
        self._act_info_view.setChecked(False)
        self._act_info_view.triggered.connect(self._toggle_info_view)

    # ===================================================================
    # Status bar
    # ===================================================================

    def _create_status_bar(self) -> None:
        """Set up the status bar with persistent labels."""
        sb = self.statusBar()
        sb.setFont(QFont("Segoe UI", 9))

        # Left: project name + modified indicator
        self._status_project_label = QLabel("Project: Untitled")
        self._status_project_label.setMinimumWidth(180)
        sb.addWidget(self._status_project_label)

        # Center: track count, note count
        self._status_track_label = QLabel("Tracks: 0  |  Notes: 0")
        self._status_track_label.setMinimumWidth(200)
        sb.addWidget(self._status_track_label)

        # Right: engine status, audio engine status
        self._status_engine_label = QLabel("")
        self._status_engine_label.setMinimumWidth(200)
        sb.addPermanentWidget(self._status_engine_label)

        # Show audio engine status
        midi_status = "MIDI: Ready"
        if self._audio_engine.available:
            audio_status = "Audio: Ready"
        else:
            audio_status = "Audio: Unavailable (no FluidSynth)"
        self._status_engine_label.setText(f"{midi_status}  |  {audio_status}")

    # ===================================================================
    # Signal wiring — complete connections
    # ===================================================================

    def _connect_signals(self) -> None:
        """Wire every signal across all UI panels and engines."""

        # ---- Transport -> Engine / State ---------------------------------
        self._transport.play_clicked.connect(self._on_play)
        self._transport.stop_clicked.connect(self._on_stop)
        self._transport.rewind_clicked.connect(lambda: self._midi_engine.seek(0))
        self._transport.bpm_changed.connect(self._on_bpm_changed)
        self._transport.key_changed.connect(self._on_key_changed)
        self._transport.scale_changed.connect(self._on_scale_changed)
        self._transport.snap_changed.connect(self._on_snap_changed)
        self._transport.loop_toggled.connect(self._on_loop_toggled)

        # ---- Engine -> UI ------------------------------------------------
        self._midi_engine.position_changed.connect(self._on_position_changed)
        self._midi_engine.playback_state_changed.connect(
            self._on_playback_state_changed
        )

        # ---- Session View ------------------------------------------------
        self._session_view.track_selected.connect(self._on_track_selected)
        self._session_view.clip_opened.connect(self._on_clip_opened)
        self._session_view.track_added.connect(self._on_session_track_added)
        self._session_view.track_removed.connect(self._on_session_track_removed)

        # ---- Detail View -------------------------------------------------
        self._detail_view.generate_requested.connect(self._on_generate)
        self._detail_view.variation_requested.connect(self._on_variation)
        self._detail_view.humanize_requested.connect(self._humanize_track)
        self._detail_view.quantize_requested.connect(self._on_quantize_request)
        self._detail_view.analyze_requested.connect(self._analyze_track)
        self._detail_view.scale_snap_requested.connect(self._on_scale_snap)
        self._detail_view.note_added.connect(self._on_note_added)
        self._detail_view.note_removed.connect(self._on_note_removed)
        self._detail_view.note_modified.connect(self._on_note_modified)
        # selection_changed forwarded if available
        if hasattr(self._detail_view, 'selection_changed'):
            self._detail_view.selection_changed.connect(self._on_selection_changed)

        # ---- Track Inspector -> Engine ------------------------------------
        if hasattr(self, '_dock_inspector') and self._dock_inspector is not None:
            inspector = self._track_inspector

            def _on_inspector_volume(val: int) -> None:
                idx = self._selected_track_index
                p = self._project_manager.state
                if 0 <= idx < len(p.tracks):
                    p.tracks[idx].volume = val
                    self._audio_engine.set_channel_volume(p.tracks[idx].channel, val)
                    self._mark_modified()

            def _on_inspector_pan(val: int) -> None:
                idx = self._selected_track_index
                p = self._project_manager.state
                if 0 <= idx < len(p.tracks):
                    p.tracks[idx].pan = val
                    self._audio_engine.set_channel_pan(p.tracks[idx].channel, val)
                    self._mark_modified()

            def _on_inspector_program(prog: int) -> None:
                idx = self._selected_track_index
                p = self._project_manager.state
                if 0 <= idx < len(p.tracks):
                    p.tracks[idx].instrument = prog
                    self._audio_engine.program_change(p.tracks[idx].channel, prog)
                    self._mark_modified()

            def _on_inspector_mute(muted: bool) -> None:
                idx = self._selected_track_index
                p = self._project_manager.state
                if 0 <= idx < len(p.tracks):
                    p.tracks[idx].muted = muted
                    self._mark_modified()
                    self._refresh_all()

            def _on_inspector_solo(solo: bool) -> None:
                idx = self._selected_track_index
                p = self._project_manager.state
                if 0 <= idx < len(p.tracks):
                    p.tracks[idx].solo = solo
                    self._mark_modified()
                    self._refresh_all()

            inspector.volume_changed.connect(_on_inspector_volume)
            inspector.pan_changed.connect(_on_inspector_pan)
            inspector.program_changed.connect(_on_inspector_program)
            inspector.mute_toggled.connect(_on_inspector_mute)
            inspector.solo_toggled.connect(_on_inspector_solo)

        # ---- File browser ------------------------------------------------
        self._file_browser.file_double_clicked.connect(self._on_file_activated)

        # ---- Project manager ---------------------------------------------
        self._project_manager.project_saved.connect(
            lambda p: self.statusBar().showMessage(f"Project saved: {p}", 4000)
        )
        self._project_manager.auto_saved.connect(
            lambda p: self.statusBar().showMessage("Auto-saved", 2000)
        )

    # ===================================================================
    # Project state management
    # ===================================================================

    def _project(self) -> ProjectState:
        """Convenience accessor for the current project state."""
        return self._project_manager.state

    def _apply_project(self, project: ProjectState) -> None:
        """Push a project state to every UI panel and engine."""
        self._midi_engine.project = project
        self._transport.set_project(project)
        self._session_view.set_project(project)
        self._detail_view.set_project(project)

        # Select the first track
        if project.tracks:
            self._selected_track_index = 0
            self._detail_view.set_track(project.tracks[0], 0)
            # Update inspector panel
            if hasattr(self, '_track_inspector') and hasattr(self._track_inspector, 'set_track'):
                self._track_inspector.set_track(project.tracks[0], 0)
        else:
            self._selected_track_index = -1

        self._undo_manager.clear()
        self._update_title()
        self._update_status()

    def _push_undo(self, description: str) -> None:
        """Snapshot current state before a modification for undo."""
        old = copy.deepcopy(self._project())
        # Caller is expected to mutate state AFTER calling this, so we
        # defer new-state capture via a zero-delay timer.
        QTimer.singleShot(0, lambda: self._undo_manager.push(
            description, old, copy.deepcopy(self._project())
        ))

    def _mark_modified(self) -> None:
        """Mark the project as modified and refresh the title bar."""
        self._project().modified = True
        self._update_title()

    def _refresh_all(self) -> None:
        """Refresh every panel from current project state."""
        project = self._project()
        self._session_view.set_project(project)
        self._transport.set_project(project)
        if 0 <= self._selected_track_index < len(project.tracks):
            self._detail_view.set_track(project.tracks[self._selected_track_index])
        self._update_status()

    # ===================================================================
    # File operations
    # ===================================================================

    def _new_project(self) -> None:
        if not self._confirm_discard():
            return
        self._midi_engine.stop()
        project = self._project_manager.new_project()
        self._apply_project(project)
        self.statusBar().showMessage("New project created", 3000)

    def _open_project(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", self._last_dir, _FILE_FILTER_PROJECT
        )
        if not path:
            return
        try:
            self._midi_engine.stop()
            project = self._project_manager.load_project(path)
            self._apply_project(project)
            self._remember_dir(path)
            self._rebuild_recent_menu()
            self.statusBar().showMessage(f"Opened: {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Open Error", f"Failed to open project:\n{exc}")

    def _open_recent(self, path: str) -> None:
        if not self._confirm_discard():
            return
        try:
            self._midi_engine.stop()
            project = self._project_manager.load_project(path)
            self._apply_project(project)
            self._remember_dir(path)
            self._rebuild_recent_menu()
        except Exception as exc:
            QMessageBox.critical(self, "Open Error", f"Failed to open:\n{exc}")

    def _save_project(self) -> None:
        path = self._project().file_path
        if path and path.endswith(".maw"):
            self._project_manager.state = self._project()
            self._project_manager.save_project(path)
            self._project().modified = False
            self._update_title()
        else:
            self._save_project_as()

    def _save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", self._last_dir, _FILE_FILTER_PROJECT
        )
        if not path:
            return
        if not path.endswith(".maw"):
            path += ".maw"
        self._project_manager.state = self._project()
        self._project_manager.save_project(path)
        self._project().file_path = path
        self._project().modified = False
        self._remember_dir(path)
        self._rebuild_recent_menu()
        self._update_title()

    def _import_midi(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import MIDI", self._last_dir, _FILE_FILTER_MIDI
        )
        if not path:
            return
        try:
            self._midi_engine.stop()
            project = self._project_manager.import_midi(path)
            self._apply_project(project)
            self._remember_dir(path)
            self._file_browser.add_recent(path)
            self.statusBar().showMessage(f"Imported: {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", f"Failed to import MIDI:\n{exc}")

    def _export_midi(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export MIDI", self._last_dir, _FILE_FILTER_MIDI
        )
        if not path:
            return
        if not path.lower().endswith((".mid", ".midi")):
            path += ".mid"
        try:
            self._project_manager.export_midi(path)
            self._remember_dir(path)
            self.statusBar().showMessage(f"Exported MIDI: {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{exc}")

    def _export_wav(self) -> None:
        if not self._audio_engine.available:
            QMessageBox.warning(
                self, "Audio Unavailable",
                "FluidSynth is not available. Cannot render audio.\n"
                "Install pyfluidsynth and a SoundFont to enable WAV export."
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export WAV", self._last_dir, _FILE_FILTER_WAV
        )
        if not path:
            return
        if not path.lower().endswith(".wav"):
            path += ".wav"
        self.statusBar().showMessage("Rendering WAV... Please wait.", 0)
        QApplication.processEvents()
        success = self._audio_engine.render_to_wav(self._project(), path)
        if success:
            self._remember_dir(path)
            self.statusBar().showMessage(f"Exported WAV: {path}", 5000)
        else:
            QMessageBox.warning(self, "Export Failed", "WAV rendering failed.")
            self.statusBar().showMessage("WAV export failed", 4000)

    # ===================================================================
    # Transport / playback callbacks
    # ===================================================================

    def _on_play(self) -> None:
        self._midi_engine.toggle_playback()

    def _on_stop(self) -> None:
        self._midi_engine.stop()

    def _on_position_changed(self, tick: int) -> None:
        self._transport.update_position(tick, self._project())
        self._detail_view.update_playhead(tick)
        self._session_view.update_playhead(tick)

    def _on_playback_state_changed(self, state: str) -> None:
        self._transport.set_playing(state == "playing")
        if state == "stopped":
            self._transport.set_playing(False)

    def _on_bpm_changed(self, bpm: float) -> None:
        self._push_undo("Change BPM")
        self._project().bpm = bpm
        self._mark_modified()

    def _on_key_changed(self, key: str) -> None:
        self._project().key = key
        self._mark_modified()

    def _on_scale_changed(self, scale: str) -> None:
        self._project().scale = scale
        self._mark_modified()

    def _on_snap_changed(self, snap: float) -> None:
        """Forward transport snap value to detail view piano roll."""
        self._detail_view.set_snap(snap)

    def _on_loop_toggled(self, enabled: bool) -> None:
        self._project().loop_enabled = enabled
        self._mark_modified()

    # ===================================================================
    # Session View callbacks
    # ===================================================================

    def _on_track_selected(self, index: int) -> None:
        """Handle track selection from session view."""
        project = self._project()
        if 0 <= index < len(project.tracks):
            self._selected_track_index = index
            self._detail_view.set_track(project.tracks[index])
            # Update inspector panel if available
            if hasattr(self, '_track_inspector') and hasattr(self._track_inspector, 'set_track'):
                self._track_inspector.set_track(project.tracks[index], index)
            self._update_status()

    def _on_clip_opened(self, track_index: int, clip_index: int) -> None:
        """Handle clip double-click — switch detail to Notes tab, load clip."""
        project = self._project()
        if 0 <= track_index < len(project.tracks):
            self._selected_track_index = track_index
            track = project.tracks[track_index]
            self._detail_view.set_track(track)
            self._detail_view.switch_to_notes_tab()
            # Ensure detail view is visible
            if self._detail_view.isHidden():
                self._detail_view.show()
            self._update_status()

    def _on_session_track_added(self) -> None:
        """Handle track added from session view."""
        self._push_undo("Add track")
        project = self._project()
        idx = len(project.tracks)
        new_track = Track(
            name=f"Track {idx + 1}",
            channel=min(idx, 15),
            color=TRACK_COLORS[idx % len(TRACK_COLORS)],
        )
        project.tracks.append(new_track)
        self._mark_modified()
        self._refresh_all()
        self._on_track_selected(idx)

    def _on_session_track_removed(self, index: int) -> None:
        """Handle track removed from session view."""
        project = self._project()
        if len(project.tracks) <= 1:
            self.statusBar().showMessage("Cannot delete the last track", 3000)
            return
        if 0 <= index < len(project.tracks):
            self._push_undo("Delete track")
            project.tracks.pop(index)
            if self._selected_track_index >= len(project.tracks):
                self._selected_track_index = max(0, len(project.tracks) - 1)
            self._mark_modified()
            self._refresh_all()

    # ===================================================================
    # Note editing callbacks (from detail view piano roll)
    # ===================================================================

    def _on_note_added(self, note: Note) -> None:
        self._push_undo("Add note")
        self._mark_modified()
        self._session_view.refresh()
        self._update_status()

    def _on_note_removed(self, note: Note) -> None:
        self._push_undo("Remove note")
        self._mark_modified()
        self._session_view.refresh()
        self._update_status()

    def _on_note_modified(self, note: Note) -> None:
        self._mark_modified()
        self._session_view.refresh()

    def _on_selection_changed(self) -> None:
        selected = self._detail_view.get_selected_notes()
        count = len(selected)
        self.statusBar().showMessage(
            f"{count} note{'s' if count != 1 else ''} selected" if count else "", 2000
        )

    # ===================================================================
    # Edit operations
    # ===================================================================

    def _undo(self) -> None:
        state = self._undo_manager.undo()
        if state is not None:
            self._project_manager.state = state
            self._apply_project(state)
            self.statusBar().showMessage("Undo", 2000)

    def _redo(self) -> None:
        state = self._undo_manager.redo()
        if state is not None:
            self._project_manager.state = state
            self._apply_project(state)
            self.statusBar().showMessage("Redo", 2000)

    def _cut(self) -> None:
        selected = self._detail_view.get_selected_notes()
        if selected:
            self._push_undo("Cut notes")
            self._midi_engine.cut_notes(self._selected_track_index, selected)
            self._detail_view.set_track(
                self._project().tracks[self._selected_track_index]
            )
            self._mark_modified()
            self._session_view.refresh()

    def _copy(self) -> None:
        selected = self._detail_view.get_selected_notes()
        if selected:
            self._midi_engine.copy_notes(selected)
            self.statusBar().showMessage(f"Copied {len(selected)} notes", 2000)

    def _paste(self) -> None:
        if self._midi_engine.clipboard_empty:
            return
        self._push_undo("Paste notes")
        pasted = self._midi_engine.paste_notes(self._selected_track_index)
        if pasted:
            self._detail_view.set_track(
                self._project().tracks[self._selected_track_index]
            )
            self._mark_modified()
            self._session_view.refresh()
            self.statusBar().showMessage(f"Pasted {len(pasted)} notes", 2000)

    def _delete_selected(self) -> None:
        selected = self._detail_view.get_selected_notes()
        if not selected:
            return
        self._push_undo("Delete notes")
        project = self._project()
        if 0 <= self._selected_track_index < len(project.tracks):
            track = project.tracks[self._selected_track_index]
            for note in selected:
                track.remove_note(note)
            self._detail_view.set_track(track)
            self._mark_modified()
            self._session_view.refresh()

    def _select_all(self) -> None:
        self._detail_view.select_all()

    def _quantize(self) -> None:
        selected = self._detail_view.get_selected_notes()
        if not selected:
            # Quantize entire track
            project = self._project()
            if 0 <= self._selected_track_index < len(project.tracks):
                selected = project.tracks[self._selected_track_index].notes
        if not selected:
            return
        self._push_undo("Quantize")
        snap = self._detail_view.snap_value
        grid = int(snap * TICKS_PER_BEAT) if snap > 0 else TICKS_PER_BEAT
        self._midi_engine.quantize_notes(selected, grid)
        self._detail_view.set_track(
            self._project().tracks[self._selected_track_index]
        )
        self._mark_modified()
        self.statusBar().showMessage("Quantized", 2000)

    def _transpose(self, semitones: int) -> None:
        selected = self._detail_view.get_selected_notes()
        if not selected:
            return
        self._push_undo(f"Transpose {'up' if semitones > 0 else 'down'}")
        self._midi_engine.transpose_notes(selected, semitones)
        self._detail_view.set_track(
            self._project().tracks[self._selected_track_index]
        )
        self._mark_modified()

    # ===================================================================
    # Track operations
    # ===================================================================

    def _add_track(self) -> None:
        self._on_session_track_added()

    def _toggle_mute(self) -> None:
        project = self._project()
        if 0 <= self._selected_track_index < len(project.tracks):
            track = project.tracks[self._selected_track_index]
            track.muted = not track.muted
            self._mark_modified()
            self._refresh_all()

    def _toggle_solo(self) -> None:
        project = self._project()
        if 0 <= self._selected_track_index < len(project.tracks):
            track = project.tracks[self._selected_track_index]
            track.solo = not track.solo
            self._mark_modified()
            self._refresh_all()

    # ===================================================================
    # AI operations
    # ===================================================================

    def _on_generate(self, params: dict) -> None:
        """Handle AI generation request from the detail view."""
        project = self._project()
        track_type = params.get("track_type", "melody")
        style = params.get("style", "pop")
        bars = params.get("length_bars", 8)
        density = params.get("density", 0.5)
        octave = params.get("octave_low", 4)
        length_beats = bars * project.time_signature.numerator

        self._push_undo(f"AI Generate {track_type}")

        try:
            if track_type == "melody":
                new_track = self._ai_engine.generate_melody(
                    key=project.key, scale=project.scale,
                    length_beats=length_beats, style=style,
                    density=density, octave=octave,
                )
            elif track_type == "chords":
                new_track = self._ai_engine.generate_chords(
                    key=project.key, scale=project.scale,
                    length_beats=length_beats, style=style, octave=octave,
                )
            elif track_type == "bass":
                # Try to use a chord track as reference
                chord_track = None
                for t in project.tracks:
                    if "chord" in t.name.lower():
                        chord_track = t
                        break
                new_track = self._ai_engine.generate_bass(
                    key=project.key, scale=project.scale,
                    length_beats=length_beats, style=style,
                    chord_track=chord_track, octave=octave,
                )
            else:
                new_track = self._ai_engine.generate_melody(
                    key=project.key, scale=project.scale,
                    length_beats=length_beats, style=style,
                    density=density, octave=octave,
                )

            if params.get("add_track", False):
                # Add as new track
                idx = len(project.tracks)
                new_track.color = TRACK_COLORS[idx % len(TRACK_COLORS)]
                new_track.channel = min(idx, 15)
                project.tracks.append(new_track)
                self._mark_modified()
                self._refresh_all()
                self._on_track_selected(idx)
            else:
                # Replace notes in selected track
                if 0 <= self._selected_track_index < len(project.tracks):
                    target = project.tracks[self._selected_track_index]
                    target.notes = new_track.notes
                    self._mark_modified()
                    self._refresh_all()

            self.statusBar().showMessage(
                f"Generated {track_type} ({len(new_track.notes)} notes)", 4000
            )
        except Exception as exc:
            logger.exception("AI generation failed")
            QMessageBox.warning(self, "Generation Error", str(exc))

    def _on_variation(self, params: dict) -> None:
        """Handle variation request from the detail view."""
        project = self._project()
        if not (0 <= self._selected_track_index < len(project.tracks)):
            return

        source = project.tracks[self._selected_track_index]
        if not source.notes:
            self.statusBar().showMessage("Track has no notes to vary", 3000)
            return

        var_type = params.get("type", "Mixed").lower()
        intensity = params.get("intensity", 0.3)

        self._push_undo("AI Variation")
        try:
            result = self._ai_engine.generate_variation(
                source, variation_type=var_type, intensity=intensity,
                key=project.key, scale=project.scale,
            )
            if params.get("keep_original", True):
                # Add variation as new track
                result.name = f"{source.name} (var)"
                idx = len(project.tracks)
                result.color = TRACK_COLORS[idx % len(TRACK_COLORS)]
                result.channel = min(idx, 15)
                project.tracks.append(result)
                self._mark_modified()
                self._refresh_all()
                self._on_track_selected(idx)
            else:
                # Replace in-place
                source.notes = result.notes
                self._mark_modified()
                self._refresh_all()

            self.statusBar().showMessage(
                f"Variation generated ({len(result.notes)} notes)", 4000
            )
        except Exception as exc:
            logger.exception("AI variation failed")
            QMessageBox.warning(self, "Variation Error", str(exc))

    def _ai_generate(self, track_type: str) -> None:
        """Quick AI generation from the menu."""
        params = {
            "track_type": track_type,
            "style": "pop",
            "length_bars": 8,
            "density": 0.5,
            "octave_low": 4 if track_type == "melody" else (3 if track_type == "chords" else 2),
            "add_track": True,
        }
        self._on_generate(params)

    def _ai_variation_quick(self) -> None:
        """Quick variation from the menu."""
        params = {
            "type": "Mixed",
            "intensity": 0.4,
            "keep_original": True,
            "selection_only": False,
            "preview": False,
        }
        self._on_variation(params)

    def _humanize_track(self, timing: float, velocity: float) -> None:
        """Apply humanize to the selected track."""
        project = self._project()
        if not (0 <= self._selected_track_index < len(project.tracks)):
            return
        source = project.tracks[self._selected_track_index]
        if not source.notes:
            return
        self._push_undo("Humanize")
        result = self._ai_engine.humanize(source, timing, velocity)
        source.notes = result.notes
        self._mark_modified()
        self._refresh_all()
        self.statusBar().showMessage("Humanized", 2000)

    def _analyze_track(self) -> None:
        """Run AI analysis on the selected track and display results."""
        project = self._project()
        if not (0 <= self._selected_track_index < len(project.tracks)):
            return
        track = project.tracks[self._selected_track_index]
        analysis = self._ai_engine.analyze_track(track, project.key, project.scale)

        # Build a readable summary
        lines = [
            f"Notes: {analysis['note_count']}",
            f"Pitch range: {analysis.get('pitch_min', '?')} - {analysis.get('pitch_max', '?')}",
            f"Velocity: {analysis.get('velocity_min', '?')} - {analysis.get('velocity_max', '?')} "
            f"(avg {analysis.get('velocity_mean', '?')})",
            f"Density: {analysis.get('density_notes_per_beat', 0):.1f} notes/beat",
            f"Scale consistency: {(analysis.get('scale_consistency', 0) * 100):.0f}%",
        ]

        # Build review data
        sc = analysis.get("scale_consistency", 0)
        vel_min = analysis.get("velocity_min", 0) or 0
        vel_max = analysis.get("velocity_max", 0) or 0
        vel_range = vel_max - vel_min if vel_max > vel_min else 0
        review = {
            "score": int(sc * 100),
            "scale_consistency": int(sc * 100),
            "velocity_dynamics": min(100, int(vel_range * 1.5)),
            "rhythm_regularity": 65,
            "note_diversity": min(100, len(set(
                n.pitch % 12 for n in track.notes
            )) * 10) if track.notes else 0,
            "issues": [],
            "pitch_distribution": analysis.get("pitch_histogram", {}),
        }
        if sc < 0.7:
            review["issues"].append("Low scale consistency - many out-of-scale notes")
        if analysis.get("note_count", 0) < 4:
            review["issues"].append("Very few notes - consider adding more content")
        if vel_range < 15:
            review["issues"].append("Flat velocity - consider adding dynamics")

        self._detail_view.show_analysis("\n".join(lines), review)
        self.statusBar().showMessage("Analysis complete", 3000)

    def _scale_snap(self) -> None:
        """Snap notes to the current project key/scale."""
        project = self._project()
        self._on_scale_snap(project.key, project.scale)

    def _on_scale_snap(self, key: str, scale: str) -> None:
        """Snap all notes in the selected track to the given scale."""
        from core.models import get_scale_pitches
        project = self._project()
        if not (0 <= self._selected_track_index < len(project.tracks)):
            return
        track = project.tracks[self._selected_track_index]
        if not track.notes:
            return

        self._push_undo("Scale snap")
        root = key_name_to_root(key)
        scale_pitches = get_scale_pitches(root, scale.lower().replace(" ", "_"))

        import numpy as np
        sp_arr = np.array(scale_pitches)
        for note in track.notes:
            if note.pitch not in scale_pitches:
                idx = int(np.argmin(np.abs(sp_arr - note.pitch)))
                note.pitch = scale_pitches[idx]

        self._mark_modified()
        self._refresh_all()
        self.statusBar().showMessage(f"Snapped to {key} {scale}", 2000)

    def _on_quantize_request(self, strength: float, grid: int) -> None:
        """Handle quantize request from detail view tools panel."""
        project = self._project()
        if not (0 <= self._selected_track_index < len(project.tracks)):
            return
        track = project.tracks[self._selected_track_index]
        if not track.notes:
            return
        self._push_undo("Quantize")
        grid_ticks = TICKS_PER_BEAT // (grid // 4) if grid >= 4 else TICKS_PER_BEAT
        self._midi_engine.quantize_notes(track.notes, grid_ticks, strength)
        self._detail_view.set_track(track)
        self._mark_modified()
        self.statusBar().showMessage(f"Quantized (1/{grid}, {int(strength*100)}%)", 2000)

    # ===================================================================
    # File browser
    # ===================================================================

    def _on_file_activated(self, path: str) -> None:
        """Handle double-click in the file browser."""
        ext = os.path.splitext(path)[1].lower()
        if ext == ".maw":
            self._open_recent(path)
        elif ext in (".mid", ".midi"):
            if not self._confirm_discard():
                return
            try:
                self._midi_engine.stop()
                project = self._project_manager.import_midi(path)
                self._apply_project(project)
                self._remember_dir(path)
                self.statusBar().showMessage(f"Imported: {path}", 4000)
            except Exception as exc:
                QMessageBox.critical(self, "Import Error", str(exc))

    # ===================================================================
    # View toggles
    # ===================================================================

    def _toggle_detail(self) -> None:
        """Toggle the detail view panel visibility."""
        if self._detail_view.isVisible():
            self._detail_view.hide()
        else:
            self._detail_view.show()

    def _toggle_inspector(self) -> None:
        """Cubase 스타일 트랙 인스펙터 토글."""
        if self._dock_inspector is not None:
            vis = not self._dock_inspector.isVisible()
            self._dock_inspector.setVisible(vis)
            if vis:
                self._dock_inspector.raise_()

    def _toggle_info_view(self, checked: bool) -> None:
        """Toggle the info view display."""
        self._detail_view.set_info_visible(checked)

    def _zoom_in(self) -> None:
        self._detail_view.zoom_in()

    def _zoom_out(self) -> None:
        self._detail_view.zoom_out()

    def _zoom_fit(self) -> None:
        self._detail_view.zoom_fit()

    # ===================================================================
    # Help
    # ===================================================================

    def _about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<h2>{APP_NAME}</h2>"
            f"<p>Version {APP_VERSION}</p>"
            f"<p>A commercial-grade MIDI AI workstation for music composition, "
            f"generation, and production.</p>"
            f"<p>Powered by AI-driven melody, chord, and bass generation "
            f"with intelligent variation and analysis.</p>"
            f"<hr>"
            f"<p style='color: {COLORS['text_secondary']}; font-size: 11px;'>"
            f"Built with PyQt6, mido, FluidSynth, and NumPy.</p>"
        )

    def _show_shortcuts(self) -> None:
        shortcuts = (
            "<table cellpadding='4'>"
            "<tr><td><b>Ctrl+N</b></td><td>New Project</td></tr>"
            "<tr><td><b>Ctrl+O</b></td><td>Open Project</td></tr>"
            "<tr><td><b>Ctrl+S</b></td><td>Save</td></tr>"
            "<tr><td><b>Ctrl+Shift+S</b></td><td>Save As</td></tr>"
            "<tr><td><b>Ctrl+I</b></td><td>Import MIDI</td></tr>"
            "<tr><td><b>Ctrl+E</b></td><td>Export MIDI</td></tr>"
            "<tr><td><b>Ctrl+Shift+E</b></td><td>Export WAV</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td><b>Ctrl+Z</b></td><td>Undo</td></tr>"
            "<tr><td><b>Ctrl+Shift+Z</b></td><td>Redo</td></tr>"
            "<tr><td><b>Ctrl+X</b></td><td>Cut</td></tr>"
            "<tr><td><b>Ctrl+C</b></td><td>Copy</td></tr>"
            "<tr><td><b>Ctrl+V</b></td><td>Paste</td></tr>"
            "<tr><td><b>Ctrl+A</b></td><td>Select All</td></tr>"
            "<tr><td><b>Ctrl+U</b></td><td>Quantize</td></tr>"
            "<tr><td><b>Ctrl+Up/Down</b></td><td>Transpose</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td><b>Ctrl+T</b></td><td>Add MIDI Track</td></tr>"
            "<tr><td><b>Ctrl+B</b></td><td>Toggle Browser</td></tr>"
            "<tr><td><b>Ctrl+Shift+D</b></td><td>Toggle Detail</td></tr>"
            "<tr><td><b>Ctrl+=/-</b></td><td>Zoom In/Out</td></tr>"
            "<tr><td><b>Ctrl+0</b></td><td>Zoom to Fit</td></tr>"
            "<tr><td><b>Space</b></td><td>Play/Pause</td></tr>"
            "</table>"
        )
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)

    # ===================================================================
    # VU meter simulation
    # ===================================================================

    def _simulate_meters(self) -> None:
        """Feed fake VU levels to the session view mixer while playing."""
        import random

        project = self._project()
        if self._midi_engine.state != "playing":
            self._session_view.update_meters(
                [0.0] * len(project.tracks)
            )
            return

        levels = []
        for track in project.tracks:
            if track.muted:
                levels.append(0.0)
            else:
                base = (track.volume / 127.0) * 0.7
                levels.append(base + random.uniform(0.0, 0.25))
        self._session_view.update_meters(levels)

    # ===================================================================
    # Helpers
    # ===================================================================

    def _update_title(self) -> None:
        """Update the window title with project name and modified indicator."""
        project = self._project()
        name = project.name or "Untitled"
        modified = " *" if project.modified else ""
        self.setWindowTitle(f"{name}{modified} - {APP_NAME} v{APP_VERSION}")

    def _update_status(self) -> None:
        """Update persistent status bar labels."""
        project = self._project()

        # Left: project name + modified indicator
        mod = " *" if project.modified else ""
        self._status_project_label.setText(
            f"Project: {project.name or 'Untitled'}{mod}"
        )

        # Center: track count, note count
        track_count = len(project.tracks)
        note_count = sum(len(t.notes) for t in project.tracks)
        self._status_track_label.setText(
            f"Tracks: {track_count}  |  Notes: {note_count}"
        )

    def _confirm_discard(self) -> bool:
        """If the project is modified, ask the user whether to save."""
        if not self._project().modified:
            return True
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "The current project has unsaved changes.\n"
            "Do you want to save before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        if reply == QMessageBox.StandardButton.Save:
            self._save_project()
        return True

    def _remember_dir(self, path: str) -> None:
        """Remember the directory of the given file path."""
        directory = os.path.dirname(os.path.abspath(path))
        self._last_dir = directory
        self._settings.setValue("last_directory", directory)

    def _rebuild_recent_menu(self) -> None:
        """Repopulate the Open Recent submenu."""
        self._recent_menu.clear()
        recent = self._project_manager.get_recent_files()
        if not recent:
            act = self._recent_menu.addAction("(No recent files)")
            act.setEnabled(False)
            return
        for path in recent:
            display = os.path.basename(path)
            act = self._recent_menu.addAction(display)
            act.setToolTip(path)
            act.triggered.connect(lambda checked, p=path: self._open_recent(p))
        self._recent_menu.addSeparator()
        clear_act = self._recent_menu.addAction("Clear Recent Files")
        clear_act.triggered.connect(self._project_manager.clear_recent_files)
        clear_act.triggered.connect(self._rebuild_recent_menu)

    # ===================================================================
    # Window state persistence
    # ===================================================================

    def _restore_state(self) -> None:
        """Restore saved window geometry and dock positions."""
        geom = self._settings.value("window_geometry")
        if geom is not None:
            self.restoreGeometry(geom)
        state = self._settings.value("window_state")
        if state is not None:
            self.restoreState(state)

    def _save_state(self) -> None:
        """Persist window geometry and dock positions."""
        self._settings.setValue("window_geometry", self.saveGeometry())
        self._settings.setValue("window_state", self.saveState())

    # ===================================================================
    # Event overrides
    # ===================================================================

    def closeEvent(self, event: QCloseEvent) -> None:
        """Prompt to save unsaved work and clean up engines on exit."""
        if not self._confirm_discard():
            event.ignore()
            return

        # Save window layout
        self._save_state()

        # Shut down engines
        self._midi_engine.shutdown()
        self._audio_engine.cleanup()
        self._meter_timer.stop()

        event.accept()
        logger.info("Application closed")
