"""
Transport bar widget for the MIDI AI Workstation.

Cubase 15 스타일 트랜스포트 바: 로케이터 디스플레이, 사이클/루프,
펀치 인/아웃, 프리롤, 마커 섹션, 이중 퍼포먼스 미터,
Cubase 블루 액센트, 구분선, 40px 높이.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QDoubleSpinBox,
    QComboBox, QFrame, QToolButton, QSizePolicy, QSpacerItem,
    QVBoxLayout, QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QPainter, QColor, QPaintEvent, QPen

from core.models import ProjectState, NOTE_NAMES, TICKS_PER_BEAT, SCALE_INTERVALS
from config import COLORS, MIN_BPM, MAX_BPM, SNAP_VALUES


# ---------------------------------------------------------------------------
# Constants / Helpers
# ---------------------------------------------------------------------------

_SEP_COLOR = "#2A2A2A"
_BTN_SIZE = 24
_MONO = "Consolas"
_CUBASE_BLUE = "#5B9BD5"          # Cubase 15 블루 액센트
_CUBASE_BLUE_DIM = "#3A6A9A"      # 비활성 블루
_CUBASE_ORANGE = "#E8983A"        # 펀치 인/아웃 오렌지


def _sep() -> QFrame:
    """얇은 수직 구분선."""
    s = QFrame()
    s.setFrameShape(QFrame.Shape.VLine)
    s.setFixedWidth(1)
    s.setStyleSheet(f"background:{_SEP_COLOR}; border:none;")
    return s


class _IconButton(QPushButton):
    """벡터 아이콘을 직접 그리는 트랜스포트 버튼."""

    def __init__(self, icon_name: str, tip: str, size: int = 28,
                 checkable: bool = False, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self.setToolTip(tip)
        self.setCheckable(checkable)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton{background:#2A2A2A;border:1px solid #444;border-radius:4px;}"
            "QPushButton:hover{background:#444;border:1px solid #666;}"
            "QPushButton:checked{background:#C0C0C0;border:1px solid #888;}"
        )

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2

        if self.isChecked():
            color = QColor("#FFF")
        elif self.underMouse():
            color = QColor("#EEE")
        else:
            color = QColor("#CCC")

        if self._icon_name == "play":
            # 삼각형
            if self.isChecked():
                color = QColor("#FFF")
            else:
                color = QColor("#4CAF50")
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            from PyQt6.QtCore import QPointF
            from PyQt6.QtGui import QPolygonF
            s = min(w, h) * 0.3
            poly = QPolygonF([
                QPointF(cx - s * 0.5, cy - s),
                QPointF(cx - s * 0.5, cy + s),
                QPointF(cx + s * 0.8, cy),
            ])
            p.drawPolygon(poly)

        elif self._icon_name == "pause":
            p.setBrush(QColor("#FFF"))
            p.setPen(Qt.PenStyle.NoPen)
            bw = 3
            gap = 3
            bh = min(w, h) * 0.4
            p.drawRect(int(cx - gap - bw), int(cy - bh / 2), bw, int(bh))
            p.drawRect(int(cx + gap), int(cy - bh / 2), bw, int(bh))

        elif self._icon_name == "stop":
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            s = min(w, h) * 0.28
            p.drawRect(int(cx - s), int(cy - s), int(s * 2), int(s * 2))

        elif self._icon_name == "record":
            if self.isChecked():
                color = QColor("#FF4444")
            else:
                color = QColor("#CC6666")
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            r = min(w, h) * 0.28
            from PyQt6.QtCore import QPointF
            p.drawEllipse(QPointF(cx, cy), r, r)

        elif self._icon_name == "rewind":
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            from PyQt6.QtCore import QPointF
            from PyQt6.QtGui import QPolygonF
            s = min(w, h) * 0.22
            # 왼쪽 삼각형
            poly1 = QPolygonF([
                QPointF(cx - s * 0.2, cy - s),
                QPointF(cx - s * 0.2, cy + s),
                QPointF(cx - s * 1.5, cy),
            ])
            p.drawPolygon(poly1)
            # 오른쪽 삼각형
            poly2 = QPolygonF([
                QPointF(cx + s * 1.2, cy - s),
                QPointF(cx + s * 1.2, cy + s),
                QPointF(cx - s * 0.1, cy),
            ])
            p.drawPolygon(poly2)
            # 왼쪽 바
            p.drawRect(int(cx - s * 1.7), int(cy - s), 2, int(s * 2))

        p.end()


def _icon_btn(icon_name: str, tip: str, size: int = _BTN_SIZE,
              checkable: bool = False) -> _IconButton:
    return _IconButton(icon_name, tip, size, checkable)


def _flat_btn(text: str, tip: str, size: int = _BTN_SIZE,
              checkable: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setToolTip(tip)
    btn.setCheckable(checkable)
    btn.setFixedSize(size, size)
    btn.setFont(QFont("Segoe UI Symbol", 12))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton{{background:#2A2A2A;border:1px solid #444;color:#E0E0E0;"
        f"border-radius:4px;font-size:13px;}}"
        f"QPushButton:hover{{color:#FFF;background:#444;border:1px solid #666;}}"
        f"QPushButton:checked{{color:#FFF;background:#C0C0C0;border:1px solid #888;}}"
    )
    return btn


def _display_label(text: str, width: int = 80) -> QLabel:
    """우묵한 모노스페이스 디스플레이 박스 (위치 / 시간)."""
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
# Cubase 15 스타일 토글 버튼 (블루/오렌지 액센트)
# ---------------------------------------------------------------------------

def _cubase_toggle_btn(text: str, tip: str, w: int = 28, h: int = 22,
                       active_color: str = _CUBASE_BLUE,
                       font_size: int = 8) -> QPushButton:
    """Cubase 15 스타일 컬러 토글 버튼."""
    btn = QPushButton(text)
    btn.setToolTip(tip)
    btn.setCheckable(True)
    btn.setFixedSize(w, h)
    btn.setFont(QFont("Segoe UI", font_size, QFont.Weight.Bold))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton{{background:#2A2A2A;border:1px solid #444;color:{COLORS['text_dim']};"
        f"border-radius:3px;}}"
        f"QPushButton:hover{{color:{COLORS['text_primary']};background:#3A3A3A;"
        f"border:1px solid #555;}}"
        f"QPushButton:checked{{background:{active_color};color:#FFF;"
        f"border:1px solid {active_color};}}"
    )
    return btn


# ---------------------------------------------------------------------------
# 로케이터 디스플레이 (클릭하여 편집 가능)
# ---------------------------------------------------------------------------

class _LocatorDisplay(QWidget):
    """Cubase 스타일 로케이터 디스플레이 (L/R). bar.beat.tick 포맷."""

    position_changed = pyqtSignal(str, str)  # label ("L"/"R"), new_text

    def __init__(self, label: str = "L", default_pos: str = "1.1.0",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._label_text = label
        self.setFixedSize(70, 22)
        self.setToolTip(f"{'Left' if label == 'L' else 'Right'} Locator — 클릭하여 편집")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # L/R 라벨
        lbl = QLabel(label)
        lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        lbl.setFixedWidth(12)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_color = _CUBASE_BLUE if label == "L" else "#E07040"
        lbl.setStyleSheet(
            f"color: {label_color}; background: transparent;"
        )
        layout.addWidget(lbl)

        # 위치 표시 / 편집
        self._edit = QLineEdit(default_pos)
        self._edit.setFont(QFont(_MONO, 8, QFont.Weight.Bold))
        self._edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._edit.setFixedHeight(18)
        self._edit.setReadOnly(True)
        self._edit.setStyleSheet(
            f"QLineEdit{{background:{COLORS['bg_darkest']};color:{COLORS['accent_light']};"
            f"border:1px solid {_SEP_COLOR};border-radius:2px;padding:0 2px;}}"
            f"QLineEdit:focus{{border:1px solid {_CUBASE_BLUE};}}"
        )
        self._edit.mousePressEvent = self._on_click
        self._edit.editingFinished.connect(self._on_edited)
        layout.addWidget(self._edit, 1)

    def set_position(self, text: str) -> None:
        self._edit.setText(text)

    def get_position(self) -> str:
        return self._edit.text()

    def _on_click(self, event) -> None:
        self._edit.setReadOnly(False)
        self._edit.selectAll()
        self._edit.setFocus()

    def _on_edited(self) -> None:
        self._edit.setReadOnly(True)
        self.position_changed.emit(self._label_text, self._edit.text())


# ---------------------------------------------------------------------------
# 퍼포먼스 미터 (Audio / MIDI 이중 바)
# ---------------------------------------------------------------------------

class _PerformanceMeter(QWidget):
    """Cubase 15 스타일 이중 퍼포먼스 미터: Audio + MIDI 수평 바."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._audio_value = 0.12
        self._midi_value = 0.05
        self.setFixedSize(60, 32)
        self.setToolTip("Performance: Audio / MIDI")

    def set_audio(self, v: float) -> None:
        self._audio_value = max(0.0, min(v, 1.0))
        self.update()

    def set_midi(self, v: float) -> None:
        self._midi_value = max(0.0, min(v, 1.0))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(self.rect(), QColor(COLORS["bg_darkest"]))

        # "Audio" 라벨 + 바
        p.setPen(QColor(COLORS["text_dim"]))
        p.setFont(QFont("Segoe UI", 6))
        p.drawText(1, 9, "Audio")
        bar_x = 28
        bar_w = w - bar_x - 2
        # Audio 바 배경
        p.fillRect(bar_x, 3, bar_w, 7, QColor(COLORS["bg_mid"]))
        # Audio 바 값
        aw = int(bar_w * self._audio_value)
        if aw > 0:
            ac = _CUBASE_BLUE if self._audio_value < 0.7 else (
                "#FFC107" if self._audio_value < 0.9 else "#F44336")
            p.fillRect(bar_x, 3, aw, 7, QColor(ac))

        # "MIDI" 라벨 + 바
        p.setPen(QColor(COLORS["text_dim"]))
        p.drawText(1, 22, "MIDI")
        # MIDI 바 배경
        p.fillRect(bar_x, 16, bar_w, 7, QColor(COLORS["bg_mid"]))
        # MIDI 바 값
        mw = int(bar_w * self._midi_value)
        if mw > 0:
            mc = "#4CAF50" if self._midi_value < 0.7 else (
                "#FFC107" if self._midi_value < 0.9 else "#F44336")
            p.fillRect(bar_x, 16, mw, 7, QColor(mc))

        # 테두리
        p.setPen(QColor(COLORS["border"]))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, w - 1, h - 1)
        p.end()


# ---------------------------------------------------------------------------
# MIDI activity indicator
# ---------------------------------------------------------------------------

class _MidiIndicator(QWidget):
    """MIDI 액티비티 표시 — 점멸 점."""

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
# TransportWidget — Cubase 15 스타일 트랜스포트 바
# ---------------------------------------------------------------------------

class TransportWidget(QWidget):
    """Cubase 15 스타일 트랜스포트 바 — 40px 높이, 로케이터, 펀치, 마커, 퍼포먼스 미터."""

    # 기존 시그널 유지
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

    # Cubase 15 추가 시그널
    punch_in_toggled = pyqtSignal(bool)
    punch_out_toggled = pyqtSignal(bool)
    preroll_toggled = pyqtSignal(bool)
    left_locator_changed = pyqtSignal(str)
    right_locator_changed = pyqtSignal(str)
    prev_marker_clicked = pyqtSignal()
    next_marker_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._playing = False
        self._recording = False
        self._project: ProjectState | None = None
        self._tap_times: list[float] = []

        # Cubase 15: 40px 높이
        self.setFixedHeight(48)
        self.setStyleSheet(
            f"TransportWidget{{background:#1A1A1A;border-bottom:1px solid #333;}}"
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

        # ── 로케이터 디스플레이 (Cubase 15) ──────────────────────────────
        self.locator_left = _LocatorDisplay("L", "1.1.0")
        self.locator_right = _LocatorDisplay("R", "5.1.0")
        root.addWidget(self.locator_left)
        root.addWidget(self.locator_right)

        root.addWidget(_sep())

        # ── 프리롤 / 펀치 인/아웃 (Cubase 15) ───────────────────────────
        self.btn_preroll = _cubase_toggle_btn(
            "Pre", "Pre-roll", w=30, h=22, active_color=_CUBASE_BLUE, font_size=7
        )
        root.addWidget(self.btn_preroll)

        self.btn_punch_in = _cubase_toggle_btn(
            "I", "Punch In", w=22, h=22, active_color=_CUBASE_ORANGE
        )
        root.addWidget(self.btn_punch_in)

        self.btn_punch_out = _cubase_toggle_btn(
            "O", "Punch Out", w=22, h=22, active_color=_CUBASE_ORANGE
        )
        root.addWidget(self.btn_punch_out)

        root.addWidget(_sep())

        # ── CENTER SPACER ─────────────────────────────────────────────────
        root.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Minimum))

        # ── CENTER: 트랜스포트 컨트롤 ────────────────────────────────────
        self.btn_rewind = _icon_btn("rewind", "Rewind", 30)
        self.btn_play = _icon_btn("play", "Play / Pause", 34, checkable=True)
        self.btn_play.setStyleSheet(
            "QPushButton{background:#2A3A2A;border:2px solid #4CAF50;border-radius:5px;}"
            "QPushButton:hover{background:#3A4A3A;border:2px solid #66FF66;}"
            "QPushButton:checked{background:#4CAF50;border:2px solid #66FF66;}"
        )
        self.btn_stop = _icon_btn("stop", "Stop", 30)
        self.btn_record = _icon_btn("record", "Record", 30, checkable=True)
        self.btn_record.setStyleSheet(
            "QPushButton{background:#2A2A2A;border:1px solid #444;border-radius:4px;}"
            "QPushButton:hover{background:#3A3A3A;border:1px solid #666;}"
            "QPushButton:checked{background:#C44;border:1px solid #F66;}"
        )

        root.addWidget(self.btn_rewind)
        root.addWidget(self.btn_play)
        root.addWidget(self.btn_stop)
        root.addWidget(self.btn_record)

        root.addWidget(_sep())

        # ── 사이클/루프 버튼 (Cubase 블루 액센트) ──────────────────────
        self.btn_loop = _cubase_toggle_btn(
            "LOOP", "Cycle On/Off", w=42, h=24,
            active_color=_CUBASE_BLUE, font_size=7
        )
        root.addWidget(self.btn_loop)

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

        # ── RIGHT: Key / Scale / Snap ─────────────────────────────────────
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

        # ── 마커 섹션 (Cubase 15) ─────────────────────────────────────────
        self.btn_prev_marker = QPushButton("|◄")
        self.btn_prev_marker.setToolTip("Previous Marker")
        self.btn_prev_marker.setFixedSize(24, 22)
        self.btn_prev_marker.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self.btn_prev_marker.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev_marker.setStyleSheet(
            f"QPushButton{{background:#2A2A2A;border:1px solid #444;color:{COLORS['text_secondary']};"
            f"border-radius:3px;}}"
            f"QPushButton:hover{{color:#FFF;background:#444;}}"
        )
        root.addWidget(self.btn_prev_marker)

        self.lbl_marker = QLabel("Marker 1")
        self.lbl_marker.setFont(QFont("Segoe UI", 7))
        self.lbl_marker.setFixedWidth(56)
        self.lbl_marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_marker.setStyleSheet(
            f"color:{COLORS['text_dim']};background:{COLORS['bg_darkest']};"
            f"border:1px solid {_SEP_COLOR};border-radius:2px;padding:0 2px;"
        )
        self.lbl_marker.setToolTip("Current Marker")
        root.addWidget(self.lbl_marker)

        self.btn_next_marker = QPushButton("►|")
        self.btn_next_marker.setToolTip("Next Marker")
        self.btn_next_marker.setFixedSize(24, 22)
        self.btn_next_marker.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self.btn_next_marker.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next_marker.setStyleSheet(
            f"QPushButton{{background:#2A2A2A;border:1px solid #444;color:{COLORS['text_secondary']};"
            f"border-radius:3px;}}"
            f"QPushButton:hover{{color:#FFF;background:#444;}}"
        )
        root.addWidget(self.btn_next_marker)

        root.addWidget(_sep())

        # ── 퍼포먼스 미터 (Audio/MIDI 이중 바) & MIDI 인디케이터 ──────────
        self._perf_meter = _PerformanceMeter()
        self._midi_ind = _MidiIndicator()
        root.addWidget(self._perf_meter)
        root.addWidget(self._midi_ind)

        # ── 시그널 연결 ───────────────────────────────────────────────────
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

        # Cubase 15 추가 시그널 연결
        self.btn_punch_in.toggled.connect(self.punch_in_toggled.emit)
        self.btn_punch_out.toggled.connect(self.punch_out_toggled.emit)
        self.btn_preroll.toggled.connect(self.preroll_toggled.emit)
        self.locator_left.position_changed.connect(
            lambda lbl, txt: self.left_locator_changed.emit(txt))
        self.locator_right.position_changed.connect(
            lambda lbl, txt: self.right_locator_changed.emit(txt))
        self.btn_prev_marker.clicked.connect(self.prev_marker_clicked.emit)
        self.btn_next_marker.clicked.connect(self.next_marker_clicked.emit)

        # 퍼포먼스 미터 애니메이션 타이머
        self._meter_timer = QTimer(self)
        self._meter_timer.timeout.connect(self._tick_cpu)
        self._meter_timer.start(900)

    # ── Internal handlers ─────────────────────────────────────────────────

    def _on_tap(self) -> None:
        import time
        now = time.monotonic()
        self._tap_times.append(now)
        # 마지막 6회 탭만 유지
        self._tap_times = self._tap_times[-6:]
        if len(self._tap_times) >= 2:
            intervals = [self._tap_times[i] - self._tap_times[i - 1]
                         for i in range(1, len(self._tap_times))]
            # 2초 이상 간격 제거
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
        # Audio 퍼포먼스 시뮬레이션
        av = self._perf_meter._audio_value + random.uniform(-0.03, 0.04)
        self._perf_meter.set_audio(max(0.05, min(av, 0.40)))
        # MIDI 퍼포먼스 시뮬레이션
        mv = self._perf_meter._midi_value + random.uniform(-0.02, 0.03)
        self._perf_meter.set_midi(max(0.02, min(mv, 0.25)))

    # ── Public API ────────────────────────────────────────────────────────

    def update_position(self, tick: int, project_state: ProjectState) -> None:
        """위치 (bar.beat.sub) 및 시간 (MM:SS.ms) 디스플레이 업데이트."""
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
        self.btn_play._icon_name = "pause" if playing else "play"
        self.btn_play.update()
        self.btn_play.blockSignals(False)

    def set_recording(self, recording: bool) -> None:
        self._recording = recording
        self.btn_record.blockSignals(True)
        self.btn_record.setChecked(recording)
        self.btn_record.blockSignals(False)

    def set_project(self, project_state: ProjectState) -> None:
        """모든 컨트롤을 프로젝트 상태에 동기화."""
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

    def set_marker_name(self, name: str) -> None:
        """현재 마커 이름 표시 업데이트."""
        self.lbl_marker.setText(name)

    def set_locators(self, left: str, right: str) -> None:
        """로케이터 위치 설정."""
        self.locator_left.set_position(left)
        self.locator_right.set_position(right)

    def flash_midi(self) -> None:
        """MIDI 액티비티 시 인디케이터 점멸."""
        self._midi_ind.blink()
