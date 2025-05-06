import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor 
from utils import log_debug, convert_spaces_to_dots_for_display 

class UIUpdater:
    def __init__(self, main_window, data_processor):
        self.mw = main_window
        self.data_processor = data_processor
        # self.linked_highlight_color = QColor("#F5F5F5") # Старий колір для всього рядка
        # linked_cursor_block_color та linked_cursor_pos_color тепер в LineNumberedTextEdit

    # ... (populate_blocks - без змін) ...
    def populate_blocks(self):
        log_debug("[UIUpdater] populate_blocks called.")
        self.mw.block_list_widget.clear()
        if not self.mw.data: log_debug("[UIUpdater] populate_blocks: No original data."); return
        for i in range(len(self.mw.data)):
            display_name = self.mw.block_names.get(str(i), f"Block {i}") 
            item = self.mw.block_list_widget.create_item(display_name, i)
            self.mw.block_list_widget.addItem(item)
        log_debug(f"[UIUpdater] populate_blocks: Added {self.mw.block_list_widget.count()} items.")

    def populate_strings_for_block(self, block_idx):
        # ... (код майже без змін, але в кінці викликаємо synchronize_original_cursor) ...
        log_debug(f"[UIUpdater] populate_strings_for_block for block_idx: {block_idx}")
        self.mw.is_programmatically_changing_text = True 
        preview_lines = []
        if block_idx < 0 or not self.mw.data or block_idx >= len(self.mw.data) or not isinstance(self.mw.data[block_idx], list):
            self.mw.preview_text_edit.setPlainText("")
            if self.mw.current_block_idx != block_idx : self.mw.current_block_idx = -1
            if hasattr(self.mw, 'list_selection_handler'): self.mw.list_selection_handler.clear_previous_line_highlight()
            self.mw.is_programmatically_changing_text = False
            self.update_text_views(); self.synchronize_original_cursor() 
            log_debug("[UIUpdater] populate_strings_for_block: Invalid block_idx or no data.")
            return
        self.mw.current_block_idx = block_idx 
        original_block_data = self.mw.data[block_idx]
        for i in range(len(original_block_data)):
            text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, i)
            text_with_converted_spaces = convert_spaces_to_dots_for_display(str(text_for_preview_raw), self.mw.show_multiple_spaces_as_dots)
            preview_line = text_with_converted_spaces.replace('\n', getattr(self.mw, "newline_display_symbol", "↵"))
            preview_lines.append(preview_line)
        self.mw.preview_text_edit.setPlainText("\n".join(preview_lines))
        self.mw.is_programmatically_changing_text = False
        if hasattr(self.mw, 'list_selection_handler') and self.mw.current_string_idx != -1:
            self.mw.list_selection_handler.highlight_selected_line_in_preview(self.mw.current_string_idx)
        elif hasattr(self.mw, 'list_selection_handler'): self.mw.list_selection_handler.clear_previous_line_highlight()
        self.update_text_views(); self.synchronize_original_cursor() 
        log_debug("[UIUpdater] populate_strings_for_block: Finished.")


    def update_status_bar(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or not hasattr(self.mw, 'pos_len_label') or not self.mw.pos_len_label: return 
        cursor = self.mw.edited_text_edit.textCursor(); block = cursor.block()
        pos_in_block = cursor.positionInBlock(); line_text_len = len(block.text()) 
        self.mw.pos_len_label.setText(f"{pos_in_block}/{line_text_len}")
        self.synchronize_original_cursor() # Викликаємо синхронізацію тут


    def synchronize_original_cursor(self):
        """
        Імітує позицію курсору в original_text_edit на основі курсору в edited_text_edit.
        """
        if not hasattr(self.mw, 'edited_text_edit') or \
           not hasattr(self.mw, 'original_text_edit') or \
           not self.mw.edited_text_edit or \
           not self.mw.original_text_edit:
            return

        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            if hasattr(self.mw.original_text_edit, 'setLinkedCursorPosition'):
                self.mw.original_text_edit.setLinkedCursorPosition(-1, -1) # Очистити
            return

        edited_cursor = self.mw.edited_text_edit.textCursor()
        current_line_in_edited = edited_cursor.blockNumber() 
        current_col_in_edited = edited_cursor.positionInBlock()

        if hasattr(self.mw.original_text_edit, 'setLinkedCursorPosition'):
            self.mw.original_text_edit.setLinkedCursorPosition(current_line_in_edited, current_col_in_edited)
            # log_debug(f"Synchronized original editor cursor to line: {current_line_in_edited}, col: {current_col_in_edited}")

    # ... (решта методів: update_status_bar_selection, clear_status_bar, update_title, update_statusbar_paths, update_text_views - без змін) ...
    def update_status_bar_selection(self):
        # ... (код без змін) ...
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or not hasattr(self.mw, 'selection_len_label') or not self.mw.selection_len_label: return
        cursor = self.mw.edited_text_edit.textCursor(); selection_len = abs(cursor.selectionStart() - cursor.selectionEnd())
        self.mw.selection_len_label.setText(f"Sel: {selection_len}")
    def clear_status_bar(self):
        # ... (код без змін) ...
        if hasattr(self.mw, 'pos_len_label') and self.mw.pos_len_label: self.mw.pos_len_label.setText("0/0")
        if hasattr(self.mw, 'selection_len_label') and self.mw.selection_len_label: self.mw.selection_len_label.setText("Sel: 0")
    def update_title(self):
        # ... (код без змін) ...
        title = "JSON Text Editor";
        if self.mw.json_path: title += f" - [{os.path.basename(self.mw.json_path)}]"
        else: title += " - [No File Open]"
        if self.mw.unsaved_changes: title += " *"; self.mw.setWindowTitle(title)
    def update_statusbar_paths(self):
        # ... (код без змін) ...
        if hasattr(self.mw, 'original_path_label') and self.mw.original_path_label:
            orig_filename = os.path.basename(self.mw.json_path) if self.mw.json_path else "[not specified]"
            self.mw.original_path_label.setText(f"Original: {orig_filename}"); self.mw.original_path_label.setToolTip(self.mw.json_path if self.mw.json_path else "Path to original file")
        if hasattr(self.mw, 'edited_path_label') and self.mw.edited_path_label:
            edited_filename = os.path.basename(self.mw.edited_json_path) if self.mw.edited_json_path else "[not specified]"
            self.mw.edited_path_label.setText(f"Changes: {edited_filename}"); self.mw.edited_path_label.setToolTip(self.mw.edited_json_path if self.mw.edited_json_path else "Path to changes file")
    def update_text_views(self): 
        # ... (код без змін) ...
        self.mw.is_programmatically_changing_text = True; original_text_raw = ""; edited_text_raw = ""
        if self.mw.current_block_idx != -1 and self.mw.current_string_idx != -1:
            original_text_raw = self.data_processor._get_string_from_source(self.mw.current_block_idx, self.mw.current_string_idx, self.mw.data, "original_data")
            if original_text_raw is None: original_text_raw = "[ORIGINAL DATA ERROR]"
            edited_text_raw, source = self.data_processor.get_current_string_text(self.mw.current_block_idx, self.mw.current_string_idx)
        original_text_for_display = convert_spaces_to_dots_for_display(original_text_raw, self.mw.show_multiple_spaces_as_dots)
        edited_text_for_display = convert_spaces_to_dots_for_display(edited_text_raw, self.mw.show_multiple_spaces_as_dots)
        self.mw.original_text_edit.setPlainText(original_text_for_display if original_text_for_display is not None else "")
        self.mw.edited_text_edit.setPlainText(edited_text_for_display if edited_text_for_display is not None else "")
        self.mw.is_programmatically_changing_text = False; self.update_status_bar(); self.update_status_bar_selection()