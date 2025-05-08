import re
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtGui import QTextCursor, QTextBlock 
# Переконаймося, що QTimer імпортовано правильно
from PyQt5.QtCore import QTimer 
from handlers.base_handler import BaseHandler
from utils import log_debug, convert_dots_to_spaces_from_editor, convert_spaces_to_dots_for_display 
# Перевіряємо цей імпорт
from tag_utils import apply_default_mappings_only, analyze_tags_for_issues, \
                      process_segment_tags_aggressively, \
                      TAG_STATUS_OK, TAG_STATUS_CRITICAL, \
                      TAG_STATUS_MISMATCHED_CURLY, TAG_STATUS_UNRESOLVED_BRACKETS, \
                      TAG_STATUS_WARNING

PREVIEW_UPDATE_DELAY = 250 

# Перевіряємо визначення класу
class TextOperationHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self.preview_update_timer = QTimer()
        self.preview_update_timer.setSingleShot(True) 
        self.preview_update_timer.timeout.connect(self._update_preview_content)

    def _update_preview_content(self):
        log_debug("Timer timeout: Updating preview content.")
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        old_scrollbar_value = preview_edit.verticalScrollBar().value() if preview_edit else 0
        self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
        if preview_edit: preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
        log_debug("Preview content update finished.")

    def text_edited(self):
        if self.mw.is_programmatically_changing_text: return 
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1: return
        
        block_idx = self.mw.current_block_idx
        string_idx_in_block = self.mw.current_string_idx
        block_key = str(block_idx)
        
        text_from_ui_with_dots = self.mw.edited_text_edit.toPlainText() 
        actual_text_with_spaces = convert_dots_to_spaces_from_editor(text_from_ui_with_dots) if self.mw.show_multiple_spaces_as_dots else text_from_ui_with_dots
        
        needs_title_update = self.data_processor.update_edited_data(block_idx, string_idx_in_block, actual_text_with_spaces)
        if needs_title_update: 
            self.ui_updater.update_title()
            
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        problems_updated = False 

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
                
                if state_changed:
                    problems_updated = True 
                    if crit_problems: self.mw.critical_problem_lines_per_block[block_key] = crit_problems
                    elif block_key in self.mw.critical_problem_lines_per_block: del self.mw.critical_problem_lines_per_block[block_key]
                    if warn_problems: self.mw.warning_problem_lines_per_block[block_key] = warn_problems
                    elif block_key in self.mw.warning_problem_lines_per_block: del self.mw.warning_problem_lines_per_block[block_key]
                    
                    if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'): 
                        self.ui_updater.update_block_item_text_with_problem_count(block_idx)

        self.preview_update_timer.start(PREVIEW_UPDATE_DELAY)
        self.ui_updater.update_status_bar()
        self.ui_updater.synchronize_original_cursor()

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

        if successfully_processed_count > 0:
             log_debug(f"Paste block finished. Triggering silent rescan for block {block_idx}.")
             if hasattr(self.mw, 'app_action_handler') and hasattr(self.mw.app_action_handler, 'rescan_tags_for_single_block'):
                  self.mw.app_action_handler.rescan_tags_for_single_block(block_idx, show_message=False)
             else:
                  log_debug("Could not find rescan_tags_for_single_block method.")
        
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

    def revert_single_line(self, line_index: int):
        block_idx = self.mw.current_block_idx
        if block_idx == -1:
             log_debug("Revert single line: No block selected.")
             return
             
        log_debug(f"Attempting to revert line {line_index} in block {block_idx} to original.")
             
        original_text = self.data_processor._get_string_from_source(block_idx, line_index, self.mw.data, "original_for_revert")
        
        if original_text is None:
            log_debug(f"Revert single line: Could not find original text for line {line_index} in block {block_idx}.")
            QMessageBox.warning(self.mw, "Revert Error", f"Could not find original text for line {line_index + 1}.")
            return

        current_text, _ = self.data_processor.get_current_string_text(block_idx, line_index)
        
        if current_text == original_text:
             log_debug(f"Revert single line: Line {line_index} in block {block_idx} already matches original.")
             return

        if self.data_processor.update_edited_data(block_idx, line_index, original_text):
             self.ui_updater.update_title() 

        block_key = str(block_idx)
        tag_status, _ = analyze_tags_for_issues(original_text, original_text, self.mw.EDITOR_PLAYER_TAG) 
        
        crit_problems = self.mw.critical_problem_lines_per_block.get(block_key, set()).copy()
        warn_problems = self.mw.warning_problem_lines_per_block.get(block_key, set()).copy()
        problems_updated = False

        should_be_crit = False 
        should_be_warn = (tag_status == TAG_STATUS_MISMATCHED_CURLY) 

        if not should_be_crit and line_index in crit_problems:
            crit_problems.discard(line_index)
            problems_updated = True
        
        if should_be_warn:
             if line_index not in warn_problems:
                 warn_problems.add(line_index)
                 problems_updated = True
        elif line_index in warn_problems:
             warn_problems.discard(line_index)
             problems_updated = True

        if problems_updated:
            if crit_problems: self.mw.critical_problem_lines_per_block[block_key] = crit_problems
            elif block_key in self.mw.critical_problem_lines_per_block: del self.mw.critical_problem_lines_per_block[block_key]
            if warn_problems: self.mw.warning_problem_lines_per_block[block_key] = warn_problems
            elif block_key in self.mw.warning_problem_lines_per_block: del self.mw.warning_problem_lines_per_block[block_key]
            
        if self.mw.current_string_idx == line_index:
             self.ui_updater.update_text_views()
        
        self.mw.is_programmatically_changing_text = True
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        old_scrollbar_value = preview_edit.verticalScrollBar().value() if preview_edit else 0
        self.ui_updater.populate_strings_for_block(block_idx)
        if preview_edit: preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
        
        if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
             self.ui_updater.update_block_item_text_with_problem_count(block_idx)
        self.mw.is_programmatically_changing_text = False

        if hasattr(self.mw, 'statusBar'):
             self.mw.statusBar.showMessage(f"Line {line_index + 1} reverted to original.", 2000)