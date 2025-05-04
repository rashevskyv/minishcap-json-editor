from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt

class CustomListWidget(QListWidget):
    """
    Кастомний віджет списку, що додає зручний метод для створення елементів з даними.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

    def create_item(self, text, data, role=Qt.UserRole):
        """
        Створює QListWidgetItem з заданим текстом та даними.

        Args:
            text (str): Текст, що відображатиметься для елемента.
            data: Дані, які потрібно пов'язати з елементом.
            role (int): Роль Qt для зберігання даних (за замовчуванням Qt.UserRole).

        Returns:
            QListWidgetItem: Створений елемент списку.
        """
        item = QListWidgetItem(text)
        item.setData(role, data)
        return item