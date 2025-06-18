import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QTextCursor
from PyQt5.QtWidgets import QApplication
from utils.logging_utils import log_debug
from utils.utils import convert_spaces_to_dots_for_display, convert_dots_to_spaces_from_editor, remove_curly_tags, calculate_string_width, remove_all_tags

class UIUpdater:
    def __init__(self, main_window, data_processor):
        self.mw = main_window
        self.data_processor = data_processor

    def populate_blocks(self):
        current_selection_block_idx = self.mw.block_list_widget.currentRow()
        self.mw.block_list_widget.clear()
        if not self.mw.data: 
            return
        
        problem_definitions = {}
        if self.mw.current_game_rules:
            problem_definitions = self.mw.current_game_rules.get_problem_definitions()

        for i in range(len(self.mw.data)):
            base_display_name = self.mw.block_names.get(str(i), f"Block {i}")
            
            block_problem_counts = {pid: 0 for pid in problem_definitions.keys()}
            
            if 0 <= i < len(self.mw.data) and isinstance(self.mw.data[i], list):
                for data_string_idx in range(len(self.mw.data[i])):
                    data_string_text, _ = self.data_processor.get_current_string_text(i, data_string_idx) 
                    if data_string_text is not None:
                        logical_sublines = str(data_string_text).split('\n')
                        for subline_local_idx in range(len(logical_sublines)):
                            problem_key = (i, data_string_idx, subline_local_idx)
                            subline_problems = self.mw.problems_per_subline.get(problem_key, set())
                            for problem_id in subline_problems:
                                if problem_id in block_problem_counts:
                                    block_problem_counts[problem_id] += 1
            
            display_name_with_issues = base_display_name
            issue_texts = []
            
            sorted_problem_ids_for_display = sorted(
                block_problem_counts.keys(),
                key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
            )

            for problem_id in sorted_problem_ids_for_display:
                count_sublines = block_problem_counts[problem_id]
                if count_sublines > 0:
                    short_name = self.mw.current_game_rules.get_short_problem_name(problem_id)
                    issue_texts.append(f"{count_sublines} {short_name}")
            
            if issue_texts:
                display_name_with_issues = f"{base_display_name} ({', '.join(issue_texts)})"
                
            item = self.mw.block_list_widget.create_item(display_name_with_issues, i)
            self.mw.block_list_widget.addItem(item)

        if 0 <= current_selection_block_idx < self.mw.block_list_widget.count():
            self.mw.block_list_widget.setCurrentRow(current_selection_block_idx)
        self.mw.block_list_widget.viewport().update()

    def update_block_item_text_with_problem_count(self, block_idx: int):
        if not hasattr(self.mw, 'block_list_widget') or not (0 <= block_idx < self.mw.block_list_widget.count()):
            return
        
        item = self.mw.block_list_widget.item(block_idx)
        if not item: return

        base_display_name = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
        
        problem_definitions = {}
        if self.mw.current_game_rules:
            problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        
        block_problem_counts = {pid: 0 for pid in problem_definitions.keys()}

        if block_idx < len(self.mw.data) and isinstance(self.mw.data[block_idx], list):
            for data_string_idx in range(len(self.mw.data[block_idx])):
                data_string_text, _ = self.data_processor.get_current_string_text(block_idx, data_string_idx)
                if data_string_text is not None:
                    logical_sublines = str(data_string_text).split('\n')
                    for subline_local_idx in range(len(logical_sublines)):
                        problem_key = (block_idx, data_string_idx, subline_local_idx)
                        subline_problems = self.mw.problems_per_subline.get(problem_key, set())
                        for problem_id in subline_problems:
                            if problem_id in block_problem_counts:
                                block_problem_counts[problem_id] += 1
        
        display_name_with_issues = base_display_name
        issue_texts = []

        sorted_problem_ids_for_display = sorted(
            block_problem_counts.keys(),
            key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
        )

        for problem_id in sorted_problem_ids_for_display:
            count_sublines = block_problem_counts[problem_id]
            if count_sublines > 0:
                short_name = self.mw.current_game_rules.get_short_problem_name(problem_id)
                issue_texts.append(f"{count_sublines} {short_name}")

        if issue_texts:
            display_name_with_issues = f"{base_display_name} ({', '.join(issue_texts)})"
        
        if item.text() != display_name_with_issues:
            item.setText(display_name_with_issues)
        
        self.mw.block_list_widget.viewport().update()

    def _apply_highlights_for_block(self, block_idx: int):
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit or not self.mw.current_game_rules:
            return

        preview_edit.highlightManager.clearAllProblemHighlights()
        
        problem_definitions = self.mw.current_game_rules.get_problem_definitions()

        for (b_idx, data_str_idx, subline_idx), problem_ids in self.mw.problems_per_subline.items():
            if b_idx != block_idx:
                continue
            
            if problem_ids:
                highest_priority_id = min(problem_ids, key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99))
                if highest_priority_id in problem_definitions:
                    preview_edit.highlightManager.addProblemLineHighlight(data_str_idx)


    def populate_strings_for_block(self, block_idx):
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        original_edit = getattr(self.mw, 'original_text_edit', None)
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        
        old_preview_scrollbar_value = preview_edit.verticalScrollBar().value() if preview_edit else 0
        
        self.mw.is_programmatically_changing_text = True 
        
        if preview_edit: preview_edit.highlightManager.clearAllProblemHighlights()
        if original_edit: original_edit.highlightManager.clearAllProblemHighlights()
        if edited_edit: edited_edit.highlightManager.clearAllProblemHighlights()

        if block_idx < 0 or not self.mw.data or block_idx >= len(self.mw.data) or not isinstance(self.mw.data[block_idx], list):
            if preview_edit: preview_edit.setPlainText("")
            if original_edit: original_edit.setPlainText("")
            if edited_edit: edited_edit.setPlainText("")
            self.update_text_views(); self.synchronize_original_cursor() 
            if preview_edit: preview_edit.verticalScrollBar().setValue(old_preview_scrollbar_value)
            self.mw.is_programmatically_changing_text = False 
            return
        
        self._apply_highlights_for_block(block_idx)
        
        if preview_edit and self.mw.current_game_rules:
            preview_lines = []
            for i in range(len(self.mw.data[block_idx])):
                text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, i)
                preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                preview_lines.append(preview_line_text)

            preview_full_text = "\n".join(preview_lines)
            
            if preview_edit.toPlainText() != preview_full_text:
                 preview_edit.setPlainText(preview_full_text)

            if self.mw.current_string_idx != -1 and \
               hasattr(preview_edit, 'highlightManager') and \
               0 <= self.mw.current_string_idx < preview_edit.document().blockCount(): 
                preview_edit.highlightManager.setPreviewSelectedLineHighlight(self.mw.current_string_idx)

            preview_edit.verticalScrollBar().setValue(old_preview_scrollbar_value)
        
        self.update_text_views() 
        self.synchronize_original_cursor() 
        self.mw.is_programmatically_changing_text = False 


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
            if hasattr(self.mw.original_text_edit, 'highlightManager'):
                self.mw.original_text_edit.highlightManager.setLinkedCursorPosition(-1, -1) 
            return

        edited_cursor = self.mw.edited_text_edit.textCursor()
        current_line_in_edited = edited_cursor.blockNumber()
        current_col_in_edited = edited_cursor.positionInBlock()

        if hasattr(self.mw.original_text_edit, 'highlightManager'):
            self.mw.original_text_edit.highlightManager.setLinkedCursorPosition(current_line_in_edited, current_col_in_edited)


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
        log_debug("UIUpdater: Cleared all problem block text. Highlights are managed by delegate.")

            
    def update_title(self):
        title = "JSON Text Editor"
        if self.mw.json_path: 
            title += f" - [{os.path.basename(self.mw.json_path)}]"
        else: 
            title += " - [No File Open]"
        if self.mw.unsaved_changes: 
            title += " *"
        self.mw.setWindowTitle(title)

    def update_plugin_status_label(self):
        if self.mw.plugin_status_label:
            if self.mw.current_game_rules:
                display_name = self.mw.current_game_rules.get_display_name()
                self.mw.plugin_status_label.setText(f"Plugin: {display_name}")
            else:
                self.mw.plugin_status_label.setText("Plugin: [None]")

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
        
        self.mw.is_programmatically_changing_text = True

        original_text_raw = ""
        edited_text_raw = ""
        if self.mw.current_block_idx != -1 and self.mw.current_string_idx != -1:
            original_text_raw = self.data_processor._get_string_from_source(
                self.mw.current_block_idx, self.mw.current_string_idx, self.mw.data, 
                "original_data_for_readonly_view"
            )
            edited_text_raw, _ = self.data_processor.get_current_string_text(self.mw.current_block_idx, self.mw.current_string_idx)
        
        if self.mw.current_game_rules and hasattr(self.mw.current_game_rules, 'get_text_representation_for_editor'):
            original_text_for_display_processed = self.mw.current_game_rules.get_text_representation_for_editor(str(original_text_raw))
            edited_text_for_display_processed = self.mw.current_game_rules.get_text_representation_for_editor(str(edited_text_raw))
        else: 
            original_text_for_display_processed = str(original_text_raw)
            edited_text_for_display_processed = str(edited_text_raw)

        original_text_for_display = convert_spaces_to_dots_for_display(original_text_for_display_processed, self.mw.show_multiple_spaces_as_dots)
        edited_text_for_display_converted = convert_spaces_to_dots_for_display(edited_text_for_display_processed, self.mw.show_multiple_spaces_as_dots)
        
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

        edited_widget = self.mw.edited_text_edit
        if edited_widget:
            if edited_widget.toPlainText() != edited_text_for_display_converted:
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
            
        self.mw.is_programmatically_changing_text = is_programmatic_call_flag_original

        if self.mw.edited_text_edit: 
            if self.mw.edited_text_edit.textCursor().hasSelection():
                self.update_status_bar_selection()
            else:
                self.update_status_bar()
        else: 
            self.clear_status_bar()