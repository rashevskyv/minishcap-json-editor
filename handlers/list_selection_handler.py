# handlers/list_selection_handler.py
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QTextBlockFormat, QColor # Added for highlighting
from handlers.base_handler import BaseHandler
from utils import log_debug

class ListSelectionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        # For highlighting in preview_text_edit
        self.previous_selected_block_format = None # Renamed for clarity
        self.previous_selected_line_number = -1

    def block_selected(self, current_item, previous_item):
        if not current_item:
            log_debug("--> ListSelectionHandler: block_selected - No current item (selection cleared).")
            self.mw.current_block_idx = -1
            self.mw.current_string_idx = -1
            self.ui_updater.populate_strings_for_block(-1)
            self.clear_previous_line_highlight() 
            self.ui_updater.update_text_views() 
            log_debug("<-- ListSelectionHandler: block_selected finished (selection cleared).")
            return

        block_index = current_item.data(Qt.UserRole)
        block_name = current_item.text()
        log_debug(f"--> ListSelectionHandler: block_selected. Item: '{block_name}', Index: {block_index}")

        if self.mw.current_block_idx == block_index:
            log_debug(f"Block {block_index} is already selected. No change in block selection.")
            log_debug("<-- ListSelectionHandler: block_selected finished (block already selected).")
            return

        # log_debug("Setting programmatic change flag for block selection.") # Usually handled by caller or ui_updater
        # self.mw.is_programmatically_changing_text = True

        self.mw.current_block_idx = block_index
        self.mw.current_string_idx = -1  
        self.clear_previous_line_highlight() 

        log_debug(f"Reset current_string_idx to -1. Calling populate_strings for block {block_index}")
        # populate_strings_for_block sets its own programmatically_changing_text flag
        self.ui_updater.populate_strings_for_block(block_index) 

        # log_debug("Clearing programmatic change flag after block selection.")
        # self.mw.is_programmatically_changing_text = False
        log_debug("<-- ListSelectionHandler: block_selected finished.")

    def string_selected_from_preview(self, line_number: int):
        log_debug(f"--> ListSelectionHandler: string_selected_from_preview. Line number: {line_number}")

        if self.mw.current_block_idx == -1:
            log_debug("No block selected. Cannot select a string.")
            # self.mw.current_string_idx = -1 # Already -1 or will be set by populate_strings
            # self.ui_updater.update_text_views() # Will be cleared by populate_strings if block_idx is -1
            self.highlight_selected_line_in_preview(line_number) 
            log_debug("<-- ListSelectionHandler: string_selected_from_preview finished (no block).")
            return

        block_data = self.mw.data[self.mw.current_block_idx] if 0 <= self.mw.current_block_idx < len(self.mw.data) else None
        is_valid_line = False
        if isinstance(block_data, list) and 0 <= line_number < len(block_data):
            is_valid_line = True
        
        # Avoid excessive flag toggling if ui_updater handles it
        # self.mw.is_programmatically_changing_text = True

        if not is_valid_line:
            log_debug(f"Invalid line number {line_number} for current block data. Clearing string selection.")
            self.mw.current_string_idx = -1
        else:
            self.mw.current_string_idx = line_number
            log_debug(f"Set current_string_idx = {line_number}.")

        self.ui_updater.update_text_views() # This will update Original and Editable Text
        self.highlight_selected_line_in_preview(self.mw.current_string_idx) # Highlight based on the final current_string_idx

        # self.mw.is_programmatically_changing_text = False

        self.ui_updater.update_status_bar()
        self.ui_updater.update_status_bar_selection()
        log_debug("<-- ListSelectionHandler: string_selected_from_preview finished.")


    def highlight_selected_line_in_preview(self, line_number):
        if not hasattr(self.mw, 'preview_text_edit') or not self.mw.preview_text_edit:
            log_debug("highlight_selected_line_in_preview: preview_text_edit not found.")
            return

        log_debug(f"Highlighting line {line_number} in preview. Previous selected: {self.previous_selected_line_number}")
        
        # Temporarily disable updates to prevent flickering
        # self.mw.preview_text_edit.setUpdatesEnabled(False) # This can sometimes hide the update

        # Clear previous highlight
        self.clear_previous_line_highlight()

        if line_number < 0:
            # self.mw.preview_text_edit.setUpdatesEnabled(True)
            log_debug("No valid line to highlight (line_number < 0).")
            return

        block_to_highlight = self.mw.preview_text_edit.document().findBlockByNumber(line_number)

        if block_to_highlight.isValid():
            # Store the original format of the block before changing it
            self.previous_selected_block_format = QTextBlockFormat(block_to_highlight.blockFormat())
            self.previous_selected_line_number = line_number

            new_format = QTextBlockFormat(self.previous_selected_block_format)
            # Let's try a slightly different color for preview selection
            highlight_color = QColor("#D0E0F0") # A softer, distinct blue
            new_format.setBackground(highlight_color)

            # Apply the new format to the block
            # Create a temporary cursor for the block and apply the format
            # This avoids changing the main text cursor's selection state
            format_cursor = QTextCursor(block_to_highlight)
            format_cursor.beginEditBlock() # Group operation for undo/redo if ever needed, good practice
            format_cursor.setBlockFormat(new_format)
            format_cursor.endEditBlock()
            
            log_debug(f"Applied highlight to line {line_number} in preview_text_edit.")
        else:
            log_debug(f"Block for line {line_number} is not valid for highlighting in preview_text_edit.")

        # self.mw.preview_text_edit.setUpdatesEnabled(True)
        # self.mw.preview_text_edit.viewport().update() # Force repaint of the viewport

    def clear_previous_line_highlight(self):
        if hasattr(self.mw, 'preview_text_edit') and \
           self.previous_selected_block_format is not None and \
           self.previous_selected_line_number >= 0:

            block_to_restore = self.mw.preview_text_edit.document().findBlockByNumber(self.previous_selected_line_number)
            
            if block_to_restore.isValid() and block_to_restore.blockNumber() == self.previous_selected_line_number:
                # Restore the previously stored original format
                format_cursor = QTextCursor(block_to_restore)
                format_cursor.beginEditBlock()
                format_cursor.setBlockFormat(self.previous_selected_block_format)
                format_cursor.endEditBlock()
                log_debug(f"Cleared highlight from line {self.previous_selected_line_number} in preview_text_edit.")
            else:
                log_debug(f"Could not clear highlight, block for previous line {self.previous_selected_line_number} not found or changed in preview_text_edit.")

        # Reset stored information
        self.previous_selected_block_format = None
        self.previous_selected_line_number = -1

    def rename_block(self, item):
        log_debug("--> ListSelectionHandler: rename_block triggered.")
        block_index_from_data = item.data(Qt.UserRole) 
        
        if block_index_from_data is None:
            log_debug("No block index (UserRole) found on item.")
            log_debug("<-- ListSelectionHandler: rename_block finished (Error).")
            return

        block_index_str = str(block_index_from_data)
        current_name = self.mw.block_names.get(block_index_str, f"Block {block_index_from_data}")
        log_debug(f"Current name for block index {block_index_str} (from UserRole {block_index_from_data}): '{current_name}'. Prompting user...")

        new_name, ok = QInputDialog.getText(self.mw, "Rename Block", f"New name for '{current_name}':", text=current_name)

        if ok and new_name and new_name.strip() and new_name.strip() != current_name:
            actual_new_name = new_name.strip()
            log_debug(f"User entered new name: '{actual_new_name}'")
            self.mw.block_names[block_index_str] = actual_new_name
            item.setText(actual_new_name) 
            log_debug(f"Updated item text and block_names dict. Saving settings...")
            if hasattr(self.mw, 'save_editor_settings'):
                self.mw.save_editor_settings()
        elif ok:
            log_debug(f"User entered empty or unchanged name: '{new_name}'. No action taken.")
        else:
            log_debug("User cancelled rename dialog.")
        log_debug("<-- ListSelectionHandler: rename_block finished.")