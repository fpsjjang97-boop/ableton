"""
Score View — visual staff notation display for MIDI tracks.
Renders notes on a 5-line staff with clef, key signature, time signature.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPainterPath
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QComboBox, QPushButton
from config import COLORS
C = COLORS

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Staff positions: MIDI pitch → staff line offset from middle C
# Middle C (60) = ledger line below treble staff

STAFF_LINE_SPACING = 8
STAFF_TOP_MARGIN = 40
NOTE_WIDTH = 40


class StaffRenderer(QWidget):
    """Renders musical staff notation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notes: list[dict] = []  # [{pitch, start_tick, duration, velocity}]
        self._key = "C"
        self._scale = "major"
        self._time_sig = (4, 4)
        self._clef = "treble"
        self._tpb = 480
        self.setMinimumSize(600, 180)
        self.setStyleSheet(f"background: {C['bg_input']};")

    def set_notes(self, notes: list[dict], key="C", scale="major",
                  time_sig=(4, 4), clef="treble", tpb=480):
        self._notes = notes
        self._key = key
        self._scale = scale
        self._time_sig = time_sig
        self._clef = clef
        self._tpb = tpb
        # Resize based on content
        bar_ticks = tpb * time_sig[0]
        total_ticks = max((n.get('end', 0) for n in notes), default=bar_ticks * 4)
        num_bars = max(1, int(total_ticks / bar_ticks) + 1)
        self.setMinimumWidth(max(600, num_bars * 200))
        self.update()

    def _pitch_to_staff_y(self, pitch: int) -> float:
        """Convert MIDI pitch to Y position on treble staff."""
        # C4(60)=0, each diatonic step = STAFF_LINE_SPACING/2
        # Staff lines: E4, G4, B4, D5, F5 (bottom to top)
        # Treble clef: bottom line = E4 (64)
        c4 = 60
        # Chromatic to diatonic step mapping
        chrom_to_diat = [0, 0.5, 1, 1.5, 2, 3, 3.5, 4, 4.5, 5, 5.5, 6]  # C,C#,D,D#,E,F,F#,G,G#,A,A#,B
        octave = (pitch // 12) - 4  # relative to C4
        pc = pitch % 12
        diatonic_pos = octave * 7 + chrom_to_diat[pc]
        # E4(64) is bottom staff line, diatonic pos = 2
        # Each diatonic step up moves half a line spacing
        staff_bottom_y = STAFF_TOP_MARGIN + 4 * STAFF_LINE_SPACING
        e4_diatonic = 2
        y = staff_bottom_y - (diatonic_pos - e4_diatonic) * (STAFF_LINE_SPACING / 2)
        return y

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(C['bg_input']))

        staff_x = 60  # left margin
        staff_w = w - 80

        # Draw 5 staff lines
        p.setPen(QPen(QColor(C['text_dim']), 1))
        for i in range(5):
            y = STAFF_TOP_MARGIN + i * STAFF_LINE_SPACING
            p.drawLine(staff_x, int(y), int(staff_x + staff_w), int(y))

        # Treble clef symbol (simplified)
        p.setPen(QPen(QColor(C['text_primary']), 2))
        p.setFont(QFont("Segoe UI", 28))
        if self._clef == "treble":
            p.drawText(int(staff_x + 2), int(STAFF_TOP_MARGIN + 4 * STAFF_LINE_SPACING - 2), "\U0001D11E")
        elif self._clef == "bass":
            p.drawText(int(staff_x + 2), int(STAFF_TOP_MARGIN + 3 * STAFF_LINE_SPACING), "\U0001D122")

        # Time signature
        p.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        p.setPen(QColor(C['text_primary']))
        ts_x = staff_x + 40
        p.drawText(int(ts_x), int(STAFF_TOP_MARGIN + 2 * STAFF_LINE_SPACING - 2),
                   str(self._time_sig[0]))
        p.drawText(int(ts_x), int(STAFF_TOP_MARGIN + 4 * STAFF_LINE_SPACING - 2),
                   str(self._time_sig[1]))

        # Bar lines
        bar_ticks = self._tpb * self._time_sig[0]
        note_start_x = staff_x + 70
        available_w = staff_w - 70
        total_ticks = max((n.get('end', 0) for n in self._notes), default=bar_ticks * 4)
        px_per_tick = available_w / max(total_ticks, 1)

        p.setPen(QPen(QColor(C['text_dim']), 1))
        tick = bar_ticks
        while tick < total_ticks:
            x = note_start_x + tick * px_per_tick
            if x < staff_x + staff_w:
                p.drawLine(int(x), int(STAFF_TOP_MARGIN),
                           int(x), int(STAFF_TOP_MARGIN + 4 * STAFF_LINE_SPACING))
            tick += bar_ticks

        # Draw notes
        p.setFont(QFont("Segoe UI", 9))
        for note in self._notes:
            pitch = note.get('pitch', 60)
            start = note.get('start', 0)
            dur = note.get('duration', self._tpb)
            vel = note.get('velocity', 80)

            x = note_start_x + start * px_per_tick
            y = self._pitch_to_staff_y(pitch)

            if x < staff_x or x > staff_x + staff_w:
                continue

            # Note head
            filled = dur < self._tpb * 2  # half notes and shorter are filled
            p.setPen(QPen(QColor(C['text_primary']), 1.5))
            if filled:
                p.setBrush(QBrush(QColor(C['text_primary'])))
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(x - 4, y - 3, 8, 6))

            # Stem
            if dur < self._tpb * 4:  # not whole note
                stem_up = y > STAFF_TOP_MARGIN + 2 * STAFF_LINE_SPACING
                if stem_up:
                    p.drawLine(int(x + 4), int(y), int(x + 4), int(y - 28))
                else:
                    p.drawLine(int(x - 4), int(y), int(x - 4), int(y + 28))

            # Flag for 8th/16th
            if dur <= self._tpb // 2:
                flag_x = x + 4 if (y > STAFF_TOP_MARGIN + 2 * STAFF_LINE_SPACING) else x - 4
                flag_y = y - 28 if (y > STAFF_TOP_MARGIN + 2 * STAFF_LINE_SPACING) else y + 28
                p.drawLine(int(flag_x), int(flag_y), int(flag_x + 6), int(flag_y + 8))

            # Ledger lines
            staff_bottom = STAFF_TOP_MARGIN + 4 * STAFF_LINE_SPACING
            staff_top = STAFF_TOP_MARGIN
            if y > staff_bottom + STAFF_LINE_SPACING / 2:
                ly = staff_bottom + STAFF_LINE_SPACING
                while ly <= y + 1:
                    p.drawLine(int(x - 7), int(ly), int(x + 7), int(ly))
                    ly += STAFF_LINE_SPACING
            elif y < staff_top - STAFF_LINE_SPACING / 2:
                ly = staff_top - STAFF_LINE_SPACING
                while ly >= y - 1:
                    p.drawLine(int(x - 7), int(ly), int(x + 7), int(ly))
                    ly -= STAFF_LINE_SPACING

            # Accidental
            pc = pitch % 12
            name = NOTE_NAMES[pc]
            if '#' in name:
                p.setFont(QFont("Segoe UI", 10))
                p.drawText(int(x - 14), int(y + 3), "#")

            # Dynamic marking
            dynamic = note.get('dynamic', '')
            if dynamic:
                p.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                p.setPen(QColor(C['text_secondary']))
                dy = y + 20 if y < STAFF_TOP_MARGIN + 2 * STAFF_LINE_SPACING else y - 15
                p.drawText(int(x - 6), int(dy), dynamic)

        p.end()


class ScoreViewPanel(QWidget):
    """Score view panel for the detail view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Score View"))

        hdr.addWidget(QLabel("Clef:"))
        self._clef_combo = QComboBox()
        self._clef_combo.addItems(["treble", "bass", "alto"])
        self._clef_combo.setFixedWidth(70)
        hdr.addWidget(self._clef_combo)

        export_btn = QPushButton("Export MusicXML")
        export_btn.setFixedHeight(22)
        export_btn.setStyleSheet(f"""
            QPushButton {{ background: {C['bg_input']}; color: {C['text_secondary']};
                          border: 1px solid {C['border']}; border-radius: 3px; font-size: 10px; }}
        """)
        hdr.addWidget(export_btn)
        hdr.addStretch()
        layout.addLayout(hdr)

        # Staff scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"QScrollArea {{ border: 1px solid {C['border']}; }}")
        self._staff = StaffRenderer()
        scroll.setWidget(self._staff)
        layout.addWidget(scroll, 1)

    def set_notes(self, notes: list[dict], **kwargs):
        self._staff.set_notes(notes, clef=self._clef_combo.currentText(), **kwargs)
