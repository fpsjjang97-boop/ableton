"""
AI Control Panel — compact device-style panels for the Detail View.

Modeled after Ableton Live's audio effect device chain: horizontal layouts
with knob controls, dropdown selectors, and inline action buttons.
"""

import math

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSlider, QGroupBox, QFrame, QSpinBox, QCheckBox, QSizePolicy,
    QGridLayout, QLineEdit, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QPainter, QPaintEvent, QPen

from config import COLORS, AI_VARIATION_TYPES, AI_STYLES


# ---------------------------------------------------------------------------
# Shared helpers / styles
# ---------------------------------------------------------------------------

_DEVICE_HEADER = f"""
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {COLORS['bg_mid']}, stop:1 {COLORS['bg_dark']});
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 3px 8px;
"""

_DEVICE_BODY = f"""
    background: {COLORS['bg_dark']};
    border: 1px solid {COLORS['border']};
    border-top: none;
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 4px;
    padding: 6px;
"""

_COMPACT_COMBO = f"""
    QComboBox {{
        background-color: {COLORS['bg_input']};
        border: 1px solid {COLORS['border']};
        border-radius: 3px;
        padding: 2px 6px;
        color: {COLORS['text_primary']};
        font-size: 11px;
        min-height: 20px;
        max-height: 22px;
    }}
    QComboBox::drop-down {{ border: none; width: 16px; }}
    QComboBox QAbstractItemView {{
        background-color: {COLORS['bg_input']};
        color: {COLORS['text_primary']};
        selection-background-color: {COLORS['bg_selected']};
    }}
"""

_COMPACT_CHECK = f"""
    QCheckBox {{
        spacing: 4px;
        color: {COLORS['text_secondary']};
        font-size: 10px;
    }}
    QCheckBox::indicator {{
        width: 12px; height: 12px;
        border: 1px solid {COLORS['border']};
        border-radius: 2px;
        background: {COLORS['bg_input']};
    }}
    QCheckBox::indicator:checked {{
        background: {COLORS['accent_secondary']};
        border-color: {COLORS['accent_secondary']};
    }}
"""

_BTN_ACCENT = f"""
    QPushButton {{
        background-color: {COLORS['accent']};
        color: {COLORS['bg_darkest']};
        border: none; border-radius: 3px;
        padding: 4px 12px; font-weight: bold;
        font-size: 11px; min-height: 22px;
    }}
    QPushButton:hover {{ background-color: {COLORS['accent_light']}; }}
    QPushButton:pressed {{ background-color: {COLORS['accent']}; }}
"""

_BTN_SMALL = f"""
    QPushButton {{
        background-color: {COLORS['bg_mid']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 3px;
        padding: 3px 10px;
        font-size: 11px; min-height: 20px;
    }}
    QPushButton:hover {{ background-color: {COLORS['bg_hover']}; }}
"""


def _tiny_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 9px;")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


# ---------------------------------------------------------------------------
# KnobWidget
# ---------------------------------------------------------------------------

class KnobWidget(QWidget):
    """Small circular knob display with click+drag editing."""

    valueChanged = pyqtSignal(int)

    def __init__(self, label: str = "", minimum: int = 0, maximum: int = 100,
                 default: int = 50, parent=None):
        super().__init__(parent)
        self._label = label
        self._min = minimum
        self._max = maximum
        self._value = default
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_val = 0
        self.setFixedSize(48, 64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{label}: {default}")

    # -- Properties --

    def value(self) -> int:
        return self._value

    def setValue(self, v: int):
        v = max(self._min, min(self._max, v))
        if v != self._value:
            self._value = v
            self.setToolTip(f"{self._label}: {v}")
            self.valueChanged.emit(v)
            self.update()

    # -- Paint --

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = 24, 22
        radius = 16

        # Shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 80))
        p.drawEllipse(cx - radius + 1, cy - radius + 1, radius * 2, radius * 2)

        # Outer ring — dark metallic
        grad_outer = QColor(50, 50, 50)
        p.setBrush(grad_outer)
        p.setPen(QPen(QColor(30, 30, 30), 1))
        p.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

        # Inner face
        inner_r = radius - 3
        p.setBrush(QColor(35, 35, 35))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)

        # Value arc — silver
        frac = (self._value - self._min) / max(1, self._max - self._min)
        start_angle = 225  # degrees, bottom-left
        sweep = -frac * 270  # clockwise 270 degrees max

        arc_pen = QPen(QColor(COLORS['accent']), 2.5)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc_pen)
        arc_rect = cx - radius + 2, cy - radius + 2, (radius - 2) * 2, (radius - 2) * 2
        p.drawArc(int(arc_rect[0]), int(arc_rect[1]),
                   int(arc_rect[2]), int(arc_rect[3]),
                   int(start_angle * 16), int(sweep * 16))

        # Indicator dot
        angle_rad = math.radians(start_angle + sweep)
        dot_r = radius - 6
        dot_x = cx + dot_r * math.cos(angle_rad)
        dot_y = cy - dot_r * math.sin(angle_rad)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 230))
        p.drawEllipse(int(dot_x) - 2, int(dot_y) - 2, 4, 4)

        # Value text
        p.setPen(QColor(COLORS['text_primary']))
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(0, 40, 48, 12, Qt.AlignmentFlag.AlignCenter, str(self._value))

        # Label text
        p.setPen(QColor(COLORS['text_dim']))
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(0, 52, 48, 12, Qt.AlignmentFlag.AlignCenter, self._label)

        p.end()

    # -- Mouse interaction --

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_y = e.globalPosition().y()
            self._drag_start_val = self._value

    def mouseMoveEvent(self, e):
        if self._dragging:
            dy = self._drag_start_y - e.globalPosition().y()
            span = self._max - self._min
            delta = int(dy * span / 150)
            self.setValue(self._drag_start_val + delta)

    def mouseReleaseEvent(self, e):
        self._dragging = False

    def wheelEvent(self, e):
        step = 1 if e.angleDelta().y() > 0 else -1
        self.setValue(self._value + step)


# ---------------------------------------------------------------------------
# AIGeneratePanel — horizontal device layout
# ---------------------------------------------------------------------------

class AIGeneratePanel(QWidget):
    """Ableton-style device panel for AI generation."""

    generate_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setStyleSheet(_DEVICE_HEADER)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(6, 2, 6, 2)
        title = QLabel("AI Generator")
        title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        hlay.addWidget(title)
        hlay.addStretch()
        root.addWidget(header)

        # Body — horizontal controls
        body = QFrame()
        body.setStyleSheet(_DEVICE_BODY)
        blay = QHBoxLayout(body)
        blay.setContentsMargins(8, 6, 8, 6)
        blay.setSpacing(12)

        # Row 1: Style + Genre + Mood + Type dropdowns
        # Style dropdown (dynamic from PatternDB)
        style_col = QVBoxLayout()
        style_col.setSpacing(2)
        style_col.addWidget(_tiny_label("STYLE"))
        self._style = QComboBox()
        self._style.setStyleSheet(_COMPACT_COMBO)
        self._style.addItems([s.title() for s in AI_STYLES])
        style_col.addWidget(self._style)
        blay.addLayout(style_col)

        # Genre dropdown (dynamic)
        genre_col = QVBoxLayout()
        genre_col.setSpacing(2)
        genre_col.addWidget(_tiny_label("GENRE"))
        self._genre = QComboBox()
        self._genre.setStyleSheet(_COMPACT_COMBO)
        self._genre.addItems(["Any", "Classical", "Jazz", "Pop", "Electronic"])
        genre_col.addWidget(self._genre)
        blay.addLayout(genre_col)

        # Mood dropdown (dynamic)
        mood_col = QVBoxLayout()
        mood_col.setSpacing(2)
        mood_col.addWidget(_tiny_label("MOOD"))
        self._mood = QComboBox()
        self._mood.setStyleSheet(_COMPACT_COMBO)
        self._mood.addItems(["Any", "Bright", "Calm", "Dark", "Energetic", "Sad", "Warm"])
        mood_col.addWidget(self._mood)
        blay.addLayout(mood_col)

        # Type dropdown
        type_col = QVBoxLayout()
        type_col.setSpacing(2)
        type_col.addWidget(_tiny_label("TYPE"))
        self._track_type = QComboBox()
        self._track_type.setStyleSheet(_COMPACT_COMBO)
        self._track_type.addItems(["Melody", "Chords", "Bass", "Drums"])
        type_col.addWidget(self._track_type)
        blay.addLayout(type_col)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        blay.addWidget(sep)

        # Length knob
        self._length_knob = KnobWidget("Bars", 1, 64, 8)
        blay.addWidget(self._length_knob)

        # Density knob
        self._density_knob = KnobWidget("Density", 0, 100, 50)
        blay.addWidget(self._density_knob)

        # Octave knob (low)
        self._oct_low = KnobWidget("Oct Lo", 0, 8, 3)
        blay.addWidget(self._oct_low)

        # Octave knob (high)
        self._oct_high = KnobWidget("Oct Hi", 1, 9, 6)
        blay.addWidget(self._oct_high)

        blay.addStretch()

        # Generate button
        btn = QPushButton("Generate")
        btn.setStyleSheet(_BTN_ACCENT)
        btn.setFixedWidth(80)
        btn.clicked.connect(self._on_generate)
        blay.addWidget(btn)

        root.addWidget(body)

        # Row 2: Natural language prompt bar
        prompt_frame = QFrame()
        prompt_frame.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg_dark']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 4px; }}"
        )
        prompt_lay = QHBoxLayout(prompt_frame)
        prompt_lay.setContentsMargins(8, 4, 8, 4)
        prompt_lay.setSpacing(6)

        prompt_lbl = QLabel("Prompt:")
        prompt_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        prompt_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; border: none;")
        prompt_lay.addWidget(prompt_lbl)

        self._prompt = QLineEdit()
        self._prompt.setPlaceholderText("e.g. '슬픈 발라드 다단조' or 'gentle jazz piano in Cm'")
        self._prompt.setStyleSheet(
            f"QLineEdit {{ background: {COLORS['bg_input']}; border: 1px solid {COLORS['border']}; "
            f"border-radius: 3px; padding: 3px 6px; color: {COLORS['text_primary']}; "
            f"font-size: 11px; min-height: 20px; }}"
        )
        self._prompt.returnPressed.connect(self._on_generate)
        prompt_lay.addWidget(self._prompt, 1)

        root.addWidget(prompt_frame)

        # Load dynamic dropdown content from PatternDB
        self._refresh_from_db()

    def _refresh_from_db(self):
        """Populate dropdowns from PatternDB if available."""
        try:
            from core.pattern_db import PatternDB
            db = PatternDB.get()
            # Update style dropdown
            styles = db.available_styles()
            if styles:
                self._style.clear()
                self._style.addItems([s.replace("_", " ").title() for s in styles])
            # Update genre dropdown
            genres = db.available_genres()
            if genres:
                self._genre.clear()
                self._genre.addItems(["Any"] + [g.title() for g in genres])
            # Update mood dropdown
            moods = db.available_moods()
            if moods:
                self._mood.clear()
                self._mood.addItems(["Any"] + [m.title() for m in moods])
        except Exception:
            pass  # PatternDB not available, keep defaults

    def refresh_dropdowns(self):
        """Public method to refresh dropdowns after DB update."""
        self._refresh_from_db()

    def _on_generate(self):
        style_text = self._style.currentText().lower().replace(" ", "_")
        # Map back to AI_STYLES if possible
        style = style_text if style_text else "pop"

        genre = self._genre.currentText().lower()
        if genre == "any":
            genre = ""

        mood = self._mood.currentText().lower()
        if mood == "any":
            mood = ""

        params = {
            "style": style,
            "genre": genre,
            "mood": mood,
            "prompt": self._prompt.text().strip(),
            "track_type": self._track_type.currentText().lower(),
            "length_bars": self._length_knob.value(),
            "density": self._density_knob.value() / 100.0,
            "octave_low": self._oct_low.value(),
            "octave_high": self._oct_high.value(),
            "add_track": False,
        }
        self.generate_requested.emit(params)


# ---------------------------------------------------------------------------
# AIVariationPanel — horizontal device layout
# ---------------------------------------------------------------------------

class AIVariationPanel(QWidget):
    """Ableton-style device panel for variations."""

    variation_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet(_DEVICE_HEADER)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(6, 2, 6, 2)
        title = QLabel("AI Variation")
        title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        hlay.addWidget(title)
        hlay.addStretch()
        root.addWidget(header)

        # Body
        body = QFrame()
        body.setStyleSheet(_DEVICE_BODY)
        blay = QHBoxLayout(body)
        blay.setContentsMargins(8, 6, 8, 6)
        blay.setSpacing(12)

        # Type dropdown
        type_col = QVBoxLayout()
        type_col.setSpacing(2)
        type_col.addWidget(_tiny_label("TYPE"))
        self._var_type = QComboBox()
        self._var_type.setStyleSheet(_COMPACT_COMBO)
        self._var_type.addItems(AI_VARIATION_TYPES)
        type_col.addWidget(self._var_type)
        blay.addLayout(type_col)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        blay.addWidget(sep)

        # Intensity knob
        self._intensity_knob = KnobWidget("Intensity", 0, 100, 30)
        blay.addWidget(self._intensity_knob)

        # Checkboxes
        chk_col = QVBoxLayout()
        chk_col.setSpacing(4)
        self._keep_original = QCheckBox("Keep Original")
        self._keep_original.setStyleSheet(_COMPACT_CHECK)
        self._keep_original.setChecked(True)
        chk_col.addWidget(self._keep_original)
        self._sel_only = QCheckBox("Selection Only")
        self._sel_only.setStyleSheet(_COMPACT_CHECK)
        chk_col.addWidget(self._sel_only)
        blay.addLayout(chk_col)

        blay.addStretch()

        # Apply button
        btn = QPushButton("Apply")
        btn.setStyleSheet(_BTN_ACCENT)
        btn.setFixedWidth(70)
        btn.clicked.connect(self._on_apply)
        blay.addWidget(btn)

        root.addWidget(body)

    def _on_apply(self):
        params = {
            "type": self._var_type.currentText(),
            "intensity": self._intensity_knob.value() / 100.0,
            "keep_original": self._keep_original.isChecked(),
            "selection_only": self._sel_only.isChecked(),
            "preview": False,
        }
        self.variation_requested.emit(params)


# ---------------------------------------------------------------------------
# AIToolsPanel — Humanize / Quantize / Scale Snap in horizontal layout
# ---------------------------------------------------------------------------

class AIToolsPanel(QWidget):
    """Compact horizontal tools panel: Humanize, Quantize, Scale Snap."""

    humanize_requested = pyqtSignal(float, float)
    quantize_requested = pyqtSignal(float, int)
    scale_snap_requested = pyqtSignal(str, str)
    analyze_requested = pyqtSignal()
    ingest_requested = pyqtSignal(str)  # path to MIDI file or directory

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # --- Humanize section ---
        hum_frame = QFrame()
        hum_frame.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg_dark']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 4px; }}"
        )
        hum_lay = QHBoxLayout(hum_frame)
        hum_lay.setContentsMargins(8, 4, 8, 4)
        hum_lay.setSpacing(8)

        hum_title = QLabel("Humanize")
        hum_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        hum_title.setStyleSheet(f"color: {COLORS['text_secondary']}; border: none;")
        hum_lay.addWidget(hum_title)

        self._hum_timing = KnobWidget("Timing", 0, 100, 20)
        hum_lay.addWidget(self._hum_timing)
        self._hum_velocity = KnobWidget("Velocity", 0, 100, 15)
        hum_lay.addWidget(self._hum_velocity)

        btn_hum = QPushButton("Apply")
        btn_hum.setStyleSheet(_BTN_SMALL)
        btn_hum.setFixedWidth(50)
        btn_hum.clicked.connect(self._on_humanize)
        hum_lay.addWidget(btn_hum)

        root.addWidget(hum_frame)

        # --- Quantize section ---
        q_frame = QFrame()
        q_frame.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg_dark']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 4px; }}"
        )
        q_lay = QHBoxLayout(q_frame)
        q_lay.setContentsMargins(8, 4, 8, 4)
        q_lay.setSpacing(8)

        q_title = QLabel("Quantize")
        q_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        q_title.setStyleSheet(f"color: {COLORS['text_secondary']}; border: none;")
        q_lay.addWidget(q_title)

        grid_col = QVBoxLayout()
        grid_col.setSpacing(1)
        grid_col.addWidget(_tiny_label("GRID"))
        self._q_grid = QComboBox()
        self._q_grid.setStyleSheet(_COMPACT_COMBO)
        self._q_grid.addItems(["1/4", "1/8", "1/16", "1/32"])
        self._q_grid.setCurrentIndex(1)
        grid_col.addWidget(self._q_grid)
        q_lay.addLayout(grid_col)

        self._q_strength = KnobWidget("Strength", 0, 100, 75)
        q_lay.addWidget(self._q_strength)

        btn_q = QPushButton("Apply")
        btn_q.setStyleSheet(_BTN_SMALL)
        btn_q.setFixedWidth(50)
        btn_q.clicked.connect(self._on_quantize)
        q_lay.addWidget(btn_q)

        root.addWidget(q_frame)

        # --- Scale Snap section ---
        s_frame = QFrame()
        s_frame.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg_dark']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 4px; }}"
        )
        s_lay = QHBoxLayout(s_frame)
        s_lay.setContentsMargins(8, 4, 8, 4)
        s_lay.setSpacing(8)

        s_title = QLabel("Scale Snap")
        s_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        s_title.setStyleSheet(f"color: {COLORS['text_secondary']}; border: none;")
        s_lay.addWidget(s_title)

        key_col = QVBoxLayout()
        key_col.setSpacing(1)
        key_col.addWidget(_tiny_label("KEY"))
        self._snap_key = QComboBox()
        self._snap_key.setStyleSheet(_COMPACT_COMBO)
        self._snap_key.addItems(
            ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        )
        key_col.addWidget(self._snap_key)
        s_lay.addLayout(key_col)

        scale_col = QVBoxLayout()
        scale_col.setSpacing(1)
        scale_col.addWidget(_tiny_label("SCALE"))
        self._snap_scale = QComboBox()
        self._snap_scale.setStyleSheet(_COMPACT_COMBO)
        self._snap_scale.addItems(
            ["Major", "Minor", "Dorian", "Mixolydian", "Pentatonic",
             "Blues", "Harmonic Minor", "Melodic Minor", "Chromatic"]
        )
        scale_col.addWidget(self._snap_scale)
        s_lay.addLayout(scale_col)

        btn_s = QPushButton("Snap")
        btn_s.setStyleSheet(_BTN_SMALL)
        btn_s.setFixedWidth(50)
        btn_s.clicked.connect(self._on_scale_snap)
        s_lay.addWidget(btn_s)

        root.addWidget(s_frame)

        # --- Analyze section ---
        a_frame = QFrame()
        a_frame.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg_dark']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 4px; }}"
        )
        a_lay = QHBoxLayout(a_frame)
        a_lay.setContentsMargins(8, 4, 8, 4)
        a_lay.setSpacing(8)

        a_title = QLabel("Analysis")
        a_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        a_title.setStyleSheet(f"color: {COLORS['text_secondary']}; border: none;")
        a_lay.addWidget(a_title)

        a_lay.addStretch()

        btn_a = QPushButton("Analyze Track")
        btn_a.setStyleSheet(_BTN_SMALL)
        btn_a.setFixedWidth(90)
        btn_a.clicked.connect(self._on_analyze)
        a_lay.addWidget(btn_a)

        root.addWidget(a_frame)

        # --- Ingest section ---
        i_frame = QFrame()
        i_frame.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg_dark']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 4px; }}"
        )
        i_lay = QHBoxLayout(i_frame)
        i_lay.setContentsMargins(8, 4, 8, 4)
        i_lay.setSpacing(8)

        i_title = QLabel("Ingest")
        i_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        i_title.setStyleSheet(f"color: {COLORS['text_secondary']}; border: none;")
        i_lay.addWidget(i_title)

        self._ingest_status = QLabel("Ready")
        self._ingest_status.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; border: none;"
        )
        i_lay.addWidget(self._ingest_status)
        i_lay.addStretch()

        btn_ingest = QPushButton("Add MIDI to DB")
        btn_ingest.setStyleSheet(_BTN_SMALL)
        btn_ingest.setFixedWidth(100)
        btn_ingest.clicked.connect(self._on_ingest)
        i_lay.addWidget(btn_ingest)

        root.addWidget(i_frame)

    def _on_analyze(self):
        self.analyze_requested.emit()

    def _on_humanize(self):
        self.humanize_requested.emit(
            self._hum_timing.value() / 100.0,
            self._hum_velocity.value() / 100.0,
        )

    def _on_quantize(self):
        grid_map = {"1/4": 4, "1/8": 8, "1/16": 16, "1/32": 32}
        grid = grid_map.get(self._q_grid.currentText(), 8)
        self.quantize_requested.emit(
            self._q_strength.value() / 100.0,
            grid,
        )

    def _on_scale_snap(self):
        self.scale_snap_requested.emit(
            self._snap_key.currentText(),
            self._snap_scale.currentText(),
        )

    def _on_ingest(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select MIDI files to ingest", "",
            "MIDI Files (*.mid *.midi);;All (*)"
        )
        if paths:
            for path in paths:
                self._ingest_status.setText(f"Ingesting {len(paths)} file(s)...")
                self.ingest_requested.emit(path)
            self._ingest_status.setText(f"Done — {len(paths)} file(s)")


# ---------------------------------------------------------------------------
# AIPanel — main container wrapping sub-panels
# ---------------------------------------------------------------------------

class AIPanel(QWidget):
    """Compact AI panel designed to fit inside the Detail View (250px height).

    Wraps AIGeneratePanel, AIVariationPanel, and AIToolsPanel in a stacked
    layout switchable via the parent DetailView tabs.
    """

    generate_requested = pyqtSignal(dict)
    variation_requested = pyqtSignal(dict)
    humanize_requested = pyqtSignal(float, float)
    quantize_requested = pyqtSignal(float, int)
    analyze_requested = pyqtSignal()
    scale_snap_requested = pyqtSignal(str, str)
    ingest_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background: {COLORS['bg_dark']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        # Sub-panels
        self._generate_panel = AIGeneratePanel()
        self._variation_panel = AIVariationPanel()
        self._tools_panel = AIToolsPanel()

        root.addWidget(self._generate_panel)
        root.addWidget(self._variation_panel)
        root.addWidget(self._tools_panel)
        root.addStretch()

        # Wire signals through
        self._generate_panel.generate_requested.connect(self.generate_requested)
        self._variation_panel.variation_requested.connect(self.variation_requested)
        self._tools_panel.humanize_requested.connect(self.humanize_requested)
        self._tools_panel.quantize_requested.connect(self.quantize_requested)
        self._tools_panel.scale_snap_requested.connect(self.scale_snap_requested)
        self._tools_panel.analyze_requested.connect(self.analyze_requested)
        self._tools_panel.ingest_requested.connect(self.ingest_requested)

    # -- Public accessors --

    def get_generate_panel(self) -> AIGeneratePanel:
        return self._generate_panel

    def get_variation_panel(self) -> AIVariationPanel:
        return self._variation_panel

    def get_tools_panel(self) -> AIToolsPanel:
        return self._tools_panel

    def set_analysis_text(self, text: str):
        """Backward-compatible stub — analysis now lives in ReviewPanel."""
        pass
