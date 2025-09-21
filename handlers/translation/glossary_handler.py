# --- START OF FILE handlers/translation/glossary_handler.py ---

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PyQt5.QtWidgets import (QAction, QMessageBox, QDialog, QVBoxLayout, QLabel, 
                             QLineEdit, QPlainTextEdit, QHBoxLayout, QPushButton, 
                             QDialogButtonBox, QListWidget, QListWidgetItem, QWidget)
from PyQt5.QtCore import Qt, QObject, QEvent

from .base_translation_handler import BaseTranslationHandler
from core.glossary_manager import GlossaryEntry, GlossaryManager, GlossaryOccurrence
from components.glossary_dialog import GlossaryDialog
from utils.logging_utils import log_debug

_DEFAULT_GLOSSARY_PROMPT = (
    "You are the creative Ukrainian localization lead for {game_name}. "
    "When given a source term (and optional context line), craft a vivid Ukrainian translation that matches the game's universe, tone, and established terminology. "
    "Describe the in-game meaning in one short note – explain what the term represents or how it is used, without grammar labels, part-of-speech hints, or plural/singular remarks. "
    "Respond strictly in JSON with keys \"translation\" and \"notes\"; keep both values in Ukrainian."
)

class _ReturnToAcceptFilter(QObject):
    """Convert Return/Enter key presses into dialog acceptance."""

    def __init__(self, dialog: QDialog) -> None:
        super().__init__(dialog)
        self._dialog = dialog

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            modifiers = event.modifiers()
            if not (modifiers & (Qt.ShiftModifier | Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
                self._dialog.accept()
                return True
        return super().eventFilter(obj, event)

class _EditEntryDialog(QDialog):
    """Simple dialog for editing a glossary entry."""
    def __init__(
        self,
        parent: QWidget,
        term: str,
        entry: Optional[GlossaryEntry] = None,
        context: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Glossary Entry")

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel(f"<b>Term:</b> {term}"))
        if context:
            form_layout.addWidget(QLabel(f"<b>Context:</b> <i>{context}</i>"))

        form_layout.addWidget(QLabel("Translation:"))
        self._translation_edit = QLineEdit(self)
        self._translation_edit.installEventFilter(_ReturnToAcceptFilter(self))
        form_layout.addWidget(self._translation_edit)

        form_layout.addWidget(QLabel("Notes:"))
        self._notes_edit = QPlainTextEdit(self)
        self._notes_edit.setMinimumHeight(80)
        form_layout.addWidget(self._notes_edit)

        if entry:
            self._translation_edit.setText(entry.translation)
            self._notes_edit.setPlainText(entry.notes)

        layout.addLayout(form_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> Tuple[str, str]:
        return (
            self._translation_edit.text().strip(),
            self._notes_edit.toPlainText().strip(),
        )

class GlossaryHandler(BaseTranslationHandler):
    def __init__(self, main_handler):
        super().__init__(main_handler)
        self.glossary_manager = GlossaryManager()
        self._open_glossary_action: Optional[QAction] = None
        self._current_glossary_path: Optional[Path] = None
        self._current_plugin_name: Optional[str] = None
        self._cached_glossary_prompt_template: Optional[str] = None
        self._cached_glossary_prompt_plugin: Optional[str] = None

    def install_menu_actions(self) -> None:
        tools_menu = getattr(self.mw, 'tools_menu', None)
        if not tools_menu:
            return

        if self._open_glossary_action is None:
            glossary_action = QAction('Open Glossary...', self.mw)
            glossary_action.setToolTip('Open glossary and jump to occurrences')
            glossary_action.triggered.connect(self.show_glossary_dialog)
            tools_menu.addAction(glossary_action)
            self._open_glossary_action = glossary_action
        
        reset_action = getattr(self.main_handler, '_reset_session_action', None)
        if reset_action is None:
            reset_action = QAction('AI Reset Translation Session', self.mw)
            reset_action.setToolTip('Reset the current AI translation session')
            reset_action.triggered.connect(self.main_handler.reset_translation_session)
            tools_menu.addAction(reset_action)
            self.main_handler._reset_session_action = reset_action

    def initialize_glossary_highlighting(self) -> None:
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        candidate_paths = []
        if plugin_name:
            candidate_paths.append(Path('plugins') / plugin_name / 'translation_prompts' / 'glossary.md')
        candidate_paths.append(Path('translation_prompts') / 'glossary.md')
        glossary_path = next((p for p in candidate_paths if p and p.exists()), None)
        glossary_text = ''
        if glossary_path is not None:
            try:
                glossary_text = glossary_path.read_text(encoding='utf-8')
            except Exception as exc:
                log_debug(f"Glossary preload error: {exc}")
        
        self._current_plugin_name = plugin_name
        self._current_glossary_path = glossary_path
        self.main_handler._cached_glossary = glossary_text
        self._ensure_glossary_loaded(glossary_text=glossary_text, plugin_name=plugin_name, glossary_path=glossary_path)

    def show_glossary_dialog(self, initial_term: Optional[str] = None) -> None:
        system_prompt, glossary_text = self.load_prompts()
        if system_prompt is None:
            return

        if not self.glossary_manager.get_entries():
            QMessageBox.information(self.mw, "Glossary", "Glossary is empty or not loaded.")
            return

        data_source = getattr(self.mw, 'data', None)
        if not isinstance(data_source, list):
            QMessageBox.information(self.mw, "Glossary", "No data is loaded for analysis.")
            return

        occurrence_map = self.glossary_manager.build_occurrence_index(data_source)
        entries = sorted(self.glossary_manager.get_entries(), key=lambda item: item.original.lower())
        dialog = GlossaryDialog(
            parent=self.mw, entries=entries, occurrence_map=occurrence_map,
            jump_callback=self._jump_to_occurrence,
            update_callback=self._handle_glossary_entry_update,
            delete_callback=self._handle_glossary_entry_delete,
            initial_term=initial_term,
        )
        dialog.exec_()

    def add_glossary_entry(self, term: str, context: Optional[str] = None) -> None:
        self.edit_glossary_entry(term, is_new=True, context=context)

    def edit_glossary_entry(self, term: str, is_new: bool = False, context: Optional[str] = None) -> None:
        provider = self.main_handler._prepare_provider()
        if not provider:
            return
        
        entry = self.glossary_manager.get_entry(term) if not is_new else None
        
        dialog = self._create_edit_dialog(term, entry, context)
        if dialog.exec_() != QDialog.Accepted:
            return
            
        new_translation, new_notes = dialog.get_values()
        if not new_translation:
            if entry and new_notes != entry.notes:
                if self.glossary_manager.update_entry(term, entry.translation, new_notes):
                    self.glossary_manager.save_to_disk()
                    self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
                    self._update_glossary_highlighting()
            return
            
        if is_new:
            self.glossary_manager.add_entry(term, new_translation, new_notes)
        else:
            self.glossary_manager.update_entry(term, new_translation, new_notes)
        
        self.glossary_manager.save_to_disk()
        self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
        self._update_glossary_highlighting()

    def _create_edit_dialog(self, term: str, entry: Optional[GlossaryEntry], context: Optional[str]) -> QDialog:
        return _EditEntryDialog(self.mw, term, entry, context)

    def load_prompts(self) -> Tuple[Optional[str], Optional[str]]:
        main_h = self.main_handler
        if main_h._cached_system_prompt and main_h._cached_glossary is not None:
            self._ensure_glossary_loaded(
                glossary_text=main_h._cached_glossary,
                plugin_name=self._current_plugin_name,
                glossary_path=self._current_glossary_path,
            )
            return main_h._cached_system_prompt, main_h._cached_glossary

        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        plugin_dir = Path('plugins', plugin_name, 'translation_prompts') if plugin_name else None
        fallback_dir = Path('translation_prompts')

        system_path = next((p for p in [plugin_dir / 'system_prompt.md' if plugin_dir else None, fallback_dir / 'system_prompt.md'] if p and p.exists()), None)
        glossary_path = next((p for p in [plugin_dir / 'glossary.md' if plugin_dir else None, fallback_dir / 'glossary.md'] if p and p.exists()), None)

        if not system_path:
            QMessageBox.critical(self.mw, "AI Translation", "system_prompt.md not found.")
            return None, None

        try:
            system_prompt = system_path.read_text('utf-8').strip()
        except Exception as e:
            QMessageBox.critical(self.mw, "AI Translation", f"Failed to read system_prompt.md: {e}")
            return None, None

        glossary_text = ''
        if glossary_path:
            try:
                glossary_text = glossary_path.read_text('utf-8').strip()
            except Exception as e:
                QMessageBox.warning(self.mw, "AI Translation", f"Failed to read glossary.md: {e}")
        
        self._current_glossary_path = glossary_path
        self._current_plugin_name = plugin_name
        self.glossary_manager.load_from_text(plugin_name=plugin_name, glossary_path=glossary_path, raw_text=glossary_text)
        self._update_glossary_highlighting()

        main_h._cached_system_prompt = system_prompt
        main_h._cached_glossary = glossary_text
        return system_prompt, glossary_text

    def _ensure_glossary_loaded(self, *, glossary_text: Optional[str], plugin_name: Optional[str], glossary_path: Optional[Path]) -> None:
        if glossary_text is None:
            return
        self.glossary_manager.load_from_text(plugin_name=plugin_name, glossary_path=glossary_path, raw_text=glossary_text)
        self._update_glossary_highlighting()

    def _update_glossary_highlighting(self) -> None:
        manager = self.glossary_manager if self.glossary_manager.get_entries() else None
        editor = getattr(self.mw, 'original_text_edit', None)
        if editor and hasattr(editor, 'set_glossary_manager'):
            editor.set_glossary_manager(manager)

    def _get_original_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return self.data_processor._get_string_from_source(block_idx, string_idx, getattr(self.mw, 'data', None), 'original_for_translation')

    def _get_original_block(self, block_idx: int) -> List[str]:
        data_source = getattr(self.mw, 'data', None)
        if not isinstance(data_source, list) or not (0 <= block_idx < len(data_source)):
            return []
        block = data_source[block_idx]
        return [str(item) for item in block] if isinstance(block, list) else []

    def _resolve_selection_from_original(self) -> Optional[Tuple[int, int, int, int, List[str]]]:
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            QMessageBox.information(self.mw, "AI Translation", "Select a row in the original editor.")
            return None

        editor = getattr(self.mw, 'original_text_edit', None)
        if not editor or not editor.textCursor().hasSelection():
            QMessageBox.information(self.mw, "AI Translation", "Select lines in the original text.")
            return None

        selection = editor.textCursor()
        start_pos, end_pos = sorted([selection.anchor(), selection.position()])
        doc = editor.document()
        start_block = doc.findBlock(start_pos).blockNumber()
        end_block = doc.findBlock(max(end_pos - 1, start_pos)).blockNumber()

        original_text = str(self._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx) or "")
        original_lines = original_text.split('\n')
        max_index = len(original_lines) - 1
        start_block = max(0, min(start_block, max_index))
        end_block = max(0, min(end_block, max_index))
        selected_lines = original_lines[start_block:end_block + 1]

        return self.mw.current_block_idx, self.mw.current_string_idx, start_block, end_block, selected_lines

    def _resolve_selection_from_preview(self) -> Optional[Tuple[int, int, int, int, List[str]]]:
        preview = getattr(self.mw, 'preview_text_edit', None)
        if not preview or not preview.textCursor().hasSelection():
            return None

        cursor = preview.textCursor()
        start_pos, end_pos = sorted([cursor.selectionStart(), cursor.selectionEnd()])
        doc = preview.document()
        start_block = doc.findBlock(start_pos).blockNumber()
        end_block = doc.findBlock(max(end_pos - 1, start_pos)).blockNumber()

        original_text = str(self._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx) or "")
        original_lines = original_text.split('\n')
        max_index = len(original_lines) - 1
        start_block = max(0, min(start_block, max_index))
        end_block = max(0, min(end_block, max_index))
        selected_lines = original_lines[start_block:end_block + 1]

        return self.mw.current_block_idx, self.mw.current_string_idx, start_block, end_block, selected_lines
    
    def _jump_to_occurrence(self, occurrence: GlossaryOccurrence) -> None:
        if occurrence is None: return
        entry = {'block_idx': occurrence.block_idx, 'string_idx': occurrence.string_idx, 'line_idx': occurrence.line_idx}
        self.main_handler.ui_handler._activate_entry(entry)
        if self.mw.statusBar: self.mw.statusBar.showMessage(f"Navigated to glossary term: {occurrence.entry.original}", 4000)

    def _handle_glossary_entry_update(self, original: str, translation: str, notes: str) -> Optional[Tuple[Sequence[GlossaryEntry], Dict[str, List[GlossaryOccurrence]]]]:
        if self.glossary_manager.update_entry(original, translation, notes):
            data_source = getattr(self.mw, 'data', [])
            occurrence_map = self.glossary_manager.build_occurrence_index(data_source)
            entries = sorted(self.glossary_manager.get_entries(), key=lambda entry: entry.original.lower())
            self.main_handler._session_manager.reset()
            self._update_glossary_highlighting()
            self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
            if self.mw.statusBar: self.mw.statusBar.showMessage(f"Glossary updated: {original}", 4000)
            return entries, occurrence_map
        return None

    def _handle_glossary_entry_delete(self, original: str) -> Optional[Tuple[Sequence[GlossaryEntry], Dict[str, List[GlossaryOccurrence]]]]:
        if self.glossary_manager.delete_entry(original):
            data_source = getattr(self.mw, 'data', [])
            occurrence_map = self.glossary_manager.build_occurrence_index(data_source)
            entries = sorted(self.glossary_manager.get_entries(), key=lambda entry: entry.original.lower())
            self.main_handler._session_manager.reset()
            self._update_glossary_highlighting()
            self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
            if self.mw.statusBar: self.mw.statusBar.showMessage(f"Glossary deleted: {original}", 4000)
            return entries, occurrence_map
        return None