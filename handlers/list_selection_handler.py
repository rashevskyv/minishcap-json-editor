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
            log_debug("--> ListSelectionHandler: block_selected - No current item (selection cleared).")
            self.mw.current_block_idx = -1
            self.mw.current_string_idx = -1
            self.ui_updater.populate_strings_for_block(-1)
            log_debug("<-- ListSelectionHandler: block_selected finished (selection cleared).")
            self.mw.is_programmatically_changing_text = False
            return

        block_index = current_item.data(Qt.UserRole)
        block_name = current_item.text()
        log_debug(f"--> ListSelectionHandler: block_selected. Item: '{block_name}', Index: {block_index}")
        
        if self.mw.current_block_idx != block_index:
            self.mw.current_block_idx = block_index
            self.mw.current_string_idx = -1
            
        self.ui_updater.populate_strings_for_block(block_index)
        log_debug("<-- ListSelectionHandler: block_selected finished.")
        self.mw.is_programmatically_changing_text = False


    def string_selected_from_preview(self, line_number: int):
        log_debug(f"--> ListSelectionHandler: string_selected_from_preview. Data Line number: {line_number}")
        preview_edit = getattr(self.mw, 'preview_text_edit', None)

        self.mw.is_programmatically_changing_text = True

        if self.mw.current_block_idx == -1:
            log_debug("No block selected. Cannot select a string.")
            self.mw.current_string_idx = -1
            if preview_edit and hasattr(preview_edit, 'clearPreviewSelectedLineHighlight'):
                 preview_edit.clearPreviewSelectedLineHighlight()
            self.ui_updater.update_text_views()
            self.mw.is_programmatically_changing_text = False
            log_debug("<-- ListSelectionHandler: string_selected_from_preview finished (no block).")
            return

        is_valid_line = False
        if 0 <= self.mw.current_block_idx < len(self.mw.data) and \
           isinstance(self.mw.data[self.mw.current_block_idx], list) and \
           0 <= line_number < len(self.mw.data[self.mw.current_block_idx]):
            is_valid_line = True
        
        previous_string_idx = self.mw.current_string_idx
        
        if not is_valid_line:
            log_debug(f"Invalid line number {line_number} for current block data. Clearing string selection.")
            self.mw.current_string_idx = -1
            if preview_edit and hasattr(preview_edit, 'clearPreviewSelectedLineHighlight'):
                preview_edit.clearPreviewSelectedLineHighlight()
        else:
            self.mw.current_string_idx = line_number
            log_debug(f"Set current_string_idx = {line_number}.")
            
            current_text_for_width_check, _ = self.data_processor.get_current_string_text(self.mw.current_block_idx, line_number)
            width_status_changed = False
            if hasattr(self.mw.editor_operation_handler, '_check_and_update_width_exceeded_status'):
                width_status_changed = self.mw.editor_operation_handler._check_and_update_width_exceeded_status(
                    self.mw.current_block_idx,
                    line_number,
                    str(current_text_for_width_check)
                )
            
            if width_status_changed or previous_string_idx != self.mw.current_string_idx :
                if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
                    self.ui_updater.update_block_item_text_with_problem_count(self.mw.current_block_idx)
            
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)

        self.ui_updater.update_text_views()

        if preview_edit and self.mw.current_string_idx != -1 and \
           0 <= self.mw.current_string_idx < preview_edit.document().blockCount():
            block_to_show = preview_edit.document().findBlockByNumber(self.mw.current_string_idx)
            if block_to_show.isValid():
                cursor = QTextCursor(block_to_show)
                preview_edit.setTextCursor(cursor)
                preview_edit.ensureCursorVisible()
        
        self.mw.is_programmatically_changing_text = False
        log_debug("<-- ListSelectionHandler: string_selected_from_preview finished.")

    def rename_block(self, item):
        log_debug("--> ListSelectionHandler: rename_block triggered.")
        block_index_from_data = item.data(Qt.UserRole);
        if block_index_from_data is None: log_debug("No block index (UserRole) found on item."); return
        block_index_str = str(block_index_from_data)
        current_name = self.mw.block_names.get(block_index_str, f"Block {block_index_from_data}")
        new_name, ok = QInputDialog.getText(self.mw, "Rename Block", f"New name for '{current_name}':", text=current_name)
        if ok and new_name and new_name.strip() and new_name.strip() != current_name:
            actual_new_name = new_name.strip()
            self.mw.block_names[block_index_str] = actual_new_name; item.setText(actual_new_name)
        elif ok: log_debug(f"User entered empty or unchanged name: '{new_name}'. No action taken.")
        else: log_debug("User cancelled rename dialog.")
        log_debug("<-- ListSelectionHandler: rename_block finished.")

    def _data_string_has_any_problem(self, block_idx: int, string_idx: int) -> bool:
        log_debug(f"  Checking problems for string B{block_idx}-S{string_idx}")
        block_key = str(block_idx)
        
        has_crit = string_idx in self.mw.critical_problem_lines_per_block.get(block_key, set())
        if has_crit: log_debug(f"    Found critical problem"); return True
        has_warn = string_idx in self.mw.warning_problem_lines_per_block.get(block_key, set())
        if has_warn: log_debug(f"    Found warning problem"); return True
        has_width = string_idx in self.mw.width_exceeded_lines_per_block.get(block_key, set())
        if has_width: log_debug(f"    Found width exceeded problem"); return True
        has_short = string_idx in self.mw.short_lines_per_block.get(block_key, set())
        if has_short: log_debug(f"    Found short line problem"); return True
        
        data_string_text_for_empty_check, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        has_empty_odd = self.mw.app_action_handler._check_data_string_for_empty_odd_unisingle_subline(str(data_string_text_for_empty_check))
        if has_empty_odd: log_debug(f"    Found empty odd unisingle problem"); return True
        
        data_string_text_for_blue_check, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        if data_string_text_for_blue_check:
            temp_doc_holder = QTextEdit() 
            temp_doc_holder.setPlainText(str(data_string_text_for_blue_check))
            doc = temp_doc_holder.document()
            current_block_in_temp_doc = doc.firstBlock()
            paint_handler_to_use = self._paint_handler_for_blue_rule
            if hasattr(self.mw, 'preview_text_edit') and hasattr(self.mw.preview_text_edit, 'paint_handler'): 
                 paint_handler_to_use = self.mw.preview_text_edit.paint_handler

            blue_rule_found = False
            while current_block_in_temp_doc.isValid():
                next_block_in_temp_doc = current_block_in_temp_doc.next()
                if hasattr(paint_handler_to_use, '_check_new_blue_rule'):
                    if not hasattr(paint_handler_to_use.editor, 'font_map'):
                        paint_handler_to_use.editor.font_map = self.mw.font_map if hasattr(self.mw, 'font_map') else {}
                    if not hasattr(paint_handler_to_use.editor, 'LINE_WIDTH_WARNING_THRESHOLD_PIXELS'):
                         paint_handler_to_use.editor.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS if hasattr(self.mw, 'LINE_WIDTH_WARNING_THRESHOLD_PIXELS') else 208
                    
                    if paint_handler_to_use._check_new_blue_rule(current_block_in_temp_doc, next_block_in_temp_doc):
                        blue_rule_found = True
                        break
                current_block_in_temp_doc = next_block_in_temp_doc
            del temp_doc_holder
            if blue_rule_found: log_debug(f"    Found blue rule problem"); return True
        
        log_debug(f"    No problems found for B{block_idx}-S{string_idx}")
        return False

    def navigate_to_problem_string(self, direction_down: bool):
        log_debug(f"Navigate to problem: direction_down={direction_down}")
        if self.mw.current_block_idx == -1 or not self.mw.data or \
           not (0 <= self.mw.current_block_idx < len(self.mw.data)):
            log_debug("Navigate problem: No block selected or data missing.")
            return

        current_block_data = self.mw.data[self.mw.current_block_idx]
        if not isinstance(current_block_data, list) or not current_block_data:
            log_debug(f"Navigate problem: Block {self.mw.current_block_idx} is empty or not a list.")
            return

        num_strings_in_block = len(current_block_data)
        start_scan_idx = self.mw.current_string_idx
        
        if start_scan_idx == -1: # If no string is selected, determine start based on direction
            start_scan_idx = 0 if direction_down else num_strings_in_block - 1
            current_check_idx = start_scan_idx
        else: # Start from next/prev of current selection
             current_check_idx = (start_scan_idx + 1) if direction_down else (start_scan_idx - 1)

        log_debug(f"  Start scan_idx={start_scan_idx}, current_check_idx={current_check_idx}, num_strings={num_strings_in_block}")

        # Iterate once through the list in the specified direction
        if direction_down:
            for s_idx in range(current_check_idx, num_strings_in_block):
                if self._data_string_has_any_problem(self.mw.current_block_idx, s_idx):
                    log_debug(f"  Found problem (down) at S{s_idx}")
                    self.string_selected_from_preview(s_idx)
                    return
            # If not found till end, try from beginning up to original start_scan_idx (if any was selected)
            # or up to where current_check_idx started if nothing was selected
            limit = start_scan_idx if self.mw.current_string_idx != -1 else current_check_idx
            for s_idx in range(0, limit):
                 if self._data_string_has_any_problem(self.mw.current_block_idx, s_idx):
                    log_debug(f"  Found problem (down, wrapped) at S{s_idx}")
                    self.string_selected_from_preview(s_idx)
                    return
        else: # Direction Up
            for s_idx in range(current_check_idx, -1, -1):
                if self._data_string_has_any_problem(self.mw.current_block_idx, s_idx):
                    log_debug(f"  Found problem (up) at S{s_idx}")
                    self.string_selected_from_preview(s_idx)
                    return
            # If not found till beginning, try from end down to original start_scan_idx
            limit = start_scan_idx if self.mw.current_string_idx != -1 else current_check_idx
            for s_idx in range(num_strings_in_block - 1, limit, -1): 
                if self._data_string_has_any_problem(self.mw.current_block_idx, s_idx):
                    log_debug(f"  Found problem (up, wrapped) at S{s_idx}")
                    self.string_selected_from_preview(s_idx)
                    return
        
        log_debug(f"Navigate problem: No OTHER problematic string found in block {self.mw.current_block_idx} in the given direction.")