from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QTextBlockFormat, QColor
from .base_handler import BaseHandler
from utils.utils import log_debug, calculate_string_width, remove_all_tags

class ListSelectionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)

    def block_selected(self, current_item, previous_item):
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        
        self.mw.is_programmatically_changing_text = True

        if not current_item:
            log_debug("--> ListSelectionHandler: block_selected - No current item (selection cleared).")
            self.mw.current_block_idx = -1
            self.mw.current_string_idx = -1
            self.ui_updater.populate_strings_for_block(-1)
            log_debug("<-- ListSelectionHandler: block_selected finished (selection cleared).")
            self.mw.is_programmatically_changing_text = False
            return

        block_index = current_item.data(Qt.UserRole)
        block_name = current_item.text()
        log_debug(f"--> ListSelectionHandler: block_selected. Item: '{block_name}', Index: {block_index}")
        
        if self.mw.current_block_idx != block_index:
            self.mw.current_block_idx = block_index
            self.mw.current_string_idx = -1
            
        self.ui_updater.populate_strings_for_block(block_index)
        log_debug("<-- ListSelectionHandler: block_selected finished.")
        self.mw.is_programmatically_changing_text = False


    def string_selected_from_preview(self, line_number: int):
        log_debug(f"--> ListSelectionHandler: string_selected_from_preview. Data Line number: {line_number}")
        preview_edit = getattr(self.mw, 'preview_text_edit', None)

        self.mw.is_programmatically_changing_text = True

        if self.mw.current_block_idx == -1:
            log_debug("No block selected. Cannot select a string.")
            self.mw.current_string_idx = -1
            if preview_edit and hasattr(preview_edit, 'clearPreviewSelectedLineHighlight'):
                 preview_edit.clearPreviewSelectedLineHighlight()
            self.ui_updater.update_text_views()
            self.mw.is_programmatically_changing_text = False
            log_debug("<-- ListSelectionHandler: string_selected_from_preview finished (no block).")
            return

        is_valid_line = False
        if 0 <= self.mw.current_block_idx < len(self.mw.data) and \
           isinstance(self.mw.data[self.mw.current_block_idx], list) and \
           0 <= line_number < len(self.mw.data[self.mw.current_block_idx]):
            is_valid_line = True
        
        previous_string_idx = self.mw.current_string_idx
        
        if not is_valid_line:
            log_debug(f"Invalid line number {line_number} for current block data. Clearing string selection.")
            self.mw.current_string_idx = -1
            if preview_edit and hasattr(preview_edit, 'clearPreviewSelectedLineHighlight'):
                preview_edit.clearPreviewSelectedLineHighlight()
        else:
            self.mw.current_string_idx = line_number
            log_debug(f"Set current_string_idx = {line_number}.")
            if preview_edit and hasattr(preview_edit, 'setPreviewSelectedLineHighlight'):
                preview_edit.setPreviewSelectedLineHighlight(line_number)
            
            current_text_for_width_check, _ = self.data_processor.get_current_string_text(self.mw.current_block_idx, line_number)
            width_status_changed = False
            if hasattr(self.mw.editor_operation_handler, '_check_and_update_width_exceeded_status'):
                width_status_changed = self.mw.editor_operation_handler._check_and_update_width_exceeded_status(
                    self.mw.current_block_idx,
                    line_number,
                    str(current_text_for_width_check)
                )
            
            if width_status_changed or previous_string_idx != self.mw.current_string_idx :
                if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
                    self.ui_updater.update_block_item_text_with_problem_count(self.mw.current_block_idx)
                self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)


        self.ui_updater.update_text_views()
        
        self.mw.is_programmatically_changing_text = False
        log_debug("<-- ListSelectionHandler: string_selected_from_preview finished.")

    def rename_block(self, item):
        log_debug("--> ListSelectionHandler: rename_block triggered.")
        block_index_from_data = item.data(Qt.UserRole);
        if block_index_from_data is None: log_debug("No block index (UserRole) found on item."); return
        block_index_str = str(block_index_from_data)
        current_name = self.mw.block_names.get(block_index_str, f"Block {block_index_from_data}")
        new_name, ok = QInputDialog.getText(self.mw, "Rename Block", f"New name for '{current_name}':", text=current_name)
        if ok and new_name and new_name.strip() and new_name.strip() != current_name:
            actual_new_name = new_name.strip()
            self.mw.block_names[block_index_str] = actual_new_name; item.setText(actual_new_name)
        elif ok: log_debug(f"User entered empty or unchanged name: '{new_name}'. No action taken.")
        else: log_debug("User cancelled rename dialog.")
        log_debug("<-- ListSelectionHandler: rename_block finished.")