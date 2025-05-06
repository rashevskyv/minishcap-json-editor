from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt
from utils import log_debug # Changed from .utils

class CustomListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        log_debug(f"CustomListWidget initialized with parent: {parent}")

    def create_item(self, text, data, role=Qt.UserRole):
        item = QListWidgetItem(text)
        item.setData(role, data)
        return item