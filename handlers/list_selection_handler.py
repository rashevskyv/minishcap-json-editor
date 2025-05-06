# handlers/list_selection_handler.py
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtCore import Qt
from handlers.base_handler import BaseHandler 
from utils import log_debug 

class ListSelectionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)

    def block_selected(self, current, previous):
        current_text = current.text() if current else 'None'
        block_index = current.data(Qt.UserRole) if current else -1
        log_debug(f"--> ListSelectionHandler: block_selected. Item: '{current_text}', Index: {block_index}")
        
        log_debug("Setting programmatic change flag.")
        self.mw.is_programmatically_changing_text = True 
        
        self.mw.current_string_idx = -1 # Reset string selection when block changes
        log_debug(f"Reset current_string_idx to -1. Calling populate_strings for block {block_index}")
        self.ui_updater.populate_strings_for_block(block_index) # This sets/clears its own flag
        
        log_debug("Clearing programmatic change flag.")
        self.mw.is_programmatically_changing_text = False 
        log_debug("<-- ListSelectionHandler: block_selected finished.")


    def string_selected(self, current, previous):
        current_text = current.text() if current else 'None (item)'
        string_index = current.data(Qt.UserRole) if current else -1
        log_debug(f"--> ListSelectionHandler: string_selected. Item: '{current_text}', Index: {string_index}")
        
        log_debug("Setting programmatic change flag.")
        self.mw.is_programmatically_changing_text = True 
        original_text_for_display_field = ""
        edited_text_to_display = ""
        source = "N/A"

        if current is None or self.mw.current_block_idx == -1 or string_index == -1:
            log_debug("No valid item/block/index, clearing state.")
            self.mw.current_string_idx = -1
            self.mw.original_text_edit.setPlainText("")
            self.mw.edited_text_edit.setPlainText("")
        else:
            self.mw.current_string_idx = string_index
            log_debug(f"Set current_string_idx = {string_index}. Fetching text...")
            # Fetch original text specifically for the read-only display
            original_text_for_display_field = self.data_processor._get_string_from_source(
                self.mw.current_block_idx, self.mw.current_string_idx, self.mw.data, "original_data"
            )
            if original_text_for_display_field is None: original_text_for_display_field = "[ORIGINAL DATA ERROR]"

            # Fetch the text to display in the editable field (could be edited or original)
            edited_text_to_display, source = self.data_processor.get_current_string_text(
                self.mw.current_block_idx, self.mw.current_string_idx
            )
            log_debug(f"Text source for editor: '{source}'. Original length: {len(original_text_for_display_field)}, Editor length: {len(edited_text_to_display)}")
            
            log_debug("Setting text in editor panes...")
            self.mw.original_text_edit.setPlainText(original_text_for_display_field)
            self.mw.edited_text_edit.setPlainText(edited_text_to_display)
            log_debug("Text set.")
        
        log_debug("Clearing programmatic change flag.")
        self.mw.is_programmatically_changing_text = False 
        
        log_debug("Updating status bar...")
        self.ui_updater.update_status_bar()
        self.ui_updater.update_status_bar_selection()
        log_debug("<-- ListSelectionHandler: string_selected finished.")


    def rename_block(self, item):
        log_debug("--> ListSelectionHandler: rename_block triggered.")
        block_index = item.data(Qt.UserRole)
        if block_index is None: 
             log_debug("No block index found on item.")
             log_debug("<-- ListSelectionHandler: rename_block finished (Error).")
             return

        # Use string keys consistently for block_names dictionary
        block_index_str = str(block_index)
        current_name = self.mw.block_names.get(block_index_str, f"Block {block_index}")
        log_debug(f"Current name for index {block_index_str}: '{current_name}'. Prompting user...")
        
        new_name, ok = QInputDialog.getText(self.mw, "Rename Block", f"New name for '{current_name}':", text=current_name)

        if ok and new_name and new_name.strip() and new_name.strip() != current_name:
            actual_new_name = new_name.strip()
            log_debug(f"User entered new name: '{actual_new_name}'")
            self.mw.block_names[block_index_str] = actual_new_name # Use string key
            item.setText(actual_new_name)
            log_debug(f"Updated item text and block_names dict. Saving settings...")
            if hasattr(self.mw, 'save_editor_settings'): self.mw.save_editor_settings() 
        elif ok:
            log_debug(f"User entered empty or unchanged name: '{new_name}'. No action.")
        else:
            log_debug("User cancelled rename dialog.")
        log_debug("<-- ListSelectionHandler: rename_block finished.")