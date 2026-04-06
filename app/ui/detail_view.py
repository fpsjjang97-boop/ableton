"""
Detail View — bottom panel modeled after Ableton Live's device/clip detail area.

Shows either the Piano Roll (clip/notes editor), AI generation tools,
AI variation controls, or analysis results, selected via tab-style buttons.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QPushButton,
    QFrame, QSplitter, QSizePolicy, QToolButton,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont

from config import COLORS
from ui.piano_roll import PianoRollWidget
from ui.ai_panel import AIPanel
from ui.review_panel import ReviewPanel
from ui.synth_panel import SynthPanel
from ui.effects_panel import EffectsChainPanel
from ui.step_sequencer import StepSequencerPanel
from ui.score_view import ScoreViewPanel


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

_TITLE_BAR_STYLE = f"""
    QFrame {{
        background: {COLORS['bg_header']};
        border-bottom: 1px solid {COLORS['border']};
    }}
"""

_TAB_BTN_STYLE = f"""
    QPushButton {{
        background: transparent;
        color: {COLORS['text_dim']};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        color: {COLORS['text_secondary']};
        background: {COLORS['bg_hover']};
    }}
"""

_TAB_BTN_ACTIVE = f"""
    QPushButton {{
        background: transparent;
        color: {COLORS['text_primary']};
        border: none;
        border-bottom: 2px solid {COLORS['accent']};
        padding: 4px 10px;
        font-size: 11px;
        font-weight: bold;
    }}
"""

_COLLAPSE_BTN_STYLE = f"""
    QToolButton {{
        background: transparent;
        color: {COLORS['text_secondary']};
        border: none;
        font-size: 10px;
        padding: 2px 4px;
    }}
    QToolButton:hover {{
        color: {COLORS['text_primary']};
        background: {COLORS['bg_hover']};
        border-radius: 2px;
    }}
"""

_CONTEXT_LABEL_STYLE = f"""
    color: {COLORS['text_secondary']};
    font-size: 11px;
    padding: 0 8px;
"""


# ---------------------------------------------------------------------------
# Tab definitions
# ---------------------------------------------------------------------------

_TABS = [
    ("notes",        "Clip / Notes"),
    ("ai_generate",  "AI Generate"),
    ("ai_variation", "AI Variation"),
    ("analysis",     "Analysis"),
    ("synth",        "Synth"),
    ("effects",      "Effects"),
    ("drum_seq",     "Step Seq"),
    ("score",        "Score"),
    # Cubase 15 확장 탭
    ("chord_pads",   "Chord Pads"),
    ("expr_map",     "Expr Map"),
]


# ---------------------------------------------------------------------------
# DetailView
# ---------------------------------------------------------------------------

class DetailView(QWidget):
    """Bottom detail panel — Ableton-style clip/device view."""

    tab_changed = pyqtSignal(str)
    collapsed = pyqtSignal(bool)
    generate_requested = pyqtSignal(dict)
    variation_requested = pyqtSignal(dict)
    humanize_requested = pyqtSignal(float, float)
    quantize_requested = pyqtSignal(float, int)
    analyze_requested = pyqtSignal()
    scale_snap_requested = pyqtSignal(str, str)
    # Forwarded from PianoRollWidget
    note_added = pyqtSignal(object)
    note_removed = pyqtSignal(object)
    note_modified = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_collapsed = False
        self._current_tab = "notes"
        self._expanded_height = 280

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(28)  # title bar only when collapsed
        self.setStyleSheet(f"background: {COLORS['bg_dark']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Title bar ---
        self._title_bar = QFrame()
        self._title_bar.setFixedHeight(28)
        self._title_bar.setStyleSheet(_TITLE_BAR_STYLE)
        tb_layout = QHBoxLayout(self._title_bar)
        tb_layout.setContentsMargins(4, 0, 4, 0)
        tb_layout.setSpacing(0)

        # Collapse toggle
        self._collapse_btn = QToolButton()
        self._collapse_btn.setText("\u25BC")  # ▼
        self._collapse_btn.setStyleSheet(_COLLAPSE_BTN_STYLE)
        self._collapse_btn.setFixedSize(22, 22)
        self._collapse_btn.clicked.connect(self.toggle_collapse)
        tb_layout.addWidget(self._collapse_btn)

        # Tab buttons
        self._tab_buttons: dict[str, QPushButton] = {}
        for key, label in _TABS:
            btn = QPushButton(label)
            btn.setStyleSheet(_TAB_BTN_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self.show_tab(k))
            self._tab_buttons[key] = btn
            tb_layout.addWidget(btn)

        tb_layout.addStretch()

        # Context label
        self._context_label = QLabel("No clip selected")
        self._context_label.setStyleSheet(_CONTEXT_LABEL_STYLE)
        tb_layout.addWidget(self._context_label)

        root.addWidget(self._title_bar)

        # --- Content area ---
        self._content = QFrame()
        self._content.setStyleSheet(f"background: {COLORS['bg_dark']};")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Create tab content widgets
        self._piano_roll = PianoRollWidget()
        self._ai_panel = AIPanel()
        self._review_panel = ReviewPanel()

        # AI sub-panels accessed via the AIPanel
        self._ai_generate_widget = self._ai_panel.get_generate_panel()
        self._ai_variation_widget = self._ai_panel.get_variation_panel()
        self._ai_tools_widget = self._ai_panel.get_tools_panel()

        # Build individual containers for each tab
        self._tab_widgets: dict[str, QWidget] = {}

        # Notes tab — piano roll
        self._tab_widgets["notes"] = self._piano_roll

        # AI Generate tab — generate panel + tools
        gen_container = QWidget()
        gen_lay = QVBoxLayout(gen_container)
        gen_lay.setContentsMargins(4, 4, 4, 4)
        gen_lay.setSpacing(4)
        gen_lay.addWidget(self._ai_generate_widget)
        gen_lay.addWidget(self._ai_tools_widget)
        gen_lay.addStretch()
        self._tab_widgets["ai_generate"] = gen_container

        # AI Variation tab — variation panel
        var_container = QWidget()
        var_lay = QVBoxLayout(var_container)
        var_lay.setContentsMargins(4, 4, 4, 4)
        var_lay.setSpacing(4)
        var_lay.addWidget(self._ai_variation_widget)
        var_lay.addStretch()
        self._tab_widgets["ai_variation"] = var_container

        # Analysis tab — review panel
        self._tab_widgets["analysis"] = self._review_panel

        # Synth tab — synthesizer controls
        self._synth_panel = SynthPanel()
        self._tab_widgets["synth"] = self._synth_panel

        # Effects tab — insert/send chain editor
        self._effects_panel = EffectsChainPanel()
        self._tab_widgets["effects"] = self._effects_panel

        # Step Sequencer tab — drum grid
        self._step_seq_panel = StepSequencerPanel()
        self._tab_widgets["drum_seq"] = self._step_seq_panel

        # Score tab — notation view
        self._score_panel = ScoreViewPanel()
        self._tab_widgets["score"] = self._score_panel

        # Cubase 15 확장: Chord Pads tab
        try:
            from ui.chord_pad_panel import ChordPadPanel
            self._chord_pad_panel = ChordPadPanel()
            self._tab_widgets["chord_pads"] = self._chord_pad_panel
        except ImportError:
            self._chord_pad_panel = QLabel("Chord Pads (loading...)")
            self._chord_pad_panel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tab_widgets["chord_pads"] = self._chord_pad_panel

        # Cubase 15 확장: Expression Map Editor tab
        try:
            from ui.expression_map_editor import ExpressionMapEditor
            self._expr_map_editor = ExpressionMapEditor()
            self._tab_widgets["expr_map"] = self._expr_map_editor
        except ImportError:
            self._expr_map_editor = QLabel("Expression Map Editor (loading...)")
            self._expr_map_editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tab_widgets["expr_map"] = self._expr_map_editor

        # Add all tab widgets to content layout
        for widget in self._tab_widgets.values():
            content_layout.addWidget(widget)

        root.addWidget(self._content, 1)

        # Wire AI signals through
        self._ai_panel.generate_requested.connect(self.generate_requested)
        self._ai_panel.variation_requested.connect(self.variation_requested)
        self._ai_panel.humanize_requested.connect(self.humanize_requested)
        self._ai_panel.quantize_requested.connect(self.quantize_requested)
        self._ai_panel.scale_snap_requested.connect(self.scale_snap_requested)
        self._ai_panel.analyze_requested.connect(self.analyze_requested)

        # Forward piano roll note signals
        if hasattr(self._piano_roll, 'note_added'):
            self._piano_roll.note_added.connect(self.note_added)
        if hasattr(self._piano_roll, 'note_removed'):
            self._piano_roll.note_removed.connect(self.note_removed)
        if hasattr(self._piano_roll, 'note_modified'):
            self._piano_roll.note_modified.connect(self.note_modified)

        # Initial state: hide all tabs except notes, mark notes active
        for key, widget in self._tab_widgets.items():
            widget.setVisible(key == "notes")
        for key, btn in self._tab_buttons.items():
            btn.setStyleSheet(_TAB_BTN_ACTIVE if key == "notes" else _TAB_BTN_STYLE)
        self._current_tab = "notes"

    # -----------------------------------------------------------------
    # Tab management
    # -----------------------------------------------------------------

    def show_tab(self, name: str):
        """Switch to the named tab."""
        if name not in self._tab_widgets:
            return
        self._current_tab = name
        # Show/hide widgets
        for key, widget in self._tab_widgets.items():
            widget.setVisible(key == name)
        # Update button styles
        for key, btn in self._tab_buttons.items():
            btn.setStyleSheet(_TAB_BTN_ACTIVE if key == name else _TAB_BTN_STYLE)
        # Expand if collapsed
        if self._is_collapsed:
            self.expand()
        self.tab_changed.emit(name)

    # -----------------------------------------------------------------
    # Collapse / expand
    # -----------------------------------------------------------------

    def collapse(self):
        """Collapse the detail view to just the title bar."""
        self._is_collapsed = True
        self._content.setVisible(False)
        self._collapse_btn.setText("\u25B6")  # ▶
        self.setMaximumHeight(28)
        self.setMinimumHeight(28)
        self.collapsed.emit(True)

    def expand(self):
        """Expand the detail view to show content."""
        self._is_collapsed = False
        self._content.setVisible(True)
        self._collapse_btn.setText("\u25BC")  # ▼
        self.setMaximumHeight(16777215)
        self.setMinimumHeight(120)
        self.collapsed.emit(False)

    def toggle_collapse(self):
        if self._is_collapsed:
            self.expand()
        else:
            self.collapse()

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def set_track(self, track, track_index: int = 0):
        """Update context when a track/clip is selected."""
        if track is None:
            self._context_label.setText("No Track")
            return
        name = getattr(track, "name", f"Track {track_index + 1}")
        self._context_label.setText(f"Clip: {name}")
        self._piano_roll.set_track(track)

    def set_project(self, project_state):
        """Pass project state to child widgets that need it."""
        if hasattr(self._piano_roll, "set_project"):
            self._piano_roll.set_project(project_state)

    def get_piano_roll(self) -> PianoRollWidget:
        return self._piano_roll

    def get_ai_panel(self) -> AIPanel:
        return self._ai_panel

    def update_playhead(self, tick: int):
        """Forward playhead position to the piano roll."""
        if hasattr(self._piano_roll, "set_playhead"):
            self._piano_roll.set_playhead(tick)
