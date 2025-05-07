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
            return 
        
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1: 
            return
        
        block_idx = self.mw.current_block_idx
        string_idx_in_block = self.mw.current_string_idx
        block_key = str(block_idx)
        
        saved_cursor = self.mw.edited_text_edit.textCursor()
        
        text_from_ui_with_dots = self.mw.edited_text_edit.toPlainText() 
        actual_text_with_spaces = text_from_ui_with_dots
        if self.mw.show_multiple_spaces_as_dots:
            actual_text_with_spaces = convert_dots_to_spaces_from_editor(text_from_ui_with_dots)
        
        unsaved_status_changed = self.data_processor.update_edited_data(block_idx, string_idx_in_block, actual_text_with_spaces)
        if unsaved_status_changed: 
            self.ui_updater.update_title()

        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        
        # Перевіряємо, чи поточний рядок був проблемним і чи проблема вирішена
        if preview_edit and hasattr(self.mw, 'problem_lines_per_block') and \
           block_key in self.mw.problem_lines_per_block and \
           string_idx_in_block in self.mw.problem_lines_per_block[block_key]:
            
            # Проблема вирішена, якщо в actual_text_with_spaces (текст, що йде в дані)
            # більше немає тегів формату [...]
            if not re.search(r"\[[^\]]*\]", actual_text_with_spaces):
                log_debug(f"TextEdited: Line {string_idx_in_block} in block {block_idx} no longer contains [...] tags. Updating problem status.")
                self.mw.problem_lines_per_block[block_key].discard(string_idx_in_block)
                if not self.mw.problem_lines_per_block[block_key]: # Якщо множина стала порожньою
                    del self.mw.problem_lines_per_block[block_key]
                    self.ui_updater.highlight_problem_block(block_idx, False) # Знімаємо фон з блоку
                
                if hasattr(preview_edit, 'removeProblemLineHighlight'): # Знімаємо фон з рядка в preview
                    preview_edit.removeProblemLineHighlight(string_idx_in_block)
                # Потрібно оновити текст елемента блоку в списку
                if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
                    self.ui_updater.update_block_item_text_with_problem_count(block_idx)
        
        self.mw.is_programmatically_changing_text = True
        self.ui_updater.populate_strings_for_block(block_idx) 
        self.mw.is_programmatically_changing_text = False

        if saved_cursor:
            self.mw.edited_text_edit.setTextCursor(saved_cursor)
        # log_debug(f"TextEdited: Finished for ({block_idx}, {string_idx_in_block}).")


    def paste_block_text(self):
        log_debug("--> TextOperationHandler: paste_block_text triggered.")
        if self.mw.current_block_idx == -1:
            QMessageBox.warning(self.mw, "Paste Error", "Please select a block.")
            return

        block_idx = self.mw.current_block_idx
        block_key = str(block_idx)

        # Зберігання стану для Undo
        self.mw.before_paste_edited_data_snapshot = dict(self.mw.edited_data) 
        self.mw.before_paste_problem_lines_snapshot = {
             k: set(v) for k, v in self.mw.problem_lines_per_block.items()
        }
        self.mw.before_paste_block_idx_affected = block_idx
        log_debug(f"PasteBlock: Stored snapshot for undo. edited_data items: {len(self.mw.before_paste_edited_data_snapshot)}, problem_lines_snapshot for block {block_key}: {self.mw.problem_lines_per_block.get(block_key, set())}")

        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'clearProblemLineHighlights'):
            preview_edit.clearProblemLineHighlights()
        
        # Очищаємо лічильник проблем для поточного блоку перед новою перевіркою
        if hasattr(self.mw, 'problem_lines_per_block'):
            self.mw.problem_lines_per_block[block_key] = set() 
        
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
        
        current_block_new_problem_indices = set() 
        successfully_processed_count = 0; any_change_applied_to_data = False
        
        self.mw.is_programmatically_changing_text = True 
        for i, segment_to_insert_raw in enumerate(parsed_strings):
            current_target_string_idx = start_string_idx + i
            if current_target_string_idx >= original_block_len:
                if i == 0: QMessageBox.warning(self.mw, "Paste Error", f"Cannot paste starting at line {start_string_idx + 1}. Block has {original_block_len} lines."); self.mw.is_programmatically_changing_text = False; return 
                break 
            original_text_for_tags = self.mw.data[block_idx][current_target_string_idx]
            processed_text, tags_ok, tag_error_msg = replace_tags_based_on_original(segment_to_insert_raw, original_text_for_tags, self.mw.default_tag_mappings)
            successfully_processed_count +=1; final_text_to_apply = processed_text.rstrip('\n')
            
            current_text_in_data, _ = self.data_processor.get_current_string_text(block_idx, current_target_string_idx)
            if final_text_to_apply != current_text_in_data:
                 self.data_processor.update_edited_data(block_idx, current_target_string_idx, final_text_to_apply)
                 any_change_applied_to_data = True

            if not tags_ok: 
                current_block_new_problem_indices.add(current_target_string_idx)
                log_debug(f"Tag processing issue for block {block_idx}, line {current_target_string_idx}: {tag_error_msg}.")
        self.mw.is_programmatically_changing_text = False 
        
        if current_block_new_problem_indices:
            self.mw.problem_lines_per_block[block_key] = current_block_new_problem_indices
            self.ui_updater.highlight_problem_block(block_idx, True)
            
            error_summary = (f"Pasted {successfully_processed_count} segment(s).\n"
                             f"{len(current_block_new_problem_indices)} line(s) in Block '{self.mw.block_names.get(str(block_idx), str(block_idx))}' "
                             f"had tag issues and were updated with auto-corrected known tags.\n"
                             f"Please review highlighted lines (yellow).")
            
            if preview_edit:
                for line_idx_in_block in current_block_new_problem_indices:
                    if hasattr(preview_edit, 'addProblemLineHighlight'): preview_edit.addProblemLineHighlight(line_idx_in_block) 
                if hasattr(preview_edit, 'applyQueuedProblemHighlights'): preview_edit.applyQueuedProblemHighlights() 
            
            QMessageBox.warning(self.mw, "Paste with Tag Issues", error_summary)
            if any_change_applied_to_data: self.mw.unsaved_changes = True; self.ui_updater.update_title()
        
        elif any_change_applied_to_data: 
            log_debug(f"Successfully pasted and processed {successfully_processed_count} segments. Auto-saving.")
            save_success = self.mw.app_action_handler.save_data_action(ask_confirmation=False)
            QMessageBox.information(self.mw, "Paste Operation", f"{successfully_processed_count} segment(s) processed. {'Pasted and saved.' if save_success else 'Pasted, but auto-save FAILED.'}")
        
        else: 
            log_debug("No effective changes detected from paste operation (text identical or no data changed).")
            QMessageBox.information(self.mw, "Paste", "Pasted text resulted in no changes to the data.")
        
        # Завжди оновлюємо UI та лічильник проблем на блоці після вставки
        self.mw.is_programmatically_changing_text = True
        self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
        if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
            self.ui_updater.update_block_item_text_with_problem_count(self.mw.current_block_idx)
        self.mw.is_programmatically_changing_text = False
        
        if preview_edit and current_block_new_problem_indices and hasattr(preview_edit, 'applyQueuedProblemHighlights'):
             preview_edit.applyQueuedProblemHighlights()
        
        if any_change_applied_to_data or current_block_new_problem_indices:
            self.mw.can_undo_paste = True
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(True)
        else:
            self.mw.can_undo_paste = False
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(False)

        log_debug("<-- TextOperationHandler: paste_block_text finished.")