from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtWidgets import QMainWindow, QTextEdit
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, ALL_TAGS_PATTERN, log_debug # Added log_debug
from components.LNET_constants import (
    SHORT_LINE_COLOR, WIDTH_EXCEEDED_LINE_COLOR, EMPTY_ODD_SUBLINE_COLOR, NEW_BLUE_SUBLINE_COLOR
)

class LNETLineNumberAreaPaintLogic:
    def __init__(self, editor, helpers):
        self.editor = editor
        self.helpers = helpers # Instance of LNETPaintHelpers

    def execute_paint_event(self, event, painter_device):
        painter = QPainter(painter_device)

        default_bg_color_for_area = self.editor.palette().base().color()
        if self.editor.isReadOnly():
             default_bg_color_for_area = self.editor.palette().window().color().lighter(105)

        total_area_width = self.editor.lineNumberAreaWidth()
        extra_part_width = 0
        if self.editor.objectName() == "original_text_edit" or self.editor.objectName() == "edited_text_edit":
            extra_part_width = self.editor.pixel_width_display_area_width
        elif self.editor.objectName() == "preview_text_edit":
            extra_part_width = self.editor.preview_indicator_area_width

        number_part_width = total_area_width - extra_part_width

        current_q_block = self.editor.firstVisibleBlock()
        current_q_block_number = current_q_block.blockNumber() 
        top = int(self.editor.blockBoundingGeometry(current_q_block).translated(self.editor.contentOffset()).top())
        bottom = top + int(self.editor.blockBoundingRect(current_q_block).height())

        current_font_for_numbers = self.editor.font()
        painter.setFont(current_font_for_numbers)
        
        odd_bg_color_const = self.editor.lineNumberArea.odd_line_background
        even_bg_color_const = default_bg_color_for_area
        empty_odd_qtextblock_problem_color = self.editor.empty_odd_subline_color 
        new_blue_subline_color = self.editor.new_blue_subline_color
        width_exceeded_qtextblock_color = self.editor.lineNumberArea.width_indicator_exceeded_color
        short_qtextblock_color = SHORT_LINE_COLOR 

        main_window_ref = self.editor.window()
        current_block_idx_data = -1
        active_data_line_idx = -1 
        
        if isinstance(main_window_ref, QMainWindow):
             current_block_idx_data = main_window_ref.current_block_idx
             active_data_line_idx = main_window_ref.current_string_idx

        while current_q_block.isValid() and top <= event.rect().bottom():
            if current_q_block.isVisible() and bottom >= event.rect().top():
                line_height = int(self.editor.blockBoundingRect(current_q_block).height())
                display_number_for_line_area = str(current_q_block_number + 1)
                
                number_part_rect = QRect(0, top, number_part_width, line_height)
                extra_info_part_rect = QRect(number_part_width, top, extra_part_width, line_height)
                
                bg_color_number_area = even_bg_color_const
                if (current_q_block_number + 1) % 2 != 0: 
                    bg_color_number_area = odd_bg_color_const
                
                bg_color_extra_info_area = bg_color_number_area 

                if self.editor.objectName() != "preview_text_edit": 
                    q_block_text_raw_dots = current_q_block.text()
                    q_block_text_spaces = convert_dots_to_spaces_from_editor(q_block_text_raw_dots)
                    
                    is_odd_qtextblock = (current_q_block_number + 1) % 2 != 0
                    is_single_qtextblock_in_doc = (self.editor.document().blockCount() == 1)
                    
                    has_tags_in_qblock = bool(ALL_TAGS_PATTERN.search(q_block_text_spaces))
                    text_no_tags_for_empty_check = remove_all_tags(q_block_text_spaces)
                    stripped_text_no_tags_for_empty_check = text_no_tags_for_empty_check.strip()
                    is_content_empty_or_zero = not stripped_text_no_tags_for_empty_check or stripped_text_no_tags_for_empty_check == "0"

                    if is_odd_qtextblock and not has_tags_in_qblock and is_content_empty_or_zero and not is_single_qtextblock_in_doc:
                         bg_color_number_area = empty_odd_qtextblock_problem_color 
                         bg_color_extra_info_area = empty_odd_qtextblock_problem_color 
                    
                    if bg_color_extra_info_area != empty_odd_qtextblock_problem_color:
                        next_q_block_for_blue_check = current_q_block.next()
                        if next_q_block_for_blue_check.isValid(): 
                            if self.helpers._check_new_blue_rule(current_q_block, next_q_block_for_blue_check):
                                bg_color_extra_info_area = new_blue_subline_color
                    
                    if self.editor.objectName() != "preview_text_edit": 
                        text_for_width_calc_rstripped_paint_text = remove_all_tags(q_block_text_spaces).rstrip()
                        pixel_width_qtextblock = calculate_string_width(text_for_width_calc_rstripped_paint_text, self.editor.font_map)
                        is_qtextblock_short_for_paint = False
                        if current_q_block.next().isValid(): 
                             is_qtextblock_short_for_paint = self.helpers._is_qtextblock_potentially_short_for_paint(current_q_block, current_q_block.next())

                        if pixel_width_qtextblock > self.editor.LINE_WIDTH_WARNING_THRESHOLD_PIXELS:
                             bg_color_extra_info_area = width_exceeded_qtextblock_color 
                        elif is_qtextblock_short_for_paint:
                             if bg_color_extra_info_area != width_exceeded_qtextblock_color and \
                                bg_color_extra_info_area != new_blue_subline_color and \
                                bg_color_extra_info_area != empty_odd_qtextblock_problem_color:
                                 bg_color_extra_info_area = short_qtextblock_color 

                painter.fillRect(number_part_rect, bg_color_number_area)
                painter.fillRect(extra_info_part_rect, bg_color_extra_info_area)

                number_text_color = QColor(Qt.black) 
                painter.setPen(number_text_color)
                painter.drawText(QRect(0, top, number_part_width - 3, line_height), Qt.AlignRight | Qt.AlignVCenter, display_number_for_line_area)

                if extra_part_width > 0:
                    if self.editor.objectName() == "original_text_edit" or self.editor.objectName() == "edited_text_edit":
                        q_block_text_raw_dots_paint_text = current_q_block.text()
                        q_block_text_spaces_paint_text = convert_dots_to_spaces_from_editor(q_block_text_raw_dots_paint_text)
                        text_for_width_calc_rstripped_paint_text = remove_all_tags(q_block_text_spaces_paint_text).rstrip()
                        pixel_width = calculate_string_width(text_for_width_calc_rstripped_paint_text, self.editor.font_map)
                        width_str_text = str(pixel_width)
                        text_color_for_extra_part = QColor(Qt.black) 
                        painter.setPen(text_color_for_extra_part)
                        painter.drawText(QRect(number_part_width, top, extra_part_width -3 , line_height), Qt.AlignRight | Qt.AlignVCenter, width_str_text)
                        
                    elif self.editor.objectName() == "preview_text_edit" and isinstance(main_window_ref, QMainWindow) and current_block_idx_data != -1:
                        indicator_x_start = number_part_width + 2
                        block_key_str_for_preview = str(current_block_idx_data)
                        data_line_index_preview = current_q_block_number 
                        indicators_to_draw_preview = []
                        
                        is_target_for_log_preview = (current_block_idx_data == 12 and data_line_index_preview == 8)
                        if is_target_for_log_preview:
                            log_debug(f"  PREVIEW PAINT for B{current_block_idx_data}-S{data_line_index_preview} (Data Line Index)")

                        has_crit = hasattr(main_window_ref, 'critical_problem_lines_per_block') and \
                                   data_line_index_preview in main_window_ref.critical_problem_lines_per_block.get(block_key_str_for_preview, set())
                        if has_crit: 
                            indicators_to_draw_preview.append(self.editor.lineNumberArea.preview_critical_indicator_color)
                            if is_target_for_log_preview: log_debug(f"    Preview: Critical problem found.")
                        else:
                            has_warn = hasattr(main_window_ref, 'warning_problem_lines_per_block') and \
                                       data_line_index_preview in main_window_ref.warning_problem_lines_per_block.get(block_key_str_for_preview, set())
                            if has_warn:
                                indicators_to_draw_preview.append(self.editor.lineNumberArea.preview_warning_indicator_color)
                                if is_target_for_log_preview: log_debug(f"    Preview: Warning problem found.")

                        has_empty_odd = hasattr(main_window_ref, 'empty_odd_unisingle_subline_problem_strings') and \
                                        data_line_index_preview in main_window_ref.empty_odd_unisingle_subline_problem_strings.get(block_key_str_for_preview, set())
                        if has_empty_odd:
                            preview_empty_odd_color = EMPTY_ODD_SUBLINE_COLOR 
                            if preview_empty_odd_color.alpha() < 100: preview_empty_odd_color = preview_empty_odd_color.lighter(120)
                            if len(indicators_to_draw_preview) < 3 and preview_empty_odd_color not in indicators_to_draw_preview:
                                indicators_to_draw_preview.append(preview_empty_odd_color)
                            if is_target_for_log_preview: log_debug(f"    Preview: EmptyOdd problem found (indicator color: {preview_empty_odd_color.name()}).")

                        data_string_for_blue_check, _ = main_window_ref.data_processor.get_current_string_text(current_block_idx_data, data_line_index_preview)
                        temp_doc_for_blue_check = QTextEdit() 
                        temp_doc_for_blue_check.setPlainText(str(data_string_for_blue_check))
                        doc_for_blue_check = temp_doc_for_blue_check.document() 
                        
                        data_string_has_blue_rule = False
                        current_block_in_temp_doc = doc_for_blue_check.firstBlock()
                        paint_handler_to_use_for_blue_check = self.editor.paint_handler 
                        
                        while current_block_in_temp_doc.isValid():
                            next_block_in_temp_doc = current_block_in_temp_doc.next()
                            if hasattr(paint_handler_to_use_for_blue_check, '_check_new_blue_rule'):
                                if not hasattr(paint_handler_to_use_for_blue_check.editor, 'font_map'): 
                                     paint_handler_to_use_for_blue_check.editor.font_map = self.mw.font_map if hasattr(self.mw, 'font_map') else {} # type: ignore
                                if not hasattr(paint_handler_to_use_for_blue_check.editor, 'LINE_WIDTH_WARNING_THRESHOLD_PIXELS'):
                                     paint_handler_to_use_for_blue_check.editor.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS if hasattr(self.mw, 'LINE_WIDTH_WARNING_THRESHOLD_PIXELS') else 208 # type: ignore

                                if paint_handler_to_use_for_blue_check._check_new_blue_rule(current_block_in_temp_doc, next_block_in_temp_doc):
                                    data_string_has_blue_rule = True
                                    break
                            current_block_in_temp_doc = next_block_in_temp_doc
                        del temp_doc_for_blue_check 

                        if data_string_has_blue_rule:
                            preview_blue_color_temp = NEW_BLUE_SUBLINE_COLOR
                            if preview_blue_color_temp.alpha() < 100: preview_blue_color_temp = preview_blue_color_temp.lighter(120)
                            if len(indicators_to_draw_preview) < 3 and preview_blue_color_temp not in indicators_to_draw_preview:
                                indicators_to_draw_preview.append(preview_blue_color_temp)
                            if is_target_for_log_preview: log_debug(f"    Preview: Blue rule problem found (indicator color: {preview_blue_color_temp.name()}).")


                        has_width_exceeded = hasattr(main_window_ref, 'width_exceeded_lines_per_block') and \
                                          data_line_index_preview in main_window_ref.width_exceeded_lines_per_block.get(block_key_str_for_preview, set())
                        if has_width_exceeded:
                             preview_width_color_temp = WIDTH_EXCEEDED_LINE_COLOR
                             if preview_width_color_temp.alpha() < 100: preview_width_color_temp = preview_width_color_temp.lighter(120) 
                             if len(indicators_to_draw_preview) < 3 and preview_width_color_temp not in indicators_to_draw_preview:
                                indicators_to_draw_preview.append(preview_width_color_temp)
                             if is_target_for_log_preview: log_debug(f"    Preview: Width exceeded problem found (indicator color: {preview_width_color_temp.name()}).")
                        
                        data_string_is_short_for_preview = False
                        if hasattr(main_window_ref, 'short_lines_per_block') and \
                           hasattr(main_window_ref, 'data_processor') and \
                           data_line_index_preview in main_window_ref.short_lines_per_block.get(block_key_str_for_preview, set()):
                            data_string_for_preview_short, _ = main_window_ref.data_processor.get_current_string_text(current_block_idx_data, data_line_index_preview)
                            if main_window_ref.editor_operation_handler._determine_if_data_string_is_short(data_string_for_preview_short, current_block_idx_data, data_line_index_preview):
                                 data_string_is_short_for_preview = True

                        if data_string_is_short_for_preview:
                            preview_short_color_temp = SHORT_LINE_COLOR
                            if preview_short_color_temp.alpha() < 100: preview_short_color_temp = preview_short_color_temp.lighter(120)
                            if len(indicators_to_draw_preview) < 3 and preview_short_color_temp not in indicators_to_draw_preview:
                                indicators_to_draw_preview.append(preview_short_color_temp)
                            if is_target_for_log_preview: log_debug(f"    Preview: Short line problem found (indicator color: {preview_short_color_temp.name()}).")
                        
                        if is_target_for_log_preview: log_debug(f"    Preview: Final indicators for B{current_block_idx_data}-S{data_line_index_preview}: {[c.name() for c in indicators_to_draw_preview]}")


                        current_indicator_x_preview = indicator_x_start
                        for color_idx, color in enumerate(indicators_to_draw_preview):
                            if current_indicator_x_preview + self.editor.lineNumberArea.preview_indicator_width <= number_part_width + extra_part_width -1:
                                ind_rect = QRect(current_indicator_x_preview,
                                                 top + 2,
                                                 self.editor.lineNumberArea.preview_indicator_width,
                                                 line_height - 4)
                                painter.fillRect(ind_rect, color)
                                current_indicator_x_preview += self.editor.lineNumberArea.preview_indicator_width + self.editor.lineNumberArea.preview_indicator_spacing
                            else: break
                
            current_q_block = current_q_block.next()
            top = bottom
            bottom = top + int(self.editor.blockBoundingRect(current_q_block).height())
            current_q_block_number += 1