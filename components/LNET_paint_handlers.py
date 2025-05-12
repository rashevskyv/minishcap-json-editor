import re
from PyQt5.QtGui import QPainter, QColor, QPen, QFontMetrics, QFont, QPaintEvent, QTextLine, QTextBlock 
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtWidgets import QMainWindow, QTextEdit 
from utils.utils import log_debug, calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, SPACE_DOT_SYMBOL, ALL_TAGS_PATTERN
from components.LNET_constants import (
    SHORT_LINE_COLOR, WIDTH_EXCEEDED_LINE_COLOR, EMPTY_ODD_SUBLINE_COLOR, NEW_BLUE_SUBLINE_COLOR,
    PAIR_SEPARATOR_LINE_COLOR, PAIR_SEPARATOR_LINE_STYLE, PAIR_SEPARATOR_LINE_THICKNESS
)

# Regex for sentence-ending punctuation followed optionally by a double quote, anchored to the end
SENTENCE_END_PUNCTUATION_PATTERN = re.compile(r'([.,!?]["\']?)$')

class LNETPaintHandlers:
    def __init__(self, editor):
        self.editor = editor 

    def _map_no_tag_index_to_raw_text_index(self, raw_qtextline_text: str, line_text_segment_no_tags: str, target_no_tag_index_in_segment: int) -> int:
        if target_no_tag_index_in_segment == 0:
            current_idx = 0
            while current_idx < len(raw_qtextline_text):
                char = raw_qtextline_text[current_idx]
                if char.isspace() or char == SPACE_DOT_SYMBOL: 
                    current_idx += 1
                    continue
                is_tag_char = False
                for tag_match in ALL_TAGS_PATTERN.finditer(raw_qtextline_text[current_idx:]):
                    if tag_match.start() == 0: 
                        tag_content = tag_match.group(0)
                        current_idx += len(tag_content)
                        is_tag_char = True
                        break 
                if is_tag_char:
                    continue
                return current_idx
            return 0

        words_no_tags = list(re.finditer(r'\S+', line_text_segment_no_tags))
        target_word_text_no_tags = ""
        current_word_idx_no_tags = -1 

        for i, word_match_no_tags in enumerate(words_no_tags):
            if word_match_no_tags.start() == target_no_tag_index_in_segment:
                target_word_text_no_tags = word_match_no_tags.group(0)
                current_word_idx_no_tags = i 
                break
        
        if not target_word_text_no_tags : 
            return min(target_no_tag_index_in_segment, len(raw_qtextline_text) -1 if raw_qtextline_text else 0)

        target_word_occurrence_count = 0
        for i in range(current_word_idx_no_tags + 1):
            if words_no_tags[i].group(0) == target_word_text_no_tags:
                target_word_occurrence_count += 1
        
        actual_word_occurrence_in_raw = 0
        for raw_match in re.finditer(r'\S+', raw_qtextline_text):
            raw_word_from_match = raw_match.group(0)
            raw_word_with_spaces = convert_dots_to_spaces_from_editor(raw_word_from_match)
            cleaned_word_for_comparison = remove_all_tags(raw_word_with_spaces)

            if cleaned_word_for_comparison == target_word_text_no_tags:
                actual_word_occurrence_in_raw += 1
                if actual_word_occurrence_in_raw == target_word_occurrence_count:
                    return raw_match.start()
        
        return min(target_no_tag_index_in_segment, len(raw_qtextline_text) -1 if raw_qtextline_text else 0)


    def _check_new_blue_rule(self, current_q_block: QTextBlock, next_q_block: QTextBlock) -> bool:
        if not current_q_block.isValid(): # next_q_block might be invalid, checked later
            return False

        # 1. Check if the current block number is odd (1-based index)
        is_odd_qtextblock = (current_q_block.blockNumber() + 1) % 2 != 0
        if not is_odd_qtextblock:
            return False

        # 2. Get text, convert dots, remove tags, and strip
        current_q_block_text_raw_dots = current_q_block.text()
        current_q_block_text_spaces = convert_dots_to_spaces_from_editor(current_q_block_text_raw_dots)
        current_q_block_text_no_tags = remove_all_tags(current_q_block_text_spaces)
        stripped_qtextblock_text = current_q_block_text_no_tags.strip()

        if not stripped_qtextblock_text:
            return False

        # Check if it starts with a lowercase letter
        starts_lowercase = stripped_qtextblock_text[0].islower()
        if not starts_lowercase:
            return False

        # Check if it ends with sentence-ending punctuation
        ends_punctuation = bool(SENTENCE_END_PUNCTUATION_PATTERN.search(stripped_qtextblock_text))
        if not ends_punctuation:
            return False

        # 3. Check if the next block is valid and not empty
        if not next_q_block.isValid():
            return False # No next block means condition cannot be met

        next_q_block_text_raw_dots = next_q_block.text()
        next_q_block_text_spaces = convert_dots_to_spaces_from_editor(next_q_block_text_raw_dots)
        next_q_block_text_no_tags = remove_all_tags(next_q_block_text_spaces)
        stripped_next_qtextblock_text = next_q_block_text_no_tags.strip()

        is_next_block_not_empty = bool(stripped_next_qtextblock_text)
        
        return is_next_block_not_empty

    # Function to check if a QTextBlock is potentially 'short' for painting the line number area
    def _is_qtextblock_potentially_short_for_paint(self, current_q_block: QTextBlock, next_q_block: QTextBlock) -> bool:
        if not self.editor.font_map: return False # Cannot calculate width without font map
        if not current_q_block.isValid() or not next_q_block.isValid(): return False
        
        sentence_end_tuples = ('.', '!', '?', '."', '!"', '?"') 
        max_width_for_short_check_paint = self.editor.LINE_WIDTH_WARNING_THRESHOLD_PIXELS
        space_width_editor = calculate_string_width(" ", self.editor.font_map)

        current_q_block_text_raw_dots = current_q_block.text()
        current_q_block_text_spaces = convert_dots_to_spaces_from_editor(current_q_block_text_raw_dots)
        current_sub_line_clean_stripped = remove_all_tags(current_q_block_text_spaces).strip()

        if not current_sub_line_clean_stripped: return False
        if current_sub_line_clean_stripped.endswith(sentence_end_tuples): return False

        next_q_block_text_raw_dots = next_q_block.text()
        next_q_block_text_spaces = convert_dots_to_spaces_from_editor(next_q_block_text_raw_dots)
        next_sub_line_clean_stripped_editor = remove_all_tags(next_q_block_text_spaces).strip()

        if not next_sub_line_clean_stripped_editor: return False

        first_word_next_editor = next_sub_line_clean_stripped_editor.split(maxsplit=1)[0] if next_sub_line_clean_stripped_editor else ""
        if not first_word_next_editor: return False

        first_word_next_width_editor = calculate_string_width(first_word_next_editor, self.editor.font_map)
        if first_word_next_width_editor <= 0: return False

        current_qblock_pixel_width_rstripped = calculate_string_width(remove_all_tags(current_q_block_text_spaces).rstrip(), self.editor.font_map)
        remaining_width_for_qblock_editor = max_width_for_short_check_paint - current_qblock_pixel_width_rstripped

        if remaining_width_for_qblock_editor >= (first_word_next_width_editor + space_width_editor):
            return True

        return False


    def paintEvent(self, event: QPaintEvent):
        # Малювання розділювальних ліній ДО основного вмісту
        if self.editor.objectName() != "preview_text_edit":
            painter_lines = QPainter(self.editor.viewport()) # Малюємо на viewport
            pen_lines = QPen(PAIR_SEPARATOR_LINE_COLOR)
            pen_lines.setStyle(PAIR_SEPARATOR_LINE_STYLE)
            pen_lines.setWidth(PAIR_SEPARATOR_LINE_THICKNESS)
            painter_lines.setPen(pen_lines)

            block = self.editor.firstVisibleBlock()
            viewport_offset = self.editor.contentOffset()
            # qtextblock_visual_line_index_overall = 0 # This counter is not needed here

            while block.isValid() and block.layout():
                layout = block.layout()
                block_rect = self.editor.blockBoundingGeometry(block).translated(viewport_offset)

                for i in range(layout.lineCount()):
                    line = layout.lineAt(i)
                    if not line.isValid():
                        continue
                    
                    # Check if this line is the second (even index, 0-based) line within its block layout
                    if (i + 1) % 2 == 0:
                         line_bottom_y_in_viewport = block_rect.top() + line.rect().bottom()
                         
                         # Check if there is a next line within the layout OR if there is a next block
                         has_next_line_in_block = (i < layout.lineCount() - 1)
                         has_next_block = block.next().isValid()

                         if has_next_line_in_block or has_next_block:
                            if line_bottom_y_in_viewport >= -PAIR_SEPARATOR_LINE_THICKNESS and \
                               line_bottom_y_in_viewport <= self.editor.viewport().height() + PAIR_SEPARATOR_LINE_THICKNESS:
                                # Малюємо на всю ширину viewport
                                painter_lines.drawLine(
                                    0, # Від лівого краю viewport
                                    int(line_bottom_y_in_viewport) -1, 
                                    self.editor.viewport().width(), # До правого краю viewport
                                    int(line_bottom_y_in_viewport) -1
                                )
                # if block_rect.bottom() > self.editor.viewport().height():
                #     break 
                block = block.next()
            # painter_lines.end() # Не потрібно, якщо QPainter створюється зі вказанням widget


        # Оригінальне малювання тексту та іншого
        if self.editor.objectName() == "edited_text_edit" and hasattr(self.editor, 'highlightManager'):
            if self.editor.highlightManager:
                self.editor.highlightManager._width_exceed_char_selections = [] 

        self.editor.super_paintEvent(event) 
        
        main_window = self.editor.window()
        if not isinstance(main_window, QMainWindow):
            return
        
        if self.editor.objectName() == "edited_text_edit":
            block = self.editor.firstVisibleBlock()
            while block.isValid() and block.isVisible():
                layout = block.layout()
                if not layout:
                    block = block.next()
                    continue
                
                q_block_text_raw_dots = block.text() 

                for i in range(layout.lineCount()):
                    line: QTextLine = layout.lineAt(i)
                    if not line.isValid():
                        continue

                    raw_line_text_with_tags_and_display_chars = q_block_text_raw_dots[line.textStart() : line.textStart() + line.textLength()]
                    line_text_with_spaces_and_tags = convert_dots_to_spaces_from_editor(raw_line_text_with_tags_and_display_chars)
                    line_text_no_tags_for_width_calc = remove_all_tags(line_text_with_spaces_and_tags).rstrip()

                    if not line_text_no_tags_for_width_calc:
                        continue

                    visual_line_width_game_px = calculate_string_width(line_text_no_tags_for_width_calc, self.editor.font_map)
                    current_threshold_game_px = self.editor.LINE_WIDTH_WARNING_THRESHOLD_PIXELS
                    
                    if visual_line_width_game_px > current_threshold_game_px:
                        words_in_no_tag_segment = []
                        for match in re.finditer(r'\S+', line_text_no_tags_for_width_calc):
                            words_in_no_tag_segment.append({'text': match.group(0), 'start_idx_in_segment': match.start()})
                        
                        target_char_index_in_no_tag_segment = 0
                        if words_in_no_tag_segment:
                            found_target_word = False
                            for word_info in reversed(words_in_no_tag_segment):
                                text_before_word_no_tags = line_text_no_tags_for_width_calc[:word_info['start_idx_in_segment']]
                                width_before_word_game_px = calculate_string_width(text_before_word_no_tags, self.editor.font_map)
                                if width_before_word_game_px <= current_threshold_game_px:
                                    target_char_index_in_no_tag_segment = word_info['start_idx_in_segment']
                                    found_target_word = True
                                    break
                            if not found_target_word:
                                target_char_index_in_no_tag_segment = 0
                        else:
                            pass
                        
                        actual_char_index_in_raw_qtextline = self._map_no_tag_index_to_raw_text_index(
                            raw_line_text_with_tags_and_display_chars,
                            line_text_no_tags_for_width_calc, 
                            target_char_index_in_no_tag_segment
                        )
                        
                        char_index_in_block = line.textStart() + actual_char_index_in_raw_qtextline
                        
                        if hasattr(self.editor, 'highlightManager') and self.editor.highlightManager:
                            highlight_color = QColor("#90EE90") 
                            self.editor.highlightManager.add_width_exceed_char_highlight(block, char_index_in_block, highlight_color)
                        break 
                block = block.next()
            
            if hasattr(self.editor, 'highlightManager') and self.editor.highlightManager:
                self.editor.highlightManager.applyHighlights()


    def super_paintEvent(self, event: QPaintEvent):
         super(type(self.editor), self.editor).paintEvent(event)


    def lineNumberAreaPaintEvent(self, event, painter_device):
        painter = QPainter(painter_device)

        default_bg_color_for_area = self.editor.palette().base().color()
        if self.editor.isReadOnly():
             default_bg_color_for_area = self.editor.palette().window().color().lighter(105)

        # Determine static parts of the area width
        total_area_width = self.editor.lineNumberAreaWidth()
        extra_part_width = 0
        if self.editor.objectName() == "original_text_edit" or self.editor.objectName() == "edited_text_edit":
            extra_part_width = self.editor.pixel_width_display_area_width
        elif self.editor.objectName() == "preview_text_edit":
            extra_part_width = self.editor.preview_indicator_area_width

        number_part_width = total_area_width - extra_part_width

        # Iterate through visible blocks
        current_q_block = self.editor.firstVisibleBlock()
        current_q_block_number = current_q_block.blockNumber() 
        top = int(self.editor.blockBoundingGeometry(current_q_block).translated(self.editor.contentOffset()).top())
        bottom = top + int(self.editor.blockBoundingRect(current_q_block).height())

        # Font for line numbers
        current_font_for_numbers = self.editor.font()
        painter.setFont(current_font_for_numbers)
        
        # Colors for highlighting rules
        odd_bg_color_const = self.editor.lineNumberArea.odd_line_background
        even_bg_color_const = default_bg_color_for_area
        empty_odd_qtextblock_problem_color = self.editor.empty_odd_subline_color
        new_blue_subline_color = self.editor.new_blue_subline_color
        width_exceeded_qtextblock_color = self.editor.lineNumberArea.width_indicator_exceeded_color
        short_qtextblock_color = SHORT_LINE_COLOR 

        # Check needed data from main window for data-string-based highlights (only for edited/original)
        main_window_ref = self.editor.window()
        current_block_idx_data = -1
        active_data_line_idx = -1 
        sentence_end_tuples = ('.', '!', '?', '."', '!"', '?"') 
        max_width_for_short_check_paint = self.editor.LINE_WIDTH_WARNING_THRESHOLD_PIXELS

        if isinstance(main_window_ref, QMainWindow):
             current_block_idx_data = main_window_ref.current_block_idx
             active_data_line_idx = main_window_ref.current_string_idx

        while current_q_block.isValid() and top <= event.rect().bottom():
            if current_q_block.isVisible() and bottom >= event.rect().top():
                line_height = int(self.editor.blockBoundingRect(current_q_block).height())
                display_number_for_line_area = str(current_q_block_number + 1)
                
                number_part_rect = QRect(0, top, number_part_width, line_height)
                extra_info_part_rect = QRect(number_part_width, top, extra_part_width, line_height)
                
                # Determine base background color (odd/even) for Number Area
                bg_color_number_area = even_bg_color_const
                if (current_q_block_number + 1) % 2 != 0: 
                    bg_color_number_area = odd_bg_color_const

                # --- Check for QTextBlock-based problems and apply background color to Number Area ---
                bg_color_extra_info_area = bg_color_number_area # Start with the same background

                if self.editor.objectName() != "preview_text_edit": # This check is only for editors showing QTextBlocks split by \n
                    
                    # 1. Empty odd non-single QTextBlock (Priority 1)
                    q_block_text_raw_dots = current_q_block.text()
                    q_block_text_spaces = convert_dots_to_spaces_from_editor(q_block_text_raw_dots)
                    text_no_tags = remove_all_tags(q_block_text_spaces)
                    stripped_text_no_tags = text_no_tags.strip()
                    is_pixel_width_zero = (calculate_string_width(stripped_text_no_tags, self.editor.font_map) == 0) if self.editor.font_map else (not stripped_text_no_tags)
                    is_odd_qtextblock = (current_q_block_number + 1) % 2 != 0
                    is_single_qtextblock_in_doc = (self.editor.document().blockCount() == 1)

                    if is_pixel_width_zero and is_odd_qtextblock and not is_single_qtextblock_in_doc:
                         bg_color_number_area = empty_odd_qtextblock_problem_color
                         bg_color_extra_info_area = empty_odd_qtextblock_problem_color
                    else:
                        # 2. New Blue Rule: Odd QTextBlock, starts lowercase, ends punctuation, next block non-empty (Priority 2)
                        next_q_block = current_q_block.next()
                        if next_q_block.isValid(): 
                            if self._check_new_blue_rule(current_q_block, next_q_block):
                                bg_color_number_area = new_blue_subline_color
                                bg_color_extra_info_area = new_blue_subline_color

                    # --- Check for Width/Short QTextBlock problems and apply background color to Extra Info Area ---
                    # These checks apply *only* to the Extra Info Area (width/short indicators)
                    if self.editor.objectName() != "preview_text_edit": 
                        q_block_text_raw_dots_paint_text = current_q_block.text()
                        q_block_text_spaces_paint_text = convert_dots_to_spaces_from_editor(q_block_text_raw_dots_paint_text)
                        text_for_width_calc_rstripped_paint_text = remove_all_tags(q_block_text_spaces_paint_text).rstrip()
                        
                        pixel_width_qtextblock = calculate_string_width(text_for_width_calc_rstripped_paint_text, self.editor.font_map)

                        is_qtextblock_short_for_paint = False
                        if current_q_block.next().isValid(): # Check only if there's a next QTextBlock to potentially merge with
                             is_qtextblock_short_for_paint = self._is_qtextblock_potentially_short_for_paint(current_q_block, current_q_block.next())


                        if pixel_width_qtextblock > self.editor.LINE_WIDTH_WARNING_THRESHOLD_PIXELS:
                             bg_color_extra_info_area = width_exceeded_qtextblock_color # Priority 3
                        elif is_qtextblock_short_for_paint:
                             bg_color_extra_info_area = short_qtextblock_color # Priority 4
                        # Otherwise, bg_color_extra_info_area remains the same as bg_color_number_area or a higher priority color applied earlier

                # Fill the backgrounds
                painter.fillRect(number_part_rect, bg_color_number_area)
                painter.fillRect(extra_info_part_rect, bg_color_extra_info_area)


                # --- Draw Line Number Text ---
                number_text_color = QColor(Qt.black) 
                painter.setPen(number_text_color)
                painter.drawText(QRect(0, top, number_part_width - 3, line_height), Qt.AlignRight | Qt.AlignVCenter, display_number_for_line_area)

                # --- Draw Extra Info (Width or Preview Indicators) ---
                if extra_part_width > 0:
                    if self.editor.objectName() == "original_text_edit" or self.editor.objectName() == "edited_text_edit":
                        # Draw Pixel Width Text
                        q_block_text_raw_dots_paint_text = current_q_block.text()
                        q_block_text_spaces_paint_text = convert_dots_to_spaces_from_editor(q_block_text_raw_dots_paint_text)
                        text_for_width_calc_rstripped_paint_text = remove_all_tags(q_block_text_spaces_paint_text).rstrip()
                        
                        pixel_width = calculate_string_width(text_for_width_calc_rstripped_paint_text, self.editor.font_map)

                        width_str_text = str(pixel_width)
                        text_color_for_extra_part = QColor(Qt.black) 
                        
                        # Set pixel width text color based on the background color of the extra info area
                        if bg_color_extra_info_area == width_exceeded_qtextblock_color:
                             text_color_for_extra_part = QColor(Qt.darkRed)
                        elif bg_color_extra_info_area == short_qtextblock_color:
                             text_color_for_extra_part = QColor(Qt.darkGreen)
                        elif bg_color_extra_info_area == empty_odd_qtextblock_problem_color:
                             text_color_for_extra_part = QColor(Qt.darkRed)


                        painter.setPen(text_color_for_extra_part)
                        painter.drawText(QRect(number_part_width, top, extra_part_width -3 , line_height), Qt.AlignRight | Qt.AlignVCenter, width_str_text)
                        
                    elif self.editor.objectName() == "preview_text_edit" and isinstance(main_window_ref, QMainWindow) and current_block_idx_data != -1:
                        # Draw Preview Indicators (these are based on the Data String status, not individual QTextBlock status)
                        indicator_x_start = number_part_width + 2
                        block_key_str_for_preview = str(current_block_idx_data)
                        data_line_index_preview = current_q_block_number 
                        indicators_to_draw_preview = []
                        
                        # Problem Indicators (Critical, Warning, EmptyOdd - based on Data String status)
                        if hasattr(main_window_ref, 'critical_problem_lines_per_block') and \
                           data_line_index_preview in main_window_ref.critical_problem_lines_per_block.get(block_key_str_for_preview, set()):
                            indicators_to_draw_preview.append(self.editor.lineNumberArea.preview_critical_indicator_color)
                        elif hasattr(main_window_ref, 'warning_problem_lines_per_block') and \
                             data_line_index_preview in main_window_ref.warning_problem_lines_per_block.get(block_key_str_for_preview, set()):
                            indicators_to_draw_preview.append(self.editor.lineNumberArea.preview_warning_indicator_color)

                        if hasattr(main_window_ref, 'empty_odd_unisingle_subline_problem_strings') and \
                            data_line_index_preview in main_window_ref.empty_odd_unisingle_subline_problem_strings.get(block_key_str_for_preview, set()):
                            preview_empty_odd_color = EMPTY_ODD_SUBLINE_COLOR
                            if preview_empty_odd_color.alpha() < 100: preview_empty_odd_color = preview_empty_odd_color.lighter(120)
                            if len(indicators_to_draw_preview) < 3 and preview_empty_odd_color not in indicators_to_draw_preview:
                                indicators_to_draw_preview.append(preview_empty_odd_color)

                        # Width Exceeded Indicator (based on Data String status)
                        if hasattr(main_window_ref, 'width_exceeded_lines_per_block') and \
                           data_line_index_preview in main_window_ref.width_exceeded_lines_per_block.get(block_key_str_for_preview, set()):
                             preview_width_color_temp = WIDTH_EXCEEDED_LINE_COLOR
                             if preview_width_color_temp.alpha() < 100: preview_width_color_temp = preview_width_color_temp.lighter(120) 
                             if len(indicators_to_draw_preview) < 3 and preview_width_color_temp not in indicators_to_draw_preview:
                                indicators_to_draw_preview.append(preview_width_color_temp)
                        
                        # Short Line Indicator (based on Data String status)
                        should_draw_short_indicator_for_preview = False
                        if hasattr(main_window_ref, 'short_lines_per_block') and \
                           hasattr(main_window_ref, 'data_processor') and \
                           data_line_index_preview in main_window_ref.short_lines_per_block.get(block_key_str_for_preview, set()):
                            data_string_for_preview, _ = main_window_ref.data_processor.get_current_string_text(current_block_idx_data, data_line_index_preview)
                            # Check if *any* sub-line in this data string is short based on data string logic
                            if main_window_ref.editor_operation_handler._determine_if_data_string_is_short(data_string_for_preview):
                                 should_draw_short_indicator_for_preview = True

                        if should_draw_short_indicator_for_preview:
                            preview_short_color_temp = SHORT_LINE_COLOR
                            if preview_short_color_temp.alpha() < 100: preview_short_color_temp = preview_short_color_temp.lighter(120)
                            if len(indicators_to_draw_preview) < 3 and preview_short_color_temp not in indicators_to_draw_preview:
                                indicators_to_draw_preview.append(preview_short_color_temp)

                        # Draw the indicators
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