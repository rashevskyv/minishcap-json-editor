import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QTextCursor
from PyQt5.QtWidgets import QApplication
# Додаємо remove_curly_tags до імпортів
from utils import log_debug, convert_spaces_to_dots_for_display, convert_dots_to_spaces_from_editor, remove_curly_tags

class UIUpdater:
    def __init__(self, main_window, data_processor):
        self.mw = main_window
        self.data_processor = data_processor
        self.problem_block_color = QColor(Qt.yellow).lighter(150) 
        self.warning_block_color = QColor(Qt.lightGray).lighter(110) 

    # ... (populate_blocks, update_block_item_text_with_problem_count, populate_strings_for_block - без змін) ...
    def populate_blocks(self):
        log_debug("[UIUpdater] populate_blocks called.")
        self.mw.block_list_widget.clear()
        if not self.mw.data: 
            log_debug("[UIUpdater] populate_blocks: No original data.")
            return
        
        for i in range(len(self.mw.data)):
            base_display_name = self.mw.block_names.get(str(i), f"Block {i}")
            
            num_critical = 0; num_warnings = 0
            block_key = str(i)
            if hasattr(self.mw, 'critical_problem_lines_per_block'):
                num_critical = len(self.mw.critical_problem_lines_per_block.get(block_key, set()))
            if hasattr(self.mw, 'warning_problem_lines_per_block'):
                num_warnings = len(self.mw.warning_problem_lines_per_block.get(block_key, set()))
            
            display_name_with_issues = base_display_name
            issue_texts = []
            if num_critical > 0: issue_texts.append(f"{num_critical} crit")
            if num_warnings > 0: issue_texts.append(f"{num_warnings} warn")
            
            if issue_texts:
                display_name_with_issues = f"{base_display_name} ({', '.join(issue_texts)})"
                
            item = self.mw.block_list_widget.create_item(display_name_with_issues, i)
            self.mw.block_list_widget.addItem(item)

            if num_critical > 0:
                self.highlight_problem_block(i, True, is_critical=True)
            elif num_warnings > 0:
                self.highlight_problem_block(i, True, is_critical=False) 
            else: 
                self.highlight_problem_block(i, False)

        log_debug(f"[UIUpdater] populate_blocks: Added {self.mw.block_list_widget.count()} items.")

    def update_block_item_text_with_problem_count(self, block_idx: int):
        if not hasattr(self.mw, 'block_list_widget') or not (0 <= block_idx < self.mw.block_list_widget.count()):
            return
        
        item = self.mw.block_list_widget.item(block_idx)
        if not item: return

        base_display_name = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
        num_critical = 0; num_warnings = 0
        block_key = str(block_idx)

        if hasattr(self.mw, 'critical_problem_lines_per_block'):
            num_critical = len(self.mw.critical_problem_lines_per_block.get(block_key, set()))
        if hasattr(self.mw, 'warning_problem_lines_per_block'):
            num_warnings = len(self.mw.warning_problem_lines_per_block.get(block_key, set()))

        display_name_with_issues = base_display_name
        issue_texts = []
        if num_critical > 0: issue_texts.append(f"{num_critical} crit")
        if num_warnings > 0: issue_texts.append(f"{num_warnings} warn")

        if issue_texts:
            display_name_with_issues = f"{base_display_name} ({', '.join(issue_texts)})"
        
        current_item_text = item.text()
        if current_item_text != display_name_with_issues:
            item.setText(display_name_with_issues)
        
        if num_critical > 0:
            self.highlight_problem_block(block_idx, True, is_critical=True)
        elif num_warnings > 0:
            self.highlight_problem_block(block_idx, True, is_critical=False)
        else:
            self.highlight_problem_block(block_idx, False)


    def populate_strings_for_block(self, block_idx):
        log_debug(f"UIUpdater: populate_strings_for_block for block_idx: {block_idx}. Current string_idx: {self.mw.current_string_idx}")
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        
        old_scrollbar_value = 0
        if preview_edit: old_scrollbar_value = preview_edit.verticalScrollBar().value()

        critical_lines_to_restore = []
        warning_lines_to_restore = []
        block_key_str = str(block_idx)

        if preview_edit:
            if hasattr(self.mw, 'critical_problem_lines_per_block'):
                critical_lines_to_restore = list(self.mw.critical_problem_lines_per_block.get(block_key_str, set()))
            if hasattr(self.mw, 'warning_problem_lines_per_block'):
                warning_lines_to_restore = list(self.mw.warning_problem_lines_per_block.get(block_key_str, set()))

        self.mw.is_programmatically_changing_text = True 
        
        if preview_edit and hasattr(preview_edit, 'clearPreviewSelectedLineHighlight'):
            preview_edit.clearPreviewSelectedLineHighlight()

        if self.mw.current_block_idx != block_idx: 
            if preview_edit and hasattr(preview_edit, 'clearAllProblemTypeHighlights'):
                log_debug(f"UIUpdater: Block changed from {self.mw.current_block_idx} to {block_idx}. Clearing all problem/warning highlights for preview.")
                preview_edit.clearAllProblemTypeHighlights()
                critical_lines_to_restore = [] 
                warning_lines_to_restore = []

        preview_lines = []
        if block_idx < 0 or not self.mw.data or block_idx >= len(self.mw.data) or not isinstance(self.mw.data[block_idx], list):
            if preview_edit: preview_edit.setPlainText("")
            if self.mw.current_block_idx != -1 and block_idx < 0: self.mw.current_block_idx = -1
            self.update_text_views(); self.synchronize_original_cursor() 
            if preview_edit: preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
            self.mw.is_programmatically_changing_text = False 
            return

        self.mw.current_block_idx = block_idx 
        
        for i in range(len(self.mw.data[self.mw.current_block_idx])):
            text_for_preview_raw, _ = self.data_processor.get_current_string_text(self.mw.current_block_idx, i)
            text_with_converted_spaces = convert_spaces_to_dots_for_display(str(text_for_preview_raw), self.mw.show_multiple_spaces_as_dots)
            preview_line = text_with_converted_spaces.replace('\n', getattr(self.mw, "newline_display_symbol", "↵"))
            preview_lines.append(preview_line)
        
        if preview_edit:
            if hasattr(preview_edit, '_critical_problem_selections'): preview_edit._critical_problem_selections = [] 
            if hasattr(preview_edit, '_warning_problem_selections'): preview_edit._warning_problem_selections = []
            preview_edit.setPlainText("\n".join(preview_lines))

            if hasattr(preview_edit, 'addCriticalProblemHighlight'):
                for line_num in critical_lines_to_restore: preview_edit.addCriticalProblemHighlight(line_num)
            if hasattr(preview_edit, 'addWarningLineHighlight'):
                for line_num in warning_lines_to_restore: preview_edit.addWarningLineHighlight(line_num) 
            
            if hasattr(preview_edit, 'applyQueuedHighlights'):
                preview_edit.applyQueuedHighlights()
            
            if self.mw.current_string_idx != -1 and \
               hasattr(preview_edit, 'setPreviewSelectedLineHighlight') and \
               self.mw.current_string_idx < preview_edit.document().blockCount(): 
                preview_edit.setPreviewSelectedLineHighlight(self.mw.current_string_idx)
            elif hasattr(preview_edit, '_apply_all_extra_selections'): 
                 preview_edit._apply_all_extra_selections()

            preview_edit.verticalScrollBar().setValue(old_scrollbar_value)
        
        self.update_text_views(); self.synchronize_original_cursor() 
        self.mw.is_programmatically_changing_text = False 
        log_debug("UIUpdater: populate_strings_for_block: Finished.")


    def update_status_bar(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or \
           not hasattr(self.mw, 'pos_len_label') or not self.mw.pos_len_label:
            return 
        cursor = self.mw.edited_text_edit.textCursor()
        block = cursor.block()
        pos_in_block = cursor.positionInBlock() # Позиція курсора в поточній лінії (з урахуванням символів-точок)
        
        # Отримуємо текст лінії з віджета (з символами-точками)
        line_text_with_dots = block.text()
        # Конвертуємо його назад до тексту з пробілами для підрахунку "реальної" довжини
        line_text_with_spaces = convert_dots_to_spaces_from_editor(line_text_with_dots)
        
        # Довжина без тегів
        line_text_no_tags = remove_curly_tags(line_text_with_spaces)
        line_len_no_tags = len(line_text_no_tags)

        # Позиція курсора без тегів (це складніше, бо теги можуть бути до курсора)
        # Для простоти, поки що позицію показуємо відносно тексту з тегами (як є зараз)
        # або можна показувати позицію в тексті без тегів, якщо курсор не всередині тегу.
        # Поки що залишимо pos_in_block як є (відносно тексту з точками).
        
        # Альтернатива: показувати довжину поточного рядка без тегів та з тегами
        line_len_with_tags = len(line_text_with_spaces)
        self.mw.pos_len_label.setText(f"{pos_in_block} ({line_len_no_tags}/{line_len_with_tags})")
        
        self.synchronize_original_cursor()

    def update_status_bar_selection(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or \
           not hasattr(self.mw, 'selection_len_label') or not self.mw.selection_len_label:
            return
        
        cursor = self.mw.edited_text_edit.textCursor()
        if not cursor.hasSelection():
            self.mw.selection_len_label.setText("Sel: 0")
            return

        selected_text_with_dots = cursor.selectedText()
        # Важливо: selectedText() може містити символи нового рядка, якщо виділення багаторядкове.
        # remove_curly_tags та convert_dots_to_spaces_from_editor мають це обробляти.

        # 1. Конвертуємо точки-пробіли назад в пробіли
        selected_text_with_spaces = convert_dots_to_spaces_from_editor(selected_text_with_dots)
        len_with_tags = len(selected_text_with_spaces)

        # 2. Видаляємо теги {...}
        selected_text_no_tags = remove_curly_tags(selected_text_with_spaces)
        len_no_tags = len(selected_text_no_tags)
        
        self.mw.selection_len_label.setText(f"Sel: {len_no_tags}/{len_with_tags}")


    def clear_status_bar(self):
        if hasattr(self.mw, 'pos_len_label') and self.mw.pos_len_label:
            self.mw.pos_len_label.setText("0 (0/0)") # Оновлений формат
        if hasattr(self.mw, 'selection_len_label') and self.mw.selection_len_label:
            self.mw.selection_len_label.setText("Sel: 0/0") # Оновлений формат


    def synchronize_original_cursor(self):
        # ... (код без змін) ...
        if not hasattr(self.mw, 'edited_text_edit') or not hasattr(self.mw, 'original_text_edit') or \
           not self.mw.edited_text_edit or not self.mw.original_text_edit:
            return
        
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1 or \
           not self.mw.edited_text_edit.document().toPlainText(): 
            if hasattr(self.mw.original_text_edit, 'setLinkedCursorPosition'):
                self.mw.original_text_edit.setLinkedCursorPosition(-1, -1) 
            return

        edited_cursor = self.mw.edited_text_edit.textCursor()
        current_line_in_edited = edited_cursor.blockNumber()
        current_col_in_edited = edited_cursor.positionInBlock()

        if hasattr(self.mw.original_text_edit, 'setLinkedCursorPosition'):
            self.mw.original_text_edit.setLinkedCursorPosition(current_line_in_edited, current_col_in_edited)


    def highlight_problem_block(self, block_idx: int, highlight: bool, is_critical: bool = True):
        # ... (код без змін) ...
        if not hasattr(self.mw, 'block_list_widget'): return
        if 0 <= block_idx < self.mw.block_list_widget.count():
            item = self.mw.block_list_widget.item(block_idx)
            if item:
                if highlight:
                    color_to_use = self.problem_block_color if is_critical else self.warning_block_color
                    item.setBackground(QBrush(color_to_use))
                else: 
                    item.setBackground(QBrush(Qt.transparent))


    def clear_all_problem_block_highlights_and_text(self): 
        # ... (код без змін) ...
        if not hasattr(self.mw, 'block_list_widget'): return
        for i in range(self.mw.block_list_widget.count()):
            item = self.mw.block_list_widget.item(i)
            if item:
                item.setBackground(QBrush(Qt.transparent))
                base_display_name = self.mw.block_names.get(str(i), f"Block {i}")
                if item.text() != base_display_name: 
                    item.setText(base_display_name)
        log_debug("UIUpdater: Cleared all problem/warning block highlights and count texts.")

            
    def update_title(self):
        # ... (код без змін) ...
        title = "JSON Text Editor"
        if self.mw.json_path: 
            title += f" - [{os.path.basename(self.mw.json_path)}]"
        else: 
            title += " - [No File Open]"
        if self.mw.unsaved_changes: 
            title += " *"
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
        # ... (код без змін) ...
        is_programmatic_call = self.mw.is_programmatically_changing_text
        log_debug(f"UIUpdater.update_text_views: Called. Programmatic: {is_programmatic_call}. Current block: {self.mw.current_block_idx}, string: {self.mw.current_string_idx}")
        original_text_raw = ""
        edited_text_raw = ""
        if self.mw.current_block_idx != -1 and self.mw.current_string_idx != -1:
            original_text_raw = self.data_processor._get_string_from_source(
                self.mw.current_block_idx, self.mw.current_string_idx, self.mw.data, 
                "original_data_for_readonly_view" 
            )
            if original_text_raw is None: 
                log_debug(f"  Original text for Read-Only view is None for ({self.mw.current_block_idx}, {self.mw.current_string_idx}). Setting to '[ORIGINAL DATA ERROR]' for display.")
                original_text_raw = "[ORIGINAL DATA ERROR]"
            edited_text_raw, _ = self.data_processor.get_current_string_text(self.mw.current_block_idx, self.mw.current_string_idx)
        else: log_debug("  No active block/string selected. Text views will be cleared.")
        original_text_for_display = convert_spaces_to_dots_for_display(str(original_text_raw), self.mw.show_multiple_spaces_as_dots)
        edited_text_for_display_converted = convert_spaces_to_dots_for_display(str(edited_text_raw), self.mw.show_multiple_spaces_as_dots)
        orig_edit = self.mw.original_text_edit
        orig_text_edit_cursor_pos = orig_edit.textCursor().position()
        orig_anchor_pos = orig_edit.textCursor().anchor()
        orig_has_selection = orig_edit.textCursor().hasSelection()
        if orig_edit.toPlainText() != original_text_for_display: orig_edit.setPlainText(original_text_for_display)
        new_orig_cursor = orig_edit.textCursor()
        new_orig_cursor.setPosition(min(orig_anchor_pos, len(original_text_for_display)))
        if orig_has_selection: new_orig_cursor.setPosition(min(orig_text_edit_cursor_pos, len(original_text_for_display)), QTextCursor.KeepAnchor)
        else: new_orig_cursor.setPosition(min(orig_text_edit_cursor_pos, len(original_text_for_display)))
        orig_edit.setTextCursor(new_orig_cursor)
        edited_widget = self.mw.edited_text_edit
        text_in_widget_for_display = edited_widget.toPlainText()
        if is_programmatic_call or (text_in_widget_for_display != edited_text_for_display_converted):
            if text_in_widget_for_display != edited_text_for_display_converted :
                 log_debug(f"UIUpdater: update_text_views - Content mismatch or programmatic call. Updating edited_text_edit.")
            saved_edited_cursor_pos = edited_widget.textCursor().position()
            saved_edited_anchor_pos = edited_widget.textCursor().anchor()
            saved_edited_has_selection = edited_widget.textCursor().hasSelection()
            edited_widget.setPlainText(edited_text_for_display_converted)
            restored_cursor = edited_widget.textCursor()
            new_edited_anchor_pos = min(saved_edited_anchor_pos, len(edited_text_for_display_converted))
            new_edited_cursor_pos = min(saved_edited_cursor_pos, len(edited_text_for_display_converted))
            restored_cursor.setPosition(new_edited_anchor_pos)
            if saved_edited_has_selection: restored_cursor.setPosition(new_edited_cursor_pos, QTextCursor.KeepAnchor)
            else: restored_cursor.setPosition(new_edited_cursor_pos)
            edited_widget.setTextCursor(restored_cursor)
        self.update_status_bar()
        self.update_status_bar_selection()