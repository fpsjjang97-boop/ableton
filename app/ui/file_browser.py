"""
File Browser Panel -- Ableton-style left sidebar with category navigation,
file tree, and info view.
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLabel, QLineEdit, QPushButton, QHeaderView, QMenu, QFrame,
    QScrollArea, QSizePolicy, QTextEdit, QSplitter, QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal, QFileInfo, QDir, QSize
from PyQt6.QtGui import QFont, QColor, QIcon, QAction, QPainter

from config import COLORS

_SUPPORTED_EXTENSIONS = {".mid", ".midi", ".wav", ".mp3", ".maw", ".json"}

_TYPE_ICONS = {
    ".mid": "\u266a",
    ".midi": "\u266a",
    ".wav": "\u223f",
    ".mp3": "\u223f",
    ".maw": "\u2662",
    ".json": "{}",
}

# -- Categories ---------------------------------------------------------------

CATEGORIES = {
    "Collections": ["Favorites", "Recent"],
    "Library": [
        "MIDI Files",
        "Instruments",
        "Scales & Keys",
        "AI Presets",
        "Embeddings",
        "Templates",
    ],
    "Project": ["Project Files", "Output", "Reviewed"],
}

# -- Stylesheet ---------------------------------------------------------------

_STYLE = f"""
    QWidget {{
        background-color: {COLORS['bg_dark']};
        color: {COLORS['text_primary']};
        font-family: "Segoe UI", "Helvetica Neue", sans-serif;
    }}

    /* Search bar */
    QLineEdit#searchBar {{
        background-color: {COLORS['bg_darkest']};
        border: 1px solid {COLORS['border']};
        border-radius: 3px;
        padding: 5px 8px 5px 8px;
        color: {COLORS['text_primary']};
        font-size: 11px;
    }}
    QLineEdit#searchBar:focus {{
        border-color: {COLORS['border_focus']};
    }}

    /* Category sidebar scroll area */
    QScrollArea#categoryScroll {{
        background-color: {COLORS['bg_dark']};
        border: none;
    }}

    /* Section headers */
    QLabel#sectionHeader {{
        color: {COLORS['text_dim']};
        font-size: 10px;
        font-weight: bold;
        padding: 6px 8px 2px 8px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}

    /* Category items */
    QPushButton.categoryItem {{
        background-color: transparent;
        color: {COLORS['text_secondary']};
        border: none;
        border-left: 3px solid transparent;
        border-radius: 0px;
        text-align: left;
        padding: 4px 10px 4px 14px;
        font-size: 11px;
        min-height: 20px;
    }}
    QPushButton.categoryItem:hover {{
        background-color: {COLORS['bg_hover']};
        color: {COLORS['text_primary']};
    }}
    QPushButton.categoryItem[selected="true"] {{
        background-color: {COLORS['bg_selected']};
        color: {COLORS['text_primary']};
        border-left: 3px solid {COLORS['accent']};
    }}

    /* File tree */
    QTreeWidget#fileTree {{
        background-color: {COLORS['bg_darkest']};
        border: 1px solid {COLORS['border']};
        border-radius: 2px;
        font-size: 11px;
        outline: none;
    }}
    QTreeWidget#fileTree::item {{
        padding: 2px 4px;
        border: none;
    }}
    QTreeWidget#fileTree::item:hover {{
        background-color: {COLORS['bg_hover']};
    }}
    QTreeWidget#fileTree::item:selected {{
        background-color: {COLORS['bg_selected']};
        color: {COLORS['text_accent']};
    }}
    QHeaderView::section {{
        background-color: {COLORS['bg_mid']};
        color: {COLORS['text_dim']};
        border: none;
        border-right: 1px solid {COLORS['border']};
        padding: 3px 6px;
        font-size: 10px;
    }}

    /* Info view */
    QFrame#infoView {{
        background-color: {COLORS['bg_darkest']};
        border: 1px solid {COLORS['border']};
        border-radius: 2px;
    }}
    QLabel#infoHeader {{
        color: {COLORS['text_dim']};
        font-size: 10px;
        font-weight: bold;
        padding: 4px 6px 2px 6px;
    }}
    QLabel#infoText {{
        color: {COLORS['text_secondary']};
        font-size: 10px;
        padding: 2px 6px 4px 6px;
    }}

    /* Context menu */
    QMenu {{
        background: {COLORS['bg_mid']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        font-size: 11px;
    }}
    QMenu::item:selected {{
        background: {COLORS['bg_selected']};
    }}

    /* Splitter handle */
    QSplitter::handle {{
        background-color: {COLORS['separator']};
        height: 2px;
    }}
"""


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.0f} {unit}" if unit == "B" else f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


# =============================================================================
# FileBrowser
# =============================================================================

class FileBrowser(QWidget):
    """Ableton-style left browser panel with categories, file tree, info view."""

    file_selected = pyqtSignal(str)
    file_double_clicked = pyqtSignal(str)
    category_changed = pyqtSignal(str)

    def __init__(self, parent=None, root_path: str | None = None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(320)
        self.setFixedWidth(250)
        self.setStyleSheet(_STYLE)

        self._root = root_path or os.getcwd()
        self._favorites: list[str] = []
        self._recent: list[str] = []
        self._current_category = "MIDI Files"
        self._category_buttons: dict[str, QPushButton] = {}
        self._info_visible = True

        self._build_ui()
        self._select_category("MIDI Files")

    # -- UI construction ------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Search bar
        search_row = QHBoxLayout()
        search_row.setContentsMargins(6, 6, 6, 4)
        self._search = QLineEdit()
        self._search.setObjectName("searchBar")
        self._search.setPlaceholderText("\U0001f50d  Search files...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self._search)
        outer.addLayout(search_row)

        # Main splitter: category sidebar + file tree  |  info view
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setChildrenCollapsible(True)

        # Top container (categories + file tree)
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        # Category sidebar (scrollable)
        self._category_area = QScrollArea()
        self._category_area.setObjectName("categoryScroll")
        self._category_area.setWidgetResizable(True)
        self._category_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._category_area.setFrameShape(QFrame.Shape.NoFrame)
        self._category_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )

        cat_widget = QWidget()
        cat_layout = QVBoxLayout(cat_widget)
        cat_layout.setContentsMargins(0, 2, 0, 4)
        cat_layout.setSpacing(0)

        for section, items in CATEGORIES.items():
            # Section header
            header = QLabel(section.upper())
            header.setObjectName("sectionHeader")
            cat_layout.addWidget(header)

            for name in items:
                btn = QPushButton(name)
                btn.setProperty("class", "categoryItem")
                btn.setProperty("selected", False)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, n=name: self._select_category(n))
                cat_layout.addWidget(btn)
                self._category_buttons[name] = btn

        self._category_area.setWidget(cat_widget)
        top_layout.addWidget(self._category_area)

        # Thin separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['separator']};")
        sep.setFixedHeight(1)
        top_layout.addWidget(sep)

        # File tree
        self._file_tree = self._build_file_tree()
        top_layout.addWidget(self._file_tree, 1)

        self._splitter.addWidget(top_widget)

        # Info view (bottom)
        self._info_frame = QFrame()
        self._info_frame.setObjectName("infoView")
        info_layout = QVBoxLayout(self._info_frame)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)

        info_header_row = QHBoxLayout()
        info_header_row.setContentsMargins(0, 0, 4, 0)
        info_header_label = QLabel("Info View")
        info_header_label.setObjectName("infoHeader")
        info_header_row.addWidget(info_header_label)
        info_header_row.addStretch()

        toggle_btn = QPushButton("\u25bc")
        toggle_btn.setFixedSize(16, 16)
        toggle_btn.setStyleSheet(
            f"background: transparent; color: {COLORS['text_dim']}; "
            "border: none; font-size: 9px;"
        )
        toggle_btn.clicked.connect(self._toggle_info)
        info_header_row.addWidget(toggle_btn)
        info_layout.addLayout(info_header_row)

        self._info_label = QLabel("Select an item to see details.")
        self._info_label.setObjectName("infoText")
        self._info_label.setWordWrap(True)
        self._info_label.setMinimumHeight(28)
        info_layout.addWidget(self._info_label)

        self._splitter.addWidget(self._info_frame)

        # Splitter proportions: categories+tree gets most, info gets small slice
        self._splitter.setStretchFactor(0, 5)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([400, 60])

        outer.addWidget(self._splitter, 1)

    def _build_file_tree(self) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setObjectName("fileTree")
        tree.setHeaderLabels(["Name", "Type", "Date"])
        tree.header().setStretchLastSection(False)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        tree.setRootIsDecorated(True)
        tree.setDragEnabled(True)
        tree.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        tree.setIndentation(14)
        tree.itemClicked.connect(self._on_item_clicked)
        tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.customContextMenuRequested.connect(self._on_context_menu)
        return tree

    # -- Category selection ---------------------------------------------------

    def _select_category(self, name: str):
        self._current_category = name
        # Update button states
        for btn_name, btn in self._category_buttons.items():
            is_sel = btn_name == name
            btn.setProperty("selected", is_sel)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.category_changed.emit(name)
        self.refresh()

    # -- Population -----------------------------------------------------------

    def _populate_tree(self, parent_item, dir_path: str, search: str = ""):
        """Recursively populate *parent_item* from *dir_path*."""
        try:
            entries = sorted(
                os.scandir(dir_path),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                folder_item = QTreeWidgetItem(parent_item, [entry.name, "\U0001f4c1", ""])
                folder_item.setData(0, Qt.ItemDataRole.UserRole, entry.path)
                folder_item.setForeground(0, QColor(COLORS["text_secondary"]))
                self._populate_tree(folder_item, entry.path, search)
                if folder_item.childCount() == 0 and search:
                    idx = parent_item.indexOfChild(folder_item)
                    parent_item.removeChild(folder_item)
            elif entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext not in _SUPPORTED_EXTENSIONS:
                    continue
                if search and search not in entry.name.lower():
                    continue
                tag = _TYPE_ICONS.get(ext, "\u00b7")
                info = QFileInfo(entry.path)
                date_str = info.lastModified().toString("yyyy-MM-dd")
                item = QTreeWidgetItem(parent_item, [entry.name, tag, date_str])
                item.setData(0, Qt.ItemDataRole.UserRole, entry.path)

    def _populate_flat(self, entries: list[str]):
        """Populate the tree with a flat list of file paths."""
        self._file_tree.clear()
        for path in entries:
            if not os.path.exists(path):
                continue
            name = os.path.basename(path)
            ext = os.path.splitext(name)[1].lower()
            tag = _TYPE_ICONS.get(ext, "\u00b7")
            info = QFileInfo(path)
            date_str = info.lastModified().toString("yyyy-MM-dd")
            item = QTreeWidgetItem(self._file_tree, [name, tag, date_str])
            item.setData(0, Qt.ItemDataRole.UserRole, path)

    def refresh(self):
        """Reload the file tree based on the current category."""
        search = self._search.text().strip().lower()
        cat = self._current_category

        if cat == "Favorites":
            self._populate_flat(self._favorites)
            return
        if cat == "Recent":
            self._populate_flat(self._recent)
            return

        # Directory-based categories
        dir_map = {
            "MIDI Files": self._root,
            "Instruments": os.path.join(self._root, "instruments"),
            "Scales & Keys": os.path.join(self._root, "scales"),
            "AI Presets": os.path.join(self._root, "ai_presets"),
            "Embeddings": os.path.join(self._root, "embeddings"),
            "Templates": os.path.join(self._root, "templates"),
            "Project Files": self._root,
            "Output": os.path.join(self._root, "output"),
            "Reviewed": os.path.join(self._root, "reviewed"),
        }

        target = dir_map.get(cat, self._root)
        self._file_tree.clear()

        if not os.path.isdir(target):
            placeholder = QTreeWidgetItem(self._file_tree, [f"({cat} folder not found)", "", ""])
            placeholder.setForeground(0, QColor(COLORS["text_dim"]))
            return

        root_item = QTreeWidgetItem(self._file_tree, [os.path.basename(target), "", ""])
        root_item.setData(0, Qt.ItemDataRole.UserRole, target)
        root_item.setForeground(0, QColor(COLORS["accent"]))
        root_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self._populate_tree(root_item, target, search)
        root_item.setExpanded(True)

    # -- Public API -----------------------------------------------------------

    def set_root(self, path: str):
        """Change the root directory and refresh."""
        if os.path.isdir(path):
            self._root = path
            self.refresh()

    def get_selected_file(self) -> str:
        """Return the path of the currently selected file, or empty string."""
        items = self._file_tree.selectedItems()
        if not items:
            return ""
        path = items[0].data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            return path
        return ""

    def set_info_text(self, text: str):
        """Set the info view description text."""
        self._info_label.setText(text)

    def add_favorite(self, path: str):
        if path not in self._favorites:
            self._favorites.append(path)
            if self._current_category == "Favorites":
                self.refresh()

    def add_recent(self, path: str):
        if path in self._recent:
            self._recent.remove(path)
        self._recent.insert(0, path)
        self._recent = self._recent[:30]

    # -- Callbacks ------------------------------------------------------------

    def _on_search_changed(self, _text: str):
        self.refresh()

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            self.file_selected.emit(path)
            info = QFileInfo(path)
            mod = info.lastModified().toString("yyyy-MM-dd HH:mm")
            self.set_info_text(
                f"{info.fileName()}\n"
                f"Size: {_human_size(info.size())}   Modified: {mod}"
            )

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            self.file_double_clicked.emit(path)
            self.add_recent(path)

    def _on_context_menu(self, pos):
        item = self._file_tree.itemAt(pos)
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        if path and os.path.isdir(path):
            act = QAction("Add to Favorites", self)
            act.triggered.connect(lambda: self.add_favorite(path))
            menu.addAction(act)
        if path and os.path.isfile(path):
            act_open = QAction("Open / Import", self)
            act_open.triggered.connect(lambda: self.file_double_clicked.emit(path))
            menu.addAction(act_open)
            act_fav = QAction("Add to Favorites", self)
            act_fav.triggered.connect(lambda: self.add_favorite(path))
            menu.addAction(act_fav)
        if menu.actions():
            menu.exec(self._file_tree.viewport().mapToGlobal(pos))

    def _toggle_info(self):
        """Show/hide the info text portion."""
        self._info_visible = not self._info_visible
        self._info_label.setVisible(self._info_visible)
