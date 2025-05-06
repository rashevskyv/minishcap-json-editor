import os
from PyQt5.QtCore import Qt
# QTextDocument більше не потрібен тут
# from PyQt5.QtGui import QTextDocument 
from utils import log_debug

# Константи ENTER_SYMBOL та VIOLET_COLOR_HEX більше не потрібні тут
# ENTER_SYMBOL = "↵"
# VIOLET_COLOR_HEX = "#A020F0" 

class UIUpdater:
    def __init__(self, main_window, data_processor):
        # log_debug("UIUpdater initialized.") 
        self.mw = main_window
        self.data_processor = data_processor

    # Допоміжні функції format_text_for_list та make_item_html_compatible більше не потрібні
    # def format_text_for_list(self, text): ...
    # def make_item_html_compatible(self, item, html_text): ...

    def populate_blocks(self):
        # ... (без змін) ...
        log_debug("[UIUpdater] populate_blocks called.")
        self.mw.block_list_widget.clear()
        if not self.mw.data: log_debug("[UIUpdater] populate_blocks: No original data."); return
        log_debug(f"[UIUpdater] populate_blocks: Populating {len(self.mw.data)} blocks.")
        for i in range(len(self.mw.data)):
            display_name = self.mw.block_names.get(str(i), f"Block {i}") 
            item = self.mw.block_list_widget.create_item(display_name, i)
            self.mw.block_list_widget.addItem(item)
        log_debug(f"[UIUpdater] populate_blocks: Added {self.mw.block_list_widget.count()} items.")


    def populate_strings_for_block(self, block_idx):
        # Повертаємо до логіки використання repr() або обрізання для списку
        log_debug(f"[UIUpdater] populate_strings_for_block for block_idx: {block_idx}")
        
        list_selection_handler = getattr(self.mw, 'list_selection_handler', None)
        string_list_signal_was_connected = False
        try:
            if list_selection_handler and hasattr(list_selection_handler, 'string_selected'):
                self.mw.string_list_widget.currentItemChanged.disconnect(list_selection_handler.string_selected)
                string_list_signal_was_connected = True
        except TypeError: string_list_signal_was_connected = False
        except AttributeError: string_list_signal_was_connected = False
        
        self.mw.is_programmatically_changing_text = True 
        self.mw.string_list_widget.clear() 
        self.mw.original_text_edit.clear() 
        self.mw.edited_text_edit.clear()   
        self.mw.is_programmatically_changing_text = False

        if block_idx == -1 or not self.mw.data or not (0 <= block_idx < len(self.mw.data)):
             self.mw.current_block_idx = -1; self.clear_status_bar()
             try:
                 if list_selection_handler and hasattr(list_selection_handler, 'string_selected') and string_list_signal_was_connected:
                     self.mw.string_list_widget.currentItemChanged.connect(list_selection_handler.string_selected)
             except AttributeError: pass
             return
             
        self.mw.current_block_idx = block_idx
        if not isinstance(self.mw.data[self.mw.current_block_idx], list):
              self.mw.current_block_idx = -1; self.clear_status_bar()
              try: 
                  if list_selection_handler and hasattr(list_selection_handler, 'string_selected') and string_list_signal_was_connected:
                      self.mw.string_list_widget.currentItemChanged.connect(list_selection_handler.string_selected)
              except AttributeError: pass
              return

        original_block_data = self.mw.data[self.mw.current_block_idx]
        current_string_item_to_select = None
        
        for i in range(len(original_block_data)):
            text_for_preview, source = self.data_processor.get_current_string_text(self.mw.current_block_idx, i)
            
            # <<< ПОВЕРНУЛИ СТАРИЙ СПОСІБ ФОРМУВАННЯ ТЕКСТУ ДЛЯ СПИСКУ >>>
            display_text_repr = repr(text_for_preview) # Використовуємо repr() для показу \n
            if len(display_text_repr) > 60:
                display_text_repr = display_text_repr[:57] + '...'
            # <<< КІНЕЦЬ ЗМІН >>>

            # Створюємо елемент списку з цим текстом
            item = self.mw.string_list_widget.create_item(f"{i}: {display_text_repr}", i) 
            self.mw.string_list_widget.addItem(item)
            
            if i == self.mw.current_string_idx: 
                current_string_item_to_select = item

        # --- Reselect Item Logic (без змін) ---
        if current_string_item_to_select:
             log_debug(f"[UIUpdater] Attempting to re-select string item index {self.mw.current_string_idx}.")
             self.mw.string_list_widget.setCurrentItem(current_string_item_to_select)
             if list_selection_handler and hasattr(list_selection_handler, 'string_selected'):
                  list_selection_handler.string_selected(current_string_item_to_select, None)
        # ... (решта логіки вибору) ...
        elif self.mw.string_list_widget.count() > 0 and self.mw.current_string_idx == -1: pass 
        else: 
            if not current_string_item_to_select and self.mw.current_string_idx != -1: self.mw.current_string_idx = -1
            if self.mw.string_list_widget.count() == 0: self.mw.current_string_idx = -1
            self.clear_status_bar()

        # --- Reconnect Signal (без змін) ---
        try:
            if list_selection_handler and hasattr(list_selection_handler, 'string_selected') and string_list_signal_was_connected:
                self.mw.string_list_widget.currentItemChanged.connect(list_selection_handler.string_selected)
        except AttributeError: pass
        except TypeError: pass 

        log_debug("[UIUpdater] populate_strings_for_block: Finished.")


    def update_string_list_item_text(self, string_idx, new_text_for_preview):
        log_debug(f"[UIUpdater] update_string_list_item_text for index {string_idx}")
        if not (0 <= string_idx < self.mw.string_list_widget.count()):
            return # Log removed for brevity
            
        item = self.mw.string_list_widget.item(string_idx)
        if item:
            # <<< ПОВЕРНУЛИ СТАРИЙ СПОСІБ ФОРМУВАННЯ ТЕКСТУ ДЛЯ СПИСКУ >>>
            display_text_repr = repr(new_text_for_preview) # Використовуємо repr()
            if len(display_text_repr) > 60:
                display_text_repr = display_text_repr[:57] + '...'
            item.setText(f"{string_idx}: {display_text_repr}") # Встановлюємо текст
            # <<< КІНЕЦЬ ЗМІН >>>
        # else: log removed for brevity

    # ... (решта методів UIUpdater без змін) ...
    def update_status_bar(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or not hasattr(self.mw, 'pos_len_label') or not self.mw.pos_len_label: return 
        cursor = self.mw.edited_text_edit.textCursor(); block = cursor.block()
        pos_in_block = cursor.positionInBlock(); line_text_len = len(block.text()) 
        self.mw.pos_len_label.setText(f"{pos_in_block}/{line_text_len}")

    def update_status_bar_selection(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or not hasattr(self.mw, 'selection_len_label') or not self.mw.selection_len_label: return
        cursor = self.mw.edited_text_edit.textCursor()
        selection_len = abs(cursor.selectionStart() - cursor.selectionEnd())
        self.mw.selection_len_label.setText(f"Sel: {selection_len}")

    def clear_status_bar(self):
        if hasattr(self.mw, 'pos_len_label') and self.mw.pos_len_label: self.mw.pos_len_label.setText("0/0")
        if hasattr(self.mw, 'selection_len_label') and self.mw.selection_len_label: self.mw.selection_len_label.setText("Sel: 0")

    def update_title(self):
        title = "JSON Text Editor"
        if self.mw.json_path: title += f" - [{os.path.basename(self.mw.json_path)}]"
        else: title += " - [No File Open]"
        if self.mw.unsaved_changes: title += " *"
        self.mw.setWindowTitle(title)

    def update_statusbar_paths(self):
        if hasattr(self.mw, 'original_path_label') and self.mw.original_path_label:
            orig_filename = os.path.basename(self.mw.json_path) if self.mw.json_path else "[not specified]"
            self.mw.original_path_label.setText(f"Original: {orig_filename}")
            self.mw.original_path_label.setToolTip(self.mw.json_path if self.mw.json_path else "Path to original file")
        if hasattr(self.mw, 'edited_path_label') and self.mw.edited_path_label:
            edited_filename = os.path.basename(self.mw.edited_json_path) if self.mw.edited_json_path else "[not specified]"
            self.mw.edited_path_label.setText(f"Changes: {edited_filename}")
            self.mw.edited_path_label.setToolTip(self.mw.edited_json_path if self.mw.edited_json_path else "Path to changes file")