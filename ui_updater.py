import os
from PyQt5.QtCore import Qt
from utils import log_debug, convert_spaces_to_dots_for_display # Оновлений імпорт

class UIUpdater:
    def __init__(self, main_window, data_processor):
        self.mw = main_window
        self.data_processor = data_processor

    def populate_blocks(self):
        log_debug("[UIUpdater] populate_blocks called.")
        self.mw.block_list_widget.clear()
        if not self.mw.data: log_debug("[UIUpdater] populate_blocks: No original data."); return
        # ... (решта коду без змін) ...
        for i in range(len(self.mw.data)):
            display_name = self.mw.block_names.get(str(i), f"Block {i}") 
            item = self.mw.block_list_widget.create_item(display_name, i)
            self.mw.block_list_widget.addItem(item)
        log_debug(f"[UIUpdater] populate_blocks: Added {self.mw.block_list_widget.count()} items.")


    def populate_strings_for_block(self, block_idx):
        log_debug(f"[UIUpdater] populate_strings_for_block for block_idx: {block_idx}")
        self.mw.is_programmatically_changing_text = True 
        
        preview_lines = []
        if block_idx < 0 or not self.mw.data or block_idx >= len(self.mw.data) or not isinstance(self.mw.data[block_idx], list):
            self.mw.preview_text_edit.setPlainText("")
            if self.mw.current_block_idx != block_idx : 
                 self.mw.current_block_idx = -1
            if hasattr(self.mw, 'list_selection_handler'):
                self.mw.list_selection_handler.clear_previous_line_highlight()
            self.mw.is_programmatically_changing_text = False
            self.update_text_views() 
            log_debug("[UIUpdater] populate_strings_for_block: Invalid block_idx or no data, cleared preview and text views.")
            return

        self.mw.current_block_idx = block_idx 
        original_block_data = self.mw.data[block_idx]

        for i in range(len(original_block_data)):
            text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, i)
            
            text_with_converted_spaces = convert_spaces_to_dots_for_display(
                str(text_for_preview_raw), 
                self.mw.show_multiple_spaces_as_dots
            )
            
            preview_line = text_with_converted_spaces.replace('\n', getattr(self.mw, "newline_display_symbol", "↵"))
            preview_lines.append(preview_line)

        self.mw.preview_text_edit.setPlainText("\n".join(preview_lines))
        # log_debug(f"[UIUpdater] Populated preview_text_edit with {len(preview_lines)} lines.")
        
        self.mw.is_programmatically_changing_text = False
        
        if hasattr(self.mw, 'list_selection_handler') and self.mw.current_string_idx != -1:
            self.mw.list_selection_handler.highlight_selected_line_in_preview(self.mw.current_string_idx)
        elif hasattr(self.mw, 'list_selection_handler'):
            self.mw.list_selection_handler.clear_previous_line_highlight()

        self.update_text_views() 
        log_debug("[UIUpdater] populate_strings_for_block: Finished.")

    def update_status_bar(self):
        # ... (код без змін) ...
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or not hasattr(self.mw, 'pos_len_label') or not self.mw.pos_len_label: return 
        cursor = self.mw.edited_text_edit.textCursor(); block = cursor.block()
        pos_in_block = cursor.positionInBlock(); line_text_len = len(block.text()) 
        self.mw.pos_len_label.setText(f"{pos_in_block}/{line_text_len}")

    def update_status_bar_selection(self):
        # ... (код без змін) ...
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or not hasattr(self.mw, 'selection_len_label') or not self.mw.selection_len_label: return
        cursor = self.mw.edited_text_edit.textCursor()
        selection_len = abs(cursor.selectionStart() - cursor.selectionEnd())
        self.mw.selection_len_label.setText(f"Sel: {selection_len}")

    def clear_status_bar(self):
        # ... (код без змін) ...
        if hasattr(self.mw, 'pos_len_label') and self.mw.pos_len_label: self.mw.pos_len_label.setText("0/0")
        if hasattr(self.mw, 'selection_len_label') and self.mw.selection_len_label: self.mw.selection_len_label.setText("Sel: 0")

    def update_title(self):
        # ... (код без змін) ...
        title = "JSON Text Editor"
        if self.mw.json_path: title += f" - [{os.path.basename(self.mw.json_path)}]"
        else: title += " - [No File Open]"
        if self.mw.unsaved_changes: title += " *"
        self.mw.setWindowTitle(title)

    def update_statusbar_paths(self):
        # ... (код без змін) ...
        if hasattr(self.mw, 'original_path_label') and self.mw.original_path_label:
            orig_filename = os.path.basename(self.mw.json_path) if self.mw.json_path else "[not specified]"
            self.mw.original_path_label.setText(f"Original: {orig_filename}")
            self.mw.original_path_label.setToolTip(self.mw.json_path if self.mw.json_path else "Path to original file")
        if hasattr(self.mw, 'edited_path_label') and self.mw.edited_path_label:
            edited_filename = os.path.basename(self.mw.edited_json_path) if self.mw.edited_json_path else "[not specified]"
            self.mw.edited_path_label.setText(f"Changes: {edited_filename}")
            self.mw.edited_path_label.setToolTip(self.mw.edited_json_path if self.mw.edited_json_path else "Path to changes file")

    def update_text_views(self): 
        log_debug(f"[UIUpdater] update_text_views called. Current block: {self.mw.current_block_idx}, string: {self.mw.current_string_idx}")
        self.mw.is_programmatically_changing_text = True

        original_text_raw = ""
        edited_text_raw = ""

        if self.mw.current_block_idx != -1 and self.mw.current_string_idx != -1:
            original_text_raw = self.data_processor._get_string_from_source(
                self.mw.current_block_idx, self.mw.current_string_idx, self.mw.data, "original_data"
            )
            if original_text_raw is None: original_text_raw = "[ORIGINAL DATA ERROR]"

            edited_text_raw, source = self.data_processor.get_current_string_text(
                self.mw.current_block_idx, self.mw.current_string_idx
            )
        
        # Конвертація для відображення (для всіх полів)
        original_text_for_display = convert_spaces_to_dots_for_display(
            original_text_raw, 
            self.mw.show_multiple_spaces_as_dots
        )
        edited_text_for_display = convert_spaces_to_dots_for_display(
            edited_text_raw, 
            self.mw.show_multiple_spaces_as_dots
        )
        
        self.mw.original_text_edit.setPlainText(original_text_for_display if original_text_for_display is not None else "")
        self.mw.edited_text_edit.setPlainText(edited_text_for_display if edited_text_for_display is not None else "")
        
        self.mw.is_programmatically_changing_text = False
        self.update_status_bar() 
        self.update_status_bar_selection()
        log_debug("[UIUpdater] update_text_views finished.")