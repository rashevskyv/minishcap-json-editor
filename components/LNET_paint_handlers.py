from PyQt5.QtGui import QPainter, QColor, QPen, QFontMetrics, QFont, QPaintEvent
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtWidgets import QMainWindow
from utils.utils import log_debug, calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor
from components.LNET_constants import SHORT_LINE_COLOR, WIDTH_EXCEEDED_LINE_COLOR

class LNETPaintHandlers:
    def __init__(self, editor):
        self.editor = editor

    def paintEvent(self, event: QPaintEvent):
        self.editor.super_paintEvent(event)
        if not self.editor.isReadOnly():
            painter = QPainter(self.editor.viewport())
            char_width = self.editor.fontMetrics().horizontalAdvance('0')
            
            x_pos = int(self.editor.document().documentMargin() + (self.editor.character_limit_line_position * char_width))
            x_pos -= self.editor.horizontalScrollBar().value()
            
            pen = QPen(self.editor.character_limit_line_color, self.editor.character_limit_line_width)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.drawLine(x_pos, 0, x_pos, self.editor.viewport().height())

    def super_paintEvent(self, event: QPaintEvent):
         super(type(self.editor), self.editor).paintEvent(event)


    def lineNumberAreaPaintEvent(self, event, painter_device):
        painter = QPainter(painter_device)

        default_bg_color_for_area = self.editor.palette().base().color()
        if self.editor.isReadOnly():
             default_bg_color_for_area = self.editor.palette().window().color().lighter(105)
        painter.fillRect(event.rect(), default_bg_color_for_area)

        main_window_ref = self.editor.window()
        active_data_line_idx = -1 # This is the index of the currently selected Data String
        current_block_idx_data = -1
        if isinstance(main_window_ref, QMainWindow):
            active_data_line_idx = main_window_ref.current_string_idx
            current_block_idx_data = main_window_ref.current_block_idx

        odd_bg_color_const = self.editor.lineNumberArea.odd_line_background
        even_bg_color_const = default_bg_color_for_area
        
        current_q_block = self.editor.firstVisibleBlock()
        current_q_block_number = current_q_block.blockNumber() # This is the index of the QTextBlock in the editor
        top = int(self.editor.blockBoundingGeometry(current_q_block).translated(self.editor.contentOffset()).top())
        bottom = top + int(self.editor.blockBoundingRect(current_q_block).height())

        total_area_width = self.editor.lineNumberAreaWidth()
        extra_part_width = 0
        if self.editor.objectName() == "original_text_edit" or self.editor.objectName() == "edited_text_edit":
            extra_part_width = self.editor.pixel_width_display_area_width
        elif self.editor.objectName() == "preview_text_edit":
            extra_part_width = self.editor.preview_indicator_area_width

        number_part_width = total_area_width - extra_part_width

        current_font_for_numbers = self.editor.font()
        painter.setFont(current_font_for_numbers)
        
        sentence_end_chars = ('.', '!', '?') # For checking short lines in editor

        while current_q_block.isValid() and top <= event.rect().bottom():
            if current_q_block.isVisible() and bottom >= event.rect().top():
                line_height = int(self.editor.blockBoundingRect(current_q_block).height())
                
                display_number_for_line_area = str(current_q_block_number + 1)
                line_num_rect = QRect(0, top, number_part_width - 3, line_height)

                current_bg_for_number_part = even_bg_color_const
                if (current_q_block_number + 1) % 2 != 0:
                    current_bg_for_number_part = odd_bg_color_const
                
                number_text_color = QColor(Qt.black)

                painter.fillRect(line_num_rect.adjusted(0, 0, 3, 0), current_bg_for_number_part)
                painter.setPen(number_text_color)
                painter.drawText(line_num_rect, Qt.AlignRight | Qt.AlignVCenter, display_number_for_line_area)

                if extra_part_width > 0:
                    extra_info_rect = QRect(number_part_width, top, extra_part_width -3 , line_height)
                    bg_for_extra_part = current_bg_for_number_part 

                    if self.editor.objectName() == "original_text_edit" or self.editor.objectName() == "edited_text_edit":
                        q_block_text_raw_dots = current_q_block.text()
                        q_block_text_spaces = convert_dots_to_spaces_from_editor(q_block_text_raw_dots)
                        text_for_width_calc = remove_all_tags(q_block_text_spaces)
                        pixel_width = calculate_string_width(text_for_width_calc, self.editor.font_map)
                        width_str = str(pixel_width)
                        text_color_for_extra_part = QColor(Qt.black)
                        
                        # Check if this specific QTextBlock is short
                        is_this_qblock_short = False
                        if isinstance(main_window_ref, QMainWindow) and \
                           current_block_idx_data != -1 and active_data_line_idx != -1 and \
                           active_data_line_idx in main_window_ref.short_lines_per_block.get(str(current_block_idx_data), set()):
                            
                            active_data_string_text, _ = main_window_ref.data_processor.get_current_string_text(current_block_idx_data, active_data_line_idx)
                            sub_lines_of_active_data_string = str(active_data_string_text).split('\n')
                            
                            if current_q_block_number < len(sub_lines_of_active_data_string) -1: # Must not be the last sub_line
                                current_sub_line_from_data = sub_lines_of_active_data_string[current_q_block_number]
                                current_sub_line_clean_stripped = remove_all_tags(current_sub_line_from_data).strip()

                                if current_sub_line_clean_stripped and not current_sub_line_clean_stripped.endswith(sentence_end_chars):
                                    next_sub_line_from_data = sub_lines_of_active_data_string[current_q_block_number + 1]
                                    next_sub_line_clean_stripped = remove_all_tags(next_sub_line_from_data).strip()
                                    
                                    if next_sub_line_clean_stripped:
                                        first_word_next = next_sub_line_clean_stripped.split(maxsplit=1)[0] if next_sub_line_clean_stripped else ""
                                        if first_word_next:
                                            first_word_next_width = calculate_string_width(first_word_next, main_window_ref.font_map)
                                            space_width = calculate_string_width(" ", main_window_ref.font_map)
                                            # Width of the current QTextBlock (which is text_for_width_calc's width)
                                            current_qblock_pixel_width = pixel_width 
                                            remaining_width_for_qblock = main_window_ref.GAME_DIALOG_MAX_WIDTH_PIXELS - current_qblock_pixel_width
                                            if remaining_width_for_qblock >= (first_word_next_width + space_width):
                                                is_this_qblock_short = True
                        
                        if is_this_qblock_short:
                             bg_for_extra_part = SHORT_LINE_COLOR
                        elif pixel_width > self.editor.LINE_WIDTH_WARNING_THRESHOLD_PIXELS:
                             bg_for_extra_part = self.editor.lineNumberArea.width_indicator_exceeded_color
                        
                        painter.fillRect(extra_info_rect.adjusted(0,0,3,0), bg_for_extra_part)
                        painter.setPen(text_color_for_extra_part)
                        painter.drawText(extra_info_rect, Qt.AlignRight | Qt.AlignVCenter, width_str)
                        

                    elif self.editor.objectName() == "preview_text_edit" and isinstance(main_window_ref, QMainWindow) and current_block_idx_data != -1:
                        painter.fillRect(extra_info_rect.adjusted(0,0,3,0), bg_for_extra_part)

                        indicator_x_start = number_part_width + 2
                        block_key_str_for_preview = str(current_block_idx_data)
                        data_line_index_preview = current_q_block_number

                        indicators_to_draw_preview = []
                        if data_line_index_preview in main_window_ref.critical_problem_lines_per_block.get(block_key_str_for_preview, set()):
                            indicators_to_draw_preview.append(self.editor.lineNumberArea.preview_critical_indicator_color)
                        elif data_line_index_preview in main_window_ref.warning_problem_lines_per_block.get(block_key_str_for_preview, set()):
                            indicators_to_draw_preview.append(self.editor.lineNumberArea.preview_warning_indicator_color)

                        if data_line_index_preview in main_window_ref.width_exceeded_lines_per_block.get(block_key_str_for_preview, set()):
                             preview_width_color_temp = WIDTH_EXCEEDED_LINE_COLOR
                             if preview_width_color_temp.alpha() < 100: preview_width_color_temp = preview_width_color_temp.lighter(120) 
                             if len(indicators_to_draw_preview) < 3 and preview_width_color_temp not in indicators_to_draw_preview:
                                indicators_to_draw_preview.append(preview_width_color_temp)
                        
                        if data_line_index_preview in main_window_ref.short_lines_per_block.get(block_key_str_for_preview, set()):
                            preview_short_color_temp = SHORT_LINE_COLOR
                            if preview_short_color_temp.alpha() < 100: preview_short_color_temp = preview_short_color_temp.lighter(120)
                            if len(indicators_to_draw_preview) < 3 and preview_short_color_temp not in indicators_to_draw_preview:
                                indicators_to_draw_preview.append(preview_short_color_temp)


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
                painter.setPen(QColor(Qt.black)) 
            current_q_block = current_q_block.next()
            top = bottom
            bottom = top + int(self.editor.blockBoundingRect(current_q_block).height())
            current_q_block_number += 1