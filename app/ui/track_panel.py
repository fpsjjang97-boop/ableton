"""
Track Panel and Arrangement View widgets.

Provides the Ableton-style arrangement view with track headers on the left
and clip/note overview on the right, synchronized scrolling, playhead,
loop regions, and full track management.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QMenu, QSlider, QToolButton, QSizePolicy, QSpacerItem,
    QColorDialog, QInputDialog, QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QMimeData, QPoint
from PyQt6.QtGui import (
    QColor, QPainter, QFont, QIcon, QPen, QBrush,
    QMouseEvent, QDragEnterEvent, QDropEvent, QAction,
)

from core.models import Track, ProjectState, TRACK_COLORS, Note, TICKS_PER_BEAT
from config import COLORS, DEFAULT_TRACK_HEIGHT


# ---------------------------------------------------------------------------
#  GM instrument family labels (first 8 families x 8 programs = 128)
# ---------------------------------------------------------------------------
_GM_FAMILIES = [
    "Piano", "Chromatic Perc", "Organ", "Guitar",
    "Bass", "Strings", "Ensemble", "Brass",
    "Reed", "Pipe", "Synth Lead", "Synth Pad",
    "Synth FX", "Ethnic", "Percussive", "SFX",
]


def _gm_instrument_name(program: int) -> str:
    if 0 <= program < 128:
        return _GM_FAMILIES[program // 8]
    return "Unknown"


# Arrangement constants
ARRANGEMENT_BEAT_WIDTH = 24  # pixels per beat in overview
RULER_HEIGHT = 22
HEADER_WIDTH = 220


# =========================================================================
#  TrackHeader — single track header (left column)
# =========================================================================
class TrackHeader(QFrame):
    """Ableton-style track header with name, mute/solo/arm, volume, pan."""

    mute_toggled = pyqtSignal(int)
    solo_toggled = pyqtSignal(int)
    arm_toggled = pyqtSignal(int)
    selected = pyqtSignal(int)
    volume_changed = pyqtSignal(int, int)
    pan_changed = pyqtSignal(int, int)
    rename_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    duplicate_requested = pyqtSignal(int)
    color_changed = pyqtSignal(int, str)

    def __init__(self, index: int, track: Track, parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._track = track
        self._is_selected = False

        self.setFixedHeight(DEFAULT_TRACK_HEIGHT)
        self.setMinimumWidth(HEADER_WIDTH)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._build_ui()
        self._apply_style()

    # ---- UI construction ----

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 4, 0)
        root.setSpacing(0)

        # Color strip
        self._color_strip = QFrame()
        self._color_strip.setFixedWidth(4)
        root.addWidget(self._color_strip)

        # Main content area
        content = QVBoxLayout()
        content.setContentsMargins(6, 4, 2, 4)
        content.setSpacing(2)

        # -- top row: number, name, mute/solo/arm --
        top = QHBoxLayout()
        top.setSpacing(4)

        self._num_label = QLabel(str(self._index + 1))
        self._num_label.setFixedWidth(18)
        self._num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._num_label.setFont(QFont("Segoe UI", 7))
        self._num_label.setStyleSheet(f"color:{COLORS['text_dim']};")
        top.addWidget(self._num_label)

        self._name_label = QLabel(self._track.name)
        self._name_label.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self._name_label.setStyleSheet(f"color:{COLORS['text_primary']};")
        self._name_label.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Preferred)
        top.addWidget(self._name_label)

        btn_size = QSize(20, 18)
        btn_font = QFont("Segoe UI", 7, QFont.Weight.Bold)

        self._mute_btn = QToolButton()
        self._mute_btn.setText("M")
        self._mute_btn.setFixedSize(btn_size)
        self._mute_btn.setFont(btn_font)
        self._mute_btn.setCheckable(True)
        self._mute_btn.setChecked(self._track.muted)
        self._mute_btn.clicked.connect(self._on_mute)
        top.addWidget(self._mute_btn)

        self._solo_btn = QToolButton()
        self._solo_btn.setText("S")
        self._solo_btn.setFixedSize(btn_size)
        self._solo_btn.setFont(btn_font)
        self._solo_btn.setCheckable(True)
        self._solo_btn.setChecked(self._track.solo)
        self._solo_btn.clicked.connect(self._on_solo)
        top.addWidget(self._solo_btn)

        self._arm_btn = QToolButton()
        self._arm_btn.setText("R")
        self._arm_btn.setFixedSize(btn_size)
        self._arm_btn.setFont(btn_font)
        self._arm_btn.setCheckable(True)
        self._arm_btn.clicked.connect(self._on_arm)
        top.addWidget(self._arm_btn)

        content.addLayout(top)

        # -- middle row: instrument label --
        self._instr_label = QLabel(_gm_instrument_name(self._track.instrument))
        self._instr_label.setFont(QFont("Segoe UI", 7))
        self._instr_label.setStyleSheet(f"color:{COLORS['text_secondary']};")
        content.addWidget(self._instr_label)

        # -- bottom row: volume slider + pan slider --
        bottom = QHBoxLayout()
        bottom.setSpacing(4)

        vol_label = QLabel("Vol")
        vol_label.setFont(QFont("Segoe UI", 7))
        vol_label.setStyleSheet(f"color:{COLORS['text_dim']};")
        vol_label.setFixedWidth(20)
        bottom.addWidget(vol_label)

        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 127)
        self._vol_slider.setValue(self._track.volume)
        self._vol_slider.setFixedHeight(14)
        self._vol_slider.valueChanged.connect(self._on_volume)
        bottom.addWidget(self._vol_slider)

        pan_label = QLabel("Pan")
        pan_label.setFont(QFont("Segoe UI", 7))
        pan_label.setStyleSheet(f"color:{COLORS['text_dim']};")
        pan_label.setFixedWidth(22)
        bottom.addWidget(pan_label)

        self._pan_slider = QSlider(Qt.Orientation.Horizontal)
        self._pan_slider.setRange(0, 127)
        self._pan_slider.setValue(self._track.pan)
        self._pan_slider.setFixedHeight(14)
        self._pan_slider.setFixedWidth(48)
        self._pan_slider.valueChanged.connect(self._on_pan)
        bottom.addWidget(self._pan_slider)

        content.addLayout(bottom)
        root.addLayout(content)

    # ---- styling ----

    def _apply_style(self):
        bg = COLORS["bg_selected"] if self._is_selected else COLORS["bg_header"]
        border_col = COLORS["border_focus"] if self._is_selected else COLORS["border"]
        self.setStyleSheet(
            f"TrackHeader{{"
            f"  background:{bg};"
            f"  border-bottom:1px solid {COLORS['separator']};"
            f"  border-right:1px solid {border_col};"
            f"}}"
        )
        self._color_strip.setStyleSheet(
            f"background:{self._track.color}; border:none;"
        )
        self._update_button_styles()

    def _update_button_styles(self):
        mute_bg = COLORS["accent_orange"] if self._track.muted else COLORS["bg_mid"]
        solo_bg = COLORS["accent_yellow"] if self._track.solo else COLORS["bg_mid"]
        arm_bg = COLORS["accent"] if self._arm_btn.isChecked() else COLORS["bg_mid"]
        base = (
            "border:1px solid {border}; border-radius:2px; color:{fg}; background:{bg};"
        )
        self._mute_btn.setStyleSheet(
            base.format(border=COLORS["border"], fg=COLORS["text_primary"], bg=mute_bg)
        )
        self._solo_btn.setStyleSheet(
            base.format(border=COLORS["border"], fg=COLORS["bg_darkest"], bg=solo_bg)
        )
        self._arm_btn.setStyleSheet(
            base.format(border=COLORS["border"], fg=COLORS["text_primary"], bg=arm_bg)
        )

    # ---- public helpers ----

    def set_selected(self, sel: bool):
        self._is_selected = sel
        self._apply_style()

    def update_track(self, index: int, track: Track):
        self._index = index
        self._track = track
        self._num_label.setText(str(index + 1))
        self._name_label.setText(track.name)
        self._instr_label.setText(_gm_instrument_name(track.instrument))
        self._mute_btn.setChecked(track.muted)
        self._solo_btn.setChecked(track.solo)
        self._vol_slider.blockSignals(True)
        self._vol_slider.setValue(track.volume)
        self._vol_slider.blockSignals(False)
        self._pan_slider.blockSignals(True)
        self._pan_slider.setValue(track.pan)
        self._pan_slider.blockSignals(False)
        self._apply_style()

    # ---- slots ----

    def _on_mute(self):
        self._track.muted = self._mute_btn.isChecked()
        self._update_button_styles()
        self.mute_toggled.emit(self._index)

    def _on_solo(self):
        self._track.solo = self._solo_btn.isChecked()
        self._update_button_styles()
        self.solo_toggled.emit(self._index)

    def _on_arm(self):
        self._update_button_styles()
        self.arm_toggled.emit(self._index)

    def _on_volume(self, val: int):
        self._track.volume = val
        self.volume_changed.emit(self._index, val)

    def _on_pan(self, val: int):
        self._track.pan = val
        self.pan_changed.emit(self._index, val)

    # ---- events ----

    def mousePressEvent(self, ev: QMouseEvent | None):
        if ev and ev.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._index)
        super().mousePressEvent(ev)

    def mouseDoubleClickEvent(self, ev: QMouseEvent | None):
        self._start_rename()

    def _start_rename(self):
        name, ok = QInputDialog.getText(
            self, "Rename Track", "Track name:",
            text=self._track.name,
        )
        if ok and name.strip():
            self._track.name = name.strip()
            self._name_label.setText(self._track.name)
            self.rename_requested.emit(self._index)

    # ---- context menu ----

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{COLORS['bg_dark']}; color:{COLORS['text_primary']};"
            f"  border:1px solid {COLORS['border']};}}"
            f"QMenu::item:selected{{background:{COLORS['bg_selected']};}}"
        )

        act_rename = menu.addAction("Rename")
        act_color = menu.addAction("Change Color...")
        menu.addSeparator()
        act_dup = menu.addAction("Duplicate Track")
        act_del = menu.addAction("Delete Track")
        menu.addSeparator()
        act_up = menu.addAction("Move Up")
        act_down = menu.addAction("Move Down")

        action = menu.exec(self.mapToGlobal(pos))
        if action == act_rename:
            self._start_rename()
        elif action == act_color:
            color = QColorDialog.getColor(
                QColor(self._track.color), self, "Track Color"
            )
            if color.isValid():
                self._track.color = color.name()
                self._apply_style()
                self.color_changed.emit(self._index, color.name())
        elif action == act_dup:
            self.duplicate_requested.emit(self._index)
        elif action == act_del:
            self.delete_requested.emit(self._index)
        elif action == act_up:
            pass  # handled at TrackPanel level via signal forwarding
        elif action == act_down:
            pass


# =========================================================================
#  TrackClipView — note overview for one track (right column)
# =========================================================================
class TrackClipView(QWidget):
    """Renders a miniature overview of note data for a single track."""

    clicked = pyqtSignal(int)

    def __init__(self, index: int, track: Track, parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._track = track
        self._pixels_per_tick: float = ARRANGEMENT_BEAT_WIDTH / TICKS_PER_BEAT
        self._total_ticks: int = TICKS_PER_BEAT * 64
        self._playhead_tick: int = 0
        self._loop_start: int = 0
        self._loop_end: int = 0
        self._loop_enabled: bool = False

        self.setFixedHeight(DEFAULT_TRACK_HEIGHT)
        self.setMinimumWidth(int(self._total_ticks * self._pixels_per_tick))

    def update_track(self, index: int, track: Track):
        self._index = index
        self._track = track
        self.update()

    def set_total_ticks(self, ticks: int):
        self._total_ticks = max(ticks, TICKS_PER_BEAT * 16)
        self.setMinimumWidth(int(self._total_ticks * self._pixels_per_tick))
        self.update()

    def set_playhead(self, tick: int):
        self._playhead_tick = tick
        self.update()

    def set_loop(self, start: int, end: int, enabled: bool):
        self._loop_start = start
        self._loop_end = end
        self._loop_enabled = enabled
        self.update()

    # ---- painting ----

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()

        # Background — subtle track-color tint
        base = QColor(COLORS["bg_darkest"])
        tint = QColor(self._track.color)
        blended = QColor(
            base.red() + (tint.red() - base.red()) // 8,
            base.green() + (tint.green() - base.green()) // 8,
            base.blue() + (tint.blue() - base.blue()) // 8,
        )
        p.fillRect(0, 0, w, h, blended)

        # Grid lines (bars)
        bar_ticks = TICKS_PER_BEAT * 4
        pen_grid = QPen(QColor(COLORS["grid_bar"]))
        pen_grid.setWidth(1)
        p.setPen(pen_grid)
        tick = 0
        while tick <= self._total_ticks:
            x = int(tick * self._pixels_per_tick)
            if x > w:
                break
            p.drawLine(x, 0, x, h)
            tick += bar_ticks

        # Beat sub-grid
        pen_beat = QPen(QColor(COLORS["grid_beat"]))
        pen_beat.setWidth(1)
        p.setPen(pen_beat)
        tick = 0
        while tick <= self._total_ticks:
            if tick % bar_ticks != 0:
                x = int(tick * self._pixels_per_tick)
                if x > w:
                    break
                p.drawLine(x, 0, x, h)
            tick += TICKS_PER_BEAT

        # Loop region
        if self._loop_enabled:
            lx1 = int(self._loop_start * self._pixels_per_tick)
            lx2 = int(self._loop_end * self._pixels_per_tick)
            p.fillRect(lx1, 0, lx2 - lx1, h, QColor(COLORS["loop_region"]))

        # Notes
        if self._track.notes:
            pitch_min = min(n.pitch for n in self._track.notes)
            pitch_max = max(n.pitch for n in self._track.notes)
            pitch_range = max(pitch_max - pitch_min, 1)
            margin_y = 6
            usable_h = h - margin_y * 2
            note_color = QColor(self._track.color)
            note_color_dim = QColor(self._track.color)
            note_color_dim.setAlpha(180)

            for note in self._track.notes:
                nx = int(note.start_tick * self._pixels_per_tick)
                nw = max(int(note.duration_ticks * self._pixels_per_tick), 2)
                # Invert Y so higher pitches are higher visually
                rel = (note.pitch - pitch_min) / pitch_range
                ny = margin_y + int((1.0 - rel) * (usable_h - 4))
                nh = max(int(usable_h / max(pitch_range, 12)), 2)
                if self._track.muted:
                    p.fillRect(nx, ny, nw, nh, QColor(COLORS["text_dim"]))
                else:
                    p.fillRect(nx, ny, nw, nh, note_color)
                    # Thin bright top edge
                    p.fillRect(nx, ny, nw, 1, note_color_dim)

        # Playhead
        if self._playhead_tick >= 0:
            px = int(self._playhead_tick * self._pixels_per_tick)
            p.setPen(QPen(QColor(COLORS["playhead"]), 1))
            p.drawLine(px, 0, px, h)

        # Bottom border
        p.setPen(QPen(QColor(COLORS["separator"])))
        p.drawLine(0, h - 1, w, h - 1)

        p.end()

    def mousePressEvent(self, ev: QMouseEvent | None):
        if ev and ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)
        super().mousePressEvent(ev)


# =========================================================================
#  TimeRuler — bar/beat ruler at top of arrangement
# =========================================================================
class TimeRuler(QWidget):
    """Horizontal ruler showing bar and beat numbers."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._pixels_per_tick: float = ARRANGEMENT_BEAT_WIDTH / TICKS_PER_BEAT
        self._total_ticks: int = TICKS_PER_BEAT * 64
        self._playhead_tick: int = 0
        self._loop_start: int = 0
        self._loop_end: int = 0
        self._loop_enabled: bool = False

        self.setFixedHeight(RULER_HEIGHT)
        self.setMinimumWidth(int(self._total_ticks * self._pixels_per_tick))

    def set_total_ticks(self, ticks: int):
        self._total_ticks = max(ticks, TICKS_PER_BEAT * 16)
        self.setMinimumWidth(int(self._total_ticks * self._pixels_per_tick))
        self.update()

    def set_playhead(self, tick: int):
        self._playhead_tick = tick
        self.update()

    def set_loop(self, start: int, end: int, enabled: bool):
        self._loop_start = start
        self._loop_end = end
        self._loop_enabled = enabled
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(COLORS["bg_dark"]))

        bar_ticks = TICKS_PER_BEAT * 4
        font = QFont("Segoe UI", 7)
        p.setFont(font)

        # Loop region highlight
        if self._loop_enabled:
            lx1 = int(self._loop_start * self._pixels_per_tick)
            lx2 = int(self._loop_end * self._pixels_per_tick)
            p.fillRect(lx1, 0, lx2 - lx1, h, QColor(COLORS["loop_region"]))

        # Bar numbers + tick marks
        tick = 0
        bar = 1
        while tick <= self._total_ticks:
            x = int(tick * self._pixels_per_tick)
            if x > w:
                break
            # Bar line
            p.setPen(QPen(QColor(COLORS["text_secondary"])))
            p.drawLine(x, h - 6, x, h)
            p.drawText(x + 3, h - 8, str(bar))

            # Beat ticks inside bar
            for beat in range(1, 4):
                bx = int((tick + beat * TICKS_PER_BEAT) * self._pixels_per_tick)
                p.setPen(QPen(QColor(COLORS["text_dim"])))
                p.drawLine(bx, h - 4, bx, h)

            tick += bar_ticks
            bar += 1

        # Playhead triangle
        if self._playhead_tick >= 0:
            px = int(self._playhead_tick * self._pixels_per_tick)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(COLORS["playhead"])))
            tri = [QPoint(px - 4, 0), QPoint(px + 4, 0), QPoint(px, 6)]
            p.drawPolygon(tri)
            p.setPen(QPen(QColor(COLORS["playhead"]), 1))
            p.drawLine(px, 0, px, h)

        # Bottom border
        p.setPen(QPen(QColor(COLORS["separator"])))
        p.drawLine(0, h - 1, w, h - 1)
        p.end()


# =========================================================================
#  ArrangementView — full arrangement area (right side)
# =========================================================================
class ArrangementView(QWidget):
    """Contains the time ruler and vertically stacked TrackClipViews."""

    track_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._clip_views: list[TrackClipView] = []
        self._playhead_tick: int = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._ruler = TimeRuler()
        layout.addWidget(self._ruler)

        self._tracks_widget = QWidget()
        self._tracks_layout = QVBoxLayout(self._tracks_widget)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(0)
        self._tracks_layout.addStretch()
        layout.addWidget(self._tracks_widget)

    def rebuild(self, project: ProjectState):
        """Rebuild all clip views from project state."""
        # Remove old views
        for cv in self._clip_views:
            self._tracks_layout.removeWidget(cv)
            cv.deleteLater()
        self._clip_views.clear()

        total = max(project.total_ticks, TICKS_PER_BEAT * 64)
        self._ruler.set_total_ticks(total)
        self._ruler.set_loop(project.loop_start, project.loop_end, project.loop_enabled)

        for i, track in enumerate(project.tracks):
            cv = TrackClipView(i, track)
            cv.set_total_ticks(total)
            cv.set_loop(project.loop_start, project.loop_end, project.loop_enabled)
            cv.set_playhead(self._playhead_tick)
            cv.clicked.connect(self.track_clicked.emit)
            self._tracks_layout.insertWidget(self._tracks_layout.count() - 1, cv)
            self._clip_views.append(cv)

    def update_playhead(self, tick: int):
        self._playhead_tick = tick
        self._ruler.set_playhead(tick)
        for cv in self._clip_views:
            cv.set_playhead(tick)

    def set_loop(self, start: int, end: int, enabled: bool):
        self._ruler.set_loop(start, end, enabled)
        for cv in self._clip_views:
            cv.set_loop(start, end, enabled)


# =========================================================================
#  TrackPanel — complete track management panel
# =========================================================================
class TrackPanel(QWidget):
    """
    Full Ableton-style track panel combining track headers (left) with
    arrangement clip views (right) and synchronized scrolling.
    """

    track_selected = pyqtSignal(int)
    track_added = pyqtSignal()
    track_removed = pyqtSignal(int)
    track_modified = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._project: ProjectState | None = None
        self._headers: list[TrackHeader] = []
        self._selected_index: int = 0
        self._playhead_tick: int = 0

        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # ---- Left: track headers in scroll area ----
        self._header_scroll = QScrollArea()
        self._header_scroll.setWidgetResizable(True)
        self._header_scroll.setFixedWidth(HEADER_WIDTH)
        self._header_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._header_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._header_scroll.setStyleSheet(
            f"QScrollArea{{background:{COLORS['bg_dark']}; border:none;}}"
        )

        self._header_container = QWidget()
        self._header_layout = QVBoxLayout(self._header_container)
        self._header_layout.setContentsMargins(0, RULER_HEIGHT, 0, 0)
        self._header_layout.setSpacing(0)
        self._header_layout.addStretch()
        self._header_scroll.setWidget(self._header_container)

        body.addWidget(self._header_scroll)

        # ---- Right: arrangement in scroll area ----
        self._arrangement_scroll = QScrollArea()
        self._arrangement_scroll.setWidgetResizable(True)
        self._arrangement_scroll.setStyleSheet(
            f"QScrollArea{{background:{COLORS['bg_darkest']}; border:none;}}"
        )

        self._arrangement = ArrangementView()
        self._arrangement.track_clicked.connect(self._on_track_clicked)
        self._arrangement_scroll.setWidget(self._arrangement)

        body.addWidget(self._arrangement_scroll)

        root.addLayout(body)

        # Sync vertical scrolling between header and arrangement scroll areas
        self._arrangement_scroll.verticalScrollBar().valueChanged.connect(
            self._header_scroll.verticalScrollBar().setValue
        )
        self._header_scroll.verticalScrollBar().valueChanged.connect(
            self._arrangement_scroll.verticalScrollBar().setValue
        )

        # ---- Bottom toolbar ----
        toolbar = QFrame()
        toolbar.setFixedHeight(30)
        toolbar.setStyleSheet(
            f"background:{COLORS['bg_dark']};"
            f"border-top:1px solid {COLORS['separator']};"
        )
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(6, 2, 6, 2)
        tb_layout.setSpacing(6)

        add_btn = QPushButton("+ Add Track")
        add_btn.setFixedHeight(22)
        add_btn.setFont(QFont("Segoe UI", 8))
        add_btn.setStyleSheet(
            f"QPushButton{{background:{COLORS['bg_mid']}; color:{COLORS['text_primary']};"
            f"  border:1px solid {COLORS['border']}; border-radius:3px; padding:0 10px;}}"
            f"QPushButton:hover{{background:{COLORS['bg_hover']};}}"
        )
        add_btn.clicked.connect(self.add_track)
        tb_layout.addWidget(add_btn)

        tb_layout.addStretch()

        self._track_count_label = QLabel("0 tracks")
        self._track_count_label.setFont(QFont("Segoe UI", 7))
        self._track_count_label.setStyleSheet(f"color:{COLORS['text_dim']};")
        tb_layout.addWidget(self._track_count_label)

        root.addWidget(toolbar)

    # ---------------------------------------------------------- public API

    def set_project(self, project_state: ProjectState):
        """Load or replace the entire project state and rebuild UI."""
        self._project = project_state
        self.refresh()
        if project_state.tracks:
            self._select_track(0)

    def get_selected_track_index(self) -> int:
        return self._selected_index

    def update_playhead(self, tick: int):
        self._playhead_tick = tick
        self._arrangement.update_playhead(tick)

    def refresh(self):
        """Rebuild headers and arrangement from current project state."""
        if self._project is None:
            return

        # Tear down old headers
        for hdr in self._headers:
            self._header_layout.removeWidget(hdr)
            hdr.deleteLater()
        self._headers.clear()

        # Build new headers
        for i, track in enumerate(self._project.tracks):
            hdr = TrackHeader(i, track)
            hdr.selected.connect(self._on_track_clicked)
            hdr.mute_toggled.connect(self._on_track_modified)
            hdr.solo_toggled.connect(self._on_track_modified)
            hdr.arm_toggled.connect(self._on_track_modified)
            hdr.volume_changed.connect(lambda idx, _v: self._on_track_modified(idx))
            hdr.pan_changed.connect(lambda idx, _v: self._on_track_modified(idx))
            hdr.rename_requested.connect(self._on_track_modified)
            hdr.delete_requested.connect(self.remove_track)
            hdr.duplicate_requested.connect(self.duplicate_track)
            hdr.color_changed.connect(self._on_color_changed)
            self._header_layout.insertWidget(
                self._header_layout.count() - 1, hdr
            )
            self._headers.append(hdr)

        # Rebuild arrangement
        self._arrangement.rebuild(self._project)
        self._arrangement.update_playhead(self._playhead_tick)

        # Update label
        n = len(self._project.tracks)
        self._track_count_label.setText(f"{n} track{'s' if n != 1 else ''}")

        # Re-select
        if self._project.tracks:
            idx = min(self._selected_index, len(self._project.tracks) - 1)
            self._select_track(idx)

    # ---- track operations ----

    def add_track(self):
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
        self._select_track(idx)
        self.track_added.emit()

    def remove_track(self, index: int):
        if self._project is None or not self._project.tracks:
            return
        if 0 <= index < len(self._project.tracks):
            self._project.tracks.pop(index)
            self._project.modified = True
            self.refresh()
            self.track_removed.emit(index)

    def duplicate_track(self, index: int):
        if self._project is None:
            return
        if 0 <= index < len(self._project.tracks):
            original = self._project.tracks[index]
            dup = original.copy()
            dup.name = f"{original.name} (copy)"
            self._project.tracks.insert(index + 1, dup)
            self._project.modified = True
            self.refresh()
            self._select_track(index + 1)

    # ---- internal ----

    def _select_track(self, index: int):
        if not self._project or not self._project.tracks:
            return
        index = max(0, min(index, len(self._project.tracks) - 1))
        self._selected_index = index
        for i, hdr in enumerate(self._headers):
            hdr.set_selected(i == index)
        self.track_selected.emit(index)

    def _on_track_clicked(self, index: int):
        self._select_track(index)

    def _on_track_modified(self, index: int):
        if self._project:
            self._project.modified = True
        self._arrangement.rebuild(self._project)  # type: ignore[arg-type]
        self.track_modified.emit(index)

    def _on_color_changed(self, index: int, color: str):
        self._on_track_modified(index)
