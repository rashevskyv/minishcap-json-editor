DARK_THEME_STYLESHEET = """
QWidget {
    background-color: #2E2E2E;
    color: #E0E0E0;
    border: 0px;
}
QMainWindow, QDialog, QStatusBar {
    background-color: #2E2E2E;
}
QMenuBar {
    background-color: #383838;
    color: #E0E0E0;
}
QMenuBar::item:selected {
    background-color: #505050;
}
QMenu {
    background-color: #383838;
    color: #E0E0E0;
    border: 1px solid #505050;
}
QMenu::item:selected {
    background-color: #505050;
}
QPlainTextEdit, QTextEdit, QListWidget {
    background-color: #252525;
    color: #E0E0E0;
    border: 1px solid #505050;
    selection-background-color: #005A9E;
    selection-color: #FFFFFF;
}
QListWidget::item:selected {
    background-color: #005A9E;
    color: #FFFFFF;
}
QLineEdit#PathLineEdit {
    background-color: #252525;
    border: 1px solid #5A5A5A;
    padding: 2px;
    color: #E0E0E0;
}
QPushButton {
    background-color: #4A4A4A;
    color: #E0E0E0;
    border: 1px solid #5A5A5A;
    padding: 5px;
    border-radius: 3px;
}
QPushButton:hover {
    background-color: #5A5A5A;
}
QPushButton:pressed {
    background-color: #3A3A3A;
}
QPushButton#close_search_panel_button {
    font-weight: bold;
    font-size: 14px;
    padding: 0px;
}
QComboBox {
    background-color: #383838;
    color: #E0E0E0;
    border: 1px solid #5A5A5A;
    padding: 3px;
    border-radius: 3px;
}
QComboBox::drop-down {
    border: none;
    background-color: #4A4A4A;
}
QComboBox QAbstractItemView {
    background-color: #383838;
    color: #E0E0E0;
    selection-background-color: #505050;
    border: 1px solid #5A5A5A;
}
QCheckBox, QLabel {
    color: #E0E0E0;
}
QSpinBox {
    background-color: #383838;
    color: #E0E0E0;
    border: 1px solid #5A5A5A;
    padding: 3px;
    border-radius: 3px;
}
QToolBar {
    background-color: #383838;
    border: none;
    spacing: 5px;
}
QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    padding: 4px;
}
QToolButton:hover {
    background-color: #5A5A5A;
    border: 1px solid #5A5A5A;
}
QToolButton:pressed {
    background-color: #3A3A3A;
}
QSplitter::handle {
    background-color: #383838;
}
QSplitter::handle:hover {
    background-color: #505050;
}
QScrollBar:vertical {
    border: 1px solid #5A5A5A;
    background: #2E2E2E;
    width: 12px;
    margin: 12px 0 12px 0;
}
QScrollBar::handle:vertical {
    background: #4A4A4A;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 12px;
    background: #383838;
    subcontrol-origin: margin;
}
QScrollBar:horizontal {
    border: 1px solid #5A5A5A;
    background: #2E2E2E;
    height: 12px;
    margin: 0 12px 0 12px;
}
QScrollBar::handle:horizontal {
    background: #4A4A4A;
    min-width: 20px;
    border-radius: 5px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 12px;
    background: #383838;
    subcontrol-origin: margin;
}
QTabWidget::pane {
    border: 1px solid #505050;
    top: -1px; 
    background-color: #2E2E2E;
}
QTabBar::tab {
    background-color: #383838;
    color: #B0B0B0;
    border: 1px solid #505050;
    border-bottom-color: #505050; 
    padding: 5px 10px;
    margin-right: -1px;
}
QTabBar::tab:selected {
    background-color: #2E2E2E;
    color: #FFFFFF;
    border-bottom-color: #2E2E2E;
}
QTabBar::tab:!selected:hover {
    background-color: #4A4A4A;
}
"""

LIGHT_THEME_STYLESHEET = ""