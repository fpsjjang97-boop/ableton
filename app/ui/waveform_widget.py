"""
Waveform display widget + Automation lane widget + Arrangement timeline widget.

Covers: audio waveform visualization, automation curve display/editing,
arrangement timeline with clips, markers, chord track.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QPainterPath,
                          QLinearGradient, QMouseEvent, QPaintEvent)
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy

from config import COLORS

C = COLORS


class WaveformWidget(QWidget):
    """Displays audio waveform peaks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._peaks: list[float] = []
        self._selection_start = -1
        self._selection_end = -1
        self._playhead_pos = 0.0   # 0-1
        self._color = QColor(C['accent'])
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_peaks(self, peaks: list[float]):
        self._peaks = peaks
        self.update()

    def set_playhead(self, position: float):
        self._playhead_pos = max(0, min(position, 1.0))
        self.update()

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid_y = h / 2

        # Background
        p.fillRect(self.rect(), QColor(C['bg_input']))

        if not self._peaks:
            p.setPen(QColor(C['text_dim']))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No audio data")
            p.end()
            return

        # Selection
        if self._selection_start >= 0 and self._selection_end >= 0:
            sx = self._selection_start * w
            sw = (self._selection_end - self._selection_start) * w
            p.fillRect(int(sx), 0, int(sw), h, QColor("#FFFFFF18"))

        # Waveform
        n = len(self._peaks)
        px_per_peak = w / n if n > 0 else 1
        p.setPen(Qt.PenStyle.NoPen)

        for i, peak in enumerate(self._peaks):
            x = int(i * px_per_peak)
            bar_h = int(peak * mid_y * 0.9)
            # Gradient color based on amplitude
            alpha = int(100 + peak * 155)
            color = QColor(self._color)
            color.setAlpha(alpha)
            p.setBrush(QBrush(color))
            p.drawRect(x, int(mid_y - bar_h), max(1, int(px_per_peak)), bar_h * 2)

        # Center line
        p.setPen(QPen(QColor(C['text_dim']), 1))
        p.drawLine(0, int(mid_y), w, int(mid_y))

        # Playhead
        if self._playhead_pos > 0:
            px = int(self._playhead_pos * w)
            p.setPen(QPen(QColor(C['playhead']), 2))
            p.drawLine(px, 0, px, h)

        # Border
        p.setPen(QPen(QColor(C['border']), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        p.end()


class AutomationLaneWidget(QWidget):
    """Displays and allows editing of an automation lane."""

    point_added = pyqtSignal(int, float)     # tick, value
    point_moved = pyqtSignal(int, int, float)  # old_tick, new_tick, new_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points: list[tuple[int, float]] = []  # (tick, value 0-1)
        self._total_ticks = 1920
        self._color = QColor(C['accent'])
        self._dragging_idx = -1
        self.setMinimumHeight(50)
        self.setMaximumHeight(80)

    def set_points(self, points: list[tuple[int, float]], total_ticks: int = 1920):
        self._points = sorted(points, key=lambda p: p[0])
        self._total_ticks = max(total_ticks, 1)
        self.update()

    def set_color(self, color: str):
        self._color = QColor(color)

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(self.rect(), QColor(C['bg_darkest']))

        if not self._points:
            p.end()
            return

        # Draw automation curve
        path = QPainterPath()
        for i, (tick, val) in enumerate(self._points):
            x = tick / self._total_ticks * w
            y = h - val * h
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        p.setPen(QPen(self._color, 1.5))
        p.drawPath(path)

        # Draw points
        for tick, val in self._points:
            x = tick / self._total_ticks * w
            y = h - val * h
            p.setPen(QPen(QColor("#FFF"), 1))
            p.setBrush(QBrush(self._color))
            p.drawEllipse(QPointF(x, y), 3, 3)

        # Border
        p.setPen(QPen(QColor(C['border']), 1))
        p.drawRect(0, 0, w - 1, h - 1)
        p.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            w, h = self.width(), self.height()
            tick = int(pos.x() / w * self._total_ticks)
            value = 1.0 - pos.y() / h
            value = max(0, min(value, 1.0))

            # Check if clicking near existing point
            for i, (pt, pv) in enumerate(self._points):
                px = pt / self._total_ticks * w
                py = h - pv * h
                if abs(pos.x() - px) < 8 and abs(pos.y() - py) < 8:
                    self._dragging_idx = i
                    return

            # Add new point
            self._points.append((tick, value))
            self._points.sort(key=lambda p: p[0])
            self.point_added.emit(tick, value)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._dragging_idx = -1

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging_idx >= 0:
            pos = event.position()
            w, h = self.width(), self.height()
            tick = int(pos.x() / w * self._total_ticks)
            value = max(0, min(1.0 - pos.y() / h, 1.0))
            old_tick = self._points[self._dragging_idx][0]
            self._points[self._dragging_idx] = (tick, value)
            self._points.sort(key=lambda p: p[0])
            self.point_moved.emit(old_tick, tick, value)
            self.update()


class ChordTrackWidget(QWidget):
    """Displays chord symbols on a horizontal timeline."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chords: list[tuple[int, int, str]] = []  # (tick, duration, name)
        self._total_ticks = 1920
        self.setFixedHeight(24)

    def set_chords(self, chords: list[tuple[int, int, str]], total_ticks: int = 1920):
        self._chords = chords
        self._total_ticks = max(total_ticks, 1)
        self.update()

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(C['bg_mid']))

        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        p.setFont(font)

        for tick, dur, name in self._chords:
            x = int(tick / self._total_ticks * w)
            cw = int(dur / self._total_ticks * w)
            # Chord box
            p.setPen(QPen(QColor(C['border']), 1))
            p.setBrush(QBrush(QColor(C['bg_panel'])))
            p.drawRect(x, 1, max(cw - 1, 20), h - 2)
            # Chord name
            p.setPen(QColor(C['text_primary']))
            p.drawText(x + 4, h - 5, name)

        p.end()


class MarkerBarWidget(QWidget):
    """Displays markers on the timeline."""

    marker_clicked = pyqtSignal(int)  # tick

    def __init__(self, parent=None):
        super().__init__(parent)
        self._markers: list[tuple[int, str, str]] = []  # (tick, name, color)
        self._total_ticks = 1920
        self.setFixedHeight(18)

    def set_markers(self, markers: list[tuple[int, str, str]], total_ticks: int = 1920):
        self._markers = markers
        self._total_ticks = max(total_ticks, 1)
        self.update()

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(C['bg_dark']))

        font = QFont("Segoe UI", 7)
        p.setFont(font)

        for tick, name, color in self._markers:
            x = int(tick / self._total_ticks * w)
            p.setPen(QPen(QColor(color), 1))
            p.setBrush(QBrush(QColor(color)))
            # Triangle marker
            p.drawPolygon([QPointF(x, 0), QPointF(x + 5, 0), QPointF(x, h)])
            p.setPen(QColor(C['text_primary']))
            p.drawText(x + 7, h - 3, name)

        p.end()

    def mousePressEvent(self, event: QMouseEvent):
        x = event.position().x()
        tick = int(x / self.width() * self._total_ticks)
        self.marker_clicked.emit(tick)
