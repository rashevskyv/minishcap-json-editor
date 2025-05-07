import re
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtGui import QTextCursor # Потрібен для збереження/відновлення курсора в preview
from handlers.base_handler import BaseHandler
from utils import log_debug, convert_dots_to_spaces_from_editor, convert_spaces_to_dots_for_display 
from tag_utils import apply_default_mappings_only, analyze_tags_for_issues, \
                      TAG_STATUS_OK, TAG_STATUS_UNRESOLVED_BRACKETS, TAG_STATUS_MISMATCHED_CURLY

class TextOperationHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        pass

    def text_edited(self):
        if self.mw.is_programmatically_changing_text: 
            return 
        
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1: 
            return
        
        block_idx = self.mw.current_block_idx
        string_idx_in_block = self.mw.current_string_idx
        block_key = str(block_idx)
        
        # Зберігаємо позицію курсора в edited_text_edit, бо вона може змінитися після оновлення UI (хоча ми намагаємося цього уникнути)
        # Однак, оскільки ми більше не будемо викликати setPlainText для edited_text_edit тут,
        # ця частина може бути менш критичною, але залишимо для безпеки.
        # saved_edited_cursor = self.mw.edited_text_edit.textCursor() 
        
        text_from_ui_with_dots = self.mw.edited_text_edit.toPlainText() 
        actual_text_with_spaces = text_from_ui_with_dots
        if self.mw.show_multiple_spaces_as_dots:
            actual_text_with_spaces = convert_dots_to_spaces_from_editor(text_from_ui_with_dots)
        
        unsaved_status_changed = self.data_processor.update_edited_data(block_idx, string_idx_in_block, actual_text_with_spaces)
        if unsaved_status_changed: 
            self.ui_updater.update_title()

        # --- Оновлення тільки preview_text_edit та статусу проблем ---
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit:
            # 1. Оновлюємо текст відповідного рядка в preview_text_edit
            # Це потрібно робити обережно, щоб не скинути прокрутку і виділення інших рядків.
            doc = preview_edit.document()
            if 0 <= string_idx_in_block < doc.blockCount():
                cursor = QTextCursor(doc.findBlockByNumber(string_idx_in_block))
                # Готуємо текст для прев'ю (з символами замість \n та точками замість пробілів)
                text_for_preview_display = convert_spaces_to_dots_for_display(
                    actual_text_with_spaces, self.mw.show_multiple_spaces_as_dots
                ).replace('\n', getattr(self.mw, "newline_display_symbol", "↵"))
                
                # Зберігаємо поточну позицію курсора в preview_edit, якщо вона важлива
                # prev_cursor_pos = preview_edit.textCursor().position()

                self.mw.is_programmatically_changing_text = True # Встановлюємо прапор перед зміною тексту в preview
                cursor.select(QTextCursor.BlockUnderCursor)
                cursor.insertText(text_for_preview_display)
                self.mw.is_programmatically_changing_text = False

                # Відновлення курсора в preview_edit може бути складним,
                # якщо ми не хочемо, щоб він стрибав. Поки що пропустимо.

            # 2. Перевіряємо та оновлюємо статус проблем для редагованого рядка
            original_text_for_comparison = self.data_processor._get_string_from_source(
                block_idx, string_idx_in_block, self.mw.data, "original_for_text_edited_check"
            )
            if original_text_for_comparison is not None:
                text_after_default_mappings, _ = apply_default_mappings_only(
                    actual_text_with_spaces, 
                    self.mw.default_tag_mappings
                )
                tag_status, _ = analyze_tags_for_issues(
                    text_after_default_mappings, 
                    original_text_for_comparison
                )

                # Оновлюємо critical_problem_lines_per_block
                crit_problems = self.mw.critical_problem_lines_per_block.get(block_key, set())
                old_crit_state = string_idx_in_block in crit_problems
                new_crit_state = (tag_status == TAG_STATUS_UNRESOLVED_BRACKETS)

                if old_crit_state != new_crit_state:
                    if new_crit_state: crit_problems.add(string_idx_in_block)
                    else: crit_problems.discard(string_idx_in_block)
                    if crit_problems: self.mw.critical_problem_lines_per_block[block_key] = crit_problems
                    elif block_key in self.mw.critical_problem_lines_per_block: del self.mw.critical_problem_lines_per_block[block_key]
                    # Оновлюємо підсвічування тільки для цього рядка
                    if new_crit_state: preview_edit.addCriticalProblemHighlight(string_idx_in_block)
                    else: preview_edit.removeCriticalProblemHighlight(string_idx_in_block)

                # Оновлюємо warning_problem_lines_per_block
                warn_problems = self.mw.warning_problem_lines_per_block.get(block_key, set())
                old_warn_state = string_idx_in_block in warn_problems
                new_warn_state = (tag_status == TAG_STATUS_MISMATCHED_CURLY) # Тільки якщо немає UNRESOLVED_BRACKETS

                if old_warn_state != new_warn_state:
                    if new_warn_state: warn_problems.add(string_idx_in_block)
                    else: warn_problems.discard(string_idx_in_block)
                    if warn_problems: self.mw.warning_problem_lines_per_block[block_key] = warn_problems
                    elif block_key in self.mw.warning_problem_lines_per_block: del self.mw.warning_problem_lines_per_block[block_key]
                    # Оновлюємо підсвічування тільки для цього рядка
                    if new_warn_state: preview_edit.addWarningLineHighlight(string_idx_in_block)
                    else: preview_edit.removeWarningLineHighlight(string_idx_in_block)
                
                preview_edit.applyQueuedHighlights() # Застосувати зміни підсвічування

                # Оновлюємо текст елемента блоку в списку
                if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
                    self.ui_updater.update_block_item_text_with_problem_count(block_idx)
        
        # НЕ викликаємо populate_strings_for_block або update_text_views тут,
        # щоб не перезаписувати edited_text_edit.

        # Оновлюємо статус бар, оскільки довжина рядка могла змінитися
        self.ui_updater.update_status_bar() 
        self.ui_updater.synchronize_original_cursor() # Також синхронізуємо курсор в original_text_edit

        # Повернення курсора в edited_text_edit тепер не потрібне, бо ми не викликали setPlainText
        # if saved_edited_cursor:
        #    self.mw.edited_text_edit.setTextCursor(saved_edited_cursor)
        # log_debug(f"TextEdited: Finished for ({block_idx}, {string_idx_in_block}). Preview updated.")

    # ... (решта коду, paste_block_text без змін відносно попередньої версії) ...
    def paste_block_text(self):
        log_debug("--> TextOperationHandler: paste_block_text triggered.")
        if self.mw.current_block_idx == -1:
            QMessageBox.warning(self.mw, "Paste Error", "Please select a block.")
            return

        block_idx = self.mw.current_block_idx
        block_key = str(block_idx)

        self.mw.before_paste_edited_data_snapshot = dict(self.mw.edited_data)
        self.mw.before_paste_critical_problems_snapshot = {
            k: set(v) for k, v in self.mw.critical_problem_lines_per_block.items()
        }
        self.mw.before_paste_warning_problems_snapshot = {
            k: set(v) for k, v in self.mw.warning_problem_lines_per_block.items()
        }
        self.mw.before_paste_block_idx_affected = block_idx

        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit:
            if hasattr(preview_edit, 'clearAllProblemTypeHighlights'): preview_edit.clearAllProblemTypeHighlights()
        
        if hasattr(self.mw, 'critical_problem_lines_per_block'):
            self.mw.critical_problem_lines_per_block[block_key] = set()
        if hasattr(self.mw, 'warning_problem_lines_per_block'):
            self.mw.warning_problem_lines_per_block[block_key] = set()
        
        if hasattr(self.ui_updater, 'highlight_problem_block'):
            self.ui_updater.highlight_problem_block(block_idx, False)
        if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
            self.ui_updater.update_block_item_text_with_problem_count(block_idx)


        start_string_idx = self.mw.current_string_idx if self.mw.current_string_idx != -1 else 0
        pasted_text_raw = QApplication.clipboard().text()
        if not pasted_text_raw: QMessageBox.information(self.mw, "Paste", "Clipboard empty."); return
        
        segments_from_clipboard_raw = re.split(r'\{END\}\r?\n', pasted_text_raw)
        parsed_strings = []; num_raw_segments = len(segments_from_clipboard_raw)
        for i, segment in enumerate(segments_from_clipboard_raw):
            cleaned_segment = segment;
            if i > 0 and segment.startswith('\n'): cleaned_segment = segment[1:]
            if cleaned_segment or i < num_raw_segments - 1: parsed_strings.append(cleaned_segment)
        if parsed_strings and not parsed_strings[-1] and num_raw_segments > 1 and segments_from_clipboard_raw[-1] == '': parsed_strings.pop()
        if not parsed_strings: QMessageBox.information(self.mw, "Paste", "No valid segments found."); return
        
        original_block_len = len(self.mw.data[block_idx])
        
        current_block_new_critical_indices = set() 
        current_block_new_warning_indices = set()
        successfully_processed_count = 0; any_change_applied_to_data = False
        
        self.mw.is_programmatically_changing_text = True 
        for i, segment_to_insert_raw in enumerate(parsed_strings):
            current_target_string_idx = start_string_idx + i
            if current_target_string_idx >= original_block_len:
                if i == 0: 
                    QMessageBox.warning(self.mw, "Paste Error", f"Cannot paste starting at line {start_string_idx + 1}. Block has {original_block_len} lines.")
                    self.mw.is_programmatically_changing_text = False
                    return 
                log_debug(f"PasteBlock: Reached end of block data at index {current_target_string_idx}. Processed {i} segments.")
                break 
            
            original_text_for_tags = self.mw.data[block_idx][current_target_string_idx]

            text_after_default_mappings, _ = apply_default_mappings_only(
                segment_to_insert_raw,
                self.mw.default_tag_mappings
            )
            
            tag_status, tag_error_msg = analyze_tags_for_issues(
                text_after_default_mappings,
                original_text_for_tags
            )
            
            successfully_processed_count +=1
            final_text_to_apply = text_after_default_mappings.rstrip('\n')
            
            current_text_in_data, _ = self.data_processor.get_current_string_text(block_idx, current_target_string_idx)
            if final_text_to_apply != current_text_in_data:
                 self.data_processor.update_edited_data(block_idx, current_target_string_idx, final_text_to_apply)
                 any_change_applied_to_data = True

            if tag_status == TAG_STATUS_UNRESOLVED_BRACKETS: 
                current_block_new_critical_indices.add(current_target_string_idx)
            elif tag_status == TAG_STATUS_MISMATCHED_CURLY:
                current_block_new_warning_indices.add(current_target_string_idx)

        self.mw.is_programmatically_changing_text = False 
        
        if current_block_new_critical_indices:
            self.mw.critical_problem_lines_per_block[block_key] = current_block_new_critical_indices
        if current_block_new_warning_indices:
            self.mw.warning_problem_lines_per_block[block_key] = current_block_new_warning_indices

        message_parts = []
        if current_block_new_critical_indices:
            message_parts.append(f"{len(current_block_new_critical_indices)} line(s) with unresolved '[...]' tags (critical).")
        if current_block_new_warning_indices:
            message_parts.append(f"{len(current_block_new_warning_indices)} line(s) with mismatched '{{...}}' counts (warning).")

        if message_parts: 
            self.ui_updater.highlight_problem_block(block_idx, True) 
            
            error_summary = (f"Pasted {successfully_processed_count} segment(s) into Block '{self.mw.block_names.get(str(block_idx), str(block_idx))}'.\n"
                             + "\n".join(message_parts) +
                             "\nKnown editor tags [...] were auto-corrected where possible.\n"
                             "Please review highlighted lines.")
            QMessageBox.warning(self.mw, "Paste with Issues/Warnings", error_summary)
            if any_change_applied_to_data: self.mw.unsaved_changes = True; self.ui_updater.update_title()
        
        elif any_change_applied_to_data: 
            log_debug(f"Successfully pasted and processed {successfully_processed_count} segments. Auto-saving.")
            save_success = self.mw.app_action_handler.save_data_action(ask_confirmation=False)
            QMessageBox.information(self.mw, "Paste Operation", f"{successfully_processed_count} segment(s) processed. {'Pasted and saved.' if save_success else 'Pasted, but auto-save FAILED.'}")
        
        else: 
            log_debug("No effective changes detected from paste operation (text identical or no data changed).")
            QMessageBox.information(self.mw, "Paste", "Pasted text resulted in no changes to the data.")
        
        self.mw.is_programmatically_changing_text = True
        self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
        if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
            self.ui_updater.update_block_item_text_with_problem_count(self.mw.current_block_idx)
        self.mw.is_programmatically_changing_text = False
        
        if any_change_applied_to_data or current_block_new_critical_indices or current_block_new_warning_indices:
            self.mw.can_undo_paste = True
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(True)
        else:
            self.mw.can_undo_paste = False
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(False)

        log_debug("<-- TextOperationHandler: paste_block_text finished.")