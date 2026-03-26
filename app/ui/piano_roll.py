"""
Piano Roll Widget — full-featured MIDI note editor modeled after Ableton Live.

Provides a scrollable/zoomable grid for editing MIDI notes with piano keyboard
reference, velocity editing, snap-to-grid, and standard DAW interactions.
"""
from __future__ import annotations

import copy
from typing import Optional

from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsLineItem,
    QGraphicsSimpleTextItem, QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QLabel, QFrame, QToolButton, QSplitter, QGraphicsItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QWheelEvent, QMouseEvent,
    QKeyEvent, QCursor, QPainterPath,
)

from core.models import (
    Note, Track, ProjectState, TICKS_PER_BEAT, NOTE_NAMES, midi_to_note_name,
)
from config import (
    COLORS, PIANO_KEY_WIDTH, NOTE_HEIGHT, BEAT_WIDTH, SNAP_VALUES,
    MIN_BEAT_WIDTH, MAX_BEAT_WIDTH, MIN_NOTE_HEIGHT, MAX_NOTE_HEIGHT,
    VELOCITY_BAR_HEIGHT,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BLACK_KEYS = {1, 3, 6, 8, 10}  # pitch-class indices of black keys


def _is_black_key(pitch: int) -> bool:
    return (pitch % 12) in _BLACK_KEYS


def _velocity_color(base: QColor, velocity: int) -> QColor:
    """Return *base* tinted by velocity (0-127). Louder = brighter / more saturated."""
    factor = 0.35 + 0.65 * (velocity / 127.0)
    return QColor(
        min(int(base.red() * factor + 40 * (1 - factor)), 255),
        min(int(base.green() * factor + 40 * (1 - factor)), 255),
        min(int(base.blue() * factor + 40 * (1 - factor)), 255),
        220,
    )


def _velocity_bar_color(velocity: int) -> QColor:
    """Gradient: low = blue, mid = green, high = red."""
    t = velocity / 127.0
    if t < 0.5:
        s = t * 2.0
        return QColor(int(40 * (1 - s) + 34 * s), int(120 * (1 - s) + 197 * s), int(220 * (1 - s) + 94 * s))
    s = (t - 0.5) * 2.0
    return QColor(int(34 * (1 - s) + 233 * s), int(197 * (1 - s) + 69 * s), int(94 * (1 - s) + 96 * s))


# ======================================================================
# NoteItem — single editable MIDI note rectangle in the scene
# ======================================================================

class NoteItem(QGraphicsRectItem):
    """Visual representation of a single MIDI note on the grid."""

    RESIZE_HANDLE_W = 4  # pixels at right edge for resize cursor

    def __init__(self, note: Note, beat_width: float, note_height: float,
                 base_color: QColor, parent=None):
        super().__init__(parent)
        self.note = note
        self._beat_width = beat_width
        self._note_height = note_height
        self._base_color = base_color
        self._selected = False
        self._hovered = False

        self.setAcceptHoverEvents(True)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self._sync_geometry()

    # -- geometry helpers ------------------------------------------------

    def _sync_geometry(self):
        """Recompute position & size from the underlying Note model."""
        x = (self.note.start_tick / TICKS_PER_BEAT) * self._beat_width
        y = (127 - self.note.pitch) * self._note_height
        w = max((self.note.duration_ticks / TICKS_PER_BEAT) * self._beat_width, 4)
        h = self._note_height
        self.setRect(0, 0, w, h)
        self.setPos(x, y)

    def update_metrics(self, beat_width: float, note_height: float):
        self._beat_width = beat_width
        self._note_height = note_height
        self._sync_geometry()

    # -- painting --------------------------------------------------------

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        path = QPainterPath()
        path.addRoundedRect(rect, 2.0, 2.0)

        # Fill — velocity-shaded base color
        fill = _velocity_color(self._base_color, self.note.velocity)
        if self._hovered:
            fill = fill.lighter(120)
        painter.fillPath(path, QBrush(fill))

        # Border
        if self._selected or self.isSelected():
            pen = QPen(QColor(COLORS["note_selected"]), 1.5)
        else:
            pen = QPen(fill.darker(140), 0.5)
        painter.setPen(pen)
        painter.drawPath(path)

        # Resize handle subtle indicator
        if rect.width() > 12:
            hx = rect.right() - self.RESIZE_HANDLE_W
            painter.setPen(QPen(QColor(255, 255, 255, 35), 0.5))
            painter.drawLine(QPointF(hx, rect.top() + 2), QPointF(hx, rect.bottom() - 2))

    # -- hover -----------------------------------------------------------

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()
        super().hoverLeaveEvent(event)

    def hoverMoveEvent(self, event):
        if event.pos().x() >= self.rect().width() - self.RESIZE_HANDLE_W:
            self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().hoverMoveEvent(event)

    def is_on_resize_handle(self, local_pos: QPointF) -> bool:
        return local_pos.x() >= self.rect().width() - self.RESIZE_HANDLE_W


# ======================================================================
# PianoKeyboard — vertical keyboard on the left side
# ======================================================================

class PianoKeyboard(QWidget):
    """128-key vertical piano keyboard drawn from C-1 (bottom) to G9 (top)."""

    note_preview = pyqtSignal(int)  # pitch

    def __init__(self, parent=None):
        super().__init__(parent)
        self._note_height = NOTE_HEIGHT
        self._pressed_keys: set[int] = set()
        self.setFixedWidth(PIANO_KEY_WIDTH)
        self.setMinimumHeight(128 * self._note_height)
        self._font = QFont("Segoe UI", 7)

    @property
    def note_height(self) -> float:
        return self._note_height

    @note_height.setter
    def note_height(self, value: float):
        self._note_height = value
        self.setMinimumHeight(int(128 * value))
        self.update()

    def set_pressed_keys(self, keys: set[int]):
        self._pressed_keys = keys
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter as _P
        p = _P(self)
        p.setRenderHint(_P.RenderHint.Antialiasing, False)
        p.setFont(self._font)
        w = self.width()
        nh = self._note_height

        white_brush = QBrush(QColor(COLORS["white_key"]))
        black_brush = QBrush(QColor(COLORS["black_key"]))
        pressed_brush = QBrush(QColor(COLORS["key_pressed"]))
        label_pen = QPen(QColor(COLORS["key_label"]))
        border_pen = QPen(QColor(COLORS["border"]), 0.5)

        for pitch in range(128):
            row = 127 - pitch
            y = int(row * nh)
            h = max(int(nh), 1)
            is_black = _is_black_key(pitch)

            if pitch in self._pressed_keys:
                p.fillRect(0, y, w, h, pressed_brush)
            elif is_black:
                bw = int(w * 0.6)
                p.fillRect(0, y, w, h, QBrush(QColor(COLORS["bg_dark"])))
                p.fillRect(0, y, bw, h, black_brush)
            else:
                p.fillRect(0, y, w, h, white_brush)

            # subtle separator between keys
            p.setPen(border_pen)
            p.drawLine(0, y + h - 1, w, y + h - 1)

            # octave C label
            if pitch % 12 == 0:
                p.setPen(QPen(QColor(COLORS["octave_line"]), 1))
                p.drawLine(0, y + h - 1, w, y + h - 1)
                p.setPen(label_pen)
                label = midi_to_note_name(pitch)
                p.drawText(2, y + h - 2, label)

        p.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pitch = 127 - int(event.position().y() / self._note_height)
            pitch = max(0, min(127, pitch))
            self.note_preview.emit(pitch)
        super().mousePressEvent(event)


# ======================================================================
# VelocityBar — bottom velocity editor
# ======================================================================

class VelocityBar(QWidget):
    """Velocity editor: vertical bars for each note, click/drag to adjust."""

    velocity_changed = pyqtSignal(object, int)  # (NoteItem, new_velocity)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(VELOCITY_BAR_HEIGHT)
        self._note_items: list[NoteItem] = []
        self._beat_width: float = BEAT_WIDTH
        self._scroll_x: int = 0
        self._dragging: Optional[NoteItem] = None

    def set_notes(self, items: list[NoteItem]):
        self._note_items = items
        self.update()

    def set_scroll_x(self, x: int):
        self._scroll_x = x
        self.update()

    def set_beat_width(self, bw: float):
        self._beat_width = bw
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter as _P
        p = _P(self)
        p.setRenderHint(_P.RenderHint.Antialiasing, True)
        h = self.height()

        # background
        p.fillRect(self.rect(), QBrush(QColor(COLORS["bg_darkest"])))

        # 127-line reference
        p.setPen(QPen(QColor(COLORS["grid_beat"]), 0.5))
        p.drawLine(0, 1, self.width(), 1)

        bar_w = max((TICKS_PER_BEAT * 0.25 / TICKS_PER_BEAT) * self._beat_width, 3)
        for item in self._note_items:
            x = item.scenePos().x() - self._scroll_x + PIANO_KEY_WIDTH
            vel = item.note.velocity
            bar_h = int((vel / 127.0) * (h - 4))
            color = _velocity_bar_color(vel)
            if item.isSelected():
                color = color.lighter(130)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(QRectF(x, h - bar_h - 2, max(bar_w, 3), bar_h), 1, 1)

        p.end()

    # -- mouse interaction for velocity editing --------------------------

    def _item_at_x(self, x: float) -> Optional[NoteItem]:
        for item in self._note_items:
            ix = item.scenePos().x() - self._scroll_x + PIANO_KEY_WIDTH
            iw = item.rect().width()
            if ix <= x <= ix + max(iw, 6):
                return item
        return None

    def _vel_from_y(self, y: float) -> int:
        h = self.height() - 4
        v = int((1.0 - (y - 2) / h) * 127)
        return max(0, min(127, v))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self._item_at_x(event.position().x())
            if item:
                self._dragging = item
                vel = self._vel_from_y(event.position().y())
                self.velocity_changed.emit(item, vel)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            vel = self._vel_from_y(event.position().y())
            self.velocity_changed.emit(self._dragging, vel)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._dragging = None
        super().mouseReleaseEvent(event)


# ======================================================================
# PianoRollView — main QGraphicsView for editing notes
# ======================================================================

class PianoRollView(QGraphicsView):
    """Scrollable, zoomable MIDI note editing grid."""

    note_added = pyqtSignal(object)       # Note
    note_removed = pyqtSignal(object)     # Note
    note_modified = pyqtSignal(object)    # Note
    notes_selected = pyqtSignal(list)     # list[Note]
    selection_changed = pyqtSignal()
    playhead_moved = pyqtSignal(int)      # tick
    scroll_changed = pyqtSignal(int)      # horizontal pixel offset

    copy_requested = pyqtSignal()
    paste_requested = pyqtSignal()
    cut_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # State
        self._track: Optional[Track] = None
        self._project: Optional[ProjectState] = None
        self._note_items: list[NoteItem] = []
        self._beat_width: float = BEAT_WIDTH
        self._note_height: float = NOTE_HEIGHT
        self._snap_value: float = 1.0  # beats
        self._tool_mode: str = "draw"  # "draw" or "select"
        self._base_color = QColor(COLORS["note_default"])
        self._total_beats: int = 64

        # Interaction state
        self._drawing = False
        self._draw_start: Optional[QPointF] = None
        self._draw_item: Optional[NoteItem] = None
        self._resizing = False
        self._resize_item: Optional[NoteItem] = None
        self._resize_start_x: float = 0
        self._resize_orig_dur: int = 0
        self._moving = False
        self._move_items: list[NoteItem] = []
        self._move_origin: QPointF = QPointF()
        self._move_offsets: list[tuple[float, float]] = []

        # Playhead
        self._playhead_line: Optional[QGraphicsLineItem] = None
        self._playhead_tick: int = 0

        # Rendering
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setBackgroundBrush(QBrush(QColor(COLORS["bg_darkest"])))
        self.setFrameShape(QFrame.Shape.NoFrame)

        # Forward scroll events
        self.horizontalScrollBar().valueChanged.connect(
            lambda v: self.scroll_changed.emit(v)
        )

    # -- properties ------------------------------------------------------

    @property
    def beat_width(self) -> float:
        return self._beat_width

    @beat_width.setter
    def beat_width(self, v: float):
        self._beat_width = max(MIN_BEAT_WIDTH, min(MAX_BEAT_WIDTH, v))
        self._rebuild_scene()

    @property
    def note_height(self) -> float:
        return self._note_height

    @note_height.setter
    def note_height(self, v: float):
        self._note_height = max(MIN_NOTE_HEIGHT, min(MAX_NOTE_HEIGHT, v))
        self._rebuild_scene()

    @property
    def snap_value(self) -> float:
        return self._snap_value

    @snap_value.setter
    def snap_value(self, v: float):
        self._snap_value = v

    @property
    def tool_mode(self) -> str:
        return self._tool_mode

    @tool_mode.setter
    def tool_mode(self, v: str):
        self._tool_mode = v
        if v == "select":
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)

    # -- data binding ----------------------------------------------------

    def set_track(self, track: Optional[Track]):
        self._track = track
        if track:
            self._base_color = QColor(track.color)
        self._rebuild_scene()

    def set_project(self, project: Optional[ProjectState]):
        self._project = project
        if project:
            self._total_beats = max(int(project.total_beats) + 16, 64)
        self._rebuild_scene()

    def get_note_items(self) -> list[NoteItem]:
        return list(self._note_items)

    def get_selected_notes(self) -> list[Note]:
        return [item.note for item in self._note_items if item.isSelected()]

    # -- scene management ------------------------------------------------

    def _rebuild_scene(self):
        """Clear and redraw the entire scene: grid, notes, playhead."""
        self._scene.clear()
        self._note_items.clear()
        self._playhead_line = None

        bw = self._beat_width
        nh = self._note_height
        ts_num = 4
        if self._project:
            ts_num = self._project.time_signature.numerator

        total_beats = self._total_beats
        scene_w = total_beats * bw
        scene_h = 128 * nh
        self._scene.setSceneRect(0, 0, scene_w, scene_h)

        self._draw_grid(scene_w, scene_h, bw, nh, ts_num, total_beats)
        self._add_track_notes()
        self._create_playhead(scene_h)

    def _draw_grid(self, scene_w: float, scene_h: float, bw: float,
                   nh: float, ts_num: int, total_beats: int):
        """Draw pitch rows and beat/bar grid lines."""
        # -- pitch row backgrounds (alternating white/black key shading) --
        row_white = QColor(COLORS["bg_dark"])
        row_black = QColor(COLORS["bg_darkest"])
        octave_pen = QPen(QColor(COLORS["octave_line"]), 0.5)
        for pitch in range(128):
            row = 127 - pitch
            y = row * nh
            color = row_black if _is_black_key(pitch) else row_white
            rect = self._scene.addRect(QRectF(0, y, scene_w, nh),
                                       QPen(Qt.PenStyle.NoPen), QBrush(color))
            rect.setZValue(-20)
            # octave separator
            if pitch % 12 == 0:
                line = self._scene.addLine(0, y + nh, scene_w, y + nh, octave_pen)
                line.setZValue(-15)

        # -- vertical beat / bar lines ------------------------------------
        beat_pen = QPen(QColor(COLORS["grid_beat"]), 0.5)
        bar_pen = QPen(QColor(COLORS["grid_bar"]), 1.0)
        label_font = QFont("Segoe UI", 7)
        label_color = QColor(COLORS["text_dim"])

        for beat in range(total_beats + 1):
            x = beat * bw
            is_bar = (beat % ts_num == 0)
            pen = bar_pen if is_bar else beat_pen
            line = self._scene.addLine(x, 0, x, scene_h, pen)
            line.setZValue(-10)

            # sub-beat lines when zoomed in enough
            if bw >= 60 and not is_bar:
                sub_pen = QPen(QColor(COLORS["grid_line"]), 0.3)
                for sub in range(1, 4):
                    sx = x + sub * (bw / 4)
                    sl = self._scene.addLine(sx, 0, sx, scene_h, sub_pen)
                    sl.setZValue(-12)

            # bar number labels
            if is_bar:
                bar_num = beat // ts_num + 1
                txt = self._scene.addSimpleText(str(bar_num), label_font)
                txt.setBrush(QBrush(label_color))
                txt.setPos(x + 3, 2)
                txt.setZValue(5)

    def _add_track_notes(self):
        if not self._track:
            return
        for note in self._track.notes:
            item = NoteItem(note, self._beat_width, self._note_height,
                            self._base_color)
            self._scene.addItem(item)
            self._note_items.append(item)

    def _create_playhead(self, scene_h: float):
        pen = QPen(QColor(COLORS["playhead"]), 1.5)
        x = (self._playhead_tick / TICKS_PER_BEAT) * self._beat_width
        self._playhead_line = self._scene.addLine(x, 0, x, scene_h, pen)
        self._playhead_line.setZValue(100)

    def update_playhead(self, tick: int):
        self._playhead_tick = tick
        if self._playhead_line:
            x = (tick / TICKS_PER_BEAT) * self._beat_width
            h = 128 * self._note_height
            self._playhead_line.setLine(x, 0, x, h)
            # auto-scroll to follow playhead
            vp = self.viewport().width()
            sx = self.horizontalScrollBar().value()
            if x < sx or x > sx + vp - 40:
                self.horizontalScrollBar().setValue(int(x - vp * 0.25))

    # -- snapping helpers ------------------------------------------------

    def _snap_tick(self, tick: float) -> int:
        if self._snap_value <= 0:
            return int(tick)
        snap_ticks = self._snap_value * TICKS_PER_BEAT
        return int(round(tick / snap_ticks) * snap_ticks)

    def _pos_to_tick(self, x: float) -> float:
        return (x / self._beat_width) * TICKS_PER_BEAT

    def _pos_to_pitch(self, y: float) -> int:
        p = 127 - int(y / self._note_height)
        return max(0, min(127, p))

    # -- add / remove notes ----------------------------------------------

    def _add_note_at(self, tick: int, pitch: int, duration: int = 0,
                     velocity: int = 80) -> NoteItem:
        if duration <= 0:
            duration = max(int(self._snap_value * TICKS_PER_BEAT), TICKS_PER_BEAT // 4)
        note = Note(pitch=pitch, velocity=velocity,
                    start_tick=tick, duration_ticks=duration)
        if self._track:
            self._track.add_note(note)
        item = NoteItem(note, self._beat_width, self._note_height,
                        self._base_color)
        self._scene.addItem(item)
        self._note_items.append(item)
        self.note_added.emit(note)
        return item

    def _remove_note_item(self, item: NoteItem):
        if item in self._note_items:
            self._note_items.remove(item)
        if self._track and item.note in self._track.notes:
            self._track.remove_note(item.note)
        self._scene.removeItem(item)
        self.note_removed.emit(item.note)

    def delete_selected(self):
        selected = [i for i in self._note_items if i.isSelected()]
        for item in selected:
            self._remove_note_item(item)

    def select_all(self):
        for item in self._note_items:
            item.setSelected(True)
        self._emit_selection()

    def deselect_all(self):
        for item in self._note_items:
            item.setSelected(False)
        self._emit_selection()

    def _emit_selection(self):
        sel = self.get_selected_notes()
        self.notes_selected.emit(sel)
        self.selection_changed.emit()

    # -- transpose -------------------------------------------------------

    def _transpose_selected(self, semitones: int):
        for item in self._note_items:
            if item.isSelected():
                new_pitch = item.note.pitch + semitones
                if 0 <= new_pitch <= 127:
                    item.note.pitch = new_pitch
                    item.update_metrics(self._beat_width, self._note_height)
                    self.note_modified.emit(item.note)

    # ====================================================================
    # Mouse event handling
    # ====================================================================

    def mousePressEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.position().toPoint())
        item_at = self._scene.itemAt(scene_pos, self.transform())

        # Right-click to delete
        if event.button() == Qt.MouseButton.RightButton:
            if isinstance(item_at, NoteItem):
                self._remove_note_item(item_at)
            return

        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        note_item = item_at if isinstance(item_at, NoteItem) else None

        # ---------- DRAW TOOL -------------------------------------------
        if self._tool_mode == "draw":
            if note_item:
                # Clicked an existing note — check for resize handle
                local = note_item.mapFromScene(scene_pos)
                if note_item.is_on_resize_handle(local):
                    self._start_resize(note_item, scene_pos)
                else:
                    # start moving
                    self._start_move([note_item], scene_pos)
            else:
                # Draw a new note
                tick = self._snap_tick(self._pos_to_tick(scene_pos.x()))
                pitch = self._pos_to_pitch(scene_pos.y())
                item = self._add_note_at(tick, pitch)
                self._drawing = True
                self._draw_start = scene_pos
                self._draw_item = item
            return

        # ---------- SELECT TOOL -----------------------------------------
        if self._tool_mode == "select":
            if note_item:
                local = note_item.mapFromScene(scene_pos)
                if note_item.is_on_resize_handle(local):
                    self._start_resize(note_item, scene_pos)
                    return

                modifiers = event.modifiers()
                if modifiers & Qt.KeyboardModifier.ShiftModifier:
                    note_item.setSelected(not note_item.isSelected())
                else:
                    if not note_item.isSelected():
                        self.deselect_all()
                        note_item.setSelected(True)
                    selected = [i for i in self._note_items if i.isSelected()]
                    self._start_move(selected, scene_pos)
                self._emit_selection()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.position().toPoint())

        # Drawing — extend note duration by dragging right
        if self._drawing and self._draw_item:
            start_tick = self._draw_item.note.start_tick
            cur_tick = self._snap_tick(self._pos_to_tick(scene_pos.x()))
            duration = max(cur_tick - start_tick,
                          int(self._snap_value * TICKS_PER_BEAT) if self._snap_value > 0 else TICKS_PER_BEAT // 4)
            self._draw_item.note.duration_ticks = duration
            self._draw_item.update_metrics(self._beat_width, self._note_height)
            return

        # Resizing
        if self._resizing and self._resize_item:
            dx = scene_pos.x() - self._resize_start_x
            dt = (dx / self._beat_width) * TICKS_PER_BEAT
            new_dur = max(int(self._resize_orig_dur + dt),
                         int(self._snap_value * TICKS_PER_BEAT) if self._snap_value > 0 else TICKS_PER_BEAT // 8)
            if self._snap_value > 0:
                snap_t = self._snap_value * TICKS_PER_BEAT
                new_dur = int(round(new_dur / snap_t) * snap_t)
                new_dur = max(new_dur, int(snap_t))
            self._resize_item.note.duration_ticks = new_dur
            self._resize_item.update_metrics(self._beat_width, self._note_height)
            return

        # Moving
        if self._moving and self._move_items:
            dx = scene_pos.x() - self._move_origin.x()
            dy = scene_pos.y() - self._move_origin.y()
            for i, item in enumerate(self._move_items):
                ox, oy = self._move_offsets[i]
                new_x = ox + dx
                new_y = oy + dy
                new_tick = self._snap_tick(self._pos_to_tick(new_x))
                new_pitch = self._pos_to_pitch(new_y)
                new_tick = max(0, new_tick)
                new_pitch = max(0, min(127, new_pitch))
                item.note.start_tick = new_tick
                item.note.pitch = new_pitch
                item.update_metrics(self._beat_width, self._note_height)
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._drawing and self._draw_item:
            self._drawing = False
            self.note_modified.emit(self._draw_item.note)
            self._draw_item = None
            self._draw_start = None

        if self._resizing and self._resize_item:
            self._resizing = False
            self.note_modified.emit(self._resize_item.note)
            self._resize_item = None

        if self._moving:
            self._moving = False
            for item in self._move_items:
                self.note_modified.emit(item.note)
            self._move_items.clear()
            self._move_offsets.clear()

        self._emit_selection()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Double-click selects all notes at the same pitch."""
        scene_pos = self.mapToScene(event.position().toPoint())
        pitch = self._pos_to_pitch(scene_pos.y())
        for item in self._note_items:
            item.setSelected(item.note.pitch == pitch)
        self._emit_selection()

    # -- drag helpers ----------------------------------------------------

    def _start_resize(self, item: NoteItem, scene_pos: QPointF):
        self._resizing = True
        self._resize_item = item
        self._resize_start_x = scene_pos.x()
        self._resize_orig_dur = item.note.duration_ticks

    def _start_move(self, items: list[NoteItem], scene_pos: QPointF):
        self._moving = True
        self._move_items = items
        self._move_origin = scene_pos
        self._move_offsets = [(item.scenePos().x(), item.scenePos().y()) for item in items]

    # ====================================================================
    # Keyboard shortcuts
    # ====================================================================

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        mod = event.modifiers()

        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
            return
        if key == Qt.Key.Key_A and mod & Qt.KeyboardModifier.ControlModifier:
            self.select_all()
            return
        if key == Qt.Key.Key_D and mod & Qt.KeyboardModifier.ControlModifier:
            self.deselect_all()
            return
        if key == Qt.Key.Key_Up:
            semi = 12 if mod & Qt.KeyboardModifier.ShiftModifier else 1
            self._transpose_selected(semi)
            return
        if key == Qt.Key.Key_Down:
            semi = -12 if mod & Qt.KeyboardModifier.ShiftModifier else -1
            self._transpose_selected(semi)
            return
        if mod & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_C:
                self.copy_requested.emit()
                return
            if key == Qt.Key.Key_V:
                self.paste_requested.emit()
                return
            if key == Qt.Key.Key_X:
                self.cut_requested.emit()
                return
        super().keyPressEvent(event)

    # ====================================================================
    # Zoom via mouse wheel
    # ====================================================================

    def wheelEvent(self, event: QWheelEvent):
        mod = event.modifiers()
        delta = event.angleDelta().y()
        if not (mod & Qt.KeyboardModifier.ControlModifier):
            super().wheelEvent(event)
            return

        factor = 1.15 if delta > 0 else 1 / 1.15

        if mod & Qt.KeyboardModifier.ShiftModifier:
            # Vertical zoom
            self._note_height = max(MIN_NOTE_HEIGHT,
                                    min(MAX_NOTE_HEIGHT, self._note_height * factor))
            self._rebuild_scene()
        else:
            # Horizontal zoom
            self._beat_width = max(MIN_BEAT_WIDTH,
                                   min(MAX_BEAT_WIDTH, self._beat_width * factor))
            self._rebuild_scene()

        event.accept()

    # -- public zoom helpers ---------------------------------------------

    def zoom_in(self):
        self.beat_width = self._beat_width * 1.25

    def zoom_out(self):
        self.beat_width = self._beat_width / 1.25

    def zoom_fit(self):
        if not self._track or not self._track.notes:
            return
        max_tick = max(n.end_tick for n in self._track.notes)
        if max_tick <= 0:
            return
        vp_w = self.viewport().width()
        self.beat_width = (vp_w / (max_tick / TICKS_PER_BEAT)) * 0.95


# ======================================================================
# PianoRollWidget — top-level container assembling all parts
# ======================================================================

class PianoRollWidget(QWidget):
    """Complete piano roll editor widget combining keyboard, grid, and velocity bar."""

    note_added = pyqtSignal(object)
    note_removed = pyqtSignal(object)
    note_modified = pyqtSignal(object)
    notes_selected = pyqtSignal(list)
    selection_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._track: Optional[Track] = None
        self._project: Optional[ProjectState] = None

        self._init_ui()
        self._connect_signals()

        # Periodic sync timer for velocity bar / keyboard highlights
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(100)
        self._sync_timer.timeout.connect(self._sync_panels)
        self._sync_timer.start()

    # -- UI construction -------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Toolbar ---------------------------------------------------
        toolbar = self._build_toolbar()
        root.addWidget(toolbar)

        # ---- Splitter: [keyboard + grid] / [velocity bar] ---------------
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.setHandleWidth(3)

        # Top area: keyboard + piano roll view
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        self._keyboard = PianoKeyboard()
        self._view = PianoRollView()

        top_layout.addWidget(self._keyboard)
        top_layout.addWidget(self._view, 1)

        splitter.addWidget(top_widget)

        # Bottom: velocity bar
        self._velocity_bar = VelocityBar()
        splitter.addWidget(self._velocity_bar)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        root.addWidget(splitter, 1)

        self.setStyleSheet(
            f"background-color: {COLORS['bg_darkest']}; color: {COLORS['text_primary']};"
        )

    def _build_toolbar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(30)
        bar.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg_header']}; border-bottom: 1px solid {COLORS['border']}; }}"
            f"QLabel {{ color: {COLORS['text_secondary']}; font-size: 11px; }}"
            f"QComboBox {{ background: {COLORS['bg_input']}; color: {COLORS['text_primary']};"
            f"  border: 1px solid {COLORS['border']}; padding: 1px 4px; font-size: 11px; }}"
            f"QToolButton {{ background: {COLORS['bg_mid']}; color: {COLORS['text_primary']};"
            f"  border: 1px solid {COLORS['border']}; padding: 2px 8px; font-size: 11px; }}"
            f"QToolButton:checked {{ background: {COLORS['accent']}; }}"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        # Tool mode buttons
        self._btn_draw = QToolButton()
        self._btn_draw.setText("Draw")
        self._btn_draw.setCheckable(True)
        self._btn_draw.setChecked(True)
        self._btn_draw.clicked.connect(lambda: self._set_tool("draw"))

        self._btn_select = QToolButton()
        self._btn_select.setText("Select")
        self._btn_select.setCheckable(True)
        self._btn_select.clicked.connect(lambda: self._set_tool("select"))

        layout.addWidget(QLabel("Tool:"))
        layout.addWidget(self._btn_draw)
        layout.addWidget(self._btn_select)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['separator']};")
        layout.addWidget(sep)

        # Snap selector
        layout.addWidget(QLabel("Snap:"))
        self._snap_combo = QComboBox()
        self._snap_combo.addItems(list(SNAP_VALUES.keys()))
        self._snap_combo.setCurrentText("1/4")
        self._snap_combo.currentTextChanged.connect(self._on_snap_changed)
        layout.addWidget(self._snap_combo)

        # Quantize button
        btn_quantize = QToolButton()
        btn_quantize.setText("Quantize")
        btn_quantize.clicked.connect(self._quantize_selected)
        layout.addWidget(btn_quantize)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet(f"color: {COLORS['separator']};")
        layout.addWidget(sep2)

        # Zoom buttons
        btn_zin = QToolButton()
        btn_zin.setText("+")
        btn_zin.setFixedWidth(24)
        btn_zin.clicked.connect(lambda: self._view.zoom_in())

        btn_zout = QToolButton()
        btn_zout.setText("\u2212")  # minus sign
        btn_zout.setFixedWidth(24)
        btn_zout.clicked.connect(lambda: self._view.zoom_out())

        btn_zfit = QToolButton()
        btn_zfit.setText("Fit")
        btn_zfit.clicked.connect(lambda: self._view.zoom_fit())

        layout.addWidget(QLabel("Zoom:"))
        layout.addWidget(btn_zout)
        layout.addWidget(btn_zin)
        layout.addWidget(btn_zfit)

        layout.addStretch()
        return bar

    # -- signal wiring ---------------------------------------------------

    def _connect_signals(self):
        v = self._view

        # Forward signals
        v.note_added.connect(self.note_added)
        v.note_removed.connect(self.note_removed)
        v.note_modified.connect(self.note_modified)
        v.notes_selected.connect(self.notes_selected)
        v.selection_changed.connect(self.selection_changed)

        # Sync vertical scroll between keyboard and view
        v.verticalScrollBar().valueChanged.connect(self._sync_keyboard_scroll)

        # Sync velocity bar horizontal scroll
        v.scroll_changed.connect(self._velocity_bar.set_scroll_x)

        # Velocity editing
        self._velocity_bar.velocity_changed.connect(self._on_velocity_changed)

        # Keyboard preview
        self._keyboard.note_preview.connect(self._on_key_preview)

    def _sync_keyboard_scroll(self, value: int):
        """Scroll the keyboard widget to match the view's vertical scroll."""
        # Translate QGraphicsView scroll to keyboard widget offset via moving
        # the keyboard within a scroll-aligned parent. We move the keyboard
        # using a simple position offset.
        total_h = int(128 * self._view.note_height)
        self._keyboard.note_height = self._view.note_height
        # We scroll the keyboard by moving it upward
        max_scroll = max(total_h - self._keyboard.parentWidget().height(), 0)
        ratio = value / max(self._view.verticalScrollBar().maximum(), 1)
        self._keyboard.move(0, -int(ratio * max_scroll))

    def _sync_panels(self):
        """Periodic sync of velocity bar and keyboard highlights."""
        self._velocity_bar.set_notes(self._view.get_note_items())
        self._velocity_bar.set_beat_width(self._view.beat_width)
        # Highlight keys for selected notes
        selected = self._view.get_selected_notes()
        self._keyboard.set_pressed_keys({n.pitch for n in selected})

    # -- toolbar callbacks -----------------------------------------------

    def _set_tool(self, mode: str):
        self._view.tool_mode = mode
        self._btn_draw.setChecked(mode == "draw")
        self._btn_select.setChecked(mode == "select")

    def _on_snap_changed(self, text: str):
        self._view.snap_value = SNAP_VALUES.get(text, 1.0)

    def _quantize_selected(self):
        """Snap selected notes' start times to the current grid."""
        snap = self._view.snap_value
        if snap <= 0:
            return
        snap_ticks = int(snap * TICKS_PER_BEAT)
        for item in self._view.get_note_items():
            if item.isSelected():
                item.note.start_tick = int(round(item.note.start_tick / snap_ticks) * snap_ticks)
                item.update_metrics(self._view.beat_width, self._view.note_height)
                self._view.note_modified.emit(item.note)

    def _on_velocity_changed(self, item: NoteItem, velocity: int):
        item.note.velocity = velocity
        item.update()
        self._velocity_bar.update()
        self._view.note_modified.emit(item.note)

    def _on_key_preview(self, pitch: int):
        """Keyboard key clicked — could trigger sound preview (handled externally)."""
        pass  # parent app can connect to keyboard.note_preview

    # -- public API ------------------------------------------------------

    @property
    def current_track(self) -> Optional[Track]:
        return self._track

    @property
    def snap_value(self) -> float:
        return self._view.snap_value

    @property
    def tool_mode(self) -> str:
        return self._view.tool_mode

    def set_track(self, track: Optional[Track], track_index: int = 0):
        self._track = track
        self._view.set_track(track)

    def set_project(self, project_state: Optional[ProjectState]):
        self._project = project_state
        self._view.set_project(project_state)

    def update_playhead(self, tick: int):
        self._view.update_playhead(tick)

    def get_selected_notes(self) -> list[Note]:
        return self._view.get_selected_notes()

    def select_all(self):
        self._view.select_all()

    def deselect_all(self):
        self._view.deselect_all()

    def zoom_in(self):
        self._view.zoom_in()

    def zoom_out(self):
        self._view.zoom_out()

    def zoom_fit(self):
        self._view.zoom_fit()

    def set_snap(self, value: float):
        """Set the snap grid value in beats."""
        self._view.snap_value = value
        # Update combo box to match
        from config import SNAP_VALUES
        for name, val in SNAP_VALUES.items():
            if abs(val - value) < 0.001:
                self._snap_combo.setCurrentText(name)
                break

    def set_playhead(self, tick: int):
        """Alias for update_playhead."""
        self.update_playhead(tick)
