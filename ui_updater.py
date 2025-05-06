import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush 
from utils import log_debug, convert_spaces_to_dots_for_display 

class UIUpdater:
    def __init__(self, main_window, data_processor):
        self.mw = main_window
        self.data_processor = data_processor
        self.problem_block_color = QColor(Qt.yellow).lighter(150) 

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
        log_debug(f"UIUpdater: populate_strings_for_block for block_idx: {block_idx}. Current string_idx: {self.mw.current_string_idx}")
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        
        # Зберігаємо номери рядків, які наразі позначені як проблемні
        # Цей список буде використано для відновлення підсвічування після setPlainText
        problem_line_numbers_to_restore = []
        if preview_edit and hasattr(preview_edit, '_problem_line_selections') and preview_edit._problem_line_selections:
            problem_line_numbers_to_restore = [sel.cursor.blockNumber() for sel in preview_edit._problem_line_selections]
            log_debug(f"UIUpdater: Preserving problem line numbers to restore: {problem_line_numbers_to_restore}")

        self.mw.is_programmatically_changing_text = True 
        
        if preview_edit and hasattr(preview_edit, 'clearPreviewSelectedLineHighlight'):
            log_debug(f"UIUpdater: Clearing preview selected line highlight from {preview_edit.widget_id if hasattr(preview_edit, 'widget_id') else 'preview_edit'}.")
            preview_edit.clearPreviewSelectedLineHighlight()

        # Очищаємо проблемні підсвічування ТІЛЬКИ якщо блок справді змінюється.
        # Якщо це просто оновлення того ж блоку, проблемні підсвічування мають залишитися.
        if self.mw.current_block_idx != block_idx:
            if preview_edit and hasattr(preview_edit, 'clearProblemLineHighlights'):
                log_debug(f"UIUpdater: Block changed from {self.mw.current_block_idx} to {block_idx}. Clearing problem highlights.")
                preview_edit.clearProblemLineHighlights()
                problem_line_numbers_to_restore = [] # Немає сенсу відновлювати, якщо блок інший

        preview_lines = []
        if block_idx < 0 or not self.mw.data or block_idx >= len(self.mw.data) or not isinstance(self.mw.data[block_idx], list):
            if preview_edit: preview_edit.setPlainText("")
            if self.mw.current_block_idx != block_idx : self.mw.current_block_idx = -1
            self.mw.is_programmatically_changing_text = False
            self.update_text_views(); self.synchronize_original_cursor() 
            log_debug("UIUpdater: populate_strings_for_block: Invalid block_idx or no data.")
            return

        self.mw.current_block_idx = block_idx # Встановлюємо/оновлюємо поточний блок
        # Якщо блок не змінився, але current_string_idx скинувся (наприклад, після paste),
        # то self.mw.current_string_idx вже буде -1.
        # Якщо блок той самий і current_string_idx валідний, він не зміниться.
        
        original_block_data = self.mw.data[self.mw.current_block_idx]
        for i in range(len(original_block_data)):
            text_for_preview_raw, _ = self.data_processor.get_current_string_text(self.mw.current_block_idx, i)
            text_with_converted_spaces = convert_spaces_to_dots_for_display(str(text_for_preview_raw), self.mw.show_multiple_spaces_as_dots)
            preview_line = text_with_converted_spaces.replace('\n', getattr(self.mw, "newline_display_symbol", "↵"))
            preview_lines.append(preview_line)
        
        if preview_edit:
            log_debug(f"UIUpdater: Setting new plain text to preview_edit.")
            # Запам'ятовуємо, що _problem_line_selections зараз порожній у віджеті
            # після clearProblemLineHighlights (якщо блок змінився) або на початку.
            # Або якщо блок не змінився, то problem_line_numbers_to_restore містить їх.
            if hasattr(preview_edit, '_problem_line_selections'):
                 preview_edit._problem_line_selections = [] # Очищаємо список об'єктів перед setPlainText

            preview_edit.setPlainText("\n".join(preview_lines))
            # setPlainText очистив усі візуальні ExtraSelections.

            # Відновлюємо проблемні підсвічування, створюючи нові ExtraSelections
            if problem_line_numbers_to_restore and hasattr(preview_edit, 'addProblemLineHighlight'):
                log_debug(f"UIUpdater: Re-queuing {len(problem_line_numbers_to_restore)} problem highlights: {problem_line_numbers_to_restore}")
                for line_num in problem_line_numbers_to_restore:
                    preview_edit.addProblemLineHighlight(line_num) # Це додасть до _problem_line_selections
            
            # Застосовуємо всі накопичені (включаючи щойно відновлені проблемні)
            if hasattr(preview_edit, 'applyQueuedProblemHighlights'):
                preview_edit.applyQueuedProblemHighlights() # Це викличе _apply_all_extra_selections
            elif hasattr(preview_edit, '_apply_all_extra_selections'): # Fallback
                 preview_edit._apply_all_extra_selections()


        self.mw.is_programmatically_changing_text = False
        
        # Відновлюємо підсвічування вибраного рядка (якщо є)
        if preview_edit and self.mw.current_string_idx != -1 and hasattr(preview_edit, 'setPreviewSelectedLineHighlight'):
            preview_edit.setPreviewSelectedLineHighlight(self.mw.current_string_idx)
            # setPreviewSelectedLineHighlight вже викликає _apply_all_extra_selections,
            # тому проблемні теж мають бути враховані.

        self.update_text_views(); self.synchronize_original_cursor() 
        log_debug("UIUpdater: populate_strings_for_block: Finished.")

    # ... (решта методів UIUpdater без змін для цього завдання) ...
    def update_status_bar(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or not hasattr(self.mw, 'pos_len_label') or not self.mw.pos_len_label: return 
        cursor = self.mw.edited_text_edit.textCursor(); block = cursor.block()
        pos_in_block = cursor.positionInBlock(); line_text_len = len(block.text()) 
        self.mw.pos_len_label.setText(f"{pos_in_block}/{line_text_len}")
        self.synchronize_original_cursor() 
    def synchronize_original_cursor(self):
        if not hasattr(self.mw, 'edited_text_edit') or not hasattr(self.mw, 'original_text_edit') or not self.mw.edited_text_edit or not self.mw.original_text_edit: return
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1: 
            if hasattr(self.mw.original_text_edit, 'setLinkedCursorPosition'): self.mw.original_text_edit.setLinkedCursorPosition(-1, -1) 
            return
        edited_cursor = self.mw.edited_text_edit.textCursor()
        current_line_in_edited = edited_cursor.blockNumber(); current_col_in_edited = edited_cursor.positionInBlock()
        if hasattr(self.mw.original_text_edit, 'setLinkedCursorPosition'):
            self.mw.original_text_edit.setLinkedCursorPosition(current_line_in_edited, current_col_in_edited)
    def highlight_problem_block(self, block_idx: int, highlight: bool):
        if not hasattr(self.mw, 'block_list_widget'): return
        if 0 <= block_idx < self.mw.block_list_widget.count():
            item = self.mw.block_list_widget.item(block_idx)
            if item:
                if highlight: item.setBackground(QBrush(self.problem_block_color)); log_debug(f"Highlighted problem block: {block_idx}")
                else: item.setBackground(QBrush(Qt.transparent)); log_debug(f"Cleared highlight for block: {block_idx}")
    def clear_all_problem_block_highlights(self):
        if not hasattr(self.mw, 'block_list_widget'): return
        for i in range(self.mw.block_list_widget.count()):
            item = self.mw.block_list_widget.item(i)
            if item: item.setBackground(QBrush(Qt.transparent))
    def update_status_bar_selection(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or not hasattr(self.mw, 'selection_len_label') or not self.mw.selection_len_label: return
        cursor = self.mw.edited_text_edit.textCursor(); selection_len = abs(cursor.selectionStart() - cursor.selectionEnd())
        self.mw.selection_len_label.setText(f"Sel: {selection_len}")
    def clear_status_bar(self):
        if hasattr(self.mw, 'pos_len_label') and self.mw.pos_len_label: self.mw.pos_len_label.setText("0/0")
        if hasattr(self.mw, 'selection_len_label') and self.mw.selection_len_label: self.mw.selection_len_label.setText("Sel: 0")
    def update_title(self):
        title = "JSON Text Editor";
        if self.mw.json_path: title += f" - [{os.path.basename(self.mw.json_path)}]"
        else: title += " - [No File Open]"
        if self.mw.unsaved_changes: title += " *"; self.mw.setWindowTitle(title)
    def update_statusbar_paths(self):
        if hasattr(self.mw, 'original_path_label') and self.mw.original_path_label:
            orig_filename = os.path.basename(self.mw.json_path) if self.mw.json_path else "[not specified]"
            self.mw.original_path_label.setText(f"Original: {orig_filename}"); self.mw.original_path_label.setToolTip(self.mw.json_path if self.mw.json_path else "Path to original file")
        if hasattr(self.mw, 'edited_path_label') and self.mw.edited_path_label:
            edited_filename = os.path.basename(self.mw.edited_json_path) if self.mw.edited_json_path else "[not specified]"
            self.mw.edited_path_label.setText(f"Changes: {edited_filename}"); self.mw.edited_path_label.setToolTip(self.mw.edited_json_path if self.mw.edited_json_path else "Path to changes file")
    def update_text_views(self): 
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