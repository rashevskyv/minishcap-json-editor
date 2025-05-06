import re
from PyQt5.QtWidgets import QMessageBox, QApplication
from handlers.base_handler import BaseHandler
from utils import log_debug, clean_newline_at_end, convert_dots_to_spaces_from_editor 
from tag_utils import replace_tags_based_on_original 

class TextOperationHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)

    def text_edited(self):
        if self.mw.is_programmatically_changing_text: 
            # log_debug("TextEdited: Programmatic change, text_edited is skipped.")
            return 
        
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1: 
            return
        
        block_idx = self.mw.current_block_idx
        string_idx_in_block = self.mw.current_string_idx
        
        saved_cursor = self.mw.edited_text_edit.textCursor()
        
        text_from_ui_with_dots = self.mw.edited_text_edit.toPlainText() 
        actual_text_with_spaces = text_from_ui_with_dots
        if self.mw.show_multiple_spaces_as_dots:
            actual_text_with_spaces = convert_dots_to_spaces_from_editor(text_from_ui_with_dots)
        
        unsaved_status_changed = self.data_processor.update_edited_data(block_idx, string_idx_in_block, actual_text_with_spaces)
        if unsaved_status_changed: 
            self.ui_updater.update_title()

        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'hasProblemHighlight'):
            if preview_edit.hasProblemHighlight(string_idx_in_block):
                if not re.search(r"\[[^\]]*\]", actual_text_with_spaces):
                    log_debug(f"TextEdited: Line {string_idx_in_block} in block {block_idx} no longer contains [...] tags. Removing problem highlight.")
                    if hasattr(preview_edit, 'removeProblemLineHighlight'):
                        preview_edit.removeProblemLineHighlight(string_idx_in_block)
                    
                    if hasattr(preview_edit, 'applyQueuedProblemHighlights'):
                         preview_edit.applyQueuedProblemHighlights()

                    if hasattr(preview_edit, 'hasProblemHighlight') and not preview_edit.hasProblemHighlight():
                        log_debug(f"TextEdited: No more problem lines in block {block_idx}. Clearing block highlight.")
                        self.ui_updater.highlight_problem_block(block_idx, False)
        
        # Встановлюємо прапор, бо populate_strings_for_block оновить ВСІ текстові поля
        self.mw.is_programmatically_changing_text = True
        self.ui_updater.populate_strings_for_block(block_idx) # Це оновить preview та edited_text_edit (для крапок)
        self.mw.is_programmatically_changing_text = False

        if saved_cursor: # Відновлюємо курсор в edited_text_edit
            self.mw.edited_text_edit.setTextCursor(saved_cursor)
        # log_debug(f"TextEdited: Finished for ({block_idx}, {string_idx_in_block}).")


    def paste_block_text(self):
        log_debug("--> TextOperationHandler: paste_block_text triggered.")
        if self.mw.current_block_idx == -1:
            QMessageBox.warning(self.mw, "Paste Error", "Please select a block.")
            return

        # Зберігаємо поточний стан self.mw.edited_data для можливого Undo
        self.mw.before_paste_edited_data_snapshot = dict(self.mw.edited_data)
        self.mw.before_paste_block_idx_affected = self.mw.current_block_idx # Зберігаємо блок, куди вставляємо
        # Також можна зберегти self.mw.edited_file_data, якщо paste_block_text його змінює,
        # або якщо Undo має відкочувати і стан файлу (що складніше).
        log_debug(f"PasteBlock: Stored snapshot for undo. edited_data items: {len(self.mw.before_paste_edited_data_snapshot)}")


        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'clearProblemLineHighlights'):
            preview_edit.clearProblemLineHighlights()
        if hasattr(self.ui_updater, 'clear_all_problem_block_highlights'):
            self.ui_updater.clear_all_problem_block_highlights()

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
        
        block_idx = self.mw.current_block_idx
        if not (0 <= block_idx < len(self.mw.data)) or not isinstance(self.mw.data[block_idx], list):
             QMessageBox.warning(self.mw, "Paste Error", f"Block data invalid for block {block_idx}."); return
        original_block_len = len(self.mw.data[block_idx])
        
        problematic_lines_info = []; successfully_processed_count = 0; any_change_applied_to_data = False
        
        self.mw.is_programmatically_changing_text = True 
        for i, segment_to_insert_raw in enumerate(parsed_strings):
            current_target_string_idx = start_string_idx + i
            if current_target_string_idx >= original_block_len:
                if i == 0: QMessageBox.warning(self.mw, "Paste Error", f"Cannot paste starting at line {start_string_idx + 1}. Block has {original_block_len} lines."); self.mw.is_programmatically_changing_text = False; return 
                break 
            original_text_for_tags = self.mw.data[block_idx][current_target_string_idx]
            processed_text, tags_ok, tag_error_msg = replace_tags_based_on_original(segment_to_insert_raw, original_text_for_tags, self.mw.default_tag_mappings)
            successfully_processed_count +=1; final_text_to_apply = processed_text.rstrip('\n')
            
            # Завжди оновлюємо дані, навіть якщо tags_ok=False
            current_text_in_data, _ = self.data_processor.get_current_string_text(block_idx, current_target_string_idx)
            if final_text_to_apply != current_text_in_data:
                 self.data_processor.update_edited_data(block_idx, current_target_string_idx, final_text_to_apply)
                 any_change_applied_to_data = True

            if not tags_ok: 
                problematic_lines_info.append((current_target_string_idx, tag_error_msg))
        
        self.mw.is_programmatically_changing_text = False 
        
        if problematic_lines_info:
            self.ui_updater.highlight_problem_block(block_idx, True)
            num_updated_despite_issues = len(problematic_lines_info) 
            error_summary = (f"Processed {successfully_processed_count} segment(s).\n"
                             f"{num_updated_despite_issues} line(s) had tag count mismatches but were updated with known tags auto-corrected. Review them (yellow).\n"
                             f"Issues reported for {len(problematic_lines_info)} line(s) in Block {self.mw.block_names.get(str(block_idx), str(block_idx))}:\n")
            if preview_edit:
                for line_idx_in_block, _ in problematic_lines_info:
                    if hasattr(preview_edit, 'addProblemLineHighlight'): preview_edit.addProblemLineHighlight(line_idx_in_block) 
                if hasattr(preview_edit, 'applyQueuedProblemHighlights'): preview_edit.applyQueuedProblemHighlights() 
            unique_problem_lines_indices = sorted(list(set(idx for idx, msg in problematic_lines_info)))
            for line_idx in unique_problem_lines_indices:
                msgs_for_line = [msg for idx, msg in problematic_lines_info if idx == line_idx]
                error_summary += f"- Line {line_idx + 1}: {'; '.join(msgs_for_line)}\n"
            error_summary += "\nLines with tag issues were updated with auto-corrected known tags. Please review remaining [...] tags."
            QMessageBox.warning(self.mw, "Paste with Tag Issues", error_summary)
            if any_change_applied_to_data: self.mw.unsaved_changes = True; self.ui_updater.update_title()
            
            self.mw.is_programmatically_changing_text = True
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) # Оновлюємо UI, щоб показати зміни і підсвічування
            self.mw.is_programmatically_changing_text = False
            # Проблемні підсвічування мають відновитися/застосуватися в populate_strings_for_block

        elif any_change_applied_to_data: 
            log_debug(f"Successfully pasted and processed {successfully_processed_count} segments. Auto-saving.")
            save_success = self.mw.app_action_handler.save_data_action(ask_confirmation=False)
            QMessageBox.information(self.mw, "Paste Operation", f"{successfully_processed_count} segment(s) processed. {'Pasted and saved.' if save_success else 'Pasted, but auto-save FAILED.'}")
        
        else: 
            log_debug("No effective changes detected from paste operation (text identical or no data changed).")
            QMessageBox.information(self.mw, "Paste", "Pasted text resulted in no changes to the data.")
            self.mw.is_programmatically_changing_text = True
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
            self.mw.is_programmatically_changing_text = False
        
        if any_change_applied_to_data or problematic_lines_info: # Активуємо Undo, якщо були зміни або проблеми
            self.mw.can_undo_paste = True
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(True)
        else:
            self.mw.can_undo_paste = False
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(False)

        log_debug("<-- TextOperationHandler: paste_block_text finished.")