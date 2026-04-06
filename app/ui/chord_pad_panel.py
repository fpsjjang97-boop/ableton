"""
Cubase 15 스타일 코드 패드 패널.

16개 코드 패드(4x4 그리드)를 표시하며, 페이지 전환으로 총 64패드를 지원합니다.
키/스케일 기반 자동 채우기, 보이싱 선택, 미니 피아노 시각화,
아르페지오/스트럼 컨트롤을 포함합니다.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QSlider, QFrame, QMenu,
    QSizePolicy, QCheckBox, QSpinBox, QToolButton, QGroupBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QAction

from config import COLORS

from midigpt.cubase_data.chord_voicings import (
    CHORD_INTERVALS, build_chord_pad_set, get_voicing, voice_lead,
    ChordPadEntry,
)


# ─── 상수 ───

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SCALE_TYPES = [
    "major", "minor", "dorian", "phrygian", "lydian",
    "mixolydian", "locrian", "harmonic_minor", "melodic_minor",
]

VOICING_TYPES = ["close", "open", "drop2", "drop3", "guitar", "quartal"]

# 코드 기능별 색상 (토닉=파랑, 도미넌트=빨강, 서브도미넌트=초록 등)
_FUNCTION_COLORS = {
    "tonic":       "#3A6EA5",
    "supertonic":  "#5B8C5A",
    "mediant":     "#8B6CAE",
    "subdominant": "#4A9F6E",
    "dominant":    "#B85450",
    "submediant":  "#7A6B4F",
    "leading":     "#9E6B3A",
    "default":     "#555555",
}

# 메이저 스케일 디그리별 기능 매핑 (0-indexed)
_DEGREE_FUNCTION = [
    "tonic", "supertonic", "mediant", "subdominant",
    "dominant", "submediant", "leading", "tonic",
]


# ─── 스타일 ───

_PAD_BASE_STYLE = f"""
    QPushButton {{
        background: {COLORS['bg_mid']};
        color: {COLORS['text_primary']};
        border: 2px solid {COLORS['border']};
        border-radius: 6px;
        font-size: 13px;
        font-weight: bold;
        padding: 6px;
    }}
    QPushButton:hover {{
        background: {COLORS['bg_hover']};
        border-color: {COLORS['accent_secondary']};
    }}
    QPushButton:pressed {{
        background: {COLORS['bg_selected']};
    }}
"""

_PAD_SELECTED_BORDER = f"border: 2px solid {COLORS['accent']};"

_CTRL_STYLE = f"""
    QComboBox, QSpinBox {{
        background: {COLORS['bg_input']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 3px;
        padding: 2px 6px;
        font-size: 11px;
        min-height: 22px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 16px;
    }}
    QComboBox QAbstractItemView {{
        background: {COLORS['bg_mid']};
        color: {COLORS['text_primary']};
        selection-background-color: {COLORS['bg_selected']};
    }}
    QLabel {{
        color: {COLORS['text_secondary']};
        font-size: 10px;
    }}
    QPushButton {{
        background: {COLORS['bg_mid']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 3px;
        padding: 3px 10px;
        font-size: 11px;
    }}
    QPushButton:hover {{
        background: {COLORS['bg_hover']};
    }}
    QCheckBox {{
        color: {COLORS['text_secondary']};
        font-size: 11px;
    }}
    QSlider::groove:horizontal {{
        background: {COLORS['bg_input']};
        height: 4px;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {COLORS['accent']};
        width: 12px;
        height: 12px;
        margin: -4px 0;
        border-radius: 6px;
    }}
"""

_PANEL_BG = f"background: {COLORS['bg_dark']};"


# ─── 미니 피아노 위젯 ───

class MiniPianoWidget(QWidget):
    """코드 보이싱을 미니 피아노 건반 위에 시각화하는 위젯."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notes: list[int] = []
        self._prev_notes: list[int] = []
        self.setFixedHeight(80)
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_notes(self, notes: list[int], prev_notes: list[int] | None = None):
        """표시할 노트 설정."""
        self._prev_notes = prev_notes or []
        self._notes = notes
        self.update()

    def paintEvent(self, event):
        """미니 피아노 건반 및 활성 노트 그리기."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 배경
        p.fillRect(0, 0, w, h, QColor(COLORS['bg_panel']))

        if not self._notes:
            p.setPen(QColor(COLORS['text_dim']))
            p.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, "코드를 선택하세요")
            p.end()
            return

        # 2옥타브 범위 결정 (노트 중심)
        if self._notes:
            center = sum(self._notes) // len(self._notes)
        else:
            center = 60
        start_note = max(21, center - 12)
        end_note = min(108, start_note + 25)
        num_white = sum(1 for n in range(start_note, end_note)
                        if n % 12 not in (1, 3, 6, 8, 10))

        if num_white == 0:
            p.end()
            return

        white_w = w / num_white
        black_w = white_w * 0.6
        black_h = h * 0.6

        # 흰 건반 그리기
        wx = 0
        white_positions: dict[int, float] = {}
        for n in range(start_note, end_note):
            if n % 12 not in (1, 3, 6, 8, 10):
                is_active = n in self._notes
                color = QColor("#E8E8E8") if not is_active else QColor(_FUNCTION_COLORS["tonic"])
                p.fillRect(int(wx), 0, int(white_w) - 1, h, color)
                p.setPen(QPen(QColor(COLORS['border']), 1))
                p.drawRect(int(wx), 0, int(white_w) - 1, h)
                white_positions[n] = wx
                wx += white_w

        # 검은 건반 그리기
        wx = 0
        for n in range(start_note, end_note):
            if n % 12 not in (1, 3, 6, 8, 10):
                wx += white_w
            else:
                is_active = n in self._notes
                bx = wx - black_w / 2 - white_w
                color = QColor("#222222") if not is_active else QColor(_FUNCTION_COLORS["dominant"])
                p.fillRect(int(bx), 0, int(black_w), int(black_h), color)

        # 보이스 리딩 화살표 (이전 노트 → 현재 노트)
        if self._prev_notes and len(self._prev_notes) == len(self._notes):
            p.setPen(QPen(QColor(COLORS['accent_light']), 1, Qt.PenStyle.DashLine))
            for pn, cn in zip(self._prev_notes, self._notes):
                diff = cn - pn
                if diff != 0:
                    arrow = "↑" if diff > 0 else "↓"
                    # 노트 위치에 화살표 표시
                    if cn in white_positions:
                        ax = white_positions[cn] + white_w / 2
                        p.drawText(int(ax) - 4, h - 4, arrow)

        p.end()


# ─── 코드 패드 버튼 ───

class ChordPadButton(QPushButton):
    """개별 코드 패드 버튼."""

    right_clicked = pyqtSignal(int)  # 패드 인덱스

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self._index = index
        self._entry: Optional[ChordPadEntry] = None
        self._function_color = _FUNCTION_COLORS["default"]
        self._is_selected = False

        self.setFixedSize(QSize(90, 64))
        self.setStyleSheet(_PAD_BASE_STYLE)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_chord(self, entry: Optional[ChordPadEntry], func_index: int = 0):
        """코드 패드 데이터를 설정."""
        self._entry = entry
        if entry is None:
            self.setText("")
            self._function_color = _FUNCTION_COLORS["default"]
        else:
            root_name = NOTE_NAMES[entry.root % 12]
            self.setText(f"{root_name}{entry.quality}")
            func_key = _DEGREE_FUNCTION[func_index % len(_DEGREE_FUNCTION)]
            self._function_color = _FUNCTION_COLORS.get(func_key, _FUNCTION_COLORS["default"])
        self._update_style()

    def set_selected(self, selected: bool):
        """선택 상태 설정."""
        self._is_selected = selected
        self._update_style()

    def get_entry(self) -> Optional[ChordPadEntry]:
        return self._entry

    def _update_style(self):
        """코드 기능 색상 및 선택 상태 반영."""
        border_color = COLORS['accent'] if self._is_selected else self._function_color
        style = f"""
            QPushButton {{
                background: {self._function_color}30;
                color: {COLORS['text_primary']};
                border: 2px solid {border_color};
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                padding: 6px;
            }}
            QPushButton:hover {{
                background: {self._function_color}50;
                border-color: {COLORS['accent_light']};
            }}
            QPushButton:pressed {{
                background: {self._function_color}70;
            }}
        """
        self.setStyleSheet(style)

    def _show_context_menu(self, pos):
        """우클릭 컨텍스트 메뉴 — 편집, 복사, 지우기."""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {COLORS['bg_mid']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
            }}
            QMenu::item:selected {{
                background: {COLORS['bg_selected']};
            }}
        """)
        edit_action = menu.addAction("편집")
        copy_action = menu.addAction("복사")
        clear_action = menu.addAction("지우기")

        action = menu.exec(self.mapToGlobal(pos))
        if action == clear_action:
            self.set_chord(None)
        elif action == edit_action:
            self.right_clicked.emit(self._index)


# ─── 메인 코드 패드 패널 ───

class ChordPadPanel(QWidget):
    """Cubase 15 스타일 코드 패드 패널 — 4×4 그리드, 4페이지, 총 64패드."""

    chord_triggered = pyqtSignal(list)   # [{'pitch': int, 'velocity': int, ...}]
    chord_notes_changed = pyqtSignal(list)  # [int] — MIDI 노트 리스트

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pads: list[ChordPadButton] = []
        self._pad_data: list[Optional[ChordPadEntry]] = [None] * 64
        self._current_page = 0
        self._selected_pad = -1
        self._prev_notes: list[int] = []

        self.setStyleSheet(_PANEL_BG)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QHBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(6)

        # 왼쪽: 컨트롤 + 그리드
        left = QVBoxLayout()
        left.setSpacing(4)

        # ─── 상단 컨트롤 바 ───
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet(_CTRL_STYLE)
        ctrl_lay = QHBoxLayout(ctrl_frame)
        ctrl_lay.setContentsMargins(4, 2, 4, 2)
        ctrl_lay.setSpacing(8)

        # 키 선택
        ctrl_lay.addWidget(QLabel("Key"))
        self._key_combo = QComboBox()
        self._key_combo.addItems(NOTE_NAMES)
        self._key_combo.setFixedWidth(60)
        ctrl_lay.addWidget(self._key_combo)

        # 스케일 선택
        ctrl_lay.addWidget(QLabel("Scale"))
        self._scale_combo = QComboBox()
        self._scale_combo.addItems(SCALE_TYPES)
        self._scale_combo.setFixedWidth(110)
        ctrl_lay.addWidget(self._scale_combo)

        # 보이싱 타입 선택
        ctrl_lay.addWidget(QLabel("Voicing"))
        self._voicing_combo = QComboBox()
        self._voicing_combo.addItems(VOICING_TYPES)
        self._voicing_combo.setFixedWidth(80)
        ctrl_lay.addWidget(self._voicing_combo)

        # Auto Fill 버튼
        self._auto_fill_btn = QPushButton("Auto Fill")
        self._auto_fill_btn.clicked.connect(self._auto_fill)
        ctrl_lay.addWidget(self._auto_fill_btn)

        # 페이지 선택
        ctrl_lay.addStretch()
        ctrl_lay.addWidget(QLabel("Page"))
        self._page_spin = QSpinBox()
        self._page_spin.setRange(1, 4)
        self._page_spin.setValue(1)
        self._page_spin.setFixedWidth(50)
        self._page_spin.valueChanged.connect(self._on_page_changed)
        ctrl_lay.addWidget(self._page_spin)

        left.addWidget(ctrl_frame)

        # ─── 4×4 코드 패드 그리드 ───
        grid_frame = QFrame()
        grid_frame.setStyleSheet(f"background: {COLORS['bg_panel']}; border-radius: 4px;")
        grid_lay = QGridLayout(grid_frame)
        grid_lay.setContentsMargins(8, 8, 8, 8)
        grid_lay.setSpacing(6)

        for row in range(4):
            for col in range(4):
                idx = row * 4 + col
                pad = ChordPadButton(idx)
                pad.clicked.connect(lambda checked, i=idx: self._on_pad_clicked(i))
                pad.right_clicked.connect(self._on_pad_right_click)
                self._pads.append(pad)
                grid_lay.addWidget(pad, row, col)

        left.addWidget(grid_frame, 1)

        # ─── 하단 플레이어 컨트롤 ───
        player_frame = QFrame()
        player_frame.setStyleSheet(_CTRL_STYLE)
        player_lay = QHBoxLayout(player_frame)
        player_lay.setContentsMargins(4, 2, 4, 2)
        player_lay.setSpacing(12)

        # 아르페지오 토글
        self._arp_check = QCheckBox("Arpeggio")
        player_lay.addWidget(self._arp_check)

        # 스트럼 속도
        player_lay.addWidget(QLabel("Strum"))
        self._strum_slider = QSlider(Qt.Orientation.Horizontal)
        self._strum_slider.setRange(0, 200)
        self._strum_slider.setValue(0)
        self._strum_slider.setFixedWidth(100)
        player_lay.addWidget(self._strum_slider)
        self._strum_label = QLabel("0 ms")
        self._strum_slider.valueChanged.connect(
            lambda v: self._strum_label.setText(f"{v} ms"))
        player_lay.addWidget(self._strum_label)

        # 벨로시티
        player_lay.addWidget(QLabel("Velocity"))
        self._vel_slider = QSlider(Qt.Orientation.Horizontal)
        self._vel_slider.setRange(1, 127)
        self._vel_slider.setValue(80)
        self._vel_slider.setFixedWidth(100)
        player_lay.addWidget(self._vel_slider)
        self._vel_label = QLabel("80")
        self._vel_slider.valueChanged.connect(
            lambda v: self._vel_label.setText(str(v)))
        player_lay.addWidget(self._vel_label)

        player_lay.addStretch()
        left.addWidget(player_frame)

        root.addLayout(left, 3)

        # ─── 오른쪽: 보이싱 디스플레이 ───
        right_frame = QFrame()
        right_frame.setStyleSheet(
            f"background: {COLORS['bg_panel']}; border-radius: 4px;"
            f"border: 1px solid {COLORS['border']};")
        right_frame.setFixedWidth(200)
        right_lay = QVBoxLayout(right_frame)
        right_lay.setContentsMargins(4, 4, 4, 4)
        right_lay.setSpacing(4)

        voicing_title = QLabel("Voicing Display")
        voicing_title.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 10px; font-weight: bold;"
            "border: none;")
        voicing_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_lay.addWidget(voicing_title)

        self._mini_piano = MiniPianoWidget()
        right_lay.addWidget(self._mini_piano)

        # 코드 정보 레이블
        self._chord_info = QLabel("—")
        self._chord_info.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 14px; font-weight: bold;"
            "border: none;")
        self._chord_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_lay.addWidget(self._chord_info)

        # 노트 리스트 레이블
        self._notes_label = QLabel("")
        self._notes_label.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; border: none;")
        self._notes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._notes_label.setWordWrap(True)
        right_lay.addWidget(self._notes_label)

        right_lay.addStretch()
        root.addWidget(right_frame)

        # 초기 Auto Fill 실행
        self._auto_fill()

    # ─── 패드 이벤트 ───

    def _on_pad_clicked(self, index: int):
        """패드 클릭 — 코드를 트리거하고 UI를 업데이트합니다."""
        global_index = self._current_page * 16 + index
        entry = self._pad_data[global_index]
        if entry is None:
            return

        # 선택 상태 업데이트
        prev_selected = self._selected_pad
        self._selected_pad = index
        for i, pad in enumerate(self._pads):
            pad.set_selected(i == index)

        # 보이싱 생성
        voicing_type = self._voicing_combo.currentText()
        velocity = self._vel_slider.value()
        notes = get_voicing(
            entry.root, entry.quality,
            voicing_type=voicing_type,
            octave=4,
            velocity_base=velocity,
        )

        # 스트럼 적용
        strum_ms = self._strum_slider.value()
        if strum_ms > 0 and len(notes) > 1:
            for i, n in enumerate(notes):
                n["spread_ms"] = strum_ms * (i / (len(notes) - 1))

        # 보이싱 디스플레이 업데이트
        midi_notes = [n["pitch"] for n in notes]
        root_name = NOTE_NAMES[entry.root % 12]
        self._chord_info.setText(f"{root_name}{entry.quality}")
        note_names = [f"{NOTE_NAMES[p % 12]}{p // 12 - 1}" for p in midi_notes]
        self._notes_label.setText("  ".join(note_names))
        self._mini_piano.set_notes(midi_notes, self._prev_notes)
        self._prev_notes = midi_notes

        # 시그널 발생
        self.chord_triggered.emit(notes)
        self.chord_notes_changed.emit(midi_notes)

    def _on_pad_right_click(self, index: int):
        """패드 우클릭 — 편집 다이얼로그 (간소화)."""
        pass  # 추후 편집 다이얼로그 연결

    def _on_page_changed(self, page: int):
        """페이지 전환."""
        self._current_page = page - 1
        self._refresh_pad_display()

    # ─── Auto Fill ───

    def _auto_fill(self):
        """키와 스케일에 기반하여 코드패드를 자동으로 채웁니다."""
        key_root = self._key_combo.currentIndex()
        scale = self._scale_combo.currentText()

        # build_chord_pad_set은 major/minor만 지원, 나머지는 major로 폴백
        effective_scale = scale if scale in ("major", "minor") else "major"
        pad_entries = build_chord_pad_set(key_root, effective_scale)

        # 현재 페이지에 16개 패드 채우기
        page_offset = self._current_page * 16
        for i in range(16):
            if i < len(pad_entries):
                self._pad_data[page_offset + i] = pad_entries[i]
            else:
                self._pad_data[page_offset + i] = None

        self._refresh_pad_display()

    def _refresh_pad_display(self):
        """현재 페이지의 패드를 UI에 반영합니다."""
        page_offset = self._current_page * 16
        for i, pad in enumerate(self._pads):
            entry = self._pad_data[page_offset + i]
            pad.set_chord(entry, func_index=i)
            pad.set_selected(i == self._selected_pad)
