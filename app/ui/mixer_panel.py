"""
Mixer panel for the MIDI AI Workstation.

Provides a horizontal strip of channel faders, pan knobs, VU meters,
mute/solo buttons, and a master channel -- Cubase 15 스타일 채널 스트립
기능 포함 (게이트, 컴프, EQ, 새츄레이션, 인서트 슬롯, 센드 노브, 향상된 VU 미터).
"""
from __future__ import annotations

import math
import random
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton,
    QFrame, QScrollArea, QComboBox, QDial, QSizePolicy, QGridLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QRectF, QPointF
from PyQt6.QtGui import (
    QColor, QPainter, QPaintEvent, QFont, QLinearGradient, QPen,
    QConicalGradient, QBrush,
)

from core.models import Track, ProjectState
from config import COLORS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CHANNEL_WIDTH = 90          # Cubase 15 스타일: 90px로 확장
FADER_HEIGHT = 130
VU_WIDTH = 14               # VU 미터 약간 넓혀서 dB 눈금 표시
VU_HEIGHT = 120

# Cubase 15 VU 색상
VU_COLOR_GREEN = "#4CAF50"
VU_COLOR_YELLOW = "#FFC107"
VU_COLOR_RED = "#F44336"

# 채널 스트립 이펙트 기본 색상
STRIP_EFFECT_ACTIVE = "#5B9BD5"   # Cubase 블루 악센트
STRIP_EFFECT_INACTIVE = COLORS["bg_mid"]


# ---------------------------------------------------------------------------
# MiniSendKnob — QPainter로 그리는 미니 로터리 노브
# ---------------------------------------------------------------------------

class MiniSendKnob(QWidget):
    """20x20px 미니 로터리 노브 (QPainter 직접 그리기)."""

    value_changed = pyqtSignal(int)

    def __init__(self, label: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._value: int = 0          # 0..127
        self._label = label
        self.setFixedSize(20, 20)
        self.setToolTip(f"{label}: 0")
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_val = 0

    def set_value(self, val: int) -> None:
        self._value = max(0, min(127, val))
        self.setToolTip(f"{self._label}: {self._value}")
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 2

        # 배경 원
        p.setBrush(QColor(COLORS["bg_darkest"]))
        p.setPen(QPen(QColor(COLORS["border"]), 1))
        p.drawEllipse(QPointF(cx, cy), radius, radius)

        # 값 표시 아크 (225도 ~ -45도 범위, 총 270도)
        ratio = self._value / 127.0
        start_angle = 225  # 7시 방향
        sweep = ratio * 270  # 시계방향으로 진행

        # 아크 그리기
        if self._value > 0:
            pen = QPen(QColor(STRIP_EFFECT_ACTIVE), 2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(cx - radius + 1, cy - radius + 1,
                          (radius - 1) * 2, (radius - 1) * 2)
            p.drawArc(rect, int(start_angle * 16), int(-sweep * 16))

        # 포인터 라인
        angle_rad = math.radians(start_angle - sweep)
        ex = cx + (radius - 3) * math.cos(angle_rad)
        ey = cy - (radius - 3) * math.sin(angle_rad)
        p.setPen(QPen(QColor(COLORS["text_primary"]), 1.5))
        p.drawLine(QPointF(cx, cy), QPointF(ex, ey))
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_y = event.pos().y()
            self._drag_start_val = self._value

    def mouseMoveEvent(self, event):
        if self._dragging:
            dy = self._drag_start_y - event.pos().y()
            new_val = self._drag_start_val + dy
            new_val = max(0, min(127, new_val))
            if new_val != self._value:
                self._value = new_val
                self.setToolTip(f"{self._label}: {self._value}")
                self.value_changed.emit(self._value)
                self.update()

    def mouseReleaseEvent(self, event):
        self._dragging = False


# ---------------------------------------------------------------------------
# VUMeter — Cubase 15 스타일 향상된 VU 미터
# ---------------------------------------------------------------------------

class VUMeter(QWidget):
    """Cubase 15 스타일 수직 VU 미터: 그린→옐로우→레드 그라디언트, 피크 홀드, dB 눈금."""

    def __init__(self, show_db_scale: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self._show_db_scale = show_db_scale
        width = VU_WIDTH + (18 if show_db_scale else 0)
        self.setFixedSize(width, VU_HEIGHT)
        self._level: float = 0.0        # 0..1
        self._peak: float = 0.0         # 0..1
        self._peak_hold: int = 0        # 프레임 단위 피크 홀드 카운터
        self._peak_timer: int = 0       # ~2초 홀드 (40프레임 @ 50ms)
        self._decay_rate: float = 0.04

    # -- public API ---------------------------------------------------------

    def set_level(self, level: float) -> None:
        """순간 레벨 설정 (0..1), 피크 업데이트."""
        self._level = max(0.0, min(level, 1.0))
        if self._level >= self._peak:
            self._peak = self._level
            self._peak_timer = 40  # ~2초 홀드 (50ms interval × 40)
        self.update()

    def decay(self) -> None:
        """주기적으로 호출하여 감쇠 애니메이션."""
        self._level = max(0.0, self._level - self._decay_rate)
        if self._peak_timer > 0:
            self._peak_timer -= 1
        else:
            self._peak = max(0.0, self._peak - self._decay_rate * 0.5)
        self.update()

    # -- painting -----------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # dB 눈금 영역 오프셋
        meter_x = 0
        meter_w = VU_WIDTH
        if self._show_db_scale:
            meter_x = 18  # dB 라벨 공간

        # 배경
        p.fillRect(meter_x, 0, meter_w, h, QColor(COLORS["bg_darkest"]))

        # Cubase 색상 그라디언트 바
        bar_h = int(h * self._level)
        if bar_h > 0:
            grad = QLinearGradient(0, h, 0, 0)
            grad.setColorAt(0.0, QColor(VU_COLOR_GREEN))
            grad.setColorAt(0.6, QColor(VU_COLOR_YELLOW))
            grad.setColorAt(1.0, QColor(VU_COLOR_RED))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(meter_x + 1, h - bar_h, meter_w - 2, bar_h)

        # 피크 홀드 라인 (흰색, 2초 유지 후 하강)
        if self._peak > 0.01:
            peak_y = int(h * (1.0 - self._peak))
            pen = QPen(QColor("#FFFFFF"), 1.5)
            p.setPen(pen)
            p.drawLine(meter_x + 1, peak_y, meter_x + meter_w - 2, peak_y)

        # 미터 테두리
        p.setPen(QColor(COLORS["border"]))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(meter_x, 0, meter_w - 1, h - 1)

        # dB 눈금 표시
        if self._show_db_scale:
            p.setFont(QFont("Segoe UI", 5))
            p.setPen(QColor(COLORS["text_dim"]))
            # dB 값과 대응하는 높이 비율 매핑
            db_marks = [
                ("0", 1.0),
                ("-3", 0.93),
                ("-6", 0.85),
                ("-12", 0.70),
                ("-20", 0.50),
                ("-40", 0.20),
                ("-∞", 0.0),
            ]
            for label, ratio in db_marks:
                y = int(h * (1.0 - ratio))
                p.drawText(0, y - 4, 16, 10,
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                           label)
                # 작은 눈금 선
                p.drawLine(meter_x - 2, y, meter_x, y)

        p.end()


# ---------------------------------------------------------------------------
# InsertSlot — Cubase 15 인서트 슬롯 위젯
# ---------------------------------------------------------------------------

class InsertSlot(QFrame):
    """인서트 이펙트 슬롯: 70px × 16px, 비어있으면 점선 테두리."""

    clicked = pyqtSignal(int)  # slot_index

    def __init__(self, slot_index: int, parent: QWidget | None = None):
        super().__init__(parent)
        self._slot_index = slot_index
        self._effect_name: str = ""
        self.setFixedSize(70, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

    def set_effect(self, name: str) -> None:
        """이펙트 이름 설정 (빈 문자열이면 비어있음)."""
        self._effect_name = name
        self._update_style()
        self.update()

    def _update_style(self) -> None:
        if self._effect_name:
            self.setStyleSheet(
                f"InsertSlot {{ background: {COLORS['bg_mid']}; "
                f"border: 1px solid {COLORS['border_focus']}; border-radius: 2px; }}"
            )
        else:
            self.setStyleSheet(
                f"InsertSlot {{ background: transparent; "
                f"border: 1px dashed {COLORS['border']}; border-radius: 2px; }}"
            )

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self._effect_name:
            p = QPainter(self)
            p.setPen(QColor(COLORS["text_secondary"]))
            p.setFont(QFont("Segoe UI", 6))
            p.drawText(self.rect().adjusted(3, 0, -3, 0),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       self._effect_name)
            p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._slot_index)


# ---------------------------------------------------------------------------
# StripEffectButton — 채널 스트립 이펙트 토글 버튼
# ---------------------------------------------------------------------------

class StripEffectButton(QPushButton):
    """20×20px 채널 스트립 이펙트 토글 버튼 (Gate, Comp, EQ, Sat)."""

    def __init__(self, label: str, parent: QWidget | None = None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setFixedSize(20, 20)
        self.setFont(QFont("Segoe UI", 5, QFont.Weight.Bold))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Channel Strip {label}")
        self.setStyleSheet(
            f"QPushButton {{ background: {STRIP_EFFECT_INACTIVE}; "
            f"color: {COLORS['text_dim']}; border: 1px solid {COLORS['border']}; "
            f"border-radius: 2px; padding: 0; }}"
            f"QPushButton:checked {{ background: {STRIP_EFFECT_ACTIVE}; "
            f"color: #FFF; border: 1px solid #7BB8E0; }}"
            f"QPushButton:hover {{ border: 1px solid {COLORS['border_focus']}; }}"
        )


# ---------------------------------------------------------------------------
# ChannelStrip — Cubase 15 스타일 채널 스트립
# ---------------------------------------------------------------------------

class ChannelStrip(QFrame):
    """Cubase 15 스타일 믹서 채널 스트립: 스트립 이펙트, 인서트, 센드, 향상된 VU."""

    volume_changed = pyqtSignal(int, int)   # track_index, value
    pan_changed = pyqtSignal(int, int)      # track_index, value
    mute_toggled = pyqtSignal(int)          # track_index
    solo_toggled = pyqtSignal(int)          # track_index
    strip_effect_toggled = pyqtSignal(int, str, bool)   # track_idx, effect_name, enabled
    insert_slot_clicked = pyqtSignal(int, int)          # track_idx, slot_idx
    send_level_changed = pyqtSignal(int, int, float)    # track_idx, send_idx, level

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

        # -- 메인 레이아웃 (수평: 컬러 바 + 콘텐츠) ---
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # -- 채널 컬러 스트립 (왼쪽 4px 세로 바) ---
        self.color_strip = QFrame()
        self.color_strip.setFixedWidth(4)
        self.color_strip.setStyleSheet(
            f"background: {track.color}; border: none; border-radius: 0px;"
        )
        outer.addWidget(self.color_strip)

        # -- 콘텐츠 영역 ---
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(3, 0, 3, 4)
        layout.setSpacing(2)
        outer.addWidget(content, 1)

        # -- 상단 컬러 헤더 바 ------------------------------------------------
        self.color_bar = QFrame()
        self.color_bar.setFixedHeight(4)
        self.color_bar.setStyleSheet(
            f"background: {track.color}; border: none; border-radius: 2px;"
        )
        layout.addWidget(self.color_bar)

        # -- 트랙 이름 -------------------------------------------------------
        self.lbl_name = QLabel(track.name)
        self.lbl_name.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_name.setStyleSheet(
            f"color: {COLORS['text_primary']}; background: transparent;"
        )
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setMaximumHeight(24)
        layout.addWidget(self.lbl_name)

        # -- 인스트루먼트 라벨 -------------------------------------------------
        gm_name = f"Prg {track.instrument}"
        self.lbl_instrument = QLabel(gm_name)
        self.lbl_instrument.setFont(QFont("Segoe UI", 6))
        self.lbl_instrument.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_instrument.setStyleSheet(
            f"color: {COLORS['text_dim']}; background: transparent;"
        )
        layout.addWidget(self.lbl_instrument)

        # -- 채널 스트립 이펙트 섹션 (Gate/Comp/EQ/Sat) ---
        strip_label = QLabel("Strip")
        strip_label.setFont(QFont("Segoe UI", 5))
        strip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        strip_label.setStyleSheet(
            f"color: {COLORS['text_dim']}; background: transparent;"
        )
        layout.addWidget(strip_label)

        strip_row = QHBoxLayout()
        strip_row.setContentsMargins(0, 0, 0, 0)
        strip_row.setSpacing(1)

        self.btn_gate = StripEffectButton("G")
        self.btn_comp = StripEffectButton("C")
        self.btn_eq = StripEffectButton("EQ")
        self.btn_sat = StripEffectButton("Sa")
        strip_row.addWidget(self.btn_gate)
        strip_row.addWidget(self.btn_comp)
        strip_row.addWidget(self.btn_eq)
        strip_row.addWidget(self.btn_sat)
        layout.addLayout(strip_row)

        # -- 인서트 슬롯 (4개) ---
        insert_label = QLabel("Inserts")
        insert_label.setFont(QFont("Segoe UI", 5))
        insert_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        insert_label.setStyleSheet(
            f"color: {COLORS['text_dim']}; background: transparent;"
        )
        layout.addWidget(insert_label)

        self.insert_slots: list[InsertSlot] = []
        for i in range(4):
            slot = InsertSlot(i)
            self.insert_slots.append(slot)
            layout.addWidget(slot, 0, Qt.AlignmentFlag.AlignCenter)

        # -- 팬 노브 ----------------------------------------------------------
        pan_row = QHBoxLayout()
        pan_row.setContentsMargins(0, 0, 0, 0)
        lbl_p = QLabel("P")
        lbl_p.setFont(QFont("Segoe UI", 6))
        lbl_p.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent;")
        pan_row.addWidget(lbl_p)

        self.dial_pan = QDial()
        self.dial_pan.setRange(0, 127)
        self.dial_pan.setValue(track.pan)
        self.dial_pan.setFixedSize(28, 28)
        self.dial_pan.setNotchesVisible(True)
        pan_row.addWidget(self.dial_pan)
        layout.addLayout(pan_row)

        # -- 센드 노브 (2개, QPainter 미니 로터리) ---
        send_row = QHBoxLayout()
        send_row.setContentsMargins(0, 0, 0, 0)
        send_row.setSpacing(2)

        self.send_knobs: list[MiniSendKnob] = []
        for i in range(2):
            lbl_s = QLabel(f"S{i+1}")
            lbl_s.setFont(QFont("Segoe UI", 5))
            lbl_s.setStyleSheet(
                f"color: {COLORS['text_dim']}; background: transparent;"
            )
            send_row.addWidget(lbl_s)
            knob = MiniSendKnob(f"Send {i+1}")
            knob.value_changed.connect(
                lambda val, si=i: self.send_level_changed.emit(
                    self._index, si, val / 127.0
                )
            )
            self.send_knobs.append(knob)
            send_row.addWidget(knob)

        layout.addLayout(send_row)

        # -- 페이더 + VU 행 (Cubase 15 향상된 VU) ---
        fader_row = QHBoxLayout()
        fader_row.setContentsMargins(0, 0, 0, 0)
        fader_row.setSpacing(2)

        self.slider_vol = QSlider(Qt.Orientation.Vertical)
        self.slider_vol.setRange(0, 127)
        self.slider_vol.setValue(track.volume)
        self.slider_vol.setFixedHeight(FADER_HEIGHT)
        fader_row.addWidget(self.slider_vol, 1)

        self.vu_meter = VUMeter(show_db_scale=True)
        fader_row.addWidget(self.vu_meter)

        layout.addLayout(fader_row, 1)

        # -- 볼륨 수치 표시 ----------------------------------------------------
        self.lbl_vol = QLabel(str(track.volume))
        self.lbl_vol.setFont(QFont("Consolas", 7))
        self.lbl_vol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_vol.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background: transparent;"
        )
        layout.addWidget(self.lbl_vol)

        # -- 뮤트 / 솔로 -------------------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(2)

        self.btn_mute = QPushButton("M")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setChecked(track.muted)
        self.btn_mute.setFixedSize(30, 20)
        self.btn_mute.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
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
        self.btn_solo.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self.btn_solo.setStyleSheet(
            f"QPushButton {{ background: {COLORS['bg_mid']}; color: {COLORS['text_secondary']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 2px; }}"
            f"QPushButton:checked {{ background: {COLORS['accent_yellow']}; color: #000; }}"
        )
        btn_row.addWidget(self.btn_solo)

        layout.addLayout(btn_row)

        # -- 시그널 연결 -------------------------------------------------------
        self.slider_vol.valueChanged.connect(self._on_vol)
        self.dial_pan.valueChanged.connect(self._on_pan)
        self.btn_mute.clicked.connect(lambda: self.mute_toggled.emit(self._index))
        self.btn_solo.clicked.connect(lambda: self.solo_toggled.emit(self._index))

        # Strip effect buttons -> strip_effect_toggled signal
        self.btn_gate.toggled.connect(
            lambda checked: self.strip_effect_toggled.emit(self._index, "gate", checked)
        )
        self.btn_comp.toggled.connect(
            lambda checked: self.strip_effect_toggled.emit(self._index, "comp", checked)
        )
        self.btn_eq.toggled.connect(
            lambda checked: self.strip_effect_toggled.emit(self._index, "eq", checked)
        )
        self.btn_sat.toggled.connect(
            lambda checked: self.strip_effect_toggled.emit(self._index, "sat", checked)
        )

        # Insert slots -> insert_slot_clicked signal
        for slot in self.insert_slots:
            slot.clicked.connect(
                lambda slot_idx: self.insert_slot_clicked.emit(self._index, slot_idx)
            )

    # -- handlers -----------------------------------------------------------

    def _on_vol(self, val: int) -> None:
        self.lbl_vol.setText(str(val))
        self.volume_changed.emit(self._index, val)

    def _on_pan(self, val: int) -> None:
        self.pan_changed.emit(self._index, val)

    # -- public API ---------------------------------------------------------

    def update_track(self, track: Track) -> None:
        """트랙 데이터와 컨트롤 동기화."""
        self._track = track
        self.lbl_name.setText(track.name)
        self.color_bar.setStyleSheet(
            f"background: {track.color}; border: none; border-radius: 2px;"
        )
        self.color_strip.setStyleSheet(
            f"background: {track.color}; border: none; border-radius: 0px;"
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
    """마스터 채널 스트립 -- 페이더 + 스테레오 VU, 뮤트/솔로 없음."""

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

        # 헤더
        header = QLabel("MASTER")
        header.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            f"color: {COLORS['accent_secondary']}; background: transparent;"
        )
        layout.addWidget(header)

        # 페이더 + VU
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

        # 볼륨 수치
        self.lbl_vol = QLabel("100")
        self.lbl_vol.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        self.lbl_vol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_vol.setStyleSheet(
            f"color: {COLORS['text_primary']}; background: transparent;"
        )
        layout.addWidget(self.lbl_vol)

        # dB 라벨
        self.lbl_db = QLabel("0.0 dB")
        self.lbl_db.setFont(QFont("Segoe UI", 7))
        self.lbl_db.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_db.setStyleSheet(
            f"color: {COLORS['text_dim']}; background: transparent;"
        )
        layout.addWidget(self.lbl_db)

        # 시그널 연결
        self.slider_vol.valueChanged.connect(self._on_vol)

    def _on_vol(self, val: int) -> None:
        self.lbl_vol.setText(str(val))
        # 0-127 → 대략 -inf..+6 dB 표시
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
    """전체 믹서 뷰: 스크롤 가능한 채널 스트립 + 고정 마스터 스트립."""

    channel_volume_changed = pyqtSignal(int, int)
    channel_pan_changed = pyqtSignal(int, int)
    channel_mute_toggled = pyqtSignal(int)
    channel_solo_toggled = pyqtSignal(int)
    master_volume_changed = pyqtSignal(int)
    channel_strip_effect_toggled = pyqtSignal(int, str, bool)  # track_idx, effect, enabled
    channel_insert_slot_clicked = pyqtSignal(int, int)         # track_idx, slot_idx
    channel_send_level_changed = pyqtSignal(int, int, float)   # track_idx, send_idx, level

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._project: ProjectState | None = None
        self._strips: list[ChannelStrip] = []

        self.setStyleSheet(f"background: {COLORS['bg_darkest']};")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- 스크롤 가능한 채널 영역 -------------------------------------------
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

        # -- 구분선 ---------------------------------------------------------
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(2)
        sep.setStyleSheet(f"background: {COLORS['border']};")
        root.addWidget(sep)

        # -- 마스터 스트립 (항상 표시) ------------------------------------
        self.master_strip = MasterStrip()
        self.master_strip.volume_changed.connect(self.master_volume_changed.emit)
        root.addWidget(self.master_strip)

        # -- VU 감쇠 타이머 ----------------------------------------------------
        self._vu_timer = QTimer(self)
        self._vu_timer.timeout.connect(self._decay_meters)
        self._vu_timer.start(50)

    # -- public API ---------------------------------------------------------

    def set_project(self, project_state: ProjectState) -> None:
        """프로젝트 트랙에서 채널 스트립 재구성."""
        self._project = project_state
        self._clear_strips()

        for i, track in enumerate(project_state.tracks):
            strip = ChannelStrip(i, track)
            strip.volume_changed.connect(self.channel_volume_changed.emit)
            strip.pan_changed.connect(self.channel_pan_changed.emit)
            strip.mute_toggled.connect(self.channel_mute_toggled.emit)
            strip.solo_toggled.connect(self.channel_solo_toggled.emit)
            strip.strip_effect_toggled.connect(self.channel_strip_effect_toggled.emit)
            strip.insert_slot_clicked.connect(self.channel_insert_slot_clicked.emit)
            strip.send_level_changed.connect(self.channel_send_level_changed.emit)
            self._strips.append(strip)
            self._channel_layout.insertWidget(
                self._channel_layout.count() - 1, strip
            )

    def update_meters(self, levels: list[float]) -> None:
        """각 채널의 VU 레벨 설정. *levels*는 트랙당 하나의 float."""
        for i, strip in enumerate(self._strips):
            if i < len(levels):
                strip.vu_meter.set_level(levels[i])
        # 마스터: 전체 평균
        if levels:
            avg = sum(levels) / len(levels)
            self.master_strip.vu_l.set_level(avg * random.uniform(0.9, 1.05))
            self.master_strip.vu_r.set_level(avg * random.uniform(0.9, 1.05))

    def refresh(self) -> None:
        """현재 프로젝트 트랙에서 스트립 컨트롤 다시 동기화."""
        if self._project is None:
            return
        tracks = self._project.tracks
        # 트랙 수 변경 시 재구성
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
