"""
Synth Control Panel — PyQt6 UI for the synthesizer engine.

Provides:
  - Synth type selector (Subtractive / FM / Wavetable / Granular / Sampler)
  - Preset browser
  - Oscillator controls (waveform, detune, mix)
  - Filter controls (type, cutoff, resonance)
  - ADSR visual editor (amp & filter envelopes)
  - LFO controls
  - Drum machine 4x4 pad grid
  - Modulation matrix
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QLinearGradient
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QSlider, QGroupBox, QGridLayout, QStackedWidget,
    QScrollArea, QSizePolicy, QSpinBox, QDoubleSpinBox,
)

from config import COLORS

# Re-use color palette
C = COLORS


def _knob_style():
    return f"""
        QSlider::groove:horizontal {{
            background: {C['bg_input']};
            height: 4px;
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {C['text_primary']};
            width: 12px; height: 12px;
            margin: -5px 0;
            border-radius: 6px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {C['accent']};
        }}
    """


def _make_knob(label: str, min_val: int, max_val: int, default: int,
               parent: QWidget = None) -> tuple[QLabel, QSlider, QLabel]:
    """Create a labeled horizontal slider (knob substitute)."""
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {C['text_secondary']}; font-size: 10px;")
    lbl.setFixedWidth(55)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(min_val, max_val)
    slider.setValue(default)
    slider.setStyleSheet(_knob_style())
    slider.setFixedHeight(18)
    val_lbl = QLabel(str(default))
    val_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px;")
    val_lbl.setFixedWidth(35)
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
    slider.valueChanged.connect(lambda v: val_lbl.setText(str(v)))
    return lbl, slider, val_lbl


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"""
        color: {C['text_secondary']};
        font-size: 11px; font-weight: bold;
        padding: 2px 0; border-bottom: 1px solid {C['border']};
    """)
    return lbl


# ── ADSR Visual Editor ────────────────────────────────────────────────────

class ADSRWidget(QWidget):
    """Visual ADSR envelope editor with draggable control points."""

    params_changed = pyqtSignal(float, float, float, float)  # A, D, S, R

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 80)
        self.setMaximumHeight(100)
        self._attack = 0.01
        self._decay = 0.2
        self._sustain = 0.7
        self._release = 0.4
        self._dragging = -1  # index of point being dragged

    def set_adsr(self, a: float, d: float, s: float, r: float):
        self._attack = a
        self._decay = d
        self._sustain = s
        self._release = r
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width() - 4, self.height() - 4
        x0, y0 = 2, 2

        # Background
        p.fillRect(self.rect(), QColor(C['bg_input']))
        p.setPen(QPen(QColor(C['border']), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

        # Normalize times for display
        total_time = self._attack + self._decay + 0.3 + self._release
        if total_time <= 0:
            total_time = 1.0
        scale = w / total_time

        # Control points
        p0 = QPointF(x0, y0 + h)  # Start
        p1 = QPointF(x0 + self._attack * scale, y0)  # Peak (end of attack)
        p2 = QPointF(p1.x() + self._decay * scale, y0 + h * (1 - self._sustain))  # Sustain level
        p3 = QPointF(p2.x() + 0.3 * scale, y0 + h * (1 - self._sustain))  # Sustain hold
        p4 = QPointF(p3.x() + self._release * scale, y0 + h)  # End of release

        # Draw envelope path
        path = QPainterPath()
        path.moveTo(p0)
        path.lineTo(p1)
        path.lineTo(p2)
        path.lineTo(p3)
        path.lineTo(p4)

        # Fill
        fill_path = QPainterPath(path)
        fill_path.lineTo(p4.x(), y0 + h)
        fill_path.lineTo(x0, y0 + h)
        fill_path.closeSubpath()
        gradient = QLinearGradient(0, y0, 0, y0 + h)
        gradient.setColorAt(0, QColor(C['accent'] + "40"))
        gradient.setColorAt(1, QColor(C['accent'] + "08"))
        p.fillPath(fill_path, QBrush(gradient))

        # Stroke
        p.setPen(QPen(QColor(C['accent']), 1.5))
        p.drawPath(path)

        # Control points
        for pt in [p1, p2, p3]:
            p.setPen(QPen(QColor(C['text_primary']), 1))
            p.setBrush(QBrush(QColor(C['accent'])))
            p.drawEllipse(pt, 4, 4)

        # Labels
        p.setPen(QColor(C['text_dim']))
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(int(p1.x()) - 5, int(y0 + h - 2), "A")
        p.drawText(int(p2.x()) - 5, int(y0 + h - 2), "D")
        p.drawText(int(p3.x()) - 5, int(y0 + h - 2), "S")
        p.drawText(int(p4.x()) - 5, int(y0 + h - 2), "R")

        p.end()


# ── Drum Pad Widget ────────────────────────────────────────────────────────

class DrumPadButton(QPushButton):
    """Single drum pad button."""

    pad_triggered = pyqtSignal(int, int)  # note, velocity

    def __init__(self, name: str, note: int, color: str = "#2A2A2A", parent=None):
        super().__init__(name, parent)
        self.note = note
        self._base_color = color
        self.setFixedSize(65, 50)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {C['text_primary']};
                border: 1px solid {C['border']};
                border-radius: 4px;
                font-size: 9px;
                font-weight: bold;
            }}
            QPushButton:pressed {{
                background-color: {C['accent']};
                color: #000;
            }}
            QPushButton:hover {{
                border-color: {C['text_secondary']};
            }}
        """)
        self.pressed.connect(lambda: self.pad_triggered.emit(self.note, 100))


# ── Drum Machine Panel ────────────────────────────────────────────────────

class DrumMachinePanel(QWidget):
    """4x4 drum pad grid."""

    pad_hit = pyqtSignal(int, int)  # note, velocity

    _PAD_COLORS = [
        "#3A2020", "#3A2020", "#202030", "#202030",
        "#2A2A20", "#2A2020", "#203020", "#203020",
        "#203020", "#202040", "#202040", "#2A2A20",
        "#2A2A20", "#2A2A20", "#2A2A20", "#2A2A20",
    ]

    _PAD_NAMES = [
        "KICK", "SNARE", "CL HH", "OP HH",
        "CLAP", "RIM", "LO TOM", "MI TOM",
        "HI TOM", "CRASH", "RIDE", "PERC 1",
        "PERC 2", "PERC 3", "PERC 4", "PERC 5",
    ]

    _PAD_NOTES = [36, 38, 42, 46, 39, 37, 41, 43, 45, 49, 51, 47, 48, 50, 52, 53]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(_section_label("Drum Machine"))

        grid = QGridLayout()
        grid.setSpacing(3)
        self._pads: list[DrumPadButton] = []
        for i in range(16):
            row, col = i // 4, i % 4
            pad = DrumPadButton(self._PAD_NAMES[i], self._PAD_NOTES[i], self._PAD_COLORS[i])
            pad.pad_triggered.connect(self.pad_hit.emit)
            grid.addWidget(pad, row, col)
            self._pads.append(pad)
        layout.addLayout(grid)


# ── Oscillator Section ────────────────────────────────────────────────────

class OscillatorSection(QWidget):
    """Controls for one oscillator."""

    changed = pyqtSignal()

    def __init__(self, osc_num: int = 1, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        layout.addWidget(_section_label(f"OSC {osc_num}"))

        # Waveform
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Wave"))
        self.wave_combo = QComboBox()
        self.wave_combo.addItems(["saw", "square", "sine", "triangle"])
        self.wave_combo.setFixedWidth(80)
        row1.addWidget(self.wave_combo)
        row1.addStretch()
        layout.addLayout(row1)

        # Detune
        lbl, self.detune_slider, val = _make_knob("Detune", -100, 100, 0)
        row2 = QHBoxLayout()
        row2.addWidget(lbl)
        row2.addWidget(self.detune_slider, 1)
        row2.addWidget(val)
        layout.addLayout(row2)

        # Level
        lbl, self.level_slider, val = _make_knob("Level", 0, 100, 100)
        row3 = QHBoxLayout()
        row3.addWidget(lbl)
        row3.addWidget(self.level_slider, 1)
        row3.addWidget(val)
        layout.addLayout(row3)

        # Semi (for OSC 2)
        if osc_num == 2:
            lbl, self.semi_slider, val = _make_knob("Semi", -24, 24, 0)
            row4 = QHBoxLayout()
            row4.addWidget(lbl)
            row4.addWidget(self.semi_slider, 1)
            row4.addWidget(val)
            layout.addLayout(row4)

        self.wave_combo.currentTextChanged.connect(lambda: self.changed.emit())
        self.detune_slider.valueChanged.connect(lambda: self.changed.emit())
        self.level_slider.valueChanged.connect(lambda: self.changed.emit())


# ── Filter Section ────────────────────────────────────────────────────────

class FilterSection(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        layout.addWidget(_section_label("FILTER"))

        # Type
        row = QHBoxLayout()
        row.addWidget(QLabel("Type"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["lowpass", "highpass", "bandpass", "notch"])
        self.type_combo.setFixedWidth(80)
        row.addWidget(self.type_combo)
        row.addStretch()
        layout.addLayout(row)

        # Cutoff
        lbl, self.cutoff_slider, val = _make_knob("Cutoff", 20, 18000, 4000)
        r2 = QHBoxLayout()
        r2.addWidget(lbl)
        r2.addWidget(self.cutoff_slider, 1)
        r2.addWidget(val)
        layout.addLayout(r2)

        # Resonance
        lbl, self.reso_slider, val = _make_knob("Reso", 1, 200, 10)  # x10 for precision
        r3 = QHBoxLayout()
        r3.addWidget(lbl)
        r3.addWidget(self.reso_slider, 1)
        r3.addWidget(val)
        layout.addLayout(r3)

        # Env Depth
        lbl, self.env_depth_slider, val = _make_knob("Env Depth", 0, 10000, 3000)
        r4 = QHBoxLayout()
        r4.addWidget(lbl)
        r4.addWidget(self.env_depth_slider, 1)
        r4.addWidget(val)
        layout.addLayout(r4)

        self.type_combo.currentTextChanged.connect(lambda: self.changed.emit())
        self.cutoff_slider.valueChanged.connect(lambda: self.changed.emit())
        self.reso_slider.valueChanged.connect(lambda: self.changed.emit())


# ── ADSR Section ──────────────────────────────────────────────────────────

class ADSRSection(QWidget):
    changed = pyqtSignal()

    def __init__(self, label: str = "AMP ENV", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        layout.addWidget(_section_label(label))

        self.adsr_widget = ADSRWidget()
        layout.addWidget(self.adsr_widget)

        # A/D/S/R sliders
        for name, attr, min_v, max_v, default in [
            ("A", "attack_slider", 1, 5000, 10),
            ("D", "decay_slider", 1, 5000, 200),
            ("S", "sustain_slider", 0, 100, 70),
            ("R", "release_slider", 1, 5000, 400),
        ]:
            lbl, slider, val = _make_knob(name, min_v, max_v, default)
            setattr(self, attr, slider)
            row = QHBoxLayout()
            row.addWidget(lbl)
            row.addWidget(slider, 1)
            row.addWidget(val)
            layout.addLayout(row)
            slider.valueChanged.connect(self._update_visual)

        self._update_visual()

    def _update_visual(self):
        a = self.attack_slider.value() / 1000.0
        d = self.decay_slider.value() / 1000.0
        s = self.sustain_slider.value() / 100.0
        r = self.release_slider.value() / 1000.0
        self.adsr_widget.set_adsr(a, d, s, r)
        self.changed.emit()

    def get_values(self) -> tuple[float, float, float, float]:
        return (
            self.attack_slider.value() / 1000.0,
            self.decay_slider.value() / 1000.0,
            self.sustain_slider.value() / 100.0,
            self.release_slider.value() / 1000.0,
        )


# ── LFO Section ───────────────────────────────────────────────────────────

class LFOSection(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        layout.addWidget(_section_label("LFO"))

        # Waveform
        row = QHBoxLayout()
        row.addWidget(QLabel("Wave"))
        self.wave_combo = QComboBox()
        self.wave_combo.addItems(["sine", "triangle", "saw", "square"])
        self.wave_combo.setFixedWidth(80)
        row.addWidget(self.wave_combo)
        row.addStretch()
        layout.addLayout(row)

        # Rate
        lbl, self.rate_slider, val = _make_knob("Rate", 1, 200, 20)  # x10 Hz
        r2 = QHBoxLayout()
        r2.addWidget(lbl)
        r2.addWidget(self.rate_slider, 1)
        r2.addWidget(val)
        layout.addLayout(r2)

        # Depth
        lbl, self.depth_slider, val = _make_knob("Depth", 0, 100, 50)
        r3 = QHBoxLayout()
        r3.addWidget(lbl)
        r3.addWidget(self.depth_slider, 1)
        r3.addWidget(val)
        layout.addLayout(r3)

        # → Filter
        lbl, self.to_filter_slider, val = _make_knob("→ Filter", 0, 5000, 0)
        r4 = QHBoxLayout()
        r4.addWidget(lbl)
        r4.addWidget(self.to_filter_slider, 1)
        r4.addWidget(val)
        layout.addLayout(r4)

        # → Pitch
        lbl, self.to_pitch_slider, val = _make_knob("→ Pitch", 0, 100, 0)
        r5 = QHBoxLayout()
        r5.addWidget(lbl)
        r5.addWidget(self.to_pitch_slider, 1)
        r5.addWidget(val)
        layout.addLayout(r5)


# ── Main Synth Panel ──────────────────────────────────────────────────────

class SynthPanel(QWidget):
    """Main synth control panel for the detail view tab."""

    synth_type_changed = pyqtSignal(str)
    preset_changed = pyqtSignal(str)
    params_changed = pyqtSignal(dict)
    pad_triggered = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)

        # ── Top bar: synth type + preset ──
        top = QHBoxLayout()
        top.addWidget(QLabel("Synth:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Subtractive", "FM", "Wavetable", "Granular", "Sampler", "Drum Machine"])
        self.type_combo.setFixedWidth(110)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        top.addWidget(self.type_combo)

        top.addSpacing(12)
        top.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setFixedWidth(130)
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        top.addWidget(self.preset_combo)

        top.addStretch()

        # Master level
        lbl, self.master_slider, val = _make_knob("Master", 0, 100, 70)
        top.addWidget(lbl)
        top.addWidget(self.master_slider)
        top.addWidget(val)

        root.addLayout(top)

        # ── Stacked widget for synth-specific controls ──
        self.stack = QStackedWidget()

        # Page 0: Subtractive
        self._sub_page = self._build_subtractive_page()
        self.stack.addWidget(self._sub_page)

        # Page 1: FM
        self._fm_page = self._build_fm_page()
        self.stack.addWidget(self._fm_page)

        # Page 2: Wavetable
        self._wt_page = self._build_wavetable_page()
        self.stack.addWidget(self._wt_page)

        # Page 3: Granular
        self._gran_page = self._build_granular_page()
        self.stack.addWidget(self._gran_page)

        # Page 4: Sampler
        self._samp_page = self._build_sampler_page()
        self.stack.addWidget(self._samp_page)

        # Page 5: Drum Machine
        self._drum_page = DrumMachinePanel()
        self._drum_page.pad_hit.connect(self.pad_triggered.emit)
        self.stack.addWidget(self._drum_page)

        root.addWidget(self.stack, 1)

        # Load initial presets
        self._update_presets()

    def _build_subtractive_page(self) -> QWidget:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {C['bg_darkest']}; }}")

        content = QWidget()
        layout = QHBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # OSC 1
        self.osc1 = OscillatorSection(1)
        layout.addWidget(self.osc1)

        # OSC 2
        self.osc2 = OscillatorSection(2)
        layout.addWidget(self.osc2)

        # Mix
        mix_w = QWidget()
        mix_l = QVBoxLayout(mix_w)
        mix_l.setContentsMargins(0, 0, 0, 0)
        mix_l.addWidget(_section_label("MIX"))
        lbl, self.osc_mix_slider, val = _make_knob("OSC Mix", 0, 100, 60)
        r = QHBoxLayout()
        r.addWidget(lbl)
        r.addWidget(self.osc_mix_slider, 1)
        r.addWidget(val)
        mix_l.addLayout(r)
        lbl, self.noise_slider, val = _make_knob("Noise", 0, 100, 0)
        r2 = QHBoxLayout()
        r2.addWidget(lbl)
        r2.addWidget(self.noise_slider, 1)
        r2.addWidget(val)
        mix_l.addLayout(r2)
        mix_l.addStretch()
        layout.addWidget(mix_w)

        # Filter
        self.filter_section = FilterSection()
        layout.addWidget(self.filter_section)

        # Amp ADSR
        self.amp_env = ADSRSection("AMP ENV")
        layout.addWidget(self.amp_env)

        # Filter ADSR
        self.filt_env = ADSRSection("FILT ENV")
        layout.addWidget(self.filt_env)

        # LFO
        self.lfo_section = LFOSection()
        layout.addWidget(self.lfo_section)

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _build_fm_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(_section_label("FM Synthesis — 4 Operators"))

        # Algorithm selector
        row = QHBoxLayout()
        row.addWidget(QLabel("Algorithm:"))
        self.fm_algo_combo = QComboBox()
        self.fm_algo_combo.addItems(["Chain (4→3→2→1)", "Parallel", "Stack (3→1, 4→2)"])
        self.fm_algo_combo.setFixedWidth(160)
        row.addWidget(self.fm_algo_combo)
        row.addStretch()
        layout.addLayout(row)

        # Operator controls
        self.fm_op_controls = []
        ops_layout = QHBoxLayout()
        for i in range(4):
            grp = QGroupBox(f"OP {i+1}")
            grp.setStyleSheet(f"""
                QGroupBox {{
                    background: {C['bg_mid']};
                    border: 1px solid {C['border']};
                    border-radius: 4px;
                    margin-top: 10px; padding-top: 14px;
                    font-weight: bold; color: {C['text_secondary']};
                }}
            """)
            gl = QVBoxLayout(grp)
            lbl, ratio_s, val = _make_knob("Ratio", 1, 160, 10 * (i + 1))  # x10
            r = QHBoxLayout()
            r.addWidget(lbl); r.addWidget(ratio_s, 1); r.addWidget(val)
            gl.addLayout(r)
            lbl, level_s, val = _make_knob("Level", 0, 100, max(10, 100 - i * 25))
            r2 = QHBoxLayout()
            r2.addWidget(lbl); r2.addWidget(level_s, 1); r2.addWidget(val)
            gl.addLayout(r2)
            self.fm_op_controls.append({"ratio": ratio_s, "level": level_s})
            ops_layout.addWidget(grp)
        layout.addLayout(ops_layout)
        layout.addStretch()
        return page

    def _build_wavetable_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(_section_label("Wavetable Synth"))

        # Morph position
        lbl, self.wt_morph_slider, val = _make_knob("Morph", 0, 100, 0)
        r = QHBoxLayout()
        r.addWidget(lbl); r.addWidget(self.wt_morph_slider, 1); r.addWidget(val)
        layout.addLayout(r)

        # Morph LFO
        lbl, self.wt_lfo_rate, val = _make_knob("LFO Rate", 1, 100, 2)
        r2 = QHBoxLayout()
        r2.addWidget(lbl); r2.addWidget(self.wt_lfo_rate, 1); r2.addWidget(val)
        layout.addLayout(r2)

        lbl, self.wt_lfo_depth, val = _make_knob("LFO Depth", 0, 100, 0)
        r3 = QHBoxLayout()
        r3.addWidget(lbl); r3.addWidget(self.wt_lfo_depth, 1); r3.addWidget(val)
        layout.addLayout(r3)

        layout.addStretch()
        return page

    def _build_granular_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(_section_label("Granular Synth"))

        for name, attr, min_v, max_v, default in [
            ("Grain Size", "gran_size_slider", 5, 500, 60),
            ("Density", "gran_density_slider", 1, 50, 8),
            ("Position", "gran_pos_slider", 0, 100, 50),
            ("Spread", "gran_spread_slider", 0, 100, 10),
            ("Pitch Var", "gran_pitch_slider", 0, 24, 0),
        ]:
            lbl, slider, val = _make_knob(name, min_v, max_v, default)
            setattr(self, attr, slider)
            r = QHBoxLayout()
            r.addWidget(lbl); r.addWidget(slider, 1); r.addWidget(val)
            layout.addLayout(r)

        layout.addStretch()
        return page

    def _build_sampler_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(_section_label("Sampler"))

        info = QLabel("Load samples via drag & drop or file browser.\nZones are auto-mapped by filename.")
        info.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; padding: 8px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Filter controls for sampler
        lbl, self.samp_cutoff, val = _make_knob("Cutoff", 20, 18000, 12000)
        r = QHBoxLayout()
        r.addWidget(lbl); r.addWidget(self.samp_cutoff, 1); r.addWidget(val)
        layout.addLayout(r)

        lbl, self.samp_reso, val = _make_knob("Reso", 1, 200, 7)
        r2 = QHBoxLayout()
        r2.addWidget(lbl); r2.addWidget(self.samp_reso, 1); r2.addWidget(val)
        layout.addLayout(r2)

        layout.addStretch()
        return page

    def _on_type_changed(self, text: str):
        type_map = {
            "Subtractive": 0, "FM": 1, "Wavetable": 2,
            "Granular": 3, "Sampler": 4, "Drum Machine": 5,
        }
        idx = type_map.get(text, 0)
        self.stack.setCurrentIndex(idx)
        self._update_presets()
        self.synth_type_changed.emit(text.lower().replace(" ", "_"))

    def _update_presets(self):
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        synth_type = self.type_combo.currentText()
        if synth_type == "Subtractive":
            from core.synth_engine import SUBTRACTIVE_PRESETS
            self.preset_combo.addItems(list(SUBTRACTIVE_PRESETS.keys()))
        elif synth_type == "FM":
            from core.synth_engine import FM_PRESETS
            self.preset_combo.addItems(list(FM_PRESETS.keys()))
        elif synth_type == "Drum Machine":
            self.preset_combo.addItems(["Default Kit"])
        else:
            self.preset_combo.addItems(["Init"])
        self.preset_combo.blockSignals(False)

    def _on_preset_changed(self, name: str):
        if name:
            self.preset_changed.emit(name)

    def get_current_params(self) -> dict:
        """Collect all current UI parameters into a dict."""
        return {
            "synth_type": self.type_combo.currentText().lower().replace(" ", "_"),
            "preset": self.preset_combo.currentText(),
            "master_level": self.master_slider.value() / 100.0,
            "osc1_wave": self.osc1.wave_combo.currentText() if hasattr(self, 'osc1') else "saw",
            "osc1_detune": self.osc1.detune_slider.value() if hasattr(self, 'osc1') else 0,
            "osc1_level": self.osc1.level_slider.value() / 100.0 if hasattr(self, 'osc1') else 1.0,
            "osc2_wave": self.osc2.wave_combo.currentText() if hasattr(self, 'osc2') else "saw",
            "osc2_detune": self.osc2.detune_slider.value() if hasattr(self, 'osc2') else 7,
            "osc2_level": self.osc2.level_slider.value() / 100.0 if hasattr(self, 'osc2') else 0.8,
            "filter_type": self.filter_section.type_combo.currentText() if hasattr(self, 'filter_section') else "lowpass",
            "filter_cutoff": self.filter_section.cutoff_slider.value() if hasattr(self, 'filter_section') else 4000,
            "filter_reso": self.filter_section.reso_slider.value() / 10.0 if hasattr(self, 'filter_section') else 1.0,
        }
