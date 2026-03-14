# --- START OF FILE handlers/list_selection_handler.py ---
from PyQt5.QtWidgets import QInputDialog, QTextEdit 
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTextCursor, QTextBlockFormat, QColor, QTextBlock 
from .base_handler import BaseHandler
from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN

class ListSelectionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self._restoring_selection = False
    def block_selected(self, current_item, previous_item):
        if self.mw.is_loading_data or self.mw.is_programmatically_changing_text:
            return
            
        self.mw.is_programmatically_changing_text = True
        try:
            preview_edit = getattr(self.mw, 'preview_text_edit', None)
            
            if previous_item:
                previous_block_idx = previous_item.data(0, Qt.UserRole)
                if previous_block_idx is not None:
                    self.ui_updater.update_block_item_text_with_problem_count(previous_block_idx)

            if not current_item:
                if not self.mw.is_loading_data:
                    if not self._restoring_selection and self.mw.current_block_idx != -1:
                        self._restoring_selection = True
                        QTimer.singleShot(0, self._restore_block_selection)
                
                self.mw.current_block_idx = -1
                self.mw.current_string_idx = -1
                self.ui_updater.populate_strings_for_block(-1)
                if hasattr(self.mw, 'string_settings_updater'):
                    self.mw.string_settings_updater.update_string_settings_panel()
                self._update_block_toolbar_button_states(-1)
                return

            block_index = current_item.data(0, Qt.UserRole)
            if block_index is None:
                self.mw.current_block_idx = -1
                self.mw.current_string_idx = -1
                self.ui_updater.populate_strings_for_block(-1)
                if hasattr(self.mw, 'string_settings_updater'):
                    self.mw.string_settings_updater.update_string_settings_panel()
                self._update_block_toolbar_button_states(-1)
                return
            
            if self.mw.current_block_idx != block_index:
                old_block = self.mw.current_block_idx
                old_string = self.mw.current_string_idx
                self.mw.current_block_idx = block_index
                
                # Restore selection if project
                restored_s_idx = 0
                if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                    project = self.mw.project_manager.project
                    if hasattr(self.mw, 'block_to_project_file_map'):
                        project_block_idx = self.mw.block_to_project_file_map.get(block_index)
                        if project_block_idx is not None and project_block_idx < len(project.blocks):
                            restored_s_idx = project.blocks[project_block_idx].last_selected_string_idx

                self.mw.current_string_idx = restored_s_idx
                
                if hasattr(self.mw, 'undo_manager'):
                    self.mw.undo_manager.record_navigation(block_index, restored_s_idx, old_block, old_string)

                # Use QTimer to ensure populate_strings_for_block has finished before selecting string
                QTimer.singleShot(0, lambda idx=restored_s_idx: self.string_selected_from_preview(idx))
                
            self.ui_updater.populate_strings_for_block(block_index)
            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_font_combobox()
                self.mw.string_settings_updater.update_string_settings_panel()

            # Update toolbar button states
            self._update_block_toolbar_button_states(block_index)
        finally:
            self.mw.is_programmatically_changing_text = False

    def _restore_block_selection(self):
        if self.mw.current_block_idx != -1:
            from PyQt5.QtWidgets import QTreeWidgetItemIterator
            iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
            while iterator.value():
                if iterator.value().data(0, Qt.UserRole) == self.mw.current_block_idx:
                    self.mw.block_list_widget.setCurrentItem(iterator.value())
                    break
                iterator += 1
        self._restoring_selection = False

    def _update_block_toolbar_button_states(self, block_idx: int):
        """Update the enabled/disabled state of toolbar buttons based on selection and position."""
        has_project = bool(hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project)
        
        # Enable Add Folder if project exists
        if hasattr(self.mw, 'add_folder_button'):
            self.mw.add_folder_button.setEnabled(has_project)

        current_item = self.mw.block_list_widget.currentItem()
        if has_project and current_item:
            parent = current_item.parent() or self.mw.block_list_widget.invisibleRootItem()
            index = parent.indexOfChild(current_item)
            is_first = index == 0
            is_last = index == parent.childCount() - 1

            # Enable delete and rename for any selected block or folder
            if hasattr(self.mw, 'delete_block_button'):
                self.mw.delete_block_button.setEnabled(True)
            if hasattr(self.mw, 'rename_block_button'):
                self.mw.rename_block_button.setEnabled(True)

            # Enable move up/down based on siblings in the tree
            if hasattr(self.mw, 'move_block_up_button'):
                self.mw.move_block_up_button.setEnabled(not is_first)
            if hasattr(self.mw, 'move_block_down_button'):
                self.mw.move_block_down_button.setEnabled(not is_last)
        else:
            # Disable selection-dependent buttons
            if hasattr(self.mw, 'delete_block_button'):
                self.mw.delete_block_button.setEnabled(False)
            if hasattr(self.mw, 'rename_block_button'):
                self.mw.rename_block_button.setEnabled(False)
            if hasattr(self.mw, 'move_block_up_button'):
                self.mw.move_block_up_button.setEnabled(False)
            if hasattr(self.mw, 'move_block_down_button'):
                self.mw.move_block_down_button.setEnabled(False)


    def string_selected_from_preview(self, line_number: int, is_manual_click: bool = False):
        preview_edit = getattr(self.mw, 'preview_text_edit', None)

        original_programmatic_state = self.mw.is_programmatically_changing_text
        self.mw.is_programmatically_changing_text = True

        if self.mw.current_block_idx == -1:
            self.mw.current_string_idx = -1
            if preview_edit and hasattr(preview_edit, 'highlightManager'):
                 preview_edit.highlightManager.clearPreviewSelectedLineHighlight()
            self.ui_updater.update_text_views()
            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_string_settings_panel()
            self.mw.is_programmatically_changing_text = original_programmatic_state
            return

        is_valid_line = False
        if 0 <= self.mw.current_block_idx < len(self.mw.data) and \
           isinstance(self.mw.data[self.mw.current_block_idx], list) and \
           0 <= line_number < len(self.mw.data[self.mw.current_block_idx]):
            is_valid_line = True
        
        previous_string_idx = self.mw.current_string_idx
        
        if not is_valid_line:
            self.mw.current_string_idx = -1
            if preview_edit and hasattr(preview_edit, 'highlightManager'):
                preview_edit.highlightManager.clearPreviewSelectedLineHighlight()
        else:
            self.mw.current_string_idx = line_number
            
            if hasattr(self.mw, 'undo_manager') and not original_programmatic_state:
                self.mw.undo_manager.record_navigation(self.mw.current_block_idx, line_number, self.mw.current_block_idx, previous_string_idx)

            if previous_string_idx != self.mw.current_string_idx and previous_string_idx != -1:
                self.ui_updater.update_block_item_text_with_problem_count(self.mw.current_block_idx)
            
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
            
            # Save selection to project
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                project = self.mw.project_manager.project
                if hasattr(self.mw, 'block_to_project_file_map'):
                    project_block_idx = self.mw.block_to_project_file_map.get(self.mw.current_block_idx)
                    if project_block_idx is not None and project_block_idx < len(project.blocks):
                        project.blocks[project_block_idx].last_selected_string_idx = line_number

        self.ui_updater.update_text_views()
        if hasattr(self.mw, 'string_settings_updater'):
            self.mw.string_settings_updater.update_string_settings_panel()

        self.mw.is_programmatically_changing_text = original_programmatic_state

        if preview_edit and self.mw.current_string_idx != -1 and \
           0 <= self.mw.current_string_idx < preview_edit.document().blockCount():
            if hasattr(preview_edit, 'set_selected_lines'): 
                preview_edit.set_selected_lines([self.mw.current_string_idx])
            
            block_to_show = preview_edit.document().findBlockByNumber(self.mw.current_string_idx)
            if block_to_show.isValid():
                cursor = QTextCursor(block_to_show)
                preview_edit.setTextCursor(cursor)
                # Use a small timer to ensure the widget has finished layout after potential text updates
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(10, lambda: preview_edit.ensureCursorVisible())
        elif preview_edit and hasattr(preview_edit, 'highlightManager'): 
            preview_edit.highlightManager.clearPreviewSelectedLineHighlight()
            
        if self.mw.current_string_idx != -1 and hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
            self.mw.edited_text_edit.setFocus()
            cursor = self.mw.edited_text_edit.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.mw.edited_text_edit.setTextCursor(cursor)


    def rename_block(self, item):
        if not item: return
        self.mw.block_list_widget.editItem(item, 0)

    def handle_block_item_text_changed(self, item, column):
        """Handle inline renaming of block or folder."""
        if self.mw.is_loading_data or self.mw.is_programmatically_changing_text:
            return
            
        new_text = item.text(column).strip()
        if not new_text:
            # Revert if empty
            self.ui_updater.populate_blocks()
            return

        # Check if it's a virtual folder or a block
        folder_id = item.data(0, Qt.UserRole + 1)
        block_index_from_data = item.data(0, Qt.UserRole)
        merged_ids = item.data(0, Qt.UserRole + 2)

        self.mw.is_programmatically_changing_text = True
        try:
            if block_index_from_data is not None:
                # Rename Block
                block_index_str = str(block_index_from_data)
                
                # If there are merged IDs (compact folders), we might need to handle the path
                if merged_ids and " / " in new_text:
                    parts = new_text.split(" / ")
                    actual_name = parts[-1].strip()
                    # We only rename the block itself here for simplicity.
                    # Renaming merged folders via one text edit is complex.
                    self.mw.block_names[block_index_str] = actual_name
                else:
                    self.mw.block_names[block_index_str] = new_text
                
                self.mw.settings_manager.save_block_names()
                log_debug(f"Block {block_index_from_data} renamed to '{new_text}'")
            elif folder_id:
                # Rename Folder
                # If merged, we only rename the deepest one for simplicity
                folder = self.mw.project_manager.find_virtual_folder(folder_id)
                if folder:
                    if " / " in new_text:
                        parts = new_text.split(" / ")
                        folder.name = parts[-1].strip()
                    else:
                        folder.name = new_text
                    self.mw.project_manager.save()
                    log_debug(f"Folder {folder_id} renamed to '{folder.name}'")
            
            # Repopulate to fix any visual issues (like adding issue counts back if they were part of the name)
            self.ui_updater.populate_blocks()
        finally:
            self.mw.is_programmatically_changing_text = False

    def _data_string_has_any_problem(self, block_idx: int, string_idx: int) -> bool:
        if not self.mw.current_game_rules:
            return False

        data_string_text, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        if data_string_text is None:
            return False
            
        num_sublines = str(data_string_text).count('\n') + 1
        
        detection_config = getattr(self.mw, 'detection_enabled', {})
        
        for i in range(num_sublines):
            key = (block_idx, string_idx, i)
            if key in self.mw.problems_per_subline:
                problems = self.mw.problems_per_subline[key]
                if any(detection_config.get(p_id, True) for p_id in problems):
                    return True
                    
        return False

    def navigate_to_problem_string(self, direction_down: bool):
        if self.mw.current_block_idx == -1 or not self.mw.data or \
           not (0 <= self.mw.current_block_idx < len(self.mw.data)):
            return

        current_block_data = self.mw.data[self.mw.current_block_idx]
        if not isinstance(current_block_data, list) or not current_block_data:
            return

        num_strings_in_block = len(current_block_data)
        start_scan_idx = self.mw.current_string_idx
        log_debug(f"[NAV] Start navigation. Direction down: {direction_down}, current_string_idx: {start_scan_idx}")
        
        current_check_idx = -1
        if start_scan_idx == -1: 
            current_check_idx = 0 if direction_down else num_strings_in_block - 1
        else: 
             current_check_idx = (start_scan_idx + 1) if direction_down else (start_scan_idx - 1)

        original_programmatic_state = self.mw.is_programmatically_changing_text
        self.mw.is_programmatically_changing_text = True

        found_target_s_idx = -1

        if direction_down:
            for s_idx in range(current_check_idx, num_strings_in_block):
                if self._data_string_has_any_problem(self.mw.current_block_idx, s_idx):
                    found_target_s_idx = s_idx
                    break
            if found_target_s_idx == -1: 
                for s_idx in range(0, current_check_idx if start_scan_idx != -1 else num_strings_in_block): 
                    if self._data_string_has_any_problem(self.mw.current_block_idx, s_idx):
                        found_target_s_idx = s_idx
                        break
        else: 
            for s_idx in range(current_check_idx, -1, -1):
                if self._data_string_has_any_problem(self.mw.current_block_idx, s_idx):
                    found_target_s_idx = s_idx
                    break
            if found_target_s_idx == -1: 
                for s_idx in range(num_strings_in_block - 1, current_check_idx if start_scan_idx != -1 else -1, -1): 
                    if self._data_string_has_any_problem(self.mw.current_block_idx, s_idx):
                        found_target_s_idx = s_idx
                        break
        
        if found_target_s_idx != -1:
            log_debug(f"[NAV] Found target string at index: {found_target_s_idx}")
            self.string_selected_from_preview(found_target_s_idx)
        else:
            log_debug("[NAV] No problem string found in current search.")
            if start_scan_idx != -1 and self._data_string_has_any_problem(self.mw.current_block_idx, start_scan_idx):
                 self.string_selected_from_preview(start_scan_idx)

            self.mw.is_programmatically_changing_text = original_programmatic_state

    def handle_preview_selection_changed(self):
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit or not preview_edit.hasFocus() or self.mw.is_programmatically_changing_text:
            return
            
        cursor = preview_edit.textCursor()
        if not cursor.hasSelection():
            if self.mw.current_string_idx != -1:
                if hasattr(preview_edit, 'set_selected_lines'):
                    preview_edit.set_selected_lines([self.mw.current_string_idx])
            return

        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()
        
        start_block = self.mw.preview_text_edit.document().findBlock(start_pos)
        end_block = self.mw.preview_text_edit.document().findBlock(end_pos)
        
        start_line = start_block.blockNumber()
        end_line = end_block.blockNumber()
        
        if end_pos > start_pos and end_pos == end_block.position() and start_block.blockNumber() != end_block.blockNumber():
            end_line -= 1
            
        if end_line < start_line:
            end_line = start_line

        selected_lines = list(range(start_line, end_line + 1))
        
        if preview_edit and hasattr(preview_edit, 'set_selected_lines'):
            preview_edit.set_selected_lines(selected_lines)

    def navigate_between_blocks(self, direction_down: bool):
        if not hasattr(self.mw, 'block_list_widget'): return
        
        current_item = self.mw.block_list_widget.currentItem()
        if not current_item:
            # Select first block if nothing is selected
            iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
            while iterator.value():
                item = iterator.value()
                if item.data(0, Qt.UserRole) is not None:
                    self.mw.block_list_widget.setCurrentItem(item)
                    return
                iterator += 1
            return

        # Find all items that are blocks (have block_idx data)
        block_items = []
        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) is not None:
                block_items.append(item)
            iterator += 1
        
        if not block_items: return
        
        try:
            current_idx = block_items.index(current_item)
        except ValueError:
            # If current item isn't a block (maybe a folder), find nearest block
            if direction_down:
                self.mw.block_list_widget.setCurrentItem(block_items[0])
            else:
                self.mw.block_list_widget.setCurrentItem(block_items[-1])
            return

        next_idx = current_idx + (1 if direction_down else -1)
        if 0 <= next_idx < len(block_items):
            self.mw.block_list_widget.setCurrentItem(block_items[next_idx])

    def navigate_between_folders(self, direction_down: bool):
        if not hasattr(self.mw, 'block_list_widget'): return
        
        current_item = self.mw.block_list_widget.currentItem()
        
        # Find all items that are folders (no block_idx data)
        folder_items = []
        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) is None:
                folder_items.append(item)
            iterator += 1
        
        if not folder_items: return
        
        # Determine starting index
        current_idx = -1
        if current_item in folder_items:
            current_idx = folder_items.index(current_item)
        else:
            # If a block is selected, find its parent or just use current list order
            parent = current_item.parent() if current_item else None
            if parent and parent in folder_items:
                current_idx = folder_items.index(parent)

        if current_idx == -1 and not direction_down:
            current_idx = len(folder_items)

        next_idx = current_idx + (1 if direction_down else -1)
        if 0 <= next_idx < len(folder_items):
            self.mw.block_list_widget.setCurrentItem(folder_items[next_idx])
            folder_items[next_idx].setExpanded(True)