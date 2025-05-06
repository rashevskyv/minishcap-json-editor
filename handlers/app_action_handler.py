# handlers/app_action_handler.py
import os
from PyQt5.QtWidgets import QMessageBox
from handlers.base_handler import BaseHandler
from utils import log_debug

class AppActionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)

    def save_data_action(self, ask_confirmation=True):
        log_debug(f"--> AppActionHandler: save_data_action called. ask_confirmation={ask_confirmation}, current unsaved={self.mw.unsaved_changes}")
        
        # Ensure paths are set if possible (though ideally set when file is opened)
        if self.mw.json_path and not self.mw.edited_json_path:
            self.mw.edited_json_path = self.mw._derive_edited_path(self.mw.json_path) # Call MainWindow's method
            self.ui_updater.update_statusbar_paths()

        current_block_idx_before_save = self.mw.current_block_idx
        current_string_idx_before_save = self.mw.current_string_idx
        log_debug(f"State before save call: current_block={current_block_idx_before_save}, current_string={current_string_idx_before_save}")

        # Call the core save logic
        save_success = self.data_processor.save_current_edits(ask_confirmation=ask_confirmation)
        log_debug(f"save_current_edits returned: {save_success}")
        
        if save_success:
            log_debug("Save successful. Proceeding with UI refresh.")
            self.ui_updater.update_title() # Update title first (removes '*')
            
            log_debug("Setting programmatic change flag before UI refresh.")
            self.mw.is_programmatically_changing_text = True 

            log_debug("Starting UI refresh...")
            if current_block_idx_before_save != -1:
                 log_debug(f"Restoring selection to block {current_block_idx_before_save}, string {current_string_idx_before_save}")
                 self.mw.current_block_idx = current_block_idx_before_save # Ensure indices are correct
                 self.mw.current_string_idx = current_string_idx_before_save
                 self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) # This should reselect and update editors
            else:
                 log_debug("No block was selected, clearing string view.")
                 self.ui_updater.populate_strings_for_block(-1)
            
            self.ui_updater.update_statusbar_paths() # Update paths if needed
            log_debug("UI refresh complete.")

            log_debug("Clearing programmatic change flag.")
            self.mw.is_programmatically_changing_text = False 
        else: 
            log_debug("Save failed or was cancelled by user.")
            self.ui_updater.update_title() # Update title in case confirmation was involved

        log_debug(f"<-- AppActionHandler: save_data_action finished. Result: {save_success}")
        return save_success

    def handle_close_event(self, event):
        log_debug("--> AppActionHandler: handle_close_event called.")
        if self.mw.unsaved_changes:
            log_debug("Unsaved changes detected. Prompting user...")
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Save changes before exiting?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
            log_debug(f"User prompt result: {reply}")
            if reply == QMessageBox.Save:
                log_debug("User chose Save. Calling save_data_action...")
                # Use ask_confirmation=True here to ensure user confirms the save on close
                if self.save_data_action(ask_confirmation=True): 
                    log_debug("Save successful. Accepting close event.")
                    event.accept()
                else: 
                    log_debug("Save failed/cancelled. Ignoring close event.")
                    event.ignore()
            elif reply == QMessageBox.Discard:
                log_debug("User chose Discard. Accepting close event.")
                event.accept()
            else: # Cancel
                log_debug("User chose Cancel. Ignoring close event.")
                event.ignore()
        else:
            log_debug("No unsaved changes. Accepting close event.")
            event.accept()
        log_debug("<-- AppActionHandler: handle_close_event finished.")