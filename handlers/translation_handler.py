import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QApplication, QMessageBox

from handlers.base_handler import BaseHandler
from core.translation.config import build_default_translation_config
from core.translation.providers import (
    TranslationProviderError,
    create_translation_provider,
)
from utils.logging_utils import log_debug
from utils.utils import convert_spaces_to_dots_for_display


class TranslationHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self._cached_system_prompt: Optional[str] = None
        self._cached_glossary: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def translate_current_string(self):
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            QMessageBox.information(self.mw, "AI-переклад", "Оберіть рядок для перекладу." )
            return

        original_text = self._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx)
        if original_text is None:
            QMessageBox.information(self.mw, "AI-переклад", "Оригінальний текст для цього рядка відсутній.")
            return

        self._translate_and_apply(
            source_text=str(original_text),
            expected_lines=len(str(original_text).split("\n")),
            mode_description="поточний рядок",
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
            mode_description=f"рядки {start_line + 1}-{end_line + 1}",
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
            mode_description=f"рядки {start_line + 1}-{end_line + 1} (прев’ю)",
            strict_line_check=True,
        )

    def translate_current_block(self, block_idx: Optional[int] = None):
        target_block = block_idx if block_idx is not None else self.mw.current_block_idx
        if target_block is None or target_block == -1:
            QMessageBox.information(self.mw, "AI-переклад", "Оберіть блок для перекладу.")
            return

        block_strings = self._get_original_block(target_block)
        if not block_strings:
            QMessageBox.information(self.mw, "AI-переклад", "У блоці немає рядків для перекладу.")
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
                    mode_description=f"блок {block_name}, рядок {idx + 1} із {total_strings}",
                )

                if self.mw.statusBar:
                    self.mw.statusBar.showMessage(
                        f"AI-переклад: рядок {idx + 1} / {total_strings} ({block_name})",
                        0,
                    )
                QApplication.processEvents()

                try:
                    raw_translation = provider.translate(messages)
                except TranslationProviderError as exc:
                    QMessageBox.critical(
                        self.mw,
                        "AI-переклад",
                        f"Помилка під час перекладу рядка {idx + 1}: {exc}",
                    )
                    return

                cleaned = self._clean_model_output(raw_translation)
                if not self._confirm_line_count(
                    expected_lines,
                    cleaned,
                    strict=False,
                    mode_label=f"рядку {idx + 1}",
                ):
                    return

                block_translations[idx] = cleaned
        finally:
            QApplication.restoreOverrideCursor()
            if self.mw.statusBar:
                self.mw.statusBar.clearMessage()

        if not block_translations:
            QMessageBox.information(self.mw, "AI-переклад", "Переклад не створено: всі рядки порожні.")
            return

        for string_idx, translated_text in block_translations.items():
            self.data_processor.update_edited_data(target_block, string_idx, translated_text)

        self.ui_updater.populate_strings_for_block(target_block)
        if self.mw.current_block_idx == target_block and self.mw.current_string_idx != -1:
            self.mw.ui_updater.update_text_views()
        if hasattr(self.mw, 'app_action_handler'):
            self.mw.app_action_handler.rescan_issues_for_single_block(target_block, show_message_on_completion=False)
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("AI-переклад виконано для всього блока.", 5000)

    def generate_variation_for_current_string(self):
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            QMessageBox.information(self.mw, "AI-переклад", "Оберіть рядок для варіації перекладу.")
            return

        original_text = self._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx)
        if original_text is None:
            QMessageBox.information(self.mw, "AI-переклад", "Оригінальний текст для цього рядка відсутній.")
            return

        current_translation, _ = self.data_processor.get_current_string_text(
            self.mw.current_block_idx,
            self.mw.current_string_idx,
        )
        if current_translation is None or not str(current_translation).strip():
            QMessageBox.information(self.mw, "AI-переклад", "Немає поточного перекладу для варіації.")
            return

        self._translate_and_apply(
            source_text=str(original_text),
            expected_lines=len(str(original_text).split("\n")),
            mode_description="варіація поточного перекладу",
            block_idx=self.mw.current_block_idx,
            string_idx=self.mw.current_string_idx,
            request_type="variation",
            current_translation=str(current_translation),
        )

    def generate_block_glossary(self, block_idx: Optional[int] = None):
        target_block = block_idx if block_idx is not None else self.mw.current_block_idx
        if target_block is None or target_block == -1:
            QMessageBox.information(self.mw, "AI-переклад", "Оберіть блок для побудови глосарію.")
            return

        block_strings = self._get_original_block(target_block)
        if not block_strings:
            QMessageBox.information(self.mw, "AI-переклад", "У блоці немає даних для глосарію.")
            return

        glossary_rows = self._request_glossary_rows(
            source_lines=block_strings,
            context_label=f"Блок #{target_block}",
        )
        if glossary_rows:
            block_name = self.mw.block_names.get(str(target_block), f"Block {target_block}")
            self._append_to_glossary(
                section_title=f"Блок {block_name} (#{target_block})",
                table_rows=glossary_rows,
            )

    def append_selection_to_glossary(self, block_idx: Optional[int] = None):
        selection = self._resolve_selection_from_preview()
        if selection is None:
            QMessageBox.information(self.mw, "AI-переклад", "Виділіть щонайменше один рядок у прев’ю.")
            return

        sel_block_idx, sel_string_idx, start_line, end_line, selected_lines = selection
        if block_idx is not None and block_idx != sel_block_idx:
            QMessageBox.warning(self.mw, "AI-переклад", "Виділення не належить вибраному блоку.")
            return

        glossary_rows = self._request_glossary_rows(
            source_lines=selected_lines,
            context_label=f"Рядки {start_line + 1}-{end_line + 1} рядка #{sel_string_idx} блоку #{sel_block_idx}",
        )
        if glossary_rows:
            block_name = self.mw.block_names.get(str(sel_block_idx), f"Block {sel_block_idx}")
            self._append_to_glossary(
                section_title=(
                    f"Виділення з блока {block_name} (#{sel_block_idx}), рядок {sel_string_idx},"
                    f" рядки {start_line + 1}-{end_line + 1}"
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

        messages = self._compose_messages(
            system_prompt,
            glossary,
            source_text,
            block_idx=block_idx,
            string_idx=string_idx,
            expected_lines=expected_lines,
            mode_description=mode_description,
            request_type=request_type,
            current_translation=current_translation,
        )

        log_debug(
            f"AI translate ({request_type}) block={block_idx}, string={string_idx}, mode={mode_description}"
        )
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            raw_translation = provider.translate(messages)
        except TranslationProviderError as exc:
            QMessageBox.critical(self.mw, "AI-переклад", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.mw, "AI-переклад", f"Несподівана помилка: {exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        cleaned_translation = self._clean_model_output(raw_translation)
        if not self._confirm_line_count(
            expected_lines,
            cleaned_translation,
            strict=False,
            mode_label=mode_description,
        ):
            return

        self._apply_full_translation(cleaned_translation)
        if self.mw.statusBar:
            self.mw.statusBar.showMessage(
                "AI-переклад застосовано.",
                4000,
            )

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
        messages = self._compose_messages(
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
            raw_translation = provider.translate(messages)
        except TranslationProviderError as exc:
            QMessageBox.critical(self.mw, "AI-переклад", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.mw, "AI-переклад", f"Несподівана помилка: {exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        cleaned_translation = self._clean_model_output(raw_translation)
        if not self._confirm_line_count(
            expected_lines,
            cleaned_translation,
            strict=strict_line_check,
            mode_label=mode_description,
        ):
            return

        self._apply_partial_translation(cleaned_translation, start_line, end_line)
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("AI-переклад застосовано до вибраних рядків.", 4000)

    def _prepare_provider(self):
        config = getattr(self.mw, 'translation_config', None)
        if not isinstance(config, dict):
            config = build_default_translation_config()
            self.mw.translation_config = config

        provider_key = config.get('provider', 'disabled')
        if not provider_key or provider_key == 'disabled':
            QMessageBox.information(self.mw, "AI-переклад", "AI-провайдер вимкнений у налаштуваннях.")
            return None

        providers_map = config.get('providers', {}) or {}
        provider_settings = providers_map.get(provider_key)
        if not isinstance(provider_settings, dict):
            QMessageBox.warning(
                self.mw,
                "AI-переклад",
                f"Немає конфігурації для провайдера '{provider_key}'.",
            )
            return None

        try:
            return create_translation_provider(provider_key, provider_settings)
        except TranslationProviderError as exc:
            QMessageBox.critical(self.mw, "AI-переклад", str(exc))
            return None
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.mw, "AI-переклад", f"Неможливо створити провайдера: {exc}")
            return None

    def _load_prompts(self) -> Tuple[Optional[str], Optional[str]]:
        if self._cached_system_prompt and self._cached_glossary is not None:
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
                "AI-переклад",
                "Не знайдено system_prompt.md ані в плагіні, ані серед шаблонів за замовчанням.",
            )
            return None, None

        if plugin_dir and system_path != plugin_dir / 'system_prompt.md':
            QMessageBox.warning(
                self.mw,
                "AI-переклад",
                f"Використовую системний промпт за замовчанням:\n{system_path}",
            )

        try:
            system_prompt = system_path.read_text(encoding='utf-8').strip()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self.mw,
                "AI-переклад",
                f"Не вдалося прочитати system_prompt.md:\n{exc}",
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
                    "AI-переклад",
                    f"Не вдалося прочитати glossary.md:\n{exc}",
                )
        else:
            QMessageBox.warning(
                self.mw,
                "AI-переклад",
                "Глосарій відсутній; переклад може бути непослідовним.",
            )

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
    ) -> List[Dict[str, str]]:
        combined_system = system_prompt.strip()
        if glossary_text:
            combined_system = (
                f"{combined_system}\n\n"
                f"ГЛОСАРІЙ (використовувати з абсолютним пріоритетом):\n{glossary_text.strip()}"
            )

        context_lines: List[str] = []
        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else "Невідома гра"
        context_lines.append(f"Гра: {game_name}")
        if block_idx is not None and block_idx != -1:
            block_label = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
            context_lines.append(f"Блок: {block_label} (#{block_idx})")
        if string_idx is not None and string_idx != -1:
            context_lines.append(f"Рядок: #{string_idx}")
        if mode_description:
            context_lines.append(f"Режим: {mode_description}")

        if request_type == "variation":
            instructions = [
                "Створи альтернативний переклад українською на основі оригіналу.",
                f"Залиши рівно {expected_lines} рядків (включно з порожніми) та їхній порядок.",
                "Збережи всі теги, плейсхолдери, пробіли та пунктуацію на тих самих позиціях.",
                "Дотримуйся термінології з глосарія та стилю гри.",
                "Варіація має відрізнятися від наявного перекладу, але зміст повинен залишатися точним.",
                "Не додавай коментарів чи службового тексту, поверни лише переклад.",
            ]
        else:
            instructions = [
                "Переклади текст українською без зміни змісту.",
                f"Залиши рівно {expected_lines} рядків (включно з порожніми) та їхній порядок.",
                "Збережи всі теги, плейсхолдери, розмітку, пробіли та пунктуацію.",
                "Глосарій має абсолютний пріоритет.",
                "Не додавай пояснень чи службового тексту, поверни лише переклад.",
            ]

        user_sections = ["\n".join(context_lines), "\n".join(instructions)]
        if request_type == "variation" and current_translation:
            user_sections.append("Чинний переклад:")
            user_sections.append(str(current_translation))
        user_sections.append("Оригінал:")
        user_sections.append(source_text)

        user_content = "\n\n".join([section for section in user_sections if section])

        return [
            {"role": "system", "content": combined_system},
            {"role": "user", "content": user_content},
        ]

    def _request_glossary_rows(self, *, source_lines: List[str], context_label: str) -> Optional[str]:
        provider = self._prepare_provider()
        if not provider:
            return None

        system_prompt, glossary_text = self._load_prompts()
        if not system_prompt:
            return None

        existing_glossary = glossary_text or ""
        combined_system = (
            "Ти — локалізаційний редактор Nintendo. Побудуй записи для глосарію у форматі Markdown. "
            "Повторюй сталі переклади, дотримуйся стилю гри та не вигадуй нових назв без потреби."
        )

        lines_text = "\n".join(str(line) for line in source_lines if line is not None)
        if not lines_text.strip():
            QMessageBox.information(self.mw, "AI-переклад", "Дані для глосарію порожні.")
            return None

        user_parts = [
            f"Контекст: {context_label}",
            "Сформуй 3-10 нових рядків глосарію (за потреби).",
            "Формат кожного рядка: | Оригінал | Переклад | Примітки |",
            "Не повторюй записи, які вже є в глосарії. Якщо дублікат, пропусти його.",
            "Поверни лише таблицю без зайвого тексту, заголовок таблиці додавати не потрібно.",
        ]
        if existing_glossary:
            user_parts.append("Поточний глосарій для перевірки дублікатів:")
            user_parts.append(existing_glossary)
        user_parts.append("Фрагмент тексту для аналізу:")
        user_parts.append(lines_text)

        messages = [
            {"role": "system", "content": combined_system},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            response = provider.translate(messages)
        except TranslationProviderError as exc:
            QMessageBox.critical(self.mw, "AI-переклад", str(exc))
            return None
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.mw, "AI-переклад", f"Несподівана помилка глосарію: {exc}")
            return None
        finally:
            QApplication.restoreOverrideCursor()

        cleaned = self._clean_model_output(response)
        cleaned = cleaned.strip()
        if not cleaned:
            QMessageBox.information(self.mw, "AI-переклад", "AI не запропонував нових термінів.")
            return None

        return cleaned

    def _append_to_glossary(self, *, section_title: str, table_rows: str) -> None:
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        if not plugin_name:
            QMessageBox.warning(self.mw, "AI-переклад", "Плагін гри не завантажено.")
            return

        prompts_dir = Path('plugins') / plugin_name / 'translation_prompts'
        prompts_dir.mkdir(parents=True, exist_ok=True)
        glossary_path = prompts_dir / 'glossary.md'

        heading = f"\n\n## {section_title}\n\n| Оригінал | Переклад | Примітки |\n|----------|----------|----------|\n"
        content_to_append = heading + table_rows.strip() + "\n"

        try:
            with glossary_path.open('a', encoding='utf-8') as fh:
                fh.write(content_to_append)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self.mw,
                "AI-переклад",
                f"Не вдалося оновити glossary.md:\n{exc}",
            )
            return

        self._cached_glossary = None  # наступне завантаження перечитає файл
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("Глосарій оновлено.", 5000)

    def _clean_model_output(self, raw_output: str) -> str:
        if raw_output is None:
            return ''
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
            f"Очікувалося {expected} рядків, отримано {actual}. "
            f"Переклад для {mode_label} може порушити форматування. "
            "Застосувати результат?"
        )
        if strict:
            QMessageBox.warning(self.mw, "AI-переклад", message)
            return False

        reply = QMessageBox.question(
            self.mw,
            "AI-переклад",
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
            QMessageBox.information(self.mw, "AI-переклад", "Оберіть рядок у редакторі оригіналу.")
            return None

        original_editor = getattr(self.mw, 'original_text_edit', None)
        if not original_editor or not original_editor.textCursor().hasSelection():
            QMessageBox.information(self.mw, "AI-переклад", "Виділіть рядки в оригіналі.")
            return None

        selection = original_editor.textCursor()
        start_pos, end_pos = sorted([selection.anchor(), selection.position()])
        if start_pos == end_pos:
            QMessageBox.information(self.mw, "AI-переклад", "Порожнє виділення перекладати немає сенсу.")
            return None

        doc = original_editor.document()
        start_block = doc.findBlock(start_pos).blockNumber()
        end_block = doc.findBlock(max(end_pos - 1, start_pos)).blockNumber()

        original_text = str(self._get_original_string(self.mw.current_block_idx, self.mw.current_string_idx) or "")
        original_lines = original_text.split('\n')
        if not original_lines:
            QMessageBox.information(self.mw, "AI-переклад", "У вибраному рядку немає тексту.")
            return None

        max_index = len(original_lines) - 1
        start_block = max(0, min(start_block, max_index))
        end_block = max(0, min(end_block, max_index))
        if start_block > end_block:
            start_block, end_block = end_block, start_block

        selected_lines = original_lines[start_block:end_block + 1]
        if not selected_lines:
            QMessageBox.information(self.mw, "AI-переклад", "Обрані рядки відсутні у поточному тексті.")
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
