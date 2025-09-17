# -*- coding: utf-8 -*-
"""Dialog for viewing glossary entries and navigating to occurrences."""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.glossary_manager import GlossaryEntry, GlossaryOccurrence


class GlossaryDialog(QDialog):
    """Show glossary entries with occurrences and allow navigation."""

    def __init__(
        self,
        *,
        parent: Optional[QWidget],
        entries: Sequence[GlossaryEntry],
        occurrence_map: Dict[str, List[GlossaryOccurrence]],
        jump_callback: Callable[[GlossaryOccurrence], None],
        update_callback: Optional[
            Callable[[str, str, str], Optional[Tuple[Sequence[GlossaryEntry], Dict[str, List[GlossaryOccurrence]]]]]
        ] = None,
        initial_term: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Глосарій")
        self.resize(840, 520)

        self._all_entries = list(entries)
        self._filtered_entries: List[GlossaryEntry] = list(entries)
        self._occurrences = occurrence_map
        self._jump_callback = jump_callback
        self._update_callback = update_callback
        self._initial_term = initial_term
        self._pending_select_term: Optional[str] = None
        self._is_populating = False

        layout = QVBoxLayout(self)

        header = QLabel("Оберіть термін, щоб переглянути входження. Подвійний клік переходить до тексту.")
        header.setWordWrap(True)
        layout.addWidget(header)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Пошук:", self))
        self._search_field = QLineEdit(self)
        self._search_field.setPlaceholderText("Введіть термін або переклад...")
        self._search_field.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self._search_field, 1)
        layout.addLayout(search_layout)

        splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(splitter, 1)

        self._entry_table = QTableWidget(self)
        self._entry_table.setColumnCount(4)
        self._entry_table.setHorizontalHeaderLabels(["Термін", "Переклад", "Примітки", "К-сть"])
        self._entry_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._entry_table.setSelectionMode(QTableWidget.SingleSelection)
        self._entry_table.cellClicked.connect(self._on_entry_selected)
        self._entry_table.cellDoubleClicked.connect(self._on_entry_activated)
        self._entry_table.setSortingEnabled(True)
        if self._update_callback:
            self._entry_table.setEditTriggers(
                QTableWidget.DoubleClicked
                | QTableWidget.EditKeyPressed
                | QTableWidget.AnyKeyPressed
            )
            self._entry_table.itemChanged.connect(self._on_entry_edited)
        else:
            self._entry_table.setEditTriggers(QTableWidget.NoEditTriggers)
        splitter.addWidget(self._entry_table)

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)

        self._details_label = QLabel("", self)
        self._details_label.setWordWrap(True)
        right_layout.addWidget(self._details_label)

        self._occurrence_label = QLabel("Входження: 0", self)
        right_layout.addWidget(self._occurrence_label)

        self._occurrence_list = QListWidget(self)
        self._occurrence_list.itemDoubleClicked.connect(self._activate_selected_occurrence)
        right_layout.addWidget(self._occurrence_list, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        self._jump_button = QPushButton("Перейти", self)
        self._jump_button.clicked.connect(self._activate_selected_occurrence)
        button_box.addButton(self._jump_button, QDialogButtonBox.ActionRole)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._populate_entries(self._filtered_entries)
        if initial_term:
            self._select_initial_term(initial_term)
        else:
            if self._filtered_entries:
                self._entry_table.selectRow(0)
                self._update_entry_details(self._filtered_entries[0])
                self._update_occurrences(self._filtered_entries[0])

    # ------------------------------------------------------------------
    # UI population
    # ------------------------------------------------------------------
    def _populate_entries(self, entries: Sequence[GlossaryEntry]) -> None:
        self._entry_table.setSortingEnabled(False)
        self._is_populating = True
        self._entry_table.blockSignals(True)
        self._entry_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            occurrences = self._occurrences.get(entry.original, [])
            values = [
                entry.original,
                entry.translation,
                entry.notes,
                str(len(occurrences)),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col == 0:
                    item.setData(Qt.UserRole, entry)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col == 3:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._entry_table.setItem(row, col, item)
        self._entry_table.resizeColumnsToContents()
        self._entry_table.setSortingEnabled(True)
        self._entry_table.blockSignals(False)
        self._is_populating = False

    def _select_initial_term(self, term: str) -> None:
        term_lower = term.lower()
        for row, entry in enumerate(self._filtered_entries):
            if entry.original.lower() == term_lower:
                self._entry_table.selectRow(row)
                self._entry_table.scrollToItem(self._entry_table.item(row, 0))
                self._update_entry_details(entry)
                self._update_occurrences(entry)
                break

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_entry_selected(self, row: int, _column: int) -> None:
        entry = self._entry_for_row(row)
        if entry:
            self._update_entry_details(entry)
            self._update_occurrences(entry)

    def _on_entry_activated(self, row: int, _column: int) -> None:
        entry = self._entry_for_row(row)
        if not entry:
            return
        occ_list = self._occurrences.get(entry.original, [])
        if occ_list:
            self._jump_callback(occ_list[0])
            self.accept()

    def _on_entry_edited(self, item: QTableWidgetItem) -> None:
        if self._is_populating or not self._update_callback:
            return
        row = item.row()
        column = item.column()
        if column not in (1, 2):
            return

        entry = self._entry_for_row(row)
        if not entry:
            return

        translation_item = self._entry_table.item(row, 1)
        notes_item = self._entry_table.item(row, 2)
        new_translation = translation_item.text().strip() if translation_item else ''
        new_notes = notes_item.text().strip() if notes_item else ''

        if new_translation == entry.translation and new_notes == entry.notes:
            return

        result = self._update_callback(entry.original, new_translation, new_notes)
        if not result:
            self._is_populating = True
            self._entry_table.blockSignals(True)
            if translation_item:
                translation_item.setText(entry.translation)
            if notes_item:
                notes_item.setText(entry.notes)
            self._entry_table.blockSignals(False)
            self._is_populating = False
            return

        new_entries, new_occurrence_map = result
        self._all_entries = list(new_entries)
        self._occurrences = new_occurrence_map
        self._pending_select_term = entry.original
        self._apply_filter(self._search_field.text())

    def _activate_selected_occurrence(self) -> None:
        current_item = self._occurrence_list.currentItem()
        if not current_item:
            if self._occurrence_list.count() == 1:
                self._occurrence_list.setCurrentRow(0)
                current_item = self._occurrence_list.currentItem()
            else:
                return
        occurrence = current_item.data(Qt.UserRole)
        if occurrence:
            self._jump_callback(occurrence)
            self.accept()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _update_occurrences(self, entry: GlossaryEntry) -> None:
        self._update_entry_details(entry)
        occ_list = self._occurrences.get(entry.original, [])
        self._occurrence_list.clear()
        for index, occ in enumerate(occ_list, start=1):
            preview = occ.line_text.strip()
            if len(preview) > 120:
                preview = preview[:117] + "…"
            item = QListWidgetItem(
                f"#{index}: блок {occ.block_idx}, рядок {occ.string_idx}, лінія {occ.line_idx + 1}\n{preview}"
            )
            item.setData(Qt.UserRole, occ)
            self._occurrence_list.addItem(item)
        self._occurrence_label.setText(f"Входження: {len(occ_list)}")
        self._jump_button.setEnabled(bool(occ_list))

    def _entry_for_row(self, row: int) -> Optional[GlossaryEntry]:
        if row < 0:
            return None
        item = self._entry_table.item(row, 0)
        if not item:
            return None
        entry = item.data(Qt.UserRole)
        if isinstance(entry, GlossaryEntry):
            return entry
        if 0 <= row < len(self._filtered_entries):
            return self._filtered_entries[row]
        return None

    def _update_entry_details(self, entry: GlossaryEntry) -> None:
        lines = [f"Термін: {entry.original}", f"Переклад: {entry.translation}"]
        if entry.notes:
            lines.append(f"Примітки: {entry.notes}")
        self._details_label.setText("\n".join(lines))

    def _apply_filter(self, text: str) -> None:
        pattern = text.strip().lower()
        if not pattern:
            self._filtered_entries = list(self._all_entries)
        else:
            def matches(entry: GlossaryEntry) -> bool:
                haystack = " ".join(
                    filter(None, [entry.original, entry.translation, entry.notes])
                ).lower()
                return pattern in haystack

            self._filtered_entries = [entry for entry in self._all_entries if matches(entry)]

        self._populate_entries(self._filtered_entries)
        if self._pending_select_term:
            self._select_initial_term(self._pending_select_term)
            self._pending_select_term = None
            return

        if self._filtered_entries:
            self._entry_table.selectRow(0)
            self._update_entry_details(self._filtered_entries[0])
            self._update_occurrences(self._filtered_entries[0])
        else:
            self._details_label.setText("Нічого не знайдено")
            self._occurrence_list.clear()
            self._occurrence_label.setText("Входження: 0")
            self._jump_button.setEnabled(False)
