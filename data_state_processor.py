import json
import os
from PyQt5.QtWidgets import QMessageBox
from data_manager import load_json_file, save_json_file
from utils import log_debug

class DataStateProcessor:
    def __init__(self, main_window):
        self.mw = main_window

    # ... _get_string_from_source, get_current_string_text, update_edited_data ...
    # (No changes needed in the above methods for this request)
    def _get_string_from_source(self, block_idx, string_idx, source_data, source_name):
        if source_data and 0 <= block_idx < len(source_data) and \
           isinstance(source_data[block_idx], list) and \
           0 <= string_idx < len(source_data[block_idx]):
            return source_data[block_idx][string_idx]
        return None

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
        log_debug(f"!!! DataStateProcessor: Error in get_current_string_text - Index ({block_idx}, {string_idx}) out of bounds.")
        return "[DATA ERROR]", "error"

    def update_edited_data(self, block_idx, string_idx, new_text):
        edit_key = (block_idx, string_idx)
        log_debug(f"--> DataStateProcessor: update_edited_data for key {edit_key}. Current edited_data size: {len(self.mw.edited_data)}")
        original_text = self._get_string_from_source(block_idx, string_idx, self.mw.data, "original_data")
        text_currently_in_edited_data = self.mw.edited_data.get(edit_key)
        old_unsaved_changes = self.mw.unsaved_changes
        log_debug(f"Comparing New Text ('{new_text[:30]}...') with Original ('{original_text[:30] if original_text is not None else 'None'}...')")
        change_made_to_dict = False
        if original_text is None: 
            log_debug(f"WARN: Original text is None for key {edit_key}.")
            if text_currently_in_edited_data != new_text:
                self.mw.edited_data[edit_key] = new_text; change_made_to_dict = True
        elif new_text != original_text:
            if text_currently_in_edited_data != new_text:
                self.mw.edited_data[edit_key] = new_text; change_made_to_dict = True
        elif edit_key in self.mw.edited_data:
            del self.mw.edited_data[edit_key]; change_made_to_dict = True
        else: log_debug("New text matches original and key not in edited_data. No change needed.")
        self.mw.unsaved_changes = bool(self.mw.edited_data)
        unsaved_status_actually_changed = self.mw.unsaved_changes != old_unsaved_changes
        log_debug(f"Dict changed: {change_made_to_dict}. Overall unsaved status changed: {unsaved_status_actually_changed}. Current unsaved: {self.mw.unsaved_changes}. New edited_data size: {len(self.mw.edited_data)}")
        log_debug(f"<-- DataStateProcessor: update_edited_data finished.")
        return unsaved_status_actually_changed


    def save_current_edits(self, ask_confirmation=True):
        log_debug(f"--> DataStateProcessor: save_current_edits called. ask_confirmation={ask_confirmation}")
        has_pending_edits = bool(self.mw.edited_data)
        log_debug(f"State Check: has_pending_edits={has_pending_edits}, edited_data count={len(self.mw.edited_data)}, json_path='{self.mw.json_path}', edited_json_path='{self.mw.edited_json_path}'")

        if not self.mw.json_path:
            QMessageBox.warning(self.mw, "Save Error", "Original file path not set.")
            log_debug("<-- DataStateProcessor: save_current_edits finished (Error: No original path).")
            return False

        if not self.mw.edited_json_path:
             self.mw.edited_json_path = self.mw._derive_edited_path(self.mw.json_path)
             log_debug(f"Derived edited_json_path: {self.mw.edited_json_path}")

        # --- MODIFICATION START ---
        # If there are no pending edits, just return True (success, nothing to do).
        # Removed the logic that prompted about cleaning the existing file.
        if not has_pending_edits:
            log_debug("No pending edits found. Save operation skipped.")
            # Optionally show info message if ask_confirmation was True?
            # if ask_confirmation:
            #     QMessageBox.information(self.mw, "Save", "No unsaved changes to save.")
            log_debug("<-- DataStateProcessor: save_current_edits finished (No pending edits). Result: True")
            return True
        # --- MODIFICATION END ---

        # Proceed only if has_pending_edits is True
        
        # Ask confirmation for saving PENDING edits if needed
        if ask_confirmation:
            log_debug("Asking user about saving pending edits.")
            reply = QMessageBox.question(self.mw, 'Save Changes', f"Save changes to '{os.path.basename(self.mw.edited_json_path)}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            log_debug(f"User reply to save prompt: {reply}")
            if reply == QMessageBox.No: 
                 log_debug("<-- DataStateProcessor: save_current_edits finished (User cancelled save). Result: False")
                 return False # User cancelled save

        log_debug("Proceeding to prepare save data...")
        try:
            output_data = []
            if not self.mw.data:
                QMessageBox.critical(self.mw, "Save Error", "Original data not loaded. Cannot save."); return False
            
            # Start with a deep copy of original data
            output_data = json.loads(json.dumps(self.mw.data))
            log_debug("Step 1: Initialized output_data from original.")

            # Merge existing disk edits first (if any)
            if os.path.exists(self.mw.edited_json_path):
                log_debug("Step 2: Merging existing disk edits...")
                existing_disk_edits, err = load_json_file(self.mw.edited_json_path, parent_widget=None, expected_type=list)
                if not err and existing_disk_edits:
                    for b_idx, block_from_disk in enumerate(existing_disk_edits):
                        if 0 <= b_idx < len(output_data) and isinstance(output_data[b_idx], list) and isinstance(block_from_disk, list):
                            for s_idx, text_from_disk in enumerate(block_from_disk):
                                if 0 <= s_idx < len(output_data[b_idx]) and 0 <= s_idx < len(self.mw.data[b_idx]) and text_from_disk != self.mw.data[b_idx][s_idx]:
                                    output_data[b_idx][s_idx] = text_from_disk
                    log_debug("Finished merging disk edits.")
                elif err: log_debug(f"WARN: Error loading existing disk edits: {err}")
                else: log_debug("Existing disk edits file was empty or not loaded.")
                 
            # Merge pending in-memory edits. These take precedence.
            log_debug(f"Step 3: Merging {len(self.mw.edited_data)} pending in-memory edits...")
            for (b_idx, s_idx), edited_text_from_memory in self.mw.edited_data.items():
                log_debug(f"  Merging edit for ({b_idx},{s_idx})...")
                if 0 <= b_idx < len(output_data) and isinstance(output_data[b_idx], list) and 0 <= s_idx < len(output_data[b_idx]):
                    output_data[b_idx][s_idx] = edited_text_from_memory
                else: log_debug(f"    WARN: Index ({b_idx},{s_idx}) out of bounds for output_data. Skipping memory edit.")
            log_debug("Finished merging memory edits.")

            # Save the final output_data to disk
            log_debug("Step 4: Saving final output_data to disk...")
            save_file_success = save_json_file(self.mw.edited_json_path, output_data, parent_widget=self.mw)
            
            if save_file_success:
                log_debug("Save to disk successful. Updating internal state.")
                self.mw.unsaved_changes = False
                self.mw.edited_data = {} 
                self.mw.edited_file_data = output_data 
                if ask_confirmation: # Show message only if user explicitly asked to save
                    QMessageBox.information(self.mw, "Saved", f"Changes saved to\n'{os.path.basename(self.mw.edited_json_path)}'.")
                log_debug("<-- DataStateProcessor: save_current_edits finished (Success). Result: True")
                return True
            else: # save_json_file failed
                 log_debug("Save to disk FAILED.")
                 log_debug("<-- DataStateProcessor: save_current_edits finished (Save file failed). Result: False")
                 return False
        except Exception as e:
            QMessageBox.critical(self.mw, "Save Error", f"Unexpected error during save prep:\n{e}")
            log_debug(f"save_current_edits: Exception: {e}")
            log_debug("<-- DataStateProcessor: save_current_edits finished (Exception). Result: False")
            return False

    # NEW METHOD for dedicated "clean" action
    def revert_edited_file_to_original(self):
        """Overwrites the edited file with the content of the original file."""
        log_debug("--> DataStateProcessor: revert_edited_file_to_original called.")
        if not self.mw.json_path or not self.mw.edited_json_path:
             log_debug("Cannot revert: Original or Edited path is not set.")
             QMessageBox.warning(self.mw, "Revert Error", "Original or Changes file path is not set.")
             return False
        if not self.mw.data:
             log_debug("Cannot revert: Original data is not loaded.")
             QMessageBox.warning(self.mw, "Revert Error", "Original data is not loaded.")
             return False

        reply = QMessageBox.question(self.mw, 'Revert Changes File',
                                     f"This will overwrite the file:\n{os.path.basename(self.mw.edited_json_path)}\n"
                                     f"with the content from:\n{os.path.basename(self.mw.json_path)}\n\n"
                                     "All previous edits in the changes file will be lost.\n"
                                     "Current unsaved edits in memory will also be discarded.\n\n"
                                     "Are you sure?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            log_debug("User cancelled revert operation.")
            return False

        log_debug("Proceeding with revert...")
        try:
            # Data to save is simply a deep copy of the original
            output_data = json.loads(json.dumps(self.mw.data))
            
            log_debug(f"Attempting to save original data to '{self.mw.edited_json_path}'...")
            save_file_success = save_json_file(self.mw.edited_json_path, output_data, parent_widget=self.mw)

            if save_file_success:
                log_debug("Revert successful. Updating internal state.")
                self.mw.unsaved_changes = False # Discard current memory edits too
                self.mw.edited_data = {} 
                self.mw.edited_file_data = output_data # Cache now reflects original
                QMessageBox.information(self.mw, "Reverted", f"Changes file '{os.path.basename(self.mw.edited_json_path)}' has been reverted to match the original.")
                log_debug("<-- DataStateProcessor: revert_edited_file_to_original finished (Success).")
                # Trigger UI refresh after reverting
                self.mw.ui_updater.update_title()
                self.mw.ui_updater.populate_strings_for_block(self.mw.current_block_idx) # Refresh current view
                return True
            else:
                 log_debug("Revert FAILED during file save.")
                 # Don't change internal state if save failed
                 log_debug("<-- DataStateProcessor: revert_edited_file_to_original finished (Save failed).")
                 return False
        except Exception as e:
            QMessageBox.critical(self.mw, "Revert Error", f"Unexpected error during revert:\n{e}")
            log_debug(f"revert_edited_file_to_original: Exception: {e}")
            log_debug("<-- DataStateProcessor: revert_edited_file_to_original finished (Exception).")
            return False