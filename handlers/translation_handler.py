# --- START OF FILE handlers/translation_handler.py ---

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QMessageBox, QApplication
from .base_handler import BaseHandler
from core.translation.config import build_default_translation_config
from core.translation.providers import (
    ProviderResponse,
    TranslationProviderError,
    create_translation_provider,
)
from core.translation.session_manager import TranslationSessionManager
from .translation.glossary_handler import GlossaryHandler
from .translation.ai_prompt_composer import AIPromptComposer
from .translation.translation_ui_handler import TranslationUIHandler
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

        self.glossary_handler = GlossaryHandler(self)
        self.prompt_composer = AIPromptComposer(self)
        self.ui_handler = TranslationUIHandler(self)

        self._glossary_manager = self.glossary_handler.glossary_manager

        QTimer.singleShot(0, self.glossary_handler.install_menu_actions)
    
    def initialize_glossary_highlighting(self):
        self.glossary_handler.initialize_glossary_highlighting()

    def show_glossary_dialog(self, initial_term: Optional[str] = None) -> None:
        self.glossary_handler.show_glossary_dialog(initial_term)

    def reset_translation_session(self) -> None:
        self._session_manager.reset()
        self._cached_system_prompt = None
        self._cached_glossary = None
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("AI session reset.", 4000)

    def translate_current_string(self):
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            QMessageBox.information(self.mw, "AI Translation", "Select a row to translate.")
            return

        original_text = self.glossary_handler._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx)
        if original_text is None:
            QMessageBox.information(self.mw, "AI Translation", "Original text is not available for this row.")
            return

        self._translate_and_apply(
            source_text=str(original_text),
            expected_lines=len(str(original_text).split("\n")),
            mode_description="current row",
            block_idx=self.mw.current_block_idx,
            string_idx=self.mw.current_string_idx,
        )

    def translate_selected_lines(self):
        selection = self.glossary_handler._resolve_selection_from_original()
        if selection is None:
            return

        block_idx, string_idx, start_line, end_line, selected_lines = selection
        self._translate_segment(
            block_idx=block_idx,
            string_idx=string_idx,
            start_line=start_line,
            end_line=end_line,
            source_lines=selected_lines,
            mode_description=f"lines {start_line + 1}-{end_line + 1}",
            strict_line_check=True,
        )

    def translate_preview_selection(self):
        selection = self.glossary_handler._resolve_selection_from_preview()
        if selection is None:
            return

        block_idx, string_idx, start_line, end_line, selected_lines = selection
        self._translate_segment(
            block_idx=block_idx,
            string_idx=string_idx,
            start_line=start_line,
            end_line=end_line,
            source_lines=selected_lines,
            mode_description=f"lines {start_line + 1}-{end_line + 1} (preview)",
            strict_line_check=True,
        )

    def translate_current_block(self, block_idx: Optional[int] = None):
        target_block = block_idx if block_idx is not None else self.mw.current_block_idx
        if target_block is None or target_block == -1:
            QMessageBox.information(self.mw, "AI Translation", "Select a block to translate.")
            return

        block_strings = self.glossary_handler._get_original_block(target_block)
        if not block_strings:
            QMessageBox.information(self.mw, "AI Translation", "There are no rows to translate in this block.")
            return

        provider = self._prepare_provider()
        if not provider:
            return
        system_prompt, glossary = self.glossary_handler.load_prompts()
        if not system_prompt:
            return

        block_name = self.mw.block_names.get(str(target_block), f"Block {target_block}")
        block_translations: Dict[int, str] = {}

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            total_strings = len(block_strings)
            for idx, original_text in enumerate(block_strings):
                source_text = str(original_text)
                if not source_text.strip():
                    continue

                expected_lines = len(source_text.split("\n"))
                combined_system, user_content = self.prompt_composer.compose_messages(
                    system_prompt,
                    glossary,
                    source_text,
                    block_idx=target_block,
                    string_idx=idx,
                    expected_lines=expected_lines,
                    mode_description=f"block {block_name}, row {idx + 1} of {total_strings}",
                )

                if self.mw.statusBar:
                    self.mw.statusBar.showMessage(f"AI translation: row {idx + 1} / {total_strings} ({block_name})", 0)
                QApplication.processEvents()

                try:
                    raw_translation = provider.translate(messages=[{"role": "system", "content": combined_system}, {"role": "user", "content": user_content}])
                except TranslationProviderError as exc:
                    QMessageBox.critical(self.mw, "AI Translation", f"Error translating row {idx + 1}: {exc}")
                    return

                cleaned = self._clean_model_output(raw_translation)
                if not self.ui_handler.confirm_line_count(expected_lines, cleaned, strict=False, mode_label=f"row {idx + 1}"):
                    return

                block_translations[idx] = cleaned
        finally:
            QApplication.restoreOverrideCursor()
            if self.mw.statusBar:
                self.mw.statusBar.clearMessage()

        if not block_translations:
            QMessageBox.information(self.mw, "AI Translation", "No translation was created: all rows are empty.")
            return

        for string_idx, translated_text in block_translations.items():
            self.data_processor.update_edited_data(target_block, string_idx, translated_text)

        self.ui_updater.populate_strings_for_block(target_block)
        if self.mw.current_block_idx == target_block and self.mw.current_string_idx != -1:
            self.mw.ui_updater.update_text_views()
        if hasattr(self.mw, 'app_action_handler'):
            self.mw.app_action_handler.rescan_issues_for_single_block(target_block, show_message_on_completion=False)
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("AI translation completed for the entire block.", 5000)

    def generate_variation_for_current_string(self):
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            QMessageBox.information(self.mw, "AI Translation", "Select a row to generate a translation variation.")
            return

        original_text = self.glossary_handler._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx)
        if original_text is None:
            QMessageBox.information(self.mw, "AI Translation", "Original text is not available for this row.")
            return

        current_translation, _ = self.data_processor.get_current_string_text(self.mw.current_block_idx, self.mw.current_string_idx)
        if current_translation is None or not str(current_translation).strip():
            QMessageBox.information(self.mw, "AI Translation", "There is no current translation to vary.")
            return

        expected_lines = len(str(original_text).split("\n"))
        variations = self._request_variation_candidates(
            source_text=str(original_text),
            current_translation=str(current_translation),
            expected_lines=expected_lines,
        )

        if not variations:
            QMessageBox.information(self.mw, "AI Translation", "Failed to obtain translation variations.")
            self.ui_handler.clear_status_message()
            return

        chosen_variation = self.ui_handler.show_variations_dialog(variations)
        if chosen_variation:
            self.ui_handler.apply_full_translation(chosen_variation)
            if self.mw.statusBar:
                self.mw.statusBar.showMessage("AI variation applied.", 5000)
        else:
            self.ui_handler.clear_status_message()
    
    def generate_variation_for_selection(self):
        editor = getattr(self.mw, 'edited_text_edit', None)
        if not editor or not editor.textCursor().hasSelection():
            QMessageBox.information(self.mw, "AI Translation", "Select a fragment of text to generate variations.")
            return

        selected_text = editor.textCursor().selectedText()
        full_text = editor.toPlainText()

        variations = self._request_inline_variation_candidates(
            full_text_context=full_text,
            selected_text_to_vary=selected_text,
        )

        if not variations:
            QMessageBox.information(self.mw, "AI Translation", "Failed to obtain translation variations for the selection.")
            self.ui_handler.clear_status_message()
            return
        
        chosen_variation = self.ui_handler.show_variations_dialog(variations)
        if chosen_variation:
            self.ui_handler.apply_inline_variation(chosen_variation)
            if self.mw.statusBar:
                self.mw.statusBar.showMessage("AI variation applied to selection.", 5000)
        else:
            self.ui_handler.clear_status_message()

    def _translate_and_apply(
        self, *, source_text: str, expected_lines: int, mode_description: str,
        block_idx: int, string_idx: int, request_type: str = "translation",
        current_translation: Optional[str] = None,
    ) -> None:
        provider = self._prepare_provider()
        if not provider: return

        system_prompt, glossary = self.glossary_handler.load_prompts()
        if not system_prompt: return

        glossary_entries = self._glossary_manager.get_entries_sorted_by_length()
        prepared_source_text, placeholder_map = self.prompt_composer.prepare_text_for_translation(source_text, glossary_entries)
        
        combined_system, user_content = self.prompt_composer.compose_messages(
            system_prompt, glossary, prepared_source_text,
            block_idx=block_idx, string_idx=string_idx, expected_lines=expected_lines,
            mode_description=mode_description, request_type=request_type,
            current_translation=current_translation, placeholder_tokens=list(placeholder_map.keys()),
        )

        log_debug(f"AI translate ({request_type}) block={block_idx}, string={string_idx}, mode={mode_description}")
        
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            response = self._send_provider_request(
                provider, combined_system, user_content,
                request_label=f"{mode_description}: request",
                placeholder_count=len(placeholder_map), expected_lines=expected_lines,
            )
            if response is None:
                self.ui_handler.clear_status_message()
                return
        finally:
            QApplication.restoreOverrideCursor()

        cleaned_translation = self._clean_model_output(response)
        restored_translation = self.prompt_composer.restore_placeholders(cleaned_translation, placeholder_map)
        
        if not self.ui_handler.confirm_line_count(expected_lines, restored_translation, strict=False, mode_label=mode_description):
            return

        normalized_translation = self.ui_handler.normalize_line_count(restored_translation, expected_lines, mode_description)
        self.ui_handler.apply_full_translation(normalized_translation)
        
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("AI translation applied.", 4000)

    def _request_variation_candidates(
        self, *, source_text: str, current_translation: str, expected_lines: int,
    ) -> List[str]:
        provider = self._prepare_provider()
        if not provider: return []

        system_prompt, glossary = self.glossary_handler.load_prompts()
        if not system_prompt: return []

        glossary_entries = self._glossary_manager.get_entries_sorted_by_length()
        prepared_source_text, placeholder_map = self.prompt_composer.prepare_text_for_translation(source_text, glossary_entries)
        
        combined_system, user_content = self.prompt_composer.compose_messages(
            system_prompt, glossary, prepared_source_text,
            block_idx=self.mw.current_block_idx, string_idx=self.mw.current_string_idx,
            expected_lines=expected_lines, mode_description="translation variations",
            request_type="variation_list", current_translation=current_translation,
            placeholder_tokens=list(placeholder_map.keys()),
        )

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            response = self._send_provider_request(
                provider, combined_system, user_content,
                request_label="variation generation", placeholder_count=len(placeholder_map),
                expected_lines=expected_lines,
            )
            if response is None:
                self.ui_handler.clear_status_message()
                return []
        finally:
            QApplication.restoreOverrideCursor()

        cleaned = self._clean_model_output(response)
        variants_raw = self.ui_handler.parse_variation_payload(cleaned)
        
        if not variants_raw:
            log_debug(f"TranslationHandler: AI returned no valid variations. Response: {cleaned[:self._MAX_LOG_EXCERPT]}")
            return []

        restored_variants = [self.prompt_composer.restore_placeholders(v, placeholder_map) for v in variants_raw]
        return [v for v in restored_variants if len(v.split('\n')) == expected_lines]

    def _request_inline_variation_candidates(self, *, full_text_context: str, selected_text_to_vary: str) -> List[str]:
        provider = self._prepare_provider()
        if not provider: return []

        system_prompt, glossary = self.glossary_handler.load_prompts()
        if not system_prompt: return []
        
        combined_system, user_content = self.prompt_composer.compose_messages(
            system_prompt, glossary, full_text_context,
            block_idx=self.mw.current_block_idx, string_idx=self.mw.current_string_idx,
            expected_lines=1,
            mode_description="inline variation",
            request_type="inline_variation",
            selected_text_to_vary=selected_text_to_vary
        )

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            response = self._send_provider_request(
                provider, combined_system, user_content,
                request_label="inline variation generation", placeholder_count=0,
                expected_lines=1
            )
            if response is None:
                self.ui_handler.clear_status_message()
                return []
        finally:
            QApplication.restoreOverrideCursor()

        cleaned = self._clean_model_output(response)
        return self.ui_handler.parse_variation_payload(cleaned)

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
            supports_sessions = getattr(provider, 'supports_sessions', False)
            session_mode = config.get('session_mode', 'auto') if supports_sessions else 'static'
            
            if self._active_provider_key != provider_key or self._session_mode != session_mode:
                self._session_manager.reset()

            self._provider_supports_sessions = supports_sessions
            self._session_mode = session_mode
            self._active_provider_key = provider_key
            return provider
        except TranslationProviderError as exc:
            QMessageBox.critical(self.mw, "AI Translation", str(exc))
            return None

    def _log_provider_response(self, response: ProviderResponse, placeholder_count: int, expected_lines: int) -> None:
        text_excerpt = (response.text or '')[: self._MAX_LOG_EXCERPT]
        log_debug(f"TranslationHandler: provider response id={getattr(response, 'message_id', None)}, placeholders={placeholder_count}, expected_lines={expected_lines}, text='{text_excerpt}'")

    def _send_provider_request(
        self, provider, combined_system: str, user_content: str, *,
        request_label: str, placeholder_count: int, expected_lines: int,
    ):
        session_prep = self._prepare_session_and_messages(combined_system, user_content)
        if session_prep is None:
            return None
        messages, session_payload, state = session_prep

        self.ui_handler.show_progress_indicator(f"Sending request ({request_label})...")
        QApplication.processEvents()

        try:
            response = provider.translate(messages, session=session_payload)

            self.ui_handler.update_status_message("AI: response received, processing...")
            QApplication.processEvents()
            
            if isinstance(response, ProviderResponse):
                self._log_provider_response(response, placeholder_count, expected_lines)
                if state:
                    state.record_exchange(
                        user_content=user_content, assistant_content=response.text or '',
                        conversation_id=response.conversation_id,
                    )
            return response
        except TranslationProviderError as e:
            QMessageBox.critical(self.mw, "AI Translation Error", str(e))
            return None
        finally:
            self.ui_handler.hide_progress_indicator()
    
    def _prepare_session_and_messages(self, combined_system, user_content):
        messages: List[Dict[str, str]] = []
        session_payload = None
        state = None
        can_use_sessions = self._provider_supports_sessions and self._session_mode != 'static' and self._active_provider_key

        if can_use_sessions:
            state = self._session_manager.ensure_session(self._active_provider_key, combined_system, True)
            if not state.bootstrap_viewed:
                instructions = self.ui_handler.prompt_session_bootstrap(combined_system)
                if instructions is None:
                    self.ui_handler.update_status_message('AI: сесію скасовано користувачем', persistent=False)
                    return None
                state.set_instructions(instructions)
            
            user_content = self.ui_handler.merge_session_instructions(state.session_instructions, user_content)
            messages, session_payload = state.prepare_request({"role": "user", "content": user_content})
        else:
            messages = [{"role": "system", "content": combined_system}, {"role": "user", "content": user_content}]
        
        return messages, session_payload, state

    def _clean_model_output(self, raw_output: Union[str, ProviderResponse]) -> str:
        text = raw_output.text if isinstance(raw_output, ProviderResponse) else str(raw_output or '')
        stripped_text = text.strip()
        
        if stripped_text.startswith("```") and stripped_text.endswith("```"):
            lines = stripped_text.splitlines()
            if len(lines) > 1:
                content_lines = lines[1:-1]
                return "\n".join(content_lines)
            else:
                return ""
                
        return text

    def _translate_segment(
        self, *, block_idx: int, string_idx: int, start_line: int, end_line: int,
        source_lines: List[str], mode_description: str, strict_line_check: bool,
    ) -> None:
        provider = self._prepare_provider()
        if not provider: return

        system_prompt, glossary = self.glossary_handler.load_prompts()
        if not system_prompt: return

        expected_lines = len(source_lines)
        combined_system, user_content = self.prompt_composer.compose_messages(
            system_prompt, glossary, "\n".join(source_lines),
            block_idx=block_idx, string_idx=string_idx,
            expected_lines=expected_lines, mode_description=mode_description,
        )

        response = self._send_provider_request(
            provider, combined_system, user_content,
            request_label=f"{mode_description}: request",
            placeholder_count=0, expected_lines=expected_lines,
        )
        if response is None:
            self.ui_handler.clear_status_message()
            return
        
        cleaned_translation = self._clean_model_output(response)
        if not self.ui_handler.confirm_line_count(expected_lines, cleaned_translation, strict=strict_line_check, mode_label=mode_description):
            return

        self.ui_handler.apply_partial_translation(cleaned_translation, start_line, end_line)
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("AI translation applied to the selected rows.", 4000)