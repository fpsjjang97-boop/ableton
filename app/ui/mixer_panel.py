"""
Mixer panel for the MIDI AI Workstation.

Provides a horizontal strip of channel faders, pan knobs, VU meters,
mute/solo buttons, and a master channel -- modeled after Ableton Live's
mixer view.
"""
from __future__ import annotations

import random
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton,
    QFrame, QScrollArea, QComboBox, QDial, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QFont, QLinearGradient, QPen

from core.models import Track, ProjectState
from config import COLORS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CHANNEL_WIDTH = 80
FADER_HEIGHT = 130
VU_WIDTH = 10
VU_HEIGHT = 120


# ---------------------------------------------------------------------------
# VUMeter
# ---------------------------------------------------------------------------

class VUMeter(QWidget):
    """Vertical volume-level meter with green/yellow/red gradient and peak hold."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(VU_WIDTH, VU_HEIGHT)
        self._level: float = 0.0        # 0..1
        self._peak: float = 0.0         # 0..1
        self._peak_hold: int = 0        # frames to hold peak
        self._decay_rate: float = 0.04

    # -- public API ---------------------------------------------------------

    def set_level(self, level: float) -> None:
        """Set instantaneous level (0..1) and update peak."""
        self._level = max(0.0, min(level, 1.0))
        if self._level >= self._peak:
            self._peak = self._level
            self._peak_hold = 18  # hold ~18 frames
        self.update()

    def decay(self) -> None:
        """Call periodically to animate decay."""
        self._level = max(0.0, self._level - self._decay_rate)
        if self._peak_hold > 0:
            self._peak_hold -= 1
        else:
            self._peak = max(0.0, self._peak - self._decay_rate * 0.5)
        self.update()

    # -- painting -----------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # background
        p.fillRect(0, 0, w, h, QColor(COLORS["bg_darkest"]))

        # gradient bar
        bar_h = int(h * self._level)
        if bar_h > 0:
            grad = QLinearGradient(0, h, 0, 0)
            grad.setColorAt(0.0, QColor(COLORS["meter_green"]))
            grad.setColorAt(0.6, QColor(COLORS["meter_yellow"]))
            grad.setColorAt(1.0, QColor(COLORS["meter_red"]))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(1, h - bar_h, w - 2, bar_h)

        # peak hold line
        if self._peak > 0.01:
            peak_y = int(h * (1.0 - self._peak))
            pen = QPen(QColor(COLORS["text_primary"]), 1)
            p.setPen(pen)
            p.drawLine(1, peak_y, w - 2, peak_y)

        # thin border
        p.setPen(QColor(COLORS["border"]))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, w - 1, h - 1)
        p.end()


# ---------------------------------------------------------------------------
# ChannelStrip
# ---------------------------------------------------------------------------

class ChannelStrip(QFrame):
    """Single mixer channel strip with fader, pan, VU, mute/solo."""

    volume_changed = pyqtSignal(int, int)   # track_index, value
    pan_changed = pyqtSignal(int, int)      # track_index, value
    mute_toggled = pyqtSignal(int)          # track_index
    solo_toggled = pyqtSignal(int)          # track_index

    def __init__(self, track_index: int, track: Track,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._index = track_index
        self._track = track

        self.setFixedWidth(CHANNEL_WIDTH)
        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet(
            f"ChannelStrip {{ background: {COLORS['bg_dark']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 3px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 4)
        layout.setSpacing(3)

        # -- colour header bar ------------------------------------------------
        self.color_bar = QFrame()
        self.color_bar.setFixedHeight(5)
        self.color_bar.setStyleSheet(
            f"background: {track.color}; border: none; border-radius: 2px;"
        )
        layout.addWidget(self.color_bar)

        # -- track name -------------------------------------------------------
        self.lbl_name = QLabel(track.name)
        self.lbl_name.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_name.setStyleSheet(
            f"color: {COLORS['text_primary']}; background: transparent;"
        )
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setMaximumHeight(28)
        layout.addWidget(self.lbl_name)

        # -- instrument label -------------------------------------------------
        gm_name = f"Prg {track.instrument}"
        self.lbl_instrument = QLabel(gm_name)
        self.lbl_instrument.setFont(QFont("Segoe UI", 7))
        self.lbl_instrument.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_instrument.setStyleSheet(
            f"color: {COLORS['text_dim']}; background: transparent;"
        )
        layout.addWidget(self.lbl_instrument)

        # -- pan knob ----------------------------------------------------------
        pan_row = QHBoxLayout()
        pan_row.setContentsMargins(0, 0, 0, 0)
        lbl_p = QLabel("P")
        lbl_p.setFont(QFont("Segoe UI", 7))
        lbl_p.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        pan_row.addWidget(lbl_p)

        self.dial_pan = QDial()
        self.dial_pan.setRange(0, 127)
        self.dial_pan.setValue(track.pan)
        self.dial_pan.setFixedSize(32, 32)
        self.dial_pan.setNotchesVisible(True)
        pan_row.addWidget(self.dial_pan)
        layout.addLayout(pan_row)

        # -- send knobs (2 aux sends) ------------------------------------------
        for i in range(2):
            send_row = QHBoxLayout()
            send_row.setContentsMargins(0, 0, 0, 0)
            lbl_s = QLabel(f"S{i+1}")
            lbl_s.setFont(QFont("Segoe UI", 7))
            lbl_s.setStyleSheet(
                f"color: {COLORS['text_dim']}; background: transparent;"
            )
            send_row.addWidget(lbl_s)
            dial_send = QDial()
            dial_send.setRange(0, 127)
            dial_send.setValue(0)
            dial_send.setFixedSize(28, 28)
            send_row.addWidget(dial_send)
            layout.addLayout(send_row)

        # -- fader + VU row ----------------------------------------------------
        fader_row = QHBoxLayout()
        fader_row.setContentsMargins(0, 0, 0, 0)
        fader_row.setSpacing(3)

        self.slider_vol = QSlider(Qt.Orientation.Vertical)
        self.slider_vol.setRange(0, 127)
        self.slider_vol.setValue(track.volume)
        self.slider_vol.setFixedHeight(FADER_HEIGHT)
        fader_row.addWidget(self.slider_vol, 1)

        self.vu_meter = VUMeter()
        fader_row.addWidget(self.vu_meter)

        layout.addLayout(fader_row, 1)

        # -- volume readout ----------------------------------------------------
        self.lbl_vol = QLabel(str(track.volume))
        self.lbl_vol.setFont(QFont("Consolas", 8))
        self.lbl_vol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_vol.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background: transparent;"
        )
        layout.addWidget(self.lbl_vol)

        # -- mute / solo -------------------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(2)

        self.btn_mute = QPushButton("M")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setChecked(track.muted)
        self.btn_mute.setFixedSize(30, 20)
        self.btn_mute.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.btn_mute.setStyleSheet(
            f"QPushButton {{ background: {COLORS['bg_mid']}; color: {COLORS['text_secondary']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 2px; }}"
            f"QPushButton:checked {{ background: {COLORS['accent_orange']}; color: #FFF; }}"
        )
        btn_row.addWidget(self.btn_mute)

        self.btn_solo = QPushButton("S")
        self.btn_solo.setCheckable(True)
        self.btn_solo.setChecked(track.solo)
        self.btn_solo.setFixedSize(30, 20)
        self.btn_solo.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.btn_solo.setStyleSheet(
            f"QPushButton {{ background: {COLORS['bg_mid']}; color: {COLORS['text_secondary']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 2px; }}"
            f"QPushButton:checked {{ background: {COLORS['accent_yellow']}; color: #000; }}"
        )
        btn_row.addWidget(self.btn_solo)

        layout.addLayout(btn_row)

        # -- connections -------------------------------------------------------
        self.slider_vol.valueChanged.connect(self._on_vol)
        self.dial_pan.valueChanged.connect(self._on_pan)
        self.btn_mute.clicked.connect(lambda: self.mute_toggled.emit(self._index))
        self.btn_solo.clicked.connect(lambda: self.solo_toggled.emit(self._index))

    # -- handlers -----------------------------------------------------------

    def _on_vol(self, val: int) -> None:
        self.lbl_vol.setText(str(val))
        self.volume_changed.emit(self._index, val)

    def _on_pan(self, val: int) -> None:
        self.pan_changed.emit(self._index, val)

    # -- public API ---------------------------------------------------------

    def update_track(self, track: Track) -> None:
        """Re-sync controls with track data."""
        self._track = track
        self.lbl_name.setText(track.name)
        self.color_bar.setStyleSheet(
            f"background: {track.color}; border: none; border-radius: 2px;"
        )
        self.slider_vol.blockSignals(True)
        self.slider_vol.setValue(track.volume)
        self.slider_vol.blockSignals(False)
        self.lbl_vol.setText(str(track.volume))

        self.dial_pan.blockSignals(True)
        self.dial_pan.setValue(track.pan)
        self.dial_pan.blockSignals(False)

        self.btn_mute.blockSignals(True)
        self.btn_mute.setChecked(track.muted)
        self.btn_mute.blockSignals(False)

        self.btn_solo.blockSignals(True)
        self.btn_solo.setChecked(track.solo)
        self.btn_solo.blockSignals(False)

        self.lbl_instrument.setText(f"Prg {track.instrument}")


# ---------------------------------------------------------------------------
# MasterStrip
# ---------------------------------------------------------------------------

class MasterStrip(QFrame):
    """Master channel strip -- fader + VU, no mute/solo."""

    volume_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(CHANNEL_WIDTH + 10)
        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet(
            f"MasterStrip {{ background: {COLORS['bg_panel']}; "
            f"border: 1px solid {COLORS['accent_secondary']}; border-radius: 3px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)

        # header
        header = QLabel("MASTER")
        header.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            f"color: {COLORS['accent_secondary']}; background: transparent;"
        )
        layout.addWidget(header)

        # fader + VU
        fader_row = QHBoxLayout()
        fader_row.setContentsMargins(0, 0, 0, 0)
        fader_row.setSpacing(4)

        self.slider_vol = QSlider(Qt.Orientation.Vertical)
        self.slider_vol.setRange(0, 127)
        self.slider_vol.setValue(100)
        self.slider_vol.setFixedHeight(FADER_HEIGHT + 30)
        fader_row.addWidget(self.slider_vol, 1)

        vu_col = QVBoxLayout()
        vu_col.setSpacing(2)
        self.vu_l = VUMeter()
        self.vu_r = VUMeter()
        vu_col.addWidget(self.vu_l)
        vu_col.addWidget(self.vu_r)
        fader_row.addLayout(vu_col)

        layout.addLayout(fader_row, 1)

        # volume readout
        self.lbl_vol = QLabel("100")
        self.lbl_vol.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        self.lbl_vol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_vol.setStyleSheet(
            f"color: {COLORS['text_primary']}; background: transparent;"
        )
        layout.addWidget(self.lbl_vol)

        # db label
        self.lbl_db = QLabel("0.0 dB")
        self.lbl_db.setFont(QFont("Segoe UI", 7))
        self.lbl_db.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_db.setStyleSheet(
            f"color: {COLORS['text_dim']}; background: transparent;"
        )
        layout.addWidget(self.lbl_db)

        # connections
        self.slider_vol.valueChanged.connect(self._on_vol)

    def _on_vol(self, val: int) -> None:
        self.lbl_vol.setText(str(val))
        # Convert 0-127 to roughly -inf..+6 dB display
        if val == 0:
            self.lbl_db.setText("-inf dB")
        else:
            db = 20.0 * (val / 100.0) - 20.0 + 6.0
            self.lbl_db.setText(f"{db:+.1f} dB")
        self.volume_changed.emit(val)


# ---------------------------------------------------------------------------
# MixerPanel
# ---------------------------------------------------------------------------

class MixerPanel(QWidget):
    """Full mixer view: scrollable channel strips + fixed master strip."""

    channel_volume_changed = pyqtSignal(int, int)
    channel_pan_changed = pyqtSignal(int, int)
    channel_mute_toggled = pyqtSignal(int)
    channel_solo_toggled = pyqtSignal(int)
    master_volume_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._project: ProjectState | None = None
        self._strips: list[ChannelStrip] = []

        self.setStyleSheet(f"background: {COLORS['bg_darkest']};")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- scrollable channel area -------------------------------------------
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {COLORS['bg_darkest']}; border: none; }}"
        )

        self._channel_container = QWidget()
        self._channel_layout = QHBoxLayout(self._channel_container)
        self._channel_layout.setContentsMargins(4, 4, 4, 4)
        self._channel_layout.setSpacing(2)
        self._channel_layout.addStretch()

        self._scroll.setWidget(self._channel_container)
        root.addWidget(self._scroll, 1)

        # -- separator ---------------------------------------------------------
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(2)
        sep.setStyleSheet(f"background: {COLORS['border']};")
        root.addWidget(sep)

        # -- master strip (always visible) ------------------------------------
        self.master_strip = MasterStrip()
        self.master_strip.volume_changed.connect(self.master_volume_changed.emit)
        root.addWidget(self.master_strip)

        # -- VU decay timer ----------------------------------------------------
        self._vu_timer = QTimer(self)
        self._vu_timer.timeout.connect(self._decay_meters)
        self._vu_timer.start(50)

    # -- public API ---------------------------------------------------------

    def set_project(self, project_state: ProjectState) -> None:
        """Rebuild channel strips from project tracks."""
        self._project = project_state
        self._clear_strips()

        for i, track in enumerate(project_state.tracks):
            strip = ChannelStrip(i, track)
            strip.volume_changed.connect(self.channel_volume_changed.emit)
            strip.pan_changed.connect(self.channel_pan_changed.emit)
            strip.mute_toggled.connect(self.channel_mute_toggled.emit)
            strip.solo_toggled.connect(self.channel_solo_toggled.emit)
            self._strips.append(strip)
            self._channel_layout.insertWidget(
                self._channel_layout.count() - 1, strip
            )

    def update_meters(self, levels: list[float]) -> None:
        """Set VU levels for each channel. *levels* has one float per track."""
        for i, strip in enumerate(self._strips):
            if i < len(levels):
                strip.vu_meter.set_level(levels[i])
        # master: average of all
        if levels:
            avg = sum(levels) / len(levels)
            self.master_strip.vu_l.set_level(avg * random.uniform(0.9, 1.05))
            self.master_strip.vu_r.set_level(avg * random.uniform(0.9, 1.05))

    def refresh(self) -> None:
        """Re-sync strip controls from current project tracks."""
        if self._project is None:
            return
        tracks = self._project.tracks
        # If track count changed, rebuild
        if len(tracks) != len(self._strips):
            self.set_project(self._project)
            return
        for i, strip in enumerate(self._strips):
            strip.update_track(tracks[i])

    # -- internal -----------------------------------------------------------

    def _clear_strips(self) -> None:
        for strip in self._strips:
            self._channel_layout.removeWidget(strip)
            strip.setParent(None)
            strip.deleteLater()
        self._strips.clear()

    def _decay_meters(self) -> None:
        for strip in self._strips:
            strip.vu_meter.decay()
        self.master_strip.vu_l.decay()
        self.master_strip.vu_r.decay()
