import re
from PyQt5.QtWidgets import QMessageBox, QApplication
from handlers.base_handler import BaseHandler
from utils import log_debug, clean_newline_at_end, convert_dots_to_spaces_from_editor 
from tag_utils import replace_tags_based_on_original 

class TextOperationHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)

    def text_edited(self):
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

        # ... (решта коду до циклу обробки сегментів без змін) ...
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
        problematic_lines_info = []; successfully_pasted_count = 0; any_change_applied_to_data = False

        for i, segment_to_insert_raw in enumerate(parsed_strings):
            current_target_string_idx = start_string_idx + i
            if current_target_string_idx >= original_block_len:
                log_debug(f"Paste stopped: Target index {current_target_string_idx} exceeds original block length {original_block_len}.")
                if i == 0: QMessageBox.warning(self.mw, "Paste Error", f"Cannot paste starting at line {start_string_idx + 1}. The block only has {original_block_len} lines."); return 
                break 
            original_text_for_tags = self.mw.data[block_idx][current_target_string_idx]
            processed_text, tags_ok, tag_error_msg = replace_tags_based_on_original(segment_to_insert_raw, original_text_for_tags)
            if tags_ok:
                final_text_to_apply = processed_text.rstrip('\n') 
                current_text_in_data, _ = self.data_processor.get_current_string_text(block_idx, current_target_string_idx)
                if final_text_to_apply != current_text_in_data:
                    self.data_processor.update_edited_data(block_idx, current_target_string_idx, final_text_to_apply)
                    any_change_applied_to_data = True
                successfully_pasted_count +=1
            else:
                problematic_lines_info.append((current_target_string_idx, tag_error_msg))
                log_debug(f"Tag processing error for block {block_idx}, string_idx_in_block {current_target_string_idx}: {tag_error_msg}")
        
        if problematic_lines_info:
            log_debug(f"Paste_block_text: Found {len(problematic_lines_info)} problematic lines.")
            self.ui_updater.highlight_problem_block(block_idx, True)
            error_summary = f"Pasted {successfully_pasted_count} segment(s) with issues in {len(problematic_lines_info)} line(s) in Block {self.mw.block_names.get(str(block_idx), str(block_idx))}:\n"
            
            if preview_edit:
                for line_idx_in_block, _ in problematic_lines_info:
                    if hasattr(preview_edit, 'addProblemLineHighlight'):
                        # Цей метод тепер тільки додає до списку
                        preview_edit.addProblemLineHighlight(line_idx_in_block) 
                
                # Застосовуємо всі накопичені проблемні підсвічування ОДИН РАЗ
                if hasattr(preview_edit, 'applyQueuedProblemHighlights'):
                    log_debug("Paste_block_text: Calling applyQueuedProblemHighlights on preview_edit.")
                    preview_edit.applyQueuedProblemHighlights()
                else: # Fallback
                    log_debug("Paste_block_text: Fallback - preview_edit has no applyQueuedProblemHighlights, trying _apply_all_extra_selections.")
                    if hasattr(preview_edit, '_apply_all_extra_selections'):
                         preview_edit._apply_all_extra_selections()


            unique_problem_lines_indices = sorted(list(set(idx for idx, msg in problematic_lines_info)))
            for line_idx in unique_problem_lines_indices:
                msgs_for_line = [msg for idx, msg in problematic_lines_info if idx == line_idx]
                error_summary += f"- Line {line_idx + 1}: {'; '.join(msgs_for_line)}\n"
            
            QMessageBox.warning(self.mw, "Paste with Tag Issues", error_summary)
            
            if any_change_applied_to_data:
                self.mw.unsaved_changes = True 
                self.ui_updater.update_title()
            
            log_debug("Paste_block_text: Updating UI via populate_strings_for_block after paste with issues.")
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
            
            # Важливо: після populate_strings_for_block, _problem_line_selections в preview_edit
            # могли бути скинуті (якщо populate_strings викликав clearProblemLineHighlights неявно).
            # Тому, якщо вони були, їх треба відновити і застосувати.
            # АЛЕ! populate_strings_for_block НЕ ПОВИНЕН скидати _problem_line_selections.
            # Якщо він це робить, то проблема в ньому.
            # Поки що, для діагностики, спробуємо ще раз застосувати, якщо вони ще є.
            if preview_edit and preview_edit._problem_line_selections and hasattr(preview_edit, 'applyQueuedProblemHighlights'):
                 log_debug("Paste_block_text: Re-applying problem highlights after populate_strings_for_block (just in case).")
                 preview_edit.applyQueuedProblemHighlights()


        elif any_change_applied_to_data: 
            log_debug(f"Successfully pasted and processed {successfully_pasted_count} segments. Auto-saving.")
            save_success = self.mw.app_action_handler.save_data_action(ask_confirmation=False)
            msg_verb = "Pasted and saved." if save_success else "Pasted, but auto-save FAILED."
            QMessageBox.information(self.mw, "Paste Operation", f"{successfully_pasted_count} segment(s) processed. {msg_verb}")
        
        else: 
            log_debug("No effective changes detected from paste operation (text identical).")
            QMessageBox.information(self.mw, "Paste", "Pasted text identical to target content. No changes made.")
            log_debug("Paste_block_text: Updating UI via populate_strings_for_block after identical paste.")
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
        
        log_debug("<-- TextOperationHandler: paste_block_text finished.")