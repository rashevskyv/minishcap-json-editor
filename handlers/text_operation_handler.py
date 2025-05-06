# handlers/text_operation_handler.py
import re
from PyQt5.QtWidgets import QMessageBox, QApplication
from handlers.base_handler import BaseHandler
from utils import log_debug, clean_newline_at_end
from tag_utils import replace_tags_based_on_original

class TextOperationHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)

    def text_edited(self):
        # Avoid overly verbose logging for every keystroke, focus on state changes
        # log_debug(f"[TextOperationHandler] text_edited TRIGGERED. Flag: {self.mw.is_programmatically_changing_text}") 
        if self.mw.is_programmatically_changing_text: return 

        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            self.ui_updater.update_status_bar(); self.ui_updater.update_status_bar_selection()
            return

        block_idx = self.mw.current_block_idx
        string_idx = self.mw.current_string_idx
        current_edited_text_from_ui = self.mw.edited_text_edit.toPlainText() 

        # Only log significant parts of the update logic
        # log_debug(f"[TextOperationHandler] User edit for ({block_idx},{string_idx}).")
        unsaved_status_changed = self.data_processor.update_edited_data(block_idx, string_idx, current_edited_text_from_ui)
        
        if unsaved_status_changed: 
            log_debug(f"Unsaved status changed to: {self.mw.unsaved_changes}. Updating title.")
            self.ui_updater.update_title()
        elif self.mw.unsaved_changes: # Changed but status remains True
             # No need to log this every time, title already has '*'
             # log_debug("Unsaved status remains true.")
             pass 

        self.ui_updater.update_string_list_item_text(string_idx, current_edited_text_from_ui)
        self.ui_updater.update_status_bar()
        self.ui_updater.update_status_bar_selection()

    def paste_block_text(self):
        log_debug("--> TextOperationHandler: paste_block_text triggered.")
        if self.mw.current_block_idx == -1:
            QMessageBox.warning(self.mw, "Paste Error", "Please select a block.")
            log_debug("<-- TextOperationHandler: paste_block_text finished (No block selected).")
            return

        start_string_idx = self.mw.current_string_idx if self.mw.current_string_idx != -1 else 0
        pasted_text = QApplication.clipboard().text()
        if not pasted_text:
            QMessageBox.information(self.mw, "Paste", "Clipboard empty.")
            log_debug("<-- TextOperationHandler: paste_block_text finished (Clipboard empty).")
            return

        log_debug("Processing clipboard text for paste...")
        parsed_strings_raw = re.split(r'\{END\}\r?\n', pasted_text)
        parsed_strings_intermediate = []
        num_raw_segments = len(parsed_strings_raw)
        for i, segment in enumerate(parsed_strings_raw):
            cleaned_segment = segment[1:] if i > 0 and segment.startswith('\n') else segment
            if i < num_raw_segments - 1 or cleaned_segment: parsed_strings_intermediate.append(cleaned_segment)
        parsed_strings = parsed_strings_intermediate
        log_debug(f"Found {len(parsed_strings)} segments after cleaning.")

        block_idx = self.mw.current_block_idx
        if not (0 <= block_idx < len(self.mw.data)) or not isinstance(self.mw.data[block_idx], list):
             QMessageBox.warning(self.mw, "Paste Error", f"Block data invalid for {block_idx}.")
             log_debug("<-- TextOperationHandler: paste_block_text finished (Invalid block data).")
             return
             
        block_data_len = len(self.mw.data[block_idx])
        if not (0 <= start_string_idx < block_data_len) and block_data_len > 0:
             QMessageBox.warning(self.mw, "Paste Error", f"Invalid start index {start_string_idx}.")
             log_debug("<-- TextOperationHandler: paste_block_text finished (Invalid start index).")
             return
             
        if block_data_len == 0 and start_string_idx != 0:
             QMessageBox.warning(self.mw, "Paste Error", "Cannot start paste in non-empty block at non-zero index.")
             log_debug("<-- TextOperationHandler: paste_block_text finished (Invalid start index for empty block).")
             return

        num_target_slots = block_data_len - start_string_idx if block_data_len > 0 else len(parsed_strings)
        num_segments_to_insert = min(len(parsed_strings), num_target_slots)
        segments_to_use = parsed_strings[:num_segments_to_insert]
        log_debug(f"Will insert {num_segments_to_insert} segments starting at index {start_string_idx}.")
        if num_segments_to_insert == 0:
             QMessageBox.information(self.mw, "Paste", "No segments to insert.")
             log_debug("<-- TextOperationHandler: paste_block_text finished (No segments to insert).")
             return
        
        effective_changes_applied = False
        log_debug("Applying pasted segments to data model...")
        for i, segment_to_insert in enumerate(segments_to_use):
            current_target_string_idx = start_string_idx + i
            original_text_for_tags = ""
            if block_data_len > 0 and 0 <= current_target_string_idx < len(self.mw.data[block_idx]):
                 original_text_for_tags = self.mw.data[block_idx][current_target_string_idx]
            
            text_with_replaced_tags = replace_tags_based_on_original(segment_to_insert, original_text_for_tags)
            final_text_to_apply = text_with_replaced_tags.rstrip('\n')
            
            # This directly modifies the data model (edited_data)
            item_changed_unsaved_status = self.data_processor.update_edited_data(block_idx, current_target_string_idx, final_text_to_apply)
            
            current_val_in_edited_data = self.mw.edited_data.get((block_idx, current_target_string_idx))
            original_text_at_idx = self.data_processor._get_string_from_source(block_idx, current_target_string_idx, self.mw.data, "original_data")
            
            if current_val_in_edited_data is not None or \
               (original_text_at_idx is not None and final_text_to_apply != original_text_at_idx) or \
               (original_text_at_idx is None and final_text_to_apply):
                effective_changes_applied = True
        
        log_debug(f"Finished applying segments. Effective changes applied: {effective_changes_applied}")

        if effective_changes_applied:
            log_debug("Effective changes detected, proceeding to auto-save...")
            save_success = False
            if hasattr(self.mw, 'app_action_handler') and hasattr(self.mw.app_action_handler, 'save_data_action'):
                save_success = self.mw.app_action_handler.save_data_action(ask_confirmation=False) # Save handler handles UI refresh
            else: # Fallback (should ideally not be needed)
                log_debug("WARN: app_action_handler not found, attempting direct save (UI refresh might be incomplete).")
                self.mw.is_programmatically_changing_text = True
                save_success = self.data_processor.save_current_edits(ask_confirmation=False)
                if save_success: 
                    self.ui_updater.update_title()
                    self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
                self.mw.is_programmatically_changing_text = False

            msg = "Pasted and saved." if save_success else "Pasted, but auto-save FAILED."
            QMessageBox.information(self.mw, "Paste Operation", f"{num_segments_to_insert} segments. {msg}")
        else:
             log_debug("No effective changes detected from paste.")
             QMessageBox.information(self.mw, "Paste", "Pasted text identical to target. No changes.")
             # Refresh UI anyway to ensure consistency
             self.mw.is_programmatically_changing_text = True
             self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
             self.mw.is_programmatically_changing_text = False
             self.ui_updater.update_title()
        log_debug("<-- TextOperationHandler: paste_block_text finished.")