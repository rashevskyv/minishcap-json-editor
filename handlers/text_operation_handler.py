import re
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtGui import QTextCursor, QTextBlock 
from PyQt5.QtCore import QTimer 
from handlers.base_handler import BaseHandler
from utils import log_debug, convert_dots_to_spaces_from_editor, convert_spaces_to_dots_for_display, calculate_string_width, remove_all_tags
from tag_utils import apply_default_mappings_only, analyze_tags_for_issues, \
                      process_segment_tags_aggressively, \
                      TAG_STATUS_OK, TAG_STATUS_CRITICAL, \
                      TAG_STATUS_MISMATCHED_CURLY, TAG_STATUS_UNRESOLVED_BRACKETS, \
                      TAG_STATUS_WARNING

PREVIEW_UPDATE_DELAY = 250 

class TextOperationHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self.preview_update_timer = QTimer()
        self.preview_update_timer.setSingleShot(True) 
        self.preview_update_timer.timeout.connect(self._update_preview_content)

    def _update_preview_content(self):
        log_debug("Timer timeout: Updating preview content.")
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        original_edit = getattr(self.mw, 'original_text_edit', None)
        edited_edit = getattr(self.mw, 'edited_text_edit', None)

        old_scrollbar_value = preview_edit.verticalScrollBar().value() if preview_edit else 0
        
        # populate_strings_for_block тепер буде обробляти всі типи підсвічувань, включно з width_exceeded
        self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
        
        if preview_edit: preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
        # Оновлюємо LineNumberArea для original/edited, щоб перемалювати ширину
        if original_edit and hasattr(original_edit, 'lineNumberArea'): original_edit.lineNumberArea.update()
        if edited_edit and hasattr(edited_edit, 'lineNumberArea'): edited_edit.lineNumberArea.update()

        log_debug("Preview content update finished.")

    def _check_and_update_width_exceeded_status(self, block_idx: int, string_idx: int, text_to_check: str):
        """Перевіряє ширину рядка та оновлює self.mw.width_exceeded_lines_per_block."""
        block_key = str(block_idx)
        sub_lines = str(text_to_check).split('\n')
        line_exceeds_width = False
        for sub_line_text in sub_lines:
            pixel_width = calculate_string_width(remove_all_tags(sub_line_text), self.mw.font_map)
            if pixel_width > self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS:
                line_exceeds_width = True
                break
        
        width_exceeded_set = self.mw.width_exceeded_lines_per_block.get(block_key, set()).copy()
        state_changed = False
        if line_exceeds_width:
            if string_idx not in width_exceeded_set:
                width_exceeded_set.add(string_idx)
                state_changed = True
        else:
            if string_idx in width_exceeded_set:
                width_exceeded_set.discard(string_idx)
                state_changed = True
        
        if state_changed:
            if width_exceeded_set:
                self.mw.width_exceeded_lines_per_block[block_key] = width_exceeded_set
            elif block_key in self.mw.width_exceeded_lines_per_block:
                del self.mw.width_exceeded_lines_per_block[block_key]
        return state_changed


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
        problems_updated_for_block_list = False 

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
                
                tag_state_changed_for_block_list = False
                if should_be_crit:
                    if not is_crit_before: crit_problems.add(string_idx_in_block); tag_state_changed_for_block_list = True
                    if is_warn_before: warn_problems.discard(string_idx_in_block); tag_state_changed_for_block_list = True # Crit overrides warn
                elif should_be_warn:
                    if not is_warn_before: warn_problems.add(string_idx_in_block); tag_state_changed_for_block_list = True
                    if is_crit_before: crit_problems.discard(string_idx_in_block); tag_state_changed_for_block_list = True # If no longer crit, but now warn
                else: # No tag problems
                    if is_crit_before: crit_problems.discard(string_idx_in_block); tag_state_changed_for_block_list = True
                    if is_warn_before: warn_problems.discard(string_idx_in_block); tag_state_changed_for_block_list = True
                
                if tag_state_changed_for_block_list:
                    problems_updated_for_block_list = True 
                    if crit_problems: self.mw.critical_problem_lines_per_block[block_key] = crit_problems
                    elif block_key in self.mw.critical_problem_lines_per_block: del self.mw.critical_problem_lines_per_block[block_key]
                    if warn_problems: self.mw.warning_problem_lines_per_block[block_key] = warn_problems
                    elif block_key in self.mw.warning_problem_lines_per_block: del self.mw.warning_problem_lines_per_block[block_key]
            
            # Перевірка ширини
            width_state_changed_for_block_list = self._check_and_update_width_exceeded_status(block_idx, string_idx_in_block, actual_text_with_spaces)
            if width_state_changed_for_block_list:
                problems_updated_for_block_list = True
                    
            if problems_updated_for_block_list and hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'): 
                self.ui_updater.update_block_item_text_with_problem_count(block_idx)

        self.preview_update_timer.start(PREVIEW_UPDATE_DELAY) # Це оновить preview_text_edit з усіма підсвітками
        self.ui_updater.update_status_bar()
        self.ui_updater.synchronize_original_cursor()
        
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if edited_edit and hasattr(edited_edit, 'lineNumberArea'): 
            edited_edit.lineNumberArea.update()


    def paste_block_text(self):
        log_debug(f"--> TextOperationHandler: paste_block_text (AGRESSIVE MODE V13) triggered.")
        if self.mw.current_block_idx == -1: QMessageBox.warning(self.mw, "Paste Error", "Please select a block."); return
        
        block_idx = self.mw.current_block_idx
        block_key = str(block_idx)
        
        self.mw.before_paste_edited_data_snapshot = dict(self.mw.edited_data)
        self.mw.before_paste_critical_problems_snapshot = { k: v.copy() for k, v in self.mw.critical_problem_lines_per_block.items() } 
        self.mw.before_paste_warning_problems_snapshot = { k: v.copy() for k, v in self.mw.warning_problem_lines_per_block.items() }   
        self.mw.before_paste_width_exceeded_snapshot = { k: v.copy() for k, v in self.mw.width_exceeded_lines_per_block.items() }
        self.mw.before_paste_block_idx_affected = block_idx
        
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'clearAllProblemTypeHighlights'): 
            preview_edit.clearAllProblemTypeHighlights() 
        
        # Очищаємо всі проблеми для поточного блоку перед вставкою
        self.mw.critical_problem_lines_per_block.pop(block_key, None)
        self.mw.warning_problem_lines_per_block.pop(block_key, None)
        self.mw.width_exceeded_lines_per_block.pop(block_key, None)
        
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
            # Після оновлення даних, перевіряємо теги та ширину для цього конкретного рядка
            # Теги будуть перевірені в rescan_tags_for_single_block нижче
            # Ширину перевіряємо тут, щоб правильно встановити before_paste_width_exceeded_snapshot
            self._check_and_update_width_exceeded_status(block_idx, current_target_string_idx, final_text_to_apply)


        if successfully_processed_count > 0:
             log_debug(f"Paste block finished. Triggering silent rescan for block {block_idx}.")
             if hasattr(self.mw, 'app_action_handler') and hasattr(self.mw.app_action_handler, 'rescan_issues_for_single_block'):
                  # Використовуємо новий метод, який сканує всі типи проблем
                  self.mw.app_action_handler.rescan_issues_for_single_block(block_idx, show_message_on_completion=False)
             else:
                  log_debug("Could not find rescan_issues_for_single_block method.")
        
        num_critical_total_for_block = len(self.mw.critical_problem_lines_per_block.get(block_key, set()))
        num_warning_total_for_block = len(self.mw.warning_problem_lines_per_block.get(block_key, set()))
        num_width_exceeded_total_for_block = len(self.mw.width_exceeded_lines_per_block.get(block_key, set()))
        
        message_parts = []
        if num_critical_total_for_block > 0: message_parts.append(f"{num_critical_total_for_block} line(s) have critical tag issues.") 
        if num_warning_total_for_block > 0: message_parts.append(f"{num_warning_total_for_block} line(s) have tag warnings.")
        if num_width_exceeded_total_for_block > 0: message_parts.append(f"{num_width_exceeded_total_for_block} line(s) exceed width limit ({self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS}px).")
        
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
        
        if any_change_applied_to_data or num_critical_total_for_block > 0 or num_warning_total_for_block > 0 or num_width_exceeded_total_for_block > 0:
            self.mw.can_undo_paste = True
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(True)
        else:
            self.mw.can_undo_paste = False;
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(False)
            
        log_debug("<-- TextOperationHandler: paste_block_text (AGRESSIVE MODE V13) finished.")

    def revert_single_line(self, line_index: int): # line_index тут - це індекс рядка даних
        block_idx = self.mw.current_block_idx
        if block_idx == -1:
             log_debug("Revert single line: No block selected.")
             return
             
        log_debug(f"Attempting to revert data line {line_index} in block {block_idx} to original.")
             
        original_text = self.data_processor._get_string_from_source(block_idx, line_index, self.mw.data, "original_for_revert")
        
        if original_text is None:
            log_debug(f"Revert single line: Could not find original text for data line {line_index} in block {block_idx}.")
            QMessageBox.warning(self.mw, "Revert Error", f"Could not find original text for data line {line_index + 1}.")
            return

        current_text, _ = self.data_processor.get_current_string_text(block_idx, line_index)
        
        if current_text == original_text:
             log_debug(f"Revert single line: Data line {line_index} in block {block_idx} already matches original.")
             return

        if self.data_processor.update_edited_data(block_idx, line_index, original_text):
             self.ui_updater.update_title() 

        block_key = str(block_idx)
        # Перевірка тегів
        tag_status, _ = analyze_tags_for_issues(original_text, original_text, self.mw.EDITOR_PLAYER_TAG) 
        crit_problems = self.mw.critical_problem_lines_per_block.get(block_key, set()).copy()
        warn_problems = self.mw.warning_problem_lines_per_block.get(block_key, set()).copy()
        problems_updated = False
        should_be_crit = False 
        should_be_warn = (tag_status == TAG_STATUS_MISMATCHED_CURLY) 
        if not should_be_crit and line_index in crit_problems: crit_problems.discard(line_index); problems_updated = True
        if should_be_warn:
             if line_index not in warn_problems: warn_problems.add(line_index); problems_updated = True
        elif line_index in warn_problems: warn_problems.discard(line_index); problems_updated = True
        if problems_updated:
            if crit_problems: self.mw.critical_problem_lines_per_block[block_key] = crit_problems
            elif block_key in self.mw.critical_problem_lines_per_block: del self.mw.critical_problem_lines_per_block[block_key]
            if warn_problems: self.mw.warning_problem_lines_per_block[block_key] = warn_problems
            elif block_key in self.mw.warning_problem_lines_per_block: del self.mw.warning_problem_lines_per_block[block_key]
        
        # Перевірка ширини
        width_state_changed = self._check_and_update_width_exceeded_status(block_idx, line_index, original_text)
        if width_state_changed: problems_updated = True # Якщо будь-яка проблема змінилася, треба оновити список блоків

        if self.mw.current_string_idx == line_index:
             self.ui_updater.update_text_views() # Це оновить original/edited, включно з їх LineNumberArea
        
        self.mw.is_programmatically_changing_text = True
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        old_scrollbar_value = preview_edit.verticalScrollBar().value() if preview_edit else 0
        self.ui_updater.populate_strings_for_block(block_idx) # Це оновить preview з усіма підсвітками
        if preview_edit: preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
        
        if problems_updated and hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
             self.ui_updater.update_block_item_text_with_problem_count(block_idx)
        self.mw.is_programmatically_changing_text = False

        if hasattr(self.mw, 'statusBar'):
             self.mw.statusBar.showMessage(f"Data line {line_index + 1} reverted to original.", 2000)
        
        # Додатково оновлюємо LineNumberArea для original/edited, якщо активний рядок був змінений
        if self.mw.current_string_idx == line_index:
            original_edit = getattr(self.mw, 'original_text_edit', None)
            edited_edit = getattr(self.mw, 'edited_text_edit', None)
            if original_edit and hasattr(original_edit, 'lineNumberArea'): original_edit.lineNumberArea.update()
            if edited_edit and hasattr(edited_edit, 'lineNumberArea'): edited_edit.lineNumberArea.update()


    def calculate_width_for_data_line_action(self, data_line_idx: int):
        log_debug(f"--> TextOperationHandler: calculate_width_for_data_line_action. Data Line: {data_line_idx}")
        if self.mw.current_block_idx == -1 or data_line_idx < 0:
            QMessageBox.warning(self.mw, "Calculate Width Error", "No block or data line selected.")
            return

        current_text_data_line, source = self.data_processor.get_current_string_text(self.mw.current_block_idx, data_line_idx)
        original_text_data_line = self.data_processor._get_string_from_source(self.mw.current_block_idx, data_line_idx, self.mw.data, "width_calc_original_data_line")

        if current_text_data_line is None and original_text_data_line is None:
            QMessageBox.warning(self.mw, "Calculate Width Error", f"Could not retrieve text for data line {data_line_idx + 1}.")
            return
        
        if not self.mw.font_map:
             QMessageBox.warning(self.mw, "Calculate Width Error", "Font map is not loaded. Cannot calculate width.")
             return

        max_allowed_width = self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS
        warning_threshold = self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS
        
        info_parts = [f"Data Line {data_line_idx + 1} (Block {self.mw.current_block_idx}):\nMax Allowed Width (Game Dialog): {max_allowed_width}px\nWidth Warning Threshold (Editor): {warning_threshold}px\n"]

        # Поточний текст
        info_parts.append(f"--- Current Text (Source: {source}) ---")
        sub_lines_current = str(current_text_data_line).split('\n')
        total_width_current = calculate_string_width(remove_all_tags(str(current_text_data_line).replace('\n','')), self.mw.font_map) # Загальна без \n для порівняння з грою
        info_parts.append(f"Total (game-like, no newlines): {total_width_current}px")
        for i, sub_line in enumerate(sub_lines_current):
            sub_line_no_tags = remove_all_tags(sub_line)
            width_px = calculate_string_width(sub_line_no_tags, self.mw.font_map)
            status = "OK"
            if width_px > warning_threshold: status = "EXCEEDED (Editor)"
            info_parts.append(f"  Sub-line {i+1}: {width_px}px (Status: {status}) '{sub_line_no_tags[:40]}...'")
        
        # Оригінальний текст
        info_parts.append(f"\n--- Original Text ---")
        sub_lines_original = str(original_text_data_line).split('\n')
        total_width_original = calculate_string_width(remove_all_tags(str(original_text_data_line).replace('\n','')), self.mw.font_map)
        info_parts.append(f"Total (game-like, no newlines): {total_width_original}px")
        for i, sub_line in enumerate(sub_lines_original):
            sub_line_no_tags = remove_all_tags(sub_line)
            width_px = calculate_string_width(sub_line_no_tags, self.mw.font_map)
            status = "OK"
            if width_px > warning_threshold: status = "EXCEEDED (Editor)"
            info_parts.append(f"  Sub-line {i+1}: {width_px}px (Status: {status}) '{sub_line_no_tags[:40]}...'")

        QMessageBox.information(self.mw, "Line Width Calculation", "\n".join(info_parts))
        log_debug(f"<-- TextOperationHandler: calculate_width_for_data_line_action finished.")