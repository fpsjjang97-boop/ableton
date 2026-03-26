"""
Comprehensive Qt stylesheet for MIDI AI Workstation.

Dark theme inspired by Ableton Live, FL Studio, and modern DAW aesthetics.
Provides pixel-perfect styling for every widget in the application.
"""

from config import COLORS


def get_stylesheet() -> str:
    """Return the complete QSS stylesheet string for the application."""

    c = COLORS  # shorthand

    return f"""

    /* ================================================================
       GLOBAL DEFAULTS
       ================================================================ */

    * {{
        font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
        font-size: 12px;
        color: {c['text_primary']};
        outline: none;
    }}

    QMainWindow {{
        background-color: {c['bg_darkest']};
        border: none;
    }}

    QWidget {{
        background-color: {c['bg_darkest']};
        border: none;
    }}

    /* ================================================================
       MENU BAR & MENUS
       ================================================================ */

    QMenuBar {{
        background-color: {c['bg_dark']};
        color: {c['text_primary']};
        border-bottom: 1px solid {c['border']};
        padding: 2px 0px;
        spacing: 0px;
    }}

    QMenuBar::item {{
        background: transparent;
        padding: 5px 10px;
        border-radius: 3px;
        margin: 1px 2px;
    }}

    QMenuBar::item:selected {{
        background-color: {c['bg_hover']};
    }}

    QMenuBar::item:pressed {{
        background-color: {c['accent']};
        color: #FFFFFF;
    }}

    QMenu {{
        background-color: {c['bg_dark']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 4px 0px;
    }}

    QMenu::item {{
        padding: 6px 28px 6px 20px;
        border: none;
        background: transparent;
    }}

    QMenu::item:selected {{
        background-color: {c['bg_hover']};
        color: #FFFFFF;
    }}

    QMenu::item:disabled {{
        color: {c['text_dim']};
    }}

    QMenu::separator {{
        height: 1px;
        background: {c['border']};
        margin: 4px 8px;
    }}

    QMenu::indicator {{
        width: 14px;
        height: 14px;
        margin-left: 4px;
    }}

    /* ================================================================
       TOOLBAR (Transport Area)
       ================================================================ */

    QToolBar {{
        background-color: {c['bg_transport']};
        border: none;
        border-bottom: 1px solid {c['border']};
        padding: 3px 6px;
        spacing: 4px;
    }}

    QToolBar::separator {{
        width: 1px;
        background: {c['border']};
        margin: 4px 6px;
    }}

    QToolBar QWidget {{
        background: transparent;
    }}

    /* ================================================================
       PUSH BUTTONS
       ================================================================ */

    QPushButton {{
        background-color: {c['bg_mid']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 3px;
        padding: 5px 14px;
        min-height: 18px;
    }}

    QPushButton:hover {{
        background-color: {c['bg_hover']};
        border-color: {c['accent_secondary']};
    }}

    QPushButton:pressed {{
        background-color: {c['bg_selected']};
        border-color: {c['accent']};
    }}

    QPushButton:checked {{
        background-color: {c['accent']};
        color: #FFFFFF;
        border-color: {c['accent_light']};
    }}

    QPushButton:disabled {{
        background-color: {c['bg_darkest']};
        color: {c['text_dim']};
        border-color: {c['border']};
    }}

    /* Accent button variant */
    QPushButton[cssClass="accent"] {{
        background-color: {c['accent']};
        color: #FFFFFF;
        border: 1px solid {c['accent_light']};
        font-weight: bold;
    }}

    QPushButton[cssClass="accent"]:hover {{
        background-color: {c['accent_light']};
    }}

    QPushButton[cssClass="accent"]:pressed {{
        background-color: #C73A52;
    }}

    /* Flat button variant */
    QPushButton[cssClass="flat"] {{
        background-color: transparent;
        border: none;
        padding: 4px 8px;
    }}

    QPushButton[cssClass="flat"]:hover {{
        background-color: {c['bg_hover']};
        border-radius: 3px;
    }}

    QPushButton[cssClass="flat"]:pressed {{
        background-color: {c['bg_selected']};
    }}

    /* Toggle button variant */
    QPushButton[cssClass="toggle"] {{
        background-color: {c['bg_dark']};
        border: 1px solid {c['border']};
        border-radius: 3px;
        padding: 4px 10px;
    }}

    QPushButton[cssClass="toggle"]:checked {{
        background-color: {c['accent']};
        color: #FFFFFF;
        border-color: {c['accent']};
    }}

    QPushButton[cssClass="toggle"]:hover {{
        border-color: {c['accent_secondary']};
    }}

    /* ================================================================
       COMBOBOX
       ================================================================ */

    QComboBox {{
        background-color: {c['bg_input']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 3px;
        padding: 4px 8px;
        padding-right: 24px;
        min-height: 18px;
    }}

    QComboBox:hover {{
        border-color: {c['accent_secondary']};
    }}

    QComboBox:focus {{
        border-color: {c['border_focus']};
    }}

    QComboBox:disabled {{
        color: {c['text_dim']};
        background-color: {c['bg_darkest']};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 20px;
        border: none;
        border-left: 1px solid {c['border']};
        border-top-right-radius: 3px;
        border-bottom-right-radius: 3px;
    }}

    QComboBox::down-arrow {{
        image: none;
        width: 0;
        height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {c['text_secondary']};
    }}

    QComboBox QAbstractItemView {{
        background-color: {c['bg_dark']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 3px;
        selection-background-color: {c['bg_selected']};
        selection-color: #FFFFFF;
        padding: 2px;
    }}

    QComboBox QAbstractItemView::item {{
        padding: 4px 8px;
        min-height: 20px;
    }}

    QComboBox QAbstractItemView::item:hover {{
        background-color: {c['bg_hover']};
    }}

    /* ================================================================
       SPINBOX & DOUBLE SPINBOX
       ================================================================ */

    QSpinBox, QDoubleSpinBox {{
        background-color: {c['bg_input']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 3px;
        padding: 3px 6px;
        min-height: 18px;
    }}

    QSpinBox:hover, QDoubleSpinBox:hover {{
        border-color: {c['accent_secondary']};
    }}

    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {c['border_focus']};
    }}

    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 16px;
        border: none;
        border-left: 1px solid {c['border']};
        border-top-right-radius: 3px;
        background-color: {c['bg_mid']};
    }}

    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 16px;
        border: none;
        border-left: 1px solid {c['border']};
        border-bottom-right-radius: 3px;
        background-color: {c['bg_mid']};
    }}

    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {c['bg_hover']};
    }}

    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        width: 0; height: 0;
        border-left: 3px solid transparent;
        border-right: 3px solid transparent;
        border-bottom: 4px solid {c['text_secondary']};
    }}

    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        width: 0; height: 0;
        border-left: 3px solid transparent;
        border-right: 3px solid transparent;
        border-top: 4px solid {c['text_secondary']};
    }}

    /* ================================================================
       SLIDERS
       ================================================================ */

    QSlider {{
        background: transparent;
        min-height: 20px;
    }}

    QSlider::groove:horizontal {{
        background: {c['bg_input']};
        border: 1px solid {c['border']};
        height: 4px;
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        background: {c['accent_secondary']};
        border: 1px solid {c['accent_secondary']};
        width: 14px;
        height: 14px;
        margin: -6px 0;
        border-radius: 7px;
    }}

    QSlider::handle:horizontal:hover {{
        background: {c['accent']};
        border-color: {c['accent']};
    }}

    QSlider::handle:horizontal:pressed {{
        background: {c['accent_light']};
        border-color: {c['accent_light']};
    }}

    QSlider::sub-page:horizontal {{
        background: {c['accent_secondary']};
        border-radius: 2px;
    }}

    QSlider::add-page:horizontal {{
        background: {c['bg_input']};
        border: 1px solid {c['border']};
        border-radius: 2px;
    }}

    QSlider::groove:vertical {{
        background: {c['bg_input']};
        border: 1px solid {c['border']};
        width: 4px;
        border-radius: 2px;
    }}

    QSlider::handle:vertical {{
        background: {c['accent_secondary']};
        border: 1px solid {c['accent_secondary']};
        width: 14px;
        height: 14px;
        margin: 0 -6px;
        border-radius: 7px;
    }}

    QSlider::handle:vertical:hover {{
        background: {c['accent']};
        border-color: {c['accent']};
    }}

    QSlider::handle:vertical:pressed {{
        background: {c['accent_light']};
        border-color: {c['accent_light']};
    }}

    QSlider::sub-page:vertical {{
        background: {c['bg_input']};
        border: 1px solid {c['border']};
        border-radius: 2px;
    }}

    QSlider::add-page:vertical {{
        background: {c['accent_secondary']};
        border-radius: 2px;
    }}

    /* ================================================================
       SCROLLBARS
       ================================================================ */

    QScrollBar:horizontal {{
        background: {c['scrollbar_bg']};
        height: 8px;
        border: none;
        border-radius: 4px;
        margin: 0px;
    }}

    QScrollBar::handle:horizontal {{
        background: {c['scrollbar_handle']};
        min-width: 30px;
        border-radius: 4px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background: {c['accent_secondary']};
    }}

    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0px;
        border: none;
    }}

    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: {c['scrollbar_bg']};
        width: 8px;
        border: none;
        border-radius: 4px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {c['scrollbar_handle']};
        min-height: 30px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {c['accent_secondary']};
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
        border: none;
    }}

    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    /* ================================================================
       TAB WIDGET & TAB BAR
       ================================================================ */

    QTabWidget {{
        border: none;
    }}

    QTabWidget::pane {{
        background-color: {c['bg_darkest']};
        border: 1px solid {c['border']};
        border-top: none;
        border-radius: 0px 0px 4px 4px;
    }}

    QTabBar {{
        background: transparent;
    }}

    QTabBar::tab {{
        background-color: {c['bg_dark']};
        color: {c['text_secondary']};
        border: 1px solid {c['border']};
        border-bottom: none;
        padding: 6px 16px;
        margin-right: 1px;
        border-radius: 4px 4px 0px 0px;
        min-width: 60px;
    }}

    QTabBar::tab:selected {{
        background-color: {c['bg_darkest']};
        color: {c['text_primary']};
        border-bottom: 2px solid {c['accent']};
    }}

    QTabBar::tab:hover:!selected {{
        background-color: {c['bg_hover']};
        color: {c['text_primary']};
    }}

    /* ================================================================
       DOCK WIDGET
       ================================================================ */

    QDockWidget {{
        background-color: {c['bg_darkest']};
        titlebar-close-icon: none;
        titlebar-normal-icon: none;
        color: {c['text_primary']};
        border: 1px solid {c['border']};
    }}

    QDockWidget::title {{
        background-color: {c['bg_header']};
        text-align: left;
        padding: 6px 10px;
        border-bottom: 1px solid {c['border']};
        font-weight: bold;
    }}

    QDockWidget::close-button, QDockWidget::float-button {{
        background: transparent;
        border: none;
        padding: 2px;
    }}

    QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
        background-color: {c['bg_hover']};
        border-radius: 3px;
    }}

    /* ================================================================
       SPLITTER
       ================================================================ */

    QSplitter {{
        background: transparent;
        border: none;
    }}

    QSplitter::handle {{
        background-color: {c['border']};
    }}

    QSplitter::handle:horizontal {{
        width: 2px;
    }}

    QSplitter::handle:vertical {{
        height: 2px;
    }}

    QSplitter::handle:hover {{
        background-color: {c['accent_secondary']};
    }}

    /* ================================================================
       GROUP BOX
       ================================================================ */

    QGroupBox {{
        background-color: {c['bg_dark']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        margin-top: 14px;
        padding-top: 16px;
        font-weight: bold;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0px 6px;
        color: {c['text_secondary']};
        background-color: {c['bg_dark']};
    }}

    /* ================================================================
       LABEL
       ================================================================ */

    QLabel {{
        background: transparent;
        color: {c['text_primary']};
        border: none;
        padding: 1px;
    }}

    QLabel[cssClass="heading"] {{
        font-size: 14px;
        font-weight: bold;
        color: {c['text_primary']};
    }}

    QLabel[cssClass="dim"] {{
        color: {c['text_secondary']};
        font-size: 11px;
    }}

    /* ================================================================
       LINE EDIT
       ================================================================ */

    QLineEdit {{
        background-color: {c['bg_input']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 3px;
        padding: 5px 8px;
        selection-background-color: {c['bg_selected']};
        selection-color: #FFFFFF;
    }}

    QLineEdit:hover {{
        border-color: {c['accent_secondary']};
    }}

    QLineEdit:focus {{
        border-color: {c['border_focus']};
    }}

    QLineEdit:disabled {{
        color: {c['text_dim']};
        background-color: {c['bg_darkest']};
    }}

    QLineEdit[readOnly="true"] {{
        background-color: {c['bg_dark']};
    }}

    /* ================================================================
       TREE VIEW & TREE WIDGET (File Browser)
       ================================================================ */

    QTreeView, QTreeWidget {{
        background-color: {c['bg_dark']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        alternate-background-color: {c['bg_mid']};
        selection-background-color: {c['bg_selected']};
        selection-color: #FFFFFF;
        show-decoration-selected: 1;
        outline: none;
    }}

    QTreeView::item, QTreeWidget::item {{
        padding: 3px 4px;
        border: none;
        min-height: 22px;
    }}

    QTreeView::item:hover, QTreeWidget::item:hover {{
        background-color: {c['bg_hover']};
    }}

    QTreeView::item:selected, QTreeWidget::item:selected {{
        background-color: {c['bg_selected']};
        color: #FFFFFF;
    }}

    QTreeView::branch {{
        background: transparent;
    }}

    QTreeView::branch:hover {{
        background-color: {c['bg_hover']};
    }}

    QTreeView::branch:selected {{
        background-color: {c['bg_selected']};
    }}

    /* ================================================================
       HEADER VIEW
       ================================================================ */

    QHeaderView {{
        background-color: {c['bg_header']};
        border: none;
    }}

    QHeaderView::section {{
        background-color: {c['bg_header']};
        color: {c['text_secondary']};
        border: none;
        border-right: 1px solid {c['border']};
        border-bottom: 1px solid {c['border']};
        padding: 4px 8px;
        font-weight: bold;
        font-size: 11px;
        text-transform: uppercase;
    }}

    QHeaderView::section:hover {{
        background-color: {c['bg_hover']};
        color: {c['text_primary']};
    }}

    QHeaderView::section:pressed {{
        background-color: {c['bg_selected']};
    }}

    /* ================================================================
       STATUS BAR
       ================================================================ */

    QStatusBar {{
        background-color: {c['bg_dark']};
        color: {c['text_secondary']};
        border-top: 1px solid {c['border']};
        font-size: 11px;
        padding: 2px 8px;
    }}

    QStatusBar::item {{
        border: none;
    }}

    QStatusBar QLabel {{
        color: {c['text_secondary']};
        padding: 0px 4px;
    }}

    /* ================================================================
       TOOLTIP
       ================================================================ */

    QToolTip {{
        background-color: {c['bg_dark']};
        color: {c['text_primary']};
        border: 1px solid {c['accent_secondary']};
        border-radius: 3px;
        padding: 4px 8px;
        font-size: 11px;
    }}

    /* ================================================================
       PROGRESS BAR
       ================================================================ */

    QProgressBar {{
        background-color: {c['bg_input']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        text-align: center;
        color: {c['text_primary']};
        font-size: 11px;
        min-height: 16px;
    }}

    QProgressBar::chunk {{
        background-color: {c['accent_secondary']};
        border-radius: 3px;
    }}

    /* ================================================================
       CHECKBOX & RADIO BUTTON
       ================================================================ */

    QCheckBox {{
        background: transparent;
        spacing: 6px;
        color: {c['text_primary']};
    }}

    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {c['border']};
        border-radius: 3px;
        background-color: {c['bg_input']};
    }}

    QCheckBox::indicator:hover {{
        border-color: {c['accent_secondary']};
    }}

    QCheckBox::indicator:checked {{
        background-color: {c['accent']};
        border-color: {c['accent']};
        image: none;
    }}

    QCheckBox::indicator:disabled {{
        background-color: {c['bg_darkest']};
        border-color: {c['text_dim']};
    }}

    QRadioButton {{
        background: transparent;
        spacing: 6px;
        color: {c['text_primary']};
    }}

    QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {c['border']};
        border-radius: 8px;
        background-color: {c['bg_input']};
    }}

    QRadioButton::indicator:hover {{
        border-color: {c['accent_secondary']};
    }}

    QRadioButton::indicator:checked {{
        background-color: {c['accent']};
        border-color: {c['accent']};
    }}

    QRadioButton::indicator:disabled {{
        background-color: {c['bg_darkest']};
        border-color: {c['text_dim']};
    }}

    /* ================================================================
       FRAME (Separators)
       ================================================================ */

    QFrame {{
        background: transparent;
        border: none;
    }}

    QFrame[frameShape="4"] {{
        background: transparent;
        max-height: 1px;
        border: none;
        border-top: 1px solid {c['separator']};
    }}

    QFrame[frameShape="5"] {{
        background: transparent;
        max-width: 1px;
        border: none;
        border-left: 1px solid {c['separator']};
    }}

    /* ================================================================
       LIST WIDGET
       ================================================================ */

    QListWidget, QListView {{
        background-color: {c['bg_dark']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        alternate-background-color: {c['bg_mid']};
        selection-background-color: {c['bg_selected']};
        selection-color: #FFFFFF;
        outline: none;
    }}

    QListWidget::item, QListView::item {{
        padding: 4px 8px;
        border: none;
        min-height: 20px;
    }}

    QListWidget::item:hover, QListView::item:hover {{
        background-color: {c['bg_hover']};
    }}

    QListWidget::item:selected, QListView::item:selected {{
        background-color: {c['bg_selected']};
        color: #FFFFFF;
    }}

    /* ================================================================
       DIALOG & MESSAGE BOX
       ================================================================ */

    QDialog {{
        background-color: {c['bg_darkest']};
        border: 1px solid {c['border']};
    }}

    QMessageBox {{
        background-color: {c['bg_darkest']};
    }}

    QMessageBox QLabel {{
        color: {c['text_primary']};
    }}

    /* ================================================================
       TEXT EDIT / PLAIN TEXT EDIT
       ================================================================ */

    QTextEdit, QPlainTextEdit {{
        background-color: {c['bg_input']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 3px;
        padding: 4px;
        selection-background-color: {c['bg_selected']};
        selection-color: #FFFFFF;
    }}

    QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {c['border_focus']};
    }}
    """


def get_button_style(color: str, text_color: str = "#FFFFFF") -> str:
    """Return an inline QSS string for a custom-colored button.

    Args:
        color: Background color in hex (e.g. '#E94560').
        text_color: Text color in hex, defaults to white.

    Returns:
        QSS string suitable for QPushButton.setStyleSheet().
    """
    # Derive a slightly lighter shade for hover and a darker one for press.
    # Simple approach: we tweak the last hex digit.
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)

    hover_r = min(r + 25, 255)
    hover_g = min(g + 25, 255)
    hover_b = min(b + 25, 255)
    hover_color = f"#{hover_r:02X}{hover_g:02X}{hover_b:02X}"

    press_r = max(r - 30, 0)
    press_g = max(g - 30, 0)
    press_b = max(b - 30, 0)
    press_color = f"#{press_r:02X}{press_g:02X}{press_b:02X}"

    return f"""
    QPushButton {{
        background-color: {color};
        color: {text_color};
        border: 1px solid {color};
        border-radius: 3px;
        padding: 5px 14px;
        min-height: 18px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {hover_color};
        border-color: {hover_color};
    }}
    QPushButton:pressed {{
        background-color: {press_color};
        border-color: {press_color};
    }}
    QPushButton:disabled {{
        background-color: {COLORS['bg_darkest']};
        color: {COLORS['text_dim']};
        border-color: {COLORS['border']};
    }}
    """


def get_track_color_style(color: str) -> str:
    """Return QSS for a colored track header strip.

    Used to apply a distinct color accent to individual track headers
    in the arrangement/mixer view, similar to Ableton's track coloring.

    Args:
        color: Accent color in hex (e.g. '#4A9EFF').

    Returns:
        QSS string suitable for a track header QWidget.setStyleSheet().
    """
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)

    # Semi-transparent background tint
    bg_tint = f"rgba({r}, {g}, {b}, 35)"
    # Slightly brighter for hover
    hover_tint = f"rgba({r}, {g}, {b}, 55)"
    # Solid border accent on the left edge
    border_color = color

    return f"""
    QWidget {{
        background-color: {bg_tint};
        border-left: 3px solid {border_color};
        border-top: none;
        border-right: none;
        border-bottom: 1px solid {COLORS['border']};
        border-radius: 0px;
    }}
    QWidget:hover {{
        background-color: {hover_tint};
    }}
    QLabel {{
        background: transparent;
        border: none;
        color: {COLORS['text_primary']};
        font-weight: bold;
    }}
    QPushButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 3px;
        padding: 2px 6px;
    }}
    QPushButton:hover {{
        background-color: rgba({r}, {g}, {b}, 80);
        border-color: {border_color};
    }}
    QPushButton:checked {{
        background-color: {border_color};
        color: #FFFFFF;
    }}
    """
