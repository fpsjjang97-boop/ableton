"""
Cubase 15 스타일 Expression Map 에디터 패널.

Cubase의 Expression Map 시스템을 재현하여, 연주 기법(Playing Technique)을
MIDI 동작(키스위치, CC, 벨로시티 등)에 매핑하는 에디터를 제공합니다.
기법 목록, MIDI 할당 뷰, 아티큘레이션 툴바를 포함합니다.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QSplitter, QTreeWidget, QTreeWidgetItem,
    QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, QGroupBox,
    QSizePolicy, QHeaderView, QCheckBox, QToolButton,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QIcon

from config import COLORS

from midigpt.cubase_data.expression_maps import (
    PLAYING_TECHNIQUES, EXPRESSION_MAPS,
)


# ─── 스타일 ───

_PANEL_BG = f"background: {COLORS['bg_dark']};"

_TREE_STYLE = f"""
    QTreeWidget {{
        background: {COLORS['bg_panel']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        font-size: 11px;
        outline: none;
    }}
    QTreeWidget::item {{
        padding: 2px 4px;
        border: none;
    }}
    QTreeWidget::item:selected {{
        background: {COLORS['bg_selected']};
        color: {COLORS['text_accent']};
    }}
    QTreeWidget::item:hover {{
        background: {COLORS['bg_hover']};
    }}
    QTreeWidget::branch {{
        background: {COLORS['bg_panel']};
    }}
    QHeaderView::section {{
        background: {COLORS['bg_header']};
        color: {COLORS['text_secondary']};
        border: 1px solid {COLORS['border']};
        padding: 3px 6px;
        font-size: 10px;
    }}
"""

_FORM_STYLE = f"""
    QLabel {{
        color: {COLORS['text_secondary']};
        font-size: 11px;
    }}
    QLineEdit, QSpinBox, QDoubleSpinBox {{
        background: {COLORS['bg_input']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 3px;
        padding: 2px 6px;
        font-size: 11px;
        min-height: 20px;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {COLORS['border_focus']};
    }}
    QCheckBox {{
        color: {COLORS['text_secondary']};
        font-size: 11px;
    }}
    QGroupBox {{
        color: {COLORS['text_secondary']};
        font-size: 11px;
        font-weight: bold;
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 12px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
"""

_COMBO_STYLE = f"""
    QComboBox {{
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
"""

_BTN_STYLE = f"""
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
    QPushButton:pressed {{
        background: {COLORS['bg_selected']};
    }}
"""

_TOOLBAR_BTN_STYLE = f"""
    QPushButton {{
        background: {COLORS['bg_mid']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 3px;
        padding: 4px 8px;
        font-size: 10px;
        min-width: 56px;
    }}
    QPushButton:hover {{
        background: {COLORS['bg_hover']};
        border-color: {COLORS['accent_secondary']};
    }}
    QPushButton:checked {{
        background: {COLORS['accent']}30;
        border-color: {COLORS['accent']};
        color: {COLORS['text_accent']};
    }}
"""

# 빠른 접근용 아티큘레이션 목록
_QUICK_ARTICULATIONS = [
    ("Natural", "nat", "N"),
    ("Staccato", "stac", "S"),
    ("Legato", "leg", "L"),
    ("Pizzicato", "pizz", "P"),
    ("Tremolo", "trem", "T"),
    ("Marcato", "marc", "M"),
    ("Spiccato", "spic", "I"),
    ("Portato", "port", "O"),
]

# 기법 그룹 표시 이름
_GROUP_LABELS = {
    "dynamics":   "Dynamics (셈여림)",
    "lengths":    "Lengths (길이)",
    "ornaments":  "Ornaments (장식음)",
    "techniques": "Techniques (주법)",
}


# ─── Expression Map 에디터 ───

class ExpressionMapEditor(QWidget):
    """Cubase 15 스타일 Expression Map 에디터 패널."""

    technique_selected = pyqtSignal(str, dict)  # (기법 이름, 기법 데이터)
    articulation_changed = pyqtSignal(str)       # 활성 아티큘레이션 이름

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_map_name: str = ""
        self._current_map_data: Dict[str, Dict[str, Any]] = {}
        self._current_technique: str = ""
        self._active_articulation: str = "natural"

        self.setStyleSheet(_PANEL_BG)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # ─── 맵 선택 바 ───
        top_bar = QFrame()
        top_bar.setStyleSheet(_COMBO_STYLE + _BTN_STYLE)
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(4, 2, 4, 2)
        top_lay.setSpacing(8)

        top_lay.addWidget(QLabel("Expression Map"))
        self._map_combo = QComboBox()
        self._map_combo.setMinimumWidth(200)
        for map_name in EXPRESSION_MAPS:
            display = map_name.replace("_", " ").title()
            self._map_combo.addItem(display, map_name)
        self._map_combo.currentIndexChanged.connect(self._on_map_changed)
        top_lay.addWidget(self._map_combo)

        self._new_btn = QPushButton("New")
        self._new_btn.clicked.connect(self._on_new_map)
        top_lay.addWidget(self._new_btn)

        self._dup_btn = QPushButton("Duplicate")
        self._dup_btn.clicked.connect(self._on_duplicate_map)
        top_lay.addWidget(self._dup_btn)

        top_lay.addStretch()

        # 현재 아티큘레이션 표시
        self._active_label = QLabel("Active: Natural")
        self._active_label.setStyleSheet(
            f"color: {COLORS['accent_light']}; font-size: 11px; font-weight: bold;")
        top_lay.addWidget(self._active_label)

        root.addWidget(top_bar)

        # ─── 메인 스플리터: 기법 목록 | 할당 뷰 ───
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {COLORS['border']};
                width: 2px;
            }}
        """)

        # ─── 왼쪽: 기법 트리 ───
        left_panel = QFrame()
        left_panel.setStyleSheet(f"background: {COLORS['bg_panel']};")
        left_panel.setFixedWidth(220)
        left_lay = QVBoxLayout(left_panel)
        left_lay.setContentsMargins(4, 4, 4, 4)
        left_lay.setSpacing(2)

        tree_label = QLabel("Playing Techniques")
        tree_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 10px; font-weight: bold;")
        left_lay.addWidget(tree_label)

        self._tech_tree = QTreeWidget()
        self._tech_tree.setHeaderLabels(["Technique", "Type", "Active"])
        self._tech_tree.setStyleSheet(_TREE_STYLE)
        self._tech_tree.setRootIsDecorated(True)
        self._tech_tree.setAlternatingRowColors(False)
        self._tech_tree.setColumnCount(3)
        header = self._tech_tree.header()
        header.setDefaultSectionSize(80)
        header.resizeSection(0, 120)
        header.resizeSection(1, 50)
        header.resizeSection(2, 40)
        self._tech_tree.itemClicked.connect(self._on_technique_clicked)
        self._tech_tree.itemDoubleClicked.connect(self._on_technique_double_clicked)
        left_lay.addWidget(self._tech_tree, 1)

        splitter.addWidget(left_panel)

        # ─── 중앙: 할당 뷰 ───
        center_panel = QFrame()
        center_panel.setStyleSheet(f"background: {COLORS['bg_dark']};")
        center_lay = QVBoxLayout(center_panel)
        center_lay.setContentsMargins(8, 8, 8, 8)
        center_lay.setSpacing(6)

        self._assign_title = QLabel("— Select a technique —")
        self._assign_title.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: bold;")
        self._assign_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_lay.addWidget(self._assign_title)

        # MIDI 할당 폼
        form_group = QGroupBox("MIDI Actions")
        form_group.setStyleSheet(_FORM_STYLE)
        form = QFormLayout(form_group)
        form.setContentsMargins(8, 16, 8, 8)
        form.setSpacing(6)

        # 키스위치 노트
        self._ks_edit = QLineEdit()
        self._ks_edit.setPlaceholderText("e.g. C0, C#1")
        self._ks_edit.setMaximumWidth(120)
        form.addRow("Keyswitch Note:", self._ks_edit)

        # CC 번호
        self._cc_num_spin = QSpinBox()
        self._cc_num_spin.setRange(0, 127)
        self._cc_num_spin.setMaximumWidth(80)
        form.addRow("CC Number:", self._cc_num_spin)

        # CC 값
        self._cc_val_spin = QSpinBox()
        self._cc_val_spin.setRange(0, 127)
        self._cc_val_spin.setMaximumWidth(80)
        form.addRow("CC Value:", self._cc_val_spin)

        # 벨로시티 팩터
        self._vel_factor = QDoubleSpinBox()
        self._vel_factor.setRange(0.0, 2.0)
        self._vel_factor.setSingleStep(0.1)
        self._vel_factor.setValue(1.0)
        self._vel_factor.setMaximumWidth(80)
        form.addRow("Velocity Factor:", self._vel_factor)

        # 길이 팩터
        self._len_factor = QDoubleSpinBox()
        self._len_factor.setRange(0.0, 2.0)
        self._len_factor.setSingleStep(0.1)
        self._len_factor.setValue(1.0)
        self._len_factor.setMaximumWidth(80)
        form.addRow("Length Factor:", self._len_factor)

        # 트랜스포즈
        self._transpose_spin = QSpinBox()
        self._transpose_spin.setRange(-24, 24)
        self._transpose_spin.setMaximumWidth(80)
        form.addRow("Transpose:", self._transpose_spin)

        # 오버랩 틱
        self._overlap_spin = QSpinBox()
        self._overlap_spin.setRange(0, 480)
        self._overlap_spin.setMaximumWidth(80)
        form.addRow("Overlap Ticks:", self._overlap_spin)

        center_lay.addWidget(form_group)

        # 적용 / 리셋 버튼
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(_BTN_STYLE)
        apply_btn.clicked.connect(self._apply_changes)
        btn_row.addWidget(apply_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.setStyleSheet(_BTN_STYLE)
        reset_btn.clicked.connect(self._reset_fields)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch()
        center_lay.addLayout(btn_row)

        center_lay.addStretch()
        splitter.addWidget(center_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        # ─── 하단: 아티큘레이션 툴바 ───
        toolbar = QFrame()
        toolbar.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_panel']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(6, 3, 6, 3)
        tb_lay.setSpacing(4)

        tb_label = QLabel("Quick Articulations:")
        tb_label.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; border: none;")
        tb_lay.addWidget(tb_label)

        self._artic_buttons: dict[str, QPushButton] = {}
        for display_name, short_name, shortcut_key in _QUICK_ARTICULATIONS:
            btn = QPushButton(f"{display_name} [{shortcut_key}]")
            btn.setStyleSheet(_TOOLBAR_BTN_STYLE)
            btn.setCheckable(True)
            btn.setChecked(short_name == "nat")
            btn.clicked.connect(
                lambda checked, sn=short_name, dn=display_name:
                    self._on_quick_articulation(sn, dn))
            self._artic_buttons[short_name] = btn
            tb_lay.addWidget(btn)

        tb_lay.addStretch()
        root.addWidget(toolbar)

        # 초기 맵 로드
        if self._map_combo.count() > 0:
            self._on_map_changed(0)

    # ─── 맵 선택 ───

    def _on_map_changed(self, index: int):
        """Expression Map 변경 시 기법 트리를 재구성합니다."""
        map_key = self._map_combo.itemData(index)
        if map_key is None:
            return
        self._current_map_name = map_key
        self._current_map_data = EXPRESSION_MAPS.get(map_key, {})
        self._populate_technique_tree()
        self._reset_fields()
        self._assign_title.setText(f"— Select a technique —")

    def _on_new_map(self):
        """새 빈 Expression Map을 생성합니다."""
        new_name = f"custom_{self._map_combo.count() + 1}"
        display = new_name.replace("_", " ").title()
        EXPRESSION_MAPS[new_name] = {"natural": {"volume_type": "velocity"}}
        self._map_combo.addItem(display, new_name)
        self._map_combo.setCurrentIndex(self._map_combo.count() - 1)

    def _on_duplicate_map(self):
        """현재 맵을 복제합니다."""
        if not self._current_map_name:
            return
        import copy
        new_name = f"{self._current_map_name}_copy"
        display = new_name.replace("_", " ").title()
        EXPRESSION_MAPS[new_name] = copy.deepcopy(
            EXPRESSION_MAPS.get(self._current_map_name, {}))
        self._map_combo.addItem(display, new_name)
        self._map_combo.setCurrentIndex(self._map_combo.count() - 1)

    # ─── 기법 트리 ───

    def _populate_technique_tree(self):
        """현재 Expression Map의 기법을 트리에 채웁니다."""
        self._tech_tree.clear()

        # 맵에 있는 기법을 그룹별로 분류
        map_techniques = set(self._current_map_data.keys())

        # PLAYING_TECHNIQUES 그룹별로 표시
        for group_key, group_label in _GROUP_LABELS.items():
            group_data = PLAYING_TECHNIQUES.get(group_key, {})
            if not group_data:
                continue

            group_item = QTreeWidgetItem([group_label, "", ""])
            group_item.setExpanded(False)
            group_item.setForeground(0, QColor(COLORS['accent_secondary']))
            font = group_item.font(0)
            font.setBold(True)
            group_item.setFont(0, font)

            for tech_name, tech_data in group_data.items():
                tech_type = tech_data.get("type", "attribute")
                is_in_map = tech_name in map_techniques
                active_str = "●" if is_in_map else ""

                child = QTreeWidgetItem([tech_name, tech_type[:4], active_str])
                child.setData(0, Qt.ItemDataRole.UserRole, tech_name)
                child.setData(1, Qt.ItemDataRole.UserRole, tech_data)

                if is_in_map:
                    child.setForeground(0, QColor(COLORS['text_primary']))
                    child.setForeground(2, QColor("#5B8C5A"))
                else:
                    child.setForeground(0, QColor(COLORS['text_dim']))

                group_item.addChild(child)

            self._tech_tree.addTopLevelItem(group_item)

        # Expression Map 고유 기법 (그룹에 없는 것)
        grouped_techs = set()
        for group_data in PLAYING_TECHNIQUES.values():
            grouped_techs.update(group_data.keys())

        extra_techs = map_techniques - grouped_techs
        if extra_techs:
            extra_group = QTreeWidgetItem(["Map Techniques", "", ""])
            extra_group.setExpanded(True)
            extra_group.setForeground(0, QColor(COLORS['accent_secondary']))
            font = extra_group.font(0)
            font.setBold(True)
            extra_group.setFont(0, font)

            for tech_name in sorted(extra_techs):
                tech_data = self._current_map_data.get(tech_name, {})
                child = QTreeWidgetItem([tech_name, "map", "●"])
                child.setData(0, Qt.ItemDataRole.UserRole, tech_name)
                child.setData(1, Qt.ItemDataRole.UserRole, tech_data)
                child.setForeground(0, QColor(COLORS['text_primary']))
                child.setForeground(2, QColor("#5B8C5A"))
                extra_group.addChild(child)

            self._tech_tree.addTopLevelItem(extra_group)

    def _on_technique_clicked(self, item: QTreeWidgetItem, column: int):
        """기법 클릭 — 할당 뷰에 MIDI 동작을 표시합니다."""
        tech_name = item.data(0, Qt.ItemDataRole.UserRole)
        if tech_name is None:
            return  # 그룹 헤더 클릭

        self._current_technique = tech_name
        self._assign_title.setText(f"Technique: {tech_name}")

        # Expression Map에서 해당 기법의 MIDI 할당 가져오기
        map_data = self._current_map_data.get(tech_name, {})

        # 폼 필드 채우기
        ks = map_data.get("keyswitch", "")
        self._ks_edit.setText(str(ks) if ks else "")

        # CC 매핑
        cc_mappings = map_data.get("cc_mappings", {})
        if cc_mappings:
            first_cc = next(iter(cc_mappings))
            self._cc_num_spin.setValue(int(first_cc) if str(first_cc).isdigit() else 0)
            self._cc_val_spin.setValue(cc_mappings[first_cc])
        else:
            # volume_type 등에서 CC 정보 추출
            vol = map_data.get("volume_type", "")
            if isinstance(vol, tuple) and len(vol) == 2:
                self._cc_num_spin.setValue(vol[1])
                self._cc_val_spin.setValue(0)
            else:
                self._cc_num_spin.setValue(0)
                self._cc_val_spin.setValue(0)

        self._vel_factor.setValue(map_data.get("velocity_mod", 1.0))
        self._len_factor.setValue(map_data.get("length_factor", 1.0))
        self._transpose_spin.setValue(map_data.get("transpose", 0))
        self._overlap_spin.setValue(map_data.get("overlap_ticks", 0))

        # 시그널 발생
        tech_info = PLAYING_TECHNIQUES.get("dynamics", {}).get(tech_name)
        if tech_info is None:
            for group in PLAYING_TECHNIQUES.values():
                if tech_name in group:
                    tech_info = group[tech_name]
                    break
        self.technique_selected.emit(tech_name, tech_info or map_data)

    def _on_technique_double_clicked(self, item: QTreeWidgetItem, column: int):
        """기법 더블클릭 — 활성 아티큘레이션으로 설정합니다."""
        tech_name = item.data(0, Qt.ItemDataRole.UserRole)
        if tech_name is None:
            return
        self._set_active_articulation(tech_name)

    # ─── 할당 편집 ───

    def _apply_changes(self):
        """현재 폼 값을 Expression Map에 반영합니다."""
        if not self._current_technique or not self._current_map_name:
            return

        data: Dict[str, Any] = {}

        ks = self._ks_edit.text().strip()
        if ks:
            data["keyswitch"] = ks

        cc_num = self._cc_num_spin.value()
        cc_val = self._cc_val_spin.value()
        if cc_num > 0:
            data["volume_type"] = ("cc", cc_num)

        vel = self._vel_factor.value()
        if vel != 1.0:
            data["velocity_mod"] = vel

        length = self._len_factor.value()
        if length != 1.0:
            data["length_factor"] = length

        transpose = self._transpose_spin.value()
        if transpose != 0:
            data["transpose"] = transpose

        overlap = self._overlap_spin.value()
        if overlap > 0:
            data["overlap_ticks"] = overlap

        # 맵 업데이트
        if self._current_map_name in EXPRESSION_MAPS:
            EXPRESSION_MAPS[self._current_map_name][self._current_technique] = data
            self._current_map_data = EXPRESSION_MAPS[self._current_map_name]

        # 트리 새로고침
        self._populate_technique_tree()

    def _reset_fields(self):
        """폼 필드를 기본값으로 초기화합니다."""
        self._ks_edit.clear()
        self._cc_num_spin.setValue(0)
        self._cc_val_spin.setValue(0)
        self._vel_factor.setValue(1.0)
        self._len_factor.setValue(1.0)
        self._transpose_spin.setValue(0)
        self._overlap_spin.setValue(0)
        self._current_technique = ""
        self._assign_title.setText("— Select a technique —")

    # ─── 아티큘레이션 툴바 ───

    def _on_quick_articulation(self, short_name: str, display_name: str):
        """빠른 아티큘레이션 버튼 클릭 핸들러."""
        self._set_active_articulation(display_name.lower())
        # 토글 상태 업데이트 — 하나만 활성화
        for sn, btn in self._artic_buttons.items():
            btn.setChecked(sn == short_name)

    def _set_active_articulation(self, name: str):
        """활성 아티큘레이션을 변경하고 UI를 업데이트합니다."""
        self._active_articulation = name
        self._active_label.setText(f"Active: {name.replace('_', ' ').title()}")
        self.articulation_changed.emit(name)
