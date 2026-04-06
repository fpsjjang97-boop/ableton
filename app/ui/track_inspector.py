"""
Cubase 15 스타일 트랙 인스펙터 패널.

좌측 도킹 패널로서 선택된 트랙의 상세 정보를 표시한다.
접이식 섹션 구조: Track, Inserts, Sends, EQ, Quick Controls, Expression Map.
"""
from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QPushButton, QComboBox, QLineEdit, QFrame, QSizePolicy,
    QGridLayout, QSpacerItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QMouseEvent,
    QPaintEvent, QLinearGradient, QConicalGradient,
)

from config import COLORS, INSPECTOR_SECTIONS
from core.models import Track

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
_INSPECTOR_WIDTH = 280
_KNOB_SIZE = 32
_SLOT_HEIGHT = 24
_SECTION_HEADER_HEIGHT = 26
_INSERT_SLOT_COUNT = 8
_SEND_SLOT_COUNT = 4
_QC_COUNT = 8
_EQ_BAND_COUNT = 4


# ===========================================================================
# InspectorKnob — 원형 노브 위젯
# ===========================================================================

class InspectorKnob(QWidget):
    """Cubase 스타일 원형 노브 위젯 (32x32).

    QPainter로 아크를 그려 값을 시각화하며, 드래그로 값 조절 가능.
    """

    valueChanged = pyqtSignal(float)

    def __init__(
        self,
        label: str = "",
        min_val: float = 0.0,
        max_val: float = 1.0,
        default: float = 0.5,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self._min = min_val
        self._max = max_val
        self._value = default
        self._default = default
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_val = 0.0

        self.setFixedSize(_KNOB_SIZE, _KNOB_SIZE + 14)
        self.setToolTip(f"{label}: {default:.2f}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # --- 프로퍼티 ---

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        v = max(self._min, min(self._max, v))
        if v != self._value:
            self._value = v
            self.setToolTip(f"{self._label}: {v:.2f}")
            self.valueChanged.emit(v)
            self.update()

    # --- 페인트 ---

    def paintEvent(self, event: QPaintEvent) -> None:
        """노브 아크와 레이블을 그린다."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = _KNOB_SIZE / 2
        cy = _KNOB_SIZE / 2
        radius = (_KNOB_SIZE - 6) / 2

        # 배경 원
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(COLORS["bg_widget"]))
        p.drawEllipse(QPointF(cx, cy), radius, radius)

        # 트랙 아크 (어두운 배경)
        arc_rect = QRectF(3, 3, _KNOB_SIZE - 6, _KNOB_SIZE - 6)
        pen_bg = QPen(QColor(COLORS["border"]), 2.5)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen_bg)
        # 아크: 225도에서 시작, -270도 스팬 (시계 방향)
        p.drawArc(arc_rect, 225 * 16, -270 * 16)

        # 값 아크 (액센트 컬러)
        norm = (self._value - self._min) / max(self._max - self._min, 0.001)
        span_deg = -270 * norm
        pen_val = QPen(QColor(COLORS["inspector_knob_arc"]), 2.5)
        pen_val.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen_val)
        p.drawArc(arc_rect, 225 * 16, int(span_deg * 16))

        # 중앙 도트
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(COLORS["text_primary"]))
        dot_angle = math.radians(225 - 270 * norm)
        dot_r = radius - 1
        dx = cx + dot_r * math.cos(dot_angle)
        dy = cy - dot_r * math.sin(dot_angle)
        p.drawEllipse(QPointF(dx, dy), 2, 2)

        # 레이블 텍스트
        p.setPen(QColor(COLORS["inspector_label"]))
        font = QFont("Segoe UI", 7)
        p.setFont(font)
        label_rect = QRectF(0, _KNOB_SIZE + 1, _KNOB_SIZE, 12)
        p.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self._label)

        p.end()

    # --- 마우스 이벤트 ---

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_y = event.globalPosition().y()
            self._drag_start_val = self._value
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.value = self._default

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            dy = self._drag_start_y - event.globalPosition().y()
            sensitivity = (self._max - self._min) / 120.0
            self.value = self._drag_start_val + dy * sensitivity

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """더블클릭 시 기본값 복원."""
        self.value = self._default


# ===========================================================================
# CollapsibleSection — 접이식 섹션
# ===========================================================================

class CollapsibleSection(QWidget):
    """Cubase 스타일 접이식 섹션 헤더 + 컨텐츠 영역.

    삼각형 아이콘과 제목 텍스트가 있는 헤더를 클릭하면
    컨텐츠가 접히거나 펼쳐진다.
    """

    toggled = pyqtSignal(bool)

    def __init__(
        self,
        title: str,
        parent: Optional[QWidget] = None,
        expanded: bool = True,
    ) -> None:
        super().__init__(parent)
        self._expanded = expanded
        self._title = title

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 헤더 바
        self._header = QPushButton()
        self._header.setFixedHeight(_SECTION_HEADER_HEIGHT)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.clicked.connect(self._toggle)
        self._update_header_text()
        self._header.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['inspector_section_bg']};
                border: none;
                border-bottom: 1px solid {COLORS['inspector_section_border']};
                color: {COLORS['text_primary']};
                font: bold 10px 'Segoe UI';
                text-align: left;
                padding-left: 8px;
            }}
            QPushButton:hover {{
                background: {COLORS['bg_hover']};
            }}
        """)
        layout.addWidget(self._header)

        # 컨텐츠 컨테이너
        self._content = QWidget()
        self._content.setVisible(self._expanded)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(6, 4, 6, 4)
        self._content_layout.setSpacing(3)
        layout.addWidget(self._content)

    @property
    def content_layout(self) -> QVBoxLayout:
        """섹션 내부 레이아웃 반환."""
        return self._content_layout

    def add_widget(self, w: QWidget) -> None:
        """컨텐츠 영역에 위젯 추가."""
        self._content_layout.addWidget(w)

    def _toggle(self) -> None:
        """접이식 토글."""
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._update_header_text()
        self.toggled.emit(self._expanded)

    def _update_header_text(self) -> None:
        arrow = "\u25BC" if self._expanded else "\u25B6"
        self._header.setText(f"  {arrow}  {self._title}")

    def set_expanded(self, expanded: bool) -> None:
        """프로그래밍 방식으로 섹션 접기/펼치기."""
        if expanded != self._expanded:
            self._toggle()


# ===========================================================================
# InsertSlot — 이펙트 삽입 슬롯
# ===========================================================================

class InsertSlot(QWidget):
    """Cubase 스타일 인서트 이펙트 슬롯.

    빈 슬롯은 '+' 버튼 표시, 할당된 슬롯은 이펙트 이름 표시.
    """

    clicked = pyqtSignal(int)

    def __init__(self, index: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._index = index
        self._effect_name: Optional[str] = None
        self._hovered = False

        self.setFixedHeight(_SLOT_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def set_effect(self, name: Optional[str]) -> None:
        """이펙트 이름 설정 (None이면 빈 슬롯)."""
        self._effect_name = name
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        bg = COLORS["bg_hover"] if self._hovered else COLORS["bg_widget"]
        p.fillRect(0, 0, w, h, QColor(bg))

        # 좌측 액센트 바 (이펙트 할당 시)
        if self._effect_name:
            p.fillRect(0, 2, 3, h - 4, QColor(COLORS["accent"]))

        # 테두리
        p.setPen(QColor(COLORS["inspector_section_border"]))
        p.drawRect(0, 0, w - 1, h - 1)

        # 텍스트
        font = QFont("Segoe UI", 8)
        p.setFont(font)

        if self._effect_name:
            p.setPen(QColor(COLORS["text_primary"]))
            p.drawText(QRectF(8, 0, w - 16, h), Qt.AlignmentFlag.AlignVCenter, self._effect_name)
        else:
            p.setPen(QColor(COLORS["text_dim"]))
            p.drawText(
                QRectF(0, 0, w, h),
                Qt.AlignmentFlag.AlignCenter,
                f"+ Insert {self._index + 1}",
            )

        p.end()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)


# ===========================================================================
# EQBandWidget — 간이 4밴드 EQ 시각화
# ===========================================================================

class EQBandWidget(QWidget):
    """4밴드 EQ 커브를 QPainter로 시각화하는 위젯."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # 각 밴드: (freq_norm 0-1, gain_db -12..+12, Q)
        self._bands = [
            (0.1, 0.0, 0.7),
            (0.3, 0.0, 1.0),
            (0.6, 0.0, 1.0),
            (0.9, 0.0, 0.7),
        ]

    def set_band(self, idx: int, freq: float, gain: float, q: float) -> None:
        """밴드 파라미터 설정."""
        if 0 <= idx < _EQ_BAND_COUNT:
            self._bands[idx] = (freq, gain, q)
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # 배경
        p.fillRect(0, 0, w, h, QColor(COLORS["bg_widget"]))

        # 그리드 라인
        p.setPen(QPen(QColor(COLORS["grid_line"]), 1))
        mid_y = h / 2
        p.drawLine(0, int(mid_y), w, int(mid_y))
        for i in range(1, 4):
            x = int(w * i / 4)
            p.drawLine(x, 0, x, h)

        # EQ 커브
        pen = QPen(QColor(COLORS["accent"]), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)

        points = []
        for px in range(w):
            x_norm = px / max(w - 1, 1)
            y_val = 0.0
            for freq, gain, q in self._bands:
                dist = abs(x_norm - freq)
                influence = math.exp(-(dist * dist) / (0.02 * q * q + 0.005))
                y_val += gain * influence
            # gain -> y coordinate
            y_px = mid_y - (y_val / 12.0) * (h / 2 - 4)
            points.append(QPointF(px, y_px))

        for i in range(len(points) - 1):
            p.drawLine(points[i], points[i + 1])

        # 밴드 도트
        for freq, gain, q in self._bands:
            bx = freq * (w - 1)
            by = mid_y - (gain / 12.0) * (h / 2 - 4)
            p.setBrush(QColor(COLORS["accent_light"]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(bx, by), 4, 4)

        # 테두리
        p.setPen(QColor(COLORS["inspector_section_border"]))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, w - 1, h - 1)

        p.end()


# ===========================================================================
# TrackInspectorPanel — 메인 인스펙터 패널
# ===========================================================================

class TrackInspectorPanel(QWidget):
    """Cubase 15 스타일 좌측 트랙 인스펙터 패널.

    선택된 트랙의 상세 정보를 접이식 섹션 구조로 표시한다.
    QDockWidget 내부에 배치하여 사용한다.
    """

    # 시그널: 트랙 파라미터 변경 시 외부에 알림
    track_param_changed = pyqtSignal(str, object)

    # Signals for engine communication
    volume_changed = pyqtSignal(int)          # 0-127
    pan_changed = pyqtSignal(int)             # 0-127
    program_changed = pyqtSignal(int)         # GM program number
    mute_toggled = pyqtSignal(bool)
    solo_toggled = pyqtSignal(bool)
    record_toggled = pyqtSignal(bool)
    insert_clicked = pyqtSignal(int)          # slot index
    insert_bypass_toggled = pyqtSignal(int, bool)  # slot index, bypassed
    send_level_changed = pyqtSignal(int, float)    # send index, level 0-1
    send_pan_changed = pyqtSignal(int, float)      # send index, pan 0-1
    eq_band_changed = pyqtSignal(int, float, float)  # band, freq, gain
    quick_control_changed = pyqtSignal(int, float)    # qc index, value 0-1
    expression_map_changed = pyqtSignal(str)          # map name
    articulation_changed = pyqtSignal(str)            # articulation name

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._track_name = "MIDI 01"
        self._track_color = COLORS["track_blue"]
        self._channel = 1
        self._current_track_index: int = -1

        self.setFixedWidth(_INSPECTOR_WIDTH)
        self.setStyleSheet(f"background: {COLORS['bg_inspector']};")

        self._build_ui()

    # -----------------------------------------------------------------
    # UI 구성
    # -----------------------------------------------------------------

    def _build_ui(self) -> None:
        """인스펙터 패널 전체 UI를 구성한다."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {COLORS['bg_inspector']};
                border: none;
            }}
            QScrollBar:vertical {{
                background: {COLORS['scrollbar_bg']};
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['scrollbar_handle']};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        container = QWidget()
        container.setStyleSheet(f"background: {COLORS['bg_inspector']};")
        self._main_layout = QVBoxLayout(container)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # 각 섹션 생성
        self._build_track_section()
        self._build_inserts_section()
        self._build_sends_section()
        self._build_eq_section()
        self._build_quick_controls_section()
        self._build_expression_map_section()

        # 하단 여백
        self._main_layout.addStretch(1)

        scroll.setWidget(container)
        outer.addWidget(scroll)

    # -----------------------------------------------------------------
    # Track 섹션
    # -----------------------------------------------------------------

    def _build_track_section(self) -> None:
        """트랙 기본 정보 섹션: 이름, 색상, 채널, 볼륨/팬."""
        section = CollapsibleSection("Track", expanded=True)

        # 트랙 이름 입력
        name_row = QHBoxLayout()
        name_row.setSpacing(4)

        self._color_indicator = QFrame()
        self._color_indicator.setFixedSize(14, 14)
        self._color_indicator.setStyleSheet(
            f"background: {self._track_color}; border-radius: 3px;"
        )
        name_row.addWidget(self._color_indicator)

        self._name_edit = QLineEdit(self._track_name)
        self._name_edit.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_input']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 2px;
                padding: 2px 4px;
                font: bold 10px 'Segoe UI';
            }}
            QLineEdit:focus {{
                border-color: {COLORS['border_focus']};
            }}
        """)
        self._name_edit.editingFinished.connect(
            lambda: self.track_param_changed.emit("name", self._name_edit.text())
        )
        name_row.addWidget(self._name_edit)

        name_widget = QWidget()
        name_widget.setLayout(name_row)
        section.add_widget(name_widget)

        # 채널 / 프로그램 행
        ch_row = QHBoxLayout()
        ch_row.setSpacing(4)

        ch_label = QLabel("Ch")
        ch_label.setStyleSheet(f"color: {COLORS['inspector_label']}; font: 9px 'Segoe UI';")
        ch_row.addWidget(ch_label)

        self._ch_combo = QComboBox()
        self._ch_combo.addItems([str(i) for i in range(1, 17)])
        self._ch_combo.setCurrentIndex(0)
        self._ch_combo.setFixedWidth(50)
        self._ch_combo.setStyleSheet(self._combo_style())
        ch_row.addWidget(self._ch_combo)

        prg_label = QLabel("Prg")
        prg_label.setStyleSheet(f"color: {COLORS['inspector_label']}; font: 9px 'Segoe UI';")
        ch_row.addWidget(prg_label)

        self._prg_combo = QComboBox()
        self._prg_combo.addItems([f"{i}: Patch" for i in range(1, 129)])
        self._prg_combo.setCurrentIndex(0)
        self._prg_combo.setStyleSheet(self._combo_style())
        ch_row.addWidget(self._prg_combo, 1)

        ch_widget = QWidget()
        ch_widget.setLayout(ch_row)
        section.add_widget(ch_widget)

        # 볼륨 / 팬 노브
        knob_row = QHBoxLayout()
        knob_row.setSpacing(12)
        knob_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._vol_knob = InspectorKnob("Vol", 0.0, 1.0, 0.8)
        self._pan_knob = InspectorKnob("Pan", -1.0, 1.0, 0.0)

        knob_row.addWidget(self._vol_knob)
        knob_row.addWidget(self._pan_knob)

        knob_widget = QWidget()
        knob_widget.setLayout(knob_row)
        section.add_widget(knob_widget)

        # 뮤트/솔로/녹음 버튼
        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)

        self._btn_mute = QPushButton("M")
        self._btn_solo = QPushButton("S")
        self._btn_record = QPushButton("R")

        for btn, color, tooltip in [
            (self._btn_mute, COLORS["accent_yellow"], "Mute"),
            (self._btn_solo, COLORS["accent_green"], "Solo"),
            (self._btn_record, COLORS["accent_red"], "Record Arm"),
        ]:
            btn.setFixedSize(36, 20)
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['bg_widget']};
                    color: {COLORS['text_dim']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 2px;
                    font: bold 9px 'Segoe UI';
                }}
                QPushButton:checked {{
                    background: {color};
                    color: {COLORS['bg_darkest']};
                }}
                QPushButton:hover {{
                    border-color: {color};
                }}
            """)
            btn_row.addWidget(btn)

        self._btn_mute.toggled.connect(self.mute_toggled.emit)
        self._btn_solo.toggled.connect(self.solo_toggled.emit)
        self._btn_record.toggled.connect(self.record_toggled.emit)

        btn_row.addStretch()
        btn_widget = QWidget()
        btn_widget.setLayout(btn_row)
        section.add_widget(btn_widget)

        # Wire knobs/combos to engine signals
        self._vol_knob.valueChanged.connect(
            lambda v: self.volume_changed.emit(int(v * 127))
        )
        self._pan_knob.valueChanged.connect(
            lambda v: self.pan_changed.emit(int((v + 1.0) / 2.0 * 127))
        )
        self._prg_combo.currentIndexChanged.connect(
            lambda idx: self.program_changed.emit(idx)
        )

        self._main_layout.addWidget(section)

    # -----------------------------------------------------------------
    # Inserts 섹션
    # -----------------------------------------------------------------

    def _build_inserts_section(self) -> None:
        """8개의 인서트 이펙트 슬롯 섹션."""
        section = CollapsibleSection("Inserts", expanded=True)

        self._insert_slots: list[InsertSlot] = []
        for i in range(_INSERT_SLOT_COUNT):
            slot = InsertSlot(i)
            slot.clicked.connect(self._on_insert_clicked)
            self._insert_slots.append(slot)
            section.add_widget(slot)

        # 바이패스 전체 버튼
        bypass_btn = QPushButton("Bypass All")
        bypass_btn.setFixedHeight(20)
        bypass_btn.setCheckable(True)
        bypass_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_widget']};
                color: {COLORS['text_dim']};
                border: 1px solid {COLORS['border']};
                border-radius: 2px;
                font: 8px 'Segoe UI';
            }}
            QPushButton:checked {{
                background: {COLORS['accent_orange']};
                color: {COLORS['bg_darkest']};
            }}
        """)
        section.add_widget(bypass_btn)

        self._main_layout.addWidget(section)

    # -----------------------------------------------------------------
    # Sends 섹션
    # -----------------------------------------------------------------

    def _build_sends_section(self) -> None:
        """4개의 센드 슬롯 + 레벨/팬 노브 섹션."""
        section = CollapsibleSection("Sends", expanded=False)

        self._send_knobs: list[tuple[InspectorKnob, InspectorKnob]] = []

        for i in range(_SEND_SLOT_COUNT):
            row = QHBoxLayout()
            row.setSpacing(4)

            # 센드 대상 콤보
            combo = QComboBox()
            combo.addItem(f"-- Send {i + 1} --")
            combo.addItems(["FX 1 - Reverb", "FX 2 - Delay", "FX 3 - Chorus", "FX 4 - Comp"])
            combo.setStyleSheet(self._combo_style())
            combo.setFixedHeight(20)
            row.addWidget(combo, 1)

            # 레벨 & 팬 노브
            lvl = InspectorKnob("Lvl", 0.0, 1.0, 0.0)
            pan = InspectorKnob("Pan", -1.0, 1.0, 0.0)
            lvl.valueChanged.connect(
                lambda val, si=i: self.send_level_changed.emit(si, val)
            )
            pan.valueChanged.connect(
                lambda val, si=i: self.send_pan_changed.emit(si, val)
            )
            row.addWidget(lvl)
            row.addWidget(pan)
            self._send_knobs.append((lvl, pan))

            row_widget = QWidget()
            row_widget.setLayout(row)
            section.add_widget(row_widget)

        self._main_layout.addWidget(section)

    # -----------------------------------------------------------------
    # EQ 섹션
    # -----------------------------------------------------------------

    def _build_eq_section(self) -> None:
        """4밴드 EQ 시각화 섹션."""
        section = CollapsibleSection("EQ", expanded=False)

        self._eq_widget = EQBandWidget()
        section.add_widget(self._eq_widget)

        # EQ 밴드 노브: Freq / Gain 각 밴드별
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(0, 4, 0, 0)

        band_names = ["LF", "LMF", "HMF", "HF"]
        self._eq_knobs: list[tuple[InspectorKnob, InspectorKnob]] = []

        for i, name in enumerate(band_names):
            freq_knob = InspectorKnob(f"{name} F", 0.0, 1.0, [0.1, 0.3, 0.6, 0.9][i])
            gain_knob = InspectorKnob(f"{name} G", -12.0, 12.0, 0.0)
            gain_knob.valueChanged.connect(
                lambda val, idx=i: self._on_eq_gain_changed(idx, val)
            )
            grid.addWidget(freq_knob, 0, i, Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(gain_knob, 1, i, Qt.AlignmentFlag.AlignCenter)
            self._eq_knobs.append((freq_knob, gain_knob))

        grid_widget = QWidget()
        grid_widget.setLayout(grid)
        section.add_widget(grid_widget)

        self._main_layout.addWidget(section)

    # -----------------------------------------------------------------
    # Quick Controls 섹션
    # -----------------------------------------------------------------

    def _build_quick_controls_section(self) -> None:
        """8개의 퀵 컨트롤 노브 섹션."""
        section = CollapsibleSection("Quick Controls", expanded=False)

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(4, 4, 4, 4)

        self._qc_knobs: list[InspectorKnob] = []
        for i in range(_QC_COUNT):
            knob = InspectorKnob(f"QC {i + 1}", 0.0, 1.0, 0.5)
            knob.valueChanged.connect(
                lambda val, qi=i: self.quick_control_changed.emit(qi, val)
            )
            row = i // 4
            col = i % 4
            grid.addWidget(knob, row, col, Qt.AlignmentFlag.AlignCenter)
            self._qc_knobs.append(knob)

        grid_widget = QWidget()
        grid_widget.setLayout(grid)
        section.add_widget(grid_widget)

        # 학습 모드 버튼
        learn_btn = QPushButton("MIDI Learn")
        learn_btn.setFixedHeight(22)
        learn_btn.setCheckable(True)
        learn_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_widget']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 2px;
                font: 9px 'Segoe UI';
            }}
            QPushButton:checked {{
                background: {COLORS['accent']};
                color: {COLORS['text_accent']};
            }}
        """)
        section.add_widget(learn_btn)

        self._main_layout.addWidget(section)

    # -----------------------------------------------------------------
    # Expression Map 섹션
    # -----------------------------------------------------------------

    def _build_expression_map_section(self) -> None:
        """익스프레션 맵 선택 및 현재 아티큘레이션 표시 섹션."""
        section = CollapsibleSection("Expression Map", expanded=False)

        # 맵 선택 콤보
        map_label = QLabel("Map:")
        map_label.setStyleSheet(
            f"color: {COLORS['inspector_label']}; font: 9px 'Segoe UI';"
        )
        section.add_widget(map_label)

        self._expr_combo = QComboBox()
        self._expr_combo.addItems([
            "-- None --",
            "HSO - Strings",
            "HSO - Brass",
            "HSO - Woodwinds",
            "HSO - Percussion",
            "NotePerformer",
            "BBCSO - Violins",
            "CSS - Legato",
        ])
        self._expr_combo.setStyleSheet(self._combo_style())
        self._expr_combo.currentTextChanged.connect(self.expression_map_changed.emit)
        section.add_widget(self._expr_combo)

        # 현재 아티큘레이션 표시
        art_label = QLabel("Articulation:")
        art_label.setStyleSheet(
            f"color: {COLORS['inspector_label']}; font: 9px 'Segoe UI'; margin-top: 4px;"
        )
        section.add_widget(art_label)

        self._art_display = QLabel("Natural")
        self._art_display.setFixedHeight(22)
        self._art_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._art_display.setStyleSheet(f"""
            QLabel {{
                background: {COLORS['bg_widget']};
                color: {COLORS['accent_light']};
                border: 1px solid {COLORS['accent_dim']};
                border-radius: 2px;
                font: bold 10px 'Segoe UI';
            }}
        """)
        section.add_widget(self._art_display)

        # 아티큘레이션 버튼 그리드
        art_grid = QGridLayout()
        art_grid.setSpacing(2)
        art_grid.setContentsMargins(0, 4, 0, 0)

        articulations = [
            "Natural", "Legato", "Staccato", "Pizzicato",
            "Tremolo", "Trill", "Marcato", "Spiccato",
        ]
        for i, art_name in enumerate(articulations):
            btn = QPushButton(art_name)
            btn.setFixedHeight(20)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['bg_widget']};
                    color: {COLORS['text_secondary']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 2px;
                    font: 8px 'Segoe UI';
                    padding: 0 2px;
                }}
                QPushButton:hover {{
                    background: {COLORS['bg_hover']};
                    border-color: {COLORS['accent_dim']};
                }}
                QPushButton:pressed {{
                    background: {COLORS['accent']};
                    color: {COLORS['text_accent']};
                }}
            """)
            btn.clicked.connect(lambda checked, n=art_name: self._set_articulation(n))
            art_grid.addWidget(btn, i // 2, i % 2)

        art_grid_widget = QWidget()
        art_grid_widget.setLayout(art_grid)
        section.add_widget(art_grid_widget)

        self._main_layout.addWidget(section)

    # -----------------------------------------------------------------
    # 공개 API
    # -----------------------------------------------------------------

    def set_track_info(
        self,
        name: str,
        color: str = "",
        channel: int = 1,
    ) -> None:
        """외부에서 선택된 트랙 정보를 업데이트한다."""
        self._track_name = name
        self._name_edit.setText(name)

        if color:
            self._track_color = color
            self._color_indicator.setStyleSheet(
                f"background: {color}; border-radius: 3px;"
            )

        self._channel = channel
        self._ch_combo.setCurrentIndex(max(0, min(15, channel - 1)))

    def set_volume(self, val: float) -> None:
        """볼륨 노브 값 설정."""
        self._vol_knob.value = val

    def set_pan(self, val: float) -> None:
        """팬 노브 값 설정."""
        self._pan_knob.value = val

    def set_track(self, track: Track, index: int) -> None:
        """Update the inspector display from a Track object.

        Blocks signals on widgets while setting values to prevent
        feedback loops back to the engine.
        """
        self._current_track_index = index

        # Track name and color
        self._track_name = track.name
        self._name_edit.blockSignals(True)
        self._name_edit.setText(track.name)
        self._name_edit.blockSignals(False)

        self._track_color = track.color
        self._color_indicator.setStyleSheet(
            f"background: {track.color}; border-radius: 3px;"
        )

        # Channel
        self._channel = track.channel
        self._ch_combo.blockSignals(True)
        self._ch_combo.setCurrentIndex(max(0, min(15, track.channel)))
        self._ch_combo.blockSignals(False)

        # Program (instrument)
        self._prg_combo.blockSignals(True)
        self._prg_combo.setCurrentIndex(max(0, min(127, track.instrument)))
        self._prg_combo.blockSignals(False)

        # Volume: Track stores 0-127, knob expects 0.0-1.0
        self._vol_knob.blockSignals(True)
        self._vol_knob.value = track.volume / 127.0
        self._vol_knob.blockSignals(False)

        # Pan: Track stores 0-127 (64=center), knob expects -1.0 to 1.0
        self._pan_knob.blockSignals(True)
        self._pan_knob.value = (track.pan - 64) / 64.0
        self._pan_knob.blockSignals(False)

        # Mute / Solo
        self._btn_mute.blockSignals(True)
        self._btn_mute.setChecked(track.muted)
        self._btn_mute.blockSignals(False)

        self._btn_solo.blockSignals(True)
        self._btn_solo.setChecked(track.solo)
        self._btn_solo.blockSignals(False)

        self._btn_record.blockSignals(True)
        self._btn_record.setChecked(False)
        self._btn_record.blockSignals(False)

    # -----------------------------------------------------------------
    # 내부 슬롯
    # -----------------------------------------------------------------

    def _on_insert_clicked(self, idx: int) -> None:
        """인서트 슬롯 클릭 핸들러 (향후 플러그인 선택 다이얼로그 연동)."""
        self.track_param_changed.emit("insert_click", idx)
        self.insert_clicked.emit(idx)

    def _on_eq_gain_changed(self, band_idx: int, gain: float) -> None:
        """EQ 게인 변경 시 시각화 업데이트 + 시그널 발신."""
        freq_knob, _ = self._eq_knobs[band_idx]
        freq = freq_knob.value
        bands = list(self._eq_widget._bands)
        bands[band_idx] = (freq, gain, bands[band_idx][2])
        self._eq_widget._bands = bands
        self._eq_widget.update()
        self.eq_band_changed.emit(band_idx, freq, gain)

    def _set_articulation(self, name: str) -> None:
        """아티큘레이션 선택 핸들러."""
        self._art_display.setText(name)
        self.track_param_changed.emit("articulation", name)
        self.articulation_changed.emit(name)

    # -----------------------------------------------------------------
    # 유틸리티
    # -----------------------------------------------------------------

    @staticmethod
    def _combo_style() -> str:
        """Cubase 스타일 콤보박스 스타일시트 반환."""
        return f"""
            QComboBox {{
                background: {COLORS['bg_input']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 2px;
                padding: 1px 4px;
                font: 9px 'Segoe UI';
            }}
            QComboBox:hover {{
                border-color: {COLORS['accent_dim']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 14px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {COLORS['text_secondary']};
                margin-right: 4px;
            }}
            QComboBox QAbstractItemView {{
                background: {COLORS['bg_panel']};
                color: {COLORS['text_primary']};
                selection-background-color: {COLORS['bg_selected']};
                border: 1px solid {COLORS['border']};
                outline: none;
            }}
        """
