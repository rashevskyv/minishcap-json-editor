import re
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtGui import QTextCursor, QTextBlock
from PyQt5.QtCore import QTimer
from .base_handler import BaseHandler
from utils.utils import log_debug, convert_dots_to_spaces_from_editor, convert_spaces_to_dots_for_display, calculate_string_width, remove_all_tags, SPACE_DOT_SYMBOL, ALL_TAGS_PATTERN
from core.tag_utils import process_segment_tags_aggressively

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
        
        self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
        
        if preview_edit: preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
        if original_edit and hasattr(original_edit, 'lineNumberArea'): original_edit.lineNumberArea.update()
        if edited_edit and hasattr(edited_edit, 'lineNumberArea'): edited_edit.lineNumberArea.update()

        main_window_ref.is_programmatically_changing_text = was_programmatically_changing
        log_debug("Preview content update finished.")

    def text_edited(self):
        log_debug(f"TextOperationHandler.text_edited: Start. Programmatic change? {self.mw.is_programmatically_changing_text}")
        if self.mw.is_programmatically_changing_text:
            return
        
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            return
        
        block_idx = self.mw.current_block_idx
        string_idx_in_block = self.mw.current_string_idx
        
        text_from_ui_with_dots = self.mw.edited_text_edit.toPlainText()
        actual_text_with_spaces = convert_dots_to_spaces_from_editor(text_from_ui_with_dots) if self.mw.show_multiple_spaces_as_dots else text_from_ui_with_dots
        
        needs_title_update = self.data_processor.update_edited_data(block_idx, string_idx_in_block, actual_text_with_spaces)
        if needs_title_update:
            self.ui_updater.update_title()
            
        if hasattr(self.mw.app_action_handler, '_perform_issues_scan_for_block'):
            log_debug(f"TextOperationHandler.text_edited: Calling _perform_issues_scan_for_block for block {block_idx}")
            self.mw.app_action_handler._perform_issues_scan_for_block(block_idx, is_single_block_scan=True, use_default_mappings_in_scan=False)
            if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
                 self.ui_updater.update_block_item_text_with_problem_count(block_idx)
            if hasattr(self.mw, 'preview_text_edit') and hasattr(self.mw.preview_text_edit, 'lineNumberArea'):
                self.mw.preview_text_edit.lineNumberArea.update()
        
        self.preview_update_timer.start(PREVIEW_UPDATE_DELAY) 
        self.ui_updater.update_status_bar() 
        self.ui_updater.synchronize_original_cursor()
        
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if edited_edit and hasattr(edited_edit, 'lineNumberArea'):
            edited_edit.lineNumberArea.update() 

    def paste_block_text(self):
        log_debug(f"--> TextOperationHandler: paste_block_text triggered.")
        if self.mw.current_block_idx == -1: QMessageBox.warning(self.mw, "Paste Error", "Please select a block."); return
        if not self.mw.current_game_rules:
            QMessageBox.warning(self.mw, "Paste Error", "Game rules not loaded.")
            return
            
        block_idx = self.mw.current_block_idx
        
        self.mw.before_paste_problems_snapshot = {
            k: v.copy() for k, v in self.mw.problems_per_subline.items() if k[0] == block_idx
        }
        self.mw.before_paste_edited_data_snapshot = {
            k: v for k,v in self.mw.edited_data.items() if k[0] == block_idx
        }
        self.mw.before_paste_block_idx_affected = block_idx
        
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'highlightManager'):
            preview_edit.highlightManager.clearAllProblemHighlights() 
        
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if edited_edit and hasattr(edited_edit, 'highlightManager'):
            edited_edit.highlightManager.clearAllProblemHighlights()

        keys_to_remove = [k for k in self.mw.problems_per_subline if k[0] == block_idx]
        for key_to_remove in keys_to_remove:
            del self.mw.problems_per_subline[key_to_remove]
        
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
            
            processed_text, _, _ = process_segment_tags_aggressively(
                segment_to_insert_raw, original_text_for_tags, self.mw.default_tag_mappings, self.mw.EDITOR_PLAYER_TAG
            )
            final_text_to_apply = processed_text.rstrip('\n')
            
            if self.data_processor.update_edited_data(block_idx, current_target_string_idx, final_text_to_apply):
                 self.ui_updater.update_title()
            
            old_text_for_this_line = self.mw.before_paste_edited_data_snapshot.get((block_idx, current_target_string_idx), original_text_for_tags)
            if final_text_to_apply != old_text_for_this_line:
                 any_change_applied_to_data = True
            successfully_processed_count += 1

        if successfully_processed_count > 0 and hasattr(self.mw.app_action_handler, '_perform_issues_scan_for_block'):
             log_debug(f"Paste block finished. Triggering silent rescan for block {block_idx} due to paste.")
             self.mw.app_action_handler._perform_issues_scan_for_block(block_idx, is_single_block_scan=True, use_default_mappings_in_scan=False) 
        
        problem_summary_texts = []
        if self.mw.current_game_rules:
            problem_definitions = self.mw.current_game_rules.get_problem_definitions()
            problem_counts = {pid: 0 for pid in problem_definitions.keys()}
            
            for b_idx_iter, ds_idx_iter, sl_idx_iter in self.mw.problems_per_subline:
                if b_idx_iter == block_idx:
                    for problem_id in self.mw.problems_per_subline[(b_idx_iter, ds_idx_iter, sl_idx_iter)]:
                        if problem_id in problem_counts:
                            problem_counts[problem_id] += 1
            
            for pid, count in problem_counts.items():
                if count > 0:
                    problem_name = problem_definitions.get(pid, {}).get("name", pid)
                    problem_summary_texts.append(f"{count} x {problem_name}")

        if problem_summary_texts:
            error_summary = (f"Pasted {successfully_processed_count} segment(s) into Block '{self.mw.block_names.get(str(block_idx), str(block_idx))}'.\n" + "\n".join(problem_summary_texts) + "\nPlease review.")
            QMessageBox.warning(self.mw, "Paste with Issues/Warnings", error_summary)
        elif any_change_applied_to_data:
            QMessageBox.information(self.mw, "Paste Successful", f"{successfully_processed_count} segment(s) processed and applied.")
        else:
            QMessageBox.information(self.mw, "Paste", "Pasted text resulted in no changes to the data.")
        
        self.mw.is_programmatically_changing_text = True
        self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
        self.ui_updater.update_block_item_text_with_problem_count(self.mw.current_block_idx)
        self.mw.is_programmatically_changing_text = False
        
        if any_change_applied_to_data or problem_summary_texts :
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

        if hasattr(self.mw.app_action_handler, '_perform_issues_scan_for_block'):
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
        if not self.mw.current_game_rules:
            QMessageBox.warning(self.mw, "Calculate Width Error", "Game rules plugin not loaded.")
            return

        max_allowed_width = self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS
        warning_threshold = self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS
        
        info_parts = [f"Data Line {data_line_idx + 1} (Block {self.mw.current_block_idx}):\nMax Allowed Width (Game Dialog): {max_allowed_width}px\nWidth Warning Threshold (Editor): {warning_threshold}px\n"]
        
        problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        
        sources_to_check = [
            ("Current", str(current_text_data_line), source),
            ("Original", str(original_text_data_line), "original_data")
        ]

        for title_prefix, text_to_analyze, text_source_info in sources_to_check:
            info_parts.append(f"--- {title_prefix} Text (Source: {text_source_info}) ---")
            
            game_like_text_no_newlines_rstripped = remove_all_tags(text_to_analyze.replace('\n','')).rstrip()
            total_game_width = calculate_string_width(game_like_text_no_newlines_rstripped, self.mw.font_map)
            game_status = "OK"
            if total_game_width > self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS:
                game_status = f"EXCEEDS GAME DIALOG LIMIT ({total_game_width - self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS}px)"
            info_parts.append(f"Total (game-like, no newlines): {total_game_width}px ({game_status})")

            logical_sublines = text_to_analyze.split('\n')
            for subline_idx, sub_line_text in enumerate(logical_sublines):
                sub_line_no_tags_rstripped = remove_all_tags(sub_line_text).rstrip()
                width_px = calculate_string_width(sub_line_no_tags_rstripped, self.mw.font_map)
                
                current_subline_problems = set()
                if title_prefix == "Current":
                    current_subline_problems = self.mw.problems_per_subline.get((self.mw.current_block_idx, data_line_idx, subline_idx), set())
                else: 
                    next_original_subline = logical_sublines[subline_idx + 1] if subline_idx + 1 < len(logical_sublines) else None
                    current_subline_problems = self.mw.current_game_rules.analyze_subline(
                        text=sub_line_text,
                        next_text=next_original_subline,
                        subline_number_in_data_string=subline_idx,
                        qtextblock_number_in_editor=subline_idx, 
                        is_last_subline_in_data_string=(subline_idx == len(logical_sublines) - 1),
                        editor_font_map=self.mw.font_map,
                        editor_line_width_threshold=warning_threshold
                    )
                
                statuses = []
                for prob_id in current_subline_problems:
                    if prob_id in problem_definitions:
                        statuses.append(problem_definitions[prob_id]['name'])
                
                status_str = ", ".join(statuses) if statuses else "OK"
                info_parts.append(f"  Sub-line {subline_idx+1} (rstripped): {width_px}px ({status_str}) '{sub_line_no_tags_rstripped[:30]}...'")
            if title_prefix == "Current": info_parts.append("") 
        
        result_dialog = QMessageBox(self.mw)
        result_dialog.setWindowTitle(f"Width Analysis for Data Line {data_line_idx + 1}")
        result_dialog.setTextFormat(Qt.PlainText)
        result_dialog.setText("\n".join(info_parts))
        result_dialog.setIcon(QMessageBox.Information)
        result_dialog.setStandardButtons(QMessageBox.Ok)
        text_edit_for_size = result_dialog.findChild(QPlainTextEdit)
        if text_edit_for_size:
            text_edit_for_size.setMinimumWidth(700)
            text_edit_for_size.setMinimumHeight(500)
        result_dialog.exec_()
        log_debug(f"<-- TextOperationHandler: calculate_width_for_data_line_action finished.")
        
    def auto_fix_current_string(self):
        log_debug(f"TextOperationHandler.auto_fix_current_string: Called.")
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            QMessageBox.information(self.mw, "Auto-fix", "No string selected to fix.")
            return
        if not self.mw.current_game_rules:
            QMessageBox.warning(self.mw, "Auto-fix Error", "Game rules plugin not loaded.")
            return

        block_idx = self.mw.current_block_idx
        string_idx = self.mw.current_string_idx
        
        current_text, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        
        final_text_to_apply, changed = self.mw.current_game_rules.autofix_data_string(
            str(current_text), 
            self.mw.font_map, 
            self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS
        )
        
        if changed:
            log_debug(f"Auto-fix: Applying changes. Original: '{str(current_text)[:100]}...', Final: '{final_text_to_apply[:100]}...'")
            
            edited_text_edit = self.mw.edited_text_edit
            original_cursor_pos = 0
            current_v_scroll = 0
            current_h_scroll = 0
            
            if edited_text_edit:
                original_cursor_pos = edited_text_edit.textCursor().position()
                current_v_scroll = edited_text_edit.verticalScrollBar().value()
                current_h_scroll = edited_text_edit.horizontalScrollBar().value()
            
            self.mw.is_programmatically_changing_text = True 

            if self.data_processor.update_edited_data(block_idx, string_idx, final_text_to_apply):
                 self.ui_updater.update_title()
            
            if edited_text_edit:
                text_for_display = convert_spaces_to_dots_for_display(final_text_to_apply, self.mw.show_multiple_spaces_as_dots)
                edited_text_edit.blockSignals(True)
                cursor = edited_text_edit.textCursor()
                cursor.beginEditBlock()
                cursor.select(QTextCursor.Document)
                cursor.insertText(text_for_display) 
                cursor.endEditBlock()
                edited_text_edit.blockSignals(False)
                
                new_doc_len = edited_text_edit.document().characterCount() -1 
                final_cursor_pos = min(original_cursor_pos, new_doc_len if new_doc_len >= 0 else 0)
                restored_cursor = edited_text_edit.textCursor() 
                restored_cursor.setPosition(final_cursor_pos)
                edited_text_edit.setTextCursor(restored_cursor)
                
                edited_text_edit.verticalScrollBar().setValue(current_v_scroll)
                edited_text_edit.horizontalScrollBar().setValue(current_h_scroll)

            self.mw.is_programmatically_changing_text = False 

            if hasattr(self.mw.app_action_handler, '_perform_issues_scan_for_block'):
                 self.mw.app_action_handler._perform_issues_scan_for_block(block_idx, is_single_block_scan=True, use_default_mappings_in_scan=False) 
            
            self.ui_updater.populate_strings_for_block(block_idx) 
            self.ui_updater.update_block_item_text_with_problem_count(block_idx) 
            
            self.ui_updater.update_status_bar()
            self.ui_updater.synchronize_original_cursor()
            
            if hasattr(self.mw, 'preview_text_edit') and self.mw.preview_text_edit and hasattr(self.mw.preview_text_edit, 'lineNumberArea'):
                self.mw.preview_text_edit.lineNumberArea.update()
            if edited_text_edit and hasattr(edited_text_edit, 'lineNumberArea'):
                edited_text_edit.lineNumberArea.update()
            
            if hasattr(self.mw, 'statusBar'):
                self.mw.statusBar.showMessage("Auto-fix applied to current string.", 2000)
        else:
            log_debug("Auto-fix: No changes made to the text by plugin.")
            if hasattr(self.mw, 'statusBar'):
                self.mw.statusBar.showMessage("Auto-fix: No changes made.", 2000)