from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtWidgets import QMainWindow, QTextEdit
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, ALL_TAGS_PATTERN, log_debug
from plugins.zelda_mc.rules import (
    PROBLEM_SHORT_LINE, PROBLEM_WIDTH_EXCEEDED, 
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY, PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL
)

class LNETLineNumberAreaPaintLogic:

    def __init__(self, editor, helpers):
        self.editor = editor
        self.helpers = helpers 

    def execute_paint_event(self, event, painter_device):
        painter = QPainter(painter_device)
        main_window_ref = self.editor.window()
        
        game_rules = None
        problem_definitions = {}
        if isinstance(main_window_ref, QMainWindow) and hasattr(main_window_ref, 'current_game_rules') and main_window_ref.current_game_rules:
            game_rules = main_window_ref.current_game_rules
            problem_definitions = game_rules.get_problem_definitions()

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
        current_q_block_number_in_editor_doc = current_q_block.blockNumber() 
        top = int(self.editor.blockBoundingGeometry(current_q_block).translated(self.editor.contentOffset()).top())
        bottom = top + int(self.editor.blockBoundingRect(current_q_block).height())

        current_font_for_numbers = self.editor.font()
        painter.setFont(current_font_for_numbers)

        odd_bg_color_const = self.editor.lineNumberArea.odd_line_background
        even_bg_color_const = default_bg_color_for_area
        
        current_block_idx_data_mw = -1
        current_string_idx_data_mw = -1
        if isinstance(main_window_ref, QMainWindow):
             current_block_idx_data_mw = main_window_ref.current_block_idx
             current_string_idx_data_mw = main_window_ref.current_string_idx


        while current_q_block.isValid() and top <= event.rect().bottom():
            if current_q_block.isVisible() and bottom >= event.rect().top():
                line_height = int(self.editor.blockBoundingRect(current_q_block).height())
                display_number_for_line_area = str(current_q_block_number_in_editor_doc + 1)

                number_part_rect = QRect(0, top, number_part_width, line_height)
                extra_info_part_rect = QRect(number_part_width, top, extra_part_width, line_height)

                bg_color_number_area = even_bg_color_const
                if (current_q_block_number_in_editor_doc + 1) % 2 != 0: 
                    bg_color_number_area = odd_bg_color_const
                bg_color_extra_info_area = bg_color_number_area 
                
                problem_ids_for_this_subline = set()

                if self.editor.objectName() == "original_text_edit" or self.editor.objectName() == "edited_text_edit":
                    if game_rules and current_block_idx_data_mw != -1 and current_string_idx_data_mw != -1:
                        subline_local_idx_for_problems = current_q_block_number_in_editor_doc
                        problem_key = (current_block_idx_data_mw, current_string_idx_data_mw, subline_local_idx_for_problems)
                        problem_ids_for_this_subline = main_window_ref.problems_per_subline.get(problem_key, set())
                        if problem_ids_for_this_subline: # Log only if there are problems
                            log_debug(f"  LNETPaintLogic ({self.editor.objectName()}): For QBlk {current_q_block_number_in_editor_doc} (Data B{current_block_idx_data_mw}S{current_string_idx_data_mw}L{subline_local_idx_for_problems}), problems_per_subline: {problem_ids_for_this_subline}")
                
                elif self.editor.objectName() == "preview_text_edit":
                    if game_rules and current_block_idx_data_mw != -1:
                        data_line_index_preview = current_q_block_number_in_editor_doc 
                        
                        aggregated_problems_for_data_line = set()
                        data_string_text_preview, _ = main_window_ref.data_processor.get_current_string_text(current_block_idx_data_mw, data_line_index_preview)
                        if data_string_text_preview is not None: 
                            logical_sublines_count_preview = len(str(data_string_text_preview).split('\n'))
                            for subline_local_idx_preview in range(logical_sublines_count_preview):
                                problem_key_preview = (current_block_idx_data_mw, data_line_index_preview, subline_local_idx_preview)
                                problems_for_logical_subline = main_window_ref.problems_per_subline.get(problem_key_preview, set())
                                aggregated_problems_for_data_line.update(problems_for_logical_subline)
                        problem_ids_for_this_subline = aggregated_problems_for_data_line
                        if problem_ids_for_this_subline: # Log only if there are problems
                             log_debug(f"  LNETPaintLogic (preview_text_edit): For DataLine {data_line_index_preview} (QBlk {current_q_block_number_in_editor_doc}), aggregated problems: {problem_ids_for_this_subline}")
                
                if self.editor.objectName() == "original_text_edit" or self.editor.objectName() == "edited_text_edit":
                    if problem_ids_for_this_subline:
                        sorted_subline_problem_ids = sorted(
                            list(problem_ids_for_this_subline),
                            key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
                        )
                        if sorted_subline_problem_ids:
                            highest_priority_pid = sorted_subline_problem_ids[0]
                            color_def = problem_definitions.get(highest_priority_pid)
                            if color_def and "color" in color_def:
                                chosen_color = QColor(color_def["color"])
                                bg_color_extra_info_area = chosen_color
                                if highest_priority_pid == PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY:
                                    bg_color_number_area = chosen_color
                                log_debug(f"    LNETPaintLogic ({self.editor.objectName()}): QBlk {current_q_block_number_in_editor_doc} - Highest priority PID: {highest_priority_pid}, ChosenColor: {chosen_color.name()}, Applied to: {'NumberArea & ExtraInfo' if highest_priority_pid == PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY else 'ExtraInfo'}")


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

                    elif self.editor.objectName() == "preview_text_edit" and isinstance(main_window_ref, QMainWindow) and current_block_idx_data_mw != -1 and game_rules:
                        indicator_x_start = number_part_width + 2
                        indicators_to_draw_preview = []
                        
                        sorted_problem_ids_for_preview_indicator = sorted(
                            list(problem_ids_for_this_subline), 
                            key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
                        )

                        for problem_id in sorted_problem_ids_for_preview_indicator:
                            if len(indicators_to_draw_preview) >= 3:
                                break
                            problem_def_preview = problem_definitions.get(problem_id)
                            if problem_def_preview:
                                color = problem_def_preview.get("color")
                                if color:
                                    indicator_color = QColor(color)
                                    if indicator_color.alpha() < 100: 
                                        indicator_color = indicator_color.lighter(120)
                                    if indicator_color not in indicators_to_draw_preview:
                                        indicators_to_draw_preview.append(indicator_color)
                        
                        current_indicator_x_preview = indicator_x_start
                        for color_idx, color_val in enumerate(indicators_to_draw_preview):
                            if current_indicator_x_preview + self.editor.lineNumberArea.preview_indicator_width <= number_part_width + extra_part_width -1:
                                ind_rect = QRect(current_indicator_x_preview,
                                                 top + 2,
                                                 self.editor.lineNumberArea.preview_indicator_width,
                                                 line_height - 4)
                                painter.fillRect(ind_rect, color_val)
                                current_indicator_x_preview += self.editor.lineNumberArea.preview_indicator_width + self.editor.lineNumberArea.preview_indicator_spacing
                            else: break

            current_q_block = current_q_block.next()
            top = bottom
            bottom = top + int(self.editor.blockBoundingRect(current_q_block).height())
            current_q_block_number_in_editor_doc += 1