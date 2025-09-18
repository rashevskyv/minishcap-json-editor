# -*- coding: utf-8 -*-
"""Dialog for viewing glossary entries and navigating to occurrences."""
from __future__ import annotations
import json
from html import escape
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QPlainTextEdit,
    QStyledItemDelegate,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtGui import QPalette, QTextDocument, QAbstractTextDocumentLayout
from core.glossary_manager import GlossaryEntry, GlossaryOccurrence
class _RichTextItemDelegate(QStyledItemDelegate):
    """Render rich-text list items (e.g., occurrences list)."""

    def paint(self, painter, option, index):  # type: ignore[override]
        text = index.data(Qt.DisplayRole)
        if not text:
            super().paint(painter, option, index)
            return

        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setHtml(str(text))
        doc.setTextWidth(option.rect.width())

        painter.save()
        paint_context = QAbstractTextDocumentLayout.PaintContext()

        color_group = QPalette.Active if option.state & QStyle.State_Active else QPalette.Inactive
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            paint_context.palette.setColor(
                QPalette.Text,
                option.palette.color(color_group, QPalette.HighlightedText),
            )
        else:
            paint_context.palette.setColor(
                QPalette.Text,
                option.palette.color(color_group, QPalette.Text),
            )

        painter.translate(option.rect.topLeft())
        painter.setClipRect(option.rect.translated(-option.rect.topLeft()))
        doc.documentLayout().draw(painter, paint_context)
        painter.restore()

    def sizeHint(self, option, index):  # type: ignore[override]
        text = index.data(Qt.DisplayRole)
        if not text:
            return super().sizeHint(option, index)

        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setHtml(str(text))
        width = option.rect.width()
        if width <= 0 and option.widget is not None:
            viewport = getattr(option.widget, 'viewport', None)
            if callable(viewport):
                width = viewport().width()
        if width > 0:
            doc.setTextWidth(width)
        size = doc.documentLayout().documentSize()
        return QSize(int(size.width()), int(size.height()))


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
        delete_callback: Optional[
            Callable[[str], Optional[Tuple[Sequence[GlossaryEntry], Dict[str, List[GlossaryOccurrence]]]]]
        ] = None,
        initial_term: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Glossary")
        self.resize(840, 520)

        parent_settings = getattr(parent, 'settings_manager', None)
        settings_path = getattr(parent_settings, 'settings_file_path', 'settings.json')
        self._settings_path = Path(settings_path)
        self._restore_maximized_on_show = False
        self._current_entry: Optional[GlossaryEntry] = None
        self._suppress_editor_signals = False
        self._editor_dirty = False

        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)

        self._all_entries = list(entries)
        self._filtered_entries: List[GlossaryEntry] = list(entries)
        self._occurrences = occurrence_map
        self._jump_callback = jump_callback
        self._update_callback = update_callback
        self._delete_callback = delete_callback
        self._initial_term = initial_term
        self._pending_select_term: Optional[str] = None
        self._is_populating = False

        layout = QVBoxLayout(self)

        header = QLabel("Select a term to review occurrences. Double-click an occurrence to jump to the editor.", self)
        header.setWordWrap(True)
        layout.addWidget(header)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:", self))
        self._search_field = QLineEdit(self)
        self._search_field.setPlaceholderText("Type a term or translation...")
        self._search_field.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self._search_field, 1)
        layout.addLayout(search_layout)

        splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(splitter, 1)

        self._entry_table = QTableWidget(self)
        self._entry_table.setColumnCount(4)
        self._entry_table.setHorizontalHeaderLabels(["Term", "Translation", "Notes", "Count"])
        self._entry_table.setSelectionMode(QTableWidget.SingleSelection)
        self._entry_table.cellClicked.connect(self._on_entry_selected)
        self._entry_table.currentCellChanged.connect(self._on_entry_current_changed)
        self._entry_table.setSortingEnabled(True)
        self._entry_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._entry_table.customContextMenuRequested.connect(self._on_entry_context_menu)
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
        self._original_label = QLabel("", self)
        self._original_label.setWordWrap(True)
        right_layout.addWidget(self._original_label)
        translation_label = QLabel("Translation:", self)
        right_layout.addWidget(translation_label)
        self._translation_edit = QLineEdit(self)
        right_layout.addWidget(self._translation_edit)
        notes_label = QLabel("Notes:", self)
        right_layout.addWidget(notes_label)
        self._notes_edit = QPlainTextEdit(self)
        right_layout.addWidget(self._notes_edit, 1)
        self._occurrence_label = QLabel("Occurrences: 0", self)
        right_layout.addWidget(self._occurrence_label)
        self._occurrence_list = QListWidget(self)
        self._occurrence_list.setSpacing(6)
        self._occurrence_list.setWordWrap(True)
        self._occurrence_list.setTextElideMode(Qt.ElideNone)
        self._occurrence_list.setItemDelegate(_RichTextItemDelegate(self._occurrence_list))
        self._occurrence_list.itemDoubleClicked.connect(self._activate_selected_occurrence)
        right_layout.addWidget(self._occurrence_list, 1)
        button_box = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        self._save_button = QPushButton("Save Changes", self)
        self._save_button.clicked.connect(self._save_editor_changes)
        button_box.addButton(self._save_button, QDialogButtonBox.ActionRole)
        if self._update_callback is None:
            self._save_button.setVisible(False)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self._translation_edit.textChanged.connect(self._on_editor_content_changed)
        self._notes_edit.textChanged.connect(self._on_editor_content_changed)
        self._update_editor_enabled_state()
        self._load_dialog_state()
        self._populate_entries(self._filtered_entries)
        if initial_term:
            self._select_initial_term(initial_term)
        else:
            if self._filtered_entries:
                self._entry_table.selectRow(0)
                self._show_entry_for_row(0)
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
                self._show_entry_for_row(row)
                break
    def _show_entry_for_row(self, row: int) -> None:
        if row < 0:
            self._clear_entry_details()
            return
        entry = self._entry_for_row(row)
        if entry:
            self._populate_entry_details(entry)
            self._update_occurrences(entry)
        else:
            self._clear_entry_details()
    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_entry_current_changed(self, row: int, _column: int, _prev_row: int, _prev_column: int) -> None:
        if self._is_populating:
            return
        self._show_entry_for_row(row)
    def _on_entry_selected(self, row: int, _column: int) -> None:
        self._show_entry_for_row(row)
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
            if self._current_entry and self._current_entry.original == entry.original:
                self._mark_editor_dirty(False)
            return
        if self._attempt_entry_update(entry, new_translation, new_notes):
            if self._current_entry and self._current_entry.original == entry.original:
                self._mark_editor_dirty(False)
            return
        self._is_populating = True
        self._entry_table.blockSignals(True)
        if translation_item:
            translation_item.setText(entry.translation)
        if notes_item:
            notes_item.setText(entry.notes)
        self._entry_table.blockSignals(False)
        self._is_populating = False
        if self._current_entry and self._current_entry.original == entry.original:
            self._populate_entry_details(entry)
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
    def _on_editor_content_changed(self) -> None:
        if self._suppress_editor_signals or not self._update_callback or not self._current_entry:
            return
        current_translation = self._translation_edit.text().strip()
        current_notes = self._notes_edit.toPlainText().strip()
        has_changes = (
            current_translation != self._current_entry.translation
            or current_notes != self._current_entry.notes
        )
        self._mark_editor_dirty(has_changes)
    def _mark_editor_dirty(self, dirty: bool) -> None:
        self._editor_dirty = bool(dirty) if self._update_callback else False
        self._update_editor_enabled_state()
    def _update_editor_enabled_state(self) -> None:
        can_edit = self._update_callback is not None and self._current_entry is not None
        self._translation_edit.setReadOnly(not can_edit)
        self._notes_edit.setReadOnly(not can_edit)
        if hasattr(self, '_save_button'):
            if self._update_callback is None:
                self._save_button.setVisible(False)
                self._save_button.setEnabled(False)
            else:
                self._save_button.setVisible(True)
                self._save_button.setEnabled(can_edit and self._editor_dirty)
    def _save_editor_changes(self) -> None:
        if self._is_populating or not self._update_callback or not self._current_entry:
            return
        new_translation = self._translation_edit.text().strip()
        new_notes = self._notes_edit.toPlainText().strip()
        entry = self._current_entry
        if new_translation == entry.translation and new_notes == entry.notes:
            self._mark_editor_dirty(False)
            return
        if not self._attempt_entry_update(entry, new_translation, new_notes):
            self._populate_entry_details(entry)
            return
        self._mark_editor_dirty(False)
    def _attempt_entry_update(self, entry: GlossaryEntry, new_translation: str, new_notes: str) -> bool:
        if not self._update_callback:
            return False
        result = self._update_callback(entry.original, new_translation, new_notes)
        if not result:
            return False
        new_entries, new_occurrence_map = result
        self._all_entries = list(new_entries)
        self._occurrences = new_occurrence_map
        self._pending_select_term = entry.original
        self._apply_filter(self._search_field.text())
        return True
    def _attempt_entry_delete(self, entry: GlossaryEntry) -> None:
        if not self._delete_callback:
            return
        response = QMessageBox.question(
            self,
            "Delete Glossary Entry",
            f"Remove term \"{entry.original}\" from the glossary?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response != QMessageBox.Yes:
            return
        result = self._delete_callback(entry.original)
        if not result:
            return
        new_entries, new_occurrence_map = result
        self._all_entries = list(new_entries)
        self._occurrences = new_occurrence_map
        self._current_entry = None
        self._mark_editor_dirty(False)
        self._update_editor_enabled_state()
        self._pending_select_term = None
        self._apply_filter(self._search_field.text())
    def _on_entry_context_menu(self, pos) -> None:
        row = self._entry_table.rowAt(pos.y())
        if row < 0:
            return
        entry = self._entry_for_row(row)
        if not entry:
            return
        menu = QMenu(self)
        delete_action = menu.addAction("Delete Entry")
        delete_action.setEnabled(self._delete_callback is not None)
        selected_action = menu.exec_(self._entry_table.viewport().mapToGlobal(pos))
        if selected_action == delete_action:
            self._entry_table.selectRow(row)
            self._attempt_entry_delete(entry)
    def _load_dialog_state(self) -> None:
        data = self._read_settings_file()
        state = data.get('glossary_dialog_state')
        if not isinstance(state, dict):
            return
        geometry_data = state.get('geometry')
        if isinstance(geometry_data, dict):
            rect = QRect(
                geometry_data.get('x', self.x()),
                geometry_data.get('y', self.y()),
                geometry_data.get('width', self.width()),
                geometry_data.get('height', self.height()),
            )
            self.setGeometry(rect)
        self._restore_maximized_on_show = bool(state.get('is_maximized', False))
    def _save_dialog_state(self) -> None:
        data = self._read_settings_file()
        state = data.get('glossary_dialog_state', {})
        geometry_source = self.normalGeometry() if self.isMaximized() else self.geometry()
        state['geometry'] = self._geometry_to_dict(geometry_source)
        state['is_maximized'] = bool(self.isMaximized())
        data['glossary_dialog_state'] = state
        self._write_settings_file(data)
    def _read_settings_file(self) -> Dict[str, Any]:
        try:
            if not self._settings_path.exists():
                return {}
            with self._settings_path.open('r', encoding='utf-8') as handle:
                return json.load(handle)
        except Exception:
            return {}
    def _write_settings_file(self, data: Dict[str, Any]) -> None:
        try:
            if self._settings_path.parent and not self._settings_path.parent.exists():
                self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            with self._settings_path.open('w', encoding='utf-8') as handle:
                json.dump(data, handle, indent=4, ensure_ascii=False)
        except Exception:
            pass
    @staticmethod
    def _geometry_to_dict(rect: QRect) -> Dict[str, int]:
        return {
            'x': rect.x(),
            'y': rect.y(),
            'width': rect.width(),
            'height': rect.height(),
        }
    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._restore_maximized_on_show:
            self._restore_maximized_on_show = False
            self.showMaximized()
    def closeEvent(self, event) -> None:
        self._save_dialog_state()
        super().closeEvent(event)
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _update_occurrences(self, entry: GlossaryEntry) -> None:
        occ_list = self._occurrences.get(entry.original, [])
        self._occurrence_list.clear()
        for index, occ in enumerate(occ_list, start=1):
            preview = occ.line_text.strip()
            if len(preview) > 120:
                preview = preview[:117] + "..."
            preview_html = escape(preview).replace('\n', '<br>')
            header_html = (
                f"<b>#{index}</b> | block <b>{occ.block_idx}</b> | "
                f"string <b>{occ.string_idx}</b> | line <b>{occ.line_idx + 1}</b>"
            )
            item = QListWidgetItem()
            item.setData(Qt.DisplayRole, f"{header_html}<br>{preview_html}")
            item.setData(Qt.UserRole, occ)
            self._occurrence_list.addItem(item)
        self._occurrence_label.setText(f"Occurrences: {len(occ_list)}")
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
    def _populate_entry_details(self, entry: GlossaryEntry) -> None:
        self._current_entry = entry
        self._suppress_editor_signals = True
        self._original_label.setText(f"Term: {entry.original}")
        self._translation_edit.setText(entry.translation or '')
        self._notes_edit.setPlainText(entry.notes or '')
        self._suppress_editor_signals = False
        self._mark_editor_dirty(False)
        self._update_editor_enabled_state()
    def _clear_entry_details(self) -> None:
        self._current_entry = None
        self._suppress_editor_signals = True
        self._original_label.setText('Nothing selected')
        self._translation_edit.clear()
        self._notes_edit.clear()
        self._suppress_editor_signals = False
        self._mark_editor_dirty(False)
        self._update_editor_enabled_state()
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
            self._show_entry_for_row(0)
        else:
            self._clear_entry_details()
            self._occurrence_list.clear()
            self._occurrence_label.setText("Occurrences: 0")
