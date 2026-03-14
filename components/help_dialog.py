# --- START OF FILE components/help_dialog.py ---
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class HelpShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts Reference")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout(self)
        
        title_label = QLabel("Keyboard Shortcuts")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Action", "Shortcut"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setAlternatingRowColors(True)
        
        self.shortcuts = [
            ("Save Project/File", "Ctrl + S"),
            ("Undo", "Ctrl + Z"),
            ("Redo", "Ctrl + Y / Ctrl + Shift + Z"),
            ("Find Text", "Ctrl + F"),
            ("Find Next", "F3"),
            ("Find Previous", "Shift + F3"),
            ("Paste Block Text", "Ctrl + Shift + V"),
            ("Auto-fix Current String", "Ctrl + Shift + A"),
            ("AI Chat Window", "Ctrl + Shift + C"),
            ("Navigate to Next Problem", "Ctrl + Down"),
            ("Navigate to Previous Problem", "Ctrl + Up"),
            ("Select Next String", "Alt + Down / Down (in Preview)"),
            ("Select Previous String", "Alt + Up / Up (in Preview)"),
            ("Next Block", "Ctrl + Shift + Down"),
            ("Previous Block", "Ctrl + Shift + Up"),
            ("Next Folder/Category", "Ctrl + Shift + Right"),
            ("Previous Folder/Category", "Ctrl + Shift + Left"),
        ]
        
        self.table.setRowCount(len(self.shortcuts))
        for i, (action, shortcut) in enumerate(self.shortcuts):
            self.table.setItem(i, 0, QTableWidgetItem(action))
            self.table.setItem(i, 1, QTableWidgetItem(shortcut))
            self.table.item(i, 1).setTextAlignment(Qt.AlignCenter)
            
        layout.addWidget(self.table)
        
        footer_layout = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        footer_layout.addStretch()
        footer_layout.addWidget(close_button)
        layout.addLayout(footer_layout)

def show_shortcuts_dialog(parent):
    dialog = HelpShortcutsDialog(parent)
    dialog.exec_()
