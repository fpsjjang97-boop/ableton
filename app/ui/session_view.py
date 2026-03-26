"""
Session View — Ableton Live-style clip grid with integrated mixer.

Replaces the old track_panel.py as the main center area. Implements a full
Session View with track headers, scrollable clip grid, scene launchers,
per-track mixer strips, and a master channel.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMenu, QSizePolicy, QToolButton,
    QAbstractScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QRect, QPoint
from PyQt6.QtGui import (
    QColor, QPainter, QFont, QPen, QBrush, QMouseEvent, QPaintEvent,
    QAction, QLinearGradient, QWheelEvent,
)

from core.models import Track, ProjectState, Note, TICKS_PER_BEAT, TRACK_COLORS
from config import COLORS

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
SLOT_WIDTH = 120
SLOT_HEIGHT = 24
HEADER_HEIGHT = 24
NUM_SCENES = 8
SCENE_LAUNCHER_WIDTH = 40
MIXER_STRIP_WIDTH = SLOT_WIDTH
MIXER_HEIGHT = 340
MASTER_WIDTH = 80
FADER_HEIGHT = 100


def _lighter(hex_color: str, amount: int = 30) -> str:
    """Return a lighter version of a hex color."""
    r = min(int(hex_color[1:3], 16) + amount, 255)
    g = min(int(hex_color[3:5], 16) + amount, 255)
    b = min(int(hex_color[5:7], 16) + amount, 255)
    return f"#{r:02X}{g:02X}{b:02X}"


def _darker(hex_color: str, amount: int = 30) -> str:
    """Return a darker version of a hex color."""
    r = max(int(hex_color[1:3], 16) - amount, 0)
    g = max(int(hex_color[3:5], 16) - amount, 0)
    b = max(int(hex_color[5:7], 16) - amount, 0)
    return f"#{r:02X}{g:02X}{b:02X}"


def _vol_to_db(val: int) -> str:
    """Convert 0-127 volume to a dB-ish readout string."""
    if val == 0:
        return "-inf"
    db = 40.0 * (val / 127.0) - 40.0
    return f"{db:+.1f}"


# =========================================================================
#  RenameableButton — QPushButton that emits a signal on double-click
# =========================================================================
class RenameableButton(QPushButton):
    """QPushButton that emits *double_clicked(int)* with its stored index."""

    double_clicked = pyqtSignal(int)

    def __init__(self, text: str, index: int, parent: QWidget | None = None):
        super().__init__(text, parent)
        self._index = index

    def set_index(self, idx: int):
        self._index = idx

    def mouseDoubleClickEvent(self, ev: QMouseEvent | None):
        self.double_clicked.emit(self._index)


# =========================================================================
#  TrackHeaderBar — horizontal row of colored track header labels
# =========================================================================
class TrackHeaderBar(QFrame):
    """Horizontal row of colored track header labels across the top."""

    track_selected = pyqtSignal(int)
    track_renamed = pyqtSignal(int, str)
    track_deleted = pyqtSignal(int)
    track_added = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._tracks: list[Track] = []
        self._labels: list[QPushButton] = []
        self._selected: int = -1

        self.setFixedHeight(HEADER_HEIGHT)
        self.setStyleSheet(
            f"background: {COLORS['bg_header']};"
            f"border-bottom: 1px solid {COLORS['separator']};"
        )

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._add_btn = QPushButton("+")
        self._add_btn.setFixedSize(HEADER_HEIGHT, HEADER_HEIGHT)
        self._add_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._add_btn.setStyleSheet(
            f"QPushButton{{background:{COLORS['bg_mid']};color:{COLORS['text_primary']};"
            f"border:none;border-left:1px solid {COLORS['separator']};}}"
            f"QPushButton:hover{{background:{COLORS['bg_hover']};}}"
        )
        self._add_btn.setToolTip("Add Track")
        self._add_btn.clicked.connect(self.track_added.emit)

    # ------------------------------------------------------------------

    def rebuild(self, tracks: list[Track], selected: int = 0):
        """Tear down and rebuild all header labels."""
        for lbl in self._labels:
            self._layout.removeWidget(lbl)
            lbl.deleteLater()
        self._labels.clear()
        self._tracks = tracks

        for i, track in enumerate(tracks):
            btn = RenameableButton(track.name, i)
            btn.setFixedSize(SLOT_WIDTH, HEADER_HEIGHT)
            btn.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, idx=i: self._context_menu(idx, pos)
            )
            btn.clicked.connect(lambda checked, idx=i: self._on_click(idx))
            btn.double_clicked.connect(self._rename)
            self._layout.addWidget(btn)
            self._labels.append(btn)

        # Spacer + add button
        self._layout.addStretch()
        self._layout.addWidget(self._add_btn)

        self._selected = selected
        self._apply_colors()

    def set_selected(self, idx: int):
        self._selected = idx
        self._apply_colors()

    def _apply_colors(self):
        for i, btn in enumerate(self._labels):
            track = self._tracks[i] if i < len(self._tracks) else None
            color = track.color if track else COLORS['bg_mid']
            is_sel = (i == self._selected)
            bg = color if is_sel else _darker(color, 50)
            text = "#FFFFFF" if is_sel else COLORS['text_primary']
            border = "2px" if is_sel else "0px"
            btn.setStyleSheet(
                f"QPushButton{{background:{bg};color:{text};"
                f"border:none;border-bottom:{border} solid {color};"
                f"border-right:1px solid {COLORS['separator']};padding:0 4px;"
                f"text-align:left;}}"
                f"QPushButton:hover{{background:{_lighter(bg, 15)};}}"
            )

    def _on_click(self, idx: int):
        self._selected = idx
        self._apply_colors()
        self.track_selected.emit(idx)

    def _rename(self, idx: int):
        from PyQt6.QtWidgets import QInputDialog
        if idx >= len(self._tracks):
            return
        name, ok = QInputDialog.getText(
            self, "Rename Track", "Track name:",
            text=self._tracks[idx].name,
        )
        if ok and name.strip():
            self._tracks[idx].name = name.strip()
            self._labels[idx].setText(name.strip())
            self.track_renamed.emit(idx, name.strip())

    def _context_menu(self, idx: int, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{COLORS['bg_dark']};color:{COLORS['text_primary']};"
            f"border:1px solid {COLORS['border']};}}"
            f"QMenu::item:selected{{background:{COLORS['bg_selected']};}}"
        )
        act_rename = menu.addAction("Rename")
        act_color = menu.addAction("Change Color...")
        menu.addSeparator()
        act_dup = menu.addAction("Duplicate")
        act_del = menu.addAction("Delete")

        action = menu.exec(self._labels[idx].mapToGlobal(pos))
        if action == act_rename:
            self._rename(idx)
        elif action == act_color:
            from PyQt6.QtWidgets import QColorDialog
            color = QColorDialog.getColor(
                QColor(self._tracks[idx].color), self, "Track Color"
            )
            if color.isValid():
                self._tracks[idx].color = color.name()
                self._apply_colors()
        elif action == act_dup:
            pass  # handled externally
        elif action == act_del:
            self.track_deleted.emit(idx)


# =========================================================================
#  ClipSlot — single cell in the clip grid
# =========================================================================
class ClipSlot(QFrame):
    """A single clip slot rendered via custom painting."""

    clip_selected = pyqtSignal(int, int)
    clip_launched = pyqtSignal(int, int)
    clip_double_clicked = pyqtSignal(int, int)

    EMPTY = 0
    HAS_CLIP = 1
    PLAYING = 2
    TRIGGERED = 3

    def __init__(self, track_idx: int, scene_idx: int,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._track_idx = track_idx
        self._scene_idx = scene_idx
        self._state = self.EMPTY
        self._clip_name: str = ""
        self._color: str = COLORS['bg_mid']
        self._is_selected: bool = False
        self._hovered: bool = False

        self.setFixedSize(SLOT_WIDTH, SLOT_HEIGHT)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    # -- public --

    def set_clip(self, name: str, color: str):
        self._state = self.HAS_CLIP
        self._clip_name = name
        self._color = color
        self.update()

    def set_empty(self):
        self._state = self.EMPTY
        self._clip_name = ""
        self.update()

    def set_playing(self, playing: bool):
        if self._state != self.EMPTY:
            self._state = self.PLAYING if playing else self.HAS_CLIP
            self.update()

    def set_triggered(self):
        if self._state != self.EMPTY:
            self._state = self.TRIGGERED
            self.update()

    def set_selected(self, sel: bool):
        self._is_selected = sel
        self.update()

    # -- painting --

    def paintEvent(self, ev: QPaintEvent | None):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        bg = QColor(COLORS['bg_darkest'])
        if self._scene_idx % 2 == 1:
            bg = QColor(COLORS['bg_dark'])
        p.fillRect(0, 0, w, h, bg)

        if self._state != self.EMPTY:
            # Clip rectangle
            clip_color = QColor(self._color)
            lighter = QColor(_lighter(self._color, 20))
            margin = 2
            r = QRect(margin, margin, w - margin * 2, h - margin * 2)

            # Gradient fill
            grad = QLinearGradient(r.x(), r.y(), r.x(), r.bottom())
            grad.setColorAt(0.0, lighter)
            grad.setColorAt(1.0, clip_color)
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, 2, 2)

            # Clip name
            p.setPen(QPen(QColor("#FFFFFF")))
            p.setFont(QFont("Segoe UI", 7))
            text_rect = QRect(margin + 14, margin, w - margin * 2 - 16, h - margin * 2)
            p.drawText(text_rect,
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       self._clip_name)

            # Play triangle or triggered indicator
            if self._state == self.PLAYING:
                p.setBrush(QBrush(QColor("#FFFFFF")))
                p.setPen(Qt.PenStyle.NoPen)
                cx, cy = margin + 8, h // 2
                tri = [QPoint(cx - 3, cy - 4), QPoint(cx - 3, cy + 4),
                       QPoint(cx + 4, cy)]
                p.drawPolygon(tri)
            elif self._state == self.TRIGGERED:
                p.setBrush(QBrush(QColor("#FFFFFF")))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPoint(margin + 8, h // 2), 3, 3)
            else:
                # Small play icon area on hover
                if self._hovered:
                    p.setBrush(QBrush(QColor(255, 255, 255, 120)))
                    p.setPen(Qt.PenStyle.NoPen)
                    cx, cy = margin + 8, h // 2
                    tri = [QPoint(cx - 2, cy - 3), QPoint(cx - 2, cy + 3),
                           QPoint(cx + 3, cy)]
                    p.drawPolygon(tri)

        # Selection border
        if self._is_selected:
            p.setPen(QPen(QColor(COLORS['border_focus']), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(1, 1, w - 2, h - 2)

        # Grid border
        p.setPen(QPen(QColor(COLORS['separator']), 0.5))
        p.drawLine(w - 1, 0, w - 1, h)
        p.drawLine(0, h - 1, w, h - 1)

        p.end()

    # -- events --

    def enterEvent(self, ev):
        self._hovered = True
        self.update()

    def leaveEvent(self, ev):
        self._hovered = False
        self.update()

    def mousePressEvent(self, ev: QMouseEvent | None):
        if ev and ev.button() == Qt.MouseButton.LeftButton:
            self.clip_selected.emit(self._track_idx, self._scene_idx)

    def mouseDoubleClickEvent(self, ev: QMouseEvent | None):
        if self._state != self.EMPTY:
            self.clip_double_clicked.emit(self._track_idx, self._scene_idx)

    def _context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{COLORS['bg_dark']};color:{COLORS['text_primary']};"
            f"border:1px solid {COLORS['border']};}}"
            f"QMenu::item:selected{{background:{COLORS['bg_selected']};}}"
        )
        if self._state == self.EMPTY:
            act_insert = menu.addAction("Insert Clip")
            action = menu.exec(self.mapToGlobal(pos))
            if action == act_insert:
                self.set_clip(f"{self._scene_idx + 1}", self._color)
                self.clip_launched.emit(self._track_idx, self._scene_idx)
        else:
            act_launch = menu.addAction("Launch")
            act_rename = menu.addAction("Rename")
            menu.addSeparator()
            act_dup = menu.addAction("Duplicate")
            act_del = menu.addAction("Delete Clip")
            action = menu.exec(self.mapToGlobal(pos))
            if action == act_launch:
                self.clip_launched.emit(self._track_idx, self._scene_idx)
            elif action == act_del:
                self.set_empty()
            elif action == act_rename:
                from PyQt6.QtWidgets import QInputDialog
                name, ok = QInputDialog.getText(
                    self, "Rename Clip", "Clip name:", text=self._clip_name
                )
                if ok and name.strip():
                    self._clip_name = name.strip()
                    self.update()


# =========================================================================
#  SceneLauncher — column of scene launch buttons on the far right
# =========================================================================
class SceneLauncher(QFrame):
    """Vertical column of scene launch buttons."""

    scene_launched = pyqtSignal(int)

    def __init__(self, num_scenes: int = NUM_SCENES,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._num_scenes = num_scenes
        self._buttons: list[QPushButton] = []

        self.setFixedWidth(SCENE_LAUNCHER_WIDTH)
        self.setStyleSheet(f"background:{COLORS['bg_dark']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for i in range(num_scenes):
            btn = QPushButton()
            btn.setFixedSize(SCENE_LAUNCHER_WIDTH, SLOT_HEIGHT)
            btn.setFont(QFont("Segoe UI", 7))
            btn.setToolTip(f"Launch Scene {i + 1}")
            btn.setStyleSheet(
                f"QPushButton{{background:{COLORS['bg_mid']};"
                f"color:{COLORS['text_secondary']};"
                f"border:none;border-bottom:1px solid {COLORS['separator']};}}"
                f"QPushButton:hover{{background:{COLORS['bg_hover']};}}"
                f"QPushButton:pressed{{background:{COLORS['bg_selected']};}}"
            )
            btn.clicked.connect(lambda checked, idx=i: self.scene_launched.emit(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()
        self._update_labels()

    def _update_labels(self):
        for i, btn in enumerate(self._buttons):
            btn.setText(f"\u25B6 {i + 1}")

    def paintEvent(self, ev: QPaintEvent | None):
        super().paintEvent(ev)
        p = QPainter(self)
        # Left border line
        p.setPen(QPen(QColor(COLORS['separator'])))
        p.drawLine(0, 0, 0, self.height())
        p.end()


# =========================================================================
#  ClipGrid — scrollable grid of ClipSlots
# =========================================================================
class ClipGrid(QWidget):
    """Scrollable grid of ClipSlots, rows=scenes, cols=tracks."""

    clip_selected = pyqtSignal(int, int)
    clip_launched = pyqtSignal(int, int)
    clip_double_clicked = pyqtSignal(int, int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._slots: list[list[ClipSlot]] = []  # [track_idx][scene_idx]
        self._num_tracks: int = 0
        self._num_scenes: int = NUM_SCENES
        self._selected_track: int = -1
        self._selected_scene: int = -1

        self._grid_layout = QGridLayout(self)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(0)

    def rebuild(self, tracks: list[Track], num_scenes: int = NUM_SCENES):
        """Reconstruct the entire grid."""
        # Tear down
        for track_slots in self._slots:
            for slot in track_slots:
                self._grid_layout.removeWidget(slot)
                slot.deleteLater()
        self._slots.clear()

        self._num_tracks = len(tracks)
        self._num_scenes = num_scenes

        for t_idx, track in enumerate(tracks):
            col_slots: list[ClipSlot] = []
            for s_idx in range(num_scenes):
                slot = ClipSlot(t_idx, s_idx)
                slot._color = track.color
                # Populate first scene with clip data if track has notes
                if s_idx == 0 and track.notes:
                    slot.set_clip(track.name, track.color)
                slot.clip_selected.connect(self._on_slot_selected)
                slot.clip_launched.connect(self.clip_launched.emit)
                slot.clip_double_clicked.connect(self.clip_double_clicked.emit)
                self._grid_layout.addWidget(slot, s_idx, t_idx)
                col_slots.append(slot)
            self._slots.append(col_slots)

        # Set fixed size for scrolling
        self.setFixedSize(
            self._num_tracks * SLOT_WIDTH,
            self._num_scenes * SLOT_HEIGHT,
        )

    def _on_slot_selected(self, track_idx: int, scene_idx: int):
        # Deselect previous
        if (0 <= self._selected_track < len(self._slots) and
                0 <= self._selected_scene < len(self._slots[self._selected_track])):
            self._slots[self._selected_track][self._selected_scene].set_selected(False)

        self._selected_track = track_idx
        self._selected_scene = scene_idx

        if (0 <= track_idx < len(self._slots) and
                0 <= scene_idx < len(self._slots[track_idx])):
            self._slots[track_idx][scene_idx].set_selected(True)

        self.clip_selected.emit(track_idx, scene_idx)

    def set_playback_state(self, track_idx: int, scene_idx: int, playing: bool):
        if (0 <= track_idx < len(self._slots) and
                0 <= scene_idx < len(self._slots[track_idx])):
            self._slots[track_idx][scene_idx].set_playing(playing)

    def get_slot(self, track_idx: int, scene_idx: int) -> ClipSlot | None:
        if (0 <= track_idx < len(self._slots) and
                0 <= scene_idx < len(self._slots[track_idx])):
            return self._slots[track_idx][scene_idx]
        return None


# =========================================================================
#  KnobIndicator — small painted knob (non-interactive display)
# =========================================================================
class KnobIndicator(QWidget):
    """Tiny circular knob indicator with mouse-drag and scroll interaction."""

    value_changed = pyqtSignal(int)

    def __init__(self, value: int = 64, min_val: int = 0, max_val: int = 127,
                 label: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._value = value
        self._min = min_val
        self._max = max_val
        self._label = label
        self._color = COLORS['accent_secondary']
        self._drag_start_y: float | None = None
        self._drag_start_value: int = value
        self.setFixedSize(28, 28)
        self.setToolTip(f"{label}: {value}")

    def value(self) -> int:
        return self._value

    def set_value(self, val: int):
        self._value = max(self._min, min(self._max, val))
        self.setToolTip(f"{self._label}: {self._value}")
        self.update()

    def _set_value_emit(self, val: int):
        """Set value and emit signal if changed."""
        old = self._value
        self._value = max(self._min, min(self._max, val))
        self.setToolTip(f"{self._label}: {self._value}")
        self.update()
        if self._value != old:
            self.value_changed.emit(self._value)

    def mousePressEvent(self, ev: QMouseEvent | None):
        if ev and ev.button() == Qt.MouseButton.LeftButton:
            self._drag_start_y = ev.position().y()
            self._drag_start_value = self._value

    def mouseMoveEvent(self, ev: QMouseEvent | None):
        if ev and self._drag_start_y is not None:
            delta_y = self._drag_start_y - ev.position().y()
            # 1 pixel of vertical drag = ~1 unit of value
            new_val = self._drag_start_value + int(delta_y)
            self._set_value_emit(new_val)

    def mouseReleaseEvent(self, ev: QMouseEvent | None):
        self._drag_start_y = None

    def wheelEvent(self, ev: QWheelEvent | None):
        if ev is None:
            return
        steps = ev.angleDelta().y() // 120
        self._set_value_emit(self._value + steps)
        ev.accept()

    def set_color(self, color: str):
        self._color = color
        self.update()

    def paintEvent(self, ev: QPaintEvent | None):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        radius = min(w, h) // 2 - 3

        # Background ring
        p.setPen(QPen(QColor(COLORS['border']), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPoint(cx, cy), radius, radius)

        # Value arc
        import math
        frac = (self._value - self._min) / max(self._max - self._min, 1)
        start_angle = 225  # degrees, bottom-left
        sweep = -frac * 270  # 270 degree range

        p.setPen(QPen(QColor(self._color), 2.5))
        # Qt angles in 1/16th degree
        p.drawArc(
            cx - radius, cy - radius, radius * 2, radius * 2,
            int(start_angle * 16), int(sweep * 16),
        )

        # Indicator dot
        angle_rad = math.radians(start_angle + sweep)
        dot_x = cx + int(radius * 0.7 * math.cos(angle_rad))
        dot_y = cy - int(radius * 0.7 * math.sin(angle_rad))
        p.setBrush(QBrush(QColor(self._color)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(dot_x, dot_y), 2, 2)

        p.end()


# =========================================================================
#  VerticalFader — simple painted vertical fader
# =========================================================================
class VerticalFader(QWidget):
    """Compact vertical fader painted custom, with mouse interaction."""

    value_changed = pyqtSignal(int)

    def __init__(self, value: int = 100, min_val: int = 0, max_val: int = 127,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._value = value
        self._min = min_val
        self._max = max_val
        self._dragging = False
        self.setFixedSize(20, FADER_HEIGHT)
        self.setMouseTracking(True)

    def set_value(self, val: int):
        self._value = max(self._min, min(self._max, val))
        self.update()

    def value(self) -> int:
        return self._value

    def paintEvent(self, ev: QPaintEvent | None):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Track groove
        groove_x = w // 2 - 2
        p.fillRect(groove_x, 4, 4, h - 8, QColor(COLORS['bg_input']))
        p.setPen(QPen(QColor(COLORS['border']), 0.5))
        p.drawRect(groove_x, 4, 4, h - 8)

        # Fill from bottom
        frac = (self._value - self._min) / max(self._max - self._min, 1)
        fill_h = int(frac * (h - 16))
        fill_y = h - 8 - fill_h

        grad = QLinearGradient(groove_x, fill_y, groove_x, h - 8)
        grad.setColorAt(0.0, QColor(COLORS['accent_light']))
        grad.setColorAt(1.0, QColor(COLORS['accent_secondary']))
        p.fillRect(groove_x, fill_y, 4, fill_h, QBrush(grad))

        # Handle
        handle_y = fill_y - 3
        handle_rect = QRect(groove_x - 4, handle_y, 12, 6)
        p.setBrush(QBrush(QColor(COLORS['text_primary'])))
        p.setPen(QPen(QColor(COLORS['border']), 0.5))
        p.drawRoundedRect(handle_rect, 1, 1)

        # Center line on handle
        p.setPen(QPen(QColor(COLORS['bg_darkest']), 0.5))
        p.drawLine(handle_rect.left() + 2, handle_y + 3,
                   handle_rect.right() - 2, handle_y + 3)

        p.end()

    def mousePressEvent(self, ev: QMouseEvent | None):
        if ev and ev.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._update_from_mouse(ev.position().y())

    def mouseMoveEvent(self, ev: QMouseEvent | None):
        if ev and self._dragging:
            self._update_from_mouse(ev.position().y())

    def mouseReleaseEvent(self, ev: QMouseEvent | None):
        self._dragging = False

    def _update_from_mouse(self, y: float):
        h = self.height()
        frac = 1.0 - max(0.0, min(1.0, (y - 8) / (h - 16)))
        new_val = int(self._min + frac * (self._max - self._min))
        if new_val != self._value:
            self._value = new_val
            self.update()
            self.value_changed.emit(self._value)


# =========================================================================
#  MixerStrip — single per-track mixer channel strip
# =========================================================================
class MixerStrip(QFrame):
    """Compact vertical mixer strip for one track, Ableton-style."""

    mute_toggled = pyqtSignal(int)
    solo_toggled = pyqtSignal(int)
    volume_changed = pyqtSignal(int, int)
    pan_changed = pyqtSignal(int, int)  # track_idx, value

    def __init__(self, track_idx: int, track: Track,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._track_idx = track_idx
        self._track = track

        self.setFixedWidth(MIXER_STRIP_WIDTH)
        self.setMinimumHeight(MIXER_HEIGHT)
        self.setStyleSheet(
            f"MixerStrip{{background:#131313;"
            f"border-right:1px solid {COLORS['separator']};}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        label_font = QFont("Segoe UI", 7)
        dim_style = f"color:{COLORS['text_dim']};background:transparent;"
        val_style = f"color:{COLORS['text_secondary']};background:transparent;"

        # -- Audio From --
        lbl_from = QLabel("Audio From")
        lbl_from.setFont(label_font)
        lbl_from.setStyleSheet(dim_style)
        lbl_from.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_from)

        from_btn = QPushButton("Ext. In")
        from_btn.setFixedHeight(16)
        from_btn.setFont(QFont("Segoe UI", 7))
        from_btn.setStyleSheet(
            f"QPushButton{{background:{COLORS['bg_input']};color:{COLORS['text_secondary']};"
            f"border:1px solid {COLORS['border']};border-radius:2px;padding:0 2px;}}"
            f"QPushButton:hover{{border-color:{COLORS['accent_secondary']};}}"
        )
        layout.addWidget(from_btn)

        # -- Monitor --
        lbl_mon = QLabel("Monitor")
        lbl_mon.setFont(label_font)
        lbl_mon.setStyleSheet(dim_style)
        lbl_mon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_mon)

        mon_row = QHBoxLayout()
        mon_row.setSpacing(1)
        mon_row.setContentsMargins(0, 0, 0, 0)
        self._monitor_buttons: list[QPushButton] = []
        mon_style = (
            f"QPushButton{{background:{COLORS['bg_input']};"
            f"color:{COLORS['text_secondary']};border:1px solid {COLORS['border']};"
            f"border-radius:1px;padding:0 1px;}}"
            f"QPushButton:checked{{background:{COLORS['bg_selected']};"
            f"color:{COLORS['text_primary']};}}"
            f"QPushButton:hover{{border-color:{COLORS['accent_secondary']};}}"
        )
        for text in ["In", "Auto", "Off"]:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setFixedHeight(14)
            b.setFont(QFont("Segoe UI", 6))
            b.setChecked(text == "Auto")
            b.setStyleSheet(mon_style)
            b.clicked.connect(lambda checked, btn=b: self._on_monitor_clicked(btn))
            mon_row.addWidget(b)
            self._monitor_buttons.append(b)
        layout.addLayout(mon_row)

        # -- Audio To --
        lbl_to = QLabel("Audio To")
        lbl_to.setFont(label_font)
        lbl_to.setStyleSheet(dim_style)
        lbl_to.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_to)

        to_btn = QPushButton("Main")
        to_btn.setFixedHeight(16)
        to_btn.setFont(QFont("Segoe UI", 7))
        to_btn.setStyleSheet(
            f"QPushButton{{background:{COLORS['bg_input']};color:{COLORS['text_secondary']};"
            f"border:1px solid {COLORS['border']};border-radius:2px;padding:0 2px;}}"
            f"QPushButton:hover{{border-color:{COLORS['accent_secondary']};}}"
        )
        layout.addWidget(to_btn)

        # -- Separator --
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{COLORS['separator']};")
        layout.addWidget(sep)

        # -- Sends (horizontal sliders) --
        lbl_sends = QLabel("Sends")
        lbl_sends.setFont(label_font)
        lbl_sends.setStyleSheet(dim_style)
        lbl_sends.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sends)

        from PyQt6.QtWidgets import QSlider
        _slider_style = (
            "QSlider{background:transparent;}"
            "QSlider::groove:horizontal{height:4px;background:#1A1A1A;"
            "border:1px solid #333;border-radius:2px;}"
            "QSlider::handle:horizontal{width:10px;height:10px;"
            "background:#888;border:1px solid #555;border-radius:5px;"
            "margin:-3px 0;}"
            "QSlider::handle:horizontal:hover{background:#AAA;}"
        )

        self._send_a = QSlider(Qt.Orientation.Horizontal)
        self._send_a.setRange(0, 127)
        self._send_a.setValue(0)
        self._send_a.setFixedHeight(16)
        self._send_a.setToolTip("Send A")
        self._send_a.setStyleSheet(_slider_style)
        layout.addWidget(self._send_a)

        self._send_b = QSlider(Qt.Orientation.Horizontal)
        self._send_b.setRange(0, 127)
        self._send_b.setValue(0)
        self._send_b.setFixedHeight(16)
        self._send_b.setToolTip("Send B")
        self._send_b.setStyleSheet(_slider_style)
        layout.addWidget(self._send_b)

        # -- Volume (horizontal slider) --
        vol_label = QLabel("Vol")
        vol_label.setFont(label_font)
        vol_label.setStyleSheet(dim_style)
        vol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(vol_label)

        self._fader = QSlider(Qt.Orientation.Horizontal)
        self._fader.setRange(0, 127)
        self._fader.setValue(track.volume)
        self._fader.setFixedHeight(22)
        self._fader.setToolTip(f"Volume: {track.volume}")
        self._fader.setStyleSheet(
            "QSlider{background:transparent;}"
            "QSlider::groove:horizontal{height:6px;background:#1A1A1A;"
            "border:1px solid #333;border-radius:3px;}"
            "QSlider::handle:horizontal{width:14px;height:14px;"
            "background:#CCC;border:1px solid #666;border-radius:7px;"
            "margin:-4px 0;}"
            "QSlider::handle:horizontal:hover{background:#FFF;}"
            "QSlider::sub-page:horizontal{background:#888;border-radius:3px;}"
        )
        self._fader.valueChanged.connect(self._on_volume)
        layout.addWidget(self._fader)

        # -- dB readout --
        self._db_label = QLabel(_vol_to_db(track.volume))
        self._db_label.setFont(QFont("Segoe UI", 7))
        self._db_label.setStyleSheet(val_style)
        self._db_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._db_label)

        # -- Pan (horizontal slider) --
        pan_label = QLabel("Pan")
        pan_label.setFont(label_font)
        pan_label.setStyleSheet(dim_style)
        pan_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(pan_label)

        self._pan_knob = QSlider(Qt.Orientation.Horizontal)
        self._pan_knob.setRange(0, 127)
        self._pan_knob.setValue(track.pan)
        self._pan_knob.setFixedHeight(22)
        self._pan_knob.setToolTip(f"Pan: {track.pan}")
        self._pan_knob.setStyleSheet(_slider_style)
        self._pan_knob.valueChanged.connect(self._on_pan)
        layout.addWidget(self._pan_knob)

        # -- Track number in colored circle --
        self._track_num = QLabel(str(track_idx + 1))
        self._track_num.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._track_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._track_num.setFixedSize(22, 22)
        self._track_num.setStyleSheet(
            f"background:{track.color};color:#FFFFFF;"
            f"border-radius:11px;border:none;"
        )
        num_row = QHBoxLayout()
        num_row.setContentsMargins(0, 2, 0, 2)
        num_row.addStretch()
        num_row.addWidget(self._track_num)
        num_row.addStretch()
        layout.addLayout(num_row)

        # -- Mute / Solo buttons --
        ms_row = QHBoxLayout()
        ms_row.setSpacing(2)
        ms_row.setContentsMargins(0, 0, 0, 0)

        self._mute_btn = QPushButton("M")
        self._mute_btn.setCheckable(True)
        self._mute_btn.setChecked(track.muted)
        self._mute_btn.setFixedSize(30, 18)
        self._mute_btn.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self._mute_btn.clicked.connect(self._on_mute)
        self._apply_mute_style()
        ms_row.addWidget(self._mute_btn)

        self._solo_btn = QPushButton("S")
        self._solo_btn.setCheckable(True)
        self._solo_btn.setChecked(track.solo)
        self._solo_btn.setFixedSize(30, 18)
        self._solo_btn.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self._solo_btn.clicked.connect(self._on_solo)
        self._apply_solo_style()
        ms_row.addWidget(self._solo_btn)

        layout.addLayout(ms_row)

    # -- internal --

    def _apply_mute_style(self):
        bg = COLORS['accent_orange'] if self._mute_btn.isChecked() else COLORS['bg_mid']
        self._mute_btn.setStyleSheet(
            f"QPushButton{{background:{bg};color:{COLORS['text_primary']};"
            f"border:1px solid {COLORS['border']};border-radius:2px;}}"
            f"QPushButton:hover{{border-color:{COLORS['accent_secondary']};}}"
        )

    def _apply_solo_style(self):
        bg = COLORS['accent_yellow'] if self._solo_btn.isChecked() else COLORS['bg_mid']
        fg = COLORS['bg_darkest'] if self._solo_btn.isChecked() else COLORS['text_primary']
        self._solo_btn.setStyleSheet(
            f"QPushButton{{background:{bg};color:{fg};"
            f"border:1px solid {COLORS['border']};border-radius:2px;}}"
            f"QPushButton:hover{{border-color:{COLORS['accent_secondary']};}}"
        )

    def _on_mute(self):
        self._track.muted = self._mute_btn.isChecked()
        self._apply_mute_style()
        self.mute_toggled.emit(self._track_idx)

    def _on_solo(self):
        self._track.solo = self._solo_btn.isChecked()
        self._apply_solo_style()
        self.solo_toggled.emit(self._track_idx)

    def _on_volume(self, val: int):
        self._track.volume = val
        self._db_label.setText(_vol_to_db(val))
        self.volume_changed.emit(self._track_idx, val)

    def _on_pan(self, val: int):
        self._track.pan = val
        self.pan_changed.emit(self._track_idx, val)

    def _on_monitor_clicked(self, active_btn: QPushButton):
        """Radio-style toggle: only one monitor button is checked at a time."""
        for btn in self._monitor_buttons:
            btn.setChecked(btn is active_btn)

    def update_track(self, track_idx: int, track: Track):
        self._track_idx = track_idx
        self._track = track
        self._fader.set_value(track.volume)
        self._pan_knob.set_value(track.pan)
        self._db_label.setText(_vol_to_db(track.volume))
        self._mute_btn.setChecked(track.muted)
        self._solo_btn.setChecked(track.solo)
        self._apply_mute_style()
        self._apply_solo_style()
        self._track_num.setText(str(track_idx + 1))
        self._track_num.setStyleSheet(
            f"background:{track.color};color:#FFFFFF;"
            f"border-radius:11px;border:none;"
        )


# =========================================================================
#  SessionMixer — row of MixerStrips below the clip grid
# =========================================================================
class SessionMixer(QWidget):
    """Horizontal row of per-track mixer strips."""

    volume_changed = pyqtSignal(int, int)   # track_idx, value
    mute_toggled = pyqtSignal(int)          # track_idx
    solo_toggled = pyqtSignal(int)          # track_idx
    pan_changed = pyqtSignal(int, int)      # track_idx, value

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._strips: list[MixerStrip] = []

        self.setStyleSheet(f"background:#111111;")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

    def rebuild(self, tracks: list[Track]):
        for strip in self._strips:
            self._layout.removeWidget(strip)
            strip.deleteLater()
        self._strips.clear()

        for i, track in enumerate(tracks):
            strip = MixerStrip(i, track)
            strip.volume_changed.connect(lambda idx, val: self.volume_changed.emit(idx, val))
            strip.mute_toggled.connect(lambda idx: self.mute_toggled.emit(idx))
            strip.solo_toggled.connect(lambda idx: self.solo_toggled.emit(idx))
            strip.pan_changed.connect(lambda idx, val: self.pan_changed.emit(idx, val))
            self._layout.addWidget(strip)
            self._strips.append(strip)

        self._layout.addStretch()
        self.setFixedHeight(MIXER_HEIGHT)

    def update_meters(self, levels: list):
        """Update VU levels on each mixer strip."""
        for i, strip in enumerate(self._strips):
            level = levels[i] if i < len(levels) else 0.0
            if hasattr(strip, '_fader'):
                pass  # VU meter update placeholder

    def get_strip(self, idx: int) -> MixerStrip | None:
        if 0 <= idx < len(self._strips):
            return self._strips[idx]
        return None


# =========================================================================
#  MasterChannel — always-visible master strip on the right
# =========================================================================
class MasterChannel(QFrame):
    """Master output channel strip."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(MASTER_WIDTH)
        self.setStyleSheet(
            f"MasterChannel{{background:#111111;"
            f"border-left:1px solid {COLORS['separator']};}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        label_font = QFont("Segoe UI", 7)
        dim_style = f"color:{COLORS['text_dim']};background:transparent;"
        val_style = f"color:{COLORS['text_secondary']};background:transparent;"

        # Cue Out
        lbl_cue = QLabel("Cue Out")
        lbl_cue.setFont(label_font)
        lbl_cue.setStyleSheet(dim_style)
        lbl_cue.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_cue)

        cue_btn = QPushButton("Main")
        cue_btn.setFixedHeight(16)
        cue_btn.setFont(QFont("Segoe UI", 7))
        cue_btn.setStyleSheet(
            f"QPushButton{{background:{COLORS['bg_input']};color:{COLORS['text_secondary']};"
            f"border:1px solid {COLORS['border']};border-radius:2px;padding:0 2px;}}"
            f"QPushButton:hover{{border-color:{COLORS['accent_secondary']};}}"
        )
        layout.addWidget(cue_btn)

        # Main Out
        lbl_main = QLabel("Main Out")
        lbl_main.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_main.setStyleSheet(f"color:{COLORS['text_primary']};background:transparent;")
        lbl_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_main)

        layout.addSpacing(6)

        # Master volume fader (taller)
        fader_row = QHBoxLayout()
        fader_row.setContentsMargins(0, 0, 0, 0)
        fader_row.addStretch()
        self._fader = VerticalFader(100, 0, 127)
        self._fader.setFixedSize(20, FADER_HEIGHT + 30)
        fader_row.addWidget(self._fader)
        fader_row.addStretch()
        layout.addLayout(fader_row)

        # dB readout
        self._db_label = QLabel(_vol_to_db(100))
        self._db_label.setFont(QFont("Segoe UI", 8))
        self._db_label.setStyleSheet(val_style)
        self._db_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._db_label)

        self._fader.value_changed.connect(self._on_fader)

        # Pan
        pan_row = QHBoxLayout()
        pan_row.setContentsMargins(0, 0, 0, 0)
        pan_row.addStretch()
        self._pan = KnobIndicator(64, 0, 127, "Pan")
        pan_row.addWidget(self._pan)
        pan_row.addStretch()
        layout.addLayout(pan_row)

        layout.addStretch()

        # Master label at bottom
        master_lbl = QLabel("M")
        master_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        master_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        master_lbl.setFixedSize(26, 26)
        master_lbl.setStyleSheet(
            f"background:{COLORS['accent']};color:#000000;"
            f"border-radius:13px;border:none;"
        )
        m_row = QHBoxLayout()
        m_row.addStretch()
        m_row.addWidget(master_lbl)
        m_row.addStretch()
        layout.addLayout(m_row)

    def _on_fader(self, val: int):
        self._db_label.setText(_vol_to_db(val))


# =========================================================================
#  SessionView — main container widget
# =========================================================================
class SessionView(QWidget):
    """
    Full Ableton Session View: track headers, clip grid, scene launchers,
    per-track mixer strips, and master channel.

    Layout:
    ┌─ TrackHeaderBar ────────────────────── + ┐
    │  ClipGrid (scrollable)          SceneL   │
    │                                 auncher  │
    ├──────────────────────────────────────────-┤
    │  SessionMixer (per-track)       Master   │
    └──────────────────────────────────────────-┘
    """

    track_selected = pyqtSignal(int)
    clip_opened = pyqtSignal(int, int)
    track_added = pyqtSignal()
    track_removed = pyqtSignal(int)
    mixer_volume_changed = pyqtSignal(int, int)
    mixer_mute_toggled = pyqtSignal(int)
    mixer_solo_toggled = pyqtSignal(int)
    mixer_pan_changed = pyqtSignal(int, int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._project: ProjectState | None = None
        self._selected_track: int = 0

        self.setStyleSheet(f"background:{COLORS['bg_darkest']};")
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Track header bar ----
        self._header_bar = TrackHeaderBar()
        self._header_bar.track_selected.connect(self._on_track_selected)
        self._header_bar.track_added.connect(self._add_track)
        self._header_bar.track_deleted.connect(self._remove_track)
        self._header_bar.track_renamed.connect(self._on_track_renamed)
        root.addWidget(self._header_bar)

        # ---- Middle area: clip grid + scene launcher ----
        mid_layout = QHBoxLayout()
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(0)

        # Clip grid in scroll area
        self._clip_scroll = QScrollArea()
        self._clip_scroll.setWidgetResizable(False)
        self._clip_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._clip_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._clip_scroll.setStyleSheet(
            f"QScrollArea{{background:{COLORS['bg_darkest']};border:none;}}"
        )

        self._clip_grid = ClipGrid()
        self._clip_grid.clip_selected.connect(self._on_clip_selected)
        self._clip_grid.clip_launched.connect(self._on_clip_launched)
        self._clip_grid.clip_double_clicked.connect(self._on_clip_double_clicked)
        self._clip_scroll.setWidget(self._clip_grid)

        mid_layout.addWidget(self._clip_scroll, 1)

        # Scene launcher
        self._scene_launcher = SceneLauncher(NUM_SCENES)
        self._scene_launcher.scene_launched.connect(self._on_scene_launched)
        mid_layout.addWidget(self._scene_launcher)

        root.addLayout(mid_layout, 1)

        # ---- Separator ----
        sep = QFrame()
        sep.setFixedHeight(2)
        sep.setStyleSheet(f"background:{COLORS['separator']};")
        root.addWidget(sep)

        # ---- Bottom: mixer + master ----
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(0)

        # Mixer in scroll area (synced horizontally with clip grid)
        self._mixer_scroll = QScrollArea()
        self._mixer_scroll.setWidgetResizable(False)
        self._mixer_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._mixer_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._mixer_scroll.setFixedHeight(MIXER_HEIGHT + 4)
        self._mixer_scroll.setStyleSheet(
            f"QScrollArea{{background:#111111;border:none;}}"
        )

        self._mixer = SessionMixer()
        self._mixer.volume_changed.connect(self.mixer_volume_changed.emit)
        self._mixer.mute_toggled.connect(self.mixer_mute_toggled.emit)
        self._mixer.solo_toggled.connect(self.mixer_solo_toggled.emit)
        self._mixer.pan_changed.connect(self.mixer_pan_changed.emit)
        self._mixer_scroll.setWidget(self._mixer)

        bottom.addWidget(self._mixer_scroll, 1)

        # Master channel
        self._master = MasterChannel()
        bottom.addWidget(self._master)

        root.addLayout(bottom)

        # ---- Sync horizontal scrolling between clip grid and mixer ----
        self._clip_scroll.horizontalScrollBar().valueChanged.connect(
            self._mixer_scroll.horizontalScrollBar().setValue
        )
        self._mixer_scroll.horizontalScrollBar().valueChanged.connect(
            self._clip_scroll.horizontalScrollBar().setValue
        )

    # -------------------------------------------------------------- public API

    def set_project(self, project_state: ProjectState):
        """Load a project and rebuild the entire view."""
        self._project = project_state
        self.refresh()
        if project_state.tracks:
            self._on_track_selected(0)

    def get_selected_track(self) -> int:
        """Return the currently selected track index."""
        return self._selected_track

    def update_playback_state(self, track_idx: int, clip_idx: int, state: str):
        """Update visual playback state: 'playing', 'triggered', 'stopped'."""
        if state == "playing":
            self._clip_grid.set_playback_state(track_idx, clip_idx, True)
        elif state == "triggered":
            slot = self._clip_grid.get_slot(track_idx, clip_idx)
            if slot:
                slot.set_triggered()
        else:
            self._clip_grid.set_playback_state(track_idx, clip_idx, False)

    def update_meters(self, levels: list):
        """Update VU meter levels on mixer strips."""
        if hasattr(self._mixer, 'update_meters'):
            self._mixer.update_meters(levels)

    def refresh(self):
        """Rebuild all sub-widgets from the current project state."""
        if self._project is None:
            return

        tracks = self._project.tracks

        self._header_bar.rebuild(tracks, self._selected_track)
        self._clip_grid.rebuild(tracks, NUM_SCENES)
        self._mixer.rebuild(tracks)

        # Update mixer scroll widget size
        total_w = len(tracks) * MIXER_STRIP_WIDTH + 40
        self._mixer.setFixedWidth(total_w)

    # -------------------------------------------------------------- slots

    def _on_track_selected(self, idx: int):
        self._selected_track = idx
        self._header_bar.set_selected(idx)
        self.track_selected.emit(idx)

    def _on_clip_selected(self, track_idx: int, scene_idx: int):
        if track_idx != self._selected_track:
            self._on_track_selected(track_idx)

    def _on_clip_launched(self, track_idx: int, scene_idx: int):
        self.update_playback_state(track_idx, scene_idx, "playing")

    def _on_clip_double_clicked(self, track_idx: int, scene_idx: int):
        self.clip_opened.emit(track_idx, scene_idx)

    def _on_scene_launched(self, scene_idx: int):
        """Launch all clips in the given scene row."""
        if self._project is None:
            return
        for t_idx in range(len(self._project.tracks)):
            slot = self._clip_grid.get_slot(t_idx, scene_idx)
            if slot and slot._state != ClipSlot.EMPTY:
                self.update_playback_state(t_idx, scene_idx, "playing")

    def _on_track_renamed(self, idx: int, name: str):
        if self._project and 0 <= idx < len(self._project.tracks):
            self._project.modified = True

    def _add_track(self):
        if self._project is None:
            return
        idx = len(self._project.tracks)
        color = TRACK_COLORS[idx % len(TRACK_COLORS)]
        new_track = Track(
            name=f"Track {idx + 1}",
            channel=min(idx, 15),
            color=color,
        )
        self._project.tracks.append(new_track)
        self._project.modified = True
        self.refresh()
        self._on_track_selected(idx)
        self.track_added.emit()

    def _remove_track(self, idx: int):
        if self._project is None or not self._project.tracks:
            return
        if 0 <= idx < len(self._project.tracks):
            self._project.tracks.pop(idx)
            self._project.modified = True
            self.refresh()
            if self._project.tracks:
                new_sel = min(idx, len(self._project.tracks) - 1)
                self._on_track_selected(new_sel)
            self.track_removed.emit(idx)
