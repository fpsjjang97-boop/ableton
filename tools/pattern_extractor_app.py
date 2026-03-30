"""
MIDI Pattern Extractor — standalone GUI application.

MIDI 파일 드래그&드롭 → v2.09 Rule DB 기반 화성 분석 → 패턴 추출 → JSON 저장.
PyInstaller로 EXE 빌드 가능.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path

# ── Path bootstrap (source & PyInstaller frozen) ────────────────────────
if getattr(sys, "frozen", False):
    _BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", ""))
    _EXE_DIR = Path(sys.executable).resolve().parent
    REPO_ROOT = _EXE_DIR
    for _c in [_EXE_DIR, _EXE_DIR.parent, _EXE_DIR.parent.parent]:
        if (_c / "analyzed_chords").is_dir() or (_c / "app").is_dir():
            REPO_ROOT = _c
            break
    APP_DIR = REPO_ROOT / "app"
    sys.path.insert(0, str(_BUNDLE_DIR))
    sys.path.insert(0, str(APP_DIR))
    sys.path.insert(0, str(REPO_ROOT / "tools"))
else:
    REPO_ROOT = Path(__file__).resolve().parent.parent
    APP_DIR = REPO_ROOT / "app"
    sys.path.insert(0, str(APP_DIR))
    sys.path.insert(0, str(REPO_ROOT / "tools"))

# Windows UTF-8
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for _s in (sys.stdout, sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            try:
                _s.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")

import numpy as np
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.models import Note, ProjectState, Track, TICKS_PER_BEAT

# ── Theme — Black / White / Gray ────────────────────────────────────────

C = {
    "bg":          "#0E0E0E",
    "bg_mid":      "#161616",
    "bg_input":    "#111111",
    "bg_panel":    "#1A1A1A",
    "accent":      "#FFFFFF",
    "accent_h":    "#E0E0E0",
    "accent_p":    "#C0C0C0",
    "accent_btn":  "#2A2A2A",
    "accent_btn_h":"#3A3A3A",
    "text":        "#E8E8E8",
    "text_sec":    "#909090",
    "text_dim":    "#505050",
    "border":      "#2A2A2A",
    "border_l":    "#3A3A3A",
    "success":     "#8CBF8C",
    "error":       "#D48A8A",
    "warning":     "#C4B46C",
    "drop":        "#141414",
    "sel":         "#3A3A3A",
    "highlight":   "#FFFFFF",
}


def _stylesheet() -> str:
    return f"""
    QMainWindow, QWidget {{
        background-color: {C['bg']};
        color: {C['text']};
        font-family: 'Segoe UI', sans-serif;
        font-size: 12px;
    }}
    QLabel {{
        background: transparent;
        color: {C['text']};
        border: none;
    }}

    /* ── Buttons ── */
    QPushButton {{
        background-color: {C['accent_btn']};
        color: {C['text']};
        border: 1px solid {C['border_l']};
        border-radius: 4px;
        padding: 5px 14px;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background-color: {C['accent_btn_h']};
        border-color: #505050;
    }}
    QPushButton:pressed {{
        background-color: #4A4A4A;
    }}
    QPushButton:disabled {{
        color: {C['text_dim']};
        border-color: {C['border']};
        background-color: #181818;
    }}
    QPushButton[cssClass="primary"] {{
        background-color: {C['accent']};
        color: #000000;
        border: none;
        font-weight: bold;
        font-size: 13px;
        padding: 10px 24px;
        border-radius: 6px;
    }}
    QPushButton[cssClass="primary"]:hover {{
        background-color: {C['accent_h']};
    }}
    QPushButton[cssClass="primary"]:pressed {{
        background-color: {C['accent_p']};
    }}
    QPushButton[cssClass="primary"]:disabled {{
        background-color: #3A3A3A;
        color: #666;
    }}
    QPushButton[cssClass="danger"] {{
        background-color: transparent;
        color: {C['error']};
        border: 1px solid {C['error']};
    }}
    QPushButton[cssClass="danger"]:hover {{
        background-color: {C['error']};
        color: #000;
    }}

    /* ── GroupBox ── */
    QGroupBox {{
        background-color: {C['bg_mid']};
        border: 1px solid {C['border']};
        border-radius: 6px;
        margin-top: 12px;
        padding-top: 18px;
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 6px;
        color: {C['text_sec']};
        background-color: {C['bg_mid']};
    }}

    /* ── ComboBox ── */
    QComboBox {{
        background-color: {C['bg_input']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 4px;
        padding: 4px 8px;
        min-height: 20px;
    }}
    QComboBox:hover {{ border-color: #505050; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{
        background-color: {C['bg_mid']};
        color: {C['text']};
        border: 1px solid {C['border_l']};
        selection-background-color: {C['sel']};
    }}

    /* ── CheckBox ── */
    QCheckBox {{
        background: transparent;
        color: {C['text']};
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {C['border_l']};
        border-radius: 3px;
        background-color: {C['bg_input']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {C['accent']};
        border-color: {C['accent']};
    }}

    /* ── Table ── */
    QTableWidget {{
        background-color: {C['bg_input']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 4px;
        gridline-color: #1C1C1C;
        selection-background-color: {C['sel']};
        selection-color: #fff;
    }}
    QHeaderView::section {{
        background-color: {C['bg_mid']};
        color: {C['text_sec']};
        border: none;
        border-right: 1px solid {C['border']};
        border-bottom: 1px solid {C['border']};
        padding: 5px 8px;
        font-weight: bold;
        font-size: 11px;
    }}

    /* ── ProgressBar ── */
    QProgressBar {{
        background-color: {C['bg_input']};
        border: 1px solid {C['border']};
        border-radius: 4px;
        text-align: center;
        color: {C['text']};
        min-height: 18px;
    }}
    QProgressBar::chunk {{
        background-color: {C['accent_p']};
        border-radius: 3px;
    }}

    /* ── TextEdit ── */
    QTextEdit {{
        background-color: {C['bg_mid']};
        color: {C['text_sec']};
        border: 1px solid {C['border']};
        border-radius: 4px;
        padding: 6px;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 11px;
    }}

    /* ── TreeWidget (preview) ── */
    QTreeWidget {{
        background-color: {C['bg_input']};
        color: {C['text']};
        border: 1px solid {C['border']};
        border-radius: 4px;
        alternate-background-color: {C['bg_mid']};
        selection-background-color: {C['sel']};
        selection-color: #fff;
    }}
    QTreeWidget::item {{
        padding: 2px 4px;
        min-height: 20px;
    }}
    QTreeWidget::item:hover {{
        background-color: #1E1E1E;
    }}
    QTreeWidget::branch {{
        background: transparent;
    }}
    QHeaderView {{
        background-color: {C['bg_mid']};
    }}

    /* ── Scrollbar ── */
    QScrollBar:vertical {{
        background: {C['bg']};
        width: 8px;
        border: none;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {C['border_l']};
        min-height: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #555; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{
        background: {C['bg']};
        height: 8px;
        border: none;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {C['border_l']};
        min-width: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: #555; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* ── Splitter ── */
    QSplitter::handle {{
        background-color: {C['border']};
    }}
    QSplitter::handle:horizontal {{ width: 2px; }}
    QSplitter::handle:vertical {{ height: 2px; }}
    QSplitter::handle:hover {{ background-color: #555; }}

    /* ── Dialog ── */
    QDialog {{
        background-color: {C['bg']};
    }}
    """


# ── Rule DB locator ─────────────────────────────────────────────────────

_RULE_DB_NAME = "260329_최종본_v2.09_analysis_no_unobserved_7th_guardrail.json"


def _find_rule_db() -> str:
    if getattr(sys, "frozen", False):
        candidates = [
            Path(getattr(sys, "_MEIPASS", "")) / _RULE_DB_NAME,
            Path(sys.executable).parent / _RULE_DB_NAME,
            Path(sys.executable).parent.parent / _RULE_DB_NAME,
        ]
    else:
        candidates = [REPO_ROOT / _RULE_DB_NAME]
    for c in candidates:
        if c.is_file():
            return str(c)
    raise FileNotFoundError(f"Rule DB v2.09 not found: {candidates}")


# ── DropZone ─────────────────────────────────────────────────────────────


class DropZone(QLabel):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("MIDI 파일을 여기에 드래그 & 드롭\n또는 클릭하여 파일 선택")
        self.setMinimumHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._default_style()

    def _default_style(self):
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {C['drop']};
                border: 2px dashed {C['border_l']};
                border-radius: 8px;
                color: {C['text_dim']};
                font-size: 13px;
                padding: 14px;
            }}
        """)

    def _highlight_style(self):
        self.setStyleSheet(f"""
            QLabel {{
                background-color: #1A1A1A;
                border: 2px dashed {C['accent']};
                border-radius: 8px;
                color: {C['text']};
                font-size: 13px;
                padding: 14px;
            }}
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".mid", ".midi")):
                    event.acceptProposedAction()
                    self._highlight_style()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._default_style()

    def dropEvent(self, event: QDropEvent):
        self._default_style()
        paths = []
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        if f.lower().endswith((".mid", ".midi")):
                            paths.append(os.path.join(root, f))
            elif p.lower().endswith((".mid", ".midi")):
                paths.append(p)
        if paths:
            self.files_dropped.emit(paths)

    def mousePressEvent(self, event):
        files, _ = QFileDialog.getOpenFileNames(
            self, "MIDI 파일 선택", "",
            "MIDI Files (*.mid *.midi);;All Files (*)",
        )
        if files:
            self.files_dropped.emit(files)


# ── Preview Dialog ───────────────────────────────────────────────────────


class PreviewDialog(QDialog):
    """분석 결과 미리보기 창."""

    def __init__(self, filename: str, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"미리보기 — {filename}")
        self.setMinimumSize(900, 650)
        self.resize(1000, 700)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Header
        hdr = QLabel(f"  {filename}")
        hdr.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {C['text']}; padding: 4px 0;")
        root.addWidget(hdr)

        # Splitter: left=summary cards, right=JSON tree
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: Summary Cards ──
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        # Basic info card
        left_lay.addWidget(self._card("기본 정보", [
            ("파일", data.get("file", "")),
            ("BPM", str(data.get("bpm", ""))),
            ("트랙 수", str(data.get("num_tracks", ""))),
            ("총 노트", f"{data.get('total_notes', 0):,}"),
            ("Schema", data.get("schema_version", "")),
        ]))

        # Harmony card
        h = data.get("harmony", {})
        left_lay.addWidget(self._card("화성 분석", [
            ("전체 점수", f"{h.get('overall_score', 0)}/100"),
            ("코드 수", str(h.get("chord_count", 0))),
            ("추정 키", h.get("key_estimate", "?")),
            ("세그먼트", str(h.get("num_segments", 0))),
        ]))

        # Song form card
        sf = data.get("song_form", {})
        sections = sf.get("sections", [])
        section_labels = ", ".join(
            s.get("label", "?").upper() for s in sections[:6]
        )
        if len(sections) > 6:
            section_labels += f" ... (+{len(sections)-6})"
        left_lay.addWidget(self._card("곡 구조", [
            ("형식", sf.get("form_type", "?")),
            ("신뢰도", f"{sf.get('confidence', 0):.0%}"),
            ("총 마디", str(sf.get("total_bars", 0))),
            ("섹션", section_labels or "없음"),
        ]))

        # Playability card
        pl = data.get("playability", {})
        left_lay.addWidget(self._card("연주 가능성", [
            ("점수", f"{pl.get('score', 0)}/100"),
            ("통과", "Yes" if pl.get("pass") else "No"),
            ("이슈 수", str(pl.get("num_issues", 0))),
        ]))

        # Composer tags card
        tags = data.get("composer_tags", {})
        if tags:
            left_lay.addWidget(self._card("작곡가 태그", [
                ("리듬", tags.get("rhythm_type", "")),
                ("화성", tags.get("harmony_type", "")),
                ("반주", tags.get("accompaniment_pattern", "")),
                ("보이싱", tags.get("voicing_type", "")),
                ("다이나믹", tags.get("dynamic_profile", "")),
                ("템포", f"{tags.get('tempo_bpm', '')} ({tags.get('tempo_category', '')})"),
            ]))

        # Retrieval tags card
        rt = data.get("db_storage", {}).get("retrieval_tags", {})
        if rt:
            items = [(k, str(v)) for k, v in rt.items() if v]
            if items:
                left_lay.addWidget(self._card("검색 태그", items))

        left_lay.addStretch()

        # ── Right: JSON Tree ──
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(4)

        tree_hdr = QHBoxLayout()
        tree_lbl = QLabel("JSON 구조")
        tree_lbl.setStyleSheet(f"font-weight: bold; color: {C['text_sec']};")
        tree_hdr.addWidget(tree_lbl)
        tree_hdr.addStretch()
        btn_copy = QPushButton("JSON 복사")
        btn_copy.setFixedWidth(90)
        btn_copy.clicked.connect(lambda: self._copy_json(data))
        tree_hdr.addWidget(btn_copy)
        right_lay.addLayout(tree_hdr)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Key", "Value", "Type"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setColumnWidth(0, 220)
        self._tree.setColumnWidth(1, 350)
        self._tree.setColumnWidth(2, 70)
        self._populate_tree(self._tree.invisibleRootItem(), data)
        self._tree.expandToDepth(1)
        right_lay.addWidget(self._tree)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([340, 660])
        root.addWidget(splitter, 1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("닫기")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

    def _card(self, title: str, items: list[tuple[str, str]]) -> QGroupBox:
        grp = QGroupBox(title)
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.setSpacing(3)
        for label, value in items:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {C['text_sec']}; font-size: 11px;")
            lbl.setFixedWidth(80)
            val = QLabel(str(value))
            val.setStyleSheet(f"color: {C['text']}; font-size: 11px;")
            val.setWordWrap(True)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            lay.addLayout(row)
        return grp

    def _populate_tree(self, parent: QTreeWidgetItem, obj, depth: int = 0):
        if isinstance(obj, dict):
            for k, v in obj.items():
                item = QTreeWidgetItem(parent)
                item.setText(0, str(k))
                if isinstance(v, (dict, list)):
                    t = "dict" if isinstance(v, dict) else "list"
                    count = len(v)
                    item.setText(1, f"[{count} items]")
                    item.setText(2, t)
                    item.setForeground(1, QColor(C["text_dim"]))
                    item.setForeground(2, QColor(C["text_dim"]))
                    if depth < 4:
                        self._populate_tree(item, v, depth + 1)
                else:
                    item.setText(1, self._format_value(v))
                    item.setText(2, type(v).__name__)
                    item.setForeground(2, QColor(C["text_dim"]))
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:200]):
                item = QTreeWidgetItem(parent)
                item.setText(0, f"[{i}]")
                if isinstance(v, (dict, list)):
                    t = "dict" if isinstance(v, dict) else "list"
                    item.setText(1, f"[{len(v)} items]")
                    item.setText(2, t)
                    item.setForeground(1, QColor(C["text_dim"]))
                    item.setForeground(2, QColor(C["text_dim"]))
                    if depth < 4:
                        self._populate_tree(item, v, depth + 1)
                else:
                    item.setText(1, self._format_value(v))
                    item.setText(2, type(v).__name__)
                    item.setForeground(2, QColor(C["text_dim"]))
            if len(obj) > 200:
                more = QTreeWidgetItem(parent)
                more.setText(0, f"... +{len(obj)-200} more")
                more.setForeground(0, QColor(C["text_dim"]))

    def _format_value(self, v) -> str:
        if isinstance(v, float):
            return f"{v:.4f}" if abs(v) < 1 else f"{v:.2f}"
        if isinstance(v, bool):
            return "true" if v else "false"
        s = str(v)
        return s if len(s) <= 120 else s[:117] + "..."

    def _copy_json(self, data: dict):
        class _Enc(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, (np.integer,)):
                    return int(obj)
                if isinstance(obj, (np.floating,)):
                    return float(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                return super().default(obj)

        text = json.dumps(data, indent=2, ensure_ascii=False, cls=_Enc, default=str)
        QApplication.clipboard().setText(text)


# ── Worker Thread ────────────────────────────────────────────────────────


class _Enc(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class ExtractionWorker(QThread):
    progress = pyqtSignal(int, int, str)
    file_done = pyqtSignal(str, dict, dict)  # filename, summary, full_result
    file_error = pyqtSignal(str, str)
    all_done = pyqtSignal(dict)
    log = pyqtSignal(str)

    def __init__(
        self,
        midi_paths: list[str],
        output_dir: str,
        key_override: str | None,
        scale_override: str | None,
        rule_db_path: str,
        save_analyzed: bool,
        rebuild_lib: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.midi_paths = midi_paths
        self.output_dir = output_dir
        self.key_override = key_override
        self.scale_override = scale_override
        self.rule_db_path = rule_db_path
        self.save_analyzed = save_analyzed
        self.rebuild_lib = rebuild_lib
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        from core.harmony_engine import HarmonyEngine

        self.log.emit("Rule DB v2.09 로딩 중...")
        try:
            engine = HarmonyEngine(db_path=self.rule_db_path)
        except Exception as e:
            self.log.emit(f"Rule DB 로딩 실패: {e}")
            self.all_done.emit({"total": 0, "successes": 0, "failures": len(self.midi_paths), "elapsed_sec": 0})
            return
        self.log.emit(f"  Schema version: {engine.schema_version}")

        os.makedirs(self.output_dir, exist_ok=True)
        successes = 0
        failures = 0
        t0 = time.time()

        for i, midi_path in enumerate(self.midi_paths):
            if self._cancelled:
                self.log.emit("\n추출이 취소되었습니다.")
                break

            fname = os.path.basename(midi_path)
            self.progress.emit(i + 1, len(self.midi_paths), fname)
            self.log.emit(f"\n[{i + 1}/{len(self.midi_paths)}] {fname}")

            try:
                result = self._process_one(engine, midi_path)
                successes += 1
                summary = {
                    "notes": result.get("total_notes", 0),
                    "chords": result.get("harmony", {}).get("chord_count", 0),
                    "form": result.get("song_form", {}).get("form_type", "?"),
                    "play": result.get("playability", {}).get("score", 0),
                }
                self.file_done.emit(fname, summary, result)
            except Exception as e:
                failures += 1
                self.log.emit(f"  ERROR: {e}")
                self.file_error.emit(fname, str(e))

        if successes > 0 and self.rebuild_lib and not self._cancelled:
            self._rebuild_patterns()

        elapsed = round(time.time() - t0, 1)
        self.all_done.emit({
            "total": len(self.midi_paths),
            "successes": successes,
            "failures": failures,
            "elapsed_sec": elapsed,
        })

    def _process_one(self, engine, midi_path: str) -> dict:
        from auto_ingest import parse_midi_to_tracks

        path = Path(midi_path).resolve()

        self.log.emit("  MIDI 파싱 중...")
        tracks, bpm, tpb = parse_midi_to_tracks(str(path))
        if not tracks:
            raise ValueError("노트 데이터 없음")

        all_notes: list[Note] = []
        for t in tracks:
            all_notes.extend(t.notes)
        all_notes.sort(key=lambda n: n.start_tick)
        combined = Track(name="Combined", channel=0, notes=all_notes)

        key = self.key_override or "C"
        scale = self.scale_override or "minor"

        self.log.emit("  화성 분석 중...")
        harmony = engine.analyze_harmony(combined, key=key, scale=scale)

        self.log.emit("  곡 구조 분석 중...")
        project = ProjectState(
            name=path.stem, tracks=tracks, bpm=bpm,
            key=key, scale=scale, ticks_per_beat=tpb,
        )
        song_form = engine.analyze_song_form(project)

        self.log.emit("  연주 가능성 검증 중...")
        playability = engine.validate_playability(all_notes)

        embedding_result = {}
        try:
            from midi_embedding import analyze_midi as compute_embedding
            self.log.emit("  임베딩 생성 중...")
            embedding_result = compute_embedding(str(path))
        except Exception as e:
            self.log.emit(f"  임베딩 건너뜀: {e}")

        # Build output
        midi_id = f"{path.stem}_{uuid.uuid4().hex[:8]}"
        segments = harmony.get("segments", [])
        tags = embedding_result.get("composer_tags", {})

        harmonic_events = []
        for idx, seg in enumerate(segments):
            harmonic_events.append({
                "event_id": f"{midi_id}_he_{idx}",
                "source_midi_id": midi_id,
                "bar_index": seg.get("bar", 0),
                "tick_start": seg.get("start_tick", 0),
                "tick_end": seg.get("end_tick", 0),
                "absolute_chord_label": seg.get("chord", "N.C."),
                "bass_pitch": seg.get("bass", ""),
                "root": seg.get("root", ""),
                "quality": seg.get("quality", ""),
                "confidence": seg.get("confidence", 0),
                "is_slash": seg.get("is_slash", False),
            })

        retrieval_tags = {
            "style": tags.get("accompaniment_pattern", ""),
            "tempo_range": tags.get("tempo_category", ""),
            "texture_type": tags.get("harmony_type", ""),
            "density_level": tags.get("rhythm_type", ""),
            "chord_family": "",
            "melody_role_context": "",
            "bass_motion_type": "",
            "arpeggio_or_block": tags.get("accompaniment_pattern", ""),
            "dynamic_profile": tags.get("dynamic_profile", ""),
            "register": tags.get("register", ""),
            "voicing_type": tags.get("voicing_type", ""),
        }

        result = {
            "file": path.name,
            "midi_id": midi_id,
            "schema_version": "2.09",
            "extracted_at": datetime.now().isoformat(timespec="seconds"),
            "bpm": bpm,
            "ticks_per_beat": tpb,
            "num_tracks": len(tracks),
            "total_notes": len(all_notes),
            "harmony": {
                "overall_score": harmony.get("overall_score", 0),
                "chord_count": harmony.get("chord_count", 0),
                "key_estimate": harmony.get("key_estimate", "C"),
                "num_segments": len(segments),
                "segments": segments,
            },
            "song_form": {
                "form_type": song_form.get("form_type", "unknown"),
                "confidence": song_form.get("confidence", 0.0),
                "total_bars": song_form.get("total_bars", 0),
                "sections": song_form.get("sections", []),
            },
            "playability": {
                "score": playability.get("score", 0),
                "pass": playability.get("pass", False),
                "num_issues": len(playability.get("issues", [])),
                "issues_sample": playability.get("issues", [])[:10],
            },
            "embedding": embedding_result.get("embedding", []),
            "composer_tags": tags,
            "db_storage": {
                "harmonic_events": harmonic_events,
                "retrieval_tags": retrieval_tags,
            },
        }

        # Save
        safe_name = path.stem.replace(" ", "_")
        out_path = Path(self.output_dir) / f"{safe_name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, cls=_Enc, default=str)
        self.log.emit(f"  저장: {out_path}")

        if self.save_analyzed:
            analyzed_dir = REPO_ROOT / "analyzed_chords"
            analyzed_dir.mkdir(exist_ok=True)
            with open(analyzed_dir / f"{safe_name}.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False, cls=_Enc, default=str)

        if embedding_result:
            embed_dir = REPO_ROOT / "embeddings" / "individual"
            embed_dir.mkdir(parents=True, exist_ok=True)
            with open(embed_dir / f"{safe_name}.json", "w", encoding="utf-8") as f:
                json.dump(embedding_result, f, indent=2, ensure_ascii=False, cls=_Enc)

        self.log.emit(
            f"  완료: {len(all_notes)} notes, "
            f"{harmony.get('chord_count', 0)} chords, "
            f"form={song_form.get('form_type', '?')}, "
            f"playability={playability.get('score', 0)}"
        )
        return result

    def _rebuild_patterns(self):
        self.log.emit("\n패턴 라이브러리 재구축 중...")
        try:
            from auto_ingest import rebuild_patterns
            rebuild_patterns()
            self.log.emit("  패턴 라이브러리 재구축 완료.")
        except Exception as e:
            self.log.emit(f"  패턴 라이브러리 재구축 실패: {e}")


# ── Main Window ──────────────────────────────────────────────────────────

_KEYS = ["Auto", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_SCALES = ["Auto", "major", "minor", "dorian", "mixolydian"]
_TABLE_COLS = ["#", "파일명", "상태", "노트", "코드", "구조", "연주", "미리보기"]


class PatternExtractorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIDI Pattern Extractor v1.0")
        self.setMinimumSize(920, 750)
        self.resize(980, 830)
        self._midi_files: list[str] = []
        self._results: dict[str, dict] = {}  # filename -> full result
        self._worker: ExtractionWorker | None = None
        self._output_dir = str(REPO_ROOT / "output" / "extracted_patterns")

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)
        root.setContentsMargins(14, 10, 14, 10)

        # ── Title ──
        hdr = QHBoxLayout()
        title = QLabel("MIDI Pattern Extractor")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {C['text']}; padding: 2px 0;")
        ver = QLabel("v1.0  |  Rule DB v2.09")
        ver.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(ver)
        root.addLayout(hdr)

        # ── Drop zone ──
        self._drop = DropZone()
        self._drop.files_dropped.connect(self._add_files)
        root.addWidget(self._drop)

        # ── File table header ──
        tbl_hdr = QHBoxLayout()
        tbl_lbl = QLabel("파일 목록")
        tbl_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        self._file_count = QLabel("0개")
        self._file_count.setStyleSheet(f"color: {C['text_sec']}; font-size: 11px;")
        tbl_hdr.addWidget(tbl_lbl)
        tbl_hdr.addWidget(self._file_count)
        tbl_hdr.addStretch()
        btn_remove = QPushButton("선택 삭제")
        btn_remove.setFixedWidth(80)
        btn_remove.clicked.connect(self._remove_selected)
        btn_clear = QPushButton("전체 삭제")
        btn_clear.setProperty("cssClass", "danger")
        btn_clear.setFixedWidth(80)
        btn_clear.clicked.connect(self._clear_files)
        tbl_hdr.addWidget(btn_remove)
        tbl_hdr.addWidget(btn_clear)
        root.addLayout(tbl_hdr)

        # ── Table ──
        self._table = QTableWidget(0, len(_TABLE_COLS))
        self._table.setHorizontalHeaderLabels(_TABLE_COLS)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setMaximumHeight(200)
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(0, 30)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in range(2, len(_TABLE_COLS)):
            h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self._table.cellDoubleClicked.connect(self._on_table_dbl_click)
        root.addWidget(self._table)

        # ── Settings ──
        grp = QGroupBox("설정")
        gl = QVBoxLayout(grp)
        gl.setSpacing(6)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("출력 경로:"))
        self._dir_label = QLabel(self._output_dir)
        self._dir_label.setStyleSheet(f"color: {C['text_sec']}; font-size: 11px;")
        dir_row.addWidget(self._dir_label, 1)
        btn_dir = QPushButton("변경")
        btn_dir.setFixedWidth(60)
        btn_dir.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(btn_dir)
        gl.addLayout(dir_row)

        ks_row = QHBoxLayout()
        ks_row.addWidget(QLabel("Key:"))
        self._key_combo = QComboBox()
        self._key_combo.addItems(_KEYS)
        self._key_combo.setFixedWidth(70)
        ks_row.addWidget(self._key_combo)
        ks_row.addSpacing(12)
        ks_row.addWidget(QLabel("Scale:"))
        self._scale_combo = QComboBox()
        self._scale_combo.addItems(_SCALES)
        self._scale_combo.setFixedWidth(110)
        ks_row.addWidget(self._scale_combo)
        ks_row.addStretch()
        gl.addLayout(ks_row)

        chk_row = QHBoxLayout()
        self._chk_analyzed = QCheckBox("analyzed_chords/ 에도 저장")
        self._chk_analyzed.setChecked(True)
        self._chk_rebuild = QCheckBox("추출 후 패턴 라이브러리 재구축")
        self._chk_rebuild.setChecked(True)
        chk_row.addWidget(self._chk_analyzed)
        chk_row.addSpacing(16)
        chk_row.addWidget(self._chk_rebuild)
        chk_row.addStretch()
        gl.addLayout(chk_row)
        root.addWidget(grp)

        # ── Action bar ──
        act_row = QHBoxLayout()
        act_row.addStretch()
        self._btn_extract = QPushButton("패턴 추출 시작")
        self._btn_extract.setProperty("cssClass", "primary")
        self._btn_extract.setFixedHeight(40)
        self._btn_extract.setMinimumWidth(200)
        self._btn_extract.setEnabled(False)
        self._btn_extract.clicked.connect(self._start_extraction)
        act_row.addWidget(self._btn_extract)
        self._btn_cancel = QPushButton("취소")
        self._btn_cancel.setFixedHeight(40)
        self._btn_cancel.setVisible(False)
        self._btn_cancel.clicked.connect(self._cancel_extraction)
        act_row.addWidget(self._btn_cancel)
        act_row.addStretch()
        root.addLayout(act_row)

        # ── Progress ──
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(True)
        root.addWidget(self._progress)

        # ── Log ──
        log_lbl = QLabel("로그")
        log_lbl.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {C['text_sec']};")
        root.addWidget(log_lbl)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(100)
        root.addWidget(self._log, 1)

        # ── Result ──
        self._result_label = QLabel("")
        self._result_label.setStyleSheet(f"color: {C['success']}; font-weight: bold; padding: 2px 0;")
        root.addWidget(self._result_label)

        self.setStyleSheet(_stylesheet())
        self._apply_palette()

    def _apply_palette(self):
        p = QPalette()
        p.setColor(QPalette.ColorRole.Window, QColor(C["bg"]))
        p.setColor(QPalette.ColorRole.WindowText, QColor(C["text"]))
        p.setColor(QPalette.ColorRole.Base, QColor(C["bg_input"]))
        p.setColor(QPalette.ColorRole.Text, QColor(C["text"]))
        p.setColor(QPalette.ColorRole.Button, QColor(C["accent_btn"]))
        p.setColor(QPalette.ColorRole.ButtonText, QColor(C["text"]))
        p.setColor(QPalette.ColorRole.Highlight, QColor(C["sel"]))
        p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(p)

    # ── File management ──

    def _add_files(self, paths: list[str]):
        existing = set(self._midi_files)
        for p in paths:
            if p not in existing:
                self._midi_files.append(p)
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
                self._table.setItem(row, 1, QTableWidgetItem(os.path.basename(p)))
                wait = QTableWidgetItem("대기")
                wait.setForeground(QColor(C["text_dim"]))
                self._table.setItem(row, 2, wait)
                # Empty preview button cell
                self._table.setItem(row, 7, QTableWidgetItem(""))
        self._btn_extract.setEnabled(len(self._midi_files) > 0)
        self._file_count.setText(f"{len(self._midi_files)}개")
        self._drop.setText(f"{len(self._midi_files)}개 파일 추가됨 — 추가 드래그 가능")

    def _remove_selected(self):
        rows = sorted(set(idx.row() for idx in self._table.selectedIndexes()), reverse=True)
        for r in rows:
            if 0 <= r < len(self._midi_files):
                fname = os.path.basename(self._midi_files[r])
                self._midi_files.pop(r)
                self._results.pop(fname, None)
                self._table.removeRow(r)
        for i in range(self._table.rowCount()):
            self._table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
        self._btn_extract.setEnabled(len(self._midi_files) > 0)
        self._file_count.setText(f"{len(self._midi_files)}개")

    def _clear_files(self):
        self._midi_files.clear()
        self._results.clear()
        self._table.setRowCount(0)
        self._btn_extract.setEnabled(False)
        self._file_count.setText("0개")
        self._drop.setText("MIDI 파일을 여기에 드래그 & 드롭\n또는 클릭하여 파일 선택")

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "출력 폴더 선택", self._output_dir)
        if d:
            self._output_dir = d
            self._dir_label.setText(d)

    # ── Preview ──

    def _on_table_dbl_click(self, row: int, col: int):
        item = self._table.item(row, 1)
        if not item:
            return
        fname = item.text()
        if fname in self._results:
            self._open_preview(fname)

    def _open_preview(self, filename: str):
        data = self._results.get(filename)
        if not data:
            return
        dlg = PreviewDialog(filename, data, parent=self)
        dlg.setStyleSheet(_stylesheet())
        dlg.exec()

    def _add_preview_button(self, row: int, filename: str):
        btn = QPushButton("보기")
        btn.setFixedSize(50, 24)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {C['accent_btn']};
                color: {C['text']};
                border: 1px solid {C['border_l']};
                border-radius: 3px;
                font-size: 11px;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: {C['accent_btn_h']};
                border-color: #555;
            }}
        """)
        btn.clicked.connect(lambda checked, fn=filename: self._open_preview(fn))
        self._table.setCellWidget(row, 7, btn)

    # ── Extraction ──

    def _start_extraction(self):
        if not self._midi_files:
            return
        try:
            rule_db = _find_rule_db()
        except FileNotFoundError as e:
            QMessageBox.critical(self, "Rule DB 오류", str(e))
            return

        key = self._key_combo.currentText()
        scale = self._scale_combo.currentText()

        self._btn_extract.setEnabled(False)
        self._btn_cancel.setVisible(True)
        self._progress.setVisible(True)
        self._progress.setMaximum(len(self._midi_files))
        self._progress.setValue(0)
        self._result_label.setText("")
        self._log.clear()

        for i in range(self._table.rowCount()):
            wait = QTableWidgetItem("처리중...")
            wait.setForeground(QColor(C["warning"]))
            self._table.setItem(i, 2, wait)
            for col in range(3, len(_TABLE_COLS)):
                self._table.setItem(i, col, QTableWidgetItem(""))
            self._table.removeCellWidget(i, 7)

        self._worker = ExtractionWorker(
            midi_paths=list(self._midi_files),
            output_dir=self._output_dir,
            key_override=key if key != "Auto" else None,
            scale_override=scale if scale != "Auto" else None,
            rule_db_path=rule_db,
            save_analyzed=self._chk_analyzed.isChecked(),
            rebuild_lib=self._chk_rebuild.isChecked(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.file_error.connect(self._on_file_error)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.log.connect(self._on_log)
        self._worker.start()

    def _cancel_extraction(self):
        if self._worker:
            self._worker.cancel()

    def _on_progress(self, current: int, total: int, filename: str):
        self._progress.setValue(current)
        self._progress.setFormat(f"{current}/{total}  {filename}")

    def _on_file_done(self, filename: str, summary: dict, full_result: dict):
        self._results[filename] = full_result
        row = self._find_row(filename)
        if row < 0:
            return
        ok = QTableWidgetItem("완료")
        ok.setForeground(QColor(C["success"]))
        self._table.setItem(row, 2, ok)
        self._table.setItem(row, 3, QTableWidgetItem(str(summary.get("notes", ""))))
        self._table.setItem(row, 4, QTableWidgetItem(str(summary.get("chords", ""))))
        self._table.setItem(row, 5, QTableWidgetItem(str(summary.get("form", ""))))
        self._table.setItem(row, 6, QTableWidgetItem(str(summary.get("play", ""))))
        self._add_preview_button(row, filename)

    def _on_file_error(self, filename: str, error: str):
        row = self._find_row(filename)
        if row < 0:
            return
        err = QTableWidgetItem("실패")
        err.setForeground(QColor(C["error"]))
        err.setToolTip(error)
        self._table.setItem(row, 2, err)

    def _on_all_done(self, summary: dict):
        self._btn_extract.setEnabled(True)
        self._btn_cancel.setVisible(False)
        self._progress.setVisible(False)
        s = summary
        self._result_label.setText(
            f"추출 완료: {s['successes']}/{s['total']}개 성공, "
            f"{s['failures']}개 실패, {s['elapsed_sec']}초 소요"
        )
        color = C["success"] if s["failures"] == 0 else C["warning"]
        self._result_label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 2px 0;")

    def _on_log(self, text: str):
        self._log.append(text)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _find_row(self, filename: str) -> int:
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 1)
            if item and item.text() == filename:
                return i
        return -1


# ── Entry point ──────────────────────────────────────────────────────────


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MIDI Pattern Extractor")
    app.setOrganizationName("MidiAI")
    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI", 10))
    w = PatternExtractorWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        app = QApplication.instance()
        if app:
            QMessageBox.critical(None, "Fatal Error", tb)
        sys.exit(1)
