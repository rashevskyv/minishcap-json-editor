from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QTextBlockFormat, QColor 
from handlers.base_handler import BaseHandler
from utils import log_debug

class ListSelectionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)

    def block_selected(self, current_item, previous_item):
        preview_edit = getattr(self.mw, 'preview_text_edit', None)

        if not current_item:
            log_debug("--> ListSelectionHandler: block_selected - No current item (selection cleared).")
            self.mw.current_block_idx = -1
            self.mw.current_string_idx = -1
            if preview_edit and hasattr(preview_edit, 'clearPreviewSelectedLineHighlight'):
                preview_edit.clearPreviewSelectedLineHighlight()
            if preview_edit and hasattr(preview_edit, 'clearProblemLineHighlights'): 
                preview_edit.clearProblemLineHighlights()
            self.ui_updater.populate_strings_for_block(-1) # Це викличе update_text_views та synchronize_original_cursor
            log_debug("<-- ListSelectionHandler: block_selected finished (selection cleared).")
            return

        block_index = current_item.data(Qt.UserRole)
        block_name = current_item.text()
        log_debug(f"--> ListSelectionHandler: block_selected. Item: '{block_name}', Index: {block_index}")

        if self.mw.current_block_idx == block_index:
            log_debug(f"Block {block_index} is already selected. No change in block selection.")
            log_debug("<-- ListSelectionHandler: block_selected finished (block already selected).")
            return

        self.mw.current_block_idx = block_index
        self.mw.current_string_idx = -1  
        
        if preview_edit and hasattr(preview_edit, 'clearPreviewSelectedLineHighlight'):
            preview_edit.clearPreviewSelectedLineHighlight()
        if preview_edit and hasattr(preview_edit, 'clearProblemLineHighlights'): 
            preview_edit.clearProblemLineHighlights()
            
        self.ui_updater.populate_strings_for_block(block_index) 
        log_debug("<-- ListSelectionHandler: block_selected finished.")

    def string_selected_from_preview(self, line_number: int):
        log_debug(f"--> ListSelectionHandler: string_selected_from_preview. Line number: {line_number}")
        preview_edit = getattr(self.mw, 'preview_text_edit', None)

        if self.mw.current_block_idx == -1:
            log_debug("No block selected. Cannot select a string.")
            self.mw.current_string_idx = -1 # Переконуємося, що індекс скинутий
            if preview_edit and hasattr(preview_edit, 'setPreviewSelectedLineHighlight'):
                 preview_edit.setPreviewSelectedLineHighlight(line_number) # Може підсвітити невалідний рядок, якщо дані порожні
            self.ui_updater.update_text_views()
            log_debug("<-- ListSelectionHandler: string_selected_from_preview finished (no block).")
            return

        is_valid_line = False
        if 0 <= self.mw.current_block_idx < len(self.mw.data) and \
           isinstance(self.mw.data[self.mw.current_block_idx], list) and \
           0 <= line_number < len(self.mw.data[self.mw.current_block_idx]):
            is_valid_line = True
        
        if not is_valid_line:
            log_debug(f"Invalid line number {line_number} for current block data. Clearing string selection.")
            self.mw.current_string_idx = -1
        else:
            self.mw.current_string_idx = line_number
            log_debug(f"Set current_string_idx = {line_number}.")
            
        self.ui_updater.update_text_views() # Це оновить original/edited та викличе synchronize_original_cursor
        
        if preview_edit and hasattr(preview_edit, 'setPreviewSelectedLineHighlight'):
            if is_valid_line:
                preview_edit.setPreviewSelectedLineHighlight(line_number)
            else: # Якщо рядок невалідний, але клік був, очистити попереднє виділення
                preview_edit.clearPreviewSelectedLineHighlight()
        
        # self.ui_updater.update_status_bar() # Вже викликається з update_text_views
        # self.ui_updater.update_status_bar_selection() # Вже викликається з update_text_views
        log_debug("<-- ListSelectionHandler: string_selected_from_preview finished.")

    def rename_block(self, item):
        # ... (код без змін) ...
        log_debug("--> ListSelectionHandler: rename_block triggered.")
        block_index_from_data = item.data(Qt.UserRole); 
        if block_index_from_data is None: log_debug("No block index (UserRole) found on item."); return
        block_index_str = str(block_index_from_data)
        current_name = self.mw.block_names.get(block_index_str, f"Block {block_index_from_data}")
        new_name, ok = QInputDialog.getText(self.mw, "Rename Block", f"New name for '{current_name}':", text=current_name)
        if ok and new_name and new_name.strip() and new_name.strip() != current_name:
            actual_new_name = new_name.strip()
            self.mw.block_names[block_index_str] = actual_new_name; item.setText(actual_new_name) 
            if hasattr(self.mw, 'save_editor_settings'): self.mw.save_editor_settings()
        elif ok: log_debug(f"User entered empty or unchanged name: '{new_name}'. No action taken.")
        else: log_debug("User cancelled rename dialog.")
        log_debug("<-- ListSelectionHandler: rename_block finished.")