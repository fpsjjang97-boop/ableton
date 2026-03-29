"""
Review / Analysis Results Panel — bottom dock showing AI analysis output.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QFrame,
    QProgressBar, QPushButton, QGroupBox, QGridLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from config import COLORS

_STYLE = f"""
    QWidget {{
        background-color: {COLORS['bg_dark']};
        color: {COLORS['text_primary']};
    }}
    QGroupBox {{
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        margin-top: 10px;
        padding-top: 12px;
        font-weight: bold;
        color: {COLORS['text_secondary']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
    QProgressBar {{
        background-color: {COLORS['bg_input']};
        border: 1px solid {COLORS['border']};
        border-radius: 3px;
        text-align: center;
        color: {COLORS['text_primary']};
        font-size: 10px;
        min-height: 16px;
        max-height: 16px;
    }}
    QProgressBar::chunk {{
        background-color: {COLORS['accent_secondary']};
        border-radius: 2px;
    }}
    QTextEdit {{
        background-color: {COLORS['bg_input']};
        border: 1px solid {COLORS['border']};
        border-radius: 3px;
        color: {COLORS['text_primary']};
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 11px;
    }}
    QPushButton {{
        background-color: {COLORS['bg_mid']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        padding: 5px 12px;
        min-height: 24px;
    }}
    QPushButton:hover {{
        background-color: {COLORS['bg_hover']};
    }}
"""

_GRADE_COLORS = {
    "A": COLORS["accent_green"],
    "B": COLORS["accent_secondary"],
    "C": COLORS["accent_yellow"],
    "D": COLORS["accent_orange"],
    "F": COLORS["accent"],
}


def _grade_for_score(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _bar_color(value: int) -> str:
    if value >= 75:
        return COLORS["accent_green"]
    if value >= 50:
        return COLORS["accent_yellow"]
    return COLORS["accent"]


class ReviewPanel(QWidget):
    """Bottom dock panel that displays AI analysis results for the current track."""

    reanalyze_requested = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setStyleSheet(_STYLE)

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(10)

        # --- Left column: score ------------------------------------------
        score_box = QVBoxLayout()
        score_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._score_label = QLabel("--")
        self._score_label.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        self._score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._score_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        score_box.addWidget(self._score_label)

        self._grade_label = QLabel("")
        self._grade_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._grade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grade_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        score_box.addWidget(self._grade_label)

        self._score_caption = QLabel("Overall Score")
        self._score_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._score_caption.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px;"
        )
        score_box.addWidget(self._score_caption)

        root.addLayout(score_box)

        # --- Separator ---------------------------------------------------
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        root.addWidget(sep)

        # --- Middle column: metrics --------------------------------------
        metrics_group = QGroupBox("Metrics")
        metrics_layout = QGridLayout(metrics_group)
        metrics_layout.setSpacing(6)

        self._metrics: dict[str, tuple[QLabel, QProgressBar, QLabel]] = {}
        metric_names = [
            ("scale_consistency", "Scale Consistency"),
            ("velocity_dynamics", "Velocity Dynamics"),
            ("rhythm_regularity", "Rhythm Regularity"),
            ("note_diversity", "Note Diversity"),
        ]
        for row, (key, label_text) in enumerate(metric_names):
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            val = QLabel("--")
            val.setFixedWidth(40)
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px;")
            metrics_layout.addWidget(lbl, row, 0)
            metrics_layout.addWidget(bar, row, 1)
            metrics_layout.addWidget(val, row, 2)
            self._metrics[key] = (lbl, bar, val)

        root.addWidget(metrics_group, 1)

        # --- Right column: issues + histogram + buttons ------------------
        right_col = QVBoxLayout()
        right_col.setSpacing(6)

        # Issues
        issues_lbl = QLabel("Issues")
        issues_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        issues_lbl.setStyleSheet(f"color: {COLORS['text_secondary']};")
        right_col.addWidget(issues_lbl)

        self._issues_text = QTextEdit()
        self._issues_text.setReadOnly(True)
        self._issues_text.setPlaceholderText("No issues detected.")
        self._issues_text.setMaximumHeight(80)
        right_col.addWidget(self._issues_text)

        # Pitch distribution
        pitch_lbl = QLabel("Pitch Distribution")
        pitch_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        pitch_lbl.setStyleSheet(f"color: {COLORS['text_secondary']};")
        right_col.addWidget(pitch_lbl)

        self._pitch_text = QTextEdit()
        self._pitch_text.setReadOnly(True)
        self._pitch_text.setPlaceholderText("Run analysis to view distribution.")
        self._pitch_text.setMaximumHeight(70)
        self._pitch_text.setFont(QFont("Consolas", 10))
        right_col.addWidget(self._pitch_text)

        # Buttons
        btn_row = QHBoxLayout()
        btn_reanalyze = QPushButton("Re-analyze")
        btn_reanalyze.clicked.connect(self.reanalyze_requested.emit)
        btn_row.addWidget(btn_reanalyze)
        btn_export = QPushButton("Export Report")
        btn_export.clicked.connect(self.export_requested.emit)
        btn_row.addWidget(btn_export)
        right_col.addLayout(btn_row)

        root.addLayout(right_col, 1)

        # --- Far-right column: Harmony Analysis (Rule DB v2.07) ----------
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet(f"color: {COLORS['border']};")
        root.addWidget(sep2)

        harmony_col = QVBoxLayout()
        harmony_col.setSpacing(4)

        harmony_header = QLabel("Harmony Analysis")
        harmony_header.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        harmony_header.setStyleSheet(f"color: {COLORS['text_secondary']};")
        harmony_col.addWidget(harmony_header)

        self._harmony_text = QTextEdit()
        self._harmony_text.setReadOnly(True)
        self._harmony_text.setPlaceholderText("Run analysis to view chord labels.")
        self._harmony_text.setMaximumHeight(100)
        self._harmony_text.setFont(QFont("Consolas", 10))
        harmony_col.addWidget(self._harmony_text)

        # Playability meter
        play_row = QHBoxLayout()
        play_lbl = QLabel("Playability")
        play_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        self._playability_bar = QProgressBar()
        self._playability_bar.setRange(0, 100)
        self._playability_bar.setValue(0)
        self._playability_val = QLabel("--")
        self._playability_val.setFixedWidth(40)
        self._playability_val.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._playability_val.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 11px;"
        )
        play_row.addWidget(play_lbl)
        play_row.addWidget(self._playability_bar)
        play_row.addWidget(self._playability_val)
        harmony_col.addLayout(play_row)

        # Difficulty + Genre
        self._difficulty_label = QLabel("")
        self._difficulty_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px;"
        )
        harmony_col.addWidget(self._difficulty_label)

        self._genre_label = QLabel("")
        self._genre_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px;"
        )
        harmony_col.addWidget(self._genre_label)

        # Rule DB version label
        self._rule_db_label = QLabel("")
        self._rule_db_label.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 9px;"
        )
        harmony_col.addWidget(self._rule_db_label)

        harmony_col.addStretch()
        root.addLayout(harmony_col, 1)

    # -- Public API ----------------------------------------------------------

    def show_review(self, review: dict):
        """
        Populate the panel from a review dictionary.

        Handles both the new format (with score, velocity_dynamics, etc.) and
        the legacy format (scale_consistency as 0.0-1.0 float, pitch_histogram
        instead of pitch_distribution, no score/issues).

        Expected keys (new format):
            score (int 0-100),
            scale_consistency (int 0-100),
            velocity_dynamics (int 0-100),
            rhythm_regularity (int 0-100),
            note_diversity (int 0-100),
            issues (list[str]),
            pitch_distribution (dict[str, int])   e.g. {"C": 42, "D": 18, ...}
        """
        # --- Normalize scale_consistency: accept both 0.0-1.0 and 0-100 ---
        raw_sc = review.get("scale_consistency", 0)
        if raw_sc is not None and isinstance(raw_sc, float) and raw_sc <= 1.0:
            review = dict(review)  # avoid mutating caller's dict
            review["scale_consistency"] = int(round(raw_sc * 100))

        score = review.get("score", 0)
        if score is None:
            score = 0
        grade = _grade_for_score(score)
        grade_color = _GRADE_COLORS.get(grade, COLORS["text_primary"])

        self._score_label.setText(str(score))
        self._score_label.setStyleSheet(f"color: {grade_color};")
        self._grade_label.setText(grade)
        self._grade_label.setStyleSheet(f"color: {grade_color};")

        # Metrics
        for key, (_, bar, val_lbl) in self._metrics.items():
            v = review.get(key, 0)
            if v is None:
                v = 0
            v = int(v)
            bar.setValue(v)
            bar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {_bar_color(v)}; border-radius: 2px; }}"
            )
            val_lbl.setText(f"{v}%")

        # Issues
        issues = review.get("issues", [])
        if issues:
            self._issues_text.setPlainText("\n".join(f"- {i}" for i in issues))
        else:
            self._issues_text.setPlainText("No issues detected.")

        # Pitch distribution histogram — accept both key names
        dist = review.get("pitch_distribution") or review.get("pitch_histogram") or {}
        if dist:
            max_val = max(dist.values()) if dist else 1
            lines = []
            for note_name, count in dist.items():
                bar_len = int((count / max_val) * 24)
                bar_str = "\u2588" * bar_len
                lines.append(f"{note_name:>2} | {bar_str} {count}")
            self._pitch_text.setPlainText("\n".join(lines))
        else:
            self._pitch_text.setPlainText("")

        # --- Harmony Analysis (Rule DB v2.07) ---
        segments = review.get("harmony_segments", [])
        if segments:
            chord_lines = []
            for seg in segments:
                bar = seg.get("bar", "?")
                chord = seg.get("chord", "N.C.")
                conf = seg.get("confidence", 0)
                conf_str = f"{int(conf * 100)}%" if isinstance(conf, float) else str(conf)
                alts = seg.get("alternatives", [])
                alt_str = ""
                if alts:
                    alt_str = f"  ({', '.join(a['label'] for a in alts[:2])})"
                chord_lines.append(f"Bar {bar}: {chord} [{conf_str}]{alt_str}")
            self._harmony_text.setPlainText("\n".join(chord_lines))
        else:
            self._harmony_text.setPlainText("")

        play_score = review.get("playability_score")
        if play_score is not None:
            play_score = int(play_score)
            self._playability_bar.setValue(play_score)
            self._playability_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {_bar_color(play_score)}; border-radius: 2px; }}"
            )
            self._playability_val.setText(f"{play_score}%")

        difficulty = review.get("difficulty", "")
        if difficulty:
            diff_colors = {
                "beginner": COLORS["accent_green"],
                "intermediate": COLORS["accent_yellow"],
                "advanced": COLORS["accent_orange"],
                "virtuoso": COLORS["accent"],
            }
            dc = diff_colors.get(difficulty, COLORS["text_secondary"])
            self._difficulty_label.setText(f"Difficulty: {difficulty.upper()}")
            self._difficulty_label.setStyleSheet(f"color: {dc}; font-size: 11px; font-weight: bold;")
        else:
            self._difficulty_label.setText("")

        genre_label = review.get("genre_label", "")
        genre_fit = review.get("genre_fit")
        if genre_label:
            fit_str = f" (fit: {genre_fit}%)" if genre_fit is not None else ""
            self._genre_label.setText(f"Genre: {genre_label}{fit_str}")
        else:
            self._genre_label.setText("")

        db_ver = review.get("rule_db_version")
        if db_ver:
            self._rule_db_label.setText(f"Rule DB v{db_ver}")
        else:
            self._rule_db_label.setText("")

    def clear(self):
        """Reset all fields to their default empty state."""
        self._score_label.setText("--")
        self._score_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        self._grade_label.setText("")
        self._grade_label.setStyleSheet(f"color: {COLORS['text_dim']};")

        for _, (_, bar, val_lbl) in self._metrics.items():
            bar.setValue(0)
            bar.setStyleSheet("")
            val_lbl.setText("--")

        self._issues_text.clear()
        self._pitch_text.clear()
        self._harmony_text.clear()
        self._playability_bar.setValue(0)
        self._playability_bar.setStyleSheet("")
        self._playability_val.setText("--")
        self._difficulty_label.setText("")
        self._genre_label.setText("")
        self._rule_db_label.setText("")
