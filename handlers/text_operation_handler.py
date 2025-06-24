import re
from PyQt5.QtWidgets import QMessageBox, QApplication, QPlainTextEdit
from PyQt5.QtGui import QTextCursor, QTextBlock
from PyQt5.QtCore import QTimer
from .base_handler import BaseHandler
from utils.logging_utils import log_debug
from utils.utils import convert_dots_to_spaces_from_editor, convert_spaces_to_dots_for_display, calculate_string_width, remove_all_tags, SPACE_DOT_SYMBOL, ALL_TAGS_PATTERN

PREVIEW_UPDATE_DELAY = 250

class TextOperationHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self.preview_update_timer = QTimer()
        self.preview_update_timer.setSingleShot(True)
        self.preview_update_timer.timeout.connect(self._update_preview_content)

    def _log_undo_state(self, editor, context_message):
        if editor and hasattr(editor, 'document'):
            doc = editor.document()
            log_debug(f"UNDO_DEBUG ({context_message}): UndoAvailable={doc.isUndoAvailable()}, RedoAvailable={doc.isRedoAvailable()}, Revision={doc.revision()}")

    def _update_preview_content(self):
        log_debug("TextOperationHandler: Updating preview content via timer.")
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit or self.mw.current_block_idx == -1:
            return

        block_idx = self.mw.current_block_idx
        old_scrollbar_value = preview_edit.verticalScrollBar().value()
        
        main_window_ref = self.mw
        was_programmatically_changing = main_window_ref.is_programmatically_changing_text
        main_window_ref.is_programmatically_changing_text = True
        
        if self.mw.current_game_rules:
            preview_lines = []
            if 0 <= block_idx < len(self.mw.data) and isinstance(self.mw.data[block_idx], list):
                for i in range(len(self.mw.data[block_idx])):
                    text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, i)
                    preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                    preview_lines.append(preview_line_text)

            preview_full_text = "\n".join(preview_lines)
            
            if preview_edit.toPlainText() != preview_full_text:
                preview_edit.setPlainText(preview_full_text)
        
        if hasattr(preview_edit, 'highlightManager'):
            preview_edit.highlightManager.clearAllProblemHighlights()
            self.ui_updater._apply_highlights_for_block(block_idx)

            if self.mw.current_string_idx != -1 and 0 <= self.mw.current_string_idx < preview_edit.document().blockCount():
                preview_edit.highlightManager.setPreviewSelectedLineHighlight(self.mw.current_string_idx)
            else:
                preview_edit.highlightManager.clearPreviewSelectedLineHighlight()

        preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
        if hasattr(preview_edit, 'lineNumberArea'):
            preview_edit.lineNumberArea.update()

        main_window_ref.is_programmatically_changing_text = was_programmatically_changing


    def text_edited(self):
        if self.mw.is_programmatically_changing_text:
            return
        
        self._log_undo_state(self.mw.edited_text_edit, "text_edited START")
        
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            return
        
        block_idx = self.mw.current_block_idx
        string_idx_in_block = self.mw.current_string_idx
        
        edited_edit = self.mw.edited_text_edit
        
        if not edited_edit or not self.mw.current_game_rules:
            return
        
        text_from_editor = edited_edit.toPlainText()
        
        actual_text = self.mw.current_game_rules.convert_editor_text_to_data(text_from_editor)
        
        actual_text_with_spaces = convert_dots_to_spaces_from_editor(actual_text)
        
        needs_title_update = self.data_processor.update_edited_data(block_idx, string_idx_in_block, actual_text_with_spaces)
        
        if needs_title_update: 
            self.mw.ui_updater.update_title()

        self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)
        self.preview_update_timer.start(PREVIEW_UPDATE_DELAY) 
        self.mw.ui_updater.update_status_bar()
        self.mw.ui_updater.synchronize_original_cursor()
        
        if edited_edit and hasattr(edited_edit, 'lineNumberArea'):
            edited_edit.lineNumberArea.update()
        
        self._log_undo_state(self.mw.edited_text_edit, "text_edited END")


    def paste_block_text(self):
        log_debug(f"--> TextOperationHandler: paste_block_text triggered.")
        if self.mw.current_block_idx == -1: QMessageBox.warning(self.mw, "Paste Error", "Please select a block."); return
        if not self.mw.current_game_rules:
            QMessageBox.warning(self.mw, "Paste Error", "Game rules not loaded.")
            return
            
        block_idx = self.mw.current_block_idx
        
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
        
        active_editor_for_paste = self.mw.edited_text_edit
        if active_editor_for_paste:
            self._log_undo_state(active_editor_for_paste, "paste_block_text - Before paste loop")

        for i, segment_to_insert_raw in enumerate(parsed_strings):
            current_target_string_idx = start_string_idx + i
            if current_target_string_idx >= original_block_len:
                if i == 0:
                    QMessageBox.warning(self.mw, "Paste Error", f"Cannot paste starting at line {start_string_idx + 1}. Block has {original_block_len} lines.")
                break
            
            original_text_for_tags = self.mw.data[block_idx][current_target_string_idx]
            
            processed_text, _, _ = self.mw.current_game_rules.process_pasted_segment(
                segment_to_insert_raw, original_text_for_tags, self.mw.EDITOR_PLAYER_TAG
            )
            final_text_to_apply = processed_text.rstrip('\n')
            
            if self.data_processor.update_edited_data(block_idx, current_target_string_idx, final_text_to_apply):
                if hasattr(self.mw, 'title_status_bar_updater'):
                    self.mw.title_status_bar_updater.update_title()
                elif hasattr(self.ui_updater, 'update_title'): 
                    self.ui_updater.update_title()
            
            old_text_for_this_line = self.mw.before_paste_edited_data_snapshot.get((block_idx, current_target_string_idx), original_text_for_tags)
            if final_text_to_apply != old_text_for_this_line:
                 any_change_applied_to_data = True
            successfully_processed_count += 1
        
        self.mw.ui_updater.populate_blocks()
        self.mw.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
        self.mw.ui_updater.update_text_views()
        
        if active_editor_for_paste:
            self._log_undo_state(active_editor_for_paste, "paste_block_text - After UI update")


        if any_change_applied_to_data:
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
        
        active_editor_for_revert = self.mw.edited_text_edit
        if active_editor_for_revert and self.mw.current_string_idx == line_index:
            self._log_undo_state(active_editor_for_revert, f"revert_single_line S:{line_index} - Before data update")

        if self.data_processor.update_edited_data(block_idx, line_index, original_text):
            if hasattr(self.mw, 'title_status_bar_updater'):
                self.mw.title_status_bar_updater.update_title()
            elif hasattr(self.ui_updater, 'update_title'): 
                self.ui_updater.update_title()

        self.mw.ui_updater.populate_blocks()
        self.mw.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
        self.mw.ui_updater.update_text_views()
        
        if active_editor_for_revert and self.mw.current_string_idx == line_index:
            self._log_undo_state(active_editor_for_revert, f"revert_single_line S:{line_index} - After UI update")


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

        max_allowed_width = self.mw.game_dialog_max_width_pixels
        warning_threshold = self.mw.line_width_warning_threshold_pixels
        
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
            if total_game_width > self.mw.game_dialog_max_width_pixels:
                game_status = f"EXCEEDS GAME DIALOG LIMIT ({total_game_width - self.mw.game_dialog_max_width_pixels}px)"
            info_parts.append(f"Total (game-like, no newlines): {total_game_width}px ({game_status})")

            logical_sublines = text_to_analyze.split('\n')
            for subline_idx, sub_line_text in enumerate(logical_sublines):
                sub_line_no_tags_rstripped = remove_all_tags(sub_line_text).rstrip()
                width_px = calculate_string_width(sub_line_no_tags_rstripped, self.mw.font_map)
                
                current_subline_problems = set()
                next_original_subline = logical_sublines[subline_idx + 1] if subline_idx + 1 < len(logical_sublines) else None
                current_subline_problems = self.mw.current_game_rules.analyze_subline(
                    text=sub_line_text,
                    next_text=next_original_subline,
                    subline_number_in_data_string=subline_idx,
                    qtextblock_number_in_editor=subline_idx, 
                    is_last_subline_in_data_string=(subline_idx == len(logical_sublines) - 1),
                    editor_font_map=self.mw.font_map,
                    editor_line_width_threshold=warning_threshold,
                    full_data_string_text_for_logical_check=text_to_analyze 
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
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            QMessageBox.information(self.mw, "Auto-fix", "No string selected to fix.")
            return
        if not self.mw.current_game_rules:
            QMessageBox.warning(self.mw, "Auto-fix Error", "Game rules plugin not loaded.")
            return

        edited_text_edit = self.mw.edited_text_edit
        
        data_to_fix = self.mw.current_game_rules.convert_editor_text_to_data(edited_text_edit.toPlainText())
        
        fixed_data, changed = self.mw.current_game_rules.autofix_data_string(
            data_to_fix, 
            self.mw.font_map, 
            self.mw.line_width_warning_threshold_pixels
        )
        
        if changed:
            visual_text_for_editor = self.mw.current_game_rules.get_text_representation_for_editor(fixed_data)
            
            self._log_undo_state(edited_text_edit, "Before auto_fix")
            cursor = edited_text_edit.textCursor()
            cursor.beginEditBlock()
            cursor.select(QTextCursor.Document)
            cursor.insertText(visual_text_for_editor)
            cursor.endEditBlock()
            self._log_undo_state(edited_text_edit, "After auto_fix")
            
            if hasattr(self.mw, 'statusBar'):
                self.mw.statusBar.showMessage("Auto-fix applied.", 2000)
        else:
            if hasattr(self.mw, 'statusBar'):
                self.mw.statusBar.showMessage("Auto-fix: No changes made.", 2000)