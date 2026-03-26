"""
Transport bar widget for the MIDI AI Workstation.

Modeled after Ableton Live's top transport bar: compact 36px strip with
tap tempo, BPM, time signature, metronome, playback controls, position
displays, key/scale/snap selectors, CPU meter, and MIDI indicator.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QDoubleSpinBox,
    QComboBox, QFrame, QToolButton, QSizePolicy, QSpacerItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QPainter, QColor, QPaintEvent, QPen

from core.models import ProjectState, NOTE_NAMES, TICKS_PER_BEAT, SCALE_INTERVALS
from config import COLORS, MIN_BPM, MAX_BPM, SNAP_VALUES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEP_COLOR = "#2A2A2A"
_BTN_SIZE = 24
_MONO = "Consolas"


def _sep() -> QFrame:
    """Thin vertical separator line."""
    s = QFrame()
    s.setFrameShape(QFrame.Shape.VLine)
    s.setFixedWidth(1)
    s.setStyleSheet(f"background:{_SEP_COLOR}; border:none;")
    return s


def _flat_btn(text: str, tip: str, size: int = _BTN_SIZE,
              checkable: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setToolTip(tip)
    btn.setCheckable(checkable)
    btn.setFixedSize(size, size)
    btn.setFont(QFont("Segoe UI Symbol", 10))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton{{background:transparent;border:none;color:{COLORS['text_secondary']};}}"
        f"QPushButton:hover{{color:{COLORS['text_primary']};background:{COLORS['bg_hover']};"
        f"border-radius:3px;}}"
        f"QPushButton:checked{{color:#FFF;background:{COLORS['accent']};border-radius:3px;}}"
    )
    return btn


def _display_label(text: str, width: int = 80) -> QLabel:
    """Recessed monospace display box (position / time)."""
    lbl = QLabel(text)
    lbl.setFont(QFont(_MONO, 11, QFont.Weight.Bold))
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setFixedWidth(width)
    lbl.setFixedHeight(22)
    lbl.setStyleSheet(
        f"color:{COLORS['accent_light']};background:{COLORS['bg_darkest']};"
        f"border:1px solid {_SEP_COLOR};border-radius:2px;padding:0 4px;"
    )
    return lbl


def _compact_combo(items: list[str], width: int = 60) -> QComboBox:
    cb = QComboBox()
    cb.addItems(items)
    cb.setFixedWidth(width)
    cb.setFixedHeight(22)
    cb.setStyleSheet(
        f"QComboBox{{background:{COLORS['bg_darkest']};color:{COLORS['text_primary']};"
        f"border:1px solid {_SEP_COLOR};border-radius:2px;padding:0 4px;"
        f"font-size:10px;}}"
        f"QComboBox::drop-down{{border:none;width:12px;}}"
        f"QComboBox QAbstractItemView{{background:{COLORS['bg_dark']};"
        f"color:{COLORS['text_primary']};selection-background-color:{COLORS['bg_selected']};}}"
    )
    return cb


# ---------------------------------------------------------------------------
# CPU meter (decorative)
# ---------------------------------------------------------------------------

class _CpuMeter(QWidget):
    """Tiny horizontal bar simulating CPU load."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._value = 0.12
        self.setFixedSize(50, 18)
        self.setToolTip("CPU")

    def set_value(self, v: float) -> None:
        self._value = max(0.0, min(v, 1.0))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(COLORS["bg_darkest"]))
        bar_w = int((self.width() - 2) * self._value)
        color = COLORS["meter_green"] if self._value < 0.6 else (
            COLORS["meter_yellow"] if self._value < 0.85 else COLORS["meter_red"])
        p.fillRect(1, 10, bar_w, 6, QColor(color))
        p.setPen(QColor(COLORS["text_secondary"]))
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(2, 9, f"CPU {int(self._value * 100)}%")
        p.end()


# ---------------------------------------------------------------------------
# MIDI activity indicator
# ---------------------------------------------------------------------------

class _MidiIndicator(QWidget):
    """Small dot that blinks on MIDI activity."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._active = False
        self.setFixedSize(14, 14)
        self.setToolTip("MIDI")

    def blink(self) -> None:
        self._active = True
        self.update()
        QTimer.singleShot(120, self._off)

    def _off(self) -> None:
        self._active = False
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#FFFFFF") if self._active else QColor(COLORS["text_dim"])
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(3, 3, 8, 8)
        p.end()


# ---------------------------------------------------------------------------
# TransportWidget
# ---------------------------------------------------------------------------

class TransportWidget(QWidget):
    """Ableton-style top transport bar — compact 36px strip."""

    # Signals
    play_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    record_clicked = pyqtSignal()
    rewind_clicked = pyqtSignal()
    loop_toggled = pyqtSignal(bool)
    bpm_changed = pyqtSignal(float)
    key_changed = pyqtSignal(str)
    scale_changed = pyqtSignal(str)
    snap_changed = pyqtSignal(float)
    metronome_toggled = pyqtSignal(bool)
    tap_tempo = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._playing = False
        self._recording = False
        self._project: ProjectState | None = None
        self._tap_times: list[float] = []

        self.setFixedHeight(36)
        self.setStyleSheet(
            f"TransportWidget{{background:{COLORS['bg_transport']};}}"
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(6, 0, 6, 0)
        root.setSpacing(4)

        # ── LEFT: Tap / BPM / Time Sig / Metronome ───────────────────────
        self.btn_tap = QPushButton("Tap")
        self.btn_tap.setFixedSize(32, 22)
        self.btn_tap.setFont(QFont("Segoe UI", 8))
        self.btn_tap.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tap.setToolTip("Tap Tempo")
        self.btn_tap.setStyleSheet(
            f"QPushButton{{background:{COLORS['bg_mid']};color:{COLORS['text_secondary']};"
            f"border:1px solid {_SEP_COLOR};border-radius:2px;font-size:9px;}}"
            f"QPushButton:hover{{color:{COLORS['text_primary']};background:{COLORS['bg_hover']};}}"
        )
        root.addWidget(self.btn_tap)

        self.spin_bpm = QDoubleSpinBox()
        self.spin_bpm.setRange(MIN_BPM, MAX_BPM)
        self.spin_bpm.setDecimals(2)
        self.spin_bpm.setSingleStep(0.5)
        self.spin_bpm.setValue(120.0)
        self.spin_bpm.setFixedSize(68, 22)
        self.spin_bpm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_bpm.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.spin_bpm.setStyleSheet(
            f"QDoubleSpinBox{{background:{COLORS['bg_darkest']};color:{COLORS['accent_light']};"
            f"border:1px solid {_SEP_COLOR};border-radius:2px;padding:0 2px;"
            f"font:bold 11px '{_MONO}';}}"
        )
        root.addWidget(self.spin_bpm)

        root.addWidget(_sep())

        self.lbl_time_sig = QLabel("4 / 4")
        self.lbl_time_sig.setFont(QFont(_MONO, 10, QFont.Weight.Bold))
        self.lbl_time_sig.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_time_sig.setFixedSize(40, 22)
        self.lbl_time_sig.setStyleSheet(
            f"color:{COLORS['text_primary']};background:{COLORS['bg_darkest']};"
            f"border:1px solid {_SEP_COLOR};border-radius:2px;"
        )
        root.addWidget(self.lbl_time_sig)

        self.btn_metronome = _flat_btn("M", "Metronome", checkable=True)
        root.addWidget(self.btn_metronome)

        root.addWidget(_sep())

        # ── CENTER SPACER ─────────────────────────────────────────────────
        root.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Minimum))

        # ── CENTER: Transport controls ────────────────────────────────────
        self.btn_rewind = _flat_btn("\u23EE", "Rewind")
        self.btn_play = _flat_btn("\u25B6", "Play / Pause", size=28, checkable=True)
        self.btn_stop = _flat_btn("\u23F9", "Stop")
        self.btn_record = _flat_btn("\u23FA", "Record", checkable=True)
        self.btn_record.setStyleSheet(
            self.btn_record.styleSheet() +
            f"QPushButton:checked{{color:#FFF;background:#C44;border-radius:3px;}}"
        )

        root.addWidget(self.btn_rewind)
        root.addWidget(self.btn_play)
        root.addWidget(self.btn_stop)
        root.addWidget(self.btn_record)

        root.addWidget(_sep())

        # ── Position / Time displays ──────────────────────────────────────
        self.lbl_position = _display_label("1.1.1", width=72)
        self.lbl_time = _display_label("00:00.00", width=76)
        self.lbl_time.setFont(QFont(_MONO, 10))
        self.lbl_time.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:{COLORS['bg_darkest']};"
            f"border:1px solid {_SEP_COLOR};border-radius:2px;padding:0 4px;"
        )
        root.addWidget(self.lbl_position)
        root.addWidget(self.lbl_time)

        root.addWidget(_sep())

        # ── CENTER SPACER ─────────────────────────────────────────────────
        root.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Minimum))

        # ── RIGHT: Loop / Key / Scale / Snap ──────────────────────────────
        self.btn_loop = _flat_btn("\U0001F501", "Loop On/Off", checkable=True)
        root.addWidget(self.btn_loop)

        self.combo_key = _compact_combo(NOTE_NAMES, width=48)
        self.combo_key.setToolTip("Key")
        root.addWidget(self.combo_key)

        self.combo_scale = _compact_combo(list(SCALE_INTERVALS.keys()), width=88)
        self.combo_scale.setToolTip("Scale")
        root.addWidget(self.combo_scale)

        root.addWidget(_sep())

        self.combo_snap = _compact_combo(list(SNAP_VALUES.keys()), width=54)
        self.combo_snap.setCurrentText("1/8")
        self.combo_snap.setToolTip("Snap / Grid")
        root.addWidget(self.combo_snap)

        root.addWidget(_sep())

        # ── CPU meter & MIDI indicator ────────────────────────────────────
        self._cpu_meter = _CpuMeter()
        self._midi_ind = _MidiIndicator()
        root.addWidget(self._cpu_meter)
        root.addWidget(self._midi_ind)

        # ── Connect signals ───────────────────────────────────────────────
        self.btn_tap.clicked.connect(self._on_tap)
        self.btn_play.clicked.connect(self._on_play)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_record.clicked.connect(self._on_record)
        self.btn_rewind.clicked.connect(self.rewind_clicked.emit)
        self.btn_loop.toggled.connect(self.loop_toggled.emit)
        self.btn_metronome.toggled.connect(self.metronome_toggled.emit)
        self.spin_bpm.valueChanged.connect(self.bpm_changed.emit)
        self.combo_key.currentTextChanged.connect(self.key_changed.emit)
        self.combo_scale.currentTextChanged.connect(self.scale_changed.emit)
        self.combo_snap.currentTextChanged.connect(self._on_snap)

        # Fake CPU animation
        self._meter_timer = QTimer(self)
        self._meter_timer.timeout.connect(self._tick_cpu)
        self._meter_timer.start(900)

    # ── Internal handlers ─────────────────────────────────────────────────

    def _on_tap(self) -> None:
        import time
        now = time.monotonic()
        self._tap_times.append(now)
        # Keep last 6 taps
        self._tap_times = self._tap_times[-6:]
        if len(self._tap_times) >= 2:
            intervals = [self._tap_times[i] - self._tap_times[i - 1]
                         for i in range(1, len(self._tap_times))]
            # Discard stale taps (>2 sec gap)
            intervals = [iv for iv in intervals if iv < 2.0]
            if intervals:
                avg = sum(intervals) / len(intervals)
                bpm = 60.0 / avg
                bpm = max(MIN_BPM, min(MAX_BPM, round(bpm, 2)))
                self.spin_bpm.setValue(bpm)
        self.tap_tempo.emit()

    def _on_play(self) -> None:
        self._playing = self.btn_play.isChecked()
        self.play_clicked.emit()

    def _on_stop(self) -> None:
        self._playing = False
        self.btn_play.setChecked(False)
        self.btn_record.setChecked(False)
        self._recording = False
        self.stop_clicked.emit()

    def _on_record(self) -> None:
        self._recording = self.btn_record.isChecked()
        self.record_clicked.emit()

    def _on_snap(self, text: str) -> None:
        val = SNAP_VALUES.get(text, 0)
        self.snap_changed.emit(float(val))

    def _tick_cpu(self) -> None:
        import random
        v = self._cpu_meter._value + random.uniform(-0.03, 0.04)
        self._cpu_meter.set_value(max(0.05, min(v, 0.40)))

    # ── Public API ────────────────────────────────────────────────────────

    def update_position(self, tick: int, project_state: ProjectState) -> None:
        """Update both position (bar.beat.sub) and time (MM:SS.ms) displays."""
        tpb = project_state.ticks_per_beat
        ts_num = project_state.time_signature.numerator
        beats_total = tick / tpb
        bar = int(beats_total // ts_num) + 1
        beat = int(beats_total % ts_num) + 1
        sixteenth = int((tick % tpb) / (tpb / 4)) + 1
        self.lbl_position.setText(f"{bar}.{beat}.{sixteenth}")

        secs = project_state.ticks_to_seconds(tick)
        mins = int(secs // 60)
        sec_part = secs % 60
        ms = int((sec_part - int(sec_part)) * 100)
        self.lbl_time.setText(f"{mins:02d}:{int(sec_part):02d}.{ms:02d}")

    def set_playing(self, playing: bool) -> None:
        self._playing = playing
        self.btn_play.blockSignals(True)
        self.btn_play.setChecked(playing)
        self.btn_play.setText("\u23F8" if playing else "\u25B6")
        self.btn_play.blockSignals(False)

    def set_recording(self, recording: bool) -> None:
        self._recording = recording
        self.btn_record.blockSignals(True)
        self.btn_record.setChecked(recording)
        self.btn_record.blockSignals(False)

    def set_project(self, project_state: ProjectState) -> None:
        """Sync all controls to the given project state."""
        self._project = project_state

        self.spin_bpm.blockSignals(True)
        self.spin_bpm.setValue(project_state.bpm)
        self.spin_bpm.blockSignals(False)

        ts = project_state.time_signature
        self.lbl_time_sig.setText(f"{ts.numerator} / {ts.denominator}")

        idx = NOTE_NAMES.index(project_state.key) if project_state.key in NOTE_NAMES else 0
        self.combo_key.blockSignals(True)
        self.combo_key.setCurrentIndex(idx)
        self.combo_key.blockSignals(False)

        self.combo_scale.blockSignals(True)
        si = self.combo_scale.findText(project_state.scale)
        if si >= 0:
            self.combo_scale.setCurrentIndex(si)
        self.combo_scale.blockSignals(False)

        self.btn_loop.blockSignals(True)
        self.btn_loop.setChecked(project_state.loop_enabled)
        self.btn_loop.blockSignals(False)

        self.update_position(0, project_state)

    def flash_midi(self) -> None:
        """Call this on any MIDI activity to blink the indicator."""
        self._midi_ind.blink()
