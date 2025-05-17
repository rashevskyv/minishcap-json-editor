from PyQt5.QtWidgets import QInputDialog, QTextEdit 
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QTextBlockFormat, QColor, QTextBlock 
from .base_handler import BaseHandler
from utils.utils import log_debug, calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN
from components.LNET_paint_handlers import LNETPaintHandlers 

class ListSelectionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        if hasattr(self.mw, 'preview_text_edit') and hasattr(self.mw.preview_text_edit, 'paint_handler'):
            self._paint_handler_for_blue_rule = self.mw.preview_text_edit.paint_handler 
        else:
            class DummyEditor:
                def __init__(self):
                    self.font_map = {} 
                    self.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = 208 
            self._paint_handler_for_blue_rule = LNETPaintHandlers(DummyEditor())


    def block_selected(self, current_item, previous_item):
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        
        self.mw.is_programmatically_changing_text = True

        if not current_item:
            # log_debug("--> ListSelectionHandler: block_selected - No current item (selection cleared).") # Reduced logging
            self.mw.current_block_idx = -1
            self.mw.current_string_idx = -1
            self.ui_updater.populate_strings_for_block(-1)
            # log_debug("<-- ListSelectionHandler: block_selected finished (selection cleared).") # Reduced logging
            self.mw.is_programmatically_changing_text = False
            return

        block_index = current_item.data(Qt.UserRole)
        # block_name = current_item.text() # Reduced logging
        # log_debug(f"--> ListSelectionHandler: block_selected. Item: '{block_name}', Index: {block_index}") # Reduced logging
        
        if self.mw.current_block_idx != block_index:
            self.mw.current_block_idx = block_index
            self.mw.current_string_idx = -1
            
        self.ui_updater.populate_strings_for_block(block_index)
        # log_debug("<-- ListSelectionHandler: block_selected finished.") # Reduced logging
        self.mw.is_programmatically_changing_text = False


    def string_selected_from_preview(self, line_number: int):
        log_debug(f"ListSelectionHandler: string_selected_from_preview. Data Line number: {line_number}")
        preview_edit = getattr(self.mw, 'preview_text_edit', None)

        original_programmatic_state = self.mw.is_programmatically_changing_text
        self.mw.is_programmatically_changing_text = True

        if self.mw.current_block_idx == -1:
            self.mw.current_string_idx = -1
            if preview_edit and hasattr(preview_edit, 'highlightManager'):
                 preview_edit.highlightManager.clearPreviewSelectedLineHighlight()
            self.ui_updater.update_text_views()
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
            if previous_string_idx != self.mw.current_string_idx :
                if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
                    self.ui_updater.update_block_item_text_with_problem_count(self.mw.current_block_idx)
            
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 

        self.ui_updater.update_text_views() 

        if preview_edit and self.mw.current_string_idx != -1 and \
           0 <= self.mw.current_string_idx < preview_edit.document().blockCount():
            if hasattr(preview_edit, 'highlightManager'): 
                preview_edit.highlightManager.setPreviewSelectedLineHighlight(self.mw.current_string_idx)
            
            block_to_show = preview_edit.document().findBlockByNumber(self.mw.current_string_idx)
            if block_to_show.isValid():
                cursor = QTextCursor(block_to_show)
                preview_edit.setTextCursor(cursor)
                preview_edit.ensureCursorVisible()
        elif preview_edit and hasattr(preview_edit, 'highlightManager'): 
            preview_edit.highlightManager.clearPreviewSelectedLineHighlight()
        
        self.mw.is_programmatically_changing_text = original_programmatic_state
        log_debug(f"ListSelectionHandler: string_selected_from_preview finished. current_string_idx: {self.mw.current_string_idx}")


    def rename_block(self, item):
        # log_debug("--> ListSelectionHandler: rename_block triggered.") # Reduced logging
        block_index_from_data = item.data(Qt.UserRole);
        if block_index_from_data is None: return
        block_index_str = str(block_index_from_data)
        current_name = self.mw.block_names.get(block_index_str, f"Block {block_index_from_data}")
        new_name, ok = QInputDialog.getText(self.mw, "Rename Block", f"New name for '{current_name}':", text=current_name)
        if ok and new_name and new_name.strip() and new_name.strip() != current_name:
            actual_new_name = new_name.strip()
            self.mw.block_names[block_index_str] = actual_new_name; item.setText(actual_new_name)
        # log_debug("<-- ListSelectionHandler: rename_block finished.") # Reduced logging

    def _data_string_has_any_problem(self, block_idx: int, string_idx: int) -> bool:
        # log_debug(f"  Checking problems for string B{block_idx}-S{string_idx}") # Reduced logging
        
        data_string_text, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        if data_string_text is None:
            return False
            
        logical_sublines = str(data_string_text).split('\n')
        for subline_local_idx in range(len(logical_sublines)):
            problem_key = (block_idx, string_idx, subline_local_idx)
            if self.mw.problems_per_subline.get(problem_key):
                # log_debug(f"    Found problems in subline {subline_local_idx} for B{block_idx}-S{string_idx}: {self.mw.problems_per_subline.get(problem_key)}") # Reduced logging
                return True
        return False

    def navigate_to_problem_string(self, direction_down: bool):
        log_debug(f"ListSelectionHandler: navigate_to_problem_string. Direction down: {direction_down}")
        if self.mw.current_block_idx == -1 or not self.mw.data or \
           not (0 <= self.mw.current_block_idx < len(self.mw.data)):
            return

        current_block_data = self.mw.data[self.mw.current_block_idx]
        if not isinstance(current_block_data, list) or not current_block_data:
            return

        num_strings_in_block = len(current_block_data)
        start_scan_idx = self.mw.current_string_idx
        
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
            if found_target_s_idx == -1: # Wrap around
                for s_idx in range(0, current_check_idx if start_scan_idx != -1 else num_strings_in_block): 
                    if self._data_string_has_any_problem(self.mw.current_block_idx, s_idx):
                        found_target_s_idx = s_idx
                        break
        else: # Direction Up
            for s_idx in range(current_check_idx, -1, -1):
                if self._data_string_has_any_problem(self.mw.current_block_idx, s_idx):
                    found_target_s_idx = s_idx
                    break
            if found_target_s_idx == -1: # Wrap around
                for s_idx in range(num_strings_in_block - 1, current_check_idx if start_scan_idx != -1 else -1, -1): 
                    if self._data_string_has_any_problem(self.mw.current_block_idx, s_idx):
                        found_target_s_idx = s_idx
                        break
        
        if found_target_s_idx != -1:
            log_debug(f"  Found problem. Navigating to S{found_target_s_idx}")
            self.string_selected_from_preview(found_target_s_idx)
        else:
            log_debug(f"  No OTHER problematic string found in block {self.mw.current_block_idx} in the given direction.")
            # If no other problem, but current is a problem, ensure it's re-selected/re-highlighted
            if start_scan_idx != -1 and self._data_string_has_any_problem(self.mw.current_block_idx, start_scan_idx):
                 self.string_selected_from_preview(start_scan_idx)


        self.mw.is_programmatically_changing_text = original_programmatic_state