import os
from PyQt5.QtCore import Qt
from utils import log_debug

class UIUpdater:
    def __init__(self, main_window, data_processor):
        log_debug("UIUpdater initialized.")
        self.mw = main_window
        self.data_processor = data_processor

    def populate_blocks(self):
        log_debug("[UIUpdater] populate_blocks called.")
        self.mw.is_programmatically_changing_text = True # <<< SET FLAG
        self.mw.block_list_widget.clear()
        if not self.mw.data:
            log_debug("[UIUpdater] populate_blocks: No original data.")
            self.mw.is_programmatically_changing_text = False # <<< CLEAR FLAG
            return
        
        for i in range(len(self.mw.data)):
            display_name = self.mw.block_names.get(str(i), f"Block {i}") 
            item = self.mw.block_list_widget.create_item(display_name, i)
            self.mw.block_list_widget.addItem(item)
        log_debug(f"[UIUpdater] populate_blocks: Added {self.mw.block_list_widget.count()} items.")
        self.mw.is_programmatically_changing_text = False # <<< CLEAR FLAG


    def populate_strings_for_block(self, block_idx):
        log_debug(f"[UIUpdater] populate_strings_for_block for block_idx: {block_idx}, current_string_idx: {self.mw.current_string_idx}")
        
        self.mw.is_programmatically_changing_text = True # <<< SET FLAG at the beginning
        list_selection_handler = getattr(self.mw, 'list_selection_handler', None)
        string_list_signal_was_connected = False

        try:
            if list_selection_handler and hasattr(list_selection_handler, 'string_selected'):
                self.mw.string_list_widget.currentItemChanged.disconnect(list_selection_handler.string_selected)
                string_list_signal_was_connected = True
        except TypeError: string_list_signal_was_connected = False
        except AttributeError: string_list_signal_was_connected = False

        self.mw.string_list_widget.clear() 
        self.mw.original_text_edit.clear() # Programmatic, flag protects
        self.mw.edited_text_edit.clear()   # Programmatic, flag protects
        log_debug("[UIUpdater] Cleared string list and text edits.")

        if block_idx == -1 or not self.mw.data or not (0 <= block_idx < len(self.mw.data)):
            self.mw.current_block_idx = -1
            self.clear_status_bar()
            try:
                if list_selection_handler and hasattr(list_selection_handler, 'string_selected') and string_list_signal_was_connected:
                    self.mw.string_list_widget.currentItemChanged.connect(list_selection_handler.string_selected)
            except AttributeError: pass
            self.mw.is_programmatically_changing_text = False # <<< CLEAR FLAG before returning
            return

        self.mw.current_block_idx = block_idx
        if not isinstance(self.mw.data[self.mw.current_block_idx], list):
            self.mw.current_block_idx = -1; self.clear_status_bar()
            try: 
                if list_selection_handler and hasattr(list_selection_handler, 'string_selected') and string_list_signal_was_connected:
                    self.mw.string_list_widget.currentItemChanged.connect(list_selection_handler.string_selected)
            except AttributeError: pass
            self.mw.is_programmatically_changing_text = False # <<< CLEAR FLAG before returning
            return
            
        original_block_data = self.mw.data[self.mw.current_block_idx]
        current_string_item_to_select = None
        for i in range(len(original_block_data)):
            text_for_list_preview, source = self.data_processor.get_current_string_text(self.mw.current_block_idx, i)
            display_text_repr = repr(text_for_list_preview)
            if len(display_text_repr) > 60: display_text_repr = display_text_repr[:57] + '...'
            item = self.mw.string_list_widget.create_item(f"{i}: {display_text_repr}", i)
            self.mw.string_list_widget.addItem(item)
            if i == self.mw.current_string_idx: current_string_item_to_select = item

        if current_string_item_to_select:
            self.mw.string_list_widget.setCurrentItem(current_string_item_to_select) # Programmatic
            if list_selection_handler and hasattr(list_selection_handler, 'string_selected'):
                 # This call to string_selected will also set and clear the flag internally
                 list_selection_handler.string_selected(current_string_item_to_select, None)
        elif self.mw.string_list_widget.count() > 0 and self.mw.current_string_idx == -1:
             pass 
        else: 
            if not current_string_item_to_select and self.mw.current_string_idx != -1: self.mw.current_string_idx = -1
            if self.mw.string_list_widget.count() == 0: self.mw.current_string_idx = -1
            self.clear_status_bar()

        try:
            if list_selection_handler and hasattr(list_selection_handler, 'string_selected') and string_list_signal_was_connected:
                self.mw.string_list_widget.currentItemChanged.connect(list_selection_handler.string_selected)
        except AttributeError: pass
        except TypeError: pass # Already connected
        
        self.mw.is_programmatically_changing_text = False # <<< CLEAR FLAG at the end
        log_debug("[UIUpdater] populate_strings_for_block: Finished.")

    def update_string_list_item_text(self, string_idx, new_text_for_preview):
        if not (0 <= string_idx < self.mw.string_list_widget.count()):
            log_debug(f"[UIUpdater] Invalid string_idx {string_idx} for update_string_list_item_text. List count: {self.mw.string_list_widget.count()}.")
            return
        item = self.mw.string_list_widget.item(string_idx)
        if item:
            display_text_repr = repr(new_text_for_preview)
            if len(display_text_repr) > 60: display_text_repr = display_text_repr[:57] + '...'
            item.setText(f"{string_idx}: {display_text_repr}")

    def update_status_bar(self): # No programmatic text changes here
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or \
           not hasattr(self.mw, 'pos_len_label') or not self.mw.pos_len_label: return
        cursor = self.mw.edited_text_edit.textCursor()
        block = cursor.block()
        pos_in_block = cursor.positionInBlock()
        line_text_len = len(block.text()) 
        self.mw.pos_len_label.setText(f"{pos_in_block}/{line_text_len}")

    def update_status_bar_selection(self): # No programmatic text changes here
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or \
           not hasattr(self.mw, 'selection_len_label') or not self.mw.selection_len_label: return
        cursor = self.mw.edited_text_edit.textCursor()
        selection_len = abs(cursor.selectionStart() - cursor.selectionEnd())
        self.mw.selection_len_label.setText(f"Sel: {selection_len}")

    def clear_status_bar(self): # No programmatic text changes here
        if hasattr(self.mw, 'pos_len_label') and self.mw.pos_len_label: self.mw.pos_len_label.setText("0/0")
        if hasattr(self.mw, 'selection_len_label') and self.mw.selection_len_label: self.mw.selection_len_label.setText("Sel: 0")

    def update_title(self): # No programmatic text changes here
        title = "JSON Text Editor"
        if self.mw.json_path: title += f" - [{os.path.basename(self.mw.json_path)}]"
        else: title += " - [No File Open]"
        if self.mw.unsaved_changes: title += " *"
        self.mw.setWindowTitle(title)

    def update_statusbar_paths(self): # No programmatic text changes here
        if hasattr(self.mw, 'original_path_label') and self.mw.original_path_label:
            orig_filename = os.path.basename(self.mw.json_path) if self.mw.json_path else "[not specified]"
            self.mw.original_path_label.setText(f"Original: {orig_filename}")
            self.mw.original_path_label.setToolTip(self.mw.json_path if self.mw.json_path else "Path to original file")
        if hasattr(self.mw, 'edited_path_label') and self.mw.edited_path_label:
            edited_filename = os.path.basename(self.mw.edited_json_path) if self.mw.edited_json_path else "[not specified]"
            self.mw.edited_path_label.setText(f"Changes: {edited_filename}")
            self.mw.edited_path_label.setToolTip(self.mw.edited_json_path if self.mw.edited_json_path else "Path to changes file")