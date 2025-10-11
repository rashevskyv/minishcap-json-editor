# --- START OF FILE handlers/list_selection_handler.py ---
from PyQt5.QtWidgets import QInputDialog, QTextEdit 
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTextCursor, QTextBlockFormat, QColor, QTextBlock 
from .base_handler import BaseHandler
from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN
from components.LNET_paint_handlers import LNETPaintHandlers

class ListSelectionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self._restoring_selection = False
        if hasattr(self.mw, 'preview_text_edit') and hasattr(self.mw.preview_text_edit, 'paint_handler'):
            self._paint_handler_for_blue_rule = self.mw.preview_text_edit.paint_handler 
        else:
            class DummyEditor:
                def __init__(self):
                    self.font_map = {} 
                    self.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = 208
                def window(self):
                    return None
            self._paint_handler_for_blue_rule = LNETPaintHandlers(DummyEditor())


    def block_selected(self, current_item, previous_item):
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        
        if previous_item:
            previous_block_idx = previous_item.data(Qt.UserRole)
            if previous_block_idx is not None:
                self.ui_updater.update_block_item_text_with_problem_count(previous_block_idx)

        if not current_item and not self.mw.is_loading_data:
            if not self._restoring_selection and self.mw.current_block_idx != -1:
                self._restoring_selection = True
                QTimer.singleShot(0, self._restore_block_selection)
            return

        self.mw.is_programmatically_changing_text = True

        if not current_item:
            self.mw.current_block_idx = -1
            self.mw.current_string_idx = -1
            self.ui_updater.populate_strings_for_block(-1)
            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_string_settings_panel()
            self.mw.is_programmatically_changing_text = False
            return

        block_index = current_item.data(Qt.UserRole)
        
        if self.mw.current_block_idx != block_index:
            self.mw.current_block_idx = block_index
            self.mw.current_string_idx = -1
            
        self.ui_updater.populate_strings_for_block(block_index)
        if hasattr(self.mw, 'string_settings_updater'):
            self.mw.string_settings_updater.update_font_combobox()
            self.mw.string_settings_updater.update_string_settings_panel()
        self.mw.is_programmatically_changing_text = False

    def _restore_block_selection(self):
        if self.mw.current_block_idx != -1:
            self.mw.block_list_widget.setCurrentRow(self.mw.current_block_idx)
        self._restoring_selection = False


    def string_selected_from_preview(self, line_number: int):
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
            if previous_string_idx != self.mw.current_string_idx and previous_string_idx != -1:
                self.ui_updater.update_block_item_text_with_problem_count(self.mw.current_block_idx)
            
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 

        self.ui_updater.update_text_views()
        if hasattr(self.mw, 'string_settings_updater'):
            self.mw.string_settings_updater.update_string_settings_panel()

        if preview_edit and self.mw.current_string_idx != -1 and \
           0 <= self.mw.current_string_idx < preview_edit.document().blockCount():
            if hasattr(preview_edit, 'highlightManager'): 
                preview_edit.highlightManager.setPreviewSelectedLineHighlight([self.mw.current_string_idx])
            
            block_to_show = preview_edit.document().findBlockByNumber(self.mw.current_string_idx)
            if block_to_show.isValid():
                cursor = QTextCursor(block_to_show)
                preview_edit.setTextCursor(cursor)
                preview_edit.ensureCursorVisible()
        elif preview_edit and hasattr(preview_edit, 'highlightManager'): 
            preview_edit.highlightManager.clearPreviewSelectedLineHighlight()
        
        self.mw.is_programmatically_changing_text = original_programmatic_state


    def rename_block(self, item):
        block_index_from_data = item.data(Qt.UserRole);
        if block_index_from_data is None: return
        block_index_str = str(block_index_from_data)
        current_name = self.mw.block_names.get(block_index_str, f"Block {block_index_from_data}")
        new_name, ok = QInputDialog.getText(self.mw, "Rename Block", f"New name for '{current_name}':", text=current_name)
        if ok and new_name and new_name.strip() and new_name.strip() != current_name:
            actual_new_name = new_name.strip()
            self.mw.block_names[block_index_str] = actual_new_name
            self.ui_updater.populate_blocks()
            self.mw.settings_manager.save_block_names()


    def _data_string_has_any_problem(self, block_idx: int, string_idx: int) -> bool:
        if not self.mw.current_game_rules:
            return False
            
        data_string_text, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        if data_string_text is None:
            return False
        
        detection_config = getattr(self.mw, 'detection_enabled', {})
        analyzer = self.mw.current_game_rules.problem_analyzer
        found_problems = set()
        
        font_map_for_string = self.mw.helper.get_font_map_for_string(block_idx, string_idx)

        if hasattr(analyzer, 'analyze_data_string'):
            problems_per_subline = analyzer.analyze_data_string(
                data_string_text, font_map_for_string, self.mw.line_width_warning_threshold_pixels
            )
            for problem_set in problems_per_subline:
                found_problems.update(problem_set)
        else:
            sublines = str(data_string_text).split('\n')
            for i, subline in enumerate(sublines):
                next_subline = sublines[i+1] if i + 1 < len(sublines) else None
                problems = analyzer.analyze_subline(
                    text=subline,
                    next_text=next_subline,
                    subline_number_in_data_string=i,
                    qtextblock_number_in_editor=i,
                    is_last_subline_in_data_string=(i == len(sublines) - 1),
                    editor_font_map=font_map_for_string,
                    editor_line_width_threshold=self.mw.line_width_warning_threshold_pixels,
                    full_data_string_text_for_logical_check=data_string_text
                )
                found_problems.update(problems)
        
        filtered_problems = {p_id for p_id in found_problems if detection_config.get(p_id, True)}
        has_problems = bool(filtered_problems)
        
        return has_problems

    def navigate_to_problem_string(self, direction_down: bool):
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
            self.string_selected_from_preview(found_target_s_idx)
        else:
            if start_scan_idx != -1 and self._data_string_has_any_problem(self.mw.current_block_idx, start_scan_idx):
                 self.string_selected_from_preview(start_scan_idx)

            self.mw.is_programmatically_changing_text = original_programmatic_state

    def handle_preview_selection_changed(self):
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit or not preview_edit.hasFocus():
            return
            
        cursor = preview_edit.textCursor()
        if not cursor.hasSelection():
            if self.mw.current_string_idx != -1:
                if hasattr(preview_edit, 'highlightManager'):
                    preview_edit.highlightManager.setPreviewSelectedLineHighlight([self.mw.current_string_idx])
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
        
        if hasattr(preview_edit, 'highlightManager'):
            preview_edit.highlightManager.setPreviewSelectedLineHighlight(selected_lines)