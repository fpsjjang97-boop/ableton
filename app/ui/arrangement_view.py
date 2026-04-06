"""
Arrangement View — linear timeline with clips, markers, chord track,
automation lanes, track headers, time ruler.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QMouseEvent, QPaintEvent, QWheelEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSplitter, QSizePolicy, QMenu,
)
from config import COLORS
C = COLORS


class TimeRuler(QWidget):
    """Top ruler showing bars/beats."""
    position_clicked = pyqtSignal(int)  # tick

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self._total_ticks = 1920 * 8
        self._px_per_tick = 0.1
        self._offset = 0
        self._playhead = 0
        self._time_sig = (4, 4)
        self._tpb = 480

    def set_params(self, total_ticks, px_per_tick, offset, playhead, tpb=480, time_sig=(4, 4)):
        self._total_ticks = total_ticks
        self._px_per_tick = px_per_tick
        self._offset = offset
        self._playhead = playhead
        self._tpb = tpb
        self._time_sig = time_sig
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(C['bg_dark']))

        bar_ticks = self._tpb * self._time_sig[0]
        font = QFont("Segoe UI", 8)
        p.setFont(font)

        # Draw bar lines
        bar = 1
        tick = 0
        while tick < self._total_ticks:
            x = int((tick - self._offset) * self._px_per_tick)
            if 0 <= x <= w:
                p.setPen(QPen(QColor(C['text_dim']), 1))
                p.drawLine(x, h - 8, x, h)
                p.setPen(QColor(C['text_secondary']))
                p.drawText(x + 3, h - 10, str(bar))
            tick += bar_ticks
            bar += 1

        # Playhead
        px = int((self._playhead - self._offset) * self._px_per_tick)
        if 0 <= px <= w:
            p.setPen(QPen(QColor("#FFFFFF"), 2))
            p.drawLine(px, 0, px, h)

        p.setPen(QPen(QColor(C['border']), 1))
        p.drawLine(0, h - 1, w, h - 1)
        p.end()

    def mousePressEvent(self, event: QMouseEvent):
        tick = int(event.position().x() / self._px_per_tick + self._offset)
        self.position_clicked.emit(tick)


class ArrangementTrackLane(QWidget):
    """Single track lane in the arrangement view showing clips."""
    clip_selected = pyqtSignal(int, int)  # track_idx, clip_idx

    def __init__(self, track_idx: int = 0, parent=None):
        super().__init__(parent)
        self._track_idx = track_idx
        self._clips: list[dict] = []  # [{start, length, name, color, notes_count}]
        self._total_ticks = 1920 * 8
        self._px_per_tick = 0.1
        self._offset = 0
        self._track_color = C['accent']
        self.setFixedHeight(60)
        self.setMinimumWidth(200)

    def set_clips(self, clips: list[dict], total_ticks=None, px_per_tick=None, offset=None):
        self._clips = clips
        if total_ticks is not None:
            self._total_ticks = total_ticks
        if px_per_tick is not None:
            self._px_per_tick = px_per_tick
        if offset is not None:
            self._offset = offset
        self.update()

    def set_color(self, color: str):
        self._track_color = color

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(C['bg_darkest']))

        # Grid lines (beats)
        beat_ticks = 480
        tick = 0
        while tick < self._total_ticks:
            x = int((tick - self._offset) * self._px_per_tick)
            if 0 <= x <= w:
                is_bar = tick % (beat_ticks * 4) == 0
                p.setPen(QPen(QColor(C['border'] if is_bar else "#1A1A1A"), 1))
                p.drawLine(x, 0, x, h)
            tick += beat_ticks

        # Clips
        font = QFont("Segoe UI", 8)
        p.setFont(font)
        for i, clip in enumerate(self._clips):
            cx = int((clip['start'] - self._offset) * self._px_per_tick)
            cw = int(clip['length'] * self._px_per_tick)
            if cx + cw < 0 or cx > w:
                continue

            # Clip body
            color = QColor(clip.get('color', self._track_color))
            color.setAlpha(180)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(cx, 2, max(cw, 4), h - 4, 3, 3)

            # Clip name
            p.setPen(QColor("#000"))
            p.drawText(cx + 4, 14, clip.get('name', ''))

            # Mini note display
            notes = clip.get('notes', [])
            if notes and cw > 20:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor("#00000040")))
                for note in notes[:50]:
                    nx = cx + int(note.get('start', 0) / max(clip['length'], 1) * cw)
                    ny = h - 6 - int(note.get('pitch', 60) / 127 * (h - 16))
                    nw = max(1, int(note.get('dur', 100) / max(clip['length'], 1) * cw))
                    p.drawRect(nx, ny, nw, 2)

        # Border
        p.setPen(QPen(QColor(C['border']), 1))
        p.drawLine(0, h - 1, w, h - 1)
        p.end()

    def mousePressEvent(self, event: QMouseEvent):
        x = event.position().x()
        tick = x / self._px_per_tick + self._offset
        for i, clip in enumerate(self._clips):
            if clip['start'] <= tick <= clip['start'] + clip['length']:
                self.clip_selected.emit(self._track_idx, i)
                return


class TrackHeader(QWidget):
    """Track header on the left side of arrangement."""
    solo_toggled = pyqtSignal(int, bool)
    mute_toggled = pyqtSignal(int, bool)
    arm_toggled = pyqtSignal(int, bool)

    def __init__(self, track_idx: int, name: str, color: str = "#888", parent=None):
        super().__init__(parent)
        self._idx = track_idx
        self.setFixedWidth(140)
        self.setFixedHeight(60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        # Name
        self._name = QLabel(name)
        self._name.setStyleSheet(f"color: {C['text_primary']}; font-size: 10px; font-weight: bold;")
        layout.addWidget(self._name)

        # Buttons row
        btns = QHBoxLayout()
        for label, signal, col in [
            ("M", self.mute_toggled, "#D48A8A"),
            ("S", self.solo_toggled, "#8CD48C"),
            ("R", self.arm_toggled, "#D4A08A"),
        ]:
            btn = QPushButton(label)
            btn.setFixedSize(22, 18)
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {C['text_dim']};
                              border: 1px solid {C['border']}; border-radius: 2px; font-size: 9px; }}
                QPushButton:checked {{ background: {col}; color: #000; border-color: {col}; }}
            """)
            btn.toggled.connect(lambda v, s=signal: s.emit(self._idx, v))
            btns.addWidget(btn)
        btns.addStretch()
        layout.addLayout(btns)

        self.setStyleSheet(f"""
            TrackHeader {{
                background: {C['bg_mid']};
                border-right: 2px solid {color};
                border-bottom: 1px solid {C['border']};
            }}
        """)


class ArrangementPanel(QWidget):
    """Full arrangement view with track headers + timeline."""

    seek_requested = pyqtSignal(int)  # tick

    def __init__(self, parent=None):
        super().__init__(parent)
        self._px_per_tick = 0.12
        self._offset = 0
        self._playhead = 0
        self._total_ticks = 1920 * 16
        self._tpb = 480
        self._time_sig = (4, 4)
        self._track_lanes: list[ArrangementTrackLane] = []
        self._track_headers: list[TrackHeader] = []
        self._project = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Time ruler
        self._ruler = TimeRuler()
        ruler_row = QHBoxLayout()
        ruler_spacer = QWidget()
        ruler_spacer.setFixedWidth(140)
        ruler_row.addWidget(ruler_spacer)
        ruler_row.addWidget(self._ruler, 1)
        ruler_row.setContentsMargins(0, 0, 0, 0)
        ruler_row.setSpacing(0)
        root.addLayout(ruler_row)

        # Splitter: headers | lanes
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: track headers
        self._headers_scroll = QScrollArea()
        self._headers_scroll.setFixedWidth(140)
        self._headers_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._headers_scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {C['bg_mid']}; }}")
        self._headers_container = QWidget()
        self._headers_layout = QVBoxLayout(self._headers_container)
        self._headers_layout.setContentsMargins(0, 0, 0, 0)
        self._headers_layout.setSpacing(0)
        self._headers_layout.addStretch()
        self._headers_scroll.setWidget(self._headers_container)

        # Right: track lanes
        self._lanes_scroll = QScrollArea()
        self._lanes_scroll.setWidgetResizable(True)
        self._lanes_scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {C['bg_darkest']}; }}")
        self._lanes_container = QWidget()
        self._lanes_layout = QVBoxLayout(self._lanes_container)
        self._lanes_layout.setContentsMargins(0, 0, 0, 0)
        self._lanes_layout.setSpacing(0)
        self._lanes_layout.addStretch()
        self._lanes_scroll.setWidget(self._lanes_container)

        # Sync scrolling
        self._headers_scroll.verticalScrollBar().valueChanged.connect(
            self._lanes_scroll.verticalScrollBar().setValue
        )
        self._lanes_scroll.verticalScrollBar().valueChanged.connect(
            self._headers_scroll.verticalScrollBar().setValue
        )

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(self._headers_scroll)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self._lanes_scroll)

        self._splitter.addWidget(left)
        self._splitter.addWidget(right)
        self._splitter.setSizes([140, 800])
        root.addWidget(self._splitter, 1)

    def add_track(self, name: str, color: str = "#888"):
        idx = len(self._track_lanes)
        header = TrackHeader(idx, name, color)
        self._headers_layout.insertWidget(self._headers_layout.count() - 1, header)
        self._track_headers.append(header)

        lane = ArrangementTrackLane(idx)
        lane.set_color(color)
        self._lanes_layout.insertWidget(self._lanes_layout.count() - 1, lane)
        self._track_lanes.append(lane)

    def update_track(self, track_idx: int, clips: list[dict]):
        if 0 <= track_idx < len(self._track_lanes):
            self._track_lanes[track_idx].set_clips(
                clips, self._total_ticks, self._px_per_tick, self._offset
            )

    def set_playhead(self, tick: int):
        self._playhead = tick
        self._ruler.set_params(
            self._total_ticks, self._px_per_tick, self._offset, tick
        )

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._px_per_tick *= 1.2
            else:
                self._px_per_tick /= 1.2
            self._px_per_tick = max(0.02, min(self._px_per_tick, 2.0))
            self._refresh_all()
        else:
            delta = event.angleDelta().y()
            self._offset -= int(delta / self._px_per_tick)
            self._offset = max(0, self._offset)
            self._refresh_all()

    # ── Project integration ──────────────────────────────────────────────

    def set_project(self, project):
        """Load a project and create track lanes for every track.

        *project* is expected to be a ``ProjectState`` (from core.models).
        """
        self._project = project

        # Derive timeline length from project data
        tpb = getattr(project, 'ticks_per_beat', 480)
        self._tpb = tpb

        ts = getattr(project, 'time_signature', None)
        if ts is not None:
            self._time_sig = (getattr(ts, 'numerator', 4), getattr(ts, 'denominator', 4))

        # Compute total ticks from the furthest note end across all tracks
        max_tick = tpb * self._time_sig[0] * 16  # at least 16 bars
        for trk in getattr(project, 'tracks', []):
            for n in getattr(trk, 'notes', []):
                end = getattr(n, 'end_tick', 0)
                if end > max_tick:
                    max_tick = end
        # Round up to the next bar boundary + some margin
        bar_ticks = tpb * self._time_sig[0]
        self._total_ticks = ((max_tick // bar_ticks) + 4) * bar_ticks

        # Remove old lanes and headers
        for hdr in self._track_headers:
            hdr.setParent(None)
            hdr.deleteLater()
        for lane in self._track_lanes:
            lane.setParent(None)
            lane.deleteLater()
        self._track_headers.clear()
        self._track_lanes.clear()

        # Build new lanes from project tracks
        tracks = getattr(project, 'tracks', [])
        for idx, trk in enumerate(tracks):
            color = getattr(trk, 'color', '#888')
            name = getattr(trk, 'name', f'Track {idx + 1}')
            self.add_track(name, color)

            # Build clip dictionaries from the track's notes
            clips = self._clips_from_track(trk, idx)
            self.update_track(idx, clips)

        self._refresh_all()

    def _clips_from_track(self, trk, track_idx: int) -> list[dict]:
        """Convert a track's notes into clip dicts for the lane renderer.

        Groups notes into one contiguous "clip" per track. If the track has
        no notes an empty list is returned.
        """
        notes = getattr(trk, 'notes', [])
        if not notes:
            return []

        # Find extent of notes in the track
        min_start = min(n.start_tick for n in notes)
        max_end = max(n.end_tick for n in notes)
        length = max(self._tpb, max_end - min_start)

        # Build mini-note data for the lane painter (limit to 80 for perf)
        mini_notes = []
        for n in notes[:80]:
            mini_notes.append({
                'start': n.start_tick - min_start,
                'pitch': n.pitch,
                'dur': n.duration_ticks,
            })

        color = getattr(trk, 'color', C.get('accent', '#888'))
        name = getattr(trk, 'name', f'Track {track_idx + 1}')

        return [{
            'start': min_start,
            'length': length,
            'name': name,
            'color': color,
            'notes': mini_notes,
        }]

    def update_playhead(self, tick: int):
        """Move the playhead to *tick* and repaint the ruler."""
        self._playhead = tick
        self._ruler.set_params(
            self._total_ticks, self._px_per_tick, self._offset,
            tick, self._tpb, self._time_sig,
        )

    def _refresh_all(self):
        self._ruler.set_params(
            self._total_ticks, self._px_per_tick, self._offset,
            self._playhead, self._tpb, self._time_sig,
        )
        for lane in self._track_lanes:
            lane._px_per_tick = self._px_per_tick
            lane._offset = self._offset
            lane._total_ticks = self._total_ticks
            lane.update()
