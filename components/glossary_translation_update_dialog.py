"""Dialog for reviewing translations after a glossary change."""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
)

from core.glossary_manager import GlossaryOccurrence


class GlossaryTranslationUpdateDialog(QDialog):
    """Manual updater for strings affected by a glossary translation change."""

    def __init__(
        self,
        *,
        parent: QWidget,
        term: str,
        old_translation: str,
        new_translation: str,
        occurrences: Sequence[GlossaryOccurrence],
        get_original_text: Callable[[GlossaryOccurrence], str],
        get_current_translation: Callable[[GlossaryOccurrence], str],
        apply_translation: Callable[[GlossaryOccurrence, str], None],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Update \"{term}\" translations")
        self.resize(880, 560)

        self._term = term
        self._old_translation = old_translation or ''
        self._new_translation = new_translation or ''
        self._occurrences: List[GlossaryOccurrence] = list(occurrences)
        self._get_original = get_original_text
        self._get_current_translation = get_current_translation
        self._apply_translation_cb = apply_translation

        self._status: Dict[int, str] = {}

        self._build_ui()
        self._populate_occurrences()
        if self._occurrences:
            self._occurrence_list.setCurrentRow(0)
            self._load_occurrence(0)

    # ------------------------------------------------------------------
    # UI building
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        header = QLabel(
            f"<b>{self._term}</b>: replace "
            f"<i>{self._old_translation or '[empty]'}</i>" 
            f" → <i>{self._new_translation or '[empty]'}</i>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(splitter, 1)

        left_panel = QWidget(splitter)
        left_layout = QVBoxLayout(left_panel)
        left_panel.setLayout(left_layout)
        left_layout.addWidget(QLabel("Occurrences", left_panel))

        self._occurrence_list = QListWidget(left_panel)
        self._occurrence_list.currentRowChanged.connect(self._load_occurrence)
        left_layout.addWidget(self._occurrence_list, 1)

        right_panel = QWidget(splitter)
        right_layout = QVBoxLayout(right_panel)
        right_panel.setLayout(right_layout)

        self._context_label = QLabel(right_panel)
        self._context_label.setWordWrap(True)
        right_layout.addWidget(self._context_label)

        self._original_view = QPlainTextEdit(right_panel)
        self._original_view.setReadOnly(True)
        right_layout.addWidget(QLabel("Original text", right_panel))
        right_layout.addWidget(self._original_view, 1)

        self._translation_edit = QPlainTextEdit(right_panel)
        right_layout.addWidget(QLabel("Translation", right_panel))
        right_layout.addWidget(self._translation_edit, 1)

        button_row = QHBoxLayout()
        right_layout.addLayout(button_row)

        apply_button = QPushButton("Apply", right_panel)
        apply_button.clicked.connect(lambda: self._apply_current(next_item=True))
        button_row.addWidget(apply_button)

        skip_button = QPushButton("Skip", right_panel)
        skip_button.clicked.connect(self._skip_current)
        button_row.addWidget(skip_button)

        button_row.addStretch(1)

        self._ai_notice = QLabel("AI suggestions coming soon", right_panel)
        self._ai_notice.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._ai_notice.setStyleSheet("color: grey; font-style: italic;")
        button_row.addWidget(self._ai_notice)

        footer = QDialogButtonBox(QDialogButtonBox.Close, right_panel)
        footer.rejected.connect(self.close)
        right_layout.addWidget(footer)

        self._status_label = QLabel(right_panel)
        self._status_label.setWordWrap(True)
        right_layout.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Occurrence helpers
    # ------------------------------------------------------------------
    def _populate_occurrences(self) -> None:
        self._occurrence_list.clear()
        for idx, occ in enumerate(self._occurrences, start=1):
            item = QListWidgetItem(self._format_occurrence_label(idx, occ))
            self._occurrence_list.addItem(item)

    def _format_occurrence_label(self, number: int, occ: GlossaryOccurrence) -> str:
        status = self._status.get(id(occ))
        suffix = ""
        if status == 'applied':
            suffix = " ✓"
        elif status == 'skipped':
            suffix = " –"
        return f"#{number} | Block {occ.block_idx} | Row {occ.string_idx}{suffix}"

    def _refresh_occurrence_item(self, occ: GlossaryOccurrence) -> None:
        occ_id = id(occ)
        for row in range(self._occurrence_list.count()):
            data_occ = self._occurrences[row]
            if id(data_occ) == occ_id:
                self._occurrence_list.item(row).setText(
                    self._format_occurrence_label(row + 1, data_occ)
                )
                break

    def _load_occurrence(self, row: int) -> None:
        if not (0 <= row < len(self._occurrences)):
            self._original_view.clear()
            self._translation_edit.clear()
            self._context_label.clear()
            return

        occ = self._occurrences[row]
        original_text = self._get_original(occ) or ""
        current_translation = self._get_current_translation(occ) or ""
        suggested = self._suggest_translation(current_translation)

        self._context_label.setText(
            f"Block {occ.block_idx} • String {occ.string_idx} • Line {occ.line_idx + 1}"
        )
        self._original_view.setPlainText(original_text)
        self._translation_edit.setPlainText(suggested)
        self._status_label.clear()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _current_occurrence(self) -> Optional[GlossaryOccurrence]:
        row = self._occurrence_list.currentRow()
        if 0 <= row < len(self._occurrences):
            return self._occurrences[row]
        return None

    def _suggest_translation(self, current_text: str) -> str:
        if not current_text:
            return current_text
        if self._old_translation and self._old_translation in current_text:
            return current_text.replace(self._old_translation, self._new_translation)
        return current_text

    def _apply_current(self, next_item: bool = False) -> None:
        occ = self._current_occurrence()
        if not occ:
            return
        candidate = self._translation_edit.toPlainText().rstrip('\n')
        if not candidate:
            QMessageBox.warning(self, "Update", "Translation cannot be empty.")
            return
        self._apply_translation_cb(occ, candidate)
        self._status[id(occ)] = 'applied'
        self._refresh_occurrence_item(occ)
        self._status_label.setText("Applied.")
        if next_item:
            self._select_next()

    def _skip_current(self) -> None:
        occ = self._current_occurrence()
        if not occ:
            return
        self._status[id(occ)] = 'skipped'
        self._refresh_occurrence_item(occ)
        self._status_label.setText("Skipped.")
        self._select_next()

    def _select_next(self) -> None:
        row = self._occurrence_list.currentRow()
        if row + 1 < self._occurrence_list.count():
            self._occurrence_list.setCurrentRow(row + 1)

