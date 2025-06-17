import json
import os
from PyQt5.QtWidgets import QMessageBox
from .data_manager import load_json_file, save_json_file
from utils.logging_utils import log_debug

class DataStateProcessor:
    def __init__(self, main_window):
        self.mw = main_window

    def _get_string_from_source(self, block_idx, string_idx, source_data, source_name):
        # Тимчасово вимикаємо це логування, щоб зменшити шум
        # log_debug(f"DSP._get_string_from_source: Request for src='{source_name}', b_idx={block_idx}, s_idx={string_idx}")
        if not source_data:
            # log_debug(f"  Error: source_data ('{source_name}') is None or empty.")
            return None
        if not (0 <= block_idx < len(source_data)):
            # log_debug(f"  Error: block_idx {block_idx} out of bounds for '{source_name}' (len: {len(source_data)}).")
            return None
        
        current_block = source_data[block_idx]
        if not isinstance(current_block, list):
            # log_debug(f"  Error: '{source_name}' block at index {block_idx} is not a list (type: {type(current_block)}).")
            return None
        
        if not (0 <= string_idx < len(current_block)):
            # log_debug(f"  Error: string_idx {string_idx} out of bounds for '{source_name}' block {block_idx} (len: {len(current_block)}).")
            return None
            
        value = current_block[string_idx]
        return value

    def get_current_string_text(self, block_idx, string_idx):
        edit_key = (block_idx, string_idx)
        if edit_key in self.mw.edited_data:
            return self.mw.edited_data[edit_key], "edited_data"
        
        text_from_file = self._get_string_from_source(block_idx, string_idx, self.mw.edited_file_data, "edited_file_data")
        if text_from_file is not None: 
            return text_from_file, "edited_file_data"
            
        text_from_original = self._get_string_from_source(block_idx, string_idx, self.mw.data, "original_data")
        if text_from_original is not None:
            return text_from_original, "original_data"
            
        log_debug(f"!!! DSP: Error in get_current_string_text - Index ({block_idx}, {string_idx}) out of bounds or data missing after checking all sources.")
        return "[DATA ERROR]", "error" 

    def update_edited_data(self, block_idx, string_idx, new_text):
        edit_key = (block_idx, string_idx)
        original_text_from_mw_data = self._get_string_from_source(block_idx, string_idx, self.mw.data, "original_data_for_update_check")
        
        text_currently_in_edited_data = self.mw.edited_data.get(edit_key)
        old_unsaved_changes = self.mw.unsaved_changes
        change_made_to_dict = False

        if original_text_from_mw_data is None: 
            log_debug(f"DSP.update_edited_data: Original text for key {edit_key} is None. Treating as new data if different from current edit.")
            if text_currently_in_edited_data != new_text: 
                self.mw.edited_data[edit_key] = new_text
                change_made_to_dict = True
        elif new_text != original_text_from_mw_data: 
            if text_currently_in_edited_data != new_text:
                 self.mw.edited_data[edit_key] = new_text
                 change_made_to_dict = True
        elif edit_key in self.mw.edited_data: 
            del self.mw.edited_data[edit_key]
            change_made_to_dict = True
        
        if change_made_to_dict:
            log_debug(f"DSP.update_edited_data: Key {edit_key} {'updated' if edit_key in self.mw.edited_data else 'removed'}. New edited_data size: {len(self.mw.edited_data)}")

        self.mw.unsaved_changes = bool(self.mw.edited_data)
        unsaved_status_actually_changed = self.mw.unsaved_changes != old_unsaved_changes
        if unsaved_status_actually_changed:
            log_debug(f"DSP.update_edited_data: Unsaved changes status changed to {self.mw.unsaved_changes}")
        return unsaved_status_actually_changed

    def save_current_edits(self, ask_confirmation=True):
        has_pending_edits = bool(self.mw.edited_data)
        if not self.mw.json_path: QMessageBox.warning(self.mw, "Save Error", "Original file path not set."); return False
        if not self.mw.edited_json_path: self.mw.edited_json_path = self.mw.app_action_handler._derive_edited_path(self.mw.json_path) 
        
        if not has_pending_edits and os.path.exists(self.mw.edited_json_path):
            log_debug("No pending memory edits found, but will proceed to write/update the changes file.")
        elif not has_pending_edits:
            log_debug("No pending memory edits and no existing changes file to update. Save operation skipped.")
            return True

        if ask_confirmation:
            reply = QMessageBox.question(self.mw, 'Save Changes', f"Save changes to '{os.path.basename(self.mw.edited_json_path)}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No: return False
        
        try:
            output_data = []
            if not self.mw.data: QMessageBox.critical(self.mw, "Save Error", "Original data not loaded. Cannot save."); return False
            
            output_data = json.loads(json.dumps(self.mw.data)) 

            if self.mw.edited_file_data:
                log_debug(f"Applying changes from loaded edited_file_data (count: {sum(len(b) for b in self.mw.edited_file_data if isinstance(b,list))})")
                for b_idx, block_from_edited_file in enumerate(self.mw.edited_file_data):
                    if 0 <= b_idx < len(output_data) and isinstance(output_data[b_idx], list) and \
                       isinstance(block_from_edited_file, list):
                        for s_idx, text_from_edited_file in enumerate(block_from_edited_file):
                            if 0 <= s_idx < len(output_data[b_idx]):
                                if 0 <= s_idx < len(self.mw.data[b_idx]) and text_from_edited_file != self.mw.data[b_idx][s_idx]:
                                    output_data[b_idx][s_idx] = text_from_edited_file
                                elif not (0 <= s_idx < len(self.mw.data[b_idx])): 
                                    log_debug(f"Save: String at ({b_idx},{s_idx}) in edited_file_data has no counterpart in original. Ignored.")


            if self.mw.edited_data:
                log_debug(f"Applying changes from current memory edits (self.mw.edited_data, count: {len(self.mw.edited_data)})")
            for (b_idx, s_idx), edited_text_from_memory in self.mw.edited_data.items():
                if 0 <= b_idx < len(output_data) and isinstance(output_data[b_idx], list) and \
                   0 <= s_idx < len(output_data[b_idx]):
                    output_data[b_idx][s_idx] = edited_text_from_memory
                else:
                    log_debug(f"Save: Memory edit for key ({b_idx},{s_idx}) is out of bounds for output_data. Ignored.")

            save_file_success = save_json_file(self.mw.edited_json_path, output_data, parent_widget=self.mw)
            if save_file_success:
                self.mw.unsaved_changes = False
                self.mw.edited_data = {} 
                self.mw.edited_file_data = json.loads(json.dumps(output_data)) 
                if ask_confirmation: QMessageBox.information(self.mw, "Saved", f"Changes saved to\n'{os.path.basename(self.mw.edited_json_path)}'.")
                return True
            else: return False
        except Exception as e: QMessageBox.critical(self.mw, "Save Error", f"Unexpected error during save prep:\n{e}"); return False

    def revert_edited_file_to_original(self):
        if not self.mw.json_path or not self.mw.edited_json_path: QMessageBox.warning(self.mw, "Revert Error", "Original or Changes file path is not set."); return False
        if not self.mw.data: QMessageBox.warning(self.mw, "Revert Error", "Original data is not loaded."); return False
        reply = QMessageBox.question(self.mw, 'Revert Changes File', f"This will overwrite the file:\n{os.path.basename(self.mw.edited_json_path)}\nwith the content from:\n{os.path.basename(self.mw.json_path)}\n\nAll previous edits in the changes file will be lost.\nCurrent unsaved edits in memory will also be discarded.\n\nAre you sure?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No: return False
        try:
            output_data = json.loads(json.dumps(self.mw.data))
            save_file_success = save_json_file(self.mw.edited_json_path, output_data, parent_widget=self.mw)
            if save_file_success:
                self.mw.unsaved_changes = False; self.mw.edited_data = {}; 
                self.mw.edited_file_data = json.loads(json.dumps(output_data)) 
                QMessageBox.information(self.mw, "Reverted", f"Changes file '{os.path.basename(self.mw.edited_json_path)}' has been reverted to match the original.")
                self.mw.ui_updater.update_title(); 
                self.mw.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
                return True
            else: return False
        except Exception as e: QMessageBox.critical(self.mw, "Revert Error", f"Unexpected error during revert:\n{e}"); return False