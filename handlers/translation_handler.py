# --- START OF FILE handlers/translation_handler.py ---
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
)
from core.translation.session_manager import TranslationSessionManager
from .translation.glossary_handler import GlossaryHandler
from .translation.ai_prompt_composer import AIPromptComposer
from .translation.translation_ui_handler import TranslationUIHandler
from .translation.ai_worker import AIWorker
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
        self.translation_progress: Dict[int, Dict[str, Union[set, int]]] = {}
        self.pre_translation_state: Dict[int, List[str]] = {}

        self.glossary_handler = GlossaryHandler(self)
        self.prompt_composer = AIPromptComposer(self)
        self.ui_handler = TranslationUIHandler(self)

        self._glossary_manager = self.glossary_handler.glossary_manager

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

    def reset_translation_session(self) -> None:
        self._session_manager.reset()
        self._cached_system_prompt = None
        self._cached_glossary = None
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("AI session reset.", 4000)

    def _trim_trailing_whitespace_from_lines(self, text: str) -> str:
        if not text:
            return ""
        lines = text.split('\n')
        cleaned_lines = [line.rstrip() for line in lines]
        return '\n'.join(cleaned_lines)
    
    def _run_ai_task(self, provider: BaseTranslationProvider, task_details: dict):
        self.thread = QThread()
        task_details['dialog_steps'] = self.ui_handler.status_dialog.steps
        self.worker = AIWorker(provider, self.prompt_composer, task_details)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.step_updated.connect(self.ui_handler.update_ai_operation_step)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

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

        self.worker.error.connect(self._handle_ai_error)

        self.thread.start()

    def _handle_translation_cancellation(self):
        self.ui_handler.finish_ai_operation()
        block_idx = self.worker.task_details.get('block_idx')
        if block_idx is None:
            return

        reply = QMessageBox.question(
            self.mw,
            "Translation Cancelled",
            "Revert all changes made during this translation session?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
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
            # If user wants to keep progress, just clear the pre-translation state
            if block_idx in self.pre_translation_state:
                del self.pre_translation_state[block_idx]

    def _setup_progress_bar(self, total_chunks: int, completed_chunks: int):
        block_idx = self.worker.task_details.get('block_idx')
        if block_idx is not None and block_idx in self.translation_progress:
            self.translation_progress[block_idx]['total_chunks'] = total_chunks
        
        self.translated_chunks_count = completed_chunks
        self.ui_handler.status_dialog.setup_progress_bar(total_chunks, completed_chunks)

    def translate_current_string(self):
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1: return
        self._translate_and_apply(
            source_text=str(self.glossary_handler._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx)),
            expected_lines=len(str(self.glossary_handler._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx)).split("\n")),
            mode_description="current row",
            block_idx=self.mw.current_block_idx,
            string_idx=self.mw.current_string_idx
        )

    def translate_preview_selection(self, context_menu_pos: QPoint):
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

        base_timeout = self._resolve_base_timeout(provider)
        operation_title = f"AI Translation (Lines {start_line + 1}-{end_line + 1})" if start_line != end_line else f"AI Translation (Line {start_line + 1})"
        self.ui_handler.start_ai_operation(operation_title)

        task_details = {
            'type': 'translate_preview',
            'provider': provider,
            'source_items': source_items,
            'attempt': 1,
            'max_retries': 4,
            'block_idx': block_idx,
            'mode_description': f"lines {start_line + 1}-{end_line + 1}",
            'timeout_seconds': base_timeout
        }
        self._initiate_batch_translation(task_details)

    def translate_current_block(self, block_idx: Optional[int] = None) -> None:
        target_block_idx = self.mw.current_block_idx if block_idx is None else block_idx
        if target_block_idx is None or target_block_idx == -1:
            QMessageBox.information(self.mw, "AI Translation", "Select a block to translate.")
            return

        data_source = getattr(self.mw, 'data', None)
        if not isinstance(data_source, list) or not (0 <= target_block_idx < len(data_source)):
            QMessageBox.information(self.mw, "AI Translation", "No block data available to translate.")
            return

        block_strings = self.glossary_handler._get_original_block(target_block_idx)
        if not block_strings:
            QMessageBox.information(self.mw, "AI Translation", "The selected block is empty.")
            return

        # Save pre-translation state for potential revert
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
        self.ui_handler.start_ai_operation(operation_title)

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
        self.ui_handler.start_ai_operation(operation_title)

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
                self.translation_progress[block_idx] = {'completed_chunks': set(), 'total_chunks': 0}
            
            context['chunks_to_skip'] = self.translation_progress[block_idx]['completed_chunks']

        system_prompt, glossary = self.glossary_handler.load_prompts()
        if not system_prompt:
            self.ui_handler.finish_ai_operation()
            return
        
        context['composer_args'] = {
            'system_prompt': system_prompt, 'glossary_text': glossary,
            'source_items': context['source_items'], 'block_idx': context['block_idx'],
            'mode_description': context['mode_description'], 'is_retry': (context['attempt'] > 1),
            'retry_reason': context.get('last_error', '')
        }
        self._run_ai_task(provider, context)

    def _handle_chunk_translated(self, chunk_index: int, chunk_text: str, context: dict):
        try:
            block_idx = context['block_idx']
            parsed_json = json.loads(chunk_text)
            translated_strings = parsed_json.get("translated_strings")
            if not isinstance(translated_strings, list):
                raise ValueError("Invalid response structure: 'translated_strings' is not a list.")

            for item in translated_strings:
                string_idx, translated_text = item["id"], item["translation"]
                restored_text = self.prompt_composer.restore_placeholders(translated_text, context['placeholder_map'])
                final_text = self._trim_trailing_whitespace_from_lines(restored_text)
                self.data_processor.update_edited_data(block_idx, string_idx, final_text)
            
            # Update progress
            if block_idx in self.translation_progress:
                self.translation_progress[block_idx]['completed_chunks'].add(chunk_index)

            self.translated_chunks_count += 1
            self.ui_handler.status_dialog.update_progress(self.translated_chunks_count)
            
            total_chunks = self.translation_progress.get(block_idx, {}).get('total_chunks', -1)
            if self.translated_chunks_count == total_chunks:
                self.ui_handler.finish_ai_operation()
                self.ui_updater.populate_strings_for_block(block_idx)
                self.ui_updater.update_text_views()
                if hasattr(self.mw, 'app_action_handler'):
                    self.mw.app_action_handler.rescan_issues_for_single_block(block_idx, show_message_on_completion=False)
                
                # Clean up progress on completion
                if block_idx in self.translation_progress:
                    del self.translation_progress[block_idx]

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
                restored_text = self.prompt_composer.restore_placeholders(translated_text, context['placeholder_map'])
                final_text = self._trim_trailing_whitespace_from_lines(restored_text)
                self.data_processor.update_edited_data(context['block_idx'], string_idx, final_text)

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
        restored_translation = self.prompt_composer.restore_placeholders(cleaned_translation, context['placeholder_map'])
        trimmed_translation = self._trim_trailing_whitespace_from_lines(restored_translation)
        
        self.ui_handler.update_ai_operation_step(4, self.ui_handler.status_dialog.steps[4], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        self.ui_handler.apply_full_translation(trimmed_translation)
        self.ui_handler.finish_ai_operation()

    def _handle_variation_success(self, response: ProviderResponse, context: dict):
        self.ui_handler.update_ai_operation_step(3, self.ui_handler.status_dialog.steps[3], self.ui_handler.status_dialog.STATUS_IN_PROGRESS)
        cleaned = self._clean_model_output(response)
        variants_raw = self.ui_handler.parse_variation_payload(cleaned)
        self.ui_handler.finish_ai_operation()

        if not variants_raw:
            QMessageBox.information(self.mw, "AI Variation", "Failed to parse variations from AI response.")
            return
            
        restored = [self.prompt_composer.restore_placeholders(v, context['placeholder_map']) for v in variants_raw]
        trimmed = [self._trim_trailing_whitespace_from_lines(v) for v in restored]
        
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
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1: return
        original_text = str(self.glossary_handler._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx))
        current_translation, _ = self.data_processor.get_current_string_text(self.mw.current_block_idx, self.mw.current_string_idx)
        if not current_translation:
            QMessageBox.information(self.mw, "AI Variation", "There is no current translation to vary.")
            return
        
        provider = self._prepare_provider()
        if not provider: return

        system_prompt, glossary = self.glossary_handler.load_prompts()
        if not system_prompt:
            self.ui_handler.finish_ai_operation()
            return
        
        self.ui_handler.start_ai_operation("AI Variation")

        glossary_entries = self._glossary_manager.get_entries_sorted_by_length()
        prepared_text, placeholder_map = self.prompt_composer.prepare_text_for_translation(
            original_text, glossary_entries
        )
        
        composer_args = {
            'system_prompt': system_prompt, 'glossary_text': glossary,
            'source_text': prepared_text,
            'placeholder_map': placeholder_map,
            'block_idx': self.mw.current_block_idx, 'string_idx': self.mw.current_string_idx,
            'expected_lines': len(original_text.split('\n')), 'current_translation': str(current_translation),
            'request_type': 'variation_list'
        }
        task_details = {'type': 'generate_variation', 'is_inline': False, 'composer_args': composer_args, 'provider_settings_override': {'temperature': 0.7}, 'attempt': 1, 'max_retries': 1}
        self._run_ai_task(provider, task_details)

    def _translate_and_apply(self, *, source_text: str, expected_lines: int, mode_description: str, block_idx: int, string_idx: int):
        provider = self._prepare_provider()
        if not provider: return

        system_prompt, glossary = self.glossary_handler.load_prompts()
        if not system_prompt:
            return

        self.ui_handler.start_ai_operation("AI Translation")
        
        glossary_entries = self._glossary_manager.get_entries_sorted_by_length()
        prepared_text, placeholder_map = self.prompt_composer.prepare_text_for_translation(
            source_text, glossary_entries
        )

        composer_args = {
            'system_prompt': system_prompt, 'glossary_text': glossary,
            'source_text': prepared_text,
            'placeholder_map': placeholder_map,
            'block_idx': block_idx, 'string_idx': string_idx, 'expected_lines': expected_lines,
            'current_translation': None, 'request_type': 'translation'
        }
        task_details = {'type': 'translate_single', 'composer_args': composer_args, 'attempt': 1, 'max_retries': 1}
        self._run_ai_task(provider, task_details)
        
    def _prepare_provider(self):
        config = getattr(self.mw, 'translation_config', None) or build_default_translation_config()
        provider_key = config.get('provider', 'disabled')
        if not provider_key or provider_key == 'disabled':
            QMessageBox.information(self.mw, "AI Translation", "The AI provider is disabled in the settings.")
            return None
        
        provider_settings = config.get('providers', {}).get(provider_key, {})
        if not provider_settings:
            QMessageBox.warning(self.mw, "AI Translation", f"No configuration found for provider '{provider_key}'.")
            return None

        try:
            provider = create_translation_provider(provider_key, provider_settings)
            self._active_provider_key = provider_key
            return provider
        except TranslationProviderError as exc:
            QMessageBox.critical(self.mw, "AI Translation", str(exc))
            return None

    def _log_provider_response(self, response: ProviderResponse, context: dict) -> None:
        full_text = response.text or ''
        log_debug(f"TranslationHandler: provider response id={getattr(response, 'message_id', None)}, FULL_TEXT='{full_text}'")

    def _clean_model_output(self, raw_output: Union[str, ProviderResponse]) -> str:
        text = raw_output.text if isinstance(raw_output, ProviderResponse) else str(raw_output or '')
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
