import re
from PyQt5.QtGui import QPainter, QColor, QPen, QFontMetrics, QFont, QPaintEvent, QTextLine
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtWidgets import QMainWindow, QTextEdit 
from utils.utils import log_debug, calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, SPACE_DOT_SYMBOL, ALL_TAGS_PATTERN
from components.LNET_constants import SHORT_LINE_COLOR, WIDTH_EXCEEDED_LINE_COLOR

class LNETPaintHandlers:
    def __init__(self, editor):
        self.editor = editor # editor is LineNumberedTextEdit

    def _map_no_tag_index_to_raw_text_index(self, raw_qtextline_text: str, line_text_segment_no_tags: str, target_no_tag_index_in_segment: int) -> int:
        log_debug(f"    _map: Start map. target_no_tag_idx={target_no_tag_index_in_segment}, no_tag_segment='{line_text_segment_no_tags[:30]}...', raw_qtextline_text='{raw_qtextline_text[:30]}...'")

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
                        current_idx += len(tag_match.group(0))
                        is_tag_char = True
                        break 
                if is_tag_char:
                    continue
                log_debug(f"    _map: For target_no_tag_idx 0, found raw_idx {current_idx} (first non-tag/display-space).")
                return current_idx
            log_debug(f"    _map: For target_no_tag_idx 0, raw line seems empty/all tags/spaces. Returning 0.")
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
            log_debug(f"    _map: Could not ID target word in no_tag_segment at no_tag_idx {target_no_tag_index_in_segment}. Fallback to no_tag_idx itself.")
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
                    log_debug(f"    _map: Found '{target_word_text_no_tags}' (occurrence {actual_word_occurrence_in_raw}) in raw at raw_idx {raw_match.start()}. Returning this index.")
                    return raw_match.start()
        
        log_debug(f"    _map: Failed to find {target_word_occurrence_count}-th '{target_word_text_no_tags}' in raw. Fallback.")
        return min(target_no_tag_index_in_segment, len(raw_qtextline_text) -1 if raw_qtextline_text else 0)

    def paintEvent(self, event: QPaintEvent):
        # Clear previous width exceed character highlights AT THE VERY START OF THE PAINT CYCLE FOR THIS EDITOR
        if self.editor.objectName() == "edited_text_edit" and hasattr(self.editor, 'highlightManager'):
            if self.editor.highlightManager:
                # Only clear the list, don't trigger applyHighlights yet
                self.editor.highlightManager._width_exceed_char_selections = [] 
                log_debug(f"LNETPaintHandlers ({self.editor.objectName()}): Cleared _width_exceed_char_selections list at start of paintEvent.")


        self.editor.super_paintEvent(event) # Standard painting happens first
        
        # Now, our custom logic to calculate and add new highlights for this paint cycle
        main_window = self.editor.window()
        if not isinstance(main_window, QMainWindow):
            return

        if self.editor.objectName() == "edited_text_edit":
            # This flag is not strictly needed anymore if applyHighlights is always called at the end
            # new_width_selections_added_this_paint = False 
            
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
                        log_debug(f"PaintEvent Line (Editor: {self.editor.objectName()}): Blk {block.blockNumber()}, QTL {i}, TextForWidth='{line_text_no_tags_for_width_calc}', GameW={visual_line_width_game_px} > Thr={current_threshold_game_px}. Finding char_idx...")
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
                                    log_debug(f"    Target word in no_tag_segment: '{word_info['text']}' starts at no_tag_idx {target_char_index_in_no_tag_segment} because width_before ({width_before_word_game_px}) <= threshold.")
                                    break
                            if not found_target_word:
                                target_char_index_in_no_tag_segment = 0
                                log_debug(f"    No suitable word found, target_char_index_in_no_tag_segment is 0.")
                        else:
                            log_debug(f"    No words in no_tag_segment, target_char_index_in_no_tag_segment is 0.")
                        
                        actual_char_index_in_raw_qtextline = self._map_no_tag_index_to_raw_text_index(
                            raw_line_text_with_tags_and_display_chars,
                            line_text_no_tags_for_width_calc, 
                            target_char_index_in_no_tag_segment
                        )
                        
                        char_index_in_block = line.textStart() + actual_char_index_in_raw_qtextline
                        
                        if hasattr(self.editor, 'highlightManager') and self.editor.highlightManager:
                            highlight_color = QColor("#90EE90") 
                            self.editor.highlightManager.add_width_exceed_char_highlight(block, char_index_in_block, highlight_color)
                            # new_width_selections_added_this_paint = True # Not strictly needed if applyHighlights is always called
                        break 
                block = block.next()
            
            # Always call applyHighlights after processing all visible blocks in this paint event for this editor
            if hasattr(self.editor, 'highlightManager') and self.editor.highlightManager:
                log_debug(f"PaintEvent (Editor: {self.editor.objectName()}): >>> END OF BLOCK LOOP, CALLING applyHighlights.")
                self.editor.highlightManager.applyHighlights()


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
        
        sentence_end_tuples = ('.', '!', '?', '."', '!"', '?"') 
        max_width_for_short_check_paint = main_window_ref.LINE_WIDTH_WARNING_THRESHOLD_PIXELS if isinstance(main_window_ref, QMainWindow) else 210


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
                        text_for_width_calc_rstripped = remove_all_tags(q_block_text_spaces).rstrip()
                        pixel_width = calculate_string_width(text_for_width_calc_rstripped, self.editor.font_map)
                        width_str = str(pixel_width)
                        text_color_for_extra_part = QColor(Qt.black)
                        
                        is_this_qblock_short_for_bg = False
                        if isinstance(main_window_ref, QMainWindow) and \
                           current_block_idx_data != -1 and active_data_line_idx != -1 and \
                           hasattr(main_window_ref, 'short_lines_per_block') and \
                           hasattr(main_window_ref, 'data_processor') and \
                           active_data_line_idx in main_window_ref.short_lines_per_block.get(str(current_block_idx_data), set()):
                            
                            active_data_string_text_for_editor, _ = main_window_ref.data_processor.get_current_string_text(current_block_idx_data, active_data_line_idx)
                            sub_lines_of_active_data_string_for_editor = str(active_data_string_text_for_editor).split('\n')
                            
                            if current_q_block_number < len(sub_lines_of_active_data_string_for_editor) -1: 
                                current_sub_line_from_data_editor = sub_lines_of_active_data_string_for_editor[current_q_block_number]
                                current_sub_line_clean_stripped_editor = remove_all_tags(current_sub_line_from_data_editor).strip()

                                if current_sub_line_clean_stripped_editor and not current_sub_line_clean_stripped_editor.endswith(sentence_end_tuples):
                                    next_sub_line_from_data_editor = sub_lines_of_active_data_string_for_editor[current_q_block_number + 1]
                                    next_sub_line_clean_stripped_editor = remove_all_tags(next_sub_line_from_data_editor).strip()
                                    
                                    if next_sub_line_clean_stripped_editor:
                                        first_word_next_editor = next_sub_line_clean_stripped_editor.split(maxsplit=1)[0] if next_sub_line_clean_stripped_editor else ""
                                        if first_word_next_editor:
                                            first_word_next_width_editor = calculate_string_width(first_word_next_editor, main_window_ref.font_map)
                                            space_width_editor = calculate_string_width(" ", main_window_ref.font_map)
                                            current_qblock_pixel_width_rstripped_editor = calculate_string_width(remove_all_tags(current_sub_line_from_data_editor).rstrip(), main_window_ref.font_map)
                                            remaining_width_for_qblock_editor = max_width_for_short_check_paint - current_qblock_pixel_width_rstripped_editor
                                            if remaining_width_for_qblock_editor >= (first_word_next_width_editor + space_width_editor):
                                                is_this_qblock_short_for_bg = True
                        
                        if pixel_width > self.editor.LINE_WIDTH_WARNING_THRESHOLD_PIXELS:
                             bg_for_extra_part = self.editor.lineNumberArea.width_indicator_exceeded_color
                        elif is_this_qblock_short_for_bg:
                             bg_for_extra_part = SHORT_LINE_COLOR
                        
                        painter.fillRect(extra_info_rect.adjusted(0,0,3,0), bg_for_extra_part)
                        painter.setPen(text_color_for_extra_part)
                        painter.drawText(extra_info_rect, Qt.AlignRight | Qt.AlignVCenter, width_str)
                        

                    elif self.editor.objectName() == "preview_text_edit" and isinstance(main_window_ref, QMainWindow) and current_block_idx_data != -1:
                        painter.fillRect(extra_info_rect.adjusted(0,0,3,0), bg_for_extra_part)

                        indicator_x_start = number_part_width + 2
                        block_key_str_for_preview = str(current_block_idx_data)
                        data_line_index_preview = current_q_block_number

                        indicators_to_draw_preview = []
                        if hasattr(main_window_ref, 'critical_problem_lines_per_block') and \
                           data_line_index_preview in main_window_ref.critical_problem_lines_per_block.get(block_key_str_for_preview, set()):
                            indicators_to_draw_preview.append(self.editor.lineNumberArea.preview_critical_indicator_color)
                        elif hasattr(main_window_ref, 'warning_problem_lines_per_block') and \
                             data_line_index_preview in main_window_ref.warning_problem_lines_per_block.get(block_key_str_for_preview, set()):
                            indicators_to_draw_preview.append(self.editor.lineNumberArea.preview_warning_indicator_color)

                        if hasattr(main_window_ref, 'width_exceeded_lines_per_block') and \
                           data_line_index_preview in main_window_ref.width_exceeded_lines_per_block.get(block_key_str_for_preview, set()):
                             preview_width_color_temp = WIDTH_EXCEEDED_LINE_COLOR
                             if preview_width_color_temp.alpha() < 100: preview_width_color_temp = preview_width_color_temp.lighter(120) 
                             if len(indicators_to_draw_preview) < 3 and preview_width_color_temp not in indicators_to_draw_preview:
                                indicators_to_draw_preview.append(preview_width_color_temp)
                        
                        should_draw_short_indicator_for_preview = False
                        if hasattr(main_window_ref, 'short_lines_per_block') and \
                           hasattr(main_window_ref, 'data_processor') and \
                           data_line_index_preview in main_window_ref.short_lines_per_block.get(block_key_str_for_preview, set()):
                            data_string_for_preview, _ = main_window_ref.data_processor.get_current_string_text(current_block_idx_data, data_line_index_preview)
                            sub_lines_for_preview_check = str(data_string_for_preview).split('\n')
                            if len(sub_lines_for_preview_check) > 1:
                                for sub_idx_preview, sub_text_preview in enumerate(sub_lines_for_preview_check):
                                    if sub_idx_preview < len(sub_lines_for_preview_check) - 1:
                                        curr_sub_clean_strip_prev = remove_all_tags(sub_text_preview).strip()
                                        if not curr_sub_clean_strip_prev or curr_sub_clean_strip_prev.endswith(sentence_end_tuples):
                                            continue
                                        next_sub_text_prev = sub_lines_for_preview_check[sub_idx_preview+1]
                                        next_sub_clean_strip_prev = remove_all_tags(next_sub_text_prev).strip()
                                        if not next_sub_clean_strip_prev: continue
                                        
                                        first_word_next_prev = next_sub_clean_strip_prev.split(maxsplit=1)[0] if next_sub_clean_strip_prev else ""
                                        if not first_word_next_prev: continue

                                        first_word_next_width_prev = calculate_string_width(first_word_next_prev, main_window_ref.font_map)
                                        if first_word_next_width_prev > 0:
                                            curr_sub_pixel_width_prev_rstripped = calculate_string_width(remove_all_tags(sub_text_preview).rstrip(), main_window_ref.font_map)
                                            space_w_prev = calculate_string_width(" ", main_window_ref.font_map)
                                            remaining_w_prev = max_width_for_short_check_paint - curr_sub_pixel_width_prev_rstripped
                                            if remaining_w_prev >= (first_word_next_width_prev + space_w_prev):
                                                should_draw_short_indicator_for_preview = True
                                                break 
                        
                        if should_draw_short_indicator_for_preview:
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