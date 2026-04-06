"""
Step Sequencer UI — 16-step drum grid with per-row controls.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QMouseEvent, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QGridLayout, QSizePolicy, QScrollArea,
)
from config import COLORS
C = COLORS


class StepButton(QWidget):
    """Single step in the sequencer grid."""
    toggled = pyqtSignal(int, int, int)  # row, col, velocity (0=off)

    def __init__(self, row: int, col: int, parent=None):
        super().__init__(parent)
        self.row = row
        self.col = col
        self.velocity = 0
        self.setFixedSize(28, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        # Background - beat grouping
        is_downbeat = self.col % 4 == 0
        bg = C['bg_mid'] if is_downbeat else C['bg_darkest']
        p.fillRect(0, 0, w, h, QColor(bg))

        if self.velocity > 0:
            brightness = 80 + int(self.velocity / 127 * 175)
            color = QColor(brightness, brightness, brightness)
            p.fillRect(2, 2, w - 4, h - 4, color)
        else:
            p.fillRect(2, 2, w - 4, h - 4, QColor(C['bg_input']))

        p.setPen(QColor(C['border']))
        p.drawRect(0, 0, w - 1, h - 1)
        p.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.velocity > 0:
                self.velocity = 0
            else:
                self.velocity = 100
            self.toggled.emit(self.row, self.col, self.velocity)
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            # Cycle velocity: 0 → 60 → 100 → 127 → 0
            levels = [0, 60, 100, 127]
            try:
                idx = levels.index(self.velocity)
            except ValueError:
                idx = 0
            self.velocity = levels[(idx + 1) % len(levels)]
            self.toggled.emit(self.row, self.col, self.velocity)
            self.update()


class StepSequencerPanel(QWidget):
    """16-step drum sequencer with row controls."""
    pattern_changed = pyqtSignal()
    pad_triggered = pyqtSignal(int, int)  # note, velocity
    step_toggled = pyqtSignal(int, int)   # row, col — 스텝 토글 시 발생

    _DEFAULT_ROWS = [
        ("Kick", 36), ("Snare", 38), ("Cl HH", 42), ("Op HH", 46),
        ("Clap", 39), ("Rim", 37), ("Lo Tom", 41), ("Hi Tom", 45),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps = 16
        self._rows: list[dict] = []
        self._buttons: list[list[StepButton]] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("STEP SEQUENCER")
        title.setStyleSheet(f"color: {C['text_secondary']}; font-size: 11px; font-weight: bold;")
        hdr.addWidget(title)
        hdr.addStretch()

        # Swing
        hdr.addWidget(QLabel("Swing"))
        self._swing_slider = QSlider(Qt.Orientation.Horizontal)
        self._swing_slider.setRange(0, 100)
        self._swing_slider.setValue(0)
        self._swing_slider.setFixedWidth(80)
        self._swing_slider.setFixedHeight(14)
        hdr.addWidget(self._swing_slider)
        self._swing_val = QLabel("0%")
        self._swing_val.setFixedWidth(30)
        self._swing_slider.valueChanged.connect(lambda v: self._swing_val.setText(f"{v}%"))
        hdr.addWidget(self._swing_val)

        # Groove preset
        hdr.addWidget(QLabel("Groove"))
        self._groove_combo = QComboBox()
        self._groove_combo.setFixedWidth(100)
        from core.groove_engine import GROOVE_PRESETS
        self._groove_combo.addItems(list(GROOVE_PRESETS.keys()))
        hdr.addWidget(self._groove_combo)

        root.addLayout(hdr)

        # Beat numbers
        beat_row = QHBoxLayout()
        beat_row.addSpacing(90)  # space for row labels
        for i in range(self._steps):
            lbl = QLabel(str(i + 1))
            lbl.setFixedWidth(28)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 8px;")
            beat_row.addWidget(lbl)
        beat_row.addStretch()
        root.addLayout(beat_row)

        # Grid
        self._grid_widget = QWidget()
        grid_layout = QVBoxLayout(self._grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(1)

        for r, (name, note) in enumerate(self._DEFAULT_ROWS):
            row_data = {"name": name, "note": note, "muted": False}
            self._rows.append(row_data)

            row_layout = QHBoxLayout()
            row_layout.setSpacing(1)

            # Row label + preview button
            preview_btn = QPushButton(name)
            preview_btn.setFixedSize(70, 24)
            preview_btn.setStyleSheet(f"""
                QPushButton {{ background: {C['bg_mid']}; color: {C['text_primary']};
                              border: 1px solid {C['border']}; border-radius: 2px; font-size: 9px; }}
                QPushButton:pressed {{ background: {C['accent']}; color: #000; }}
            """)
            preview_btn.clicked.connect(lambda _, n=note: self.pad_triggered.emit(n, 100))
            row_layout.addWidget(preview_btn)

            # Mute button
            mute_btn = QPushButton("M")
            mute_btn.setFixedSize(18, 24)
            mute_btn.setCheckable(True)
            mute_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {C['text_dim']};
                              border: none; font-size: 9px; }}
                QPushButton:checked {{ color: #D48A8A; }}
            """)
            row_layout.addWidget(mute_btn)

            # Step buttons
            btn_row = []
            for c in range(self._steps):
                btn = StepButton(r, c)
                btn.toggled.connect(self._on_step_toggled)
                row_layout.addWidget(btn)
                btn_row.append(btn)
            self._buttons.append(btn_row)

            row_layout.addStretch()
            grid_layout.addLayout(row_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {C['bg_darkest']}; }}")
        scroll.setWidget(self._grid_widget)
        root.addWidget(scroll, 1)

        # Transport
        trans = QHBoxLayout()
        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.clicked.connect(self._clear_all)
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{ background: {C['bg_input']}; color: {C['text_secondary']};
                          border: 1px solid {C['border']}; border-radius: 3px; font-size: 10px; }}
        """)
        trans.addWidget(self._clear_btn)
        trans.addStretch()

        self._randomize_btn = QPushButton("Randomize")
        self._randomize_btn.setFixedHeight(24)
        self._randomize_btn.clicked.connect(self._randomize)
        self._randomize_btn.setStyleSheet(self._clear_btn.styleSheet())
        trans.addWidget(self._randomize_btn)
        root.addLayout(trans)

    def _on_step_toggled(self, row, col, velocity):
        self.step_toggled.emit(row, col)
        self.pattern_changed.emit()

    def _clear_all(self):
        for row in self._buttons:
            for btn in row:
                btn.velocity = 0
                btn.update()
        self.pattern_changed.emit()

    def _randomize(self):
        import numpy as np
        rng = np.random.default_rng()
        for r, row in enumerate(self._buttons):
            # Different density per instrument
            density = 0.2 if r < 2 else 0.3 if r < 4 else 0.15
            for btn in row:
                btn.velocity = int(rng.choice([0, 80, 100, 127],
                                              p=[1 - density, density * 0.3, density * 0.4, density * 0.3]))
                btn.update()
        self.pattern_changed.emit()

    def get_pattern(self) -> list[list[int]]:
        """Get current pattern as velocity grid."""
        return [[btn.velocity for btn in row] for row in self._buttons]

    def set_pattern(self, pattern: list[list[int]]):
        for r, row in enumerate(pattern):
            if r < len(self._buttons):
                for c, vel in enumerate(row):
                    if c < len(self._buttons[r]):
                        self._buttons[r][c].velocity = vel
                        self._buttons[r][c].update()

    def load_default_pattern(self):
        """Load a basic rock/pop beat."""
        patterns = [
            [127, 0, 0, 0, 127, 0, 0, 0, 127, 0, 0, 0, 127, 0, 0, 0],  # Kick
            [0, 0, 0, 0, 127, 0, 0, 0, 0, 0, 0, 0, 127, 0, 0, 0],      # Snare
            [100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0, 100, 0],  # HH
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 80, 0],         # Open HH
            [0] * 16, [0] * 16, [0] * 16, [0] * 16,
        ]
        self.set_pattern(patterns)
