from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtWidgets import QMainWindow, QTextEdit
from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, ALL_TAGS_PATTERN

class LNETLineNumberAreaPaintLogic:

    def __init__(self, editor, helpers):
        self.editor = editor
        self.helpers = helpers

    def execute_paint_event(self, event, painter_device):
        painter = QPainter(painter_device)
        main_window_ref = self.editor.window()

        game_rules = None
        problem_definitions = {}
        theme = 'light'
        detection_config = {}
        if isinstance(main_window_ref, QMainWindow):
            if hasattr(main_window_ref, 'current_game_rules') and main_window_ref.current_game_rules:
                game_rules = main_window_ref.current_game_rules
                problem_definitions = game_rules.get_problem_definitions()
            if hasattr(main_window_ref, 'theme'):
                theme = main_window_ref.theme
            if hasattr(main_window_ref, 'detection_enabled'):
                detection_config = main_window_ref.detection_enabled

        default_bg_color_for_area = self.editor.palette().base().color()
        if self.editor.isReadOnly():
             default_bg_color_for_area = self.editor.palette().window().color().lighter(105)

        total_area_width = self.editor.lineNumberAreaWidth()
        extra_part_width = 0
        if self.editor.objectName() in ["original_text_edit", "edited_text_edit"] and self.editor.font_map:
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
        even_bg_color_const = self.editor.lineNumberArea.even_line_background
        number_text_color_const = self.editor.lineNumberArea.number_color


        current_block_idx_data_mw = -1
        current_string_idx_data_mw = -1
        if isinstance(main_window_ref, QMainWindow):
             current_block_idx_data_mw = main_window_ref.current_block_idx
             current_string_idx_data_mw = main_window_ref.current_string_idx


        while current_q_block.isValid() and top <= event.rect().bottom():
            if current_q_block.isVisible() and bottom >= event.rect().top():
                line_height = int(self.editor.blockBoundingRect(current_q_block).height())
                
                is_preview = self.editor.objectName() == "preview_text_edit"
                is_editor = self.editor.objectName() in ["original_text_edit", "edited_text_edit"]
                
                display_number_for_line_area = str(current_q_block_number_in_editor_doc + 1)
                
                if isinstance(main_window_ref, QMainWindow):
                    is_unsaved = False
                    if is_preview:
                        data_line_idx = current_q_block_number_in_editor_doc
                        is_unsaved = (current_block_idx_data_mw, data_line_idx) in main_window_ref.edited_data
                    elif is_editor and current_string_idx_data_mw != -1:
                        is_unsaved = (current_block_idx_data_mw, current_string_idx_data_mw) in main_window_ref.edited_data
                    
                    if is_unsaved:
                        display_number_for_line_area = f"* {display_number_for_line_area}"


                number_part_rect = QRect(0, top, number_part_width, line_height)
                extra_info_part_rect = QRect(number_part_width, top, extra_part_width, line_height)

                bg_color_number_area = even_bg_color_const
                if (current_q_block_number_in_editor_doc + 1) % 2 != 0:
                    bg_color_number_area = odd_bg_color_const
                bg_color_extra_info_area = bg_color_number_area

                problem_ids_for_this_qtextblock = set()
                
                if game_rules and hasattr(game_rules, 'problem_analyzer'):
                    analyzer = game_rules.problem_analyzer
                    data_string_text, _ = main_window_ref.data_processor.get_current_string_text(current_block_idx_data_mw, current_string_idx_data_mw if is_editor else current_q_block_number_in_editor_doc)
                    
                    if data_string_text is not None:
                        current_text = str(data_string_text)
                        all_problems_for_string = []
                        if hasattr(analyzer, 'analyze_data_string'):
                            all_problems_for_string = analyzer.analyze_data_string(current_text, main_window_ref.font_map, main_window_ref.line_width_warning_threshold_pixels)
                        else:
                            sublines = current_text.split('\n')
                            for i, subline in enumerate(sublines):
                                next_subline = sublines[i+1] if i + 1 < len(sublines) else None
                                problems = analyzer.analyze_subline(
                                    text=subline, next_text=next_subline, subline_number_in_data_string=i, qtextblock_number_in_editor=i,
                                    is_last_subline_in_data_string=(i == len(sublines) - 1), editor_font_map=main_window_ref.font_map,
                                    editor_line_width_threshold=main_window_ref.line_width_warning_threshold_pixels,
                                    full_data_string_text_for_logical_check=current_text
                                )
                                all_problems_for_string.append(problems)

                        if is_editor and current_q_block_number_in_editor_doc < len(all_problems_for_string):
                            problem_ids_for_this_qtextblock = all_problems_for_string[current_q_block_number_in_editor_doc]
                        elif is_preview:
                            for problem_set in all_problems_for_string:
                                problem_ids_for_this_qtextblock.update(problem_set)

                filtered_problems = {p_id for p_id in problem_ids_for_this_qtextblock if detection_config.get(p_id, True)}
                
                if is_editor and filtered_problems:
                    sorted_subline_problem_ids = sorted(
                        list(filtered_problems),
                        key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
                    )
                    if sorted_subline_problem_ids:
                        highest_priority_pid = sorted_subline_problem_ids[0]
                        color_def = problem_definitions.get(highest_priority_pid)
                        if color_def and "color" in color_def:
                            bg_color_extra_info_area = QColor(color_def["color"])


                painter.fillRect(number_part_rect, bg_color_number_area)
                painter.fillRect(extra_info_part_rect, bg_color_extra_info_area)
                
                painter.setPen(number_text_color_const)
                painter.drawText(QRect(0, top, number_part_width - 3, line_height), Qt.AlignRight | Qt.AlignVCenter, display_number_for_line_area)

                if extra_part_width > 0:
                    if is_editor and self.editor.font_map:
                        q_block_text_raw_dots_paint_text = current_q_block.text()
                        q_block_text_spaces_paint_text = convert_dots_to_spaces_from_editor(q_block_text_raw_dots_paint_text)
                        text_for_width_calc_rstripped_paint_text = remove_all_tags(q_block_text_spaces_paint_text).rstrip()
                        pixel_width = calculate_string_width(text_for_width_calc_rstripped_paint_text, self.editor.font_map)
                        width_str_text = str(pixel_width)
                        
                        text_color_for_extra_part = QColor(Qt.darkGray) if theme == 'light' else QColor(Qt.darkGray).darker(120)
                        painter.setPen(text_color_for_extra_part)
                        painter.drawText(QRect(number_part_width, top, extra_part_width -3 , line_height), Qt.AlignRight | Qt.AlignVCenter, width_str_text)

                    elif is_preview and isinstance(main_window_ref, QMainWindow) and current_block_idx_data_mw != -1 and game_rules:
                        indicator_x_start = number_part_width + 2
                        indicators_to_draw_preview = []

                        if filtered_problems:
                            log_debug(f"Preview Line {current_q_block_number_in_editor_doc+1} has filtered problems: {filtered_problems}")

                        sorted_problem_ids_for_preview_indicator = sorted(
                            list(filtered_problems),
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
                                    if indicator_color.alpha() < 120 and theme == 'dark':
                                         indicator_color.setAlpha(180)
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