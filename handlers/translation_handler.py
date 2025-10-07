# handlers/translation/translation_handler.py ---
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from PyQt5.QtCore import QTimer, Qt, QPoint, QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QApplication
from .base_handler import BaseHandler
from core.glossary_manager import GlossaryEntry
from core.translation.config import build_default_translation_config
from core.translation.providers import (
    ProviderResponse,
    TranslationProviderError,
    create_translation_provider,
    BaseTranslationProvider,
    GeminiProvider,
)
from core.translation.session_manager import TranslationSessionManager
from .translation.glossary_handler import GlossaryHandler
from .translation.ai_prompt_composer import AIPromptComposer
from .translation.translation_ui_handler import TranslationUIHandler
from .translation.ai_worker import AIWorker
from components.prompt_editor_dialog import PromptEditorDialog
from utils.logging_utils import log_debug
from utils.utils import convert_spaces_to_dots_for_display


class TranslationHandler(BaseHandler):
    _MAX_LOG_EXCERPT = 160

    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self._cached_system_prompt: Optional[str] = None
        self._cached_glossary: Optional[str] = None
        self._session_manager = TranslationSessionManager()
        self._session_mode: str = 'auto'
        self._provider_supports_sessions: bool = False
        self._active_provider_key: Optional[str] = None
        self.thread: Optional[QThread] = None
        self.worker: Optional[AIWorker] = None
        self.is_ai_running = False
        self.translation_progress: Dict[int, Dict[str, Union[set, int]]] = {}
        self.pre_translation_state: Dict[int, List[str]] = {}

        self.glossary_handler = GlossaryHandler(self)
        self.prompt_composer = AIPromptComposer(self)
        self.ui_handler = TranslationUIHandler(self)

        self._glossary_manager = self.glossary_handler.glossary_manager
        
        self.start_new_session = True
        log_debug(f"TranslationHandler.__init__: start_new_session initialized to {self.start_new_session}")

        QTimer.singleShot(0, self.glossary_handler.install_menu_actions)
    
    def initialize_glossary_highlighting(self):
        self.glossary_handler.initialize_glossary_highlighting()

    def show_glossary_dialog(self, initial_term: Optional[str] = None) -> None:
        self.glossary_handler.show_glossary_dialog(initial_term)

    def get_glossary_entry(self, term: str) -> Optional[GlossaryEntry]:
        return self.glossary_handler.glossary_manager.get_entry(term)

    def add_glossary_entry(self, term: str, context: Optional[str] = None) -> None:
        self.glossary_handler.add_glossary_entry(term, context)

    def edit_glossary_entry(self, term: str) -> None:
        self.glossary_handler.edit_glossary_entry(term)

    def append_selection_to_glossary(self):
        preview_edit = self.mw.preview_text_edit
        selection_range = preview_edit._get_selected_line_range()
        if not selection_range:
            QMessageBox.information(self.mw, "Glossary", "No lines selected in the preview.")
            return

        start_line, end_line = selection_range
        
        block_idx = self.mw.current_block_idx
        if block_idx == -1:
            return

        selected_lines = []
        for i in range(start_line, end_line + 1):
            line_text = self.glossary_handler._get_original_string(block_idx, i)
            if line_text is not None:
                selected_lines.append(line_text)
        
        if not selected_lines:
            return

        term_to_add = "\n".join(selected_lines)
        self.glossary_handler.add_glossary_entry(term_to_add)

    def request_glossary_occurrence_update(
        self,
        *,
        occurrence,
        original_text: str,
        current_translation: str,
        term: str,
        old_term_translation: str,
        new_term_translation: str,
        dialog,
        from_batch: bool,
        prompt_override: Optional[Tuple[str, str]] = None,
    ) -> Optional[Tuple[str, str]]:
        provider = self._prepare_provider()
        if not provider:
            self.glossary_handler._handle_occurrence_ai_error("AI provider is not configured.", from_batch)
            return None

        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            self.glossary_handler._handle_occurrence_ai_error("Failed to load prompts.", from_batch)
            return None

        session_state = self._session_manager.get_state()

        composer_args = {
            'system_prompt': system_prompt,
            'source_text': current_translation or '',
            'current_translation': current_translation or '',
            'original_text': original_text or '',
            'term': term,
            'old_translation': old_term_translation or '',
            'new_translation': new_term_translation or '',
            'expected_lines': max(1, (current_translation or '').count('\n') + 1),
            'session_state': session_state,
        }
        combined_system, user_prompt = self.prompt_composer.compose_glossary_occurrence_update_request(**composer_args)
        if prompt_override and all(isinstance(item, str) and item.strip() for item in prompt_override):
            edited_system, edited_user = prompt_override
        else:
            edited = self._maybe_edit_prompt(
                title="AI Glossary Update Prompt",
                system_prompt=combined_system,
                user_prompt=user_prompt,
                save_section='glossary_occurrence_update',
            )
            if edited is None:
                if from_batch and hasattr(dialog, 'set_ai_busy'):
                    dialog.set_ai_busy(False)
                    dialog.set_batch_active(False)
                return None
            edited_system, edited_user = edited

        precomposed = [
            {"role": "system", "content": edited_system},
            {"role": "user", "content": edited_user},
        ]
        task_details = {
            'type': 'glossary_occurrence_update',
            'composer_args': composer_args,
            'attempt': 1,
            'max_retries': 1,
            'occurrence': occurrence,
            'dialog': dialog,
            'from_batch': from_batch,
        }
        if not self._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt,
            full_system_prompt=edited_system,
            user_prompt=edited_user,
            task_type='glossary_occurrence_batch_update',
        ):
            task_details['precomposed_prompt'] = precomposed

        self.ui_handler.start_ai_operation("AI Glossary Update", model_name=self._active_model_name)
        self._run_ai_task(provider, task_details)
        return edited_system, edited_user

    def request_glossary_occurrence_batch_update(
        self,
        *,
        occurrences,
        term: str,
        old_term_translation: str,
        new_term_translation: str,
        dialog,
    ) -> bool:
        if not occurrences:
            self.glossary_handler._handle_occurrence_ai_error("No occurrences to process.", True)
            return False

        provider = self._prepare_provider()
        if not provider:
            return False

        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            self.glossary_handler._handle_occurrence_ai_error("Failed to load prompts.", True)
            return False

        session_state = self._session_manager.get_state()
        occurrences_list = list(occurrences)
        batch_items = []
        expected_lines_by_id: Dict[str, int] = {}
        occurrence_metadata: List[Dict[str, object]] = []
        occurrence_lookup: Dict[str, object] = {}

        for index, occurrence in enumerate(occurrences_list):
            occurrence_id = str(index)
            original_text = self.glossary_handler._get_occurrence_original_text(occurrence) or ""
            current_translation = self.glossary_handler._get_occurrence_translation_text(occurrence) or ""
            expected_lines = max(1, current_translation.count('\n') + 1)
            expected_lines_by_id[occurrence_id] = expected_lines
            batch_items.append({
                "id": occurrence_id,
                "block_index": occurrence.block_idx,
                "string_index": occurrence.string_idx,
                "line_index": occurrence.line_idx + 1,
                "original_text": original_text,
                "current_translation": current_translation,
                "expected_lines": expected_lines,
            })
            occurrence_metadata.append({"id": occurrence_id, "occurrence": occurrence})
            occurrence_lookup[occurrence_id] = occurrence

        combined_system, user_prompt = self.prompt_composer.compose_glossary_occurrence_batch_request(
            system_prompt=system_prompt,
            term=term,
            old_translation=old_term_translation,
            new_translation=new_term_translation,
            batch_items=batch_items,
            session_state=session_state,
        )

        edited = self._maybe_edit_prompt(
            title="AI Glossary Batch Update Prompt",
            system_prompt=combined_system,
            user_prompt=user_prompt,
            save_section='glossary_occurrence_update',
        )
        if edited is None:
            return False
        edited_system, edited_user = edited

        composer_args = {
            'system_prompt': edited_system,
            'user_prompt': edited_user,
            'batch_items': batch_items,
        }
        precomposed = [
            {"role": "system", "content": edited_system},
            {"role": "user", "content": edited_user},
        ]
        task_details = {
            'type': 'glossary_occurrence_batch_update',
            'composer_args': composer_args,
            'attempt': 1,
            'max_retries': 1,
            'dialog': dialog,
            'occurrence_metadata': occurrence_metadata,
            'occurrence_lookup': occurrence_lookup,
            'expected_lines': expected_lines_by_id,
            'from_batch': True,
        }
        if not self._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt,
            full_system_prompt=edited_system,
            user_prompt=edited_user,
            task_type='glossary_occurrence_batch_update',
        ):
            task_details['precomposed_prompt'] = precomposed

        self.ui_handler.start_ai_operation("AI Glossary Update (All)", model_name=self._active_model_name)
        self._run_ai_task(provider, task_details)
        return True

    def request_glossary_notes_variation(
        self,
        *,
        term: str,
        translation: str,
        current_notes: str,
        context_line: Optional[str],
        dialog,
    ) -> bool:
        provider = self._prepare_provider()
        if not provider:
            return False

        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            return False

        session_state = self._session_manager.get_state()
        source_sections = [f"Term: {term}", f"Translation: {translation or '[empty]'}"]
        if context_line:
            source_sections.append(f"Context: {context_line}")
        source_text = '\n'.join(source_sections)

        composer_args = {
            'system_prompt': system_prompt,
            'source_text': source_text,
            'block_idx': None,
            'string_idx': None,
            'expected_lines': max(1, (current_notes or '').count('\n') + 1),
            'current_translation': current_notes or '',
            'mode_description': 'glossary_notes',
            'request_type': 'glossary_notes_variation',
            'session_state': session_state,
        }
        combined_system, user_prompt = self.prompt_composer.compose_variation_request(**composer_args)
        edited = self._maybe_edit_prompt(
            title="AI Glossary Notes Prompt",
            system_prompt=combined_system,
            user_prompt=user_prompt,
        )
        if edited is None:
            return False
        edited_system, edited_user = edited

        precomposed = [
            {"role": "system", "content": edited_system},
            {"role": "user", "content": edited_user},
        ]
        task_details = {
            'type': 'glossary_notes_variation',
            'composer_args': composer_args,
            'attempt': 1,
            'max_retries': 1,
            'dialog': dialog,
            'term': term,
            'translation': translation,
            'current_notes': current_notes,
        }
        if not self._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt,
            full_system_prompt=edited_system,
            user_prompt=edited_user,
            task_type='glossary_notes_variation',
        ):
            task_details['precomposed_prompt'] = precomposed

        self.ui_handler.start_ai_operation("AI Glossary Notes", model_name=self._active_model_name)
        self._run_ai_task(provider, task_details)
        return True

    def reset_translation_session(self) -> None:
        self._session_manager.reset()
        self._cached_system_prompt = None
        self._cached_glossary = None
        self.start_new_session = True
        log_debug(f"TranslationHandler.reset_translation_session: Manual reset. start_new_session set to {self.start_new_session}")

        config = getattr(self.mw, 'translation_config', None)
        if config and config.get('provider') == 'gemini':
            provider_settings = config.get('providers', {}).get('gemini', {})
            if provider_settings:
                try:
                    provider = GeminiProvider(provider_settings)
                    provider.start_new_chat_session()
                except Exception as e:
                    log_debug(f"Could not start new chat session on reset: {e}")

        if self.mw.statusBar:
            self.mw.statusBar.showMessage("AI session reset.", 4000)

    def _trim_trailing_whitespace_from_lines(self, text: str) -> str:
        if not text:
            return ""
        lines = text.split('\n')
        cleaned_lines = [line.rstrip() for line in lines]
        return '\n'.join(cleaned_lines)
    
    def _maybe_edit_prompt(
        self,
        *,
        title: str,
        system_prompt: str,
        user_prompt: str,
        save_section: Optional[str] = None,
        save_field: str = 'system_prompt',
    ) -> Optional[tuple[str, str]]:
        is_ctrl_pressed = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
        enabled = getattr(self.mw, 'prompt_editor_enabled', True)
        if not is_ctrl_pressed and not enabled:
            return system_prompt, user_prompt

        allow_save = bool(save_section and self.glossary_handler._current_prompts_path)
        dialog = PromptEditorDialog(
            parent=self.mw,
            title=title,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            allow_save=allow_save,
        )
        if dialog.exec_() != dialog.Accepted:
            return None

        edited_system, edited_user, save_requested = dialog.get_user_inputs()
        edited_system = edited_system.rstrip()
        edited_user = edited_user.rstrip()

        if save_requested and allow_save and save_section:
            if self.glossary_handler.save_prompt_section(save_section, save_field, edited_system):
                if save_section == 'translation' and save_field == 'system_prompt':
                    self._cached_system_prompt = edited_system
        return edited_system, edited_user


    def _should_use_session(self, task_type: str) -> bool:
        if not self._provider_supports_sessions:
            return False
        return True

    def _prepare_session_for_request(self, *, base_system_prompt: str, full_system_prompt: str, user_prompt: str, task_type: str) -> Optional[dict]:
        log_debug(f"Preparing session, start_new_session is {self.start_new_session}")
        if not self._should_use_session(task_type):
            return None
        state = self._session_manager.ensure_session(
            provider_key=self._active_provider_key or '',
            base_system_prompt=base_system_prompt,
            full_system_prompt=full_system_prompt,
            supports_sessions=self._provider_supports_sessions,
            start_new_session=self.start_new_session,
        )
        if not state:
            return None
        
        self.start_new_session = False
        log_debug(f"Session established. start_new_session set to {self.start_new_session}")
        
        return {
            'state': state,
            'user_message': {'role': 'user', 'content': user_prompt},
        }

    def _attach_session_to_task(self, task_details: dict, *, base_system_prompt: str, full_system_prompt: str, user_prompt: str, task_type: str) -> bool:
        session_info = self._prepare_session_for_request(
            base_system_prompt=base_system_prompt,
            full_system_prompt=full_system_prompt,
            user_prompt=user_prompt,
            task_type=task_type,
        )
        if not session_info:
            return False
        task_details['session'] = session_info
        task_details['session_state'] = session_info['state']
        task_details['session_user_message'] = session_info['user_message']['content']
        return True

    def _record_session_exchange(self, *, context: dict, assistant_content: str, response: Optional[ProviderResponse] = None) -> None:
        state = context.get('session_state') if isinstance(context, dict) else None
        user_content = context.get('session_user_message') if isinstance(context, dict) else None
        if not state or not isinstance(user_content, str):
            return
        conversation_id = response.conversation_id if isinstance(response, ProviderResponse) else None
        state.record_exchange(
            user_content=user_content,
            assistant_content=assistant_content or '',
            conversation_id=conversation_id,
        )

    def _set_notes_dialog_busy(self, dialog_obj, busy: bool) -> None:
        if not dialog_obj:
            return
        if hasattr(dialog_obj, 'set_ai_busy'):
            dialog_obj.set_ai_busy(busy)
        elif hasattr(dialog_obj, 'set_notes_variation_busy'):
            dialog_obj.set_notes_variation_busy(busy)

    def _run_ai_task(self, provider: BaseTranslationProvider, task_details: dict):
        self.is_ai_running = True
        self.thread = QThread()
        task_details['dialog_steps'] = self.ui_handler.status_dialog.steps
        self.worker = AIWorker(provider, self.prompt_composer, task_details)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.step_updated.connect(self.ui_handler.update_ai_operation_step)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: setattr(self, 'thread', None))
        self.thread.finished.connect(lambda: setattr(self, 'worker', None))
        self.thread.finished.connect(lambda: setattr(self, 'is_ai_running', False))

        task_type = task_details.get('type')
        if task_type == 'translate_preview':
            self.worker.success.connect(self._handle_preview_translation_success)
        elif task_type == 'translate_block_chunked':
            self.worker.total_chunks_calculated.connect(self._setup_progress_bar)
            self.worker.chunk_translated.connect(self._handle_chunk_translated)
            self.worker.translation_cancelled.connect(self._handle_translation_cancellation)
            self.worker.progress_updated.connect(self.ui_handler.status_dialog.update_progress)
        elif task_type == 'translate_single':
            self.worker.success.connect(self._handle_single_translation_success)
        elif task_type == 'generate_variation':
            self.worker.success.connect(self._handle_variation_success)
        elif task_type == 'fill_glossary':
            self.worker.success.connect(self.glossary_handler._handle_ai_fill_success)
        elif task_type == 'glossary_occurrence_update':
            self.worker.success.connect(self._handle_glossary_occurrence_update_success)
        elif task_type == 'glossary_occurrence_batch_update':
            self.worker.success.connect(self._handle_glossary_occurrence_batch_success)
        elif task_type == 'glossary_notes_variation':
            self.worker.success.connect(self._handle_glossary_notes_variation_success)

        self.worker.error.connect(self._handle_ai_error)

        self.thread.start()

    def prompt_for_revert_after_cancel(self):
        if not self.worker:
            return

        block_idx = self.worker.task_details.get('block_idx')
        if block_idx is None or block_idx not in self.pre_translation_state:
            self.ui_handler.finish_ai_operation()
            return

        reply = QMessageBox.question(
            self.mw,
            "Translation Cancelled",
            "Keep the already translated parts?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.No:
            if block_idx in self.pre_translation_state:
                original_texts = self.pre_translation_state[block_idx]
                for i, text in enumerate(original_texts):
                    self.data_processor.update_edited_data(block_idx, i, text)
                
                del self.pre_translation_state[block_idx]

            if block_idx in self.translation_progress:
                del self.translation_progress[block_idx]

            self.ui_updater.populate_strings_for_block(block_idx)
            self.ui_updater.update_text_views()
        else:
            if block_idx in self.pre_translation_state:
                del self.pre_translation_state[block_idx]
        
        self.ui_handler.finish_ai_operation()
        self.ui_updater.update_block_item_text_with_problem_count(block_idx)

    def _handle_translation_cancellation(self):
        log_debug("TranslationHandler: Worker has confirmed cancellation.")
        self.reset_translation_session()
        self.ui_handler.finish_ai_operation()

    def _setup_progress_bar(self, total_chunks: int, completed_chunks: int):
        block_idx = self.worker.task_details.get('block_idx')
        if block_idx is not None and block_idx in self.translation_progress:
            self.translation_progress[block_idx]['total_chunks'] = total_chunks
        
        self.translated_chunks_count = completed_chunks
        self.ui_handler.status_dialog.setup_progress_bar(total_chunks, completed_chunks)

    def translate_current_string(self):
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1: return
        self._translate_and_apply(
            source_text=str(self.glossary_handler._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx)),
            expected_lines=len(str(self.glossary_handler._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx)).split("\n")),
            mode_description="current row",
            block_idx=self.mw.current_block_idx,
            string_idx=self.mw.current_string_idx
        )

    def translate_preview_selection(self, context_menu_pos: QPoint):
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        block_idx = self.mw.current_block_idx
        if block_idx == -1: return

        preview_edit = self.mw.preview_text_edit
        selection_range = preview_edit._get_selected_line_range()
        start_line, end_line = selection_range if selection_range else (cursor.blockNumber(), cursor.blockNumber()) if (cursor := preview_edit.cursorForPosition(context_menu_pos)).blockNumber() >= 0 else (None, None)
        if start_line is None: return

        string_indices = list(range(start_line, end_line + 1))
        source_items = [{"id": idx, "text": str(self.glossary_handler._get_original_string(block_idx, idx))} for idx in string_indices]

        provider = self._prepare_provider()
        if not provider: return

        operation_title = f"AI Translation (Lines {start_line + 1}-{end_line + 1})" if start_line != end_line else f"AI Translation (Line {start_line + 1})"
        
        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            return

        session_state = self._session_manager.get_state()
        composer_args = {
            'system_prompt': system_prompt,
            'source_items': source_items, 'block_idx': block_idx,
            'mode_description': f"lines {start_line + 1}-{end_line + 1}",
            'session_state': session_state,
        }
        
        preview_system, preview_user, p_map = self.prompt_composer.compose_batch_request(**composer_args)

        edited = self._maybe_edit_prompt(
            title=operation_title,
            system_prompt=preview_system,
            user_prompt=preview_user,
            save_section='translation'
        )

        if edited is None:
            return
        edited_system, edited_user = edited

        self.ui_handler.start_ai_operation(operation_title, model_name=self._active_model_name)

        task_details = {
            'type': 'translate_preview',
            'provider': provider,
            'source_items': source_items,
            'attempt': 1,
            'max_retries': 4,
            'block_idx': block_idx,
            'mode_description': f"lines {start_line + 1}-{end_line + 1}",
            'timeout_seconds': self._resolve_base_timeout(provider),
            'precomposed_prompt': [
                {"role": "system", "content": edited_system},
                {"role": "user", "content": edited_user}
            ],
            'placeholder_map': p_map,
        }
        self._initiate_batch_translation(task_details)

    def translate_current_block(self, block_idx: Optional[int] = None) -> None:
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        target_block_idx = self.mw.current_block_idx if block_idx is None else block_idx
        if target_block_idx is None or target_block_idx == -1:
            QMessageBox.information(self.mw, "AI Translation", "Select a block to translate.")
            return
        
        self.start_new_session = True
        log_debug(f"TranslationHandler.translate_current_block: Block translation initiated. start_new_session set to {self.start_new_session}")

        data_source = getattr(self.mw, 'data', None)
        if not isinstance(data_source, list) or not (0 <= target_block_idx < len(data_source)):
            QMessageBox.information(self.mw, "AI Translation", "No block data available to translate.")
            return

        block_strings = self.glossary_handler._get_original_block(target_block_idx)
        if not block_strings:
            QMessageBox.information(self.mw, "AI Translation", "The selected block is empty.")
            return

        self.pre_translation_state[target_block_idx] = self.data_processor.get_block_texts(target_block_idx)

        source_items = [
            {"id": idx, "text": str(self.glossary_handler._get_original_string(target_block_idx, idx) or "")}
            for idx in range(len(block_strings))
        ]

        provider = self._prepare_provider()
        if not provider:
            return

        base_timeout = self._resolve_base_timeout(provider)
        block_timeout = base_timeout * 10
        log_debug(
            f"Starting block AI translation for block {target_block_idx} with timeout {block_timeout}s (base {base_timeout}s); lines={len(source_items)}"
        )

        operation_title = f"AI Translation (Block {target_block_idx + 1})"
        self.ui_handler.start_ai_operation(operation_title, is_chunked=True, model_name=self._active_model_name)

        task_details = {
            'type': 'translate_block_chunked',
            'provider': provider,
            'source_items': source_items,
            'attempt': 1,
            'max_retries': 4,
            'block_idx': target_block_idx,
            'mode_description': f"block {target_block_idx + 1}",
            'provider_settings_override': {'timeout': block_timeout},
            'timeout_seconds': block_timeout
        }
        self._initiate_batch_translation(task_details)

    def resume_block_translation(self, block_idx: int) -> None:
        if block_idx not in self.translation_progress:
            QMessageBox.information(self.mw, "Resume Translation", "No active translation session found for this block.")
            return

        progress_entry = self.translation_progress.get(block_idx, {})

        if block_idx not in self.pre_translation_state:
            self.pre_translation_state[block_idx] = self.data_processor.get_block_texts(block_idx)

        target_block_idx = block_idx
        block_strings = self.glossary_handler._get_original_block(target_block_idx)
        source_items = [
            {"id": idx, "text": str(self.glossary_handler._get_original_string(target_block_idx, idx) or "")}
            for idx in range(len(block_strings))
        ]

        provider = self._prepare_provider()
        if not provider:
            return

        base_timeout = self._resolve_base_timeout(provider)
        block_timeout = base_timeout * 10

        operation_title = f"Resuming Translation (Block {target_block_idx + 1})"
        self.ui_handler.start_ai_operation(operation_title, is_chunked=True, model_name=self._active_model_name)

        task_details = {
            'type': 'translate_block_chunked',
            'provider': provider,
            'source_items': source_items,
            'attempt': 1,
            'max_retries': 4,
            'block_idx': target_block_idx,
            'mode_description': f"block {target_block_idx + 1}",
            'provider_settings_override': {'timeout': block_timeout},
            'timeout_seconds': block_timeout,
            'is_resume': True
        }
        if progress_entry.get('custom_user_header'):
            task_details['custom_user_header'] = progress_entry.get('custom_user_header')
            task_details['custom_user_label'] = progress_entry.get('custom_user_label')
        if progress_entry.get('system_prompt_override'):
            task_details['system_prompt_override'] = progress_entry.get('system_prompt_override')
        self._initiate_batch_translation(task_details)

    def _resolve_base_timeout(self, provider: BaseTranslationProvider) -> int:
        try:
            base = int(provider.settings.get('timeout', 120))
        except (TypeError, ValueError):
            base = 120
        return max(base, 30)


    def _initiate_batch_translation(self, context: dict):
        self.translated_chunks_count = 0
        provider = context['provider']
        
        block_idx = context.get('block_idx')
        task_type = context.get('type')

        if task_type == 'translate_block_chunked' and block_idx is not None:
            if not context.get('is_resume', False):
                self.reset_translation_session()
                self.translation_progress[block_idx] = {'completed_chunks': set(), 'total_chunks': 0}
            
            context['chunks_to_skip'] = self.translation_progress.get(block_idx, {}).get('completed_chunks', set())

        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            self.ui_handler.finish_ai_operation()
            return

        if context.get('system_prompt_override'):
            system_prompt = context['system_prompt_override']

        session_state = self._session_manager.get_state()
        composer_args = {
            'system_prompt': system_prompt,
            'source_items': context['source_items'], 'block_idx': context['block_idx'],
            'mode_description': context['mode_description'], 'is_retry': (context['attempt'] > 1),
            'retry_reason': context.get('last_error', ''),
            'session_state': session_state,
        }
        context['composer_args'] = composer_args

        if 'precomposed_prompt' not in context:
            force_prompt = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
            should_edit_prompt = (
                task_type == 'translate_block_chunked'
                and block_idx is not None
                and (force_prompt or not context.get('is_resume', False))
            )
            if should_edit_prompt:
                preview_system, preview_user, _ = self.prompt_composer.compose_batch_request(**composer_args)
                edited = self._maybe_edit_prompt(
                    title="AI Block Translation Prompt",
                    system_prompt=preview_system,
                    user_prompt=preview_user,
                    save_section='translation',
                )
                if edited is None:
                    self.ui_handler.finish_ai_operation()
                    if block_idx is not None and not context.get('is_resume', False):
                        self.translation_progress.pop(block_idx, None)
                        self.pre_translation_state.pop(block_idx, None)
                    return
                edited_system, edited_user = edited
                context['composer_args']['system_prompt'] = edited_system
                header, sep, json_section = edited_user.partition('JSON DATA TO PROCESS:')
                if sep:
                    context['custom_user_header'] = header
                    context['custom_user_label'] = sep
                else:
                    context['custom_user_header'] = edited_user
                    context['custom_user_label'] = 'JSON DATA TO PROCESS:'
                context['system_prompt_override'] = edited_system
                if block_idx is not None:
                    progress_entry = self.translation_progress.setdefault(block_idx, {'completed_chunks': set(), 'total_chunks': 0})
                    progress_entry['custom_user_header'] = context['custom_user_header']
                    progress_entry['custom_user_label'] = context['custom_user_label']
                    progress_entry['system_prompt_override'] = edited_system
        
        final_system_prompt = context['composer_args']['system_prompt']
        final_user_prompt, _, p_map = self.prompt_composer.compose_batch_request(**context['composer_args'])
        context['placeholder_map'] = p_map 

        if not self._attach_session_to_task(
            context,
            base_system_prompt=system_prompt,
            full_system_prompt=final_system_prompt,
            user_prompt=final_user_prompt,
            task_type=task_type,
        ):
             if 'precomposed_prompt' not in context:
                context['precomposed_prompt'] = [
                    {"role": "system", "content": final_system_prompt},
                    {"role": "user", "content": final_user_prompt}
                ]
        
        self._run_ai_task(provider, context)

    def _handle_chunk_translated(self, chunk_index: int, chunk_text: str, context: dict):
        log_debug(f"Received translated chunk {chunk_index}. Raw AI response:\n{chunk_text}")
        try:
            block_idx = context['block_idx']
            parsed_json = json.loads(chunk_text)
            translated_strings = parsed_json.get("translated_strings")
            if not isinstance(translated_strings, list):
                raise ValueError("Invalid response structure: 'translated_strings' is not a list.")

            for item in translated_strings:
                string_idx, translated_text = item["id"], item["translation"]
                final_text = self._trim_trailing_whitespace_from_lines(translated_text)
                self.data_processor.update_edited_data(block_idx, string_idx, final_text)
            
            if block_idx in self.translation_progress:
                self.translation_progress[block_idx]['completed_chunks'].add(chunk_index)

            self.ui_updater.populate_strings_for_block(block_idx)
            self.translated_chunks_count = len(self.translation_progress.get(block_idx, {}).get('completed_chunks', set()))
            self.ui_handler.status_dialog.update_progress(self.translated_chunks_count)
            
            total_chunks = self.translation_progress.get(block_idx, {}).get('total_chunks', -1)
            if self.translated_chunks_count == total_chunks:
                self.ui_handler.finish_ai_operation()
                self.ui_updater.update_text_views()
                if hasattr(self.mw, 'app_action_handler'):
                    self.mw.app_action_handler.rescan_issues_for_single_block(block_idx, show_message_on_completion=False)
                
                if block_idx in self.translation_progress:
                    del self.translation_progress[block_idx]
                if block_idx in self.pre_translation_state:
                    del self.pre_translation_state[block_idx]
                
                self.reset_translation_session()

        except (json.JSONDecodeError, ValueError) as e:
            self._handle_ai_error(f"Failed to process chunk {chunk_index + 1}: {e}", context)

    def _handle_preview_translation_success(self, response: ProviderResponse, context: dict):
        self.ui_handler.update_ai_operation_step(3, self.ui_handler.status_dialog.steps[3], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned_text = self._clean_model_output(response)
        
        try:
            parsed_json = json.loads(cleaned_text)
            translated_strings = parsed_json.get("translated_strings")
            if not isinstance(translated_strings, list) or len(translated_strings) != len(context['source_items']):
                raise ValueError("Invalid response structure or item count mismatch.")

            self.ui_handler.update_ai_operation_step(4, self.ui_handler.status_dialog.steps[4], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
            for item in translated_strings:
                string_idx, translated_text = item["id"], item["translation"]
                final_text = self._trim_trailing_whitespace_from_lines(translated_text)
                self.data_processor.update_edited_data(context['block_idx'], string_idx, final_text)

            self._record_session_exchange(context=context, assistant_content=cleaned_text, response=response)
            self.ui_handler.finish_ai_operation()
            self.ui_updater.populate_strings_for_block(context['block_idx'])
            self.ui_updater.update_text_views()
            if hasattr(self.mw, 'app_action_handler'):
                self.mw.app_action_handler.rescan_issues_for_single_block(context['block_idx'], show_message_on_completion=False)

        except (json.JSONDecodeError, ValueError) as e:
            self._handle_ai_error(f"Validation failed: {e}", context)

    def _handle_single_translation_success(self, response: ProviderResponse, context: dict):
        self.ui_handler.update_ai_operation_step(3, self.ui_handler.status_dialog.steps[3], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned_translation = self._clean_model_output(response)
        trimmed_translation = self._trim_trailing_whitespace_from_lines(cleaned_translation)
        self._record_session_exchange(context=context, assistant_content=cleaned_translation, response=response)
        
        self.ui_handler.update_ai_operation_step(4, self.ui_handler.status_dialog.steps[4], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        self.ui_handler.apply_full_translation(trimmed_translation)
        self.ui_handler.finish_ai_operation()

    def _handle_glossary_occurrence_update_success(self, response: ProviderResponse, context: dict) -> None:
        from_batch = context.get('from_batch', False)
        occurrence = context.get('occurrence')
        composer_args = context.get('composer_args') or {}

        self.ui_handler.finish_ai_operation()
        cleaned = self._clean_model_output(response)
        try:
            payload = json.loads(cleaned) if cleaned else {}
        except json.JSONDecodeError as exc:
            self.glossary_handler._handle_occurrence_ai_error(f"Failed to parse AI response: {exc}", from_batch)
            return

        translation_value = payload.get('translation') if isinstance(payload, dict) else None
        if not isinstance(translation_value, str):
            self.glossary_handler._handle_occurrence_ai_error("AI response missing string 'translation' field.", from_batch)
            return

        trimmed = self._trim_trailing_whitespace_from_lines(translation_value)

        expected_lines = composer_args.get('expected_lines') if isinstance(composer_args, dict) else None
        if isinstance(expected_lines, int) and expected_lines > 0:
            actual_lines = trimmed.count('\n') + 1
            if actual_lines != expected_lines:
                self.glossary_handler._handle_occurrence_ai_error(
                    f"AI response returned {actual_lines} lines (expected {expected_lines}).",
                    from_batch,
                )
                return

        if occurrence is None:
            self.glossary_handler._handle_occurrence_ai_error("Glossary update is missing occurrence context.", from_batch)
            return

        self._record_session_exchange(context=context, assistant_content=cleaned, response=response)
        self.glossary_handler._handle_occurrence_ai_result(
            occurrence=occurrence,
            updated_translation=trimmed,
            from_batch=from_batch,
        )
        log_debug("Glossary AI occurrence update validated and applied.")


    def _handle_glossary_occurrence_batch_success(self, response: ProviderResponse, context: dict) -> None:
        from_batch = context.get('from_batch', True)
        expected_lines = context.get('expected_lines') or {}
        occurrence_lookup = context.get('occurrence_lookup') or {}

        self.ui_handler.finish_ai_operation()
        cleaned = self._clean_model_output(response)
        try:
            payload = json.loads(cleaned) if cleaned else {}
        except json.JSONDecodeError as exc:
            self.glossary_handler._handle_occurrence_ai_error(f"Failed to parse AI response: {exc}", from_batch)
            return

        updates = None
        if isinstance(payload, dict):
            updates = payload.get('occurrences') or payload.get('translations') or payload.get('updated_translations')
        if not isinstance(updates, list):
            self.glossary_handler._handle_occurrence_ai_error("AI response missing 'occurrences' array.", from_batch)
            return

        results: Dict[str, str] = {}
        for item in updates:
            if not isinstance(item, dict):
                continue
            occ_id = item.get('id') or item.get('occurrence_id')
            translation_value = item.get('translation')
            if occ_id is None or not isinstance(translation_value, str):
                continue
            occ_id = str(occ_id)
            trimmed = self._trim_trailing_whitespace_from_lines(translation_value)
            expected = expected_lines.get(occ_id)
            if isinstance(expected, int) and expected > 0:
                actual = trimmed.count('\n') + 1
                if actual != expected:
                    self.glossary_handler._handle_occurrence_ai_error(
                        f"AI response for occurrence {occ_id} returned {actual} lines (expected {expected}).",
                        from_batch,
                    )
                    return
            results[occ_id] = trimmed

        missing = [occ_id for occ_id in occurrence_lookup.keys() if occ_id not in results]
        if missing:
            self.glossary_handler._handle_occurrence_ai_error(
                f"AI response missing translations for occurrences: {', '.join(missing)}.",
                from_batch,
            )
            return

        self._record_session_exchange(context=context, assistant_content=cleaned, response=response)
        self.glossary_handler._handle_occurrence_batch_success(results=results, context=context)


    def _handle_glossary_notes_variation_success(self, response: ProviderResponse, context: dict) -> None:
        self.ui_handler.finish_ai_operation()
        cleaned = self._clean_model_output(response)
        self._record_session_exchange(context=context, assistant_content=cleaned, response=response)

        dialog = context.get('dialog')
        self._set_notes_dialog_busy(dialog, False)

        variants = self.ui_handler.parse_variation_payload(cleaned)
        if not variants:
            QMessageBox.information(self.mw, "AI Glossary Notes", "Failed to parse variations from AI response.")
            return

        chosen = self.ui_handler.show_variations_dialog(variants)
        if not chosen:
            return

        if dialog and hasattr(dialog, 'get_values') and hasattr(dialog, 'set_values'):
            current_translation, _ = dialog.get_values()
            dialog.set_values(current_translation, chosen)
        elif dialog and hasattr(dialog, 'apply_notes_variation'):
            dialog.apply_notes_variation(chosen)
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("Applied AI-generated glossary notes.", 4000)

    def _handle_variation_success(self, response: ProviderResponse, context: dict):
        self.ui_handler.update_ai_operation_step(3, self.ui_handler.status_dialog.steps[3], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned = self._clean_model_output(response)
        self._record_session_exchange(context=context, assistant_content=cleaned, response=response)
        variants_raw = self.ui_handler.parse_variation_payload(cleaned)
        self.ui_handler.finish_ai_operation()

        if not variants_raw:
            QMessageBox.information(self.mw, "AI Variation", "Failed to parse variations from AI response.")
            return
            
        trimmed = [self._trim_trailing_whitespace_from_lines(v) for v in variants_raw]
        
        chosen = self.ui_handler.show_variations_dialog(trimmed)
        if chosen:
            if context.get('is_inline', False):
                self.ui_handler.apply_inline_variation(chosen)
            else:
                self.ui_handler.apply_full_translation(chosen)

    def _handle_ai_error(self, error_message: str, context: dict):
        attempt = context.get('attempt', 1)
        max_attempts = context.get('max_retries', 1)
        mode = context.get('mode_description', 'unknown')
        task_type = context.get('type', 'unknown')
        timeout_seconds = context.get('timeout_seconds')

        log_debug(
            f"AI Error (type={task_type}, attempt={attempt}/{max_attempts}, mode={mode}): {error_message}"
        )
        self.reset_translation_session()

        if task_type == 'translate_block_chunked':
            provider = context.get('provider')
            if isinstance(provider, GeminiProvider):
                provider.start_new_chat_session()

        if context.get('type') == 'fill_glossary':
            self.ui_handler.finish_ai_operation()
            self.glossary_handler._handle_ai_fill_error(error_message, context)
            return

        if context.get('type') == 'glossary_occurrence_update':
            self.ui_handler.finish_ai_operation()
            self.glossary_handler._handle_occurrence_ai_error(error_message, context.get('from_batch', False))
            return

        if context.get('type') == 'glossary_occurrence_batch_update':
            self.ui_handler.finish_ai_operation()
            self.glossary_handler._handle_occurrence_ai_error(error_message, True)
            return

        if context.get('type') == 'glossary_notes_variation':
            self.ui_handler.finish_ai_operation()
            self._set_notes_dialog_busy(context.get('dialog'), False)
            message = error_message or "AI request failed."
            QMessageBox.warning(self.mw, "AI Glossary Notes", message)
            return

        is_timeout = 'timed out' in error_message.lower()
        context['last_error'] = error_message
        next_attempt = attempt + 1
        context['attempt'] = next_attempt

        if (next_attempt <= max_attempts) and task_type == 'translate_preview':
            if is_timeout:
                message = (
                    f"AI translation timed out after {timeout_seconds or '?'} seconds while processing {mode}."
                    "\n\nWould you like to wait longer and retry?"
                )
                user_choice = QMessageBox.question(
                    self.mw,
                    "AI Translation Timeout",
                    message,
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if user_choice != QMessageBox.Yes:
                    log_debug("User cancelled AI retry after timeout.")
                    self.ui_handler.finish_ai_operation()
                    QMessageBox.information(
                        self.mw,
                        "AI Translation",
                        "Translation cancelled after timeout."
                    )
                    return
                log_debug("Retrying AI translation after user confirmation post-timeout.")
            QTimer.singleShot(0, lambda: self._initiate_batch_translation(context))
            return

        self.ui_handler.finish_ai_operation()
        failure_message = (
            f"Operation failed after {max_attempts} attempts while processing {mode}."
            "\n\n"
            f"Last error: {error_message}"
        )
        QMessageBox.critical(
            self.mw,
            "AI Operation Failed",
            failure_message
        )


    def generate_variation_for_current_string(self):
        if self.is_ai_running:
            QMessageBox.information(self.mw, "AI Busy", "An AI task is already running. Please wait for it to complete.")
            return
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1: return
        original_text = str(self.glossary_handler._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx))
        current_translation, _ = self.data_processor.get_current_string_text(self.mw.current_block_idx, self.mw.current_string_idx)
        if not current_translation:
            QMessageBox.information(self.mw, "AI Variation", "There is no current translation to vary.")
            return
        
        provider = self._prepare_provider()
        if not provider: return

        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            self.ui_handler.finish_ai_operation()
            return
        
        session_state = self._session_manager.get_state()
        composer_args = {
            'system_prompt': system_prompt,
            'source_text': original_text,
            'block_idx': self.mw.current_block_idx, 'string_idx': self.mw.current_string_idx,
            'expected_lines': len(original_text.split('\n')), 'current_translation': str(current_translation),
            'request_type': 'variation_list',
            'session_state': session_state,
        }
        combined_system, user_prompt = self.prompt_composer.compose_variation_request(**composer_args)
        edited = self._maybe_edit_prompt(
            title="AI Variation Prompt",
            system_prompt=combined_system,
            user_prompt=user_prompt,
            save_section='translation',
        )
        if edited is None:
            return
        edited_system, edited_user = edited

        self.ui_handler.start_ai_operation("AI Variation", model_name=self._active_model_name)

        precomposed = [
            {"role": "system", "content": edited_system},
            {"role": "user", "content": edited_user},
        ]
        task_details = {
            'type': 'generate_variation',
            'is_inline': False,
            'composer_args': composer_args,
            'provider_settings_override': {'temperature': 0.7},
            'attempt': 1,
            'max_retries': 1,
        }
        if not self._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt,
            full_system_prompt=edited_system,
            user_prompt=edited_user,
            task_type='generate_variation',
        ):
            task_details['precomposed_prompt'] = precomposed
        
        self._run_ai_task(provider, task_details)

    def _translate_and_apply(self, *, source_text: str, expected_lines: int, mode_description: str, block_idx: int, string_idx: int):
        provider = self._prepare_provider()
        if not provider: return

        system_prompt, _ = self.glossary_handler.load_prompts()
        if not system_prompt:
            return

        session_state = self._session_manager.get_state()
        composer_args = {
            'system_prompt': system_prompt,
            'source_text': source_text,
            'block_idx': block_idx, 'string_idx': string_idx, 'expected_lines': expected_lines,
            'current_translation': None, 'request_type': 'translation',
            'session_state': session_state,
        }
        combined_system, user_prompt = self.prompt_composer.compose_variation_request(**composer_args)
        edited = self._maybe_edit_prompt(
            title="AI Translation Prompt",
            system_prompt=combined_system,
            user_prompt=user_prompt,
            save_section='translation',
        )
        if edited is None:
            return
        edited_system, edited_user = edited

        precomposed = [
            {"role": "system", "content": edited_system},
            {"role": "user", "content": edited_user},
        ]
        task_details = {
            'type': 'translate_single',
            'composer_args': composer_args,
            'attempt': 1,
            'max_retries': 1,
        }
        if not self._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt,
            full_system_prompt=edited_system,
            user_prompt=edited_user,
            task_type='translate_single',
        ):
            task_details['precomposed_prompt'] = precomposed
        self.ui_handler.start_ai_operation("AI Translation", model_name=self._active_model_name)
        self._run_ai_task(provider, task_details)
        
    def _prepare_provider(self, provider_key_override: Optional[str] = None):
        config = getattr(self.mw, 'translation_config', None) or build_default_translation_config()
        provider_key = provider_key_override if provider_key_override is not None else config.get('provider', 'disabled')
        
        if not provider_key or provider_key == 'disabled':
            QMessageBox.information(self.mw, "AI Translation", "The AI provider is disabled in the settings.")
            return None
        
        provider_settings = config.get('providers', {}).get(provider_key, {})
        if not provider_settings:
            QMessageBox.warning(self.mw, "AI Translation", f"No configuration found for provider '{provider_key}'.")
            return None

        try:
            provider = create_translation_provider(provider_key, provider_settings)
            
            if provider_key_override is None:
                self._active_provider_key = provider_key
                self._active_model_name = provider_settings.get('model') if isinstance(provider_settings, dict) else None
                self._provider_supports_sessions = bool(getattr(provider, 'supports_sessions', False))
                if not self._provider_supports_sessions:
                    self._session_manager.reset()

            return provider
        except TranslationProviderError as exc:
            if provider_key_override is None:
                self._provider_supports_sessions = False
            QMessageBox.critical(self.mw, "AI Translation", str(exc))
            return None

    def _log_provider_response(self, response: ProviderResponse, context: dict) -> None:
        full_text = response.text or ''
        log_debug(f"TranslationHandler: provider response id={getattr(response, 'message_id', None)}, FULL_TEXT='{full_text}'")

    def _clean_model_output(self, raw_output: Union[str, ProviderResponse]) -> str:
        text = raw_output.text if isinstance(raw_output, ProviderResponse) else str(raw_output or '')
        if not text:
            return ""
            
        stripped_text = text.strip()
        
        if stripped_text.startswith("```") and stripped_text.endswith("```"):
            lines = stripped_text.splitlines()
            if len(lines) > 1:
                content_lines = lines[1:-1]
                joined_content = "\n".join(content_lines).strip()
                if joined_content.startswith("json"):
                    joined_content = joined_content[4:].strip()
                return joined_content
            else:
                return ""
                
        return text