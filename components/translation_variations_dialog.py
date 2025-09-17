# -*- coding: utf-8 -*-
"""Dialog for choosing among AI translation variations."""
from __future__ import annotations

from typing import Iterable, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)


class TranslationVariationsDialog(QDialog):
    """Show multiple translation options and allow the user to pick one."""

    def __init__(self, parent=None, variations: Optional[Iterable[str]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI-варіації перекладу")
        self.resize(720, 520)
        self.selected_translation: Optional[str] = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Оберіть варіант перекладу та двічі клацніть або натисніть \"Застосувати\"."))

        lists_layout = QHBoxLayout()
        self._list = QListWidget(self)
        self._list.setSelectionMode(QListWidget.SingleSelection)
        self._list.itemSelectionChanged.connect(self._update_preview)
        self._list.itemDoubleClicked.connect(self._apply_current_selection)
        lists_layout.addWidget(self._list, 1)

        self._preview = QTextEdit(self)
        self._preview.setReadOnly(True)
        lists_layout.addWidget(self._preview, 2)

        layout.addLayout(lists_layout)

        self._buttons = QDialogButtonBox(self)
        self._apply_button = QPushButton("Застосувати", self)
        self._apply_button.clicked.connect(self._apply_current_selection)
        self._buttons.addButton(self._apply_button, QDialogButtonBox.AcceptRole)
        self._buttons.addButton("Скасувати", QDialogButtonBox.RejectRole)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        if variations:
            self._populate_variations(list(variations))

    def _populate_variations(self, variations: List[str]) -> None:
        self._list.clear()
        for index, option in enumerate(variations, start=1):
            display = option.replace("\n", " ⏎ ")
            if len(display) > 120:
                display = f"{display[:117]}…"
            item = QListWidgetItem(f"#{index}: {display}")
            item.setData(Qt.UserRole, option)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _update_preview(self) -> None:
        current = self._list.currentItem()
        text = current.data(Qt.UserRole) if current else ""
        self._preview.setPlainText(text or "")

    def _apply_current_selection(self) -> None:
        current = self._list.currentItem()
        if not current:
            return
        selected = current.data(Qt.UserRole)
        if not isinstance(selected, str):
            return
        self.selected_translation = selected
        self.accept()
