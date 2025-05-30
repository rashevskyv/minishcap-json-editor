import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QTextCursor
from PyQt5.QtWidgets import QApplication
from utils.utils import log_debug, convert_spaces_to_dots_for_display, convert_dots_to_spaces_from_editor, remove_curly_tags, calculate_string_width, remove_all_tags

class UIUpdater:
    def __init__(self, main_window, data_processor):
        self.mw = main_window
        self.data_processor = data_processor
        self.critical_block_color = QColor(Qt.yellow).lighter(150) 
        self.warning_block_color = QColor(Qt.lightGray).lighter(110) 
        self.width_exceeded_block_color = QColor(255, 192, 203)
        self.short_line_block_color = QColor(173, 216, 230)

    def populate_blocks(self):
        log_debug("[UIUpdater] populate_blocks called.")
        current_selection_block_idx = self.mw.block_list_widget.currentRow()
        self.mw.block_list_widget.clear()
        if not self.mw.data: 
            log_debug("[UIUpdater] populate_blocks: No original data.")
            return
        
        for i in range(len(self.mw.data)):
            base_display_name = self.mw.block_names.get(str(i), f"Block {i}")
            
            num_critical = 0; num_warnings = 0; num_width_exceeded = 0; num_short = 0
            num_empty_odd = 0 # Новий лічильник
            block_key = str(i)

            if hasattr(self.mw, 'critical_problem_lines_per_block'):
                num_critical = len(self.mw.critical_problem_lines_per_block.get(block_key, set()))
            if hasattr(self.mw, 'warning_problem_lines_per_block'):
                num_warnings = len(self.mw.warning_problem_lines_per_block.get(block_key, set()))
            if hasattr(self.mw, 'width_exceeded_lines_per_block'):
                num_width_exceeded = len(self.mw.width_exceeded_lines_per_block.get(block_key, set()))
            if hasattr(self.mw, 'short_lines_per_block'):
                num_short = len(self.mw.short_lines_per_block.get(block_key, set()))
            if hasattr(self.mw, 'empty_odd_unisingle_subline_problem_strings'): # Нова перевірка
                num_empty_odd = len(self.mw.empty_odd_unisingle_subline_problem_strings.get(block_key, set()))

            display_name_with_issues = base_display_name
            issue_texts = []
            if num_critical > 0: issue_texts.append(f"{num_critical} crit")
            if num_warnings > 0: issue_texts.append(f"{num_warnings} warn")
            if num_width_exceeded > 0: issue_texts.append(f"{num_width_exceeded} width")
            if num_short > 0: issue_texts.append(f"{num_short} short")
            if num_empty_odd > 0: issue_texts.append(f"{num_empty_odd} emptyOdd") # Новий текст проблеми
            
            if issue_texts:
                display_name_with_issues = f"{base_display_name} ({', '.join(issue_texts)})"
                
            item = self.mw.block_list_widget.create_item(display_name_with_issues, i)
            self.mw.block_list_widget.addItem(item)

        if 0 <= current_selection_block_idx < self.mw.block_list_widget.count():
            self.mw.block_list_widget.setCurrentRow(current_selection_block_idx)
        self.mw.block_list_widget.viewport().update()


        log_debug(f"[UIUpdater] populate_blocks: Added {self.mw.block_list_widget.count()} items.")

    def update_block_item_text_with_problem_count(self, block_idx: int):
        if not hasattr(self.mw, 'block_list_widget') or not (0 <= block_idx < self.mw.block_list_widget.count()):
            return
        
        item = self.mw.block_list_widget.item(block_idx)
        if not item: return

        base_display_name = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
        num_critical = 0; num_warnings = 0; num_width_exceeded = 0; num_short = 0
        num_empty_odd = 0 # Новий лічильник
        block_key = str(block_idx)

        if hasattr(self.mw, 'critical_problem_lines_per_block'):
            num_critical = len(self.mw.critical_problem_lines_per_block.get(block_key, set()))
        if hasattr(self.mw, 'warning_problem_lines_per_block'):
            num_warnings = len(self.mw.warning_problem_lines_per_block.get(block_key, set()))
        if hasattr(self.mw, 'width_exceeded_lines_per_block'):
            num_width_exceeded = len(self.mw.width_exceeded_lines_per_block.get(block_key, set()))
        if hasattr(self.mw, 'short_lines_per_block'):
            num_short = len(self.mw.short_lines_per_block.get(block_key, set()))
        if hasattr(self.mw, 'empty_odd_unisingle_subline_problem_strings'): # Нова перевірка
            num_empty_odd = len(self.mw.empty_odd_unisingle_subline_problem_strings.get(block_key, set()))


        display_name_with_issues = base_display_name
        issue_texts = []
        if num_critical > 0: issue_texts.append(f"{num_critical} crit")
        if num_warnings > 0: issue_texts.append(f"{num_warnings} warn")
        if num_width_exceeded > 0: issue_texts.append(f"{num_width_exceeded} width")
        if num_short > 0: issue_texts.append(f"{num_short} short")
        if num_empty_odd > 0: issue_texts.append(f"{num_empty_odd} emptyOdd") # Новий текст проблеми

        
        if issue_texts:
            display_name_with_issues = f"{base_display_name} ({', '.join(issue_texts)})"
        
        text_changed = False
        if item.text() != display_name_with_issues:
            item.setText(display_name_with_issues)
            text_changed = True
        
        self.mw.block_list_widget.viewport().update()

    def _apply_empty_odd_subline_highlights_to_edited_text(self):
        # Цей метод більше не потрібен для підсвічування LineNumberArea в edited_text_edit,
        # оскільки це тепер робиться напряму в LNETPaintHandlers.lineNumberAreaPaintEvent
        # на основі pixel_width та непарності QTextBlock.
        # Залишаємо його порожнім або видаляємо, якщо він більше ніде не використовується.
        # Поки що просто закоментуємо його вміст, щоб не викликати помилок, якщо десь залишився виклик.
        # edited_edit = getattr(self.mw, 'edited_text_edit', None)
        # if not edited_edit or not hasattr(edited_edit, 'document'):
        #     log_debug("UIUpdater._apply_empty_odd_subline_highlights_to_edited_text: No edited_edit or document.")
        #     return

        # log_debug("UIUpdater._apply_empty_odd_subline_highlights_to_edited_text: Applying highlights...")
        # if hasattr(edited_edit, 'clearEmptyOddSublineHighlights'):
        #     log_debug("  Clearing previous empty odd subline highlights.")
        #     edited_edit.clearEmptyOddSublineHighlights()

        # doc = edited_edit.document()
        # block = doc.firstBlock()
        # qtextblock_index = 0
        # highlights_applied_this_run = False
        # while block.isValid():
        #     text = block.text()
        #     text_with_spaces = convert_dots_to_spaces_from_editor(text) if self.mw.show_multiple_spaces_as_dots else text
        #     text_no_tags = remove_all_tags(text_with_spaces)
            
        #     stripped_text_no_tags = text_no_tags.strip()
        #     is_empty = not stripped_text_no_tags or stripped_text_no_tags == "0"
            
        #     is_odd_qtextblock = (qtextblock_index + 1) % 2 != 0

        #     # log_debug(f"  QTextBlock {qtextblock_index}: Text='{text[:30]}...', NoTagsStripped='{stripped_text_no_tags}', IsEmpty={is_empty}, IsOdd={is_odd_qtextblock}")

        #     if is_empty and is_odd_qtextblock:
        #         if hasattr(edited_edit, 'addEmptyOddSublineHighlight'):
        #             # log_debug(f"    Highlighting QTextBlock {qtextblock_index} (BlockNum: {block.blockNumber()}) as empty odd.")
        #             edited_edit.addEmptyOddSublineHighlight(block.blockNumber())
        #             highlights_applied_this_run = True
            
        #     block = block.next()
        #     qtextblock_index += 1
        
        # if highlights_applied_this_run:
        #     # log_debug("  At least one empty odd subline highlight was added.")
        #     pass
        # else:
        #     # log_debug("  No empty odd subline highlights were added in this run.")
        #     pass

        # if hasattr(edited_edit, 'applyQueuedHighlights'):
        #     # log_debug("  Calling applyQueuedHighlights on edited_edit.")
        #     edited_edit.applyQueuedHighlights()
        # elif hasattr(edited_edit, 'highlightManager') and hasattr(edited_edit.highlightManager, 'applyHighlights'):
        #      # log_debug("  Calling highlightManager.applyHighlights on edited_edit.")
        #      edited_edit.highlightManager.applyHighlights()
        # log_debug("UIUpdater._apply_empty_odd_subline_highlights_to_edited_text: Finished.")
        pass


    def populate_strings_for_block(self, block_idx):
        log_debug(f"UIUpdater: populate_strings_for_block for block_idx: {block_idx}. Current string_idx: {self.mw.current_string_idx}")
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        original_edit = getattr(self.mw, 'original_text_edit', None)
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        
        old_preview_scrollbar_value = preview_edit.verticalScrollBar().value() if preview_edit else 0
        
        critical_lines_data = set()
        warning_lines_data = set()
        block_key_str = str(block_idx)

        if block_idx >=0: 
            if hasattr(self.mw, 'critical_problem_lines_per_block'):
                critical_lines_data = self.mw.critical_problem_lines_per_block.get(block_key_str, set()).copy()
            if hasattr(self.mw, 'warning_problem_lines_per_block'):
                warning_lines_data = self.mw.warning_problem_lines_per_block.get(block_key_str, set()).copy()

        self.mw.is_programmatically_changing_text = True 
        
        editors_to_clear_and_update_LNA = [preview_edit, original_edit, edited_edit]
        for editor_widget_loop in editors_to_clear_and_update_LNA: 
            if editor_widget_loop:
                if hasattr(editor_widget_loop, 'clearAllProblemTypeHighlights'):
                    editor_widget_loop.clearAllProblemTypeHighlights()
                if hasattr(editor_widget_loop, 'clearPreviewSelectedLineHighlight') and editor_widget_loop == preview_edit:
                    editor_widget_loop.clearPreviewSelectedLineHighlight()


        preview_lines = []
        if block_idx < 0 or not self.mw.data or block_idx >= len(self.mw.data) or not isinstance(self.mw.data[block_idx], list):
            if preview_edit: preview_edit.setPlainText("")
            if original_edit: original_edit.setPlainText("")
            if edited_edit: edited_edit.setPlainText("")
            self.update_text_views(); self.synchronize_original_cursor() 
            if preview_edit: preview_edit.verticalScrollBar().setValue(old_preview_scrollbar_value)
            for editor_widget_loop in editors_to_clear_and_update_LNA:
                if editor_widget_loop and hasattr(editor_widget_loop, 'lineNumberArea'): editor_widget_loop.lineNumberArea.update()
            self.mw.is_programmatically_changing_text = False 
            return
        
        if preview_edit:
            for i in range(len(self.mw.data[block_idx])):
                text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, i)
                text_with_converted_spaces = convert_spaces_to_dots_for_display(str(text_for_preview_raw), self.mw.show_multiple_spaces_as_dots)
                preview_line = text_with_converted_spaces.replace('\n', getattr(self.mw, "newline_display_symbol", "↵"))
                preview_lines.append(preview_line)
            
            if preview_edit.toPlainText() != "\n".join(preview_lines):
                 preview_edit.setPlainText("\n".join(preview_lines))
            
            for line_num in range(len(preview_lines)): 
                if line_num in critical_lines_data:
                    preview_edit.addCriticalProblemHighlight(line_num)
                elif line_num in warning_lines_data: 
                    preview_edit.addWarningLineHighlight(line_num)
            
            if hasattr(preview_edit, 'applyQueuedHighlights'): 
                preview_edit.applyQueuedHighlights()
            
            if self.mw.current_string_idx != -1 and \
               hasattr(preview_edit, 'setPreviewSelectedLineHighlight') and \
               self.mw.current_string_idx < preview_edit.document().blockCount(): 
                preview_edit.setPreviewSelectedLineHighlight(self.mw.current_string_idx)
            preview_edit.verticalScrollBar().setValue(old_preview_scrollbar_value)
        
        self.update_text_views() 
        
        for editor_widget_loop in editors_to_clear_and_update_LNA:
            if editor_widget_loop and hasattr(editor_widget_loop, 'lineNumberArea'): editor_widget_loop.lineNumberArea.update()

        self.synchronize_original_cursor() 
        self.mw.is_programmatically_changing_text = False 
        log_debug("UIUpdater: populate_strings_for_block: Finished.")


    def update_status_bar(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or \
           not all(hasattr(self.mw, label_name) for label_name in ['status_label_part1', 'status_label_part2', 'status_label_part3']):
            return 
        
        editor = self.mw.edited_text_edit
        cursor = editor.textCursor()

        if cursor.hasSelection():
            self.update_status_bar_selection() 
        else:
            block = cursor.block()
            pos_in_block = cursor.positionInBlock()
            
            line_text_with_dots = block.text()
            line_text_with_spaces = convert_dots_to_spaces_from_editor(line_text_with_dots)
            
            line_text_no_all_tags = remove_all_tags(line_text_with_spaces)
            line_len_no_tags = len(line_text_no_all_tags)
            line_len_with_tags = len(line_text_with_spaces)

            text_to_cursor_with_dots = line_text_with_dots[:pos_in_block]
            text_to_cursor_with_spaces = convert_dots_to_spaces_from_editor(text_to_cursor_with_dots)
            text_to_cursor_no_all_tags = remove_all_tags(text_to_cursor_with_spaces)
            pixel_width = calculate_string_width(text_to_cursor_no_all_tags, self.mw.font_map)
            
            self.mw.status_label_part1.setText(f"Pos: {pos_in_block}")
            self.mw.status_label_part2.setText(f"Line: {line_len_no_tags}/{line_len_with_tags}")
            self.mw.status_label_part3.setText(f"Width: {pixel_width}px")
        
        self.synchronize_original_cursor()


    def update_status_bar_selection(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or \
           not all(hasattr(self.mw, label_name) for label_name in ['status_label_part1', 'status_label_part2', 'status_label_part3']):
            return
        
        editor = self.mw.edited_text_edit
        cursor = editor.textCursor()

        if not cursor.hasSelection():
            block = cursor.block()
            pos_in_block = cursor.positionInBlock()
            line_text_with_dots = block.text()
            line_text_with_spaces = convert_dots_to_spaces_from_editor(line_text_with_dots)
            line_text_no_all_tags = remove_all_tags(line_text_with_spaces)
            line_len_no_tags = len(line_text_no_all_tags)
            line_len_with_tags = len(line_text_with_spaces)
            text_to_cursor_with_dots = line_text_with_dots[:pos_in_block]
            text_to_cursor_with_spaces = convert_dots_to_spaces_from_editor(text_to_cursor_with_dots)
            text_to_cursor_no_all_tags = remove_all_tags(text_to_cursor_with_spaces)
            pixel_width = calculate_string_width(text_to_cursor_no_all_tags, self.mw.font_map)
            self.mw.status_label_part1.setText(f"Pos: {pos_in_block}")
            self.mw.status_label_part2.setText(f"Line: {line_len_no_tags}/{line_len_with_tags}")
            self.mw.status_label_part3.setText(f"Width: {pixel_width}px")
            return

        selected_text_with_dots = cursor.selectedText()
        selected_text_with_spaces = convert_dots_to_spaces_from_editor(selected_text_with_dots)
        len_with_tags = len(selected_text_with_spaces)
        selected_text_no_all_tags = remove_all_tags(selected_text_with_spaces)
        len_no_tags = len(selected_text_no_all_tags)
        pixel_width = calculate_string_width(selected_text_no_all_tags, self.mw.font_map)
        
        sel_start_abs = cursor.selectionStart()
        sel_start_block_obj = editor.document().findBlock(sel_start_abs)
        sel_start_pos_in_block = sel_start_abs - sel_start_block_obj.position()
        
        self.mw.status_label_part1.setText(f"Sel: {len_no_tags}/{len_with_tags}")
        self.mw.status_label_part2.setText(f"At: {sel_start_pos_in_block}")
        self.mw.status_label_part3.setText(f"Width: {pixel_width}px")


    def clear_status_bar(self):
        if hasattr(self.mw, 'status_label_part1'): self.mw.status_label_part1.setText("Pos: 0")
        if hasattr(self.mw, 'status_label_part2'): self.mw.status_label_part2.setText("Line: 0/0")
        if hasattr(self.mw, 'status_label_part3'): self.mw.status_label_part3.setText("Width: 0px")


    def synchronize_original_cursor(self):
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
        pass 


    def clear_all_problem_block_highlights_and_text(self): 
        if not hasattr(self.mw, 'block_list_widget'): return
        for i in range(self.mw.block_list_widget.count()):
            item = self.mw.block_list_widget.item(i)
            if item:
                base_display_name = self.mw.block_names.get(str(i), f"Block {i}")
                if item.text() != base_display_name: 
                    item.setText(base_display_name)
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.viewport().update()
        log_debug("UIUpdater: Cleared all problem/warning/width/short block highlights and count texts.")

            
    def update_title(self):
        title = "JSON Text Editor"
        if self.mw.json_path: 
            title += f" - [{os.path.basename(self.mw.json_path)}]"
        else: 
            title += " - [No File Open]"
        if self.mw.unsaved_changes: 
            title += " *"
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

            
    def update_text_views(self): 
        is_programmatic_call_flag_original = self.mw.is_programmatically_changing_text
        log_debug(f"UIUpdater.update_text_views: Called. Programmatic: {is_programmatic_call_flag_original}. Current block: {self.mw.current_block_idx}, string: {self.mw.current_string_idx}")
        
        self.mw.is_programmatically_changing_text = True

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
        if orig_edit:
            if orig_edit.toPlainText() != original_text_for_display:
                orig_text_edit_cursor_pos = orig_edit.textCursor().position()
                orig_anchor_pos = orig_edit.textCursor().anchor()
                orig_has_selection = orig_edit.textCursor().hasSelection()
                orig_edit.setPlainText(original_text_for_display)
                new_orig_cursor = orig_edit.textCursor()
                new_orig_cursor.setPosition(min(orig_anchor_pos, len(original_text_for_display)))
                if orig_has_selection: new_orig_cursor.setPosition(min(orig_text_edit_cursor_pos, len(original_text_for_display)), QTextCursor.KeepAnchor)
                else: new_orig_cursor.setPosition(min(orig_text_edit_cursor_pos, len(original_text_for_display)))
                orig_edit.setTextCursor(new_orig_cursor)
            else:
                log_debug(f"UIUpdater: update_text_views - Content for {orig_edit.objectName()} matches. No setPlainText needed.")

        edited_widget = self.mw.edited_text_edit
        if edited_widget:
            if edited_widget.toPlainText() != edited_text_for_display_converted:
                log_debug(f"UIUpdater: update_text_views - Content mismatch for {edited_widget.objectName()}. Updating.")
                saved_edited_cursor_pos = edited_widget.textCursor().position()
                saved_edited_anchor_pos = edited_widget.textCursor().anchor()
                saved_edited_has_selection = edited_widget.textCursor().hasSelection()
                
                edited_widget.setPlainText(edited_text_for_display_converted)
                log_debug(f"  UIUpdater: setPlainText called on {edited_widget.objectName()}. Undo available after: {edited_widget.document().isUndoAvailable()}")

                restored_cursor = edited_widget.textCursor()
                new_edited_anchor_pos = min(saved_edited_anchor_pos, len(edited_text_for_display_converted))
                new_edited_cursor_pos = min(saved_edited_cursor_pos, len(edited_text_for_display_converted))
                restored_cursor.setPosition(new_edited_anchor_pos)
                if saved_edited_has_selection: restored_cursor.setPosition(new_edited_cursor_pos, QTextCursor.KeepAnchor)
                else: restored_cursor.setPosition(new_edited_cursor_pos)
                edited_widget.setTextCursor(restored_cursor)
            else:
                 log_debug(f"UIUpdater: update_text_views - Content for {edited_widget.objectName()} matches. No setPlainText needed.")
            
        self.mw.is_programmatically_changing_text = is_programmatic_call_flag_original

        if self.mw.edited_text_edit: 
            if self.mw.edited_text_edit.textCursor().hasSelection():
                self.update_status_bar_selection()
            else:
                self.update_status_bar()
        else: 
            self.clear_status_bar()