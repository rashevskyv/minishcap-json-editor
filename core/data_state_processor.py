import json
import os
from PyQt5.QtWidgets import QMessageBox
from .data_manager import load_json_file, save_json_file
from utils.logging_utils import log_debug

class DataStateProcessor:
    def __init__(self, main_window):
        self.mw = main_window

    def _get_string_from_source(self, block_idx, string_idx, source_data, source_name):
        if not source_data:
            return None
        if not (0 <= block_idx < len(source_data)):
            return None
        
        current_block = source_data[block_idx]
        if not isinstance(current_block, list):
            return None
        
        if not (0 <= string_idx < len(current_block)):
            return None
            
        value = current_block[string_idx]
        return value

    def get_current_string_text(self, block_idx, string_idx):
        edit_key = (block_idx, string_idx)
        if edit_key in self.mw.edited_data:
            return self.mw.edited_data[edit_key], "edited_data (in-memory)"
        
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
        
        original_text = self._get_string_from_source(block_idx, string_idx, self.mw.data, "original_data_for_update_check")
        
        text_from_saved_file = self._get_string_from_source(block_idx, string_idx, self.mw.edited_file_data, "edited_file_data")
        if text_from_saved_file is None:
            text_from_saved_file = original_text
            
        old_unsaved_changes = self.mw.unsaved_changes

        if new_text == text_from_saved_file:
            if edit_key in self.mw.edited_data:
                del self.mw.edited_data[edit_key]
        else:
            self.mw.edited_data[edit_key] = new_text

        self.mw.unsaved_changes = bool(self.mw.edited_data)
        
        unsaved_status_actually_changed = self.mw.unsaved_changes != old_unsaved_changes
        if unsaved_status_actually_changed:
            log_debug(f"DSP.update_edited_data: Unsaved changes status changed to {self.mw.unsaved_changes}")
        
        return unsaved_status_actually_changed


    def save_current_edits(self, ask_confirmation=True):
        log_debug(f"--> AppActionHandler: save_data_action called. ask_confirmation={ask_confirmation}, current unsaved={self.mw.unsaved_changes}")
        if self.mw.json_path and not self.mw.edited_json_path:
            self.mw.edited_json_path = self.mw.app_action_handler._derive_edited_path(self.mw.json_path) 
        if not self.mw.edited_json_path:
            QMessageBox.warning(self.mw, "Save Error", "Edited file path is not set. Cannot save.")
            return False
        if not self.mw.current_game_rules: 
            QMessageBox.critical(self.mw, "Save Error", "No game plugin active to format the save file.")
            return False
        
        if not self.mw.unsaved_changes:
            log_debug("Save called but no unsaved changes detected. Skipping file write.")
            if ask_confirmation:
                QMessageBox.information(self.mw, "Save", "No changes to save.")
            return True

        if ask_confirmation:
            reply = QMessageBox.question(self.mw, 'Save Changes', f"Save changes to '{os.path.basename(self.mw.edited_json_path)}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No: return False
        
        try:
            if not self.mw.data: QMessageBox.critical(self.mw, "Save Error", "Original data not loaded. Cannot save."); return False
            
            output_data_list = json.loads(json.dumps(self.mw.data)) 
            if self.mw.edited_file_data:
                output_data_list = json.loads(json.dumps(self.mw.edited_file_data))

            if self.mw.edited_data:
                log_debug(f"Applying {len(self.mw.edited_data)} in-memory edits before saving...")
            for (b_idx, s_idx), edited_text_from_memory in self.mw.edited_data.items():
                if 0 <= b_idx < len(output_data_list) and isinstance(output_data_list[b_idx], list) and \
                   0 <= s_idx < len(output_data_list[b_idx]):
                    output_data_list[b_idx][s_idx] = edited_text_from_memory
                else:
                    log_debug(f"Save: Memory edit for key ({b_idx},{s_idx}) is out of bounds for output_data. Ignored.")
            
            final_json_obj_to_save = self.mw.current_game_rules.save_data_to_json_obj(output_data_list, self.mw.block_names)

            save_file_success = save_json_file(self.mw.edited_json_path, final_json_obj_to_save, parent_widget=self.mw)
            if save_file_success:
                self.mw.unsaved_changes = False
                self.mw.edited_data = {} 
                
                reloaded_edited_data, _ = self.mw.current_game_rules.load_data_from_json_obj(final_json_obj_to_save)
                self.mw.edited_file_data = reloaded_edited_data

                if ask_confirmation: QMessageBox.information(self.mw, "Saved", f"Changes saved to\n'{os.path.basename(self.mw.edited_json_path)}'.")
                return True
            else: return False
        except Exception as e: QMessageBox.critical(self.mw, "Save Error", f"Unexpected error during save prep:\n{e}"); return False

    def revert_edited_file_to_original(self):
        if not self.mw.json_path or not self.mw.edited_json_path: QMessageBox.warning(self.mw, "Revert Error", "Original or Changes file path is not set."); return False
        if not self.mw.data: QMessageBox.warning(self.mw, "Revert Error", "Original data is not loaded."); return False
        if not self.mw.current_game_rules: QMessageBox.critical(self.mw, "Revert Error", "No game plugin active to format the save file."); return False

        reply = QMessageBox.question(self.mw, 'Revert Changes File', f"This will overwrite the file:\n{os.path.basename(self.mw.edited_json_path)}\nwith the content from:\n{os.path.basename(self.mw.json_path)}\n\nAll previous edits in the changes file will be lost.\nCurrent unsaved edits in memory will also be discarded.\n\nAre you sure?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No: return False
        try:
            output_data = self.mw.current_game_rules.save_data_to_json_obj(self.mw.data, self.mw.block_names)

            save_file_success = save_json_file(self.mw.edited_json_path, output_data, parent_widget=self.mw)
            if save_file_success:
                self.mw.unsaved_changes = False; self.mw.edited_data = {}; 
                
                reverted_data_list, _ = self.mw.current_game_rules.load_data_from_json_obj(output_data)
                self.mw.edited_file_data = reverted_data_list

                QMessageBox.information(self.mw, "Reverted", f"Changes file '{os.path.basename(self.mw.edited_json_path)}' has been reverted to match the original.")
                self.mw.ui_updater.update_title(); 
                self.mw.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
                return True
            else: return False
        except Exception as e: QMessageBox.critical(self.mw, "Revert Error", f"Unexpected error during revert:\n{e}"); return False