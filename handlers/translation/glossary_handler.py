# handlers/translation/glossary_handler.py ---
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
from components.glossary_translation_update_dialog import GlossaryTranslationUpdateDialog
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
        ai_assist_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Glossary Entry")

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel(f"<b>Term:</b> {term}"))
        if context:
            form_layout.addWidget(QLabel(f"<b>Context:</b> <i>{context}</i>"))
        
        translation_layout = QHBoxLayout()
        translation_layout.addWidget(QLabel("Translation:"))
        translation_layout.addStretch(1)
        self._ai_button_default_text = "AI Fill"
        self._ai_button = QPushButton(self._ai_button_default_text, self)
        self._ai_button.setVisible(ai_assist_callback is not None)
        if ai_assist_callback:
            self._ai_button.clicked.connect(ai_assist_callback)
        translation_layout.addWidget(self._ai_button)
        form_layout.addLayout(translation_layout)
        
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
        
    def set_values(self, translation: str, notes: str) -> None:
        self._translation_edit.setText(translation)
        self._notes_edit.setPlainText(notes)

    def get_values(self) -> Tuple[str, str]:
        return (
            self._translation_edit.text().strip(),
            self._notes_edit.toPlainText().strip(),
        )

    def set_ai_busy(self, busy: bool) -> None:
        if not self._ai_button:
            return
        self._ai_button.setEnabled(not busy)
        if busy:
            self._ai_button.setText(f"{self._ai_button_default_text} (working...)")
        else:
            self._ai_button.setText(self._ai_button_default_text)

class GlossaryHandler(BaseTranslationHandler):
    def __init__(self, main_handler):
        super().__init__(main_handler)
        self.glossary_manager = GlossaryManager()
        self._open_glossary_action: Optional[QAction] = None
        self._current_glossary_path: Optional[Path] = None
        self._current_plugin_name: Optional[str] = None
        self._cached_glossary_prompt_template: Optional[str] = None
        self._cached_glossary_prompt_plugin: Optional[str] = None
        self.dialog: Optional[GlossaryDialog] = None
        self._current_prompts_path: Optional[Path] = None
        self.translation_update_dialog: Optional[GlossaryTranslationUpdateDialog] = None
        self._pending_ai_occurrences: List[GlossaryOccurrence] = []
        self._current_translation_entry: Optional[GlossaryEntry] = None
        self._previous_translation_value: Optional[str] = None

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

    def _on_glossary_dialog_closed(self):
        self.dialog = None
        log_debug("Glossary dialog closed and reference cleared.")

    def show_glossary_dialog(self, initial_term: Optional[str] = None) -> None:
        if self.dialog and self.dialog.isVisible():
            self.dialog.raise_()
            self.dialog.activateWindow()
            return

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
        self.dialog = GlossaryDialog(
            parent=self.mw, entries=entries, occurrence_map=occurrence_map,
            jump_callback=self._jump_to_occurrence,
            update_callback=self._handle_glossary_entry_update,
            delete_callback=self._handle_glossary_entry_delete,
            initial_term=initial_term,
        )
        self.dialog.finished.connect(self._on_glossary_dialog_closed)
        self.dialog.show()

    def add_glossary_entry(self, term: str, context: Optional[str] = None) -> None:
        self.edit_glossary_entry(term, is_new=True, context=context)

    def edit_glossary_entry(self, term: str, is_new: bool = False, context: Optional[str] = None) -> None:
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
                    self.main_handler.reset_translation_session()
            return
            
        if is_new:
            self.glossary_manager.add_entry(term, new_translation, new_notes)
        else:
            self.glossary_manager.update_entry(term, new_translation, new_notes)
        
        self.glossary_manager.save_to_disk()
        self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
        self._update_glossary_highlighting()
        self.main_handler.reset_translation_session()

    def _create_edit_dialog(self, term: str, entry: Optional[GlossaryEntry], context: Optional[str]) -> _EditEntryDialog:
        dialog = _EditEntryDialog(
            self.mw, term, entry, context,
            ai_assist_callback=lambda: self._ai_fill_glossary_entry(term, context, dialog)
        )
        return dialog
        
    def _ai_fill_glossary_entry(self, term: str, context: Optional[str], dialog: _EditEntryDialog) -> None:
        provider = self.main_handler._prepare_provider()
        if not provider: return

        template, _ = self._get_glossary_prompt_template()
        if not template: return

        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else "this game"
        system_prompt = template.replace("{{GAME_NAME}}", game_name)

        user_content_parts = [f'Term: "{term}"']
        if context: user_content_parts.append(f'Context line: "{context}"')
        user_content = "\n".join(user_content_parts)

        edited = self.main_handler._maybe_edit_prompt(
            title="AI Glossary Fill Prompt",
            system_prompt=system_prompt,
            user_prompt=user_content,
            save_section='glossary',
            save_field='prompt_template',
        )
        if edited is None:
            return
        edited_system, edited_user = edited

        task_details = {
            'type': 'fill_glossary',
            'composer_args': {'system_prompt': edited_system, 'user_content': edited_user},
            'attempt': 1,
            'max_retries': 1,
            'dialog': dialog,
            'term': term,
            'context_line': context,
            'precomposed_prompt': [
                {"role": "system", "content": edited_system},
                {"role": "user", "content": edited_user},
            ],
        }
        if hasattr(dialog, 'set_ai_busy'):
            dialog.set_ai_busy(True)
        self.main_handler.ui_handler.start_ai_operation("AI Glossary Fill", model_name=self.main_handler._active_model_name)
        self.main_handler._run_ai_task(provider, task_details)

    def _handle_ai_fill_success(self, response, context: dict) -> None:
        """Handle successful AI Fill response for the glossary dialog."""
        self.main_handler.ui_handler.finish_ai_operation()

        dialog = context.get('dialog') if isinstance(context, dict) else None
        if not isinstance(dialog, _EditEntryDialog):
            return

        if hasattr(dialog, 'set_ai_busy'):
            dialog.set_ai_busy(False)

        cleaned = self.main_handler._clean_model_output(response)
        translation_value = None
        notes_value = None

        if cleaned:
            try:
                payload = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                log_debug(f"AI Glossary Fill: failed to parse response: {exc}")
                QMessageBox.warning(self.mw, "AI Glossary Fill", "Could not parse AI response. Check logs for details.")
                return

            if isinstance(payload, dict):
                if 'translation' in payload:
                    translation_value = str(payload.get('translation') or '').strip()
                if 'notes' in payload:
                    notes_value = str(payload.get('notes') or '').strip()

        current_translation, current_notes = dialog.get_values()
        if translation_value is None and notes_value is None:
            QMessageBox.information(self.mw, "AI Glossary Fill", "AI response did not include translation or notes.")
            return

        new_translation = translation_value or current_translation
        new_notes = notes_value if notes_value is not None else current_notes
        dialog.set_values(new_translation, new_notes)

    def _handle_ai_fill_error(self, error_message: str, context: dict) -> None:
        dialog = context.get('dialog') if isinstance(context, dict) else None
        if isinstance(dialog, _EditEntryDialog) and hasattr(dialog, 'set_ai_busy'):
            dialog.set_ai_busy(False)
        if error_message:
            QMessageBox.warning(self.mw, "AI Glossary Fill", error_message)
        else:
            QMessageBox.warning(self.mw, "AI Glossary Fill", "AI request failed.")


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

        prompt_candidates = [
            plugin_dir / 'prompts.json' if plugin_dir else None,
            fallback_dir / 'prompts.json'
        ]
        prompts_path = next((p for p in prompt_candidates if p and p.exists()), None)
        self._current_prompts_path = prompts_path

        if not prompts_path:
            QMessageBox.critical(self.mw, "AI Translation", "prompts.json not found.")
            return None, None

        try:
            prompt_data = json.loads(prompts_path.read_text('utf-8'))
        except Exception as e:
            QMessageBox.critical(self.mw, "AI Translation", f"Failed to load prompts.json: {e}")
            return None, None

        system_prompt = self._extract_system_prompt(prompt_data)
        if not system_prompt:
            QMessageBox.critical(self.mw, "AI Translation", "System prompt not defined in prompts.json.")
            return None, None

        glossary_path = next((p for p in [plugin_dir / 'glossary.md' if plugin_dir else None, fallback_dir / 'glossary.md'] if p and p.exists()), None)

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

    def _extract_glossary_prompt(self, payload: Dict) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        glossary_section = payload.get('glossary')
        if isinstance(glossary_section, dict):
            candidate = glossary_section.get('prompt_template')
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        candidate = payload.get('glossary_prompt')
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        return None

    def _extract_system_prompt(self, payload: Dict) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        translation_section = payload.get('translation')
        if isinstance(translation_section, dict):
            candidate = translation_section.get('system_prompt')
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        candidate = payload.get('translation_system_prompt')
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        return None

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
            
    def _get_glossary_prompt_template(self) -> Tuple[str, Path]:
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        if (self._cached_glossary_prompt_template and self._cached_glossary_prompt_plugin == plugin_name):
            return self._cached_glossary_prompt_template, self._current_glossary_path
        
        plugin_dir = Path('plugins', plugin_name, 'translation_prompts') if plugin_name else None
        fallback_dir = Path('translation_prompts')

        prompt_candidates = [
            plugin_dir / 'prompts.json' if plugin_dir else None,
            fallback_dir / 'prompts.json'
        ]
        prompts_path = next((p for p in prompt_candidates if p and p.exists()), None)
        if prompts_path:
            self._current_prompts_path = prompts_path

        template = _DEFAULT_GLOSSARY_PROMPT
        if prompts_path:
            try:
                prompt_data = json.loads(prompts_path.read_text('utf-8'))
                extracted = self._extract_glossary_prompt(prompt_data)
                if extracted:
                    template = extracted
            except Exception as e:
                log_debug(f"Glossary prompt template read error: {e}")

        self._cached_glossary_prompt_template = template
        self._cached_glossary_prompt_plugin = plugin_name
        return template, self._current_glossary_path

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
        self.mw.ui_updater.highlight_glossary_occurrence(occurrence)
        self.mw.activateWindow()
        self.mw.raise_()
        if self.mw.statusBar: self.mw.statusBar.showMessage(f"Navigated to glossary term: {occurrence.entry.original}", 4000)

    def _handle_glossary_entry_update(self, original: str, translation: str, notes: str) -> Optional[Tuple[Sequence[GlossaryEntry], Dict[str, List[GlossaryOccurrence]]]]:
        previous_entry = self.glossary_manager.get_entry(original)
        previous_translation = previous_entry.translation if previous_entry else None

        if self.glossary_manager.update_entry(original, translation, notes):
            data_source = getattr(self.mw, 'data', [])
            occurrence_map = self.glossary_manager.build_occurrence_index(data_source)
            entries = sorted(self.glossary_manager.get_entries(), key=lambda entry: entry.original.lower())
            self.main_handler.reset_translation_session()
            self._update_glossary_highlighting()
            self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
            if self.mw.statusBar:
                self.mw.statusBar.showMessage(f"Glossary updated: {original}", 4000)

            updated_entry = self.glossary_manager.get_entry(original)
            if (
                previous_translation is not None
                and updated_entry is not None
                and previous_translation.strip() != updated_entry.translation.strip()
            ):
                occurrences = occurrence_map.get(updated_entry.original, [])
                if occurrences:
                    self._show_translation_update_dialog(
                        entry=updated_entry,
                        previous_translation=previous_translation,
                        occurrences=occurrences,
                    )
            return entries, occurrence_map
        return None

    def _show_translation_update_dialog(
        self,
        *,
        entry: GlossaryEntry,
        previous_translation: str,
        occurrences: Sequence[GlossaryOccurrence],
    ) -> None:
        if self.translation_update_dialog and self.translation_update_dialog.isVisible():
            self.translation_update_dialog.raise_()
            self.translation_update_dialog.activateWindow()
            return

        self._current_translation_entry = entry
        self._previous_translation_value = previous_translation
        self._pending_ai_occurrences = []

        dialog = GlossaryTranslationUpdateDialog(
            parent=self.mw,
            term=entry.original,
            old_translation=previous_translation,
            new_translation=entry.translation,
            occurrences=occurrences,
            get_original_text=self._get_occurrence_original_text,
            get_current_translation=self._get_occurrence_translation_text,
            apply_translation=self._apply_occurrence_translation,
            ai_request_single=lambda occ: self._request_ai_occurrence_update(occ, from_batch=False),
            ai_request_all=self._start_ai_occurrence_batch,
        )
        dialog.finished.connect(self._on_translation_update_dialog_closed)
        dialog.show()
        self.translation_update_dialog = dialog

    def _on_translation_update_dialog_closed(self, *_args) -> None:
        self.translation_update_dialog = None
        self._pending_ai_occurrences = []
        self._current_translation_entry = None
        self._previous_translation_value = None

    def save_prompt_section(self, section: str, field: str, value: str) -> bool:
        path = self._current_prompts_path
        if not path:
            return False
        try:
            data = json.loads(path.read_text('utf-8')) if path.exists() else {}
            if not isinstance(data, dict):
                data = {}
        except Exception as exc:
            log_debug(f'Failed to load prompts file {path}: {exc}')
            return False

        section_data = data.setdefault(section, {}) if isinstance(data, dict) else None
        if section_data is None or not isinstance(section_data, dict):
            section_data = {}
            data[section] = section_data
        section_data[field] = value
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except Exception as exc:
            log_debug(f'Failed to write prompts file {path}: {exc}')
            return False

        if section == 'glossary' and field == 'prompt_template':
            self._cached_glossary_prompt_template = value
        if section == 'translation' and field == 'system_prompt':
            self.main_handler._cached_system_prompt = value
        return True

    def _get_occurrence_original_text(self, occurrence: GlossaryOccurrence) -> str:
        return str(self._get_original_string(occurrence.block_idx, occurrence.string_idx) or '')

    def _get_occurrence_translation_text(self, occurrence: GlossaryOccurrence) -> str:
        text, _ = self.main_handler.data_processor.get_current_string_text(occurrence.block_idx, occurrence.string_idx)
        return str(text or '')

    def _apply_occurrence_translation(self, occurrence: GlossaryOccurrence, new_text: str) -> None:
        self.main_handler.data_processor.update_edited_data(occurrence.block_idx, occurrence.string_idx, new_text)
        self.mw.ui_updater.populate_strings_for_block(occurrence.block_idx)
        if self.mw.current_block_idx == occurrence.block_idx:
            self.mw.ui_updater.update_text_views()
        if self.mw.statusBar:
            self.mw.statusBar.showMessage(
                f"Updated translation for block {occurrence.block_idx}, string {occurrence.string_idx}",
                3000,
            )

    def _request_ai_occurrence_update(self, occurrence: GlossaryOccurrence, from_batch: bool) -> None:
        if not self.translation_update_dialog or not self._current_translation_entry:
            return

        dialog = self.translation_update_dialog
        term_entry = self._current_translation_entry
        original_text = self._get_occurrence_original_text(occurrence)
        current_translation = self._get_occurrence_translation_text(occurrence)

        if not from_batch:
            self._pending_ai_occurrences = []

        dialog.set_ai_busy(True)
        if from_batch:
            dialog.set_batch_active(True)

        self.main_handler.request_glossary_occurrence_update(
            occurrence=occurrence,
            original_text=original_text,
            current_translation=current_translation,
            term=term_entry.original,
            old_term_translation=self._previous_translation_value or '',
            new_term_translation=term_entry.translation,
            dialog=dialog,
            from_batch=from_batch,
        )

    def _start_ai_occurrence_batch(self, occurrences: List[GlossaryOccurrence]) -> None:
        if not occurrences:
            QMessageBox.information(self.mw, "AI Update", "No occurrences to process.")
            return
        if not self.translation_update_dialog:
            return

        # Clone list to avoid modifying original sequence
        queue = list(occurrences)
        first = queue.pop(0)
        self._pending_ai_occurrences = queue
        self._request_ai_occurrence_update(first, from_batch=True)

    def _resume_ai_occurrence_batch(self) -> None:
        if not self._pending_ai_occurrences:
            if self.translation_update_dialog:
                self.translation_update_dialog.set_ai_busy(False)
                self.translation_update_dialog.set_batch_active(False)
            return
        next_occ = self._pending_ai_occurrences.pop(0)
        self._request_ai_occurrence_update(next_occ, from_batch=True)

    def _handle_occurrence_ai_result(self, *, occurrence: GlossaryOccurrence, updated_translation: str, from_batch: bool) -> None:
        dialog = self.translation_update_dialog
        if not dialog:
            return

        dialog.on_ai_result(occurrence, updated_translation)
        if from_batch:
            if self._pending_ai_occurrences:
                self._resume_ai_occurrence_batch()
            else:
                dialog.set_ai_busy(False)
                dialog.set_batch_active(False)
        else:
            dialog.set_ai_busy(False)
            dialog.set_batch_active(False)

    def _handle_occurrence_ai_error(self, message: str, from_batch: bool) -> None:
        dialog = self.translation_update_dialog
        if dialog:
            dialog.on_ai_error(message)
        self._pending_ai_occurrences = []

    def _handle_glossary_entry_delete(self, original: str) -> Optional[Tuple[Sequence[GlossaryEntry], Dict[str, List[GlossaryOccurrence]]]]:
        if self.glossary_manager.delete_entry(original):
            data_source = getattr(self.mw, 'data', [])
            occurrence_map = self.glossary_manager.build_occurrence_index(data_source)
            entries = sorted(self.glossary_manager.get_entries(), key=lambda entry: entry.original.lower())
            self.main_handler.reset_translation_session()
            self._update_glossary_highlighting()
            self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
            if self.mw.statusBar: self.mw.statusBar.showMessage(f"Glossostary deleted: {original}", 4000)
            return entries, occurrence_map
        return None