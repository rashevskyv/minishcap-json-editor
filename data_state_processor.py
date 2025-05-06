# data_state_processor.py
import json
import os
from PyQt5.QtWidgets import QMessageBox
from data_manager import load_json_file, save_json_file
from utils import log_debug

class DataStateProcessor:
    def __init__(self, main_window):
        self.mw = main_window

    def _get_string_from_source(self, block_idx, string_idx, source_data, source_name):
        # ... (код без змін) ...
        if source_data and 0 <= block_idx < len(source_data) and \
           isinstance(source_data[block_idx], list) and \
           0 <= string_idx < len(source_data[block_idx]):
            return source_data[block_idx][string_idx]
        return None


    def get_current_string_text(self, block_idx, string_idx):
        edit_key = (block_idx, string_idx)
        # Розкоментуйте для детального логування джерела даних
        # log_debug(f"DSP.get_current_string_text for key {edit_key}. edited_data has key: {edit_key in self.mw.edited_data}")
        if edit_key in self.mw.edited_data:
            # log_debug(f"  > From edited_data: '{self.mw.edited_data[edit_key][:30]}...'")
            return self.mw.edited_data[edit_key], "edited_data"
        
        text_from_file = self._get_string_from_source(block_idx, string_idx, self.mw.edited_file_data, "edited_file_data")
        if text_from_file is not None:
            # log_debug(f"  > From edited_file_data: '{text_from_file[:30]}...'")
            return text_from_file, "edited_file_data"
            
        text_from_original = self._get_string_from_source(block_idx, string_idx, self.mw.data, "original_data")
        if text_from_original is not None:
            # log_debug(f"  > From original_data: '{text_from_original[:30]}...'")
            return text_from_original, "original_data"
            
        log_debug(f"!!! DSP: Error in get_current_string_text - Index ({block_idx}, {string_idx}) out of bounds or data missing.")
        return "[DATA ERROR]", "error"

    # ... (решта DataStateProcessor без змін) ...
    def update_edited_data(self, block_idx, string_idx, new_text):
        edit_key = (block_idx, string_idx)
        original_text = self._get_string_from_source(block_idx, string_idx, self.mw.data, "original_data")
        text_currently_in_edited_data = self.mw.edited_data.get(edit_key)
        old_unsaved_changes = self.mw.unsaved_changes
        change_made_to_dict = False
        if original_text is None: 
            if text_currently_in_edited_data != new_text: self.mw.edited_data[edit_key] = new_text; change_made_to_dict = True
        elif new_text != original_text:
            if text_currently_in_edited_data != new_text: self.mw.edited_data[edit_key] = new_text; change_made_to_dict = True
        elif edit_key in self.mw.edited_data:
            del self.mw.edited_data[edit_key]; change_made_to_dict = True
        self.mw.unsaved_changes = bool(self.mw.edited_data)
        unsaved_status_actually_changed = self.mw.unsaved_changes != old_unsaved_changes
        return unsaved_status_actually_changed
    def save_current_edits(self, ask_confirmation=True):
        has_pending_edits = bool(self.mw.edited_data)
        if not self.mw.json_path: QMessageBox.warning(self.mw, "Save Error", "Original file path not set."); return False
        if not self.mw.edited_json_path: self.mw.edited_json_path = self.mw._derive_edited_path(self.mw.json_path)
        if not has_pending_edits: log_debug("No pending edits found. Save operation skipped."); return True
        if ask_confirmation:
            reply = QMessageBox.question(self.mw, 'Save Changes', f"Save changes to '{os.path.basename(self.mw.edited_json_path)}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No: return False
        try:
            output_data = []
            if not self.mw.data: QMessageBox.critical(self.mw, "Save Error", "Original data not loaded. Cannot save."); return False
            output_data = json.loads(json.dumps(self.mw.data))
            if os.path.exists(self.mw.edited_json_path):
                existing_disk_edits, err = load_json_file(self.mw.edited_json_path, parent_widget=None, expected_type=list)
                if not err and existing_disk_edits:
                    for b_idx, block_from_disk in enumerate(existing_disk_edits):
                        if 0 <= b_idx < len(output_data) and isinstance(output_data[b_idx], list) and isinstance(block_from_disk, list):
                            for s_idx, text_from_disk in enumerate(block_from_disk):
                                if 0 <= s_idx < len(output_data[b_idx]) and 0 <= s_idx < len(self.mw.data[b_idx]) and text_from_disk != self.mw.data[b_idx][s_idx]:
                                    output_data[b_idx][s_idx] = text_from_disk
            for (b_idx, s_idx), edited_text_from_memory in self.mw.edited_data.items():
                if 0 <= b_idx < len(output_data) and isinstance(output_data[b_idx], list) and 0 <= s_idx < len(output_data[b_idx]):
                    output_data[b_idx][s_idx] = edited_text_from_memory
            save_file_success = save_json_file(self.mw.edited_json_path, output_data, parent_widget=self.mw)
            if save_file_success:
                self.mw.unsaved_changes = False; self.mw.edited_data = {}; self.mw.edited_file_data = output_data 
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
                self.mw.unsaved_changes = False; self.mw.edited_data = {}; self.mw.edited_file_data = output_data
                QMessageBox.information(self.mw, "Reverted", f"Changes file '{os.path.basename(self.mw.edited_json_path)}' has been reverted to match the original.")
                self.mw.ui_updater.update_title(); self.mw.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
                return True
            else: return False
        except Exception as e: QMessageBox.critical(self.mw, "Revert Error", f"Unexpected error during revert:\n{e}"); return False