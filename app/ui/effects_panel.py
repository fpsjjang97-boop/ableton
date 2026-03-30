"""
Effects Chain Editor — drag-and-drop effect chain management UI.
Insert/Send routing, effect parameter controls, bypass, dry/wet, presets.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QGroupBox, QScrollArea, QMenu,
    QSizePolicy, QFrame,
)
from config import COLORS
C = COLORS


class EffectSlotWidget(QWidget):
    """Single effect slot in the chain."""
    bypass_toggled = pyqtSignal(int, bool)
    remove_requested = pyqtSignal(int)
    params_changed = pyqtSignal(int, dict)

    def __init__(self, index: int, effect_name: str, parent=None):
        super().__init__(parent)
        self._index = index
        self._bypassed = False
        self.setFixedHeight(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        # Header
        hdr = QHBoxLayout()
        self._bypass_btn = QPushButton("ON")
        self._bypass_btn.setFixedSize(32, 18)
        self._bypass_btn.setCheckable(True)
        self._bypass_btn.setStyleSheet(f"""
            QPushButton {{ background: #2A4A2A; color: {C['text_primary']}; border: none;
                          border-radius: 3px; font-size: 8px; font-weight: bold; }}
            QPushButton:checked {{ background: #4A2A2A; color: #D48A8A; }}
        """)
        self._bypass_btn.toggled.connect(lambda v: self._on_bypass(v))
        hdr.addWidget(self._bypass_btn)

        self._name_lbl = QLabel(effect_name)
        self._name_lbl.setStyleSheet(f"color: {C['text_primary']}; font-size: 11px; font-weight: bold;")
        hdr.addWidget(self._name_lbl, 1)

        rm_btn = QPushButton("X")
        rm_btn.setFixedSize(18, 18)
        rm_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C['text_dim']}; border: none; font-size: 10px; }}
            QPushButton:hover {{ color: #D48A8A; }}
        """)
        rm_btn.clicked.connect(lambda: self.remove_requested.emit(self._index))
        hdr.addWidget(rm_btn)
        layout.addLayout(hdr)

        # Dry/Wet slider
        dw_row = QHBoxLayout()
        dw_row.addWidget(QLabel("D/W"))
        self._drywet = QSlider(Qt.Orientation.Horizontal)
        self._drywet.setRange(0, 100)
        self._drywet.setValue(100)
        self._drywet.setFixedHeight(14)
        self._drywet.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background: {C['bg_input']}; height: 3px; border-radius: 1px; }}
            QSlider::handle:horizontal {{ background: {C['text_primary']}; width: 10px; height: 10px;
                                         margin: -4px 0; border-radius: 5px; }}
        """)
        dw_row.addWidget(self._drywet, 1)
        self._dw_val = QLabel("100%")
        self._dw_val.setFixedWidth(32)
        self._dw_val.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px;")
        self._drywet.valueChanged.connect(lambda v: self._dw_val.setText(f"{v}%"))
        dw_row.addWidget(self._dw_val)
        layout.addLayout(dw_row)

        # Style
        self.setStyleSheet(f"""
            EffectSlotWidget {{
                background: {C['bg_mid']};
                border: 1px solid {C['border']};
                border-radius: 4px;
            }}
        """)

    def _on_bypass(self, bypassed):
        self._bypassed = bypassed
        self._bypass_btn.setText("OFF" if bypassed else "ON")
        self.bypass_toggled.emit(self._index, bypassed)
        self._name_lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 11px; font-weight: bold;"
            if bypassed else
            f"color: {C['text_primary']}; font-size: 11px; font-weight: bold;"
        )


class EffectsChainPanel(QWidget):
    """Effects chain editor for a single track."""
    effect_added = pyqtSignal(int, str)      # track_idx, effect_name
    effect_removed = pyqtSignal(int, int)    # track_idx, slot_idx
    effect_bypassed = pyqtSignal(int, int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._track_idx = 0
        self._slots: list[EffectSlotWidget] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # Header
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("INSERT EFFECTS"))
        self._add_btn = QPushButton("+ Add")
        self._add_btn.setFixedSize(60, 22)
        self._add_btn.setStyleSheet(f"""
            QPushButton {{ background: {C['bg_input']}; color: {C['text_secondary']};
                          border: 1px solid {C['border']}; border-radius: 3px; font-size: 10px; }}
            QPushButton:hover {{ border-color: {C['text_secondary']}; }}
        """)
        self._add_btn.clicked.connect(self._show_add_menu)
        hdr.addWidget(self._add_btn)
        root.addLayout(hdr)

        # Scroll area for effect slots
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {C['bg_darkest']}; }}")
        self._slots_container = QWidget()
        self._slots_layout = QVBoxLayout(self._slots_container)
        self._slots_layout.setContentsMargins(0, 0, 0, 0)
        self._slots_layout.setSpacing(2)
        self._slots_layout.addStretch()
        scroll.setWidget(self._slots_container)
        root.addWidget(scroll, 1)

        # Send section
        send_hdr = QLabel("SENDS")
        send_hdr.setStyleSheet(f"color: {C['text_secondary']}; font-size: 10px; font-weight: bold; padding-top: 4px;")
        root.addWidget(send_hdr)

        for name in ["Reverb", "Delay"]:
            row = QHBoxLayout()
            row.addWidget(QLabel(name))
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(0, 100)
            sl.setValue(0)
            sl.setFixedHeight(14)
            sl.setStyleSheet(f"""
                QSlider::groove:horizontal {{ background: {C['bg_input']}; height: 3px; }}
                QSlider::handle:horizontal {{ background: {C['text_primary']}; width: 10px; height: 10px;
                                             margin: -4px 0; border-radius: 5px; }}
            """)
            row.addWidget(sl, 1)
            val = QLabel("0")
            val.setFixedWidth(24)
            val.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px;")
            sl.valueChanged.connect(lambda v, l=val: l.setText(str(v)))
            row.addWidget(val)
            root.addLayout(row)

    def _show_add_menu(self):
        from core.effects_engine import EFFECT_PRESETS
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {C['bg_mid']}; color: {C['text_primary']}; border: 1px solid {C['border']}; }}
            QMenu::item:selected {{ background: {C['bg_input']}; }}
        """)
        for name in EFFECT_PRESETS:
            menu.addAction(name, lambda n=name: self._add_effect(n))
        menu.exec(self._add_btn.mapToGlobal(self._add_btn.rect().bottomLeft()))

    def _add_effect(self, name: str):
        idx = len(self._slots)
        slot = EffectSlotWidget(idx, name)
        slot.bypass_toggled.connect(lambda i, b: self.effect_bypassed.emit(self._track_idx, i, b))
        slot.remove_requested.connect(self._remove_effect)
        self._slots.append(slot)
        self._slots_layout.insertWidget(self._slots_layout.count() - 1, slot)
        self.effect_added.emit(self._track_idx, name)

    def _remove_effect(self, index: int):
        if 0 <= index < len(self._slots):
            slot = self._slots.pop(index)
            self._slots_layout.removeWidget(slot)
            slot.deleteLater()
            self.effect_removed.emit(self._track_idx, index)
            # Reindex
            for i, s in enumerate(self._slots):
                s._index = i

    def set_track(self, track_idx: int):
        self._track_idx = track_idx
