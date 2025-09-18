import json
import os
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

from PyQt5.QtCore import Qt, QTimer, QObject, QEvent
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from handlers.base_handler import BaseHandler
from core.translation.config import build_default_translation_config
from core.translation.providers import (
    ProviderResponse,
    TranslationProviderError,
    create_translation_provider,
)
from core.translation.session_manager import TranslationSessionManager
from core.glossary_manager import GlossaryEntry, GlossaryManager, GlossaryOccurrence
from components.translation_variations_dialog import TranslationVariationsDialog
from components.glossary_dialog import GlossaryDialog
from utils.logging_utils import log_debug
from utils.utils import ALL_TAGS_PATTERN, convert_spaces_to_dots_for_display


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

    def eventFilter(self, obj, event):  # type: ignore[override]
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            modifiers = event.modifiers()
            if not (modifiers & (Qt.ShiftModifier | Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
                self._dialog.accept()
                return True
        return super().eventFilter(obj, event)


class TranslationHandler(BaseHandler):
    _TAG_PLACEHOLDER_PREFIX = "__TAG_"
    _GLOSS_PLACEHOLDER_PREFIX = "__GLOS_"
    _PLACEHOLDER_SUFFIX = "__"
    _MAX_LOG_EXCERPT = 160

    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self._cached_system_prompt: Optional[str] = None
        self._cached_glossary: Optional[str] = None
        self._session_manager = TranslationSessionManager()
        self._active_provider_key: Optional[str] = None
        self._progress_dialog: Optional[QProgressDialog] = None
        self._reset_session_action: Optional[QAction] = None
        self._open_glossary_action: Optional[QAction] = None
        self._glossary_manager = GlossaryManager()
        self._current_glossary_path: Optional[Path] = None
        self._current_plugin_name: Optional[str] = None
        self._cached_glossary_prompt_template: Optional[str] = None
        self._cached_glossary_prompt_plugin: Optional[str] = None

        QTimer.singleShot(0, self._install_menu_actions)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def translate_current_string(self):
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            QMessageBox.information(self.mw, "AI Translation", "Select a row to translate.")
            return

        original_text = self._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx)
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
        selection = self._resolve_selection_from_original()
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
        selection = self._resolve_selection_from_preview()
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

        block_strings = self._get_original_block(target_block)
        if not block_strings:
            QMessageBox.information(self.mw, "AI Translation", "There are no rows to translate in this block.")
            return

        provider = self._prepare_provider()
        if not provider:
            return
        system_prompt, glossary = self._load_prompts()
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
                messages = self._compose_messages(
                    system_prompt,
                    glossary,
                    source_text,
                    block_idx=target_block,
                    string_idx=idx,
                    expected_lines=expected_lines,
                    mode_description=f"block {block_name}, row {idx + 1} of {total_strings}",
                )

                if self.mw.statusBar:
                    self.mw.statusBar.showMessage(
                        f"AI translation: row {idx + 1} / {total_strings} ({block_name})",
                        0,
                    )
                QApplication.processEvents()

                try:
                    raw_translation = provider.translate(messages)
                except TranslationProviderError as exc:
                    QMessageBox.critical(
                        self.mw,
                        "AI Translation",
                        f"Error translating row {idx + 1}: {exc}",
                    )
                    return

                cleaned = self._clean_model_output(raw_translation)
                if not self._confirm_line_count(
                    expected_lines,
                    cleaned,
                    strict=False,
                    mode_label=f"row {idx + 1}",
                ):
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

        original_text = self._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx)
        if original_text is None:
            QMessageBox.information(self.mw, "AI Translation", "Original text is not available for this row.")
            return

        current_translation, _ = self.data_processor.get_current_string_text(
            self.mw.current_block_idx,
            self.mw.current_string_idx,
        )
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
            QMessageBox.information(
                self.mw,
                "AI Translation",
                "Failed to obtain translation variations.",
            )
            self._clear_status_message()
            return

        self._update_status_message("AI: choose one of the suggested options", persistent=False)
        dialog = TranslationVariationsDialog(self.mw, variations)
        if dialog.exec_() == dialog.Accepted:
            chosen = dialog.selected_translation
            if chosen:
                self._apply_full_translation(chosen)
                if self.mw.statusBar:
                    self.mw.statusBar.showMessage("AI variation applied.", 5000)
        else:
            self._clear_status_message()

    def show_glossary_dialog(self, initial_term: Optional[str] = None) -> None:
        system_prompt, glossary_text = self._load_prompts()
        if system_prompt is None:
            return

        if not self._glossary_manager.get_entries():
            QMessageBox.information(
                self.mw,
                "Glossary",
                "Glossary is empty or not loaded.",
            )
            return

        data_source = getattr(self.mw, 'data', None)
        if not isinstance(data_source, list):
            QMessageBox.information(self.mw, "Glossary", "No data is loaded for analysis.")
            return

        occurrence_map = self._glossary_manager.build_occurrence_index(data_source)
        entries = sorted(
            self._glossary_manager.get_entries(),
            key=lambda item: item.original.lower(),
        )
        dialog = GlossaryDialog(
            parent=self.mw,
            entries=entries,
            occurrence_map=occurrence_map,
            jump_callback=self._jump_to_occurrence,
            update_callback=self._handle_glossary_entry_update,
            delete_callback=self._handle_glossary_entry_delete,
            initial_term=initial_term,
        )
        dialog.exec_()

    def reset_translation_session(self) -> None:
        self._session_manager.reset()
        self._cached_system_prompt = None
        self._cached_glossary = None
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("AI session reset.", 4000)

    def _jump_to_occurrence(self, occurrence: GlossaryOccurrence) -> None:
        if occurrence is None:
            return
        entry = {
            'block_idx': occurrence.block_idx,
            'string_idx': occurrence.string_idx,
            'line_idx': occurrence.line_idx,
        }
        self._activate_entry(entry)
        if self.mw.statusBar:
            self.mw.statusBar.showMessage(
                f"Navigated to glossary term: {occurrence.entry.original}",
                4000,
            )

    def _install_menu_actions(self) -> None:
        tools_menu = getattr(self.mw, 'tools_menu', None)
        if not tools_menu:
            return

        if self._open_glossary_action is None:
            glossary_action = QAction('Open Glossary...', self.mw)
            glossary_action.setToolTip('Open glossary and jump to occurrences')
            glossary_action.triggered.connect(self.show_glossary_dialog)
            tools_menu.addAction(glossary_action)
            self._open_glossary_action = glossary_action

        if self._reset_session_action is None:
            reset_action = QAction('AI Reset Translation Session', self.mw)
            reset_action.setToolTip('Reset the current AI translation session')
            reset_action.triggered.connect(self.reset_translation_session)
            tools_menu.addAction(reset_action)
            self._reset_session_action = reset_action

    def generate_block_glossary(self, block_idx: Optional[int] = None):
        target_block = block_idx if block_idx is not None else self.mw.current_block_idx
        if target_block is None or target_block == -1:
            QMessageBox.information(self.mw, "AI Translation", "Select a block to build a glossary.")
            return

        block_strings = self._get_original_block(target_block)
        if not block_strings:
            QMessageBox.information(self.mw, "AI Translation", "There is no data in the block for glossary generation.")
            return

        glossary_rows = self._request_glossary_rows(
            source_lines=block_strings,
            context_label=f"Block #{target_block}",
        )
        if glossary_rows:
            block_name = self.mw.block_names.get(str(target_block), f"Block {target_block}")
            self._append_to_glossary(
                section_title=f"Block {block_name} (#{target_block})",
                table_rows=glossary_rows,
            )

    def append_selection_to_glossary(self, block_idx: Optional[int] = None):
        selection = self._resolve_selection_from_preview()
        if selection is None:
            QMessageBox.information(self.mw, "AI Translation", "Select at least one line in the preview.")
            return

        sel_block_idx, sel_string_idx, start_line, end_line, selected_lines = selection
        if block_idx is not None and block_idx != sel_block_idx:
            QMessageBox.warning(self.mw, "AI Translation", "The selection does not belong to the selected block.")
            return

        glossary_rows = self._request_glossary_rows(
            source_lines=selected_lines,
            context_label=(
                f"Lines {start_line + 1}-{end_line + 1} of row #{sel_string_idx} "
                f"in block #{sel_block_idx}"
            ),
        )
        if glossary_rows:
            block_name = self.mw.block_names.get(str(sel_block_idx), f"Block {sel_block_idx}")
            self._append_to_glossary(
                section_title=(
                    f"Selection from block {block_name} (#{sel_block_idx}), row {sel_string_idx}, "
                    f"lines {start_line + 1}-{end_line + 1}"
                ),
                table_rows=glossary_rows,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _translate_and_apply(
        self,
        *,
        source_text: str,
        expected_lines: int,
        mode_description: str,
        block_idx: int,
        string_idx: int,
        request_type: str = "translation",
        current_translation: Optional[str] = None,
    ) -> None:
        provider = self._prepare_provider()
        if not provider:
            return

        system_prompt, glossary = self._load_prompts()
        if not system_prompt:
            return

        glossary_entries = self._glossary_manager.get_entries_sorted_by_length()
        prepared_source_text, placeholder_map = self._prepare_text_for_translation(
            source_text,
            glossary_entries,
        )
        placeholder_tokens = list(placeholder_map.keys())

        combined_system, user_content = self._compose_messages(
            system_prompt,
            glossary,
            prepared_source_text,
            block_idx=block_idx,
            string_idx=string_idx,
            expected_lines=expected_lines,
            mode_description=mode_description,
            request_type=request_type,
            current_translation=current_translation,
            placeholder_tokens=placeholder_tokens,
        )

        log_debug(
            f"AI translate ({request_type}) block={block_idx}, string={string_idx}, mode={mode_description}"
        )
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            response = self._send_provider_request(
                provider,
                combined_system,
                user_content,
                request_label=f"{mode_description}: request",
                placeholder_count=len(placeholder_map),
                expected_lines=expected_lines,
            )
        except TranslationProviderError as exc:
            QMessageBox.critical(self.mw, "AI Translation", str(exc))
            self._clear_status_message()
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.mw, "AI Translation", f"Unexpected error: {exc}")
            self._clear_status_message()
            return
        finally:
            QApplication.restoreOverrideCursor()

        cleaned_translation = self._clean_model_output(response)
        restored_translation = self._restore_placeholders(
            cleaned_translation,
            placeholder_map,
        )
        if not self._confirm_line_count(
            expected_lines,
            restored_translation,
            strict=False,
            mode_label=mode_description,
        ):
            return

        normalized_translation = self._normalize_line_count(
            restored_translation,
            expected_lines,
            mode_description,
        )
        self._apply_full_translation(normalized_translation)
        if self.mw.statusBar:
            self.mw.statusBar.showMessage(
                "AI translation applied.",
                4000,
            )

    def _request_variation_candidates(
        self,
        *,
        source_text: str,
        current_translation: str,
        expected_lines: int,
    ) -> List[str]:
        provider = self._prepare_provider()
        if not provider:
            return []

        system_prompt, glossary = self._load_prompts()
        if not system_prompt:
            return []

        glossary_entries = self._glossary_manager.get_entries_sorted_by_length()
        prepared_source_text, placeholder_map = self._prepare_text_for_translation(
            source_text,
            glossary_entries,
        )
        combined_system, user_content = self._compose_messages(
            system_prompt,
            glossary,
            prepared_source_text,
            block_idx=self.mw.current_block_idx,
            string_idx=self.mw.current_string_idx,
            expected_lines=expected_lines,
            mode_description="translation variations",
            request_type="variation_list",
            current_translation=current_translation,
            placeholder_tokens=list(placeholder_map.keys()),
        )

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            response = self._send_provider_request(
                provider,
                combined_system,
                user_content,
                request_label="variation generation",
                placeholder_count=len(placeholder_map),
                expected_lines=expected_lines,
            )
        except TranslationProviderError as exc:
            QMessageBox.critical(self.mw, "AI Translation", str(exc))
            self._clear_status_message()
            return []
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.mw, "AI Translation", f"Unexpected error: {exc}")
            self._clear_status_message()
            return []
        finally:
            QApplication.restoreOverrideCursor()

        cleaned = self._clean_model_output(response)
        variants_raw = self._parse_variation_payload(cleaned)
        if not variants_raw:
            log_debug(
                f"TranslationHandler: AI returned no valid variations. Response: {cleaned[:self._MAX_LOG_EXCERPT]}"
            )
            return []

        restored_variants: List[str] = []
        for idx, variant in enumerate(variants_raw):
            restored = self._restore_placeholders(variant, placeholder_map)
            lines = restored.split('\n') if restored else []
            if len(lines) != expected_lines:
                log_debug(
                    f"TranslationHandler: variation #{idx + 1} has {len(lines)} lines instead of {expected_lines}, skipping."
                )
                continue
            restored_variants.append(restored)

        deduped: List[str] = []
        seen: set = set()
        for variant in restored_variants:
            if variant not in seen:
                deduped.append(variant)
                seen.add(variant)

        restored_variants = deduped

        if len(restored_variants) > 10:
            restored_variants = restored_variants[:10]

        return restored_variants

    def _prepare_text_for_translation(
        self,
        source_text: str,
        glossary_entries: Sequence[GlossaryEntry],
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        if source_text is None:
            return '', {}

        placeholder_map: Dict[str, Dict[str, str]] = {}
        tag_index = 0

        def _replace_tag(match: re.Match) -> str:
            nonlocal tag_index
            placeholder = (
                f"{self._TAG_PLACEHOLDER_PREFIX}{tag_index}{self._PLACEHOLDER_SUFFIX}"
            )
            placeholder_map[placeholder] = {
                'type': 'tag',
                'value': match.group(0),
            }
            tag_index += 1
            return placeholder

        tagged_text = ALL_TAGS_PATTERN.sub(_replace_tag, source_text)

        prepared_text, glossary_placeholders = self._inject_glossary_placeholders(
            tagged_text,
            glossary_entries,
        )
        placeholder_map.update(glossary_placeholders)

        if placeholder_map:
            log_debug(
                f"TranslationHandler: prepared {len(placeholder_map)} placeholders before translation."
            )
        return prepared_text, placeholder_map

    def _inject_glossary_placeholders(
        self,
        text: str,
        glossary_entries: Sequence[GlossaryEntry],
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        if not text:
            return '', {}

        placeholder_map: Dict[str, Dict[str, str]] = {}
        counter = 0
        working_text = text

        for entry in glossary_entries:
            if not entry.original:
                continue
            pattern = self._glossary_manager.get_compiled_pattern(entry)
            if not pattern:
                continue

            def _replace(match: re.Match) -> str:
                nonlocal counter
                placeholder = (
                    f"{self._GLOSS_PLACEHOLDER_PREFIX}{counter}{self._PLACEHOLDER_SUFFIX}"
                )
                placeholder_map[placeholder] = {
                    'type': 'glossary',
                    'value': entry.translation,
                    'original': entry.original,
                }
                counter += 1
                return placeholder

            working_text, replaced = pattern.subn(_replace, working_text)
            if replaced:
                log_debug(
                    f"TranslationHandler: replaced {replaced} occurrences of glossary term '{entry.original}' with placeholders."
                )

        return working_text, placeholder_map

    def _restore_placeholders(
        self,
        translated_text: str,
        placeholder_map: Dict[str, Dict[str, str]],
    ) -> str:
        if not placeholder_map:
            return translated_text or ''

        restored = translated_text or ''
        for placeholder, info in placeholder_map.items():
            replacement = info.get('value', '')
            if placeholder not in restored:
                log_debug(
                    f"TranslationHandler: placeholder '{placeholder}' missing in response; leaving value unchanged."
                )
                continue
            restored = restored.replace(placeholder, replacement)
        return restored

    def _parse_variation_payload(self, raw_text: str) -> List[str]:
        text = (raw_text or '').strip()
        if not text:
            return []

        try:
            parsed = json.loads(text)
            variants: List[str] = []
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, str):
                        variants.append(item)
                    elif isinstance(item, dict) and 'text' in item:
                        variants.append(str(item['text']))
            if variants:
                return variants
        except json.JSONDecodeError:
            pass

        numbered_pattern = re.compile(r'^\s*(\d+)[\).:-]\s*', re.MULTILINE)
        entries: List[str] = []
        if numbered_pattern.search(text):
            current: List[str] = []
            for line in text.splitlines():
                if numbered_pattern.match(line):
                    if current:
                        entries.append('\n'.join(current).strip())
                        current = []
                    current.append(numbered_pattern.sub('', line, count=1))
                else:
                    current.append(line)
            if current:
                entries.append('\n'.join(current).strip())
        else:
            for chunk in text.split('\n\n'):
                chunk = chunk.strip()
                if chunk:
                    entries.append(chunk)

        return [entry for entry in entries if entry][:10]

    def _normalize_line_count(
        self,
        translation: str,
        expected_lines: int,
        mode_label: str,
    ) -> str:
        text = translation or ''
        lines = text.split('\n') if text else []
        actual = len(lines)
        if actual == expected_lines:
            return text

        if actual < expected_lines:
            log_debug(
                f"TranslationHandler: translation returned fewer lines ({actual} < {expected_lines}) for {mode_label}; padding with blanks."
            )
            lines.extend([''] * (expected_lines - actual))
            return '\n'.join(lines)

        log_debug(
            f"TranslationHandler: translation returned more lines ({actual} > {expected_lines}) for {mode_label}; trimming extras."
        )
        return '\n'.join(lines[:expected_lines])

    def _log_provider_response(
        self,
        response: ProviderResponse,
        placeholder_count: int,
        expected_lines: int,
    ) -> None:
        text_excerpt = (response.text or '')[: self._MAX_LOG_EXCERPT]
        payload = response.raw_payload
        try:
            payload_snippet = json.dumps(payload)[: self._MAX_LOG_EXCERPT] if isinstance(payload, dict) else str(payload)
        except Exception:  # noqa: BLE001
            payload_snippet = str(payload)

        log_debug(
            "TranslationHandler: provider response "
            f"id={getattr(response, 'message_id', None)}, "
            f"placeholders={placeholder_count}, expected_lines={expected_lines}, "
            f"text='{text_excerpt}', payload='{payload_snippet}'"
        )

    def _send_provider_request(
        self,
        provider,
        combined_system: str,
        user_content: str,
        *,
        request_label: str,
        placeholder_count: int,
        expected_lines: int,
    ):
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": combined_system},
            {"role": "user", "content": user_content},
        ]
        session_payload = None
        state = None
        supports_sessions = getattr(provider, 'supports_sessions', False)
        if supports_sessions and self._active_provider_key:
            state = self._session_manager.ensure_session(
                provider_key=self._active_provider_key,
                system_content=combined_system,
                supports_sessions=True,
            )
            if state:
                messages, session_payload = state.prepare_request(
                    {"role": "user", "content": user_content}
                )

        self._update_status_message(f"AI: {request_label}")
        self._show_progress_indicator(f"{request_label.capitalize()}...")

        try:
            response = provider.translate(messages, session=session_payload)
            if isinstance(response, ProviderResponse):
                self._log_provider_response(response, placeholder_count, expected_lines)
                if state:
                    state.record_exchange(
                        user_content=user_content,
                        assistant_content=response.text or '',
                        conversation_id=response.conversation_id,
                    )
            self._update_status_message("AI: response received, processing...")
            return response
        finally:
            self._hide_progress_indicator()

    def _update_status_message(self, message: str, *, persistent: bool = True) -> None:
        log_debug(f"TranslationHandler status: {message}")
        if self.mw.statusBar:
            self.mw.statusBar.showMessage(message, 0 if persistent else 4000)
        QApplication.processEvents()

    def _clear_status_message(self) -> None:
        if self.mw.statusBar:
            self.mw.statusBar.clearMessage()
        QApplication.processEvents()

    def _show_progress_indicator(self, message: str) -> None:
        if self._progress_dialog is None:
            dialog = QProgressDialog(self.mw)
            dialog.setWindowTitle("AI Translation")
            dialog.setModal(True)
            dialog.setCancelButton(None)
            dialog.setRange(0, 0)
            dialog.setMinimumDuration(0)
            dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
            self._progress_dialog = dialog
        self._progress_dialog.setLabelText(message)
        self._progress_dialog.show()
        QApplication.processEvents()

    def _hide_progress_indicator(self) -> None:
        if self._progress_dialog and self._progress_dialog.isVisible():
            self._progress_dialog.hide()
            QApplication.processEvents()

    def _translate_segment(
        self,
        *,
        block_idx: int,
        string_idx: int,
        start_line: int,
        end_line: int,
        source_lines: List[str],
        mode_description: str,
        strict_line_check: bool,
    ) -> None:
        provider = self._prepare_provider()
        if not provider:
            return

        system_prompt, glossary = self._load_prompts()
        if not system_prompt:
            return

        expected_lines = len(source_lines)
        combined_system, user_content = self._compose_messages(
            system_prompt,
            glossary,
            "\n".join(source_lines),
            block_idx=block_idx,
            string_idx=string_idx,
            expected_lines=expected_lines,
            mode_description=mode_description,
        )

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            response = self._send_provider_request(
                provider,
                combined_system,
                user_content,
                request_label=f"{mode_description}: request",
                placeholder_count=0,
                expected_lines=expected_lines,
            )
        except TranslationProviderError as exc:
            QMessageBox.critical(self.mw, "AI Translation", str(exc))
            self._clear_status_message()
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.mw, "AI Translation", f"Unexpected error: {exc}")
            self._clear_status_message()
            return
        finally:
            QApplication.restoreOverrideCursor()

        cleaned_translation = self._clean_model_output(response)
        if not self._confirm_line_count(
            expected_lines,
            cleaned_translation,
            strict=strict_line_check,
            mode_label=mode_description,
        ):
            return

        self._apply_partial_translation(cleaned_translation, start_line, end_line)
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("AI translation applied to the selected rows.", 4000)

    def _prepare_provider(self):
        config = getattr(self.mw, 'translation_config', None)
        if not isinstance(config, dict):
            config = build_default_translation_config()
            self.mw.translation_config = config

        provider_key = config.get('provider', 'disabled')
        if not provider_key or provider_key == 'disabled':
            QMessageBox.information(self.mw, "AI Translation", "The AI provider is disabled in the settings.")
            return None

        providers_map = config.get('providers', {}) or {}
        provider_settings = providers_map.get(provider_key)
        if not isinstance(provider_settings, dict):
            QMessageBox.warning(
                self.mw,
                "AI Translation",
                f"No configuration found for provider '{provider_key}'.",
            )
            return None

        try:
            provider = create_translation_provider(provider_key, provider_settings)
            if self._active_provider_key != provider_key:
                self._session_manager.reset()
            self._active_provider_key = provider_key
            return provider
        except TranslationProviderError as exc:
            QMessageBox.critical(self.mw, "AI Translation", str(exc))
            return None
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.mw, "AI Translation", f"Unable to create provider: {exc}")
            return None

    def _load_prompts(self) -> Tuple[Optional[str], Optional[str]]:
        if self._cached_system_prompt and self._cached_glossary is not None:
            self._ensure_glossary_loaded(
                glossary_text=self._cached_glossary,
                plugin_name=self._current_plugin_name,
                glossary_path=self._current_glossary_path,
            )
            return self._cached_system_prompt, self._cached_glossary

        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        plugin_dir = Path('plugins') / (plugin_name or '') / 'translation_prompts' if plugin_name else None
        fallback_dir = Path('translation_prompts')

        system_candidates = []
        glossary_candidates = []
        if plugin_dir and plugin_dir.exists():
            system_candidates.append(plugin_dir / 'system_prompt.md')
            glossary_candidates.append(plugin_dir / 'glossary.md')
        if fallback_dir.exists():
            system_candidates.append(fallback_dir / 'system_prompt.md')
            glossary_candidates.append(fallback_dir / 'glossary.md')

        system_path = next((p for p in system_candidates if p.exists()), None)
        if system_path is None:
            QMessageBox.critical(
                self.mw,
                "AI Translation",
                "system_prompt.md was not found in the plugin or in the default templates.",
            )
            return None, None

        if plugin_dir and system_path != plugin_dir / 'system_prompt.md':
            QMessageBox.warning(
                self.mw,
                "AI Translation",
                f"Using the default system prompt:\n{system_path}",
            )

        try:
            system_prompt = system_path.read_text(encoding='utf-8').strip()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self.mw,
                "AI Translation",
                f"Failed to read system_prompt.md:\n{exc}",
            )
            return None, None

        glossary_path = next((p for p in glossary_candidates if p.exists()), None)
        glossary_text = ''
        if glossary_path is not None:
            try:
                glossary_text = glossary_path.read_text(encoding='utf-8').strip()
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(
                    self.mw,
                    "AI Translation",
                    f"Failed to read glossary.md:\n{exc}",
                )
        else:
            QMessageBox.warning(
                self.mw,
                "AI Translation",
                "Glossary is missing; translation may be inconsistent.",
            )

        self._current_glossary_path = glossary_path
        self._current_plugin_name = plugin_name
        self._glossary_manager.load_from_text(
            plugin_name=plugin_name,
            glossary_path=glossary_path,
            raw_text=glossary_text,
        )
        self._update_glossary_highlighting()

        self._cached_system_prompt = system_prompt
        self._cached_glossary = glossary_text
        return system_prompt, glossary_text

    def _compose_messages(
        self,
        system_prompt: str,
        glossary_text: str,
        source_text: str,
        *,
        block_idx: Optional[int],
        string_idx: Optional[int],
        expected_lines: int,
        mode_description: str,
        request_type: str = "translation",
        current_translation: Optional[str] = None,
        placeholder_tokens: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        combined_system = system_prompt.strip()
        if glossary_text:
            combined_system = (
                f"{combined_system}\n\n"
                f"GLOSSARY (use with absolute priority):\n{glossary_text.strip()}"
            )

        context_lines: List[str] = []
        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else "Unknown game"
        context_lines.append(f"Game: {game_name}")
        if block_idx is not None and block_idx != -1:
            block_label = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
            context_lines.append(f"Block: {block_label} (#{block_idx})")
        if string_idx is not None and string_idx != -1:
            context_lines.append(f"Row: #{string_idx}")
        if mode_description:
            context_lines.append(f"Mode: {mode_description}")

        if request_type == "variation":
            instructions = [
                "Create an alternative Ukrainian translation based on the original text.",
                f"Keep exactly {expected_lines} lines (including empty ones) and preserve their order.",
                "Preserve all tags, placeholders, spaces, and punctuation in their original positions.",
                "Follow the glossary terminology and the game's style.",
                "The variation must differ from the current translation while staying semantically accurate.",
                "Do not add comments or meta text; return only the translation.",
            ]
        elif request_type == "variation_list":
            instructions = [
                "Generate 10 different Ukrainian translation alternatives for the provided text.",
                f"Each option must contain exactly {expected_lines} lines (including empty ones) in the same order.",
                "Preserve all tags, placeholders, markup, spaces, and punctuation in their original positions.",
                "Follow the glossary and the tone of the original text.",
                "Return the response as a JSON array with 10 strings and no additional commentary.",
            ]
        else:
            instructions = [
                "Translate the text into Ukrainian without altering the meaning.",
                f"Keep exactly {expected_lines} lines (including empty ones) and preserve their order.",
                "Preserve all tags, placeholders, markup, spaces, and punctuation.",
                "The glossary has absolute priority.",
                "Do not add explanations or meta text; return only the translation.",
            ]

        if placeholder_tokens:
            sample_tokens = placeholder_tokens[:4]
            sample_display = ', '.join(sample_tokens)
            if len(placeholder_tokens) > 4:
                sample_display += ', ...'
            instructions.append(
                (
                    "Leave the markers "
                    f"{sample_display} unchanged - they will be automatically restored after translation."
                )
            )

        user_sections = ["\n".join(context_lines), "\n".join(instructions)]
        if request_type in {"variation", "variation_list"} and current_translation:
            user_sections.append("Current translation:")
            user_sections.append(str(current_translation))
        user_sections.append("Original text:")
        user_sections.append(source_text)

        user_content = "\n\n".join([section for section in user_sections if section])
        return combined_system, user_content

    def _request_glossary_rows(self, *, source_lines: List[str], context_label: str) -> Optional[str]:
        provider = self._prepare_provider()
        if not provider:
            return None

        system_prompt, glossary_text = self._load_prompts()
        if not system_prompt:
            return None

        existing_glossary = glossary_text or ""
        combined_system = (
            "You are a Nintendo localization editor. Build glossary entries in Markdown format. "
            "Repeat established translations, follow the game's style, and avoid introducing new names unnecessarily."
        )

        lines_text = "\n".join(str(line) for line in source_lines if line is not None)
        if not lines_text.strip():
            QMessageBox.information(self.mw, "AI Translation", "No data available for glossary generation.")
            return None

        user_parts = [
            f"Context: {context_label}",
            "Create 3-10 new glossary rows if needed.",
            "Each row format: | Original | Translation | Notes |",
            "Do not repeat entries that already exist in the glossary; skip duplicates.",
            "Return only the table without extra text; no table header is required.",
        ]
        if existing_glossary:
            user_parts.append("Current glossary for duplicate checks:")
            user_parts.append(existing_glossary)
        user_parts.append("Text fragment for analysis:")
        user_parts.append(lines_text)

        messages = [
            {"role": "system", "content": combined_system},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            response = provider.translate(messages)
        except TranslationProviderError as exc:
            QMessageBox.critical(self.mw, "AI Translation", str(exc))
            return None
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.mw, "AI Translation", f"Unexpected glossary error: {exc}")
            return None
        finally:
            QApplication.restoreOverrideCursor()

        cleaned = self._clean_model_output(response)
        cleaned = cleaned.strip()
        if not cleaned:
            QMessageBox.information(self.mw, "AI Translation", "AI did not propose new glossary terms.")
            return None

        return cleaned

    def _append_to_glossary(self, *, section_title: str, table_rows: str) -> None:
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        if not plugin_name:
            QMessageBox.warning(self.mw, "AI Translation", "The game plugin is not loaded.")
            return

        prompts_dir = Path('plugins') / plugin_name / 'translation_prompts'
        prompts_dir.mkdir(parents=True, exist_ok=True)
        glossary_path = prompts_dir / 'glossary.md'

        heading = f"\n\n## {section_title}\n\n| Original | Translation | Notes |\n|----------|-------------|-------|\n"
        content_to_append = heading + table_rows.strip() + "\n"

        try:
            with glossary_path.open('a', encoding='utf-8') as fh:
                fh.write(content_to_append)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self.mw,
                "AI Translation",
                f"Failed to update glossary.md:\n{exc}",
            )
            return

        try:
            updated_text = glossary_path.read_text(encoding='utf-8')
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self.mw,
                "AI Translation",
                f"Failed to reload the updated glossary.md:\n{exc}",
            )
            updated_text = ''

        self._current_glossary_path = glossary_path
        self._glossary_manager.load_from_text(
            plugin_name=plugin_name,
            glossary_path=glossary_path,
            raw_text=updated_text,
        )
        self._session_manager.reset()
        self._cached_glossary = None  # force reload on next access
        self._update_glossary_highlighting()
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("Glossary updated.", 5000)

    def _update_glossary_highlighting(self) -> None:
        manager = self._glossary_manager if self._glossary_manager.get_entries() else None
        editor = getattr(self.mw, 'original_text_edit', None)
        if editor and hasattr(editor, 'set_glossary_manager'):
            editor.set_glossary_manager(manager)

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
                glossary_text = ''
        self._current_plugin_name = plugin_name
        self._current_glossary_path = glossary_path
        self._cached_glossary = glossary_text
        self._ensure_glossary_loaded(
            glossary_text=glossary_text,
            plugin_name=plugin_name,
            glossary_path=glossary_path,
        )

    def _load_glossary_prompt_template(self) -> str:
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        game_name = (
            self.mw.current_game_rules.get_display_name()
            if getattr(self.mw, 'current_game_rules', None)
            else (plugin_name or "the game")
        )
        if (
            self._cached_glossary_prompt_template is not None
            and self._cached_glossary_prompt_plugin == plugin_name
        ):
            return self._cached_glossary_prompt_template

        template_text = None
        candidates = []
        if plugin_name:
            candidates.append(Path('plugins') / plugin_name / 'translation_prompts' / 'glossary_prompt.md')
        candidates.append(Path('translation_prompts') / 'glossary_prompt.md')
        for candidate in candidates:
            if candidate.exists():
                try:
                    template_text = candidate.read_text(encoding='utf-8').strip()
                    break
                except Exception as exc:
                    log_debug(f"Glossary prompt read error ({candidate}): {exc}")

        if not template_text:
            template_text = _DEFAULT_GLOSSARY_PROMPT.format(game_name=game_name)
        else:
            template_text = (
                template_text.replace('{{GAME_NAME}}', game_name)
                .replace('{{game_name}}', game_name)
            )

        self._cached_glossary_prompt_template = template_text
        self._cached_glossary_prompt_plugin = plugin_name
        return template_text

    def _prompt_new_glossary_entry(
        self,
        original: str,
        suggestion_provider: Optional[Callable[[], Optional[Tuple[str, str]]]] = None,
        variation_provider: Optional[Callable[[], Optional[List[Tuple[str, str]]]]] = None,
    ) -> Optional[Tuple[str, str]]:
        dialog = QDialog(self.mw)
        dialog.setWindowTitle("Add Glossary Term")
        layout = QVBoxLayout(dialog)

        prompt_label = QLabel(f'Original: "{original}"', dialog)
        prompt_label.setWordWrap(True)
        layout.addWidget(prompt_label)

        translation_edit = QLineEdit(dialog)
        translation_edit.setPlaceholderText("Translation")
        layout.addWidget(translation_edit)

        notes_edit = QPlainTextEdit(dialog)
        notes_edit.setPlaceholderText("Notes (Shift+Enter for newline)")
        layout.addWidget(notes_edit)

        controls_layout: Optional[QHBoxLayout] = None
        if suggestion_provider or variation_provider:
            controls_layout = QHBoxLayout()
            controls_layout.addStretch(1)

        if suggestion_provider:
            suggest_button = QPushButton("AI Suggest", dialog)

            def on_suggest_clicked() -> None:
                suggest_button.setEnabled(False)
                try:
                    suggestion = suggestion_provider()
                finally:
                    suggest_button.setEnabled(True)
                if not suggestion:
                    QMessageBox.information(
                        dialog,
                        "AI Suggestion",
                        "No suggestion could be generated.",
                    )
                    return
                suggested_translation, suggested_notes = suggestion
                translation_edit.setText(suggested_translation)
                notes_edit.setPlainText(suggested_notes)
                translation_edit.selectAll()
                translation_edit.setFocus()

            suggest_button.clicked.connect(on_suggest_clicked)
            controls_layout.addWidget(suggest_button)

        if variation_provider:
            variations_button = QPushButton("AI Variations", dialog)

            def on_variations_clicked() -> None:
                variations_button.setEnabled(False)
                try:
                    variants = variation_provider() or []
                finally:
                    variations_button.setEnabled(True)
                if not variants:
                    QMessageBox.information(
                        dialog,
                        "AI Variations",
                        "No variations could be generated.",
                    )
                    return

                chooser = QDialog(dialog)
                chooser.setWindowTitle("Select AI Variation")
                chooser_layout = QVBoxLayout(chooser)
                list_widget = QListWidget(chooser)
                for translation, notes in variants:
                    display = translation
                    if notes:
                        display = f"{translation}\n{notes}"
                    item = QListWidgetItem(display)
                    item.setData(Qt.UserRole, (translation, notes))
                    list_widget.addItem(item)
                if list_widget.count() > 0:
                    list_widget.setCurrentRow(0)

                chooser_layout.addWidget(list_widget)
                chooser_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=chooser)
                chooser_layout.addWidget(chooser_buttons)

                def accept_current() -> None:
                    chooser.accept()

                list_widget.itemDoubleClicked.connect(lambda _: accept_current())
                chooser_buttons.accepted.connect(chooser.accept)
                chooser_buttons.rejected.connect(chooser.reject)

                if chooser.exec_() != QDialog.Accepted:
                    return

                current_item = list_widget.currentItem()
                if not current_item:
                    return
                translation, notes = current_item.data(Qt.UserRole)
                translation_edit.setText(translation)
                notes_edit.setPlainText(notes)
                translation_edit.selectAll()
                translation_edit.setFocus()

            variations_button.clicked.connect(on_variations_clicked)
            controls_layout.addWidget(variations_button)

        if controls_layout and controls_layout.count() > 1:
            layout.addLayout(controls_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        enter_filter = _ReturnToAcceptFilter(dialog)
        notes_edit.installEventFilter(enter_filter)
        translation_edit.returnPressed.connect(dialog.accept)

        translation_edit.selectAll()
        translation_edit.setFocus()

        if dialog.exec_() != QDialog.Accepted:
            return None

        translation = translation_edit.text().strip()
        notes = notes_edit.toPlainText().strip()
        return translation, notes

    def add_glossary_entry(self, original: str, context: Optional[str] = None) -> None:
        original_value = ' '.join((original or '').splitlines()).strip()
        while '  ' in original_value:
            original_value = original_value.replace('  ', ' ')
        if not original_value:
            QMessageBox.information(self.mw, 'Glossary', 'Select text to add to the glossary.')
            return

        context_line = ' '.join((context or '').splitlines()).strip() if context else ''

        if context_line:
            suggestion_provider = lambda: self._request_glossary_suggestion(original_value, context_line)
            variation_provider = lambda: self._request_glossary_variations(original_value, context_line)
        else:
            suggestion_provider = lambda: self._request_glossary_suggestion(original_value, None)
            variation_provider = lambda: self._request_glossary_variations(original_value, None)

        result = self._prompt_new_glossary_entry(
            original_value,
            suggestion_provider=suggestion_provider,
            variation_provider=variation_provider,
        )
        if not result:
            return
        translation, notes = result

        entry = self._glossary_manager.add_entry(original_value, translation, notes)
        if not entry:
            QMessageBox.warning(self.mw, 'Glossary', 'Failed to add the glossary entry.')
            return
        self._cached_glossary = self._glossary_manager.get_raw_text()
        self._session_manager.reset()
        self._update_glossary_highlighting()
        if self.mw.statusBar:
            self.mw.statusBar.showMessage(f'Added to glossary: {original_value}', 4000)

    def _request_glossary_suggestion(
        self,
        term: str,
        context_line: Optional[str],
    ) -> Optional[Tuple[str, str]]:
        provider = self._prepare_provider()
        if not provider:
            return None

        template = self._load_glossary_prompt_template()
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        game_name = (
            self.mw.current_game_rules.get_display_name()
            if getattr(self.mw, 'current_game_rules', None)
            else (plugin_name or "the game")
        )

        system_prompt = template
        user_sections = [
            f"Game: {game_name}",
            f"Source term: {term}",
        ]
        if context_line:
            user_sections.append(f"Context line: {context_line}")
        user_sections.extend([
            "Provide Ukrainian strings only.",
            "Return JSON with keys \"translation\" and \"notes\".",
            "Use \"notes\" for a short usage comment; leave it empty if unnecessary.",
        ])
        user_content = "\n".join(user_sections)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        self._update_status_message("AI: generating glossary suggestion", persistent=False)
        self._show_progress_indicator("Generating glossary suggestion...")

        try:
            response = provider.translate(messages)
        except TranslationProviderError as exc:
            log_debug(f"Glossary suggestion provider error: {exc}")
            self._clear_status_message()
            return None
        except Exception as exc:  # noqa: BLE001
            log_debug(f"Unexpected glossary suggestion error: {exc}")
            self._clear_status_message()
            return None
        finally:
            self._hide_progress_indicator()

        cleaned = self._clean_model_output(response)
        self._clear_status_message()

        try:
            suggestion_data = json.loads(cleaned)
        except json.JSONDecodeError:
            log_debug("Glossary suggestion response is not valid JSON")
            return None

        if isinstance(suggestion_data, list) and suggestion_data:
            suggestion_data = suggestion_data[0]

        if not isinstance(suggestion_data, dict):
            return None

        translation = str(suggestion_data.get('translation', '')).strip()
        notes = str(suggestion_data.get('notes', '')).strip()
        if not translation:
            return None
        return translation, notes

    def _request_glossary_variations(
        self,
        term: str,
        context_line: Optional[str],
    ) -> Optional[List[Tuple[str, str]]]:
        provider = self._prepare_provider()
        if not provider:
            return None

        template = self._load_glossary_prompt_template()
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        game_name = (
            self.mw.current_game_rules.get_display_name()
            if getattr(self.mw, 'current_game_rules', None)
            else (plugin_name or "the game")
        )

        system_prompt = template
        user_sections = [
            f"Game: {game_name}",
            f"Source term: {term}",
        ]
        if context_line:
            user_sections.append(f"Context line: {context_line}")
        user_sections.extend([
            "Provide 3-5 creative Ukrainian translation options.",
            "Respond strictly as a JSON array where each item is an object with keys \"translation\" and \"notes\".",
            "Keep notes short (<= 120 characters) and focused on in-game meaning only.",
        ])
        user_content = "\n".join(user_sections)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        self._update_status_message("AI: generating glossary variations", persistent=False)
        self._show_progress_indicator("Generating glossary variations...")

        try:
            response = provider.translate(messages)
        except TranslationProviderError as exc:
            log_debug(f"Glossary variation provider error: {exc}")
            self._clear_status_message()
            return None
        except Exception as exc:  # noqa: BLE001
            log_debug(f"Unexpected glossary variation error: {exc}")
            self._clear_status_message()
            return None
        finally:
            self._hide_progress_indicator()

        cleaned = self._clean_model_output(response)
        self._clear_status_message()

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            log_debug("Glossary variation response is not valid JSON")
            return None

        if isinstance(payload, dict) and 'variations' in payload:
            payload = payload['variations']

        if not isinstance(payload, list):
            return None

        results: List[Tuple[str, str]] = []
        for item in payload:
            if isinstance(item, dict):
                translation = str(item.get('translation', '')).strip()
                notes = str(item.get('notes', '')).strip()
                if translation:
                    results.append((translation, notes))
            elif isinstance(item, str):
                results.append((item.strip(), ''))

        return results or None

    def _handle_glossary_entry_update(
        self,
        original: str,
        translation: str,
        notes: str,
    ) -> Optional[Tuple[Sequence[GlossaryEntry], Dict[str, List[GlossaryOccurrence]]]]:
        updated_entry = self._glossary_manager.update_entry(original, translation, notes)
        if not updated_entry:
            QMessageBox.warning(
                self.mw,
                "Glossary",
                f"Failed to update term '{original}'.",
            )
            return None

        data_source = getattr(self.mw, 'data', None)
        dataset = data_source if isinstance(data_source, list) else []
        occurrence_map = self._glossary_manager.build_occurrence_index(dataset)
        entries = sorted(
            self._glossary_manager.get_entries(),
            key=lambda entry: entry.original.lower(),
        )
        self._session_manager.reset()
        self._update_glossary_highlighting()
        self._cached_glossary = self._glossary_manager.get_raw_text()
        if self.mw.statusBar:
            self.mw.statusBar.showMessage(
                f"Glossary updated: {original}",
                4000,
            )
        return entries, occurrence_map

    def _handle_glossary_entry_delete(
        self,
        original: str,
    ) -> Optional[Tuple[Sequence[GlossaryEntry], Dict[str, List[GlossaryOccurrence]]]]:
        if not self._glossary_manager.delete_entry(original):
            QMessageBox.warning(
                self.mw,
                "Glossary",
                f"Failed to delete term '{original}'.",
            )
            return None

        data_source = getattr(self.mw, 'data', None)
        dataset = data_source if isinstance(data_source, list) else []
        occurrence_map = self._glossary_manager.build_occurrence_index(dataset)
        entries = sorted(
            self._glossary_manager.get_entries(),
            key=lambda entry: entry.original.lower(),
        )
        self._session_manager.reset()
        self._update_glossary_highlighting()
        self._cached_glossary = self._glossary_manager.get_raw_text()
        if self.mw.statusBar:
            self.mw.statusBar.showMessage(
                f"Glossary deleted: {original}",
                4000,
            )
        return entries, occurrence_map

    def _ensure_glossary_loaded(
        self,
        *,
        glossary_text: Optional[str],
        plugin_name: Optional[str],
        glossary_path: Optional[Path],
    ) -> None:
        if glossary_text is None:
            return
        self._glossary_manager.load_from_text(
            plugin_name=plugin_name,
            glossary_path=glossary_path,
            raw_text=glossary_text,
        )
        self._update_glossary_highlighting()

    def _clean_model_output(self, raw_output: Union[str, ProviderResponse]) -> str:
        if isinstance(raw_output, ProviderResponse):
            text = raw_output.text or ''
        elif raw_output is None:
            text = ''
        else:
            text = str(raw_output)
        trimmed_left = text.lstrip()
        if trimmed_left.startswith('```'):
            trimmed = trimmed_left.strip()
            lines = trimmed.splitlines()
            if len(lines) >= 3 and lines[0].startswith('```') and lines[-1].startswith('```'):
                return "\n".join(lines[1:-1])
        return text

    def _confirm_line_count(self, expected: int, translation: str, *, strict: bool, mode_label: str) -> bool:
        actual = len(translation.split('\n')) if translation else 0
        if actual == expected:
            return True

        message = (
            f"Expected {expected} lines, received {actual}. "
            f"The translation for {mode_label} may break formatting. "
            "Apply the result?"
        )
        if strict:
            QMessageBox.warning(self.mw, "AI Translation", message)
            return False

        reply = QMessageBox.question(
            self.mw,
            "AI Translation",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _apply_full_translation(self, new_text: str):
        edited_widget = getattr(self.mw, 'edited_text_edit', None)
        if not edited_widget:
            return

        visual_text = new_text
        if self.mw.current_game_rules and hasattr(self.mw.current_game_rules, 'get_text_representation_for_editor'):
            visual_text = self.mw.current_game_rules.get_text_representation_for_editor(str(new_text))
        display_text = convert_spaces_to_dots_for_display(visual_text, self.mw.show_multiple_spaces_as_dots)

        cursor = edited_widget.textCursor()
        saved_anchor = cursor.anchor()
        saved_position = cursor.position()
        saved_has_selection = cursor.hasSelection()

        self.mw.is_programmatically_changing_text = True
        cursor.beginEditBlock()
        cursor.select(QTextCursor.Document)
        cursor.insertText(display_text)
        cursor.endEditBlock()
        self.mw.is_programmatically_changing_text = False

        restored = edited_widget.textCursor()
        if saved_has_selection:
            restored.setPosition(min(saved_anchor, len(display_text)))
            restored.setPosition(min(saved_position, len(display_text)), QTextCursor.KeepAnchor)
        else:
            restored.movePosition(QTextCursor.End)
        edited_widget.setTextCursor(restored)

        self.mw.editor_operation_handler.text_edited()

    def _apply_partial_translation(self, translated_segment: str, start_line: int, end_line: int):
        current_text, _ = self.data_processor.get_current_string_text(
            self.mw.current_block_idx,
            self.mw.current_string_idx,
        )
        current_lines = str(current_text).split('\n')
        translated_lines = translated_segment.split('\n') if translated_segment else []
        for offset, new_line in enumerate(translated_lines):
            target_idx = start_line + offset
            while len(current_lines) <= target_idx:
                current_lines.append('')
            current_lines[target_idx] = new_line
        self._apply_full_translation('\n'.join(current_lines))

    def _get_original_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return self.data_processor._get_string_from_source(  # noqa: SLF001
            block_idx,
            string_idx,
            getattr(self.mw, 'data', None),
            'original_for_translation',
        )

    def _activate_entry(self, entry: Dict[str, object]) -> None:
        block = entry.get('block_idx')
        string = entry.get('string_idx')
        line_idx = entry.get('line_idx')
        if block is None or string is None:
            return

        try:
            block_idx = int(block)
            string_idx = int(string)
        except (TypeError, ValueError):
            return

        line_number = None
        if line_idx is not None:
            try:
                line_number = int(line_idx)
            except (TypeError, ValueError):
                line_number = None

        block_widget = getattr(self.mw, 'block_list_widget', None)
        if block_widget and 0 <= block_idx < block_widget.count():
            block_widget.setCurrentRow(block_idx)

        if hasattr(self.mw, 'list_selection_handler'):
            self.mw.list_selection_handler.string_selected_from_preview(string_idx)
        else:
            self.mw.current_block_idx = block_idx
            self.mw.current_string_idx = string_idx
            self.ui_updater.populate_strings_for_block(block_idx)
            self.mw.ui_updater.update_text_views()

        original_editor = getattr(self.mw, 'original_text_edit', None)
        if original_editor and line_number is not None:
            block_obj = original_editor.document().findBlockByNumber(line_number)
            if block_obj.isValid():
                cursor = original_editor.textCursor()
                cursor.setPosition(block_obj.position())
                original_editor.setTextCursor(cursor)
                original_editor.ensureCursorVisible()

    def _get_original_block(self, block_idx: int) -> List[str]:
        data_source = getattr(self.mw, 'data', None)
        if not isinstance(data_source, list) or not (0 <= block_idx < len(data_source)):
            return []
        block = data_source[block_idx]
        if not isinstance(block, list):
            return []
        return [str(item) for item in block]

    def _resolve_selection_from_original(self) -> Optional[Tuple[int, int, int, int, List[str]]]:
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            QMessageBox.information(self.mw, "AI Translation", "Select a row in the original editor.")
            return None

        original_editor = getattr(self.mw, 'original_text_edit', None)
        if not original_editor or not original_editor.textCursor().hasSelection():
            QMessageBox.information(self.mw, "AI Translation", "Select lines in the original text.")
            return None

        selection = original_editor.textCursor()
        start_pos, end_pos = sorted([selection.anchor(), selection.position()])
        if start_pos == end_pos:
            QMessageBox.information(self.mw, "AI Translation", "Translating an empty selection is not meaningful.")
            return None

        doc = original_editor.document()
        start_block = doc.findBlock(start_pos).blockNumber()
        end_block = doc.findBlock(max(end_pos - 1, start_pos)).blockNumber()

        original_text = str(self._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx) or "")
        original_lines = original_text.split('\n')
        if not original_lines:
            QMessageBox.information(self.mw, "AI Translation", "The selected row has no text.")
            return None

        max_index = len(original_lines) - 1
        start_block = max(0, min(start_block, max_index))
        end_block = max(0, min(end_block, max_index))
        if start_block > end_block:
            start_block, end_block = end_block, start_block

        selected_lines = original_lines[start_block:end_block + 1]
        if not selected_lines:
            QMessageBox.information(self.mw, "AI Translation", "The selected rows are missing from the current text.")
            return None

        return (
            self.mw.current_block_idx,
            self.mw.current_string_idx,
            start_block,
            end_block,
            selected_lines,
        )

    def _resolve_selection_from_preview(self) -> Optional[Tuple[int, int, int, int, List[str]]]:
        preview = getattr(self.mw, 'preview_text_edit', None)
        if not preview or not preview.textCursor().hasSelection():
            return None

        cursor = preview.textCursor()
        start_pos, end_pos = sorted([cursor.selectionStart(), cursor.selectionEnd()])
        if start_pos == end_pos:
            return None

        doc = preview.document()
        start_block = doc.findBlock(start_pos).blockNumber()
        end_block = doc.findBlock(max(end_pos - 1, start_pos)).blockNumber()

        block_idx = self.mw.current_block_idx
        string_idx = self.mw.current_string_idx
        if block_idx == -1 or string_idx == -1:
            return None

        original_text = str(self._get_original_string(block_idx, string_idx) or "")
        original_lines = original_text.split('\n')
        if not original_lines:
            return None

        max_index = len(original_lines) - 1
        start_block = max(0, min(start_block, max_index))
        end_block = max(0, min(end_block, max_index))
        if start_block > end_block:
            start_block, end_block = end_block, start_block

        selected_lines = original_lines[start_block:end_block + 1]
        if not selected_lines:
            return None

        return (block_idx, string_idx, start_block, end_block, selected_lines)
