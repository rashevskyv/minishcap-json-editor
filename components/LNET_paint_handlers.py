from PyQt5.QtGui import QPainter, QColor, QPen, QFontMetrics, QFont, QPaintEvent
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtWidgets import QMainWindow
from utils.utils import log_debug, calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor

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
        active_data_line_idx = -1
        current_block_idx_data = -1
        if isinstance(main_window_ref, QMainWindow):
            active_data_line_idx = main_window_ref.current_string_idx
            current_block_idx_data = main_window_ref.current_block_idx

        odd_bg_color_const = self.editor.lineNumberArea.odd_line_background
        even_bg_color_const = default_bg_color_for_area
        width_exceeded_bg_color_const = self.editor.lineNumberArea.width_indicator_exceeded_color

        current_q_block = self.editor.firstVisibleBlock()
        current_q_block_number = current_q_block.blockNumber()
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

        while current_q_block.isValid() and top <= event.rect().bottom():
            if current_q_block.isVisible() and bottom >= event.rect().top():
                line_height = int(self.editor.blockBoundingRect(current_q_block).height())

                data_line_index_for_this_q_block = current_q_block_number
                if self.editor.objectName() in ["original_text_edit", "edited_text_edit"]:
                    data_line_index_for_this_q_block = active_data_line_idx if active_data_line_idx != -1 else -1

                display_number_for_line_area = str(current_q_block_number + 1)
                line_num_rect = QRect(0, top, number_part_width - 3, line_height)

                current_bg_for_number_part = even_bg_color_const
                if (current_q_block_number + 1) % 2 != 0:
                    current_bg_for_number_part = odd_bg_color_const

                painter.fillRect(line_num_rect.adjusted(0, 0, 3, 0), current_bg_for_number_part)
                painter.setPen(QColor(Qt.black))
                painter.drawText(line_num_rect, Qt.AlignRight | Qt.AlignVCenter, display_number_for_line_area)

                if extra_part_width > 0:
                    extra_info_rect = QRect(number_part_width, top, extra_part_width -3 , line_height)
                    bg_for_extra_part = current_bg_for_number_part

                    if self.editor.objectName() == "original_text_edit" or self.editor.objectName() == "edited_text_edit":
                        q_block_text_raw = current_q_block.text()
                        text_for_width_calc = convert_dots_to_spaces_from_editor(q_block_text_raw)
                        text_for_width_calc = remove_all_tags(text_for_width_calc)
                        pixel_width = calculate_string_width(text_for_width_calc, self.editor.font_map)
                        width_str = str(pixel_width)
                        text_color_for_extra_part = QColor(Qt.black)

                        if pixel_width > self.editor.LINE_WIDTH_WARNING_THRESHOLD_PIXELS:
                            bg_for_extra_part = width_exceeded_bg_color_const

                        painter.fillRect(extra_info_rect.adjusted(0,0,3,0), bg_for_extra_part)
                        painter.setPen(text_color_for_extra_part)
                        painter.drawText(extra_info_rect, Qt.AlignRight | Qt.AlignVCenter, width_str)

                    elif self.editor.objectName() == "preview_text_edit" and isinstance(main_window_ref, QMainWindow) and current_block_idx_data != -1:
                        painter.fillRect(extra_info_rect.adjusted(0,0,3,0), bg_for_extra_part)

                        indicator_x_start = number_part_width + 2
                        block_key_str_for_preview = str(current_block_idx_data)

                        indicators_to_draw_preview = []
                        if data_line_index_for_this_q_block in main_window_ref.critical_problem_lines_per_block.get(block_key_str_for_preview, set()):
                            indicators_to_draw_preview.append(self.editor.lineNumberArea.preview_critical_indicator_color)
                        elif data_line_index_for_this_q_block in main_window_ref.warning_problem_lines_per_block.get(block_key_str_for_preview, set()):
                            indicators_to_draw_preview.append(self.editor.lineNumberArea.preview_warning_indicator_color)

                        if data_line_index_for_this_q_block in main_window_ref.width_exceeded_lines_per_block.get(block_key_str_for_preview, set()):
                            if not indicators_to_draw_preview or \
                               (len(indicators_to_draw_preview) < 2 and self.editor.lineNumberArea.preview_width_exceeded_indicator_color not in indicators_to_draw_preview):
                                indicators_to_draw_preview.append(self.editor.lineNumberArea.preview_width_exceeded_indicator_color)


                        current_indicator_x_preview = indicator_x_start
                        for color in indicators_to_draw_preview:
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