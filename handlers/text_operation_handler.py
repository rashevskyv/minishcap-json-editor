import re
from PyQt5.QtWidgets import QMessageBox, QApplication
from handlers.base_handler import BaseHandler
from utils import log_debug, clean_newline_at_end, convert_dots_to_spaces_from_editor 
from tag_utils import replace_tags_based_on_original 

class TextOperationHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)

    def text_edited(self):
        # ... (код без змін) ...
        if self.mw.is_programmatically_changing_text: return 
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1: return
        block_idx, string_idx = self.mw.current_block_idx, self.mw.current_string_idx
        text_from_ui_with_dots = self.mw.edited_text_edit.toPlainText() 
        actual_text_with_spaces = text_from_ui_with_dots
        if self.mw.show_multiple_spaces_as_dots:
            actual_text_with_spaces = convert_dots_to_spaces_from_editor(text_from_ui_with_dots)
        unsaved_status_changed = self.data_processor.update_edited_data(block_idx, string_idx, actual_text_with_spaces)
        if unsaved_status_changed: self.ui_updater.update_title()

    def paste_block_text(self):
        log_debug("--> TextOperationHandler: paste_block_text triggered.")
        if self.mw.current_block_idx == -1:
            QMessageBox.warning(self.mw, "Paste Error", "Please select a block.")
            return

        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'clearProblemLineHighlights'):
            log_debug("Paste_block_text: Clearing previous problem line highlights from preview_edit.")
            preview_edit.clearProblemLineHighlights()
        if hasattr(self.ui_updater, 'clear_all_problem_block_highlights'):
            log_debug("Paste_block_text: Clearing previous problem block highlights.")
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
        if not parsed_strings: QMessageBox.information(self.mw, "Paste", "No valid segments found in clipboard after parsing."); return
        
        log_debug(f"Found {len(parsed_strings)} segments to process.")
        block_idx = self.mw.current_block_idx
        if not (0 <= block_idx < len(self.mw.data)) or not isinstance(self.mw.data[block_idx], list):
             QMessageBox.warning(self.mw, "Paste Error", f"Block data invalid for selected block {block_idx}."); return
        original_block_len = len(self.mw.data[block_idx])
        
        problematic_lines_info = [] 
        processed_segments_count = 0 
        any_change_applied_to_data = False

        for i, segment_to_insert_raw in enumerate(parsed_strings):
            current_target_string_idx = start_string_idx + i
            if current_target_string_idx >= original_block_len:
                log_debug(f"Paste stopped: Target index {current_target_string_idx} exceeds original block length {original_block_len}.")
                if i == 0: QMessageBox.warning(self.mw, "Paste Error", f"Cannot paste starting at line {start_string_idx + 1}. The block only has {original_block_len} lines."); return 
                break 

            original_text_for_tags = self.mw.data[block_idx][current_target_string_idx]
            
            # processed_text_from_util містить результат роботи tag_utils:
            # - якщо tags_ok=True: текст з повною заміною тегів
            # - якщо tags_ok=False: текст з частковою заміною по словнику (відомі теги), решта [...] як є
            processed_text_from_util, tags_ok, tag_error_msg = replace_tags_based_on_original(
                segment_to_insert_raw, 
                original_text_for_tags,
                self.mw.default_tag_mappings 
            )
            processed_segments_count += 1 # Рахуємо всі оброблені сегменти

            final_text_to_apply = processed_text_from_util.rstrip('\n')
            current_text_in_data, _ = self.data_processor.get_current_string_text(block_idx, current_target_string_idx)

            # Оновлюємо дані ЗАВЖДИ, використовуючи processed_text_from_util,
            # оскільки він містить щонайменше заміни по словнику.
            # Користувач буде попереджений, якщо tags_ok == False.
            if final_text_to_apply != current_text_in_data:
                self.data_processor.update_edited_data(block_idx, current_target_string_idx, final_text_to_apply)
                any_change_applied_to_data = True
            
            if not tags_ok: # Якщо була невідповідність кількості тегів
                problematic_lines_info.append((current_target_string_idx, tag_error_msg))
                log_debug(f"Tag processing issue (Strategy 2) for block {block_idx}, line_idx {current_target_string_idx}: {tag_error_msg}. "
                          f"Data for this line WAS updated with default-mapped text: '{repr(final_text_to_apply)}'")
        
        if problematic_lines_info:
            self.ui_updater.highlight_problem_block(block_idx, True)
            num_updated_segments = processed_segments_count # Усі оброблені сегменти тепер оновлюють дані
            
            error_summary = (f"Processed {processed_segments_count} segment(s). "
                             f"{num_updated_segments} segment(s) were updated in data (known tags auto-corrected).\n"
                             f"However, tag structure mismatch issues found in {len(problematic_lines_info)} line(s) in Block {self.mw.block_names.get(str(block_idx), str(block_idx))}:\n")
            
            if preview_edit:
                for line_idx_in_block, _ in problematic_lines_info:
                    if hasattr(preview_edit, 'addProblemLineHighlight'):
                        preview_edit.addProblemLineHighlight(line_idx_in_block) 
                if hasattr(preview_edit, 'applyQueuedProblemHighlights'):
                    preview_edit.applyQueuedProblemHighlights() 
            
            unique_problem_lines_indices = sorted(list(set(idx for idx, msg in problematic_lines_info)))
            for line_idx in unique_problem_lines_indices:
                msgs_for_line = [msg for idx, msg in problematic_lines_info if idx == line_idx]
                error_summary += f"- Line {line_idx + 1}: {'; '.join(msgs_for_line)}\n"
            error_summary += "\nPlease review these lines. Unmapped [...] tags may still be present."
            
            QMessageBox.warning(self.mw, "Paste with Tag Issues", error_summary)
            
            # Оскільки ми оновили дані, навіть з частковою заміною, позначаємо зміни
            if any_change_applied_to_data or problematic_lines_info: # Якщо були проблеми, це теж "зміна" стану
                self.mw.unsaved_changes = True 
                self.ui_updater.update_title()
            
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
            if preview_edit and hasattr(preview_edit, 'applyQueuedProblemHighlights'):
                 preview_edit.applyQueuedProblemHighlights()

        elif any_change_applied_to_data: 
            log_debug(f"Successfully pasted and processed {processed_segments_count} segments. Auto-saving.")
            save_success = self.mw.app_action_handler.save_data_action(ask_confirmation=False)
            msg_verb = "Pasted and saved." if save_success else "Pasted, but auto-save FAILED."
            QMessageBox.information(self.mw, "Paste Operation", f"{processed_segments_count} segment(s) processed. {msg_verb}")
        
        else: 
            log_debug("No effective changes detected from paste operation (text identical or no data changed).")
            QMessageBox.information(self.mw, "Paste", "Pasted text resulted in no changes to the data.")
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
        
        log_debug("<-- TextOperationHandler: paste_block_text finished.")