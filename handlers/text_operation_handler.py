import re
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtGui import QTextCursor, QTextBlock
from PyQt5.QtCore import QTimer
from .base_handler import BaseHandler
from utils.utils import log_debug, convert_dots_to_spaces_from_editor, convert_spaces_to_dots_for_display, calculate_string_width, remove_all_tags, SPACE_DOT_SYMBOL
from core.tag_utils import apply_default_mappings_only, analyze_tags_for_issues, \
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
        
        main_window_ref = self.mw
        was_programmatically_changing = main_window_ref.is_programmatically_changing_text
        main_window_ref.is_programmatically_changing_text = True
        
        log_debug(f"  _update_preview_content: Set is_programmatically_changing_text to True (was {was_programmatically_changing})")

        self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
        
        if preview_edit: preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
        if original_edit and hasattr(original_edit, 'lineNumberArea'): original_edit.lineNumberArea.update()
        if edited_edit and hasattr(edited_edit, 'lineNumberArea'): edited_edit.lineNumberArea.update()

        main_window_ref.is_programmatically_changing_text = was_programmatically_changing
        log_debug(f"  _update_preview_content: Restored is_programmatically_changing_text to {was_programmatically_changing}")
        log_debug("Preview content update finished.")

    def _check_and_update_width_exceeded_status(self, block_idx: int, string_idx: int, text_to_check: str):
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

    def _determine_if_data_string_is_short(self, data_string_text: str) -> bool:
        sub_lines = str(data_string_text).split('\n')
        if len(sub_lines) <= 1:
            return False 

        sentence_end_chars = ('.', '!', '?')
        space_width = calculate_string_width(" ", self.mw.font_map)

        for sub_line_idx, current_sub_line_text in enumerate(sub_lines):
            if sub_line_idx == len(sub_lines) - 1: 
                break

            current_sub_line_clean_stripped = remove_all_tags(current_sub_line_text).strip()
            if not current_sub_line_clean_stripped:
                continue
            if current_sub_line_clean_stripped.endswith(sentence_end_chars):
                continue

            next_sub_line_text = sub_lines[sub_line_idx + 1]
            next_sub_line_clean_stripped = remove_all_tags(next_sub_line_text).strip()
            if not next_sub_line_clean_stripped:
                continue

            first_word_next_sub_line = next_sub_line_clean_stripped.split(maxsplit=1)[0] if next_sub_line_clean_stripped else ""
            if not first_word_next_sub_line:
                continue
            
            first_word_next_width = calculate_string_width(first_word_next_sub_line, self.mw.font_map)
            if first_word_next_width > 0:
                current_sub_line_pixel_width = calculate_string_width(remove_all_tags(current_sub_line_text), self.mw.font_map)
                remaining_width = self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS - current_sub_line_pixel_width
                if remaining_width >= (first_word_next_width + space_width):
                    return True 
        return False

    def _check_and_update_short_line_status_for_data_string(self, block_idx: int, string_idx: int, data_string_text: str) -> bool:
        block_key = str(block_idx)
        is_short = self._determine_if_data_string_is_short(data_string_text)
        
        short_lines_set = self.mw.short_lines_per_block.get(block_key, set()).copy()
        state_changed = False

        if is_short:
            if string_idx not in short_lines_set:
                short_lines_set.add(string_idx)
                state_changed = True
        else:
            if string_idx in short_lines_set:
                short_lines_set.discard(string_idx)
                state_changed = True
        
        if state_changed:
            if short_lines_set:
                self.mw.short_lines_per_block[block_key] = short_lines_set
            elif block_key in self.mw.short_lines_per_block:
                del self.mw.short_lines_per_block[block_key]
        return state_changed

    def text_edited(self):
        log_debug(f"TextOperationHandler.text_edited: Start. Programmatic change? {self.mw.is_programmatically_changing_text}")
        if self.mw.is_programmatically_changing_text:
            log_debug("TextOperationHandler.text_edited: Is programmatic, returning.")
            return
        
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            log_debug("TextOperationHandler.text_edited: No block/string selected, returning.")
            return
        
        block_idx = self.mw.current_block_idx
        string_idx_in_block = self.mw.current_string_idx
        block_key = str(block_idx)
        
        text_from_ui_with_dots = self.mw.edited_text_edit.toPlainText()
        actual_text_with_spaces = convert_dots_to_spaces_from_editor(text_from_ui_with_dots) if self.mw.show_multiple_spaces_as_dots else text_from_ui_with_dots
        
        needs_title_update = self.data_processor.update_edited_data(block_idx, string_idx_in_block, actual_text_with_spaces)
        if needs_title_update:
            self.ui_updater.update_title()
            
        problems_updated_for_block_list = False

        original_text_for_comparison = self.data_processor._get_string_from_source(block_idx, string_idx_in_block, self.mw.data, "original_for_text_edited_check")
        if original_text_for_comparison is not None:
            tag_status, _ = analyze_tags_for_issues(actual_text_with_spaces, original_text_for_comparison, self.mw.EDITOR_PLAYER_TAG)
            crit_problems = self.mw.critical_problem_lines_per_block.get(block_key, set()).copy()
            warn_problems = self.mw.warning_problem_lines_per_block.get(block_key, set()).copy()
            
            is_crit_before = string_idx_in_block in crit_problems
            is_warn_before = string_idx_in_block in warn_problems
            should_be_crit = (tag_status == TAG_STATUS_UNRESOLVED_BRACKETS)
            should_be_warn = (tag_status == TAG_STATUS_MISMATCHED_CURLY)    
            
            tag_state_changed = False
            if should_be_crit:
                if not is_crit_before: crit_problems.add(string_idx_in_block); tag_state_changed = True
                if is_warn_before: warn_problems.discard(string_idx_in_block); tag_state_changed = True
            elif should_be_warn:
                if not is_warn_before: warn_problems.add(string_idx_in_block); tag_state_changed = True
                if is_crit_before: crit_problems.discard(string_idx_in_block); tag_state_changed = True
            else:
                if is_crit_before: crit_problems.discard(string_idx_in_block); tag_state_changed = True
                if is_warn_before: warn_problems.discard(string_idx_in_block); tag_state_changed = True
            
            if tag_state_changed:
                problems_updated_for_block_list = True
                if crit_problems: self.mw.critical_problem_lines_per_block[block_key] = crit_problems
                elif block_key in self.mw.critical_problem_lines_per_block: del self.mw.critical_problem_lines_per_block[block_key]
                if warn_problems: self.mw.warning_problem_lines_per_block[block_key] = warn_problems
                elif block_key in self.mw.warning_problem_lines_per_block: del self.mw.warning_problem_lines_per_block[block_key]
        
        width_state_changed = self._check_and_update_width_exceeded_status(block_idx, string_idx_in_block, actual_text_with_spaces)
        if width_state_changed:
            problems_updated_for_block_list = True
        
        short_line_state_changed_current = self._check_and_update_short_line_status_for_data_string(block_idx, string_idx_in_block, actual_text_with_spaces)
        if short_line_state_changed_current:
            problems_updated_for_block_list = True
        
        if problems_updated_for_block_list and hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
            self.ui_updater.update_block_item_text_with_problem_count(block_idx)
        
        if hasattr(self.ui_updater, '_apply_empty_odd_subline_highlights_to_edited_text'):
            self.ui_updater._apply_empty_odd_subline_highlights_to_edited_text()

        self.preview_update_timer.start(PREVIEW_UPDATE_DELAY)
        self.ui_updater.update_status_bar() 
        self.ui_updater.synchronize_original_cursor()
        
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if edited_edit and hasattr(edited_edit, 'lineNumberArea'):
            edited_edit.lineNumberArea.update()
        log_debug(f"TextOperationHandler.text_edited: End. Final undoAvailable = {self.mw.edited_text_edit.document().isUndoAvailable()}")


    def paste_block_text(self):
        log_debug(f"--> TextOperationHandler: paste_block_text triggered.")
        if self.mw.current_block_idx == -1: QMessageBox.warning(self.mw, "Paste Error", "Please select a block."); return
        
        block_idx = self.mw.current_block_idx
        block_key = str(block_idx)
        
        self.mw.before_paste_edited_data_snapshot = dict(self.mw.edited_data)
        self.mw.before_paste_critical_problems_snapshot = { k: v.copy() for k, v in self.mw.critical_problem_lines_per_block.items() }
        self.mw.before_paste_warning_problems_snapshot = { k: v.copy() for k, v in self.mw.warning_problem_lines_per_block.items() }
        self.mw.before_paste_width_exceeded_snapshot = { k: v.copy() for k, v in self.mw.width_exceeded_lines_per_block.items() }
        self.mw.before_paste_short_lines_snapshot = { k: v.copy() for k, v in self.mw.short_lines_per_block.items()}
        self.mw.before_paste_block_idx_affected = block_idx
        
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'clearAllProblemTypeHighlights'):
            preview_edit.clearAllProblemTypeHighlights()
        
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if edited_edit:
            edited_edit.clearAllProblemTypeHighlights()
            if hasattr(edited_edit, 'clearEmptyOddSublineHighlights'):
                edited_edit.clearEmptyOddSublineHighlights()

        self.mw.critical_problem_lines_per_block.pop(block_key, None)
        self.mw.warning_problem_lines_per_block.pop(block_key, None)
        self.mw.width_exceeded_lines_per_block.pop(block_key, None)
        self.mw.short_lines_per_block.pop(block_key, None)
        
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
        
        affected_string_indices = set()

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
            affected_string_indices.add(current_target_string_idx)
            
            old_text_for_this_line = self.mw.before_paste_edited_data_snapshot.get((block_idx, current_target_string_idx), original_text_for_tags)
            if final_text_to_apply != old_text_for_this_line:
                 any_change_applied_to_data = True
            successfully_processed_count += 1

        if successfully_processed_count > 0:
             log_debug(f"Paste block finished. Triggering silent rescan for block {block_idx} due to paste.")
             self.mw.app_action_handler._perform_issues_scan_for_block(block_idx, is_single_block_scan=True, use_default_mappings_in_scan=False)
        
        num_critical_total_for_block = len(self.mw.critical_problem_lines_per_block.get(block_key, set()))
        num_warning_total_for_block = len(self.mw.warning_problem_lines_per_block.get(block_key, set()))
        num_width_exceeded_total_for_block = len(self.mw.width_exceeded_lines_per_block.get(block_key, set()))
        num_short_lines_total_for_block = len(self.mw.short_lines_per_block.get(block_key, set()))
        
        message_parts = []
        if num_critical_total_for_block > 0: message_parts.append(f"{num_critical_total_for_block} line(s) have critical tag issues.")
        if num_warning_total_for_block > 0: message_parts.append(f"{num_warning_total_for_block} line(s) have tag warnings.")
        if num_width_exceeded_total_for_block > 0: message_parts.append(f"{num_width_exceeded_total_for_block} line(s) exceed width limit ({self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS}px).")
        if num_short_lines_total_for_block > 0: message_parts.append(f"{num_short_lines_total_for_block} line(s) are potentially too short.")
        
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
        
        if any_change_applied_to_data or num_critical_total_for_block > 0 or num_warning_total_for_block > 0 or num_width_exceeded_total_for_block > 0 or num_short_lines_total_for_block > 0 :
            self.mw.can_undo_paste = True
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(True)
        else:
            self.mw.can_undo_paste = False;
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(False)
            
        log_debug("<-- TextOperationHandler: paste_block_text finished.")

    def revert_single_line(self, line_index: int):
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

        self.mw.app_action_handler._perform_issues_scan_for_block(block_idx, is_single_block_scan=True, use_default_mappings_in_scan=False)
        
        if self.mw.current_string_idx == line_index: 
             self.ui_updater.update_text_views() 
        
        self.mw.is_programmatically_changing_text = True
        self.ui_updater.populate_strings_for_block(block_idx) 
        self.ui_updater.update_block_item_text_with_problem_count(block_idx) 
        self.mw.is_programmatically_changing_text = False

        if hasattr(self.mw, 'statusBar'):
             self.mw.statusBar.showMessage(f"Data line {line_index + 1} reverted to original.", 2000)
        
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
        space_width = calculate_string_width(" ", self.mw.font_map)
        sentence_end_chars = ('.', '!', '?')
        
        info_parts = [f"Data Line {data_line_idx + 1} (Block {self.mw.current_block_idx}):\nMax Allowed Width (Game Dialog): {max_allowed_width}px\nWidth Warning Threshold (Editor): {warning_threshold}px\n"]

        info_parts.append(f"--- Current Text (Source: {source}) ---")
        sub_lines_current = str(current_text_data_line).split('\n')
        total_width_current = calculate_string_width(remove_all_tags(str(current_text_data_line).replace('\n','')), self.mw.font_map)
        info_parts.append(f"Total (game-like, no newlines): {total_width_current}px")
        for i, sub_line in enumerate(sub_lines_current):
            sub_line_no_tags = remove_all_tags(sub_line)
            width_px = calculate_string_width(sub_line_no_tags, self.mw.font_map)
            status = "OK"
            short_status = ""
            if width_px > warning_threshold: status = "EXCEEDED (Editor)"

            if i < len(sub_lines_current) - 1 : 
                current_sub_line_no_tags_stripped_calc = remove_all_tags(sub_line).strip()
                if current_sub_line_no_tags_stripped_calc and not current_sub_line_no_tags_stripped_calc.endswith(sentence_end_chars):
                    next_sub_line_text_calc = sub_lines_current[i+1]
                    next_sub_line_clean_stripped_calc = remove_all_tags(next_sub_line_text_calc).strip()
                    if next_sub_line_clean_stripped_calc:
                        first_word_next_sub_line_calc = next_sub_line_clean_stripped_calc.split(maxsplit=1)[0] if next_sub_line_clean_stripped_calc else ""
                        if first_word_next_sub_line_calc:
                            first_word_next_line_width_calc = calculate_string_width(first_word_next_sub_line_calc, self.mw.font_map)
                            if first_word_next_line_width_calc > 0:
                                remaining_width_calc = max_allowed_width - width_px
                                if remaining_width_calc >= (first_word_next_line_width_calc + space_width):
                                    short_status = f"SHORT (can fit {first_word_next_line_width_calc + space_width}px, has {remaining_width_calc}px)"
            info_parts.append(f"  Sub-line {i+1}: {width_px}px (Status: {status}) {short_status} '{sub_line_no_tags[:40]}...'")
        
        info_parts.append(f"\n--- Original Text ---")
        sub_lines_original = str(original_text_data_line).split('\n')
        original_total_game_width = calculate_string_width(remove_all_tags(str(original_text_data_line).replace('\n','')), self.mw.font_map)
        info_parts.append(f"Total (game-like, no newlines): {original_total_game_width}px")
        for i, sub_line in enumerate(sub_lines_original):
            sub_line_no_tags = remove_all_tags(sub_line)
            width_px = calculate_string_width(sub_line_no_tags, self.mw.font_map)
            status = "OK"
            short_status_orig = ""
            if width_px > warning_threshold: status = "EXCEEDED (Editor)"

            if i < len(sub_lines_original) -1:
                original_sub_line_no_tags_stripped_calc = remove_all_tags(sub_line).strip()
                if original_sub_line_no_tags_stripped_calc and not original_sub_line_no_tags_stripped_calc.endswith(sentence_end_chars):
                    next_original_sub_line_text_calc = sub_lines_original[i+1]
                    next_original_sub_line_clean_stripped_calc = remove_all_tags(next_original_sub_line_text_calc).strip()
                    if next_original_sub_line_clean_stripped_calc:
                        first_word_next_original_sub_line_calc = next_original_sub_line_clean_stripped_calc.split(maxsplit=1)[0] if next_original_sub_line_clean_stripped_calc else ""
                        if first_word_next_original_sub_line_calc:
                            first_word_next_original_line_width_calc = calculate_string_width(first_word_next_original_sub_line_calc, self.mw.font_map)
                            if first_word_next_original_line_width_calc > 0:
                                remaining_width_orig_calc = max_allowed_width - width_px
                                if remaining_width_orig_calc >= (first_word_next_original_line_width_calc + space_width):
                                    short_status_orig = f"SHORT (can fit {first_word_next_original_line_width_calc+space_width}px, has {remaining_width_orig_calc}px)"
            info_parts.append(f"  Sub-line {i+1}: {width_px}px (Status: {status}) {short_status_orig} '{sub_line_no_tags[:40]}...'")

        QMessageBox.information(self.mw, "Line Width Calculation", "\n".join(info_parts))
        log_debug(f"<-- TextOperationHandler: calculate_width_for_data_line_action finished.")