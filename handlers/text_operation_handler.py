import re
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtGui import QTextCursor 
from handlers.base_handler import BaseHandler
from utils import log_debug, convert_dots_to_spaces_from_editor, convert_spaces_to_dots_for_display 
from tag_utils import apply_default_mappings_only, analyze_tags_for_issues, \
                      process_segment_tags_aggressively, \
                      TAG_STATUS_OK, TAG_STATUS_CRITICAL, \
                      TAG_STATUS_MISMATCHED_CURLY, TAG_STATUS_UNRESOLVED_BRACKETS, \
                      TAG_STATUS_WARNING

class TextOperationHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        pass

    def text_edited(self):
        if self.mw.is_programmatically_changing_text: return 
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1: return
        
        block_idx = self.mw.current_block_idx
        string_idx_in_block = self.mw.current_string_idx
        block_key = str(block_idx)
        
        text_from_ui_with_dots = self.mw.edited_text_edit.toPlainText() 
        actual_text_with_spaces = convert_dots_to_spaces_from_editor(text_from_ui_with_dots) if self.mw.show_multiple_spaces_as_dots else text_from_ui_with_dots
        
        # Оновлюємо дані та заголовок вікна, якщо потрібно
        needs_title_update = self.data_processor.update_edited_data(block_idx, string_idx_in_block, actual_text_with_spaces)
        if needs_title_update: 
            self.ui_updater.update_title()
            
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        needs_preview_update = False # Флаг, що показує, чи треба оновлювати preview

        # Аналізуємо теги та оновлюємо стан проблем
        if preview_edit: 
            original_text_for_comparison = self.data_processor._get_string_from_source(block_idx, string_idx_in_block, self.mw.data, "original_for_text_edited_check")
            if original_text_for_comparison is not None:
                
                text_to_analyze_for_issues = actual_text_with_spaces 
                tag_status, _ = analyze_tags_for_issues(text_to_analyze_for_issues, original_text_for_comparison, self.mw.EDITOR_PLAYER_TAG)

                crit_problems = self.mw.critical_problem_lines_per_block.get(block_key, set()).copy()
                warn_problems = self.mw.warning_problem_lines_per_block.get(block_key, set()).copy()
                is_crit_before = string_idx_in_block in crit_problems
                is_warn_before = string_idx_in_block in warn_problems
                
                should_be_crit = (tag_status == TAG_STATUS_UNRESOLVED_BRACKETS) 
                should_be_warn = (tag_status == TAG_STATUS_MISMATCHED_CURLY)    
                
                # Визначаємо, чи змінився стан проблем для цього рядка
                state_changed = False
                if should_be_crit:
                    if not is_crit_before: crit_problems.add(string_idx_in_block); state_changed = True
                    if is_warn_before: warn_problems.discard(string_idx_in_block); state_changed = True
                elif should_be_warn:
                    if not is_warn_before: warn_problems.add(string_idx_in_block); state_changed = True
                    if is_crit_before: crit_problems.discard(string_idx_in_block); state_changed = True 
                else: 
                    if is_crit_before: crit_problems.discard(string_idx_in_block); state_changed = True
                    if is_warn_before: warn_problems.discard(string_idx_in_block); state_changed = True
                
                # Оновлюємо словники проблем, якщо були зміни
                if state_changed:
                    if crit_problems: self.mw.critical_problem_lines_per_block[block_key] = crit_problems
                    elif block_key in self.mw.critical_problem_lines_per_block: del self.mw.critical_problem_lines_per_block[block_key]
                    
                    if warn_problems: self.mw.warning_problem_lines_per_block[block_key] = warn_problems
                    elif block_key in self.mw.warning_problem_lines_per_block: del self.mw.warning_problem_lines_per_block[block_key]
                    
                    # Позначаємо, що preview потрібно оновити через зміну статусу проблем
                    needs_preview_update = True
                    # Оновлюємо текст елемента списку блоків
                    if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'): 
                        self.ui_updater.update_block_item_text_with_problem_count(block_idx)

        # Оновлюємо preview тільки якщо текст змінився АБО якщо статус проблеми змінився
        # Викликаємо повне оновлення блоку в preview замість зміни одного рядка
        if preview_edit and (needs_title_update or needs_preview_update): # needs_title_update означає, що текст точно змінився
             log_debug(f"Text edited handler: Updating preview for block {block_idx} due to text/problem change.")
             # Зберігаємо позицію скролбара ПЕРЕД викликом populate_strings_for_block
             old_scrollbar_value = preview_edit.verticalScrollBar().value()
             # Викликаємо повне оновлення, яке саме подбає про підсвічування
             self.ui_updater.populate_strings_for_block(block_idx)
             # Відновлюємо позицію скролбара ПІСЛЯ оновлення
             preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
        
        # Оновлюємо статус бар і синхронізуємо курсор оригінального тексту
        self.ui_updater.update_status_bar()
        self.ui_updater.synchronize_original_cursor()

    # --- Метод paste_block_text залишається без змін від попередньої версії ---
    def paste_block_text(self):
        log_debug(f"--> TextOperationHandler: paste_block_text (AGRESSIVE MODE V13) triggered.")
        if self.mw.current_block_idx == -1: QMessageBox.warning(self.mw, "Paste Error", "Please select a block."); return
        
        block_idx = self.mw.current_block_idx
        block_key = str(block_idx)
        
        self.mw.before_paste_edited_data_snapshot = dict(self.mw.edited_data)
        self.mw.before_paste_critical_problems_snapshot = { k: v.copy() for k, v in self.mw.critical_problem_lines_per_block.items() } 
        self.mw.before_paste_warning_problems_snapshot = { k: v.copy() for k, v in self.mw.warning_problem_lines_per_block.items() }   
        self.mw.before_paste_block_idx_affected = block_idx
        
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'clearAllProblemTypeHighlights'): 
            preview_edit.clearAllProblemTypeHighlights() 
        
        self.mw.critical_problem_lines_per_block.pop(block_key, None)
        self.mw.warning_problem_lines_per_block.pop(block_key, None)
        
        if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'): 
            self.ui_updater.update_block_item_text_with_problem_count(block_idx) 
            
        start_string_idx = self.mw.current_string_idx if self.mw.current_string_idx != -1 else 0
        pasted_text_raw = QApplication.clipboard().text()
        if not pasted_text_raw: QMessageBox.information(self.mw, "Paste", "Clipboard empty."); return
        
        segments_from_clipboard_raw = re.split(r'\{END\}\r?\n', pasted_text_raw)
        parsed_strings = []
        num_raw_segments = len(segments_from_clipboard_raw)
        for i, segment in enumerate(segments_from_clipboard_raw):
            cleaned_segment = segment
            if i > 0 and segment.startswith('\n'): cleaned_segment = segment[1:]
            if cleaned_segment or i < num_raw_segments - 1: parsed_strings.append(cleaned_segment)
        
        if parsed_strings and not parsed_strings[-1] and num_raw_segments > 1 and segments_from_clipboard_raw[-1] == '': 
            parsed_strings.pop()
            
        if not parsed_strings: QMessageBox.information(self.mw, "Paste", "No valid segments found."); return
        
        original_block_len = len(self.mw.data[block_idx])
        current_block_new_critical_indices = set()
        current_block_new_warning_indices = set() 
        successfully_processed_count = 0
        any_change_applied_to_data = False
        
        for i, segment_to_insert_raw in enumerate(parsed_strings):
            current_target_string_idx = start_string_idx + i
            if current_target_string_idx >= original_block_len:
                if i == 0: 
                    QMessageBox.warning(self.mw, "Paste Error", f"Cannot paste starting at line {start_string_idx + 1}. Block has {original_block_len} lines.")
                break 
            
            original_text_for_tags = self.mw.data[block_idx][current_target_string_idx]
            
            processed_text, tag_status, tag_error_msg = process_segment_tags_aggressively(
                segment_to_insert_raw, original_text_for_tags, self.mw.default_tag_mappings, self.mw.EDITOR_PLAYER_TAG
            )
            final_text_to_apply = processed_text.rstrip('\n')
            
            if self.data_processor.update_edited_data(block_idx, current_target_string_idx, final_text_to_apply):
                 self.ui_updater.update_title() 
            
            old_text_for_this_line = self.mw.before_paste_edited_data_snapshot.get((block_idx, current_target_string_idx), original_text_for_tags)
            if final_text_to_apply != old_text_for_this_line:
                 any_change_applied_to_data = True

            successfully_processed_count += 1

            if tag_status == TAG_STATUS_CRITICAL or tag_status == TAG_STATUS_UNRESOLVED_BRACKETS:
                current_block_new_critical_indices.add(current_target_string_idx)
                log_debug(f"Paste AGGRESSIVE: CRITICAL/UNRESOLVED for block {block_idx}, line {current_target_string_idx}: {tag_error_msg}")
            elif tag_status == TAG_STATUS_MISMATCHED_CURLY or tag_status == TAG_STATUS_WARNING: 
                 current_block_new_warning_indices.add(current_target_string_idx)
                 log_debug(f"Paste AGGRESSIVE: WARNING/MISMATCHED_CURLY for block {block_idx}, line {current_target_string_idx}: {tag_error_msg}")
            elif tag_status == TAG_STATUS_OK:
                 log_debug(f"Paste AGGRESSIVE: OK for block {block_idx}, line {current_target_string_idx}: No issues.")
        
        if current_block_new_critical_indices: 
            self.mw.critical_problem_lines_per_block[block_key] = self.mw.critical_problem_lines_per_block.get(block_key, set()).union(current_block_new_critical_indices)
        if current_block_new_warning_indices: 
            self.mw.warning_problem_lines_per_block[block_key] = self.mw.warning_problem_lines_per_block.get(block_key, set()).union(current_block_new_warning_indices)
        
        num_critical_total_for_block = len(self.mw.critical_problem_lines_per_block.get(block_key, set()))
        num_warning_total_for_block = len(self.mw.warning_problem_lines_per_block.get(block_key, set()))
        
        message_parts = []
        if num_critical_total_for_block > 0: message_parts.append(f"{num_critical_total_for_block} line(s) have critical issues (unresolved tags or errors, marked yellow).") 
        if num_warning_total_for_block > 0: message_parts.append(f"{num_warning_total_for_block} line(s) have warnings (e.g. mismatched {{...}} tags, marked gray).")
        
        if message_parts: 
            error_summary = (f"Pasted {successfully_processed_count} segment(s) into Block '{self.mw.block_names.get(block_key, block_key)}'.\n" + "\n".join(message_parts) + "\nPlease review.")
            QMessageBox.warning(self.mw, "Paste with Issues/Warnings", error_summary)
        elif any_change_applied_to_data:
            QMessageBox.information(self.mw, "Paste Successful", f"{successfully_processed_count} segment(s) processed and applied.")
        else: 
            QMessageBox.information(self.mw, "Paste", "Pasted text resulted in no changes to the data.")
        
        self.mw.is_programmatically_changing_text = True 
        self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
        self.ui_updater.update_block_item_text_with_problem_count(self.mw.current_block_idx) 
        self.mw.is_programmatically_changing_text = False
        
        if any_change_applied_to_data or num_critical_total_for_block > 0 or num_warning_total_for_block > 0 :
            self.mw.can_undo_paste = True
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(True)
        else:
            self.mw.can_undo_paste = False;
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(False)
            
        log_debug("<-- TextOperationHandler: paste_block_text (AGRESSIVE MODE V13) finished.")