from PyQt5.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem
from PyQt5.QtGui import QPainter, QColor, QPalette, QBrush, QPen, QFontMetrics, QFont
from PyQt5.QtCore import QRect, Qt, QPoint, QSize, QModelIndex
from utils.logging_utils import log_debug
from utils.constants import LT_PREVIEW_SELECTED_LINE_COLOR, DT_PREVIEW_SELECTED_LINE_COLOR

class CustomListItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.list_widget = parent
        
        self.problem_indicator_strip_width = 3 
        self.problem_indicator_strip_spacing = 2 
        self.max_problem_indicators = 5 

        self.color_marker_size = 8 
        self.color_marker_spacing = 3
        self.max_color_markers = 3 
        
        self.fixed_number_area_width_base_font_size = 10
        self.fixed_number_area_width_base_pixels = 30
        
        self.padding_after_number_area = 3 
        self.padding_after_color_marker_zone = 2
        self.padding_after_problem_indicator_zone = 5 
        self.indicator_v_offset = 2 

        self.marker_qcolors = {
            "red": QColor(Qt.red),
            "green": QColor(Qt.green),
            "blue": QColor(Qt.blue),
        }


    def _get_current_number_area_width(self, option: QStyleOptionViewItem) -> int:
        font_to_use = option.font
        if not font_to_use.family():
            font_for_metrics = QFont()
        else:
            font_for_metrics = font_to_use

        current_font_size = font_for_metrics.pointSize()
        if current_font_size <= 0: current_font_size = self.fixed_number_area_width_base_font_size

        scaled_width = int(self.fixed_number_area_width_base_pixels * \
                           (current_font_size / self.fixed_number_area_width_base_font_size))
        return max(scaled_width, 20)

    def _get_problem_indicator_zone_width(self) -> int:
        if self.max_problem_indicators == 0: return 0
        return (self.problem_indicator_strip_width * self.max_problem_indicators) + \
               (self.problem_indicator_strip_spacing * (self.max_problem_indicators - 1))
    
    def _get_color_marker_zone_width(self) -> int:
        if self.max_color_markers == 0: return 0
        return (self.color_marker_size * self.max_color_markers) + \
               (self.color_marker_spacing * (self.max_color_markers -1))


    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        default_hint = super().sizeHint(option, index)

        font_to_use = option.font
        if not font_to_use.family():
            font_for_metrics = QFont()
        else:
            font_for_metrics = font_to_use

        fm = QFontMetrics(font_for_metrics)
        min_height = fm.height() + 6 

        current_number_area_width = self._get_current_number_area_width(option)
        problem_indicator_zone_total_width = self._get_problem_indicator_zone_width()
        color_marker_zone_total_width = self._get_color_marker_zone_width()

        calculated_width = current_number_area_width + \
                           self.padding_after_number_area + \
                           color_marker_zone_total_width + \
                           (self.padding_after_color_marker_zone if color_marker_zone_total_width > 0 else 0) + \
                           problem_indicator_zone_total_width + \
                           (self.padding_after_problem_indicator_zone if problem_indicator_zone_total_width > 0 else 0) + \
                           fm.horizontalAdvance(str(index.data(Qt.DisplayRole))) + 20

        return QSize(max(default_hint.width(), calculated_width), max(default_hint.height(), min_height))


    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        is_selected = option.state & QStyle.State_Selected
        
        if is_selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            painter.fillRect(option.rect, option.palette.base())
        
        main_window = self.list_widget.window() if self.list_widget else None
        theme = 'light'
        if main_window and hasattr(main_window, 'theme'):
            theme = main_window.theme

        item_rect = option.rect
        current_number_area_width = self._get_current_number_area_width(option)

        if theme == 'dark':
            number_area_bg = QColor("#383838") if not is_selected else option.palette.highlight().color().darker(110)
            number_text_color = QColor("#B0B0B0") if not is_selected else option.palette.color(QPalette.HighlightedText)
        else:
            number_area_bg = QColor("#F0F0F0") if not is_selected else option.palette.highlight().color().darker(105)
            number_text_color = QColor(Qt.darkGray) if not is_selected else QColor(Qt.black)
        
        active_color_markers_for_block = set()
        
        block_idx_data = index.data(Qt.UserRole)
        problem_definitions = {}
        block_problem_counts = {}
        has_unsaved_changes_in_block = False

        if main_window and block_idx_data is not None:
            if hasattr(main_window, 'unsaved_block_indices'):
                 has_unsaved_changes_in_block = block_idx_data in main_window.unsaved_block_indices
            
            if hasattr(main_window, 'get_block_color_markers'):
                active_color_markers_for_block = main_window.get_block_color_markers(block_idx_data)

            if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
                problem_definitions = main_window.current_game_rules.get_problem_definitions()

            if hasattr(main_window, 'ui_updater') and hasattr(main_window.ui_updater, '_get_aggregated_problems_for_block'):
                block_problem_counts = main_window.ui_updater._get_aggregated_problems_for_block(block_idx_data)


        number_rect = QRect(item_rect.left(), item_rect.top(), current_number_area_width, item_rect.height())
        painter.fillRect(number_rect, number_area_bg)
        painter.setPen(number_text_color)
        current_font = option.font
        if not current_font.family(): current_font = QFont()
        painter.setFont(current_font)
        
        number_text = f"* {index.row() + 1}" if has_unsaved_changes_in_block else str(index.row() + 1)
        painter.drawText(number_rect, Qt.AlignCenter | Qt.TextShowMnemonic, number_text)

        color_marker_zone_x_start = number_rect.right() + self.padding_after_number_area
        current_color_marker_x = color_marker_zone_x_start
        sorted_active_markers = sorted(list(active_color_markers_for_block)) 

        for i, color_name in enumerate(sorted_active_markers):
            if i >= self.max_color_markers: break
            q_color = self.marker_qcolors.get(color_name)
            if q_color:
                marker_y = item_rect.top() + (item_rect.height() - self.color_marker_size) // 2
                painter.setBrush(q_color)
                painter.setPen(Qt.NoPen) 
                painter.drawEllipse(current_color_marker_x, marker_y, self.color_marker_size, self.color_marker_size)
                current_color_marker_x += self.color_marker_size + self.color_marker_spacing
        
        problem_indicator_zone_x_start = current_color_marker_x + (self.padding_after_color_marker_zone if active_color_markers_for_block else 0)
        
        problem_indicator_colors_to_draw = []
        if problem_definitions and block_problem_counts:
            sorted_block_problem_ids = sorted(
                block_problem_counts.keys(),
                key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
            )
            for problem_id in sorted_block_problem_ids:
                if block_problem_counts[problem_id] > 0:
                    if len(problem_indicator_colors_to_draw) >= self.max_problem_indicators: break
                    problem_def = problem_definitions.get(problem_id)
                    if problem_def and "color" in problem_def:
                        indicator_color = QColor(problem_def["color"])
                        if indicator_color.alpha() < 120 and theme == 'dark':
                            indicator_color.setAlpha(180)
                        if indicator_color not in problem_indicator_colors_to_draw:
                            problem_indicator_colors_to_draw.append(indicator_color)
        
        current_problem_indicator_x = problem_indicator_zone_x_start
        for i, color in enumerate(problem_indicator_colors_to_draw):
            if i >= self.max_problem_indicators: break 
            indicator_rect = QRect(current_problem_indicator_x,
                                   item_rect.top() + self.indicator_v_offset,
                                   self.problem_indicator_strip_width,
                                   item_rect.height() - 2 * self.indicator_v_offset)
            painter.fillRect(indicator_rect, color)
            current_problem_indicator_x += self.problem_indicator_strip_width + self.problem_indicator_strip_spacing
        
        text_start_x = current_problem_indicator_x + (self.padding_after_problem_indicator_zone if problem_indicator_colors_to_draw else 0)
        
        text_rect = QRect(text_start_x, item_rect.top(),
                          item_rect.width() - text_start_x - 2, 
                          item_rect.height())

        painter.setPen(option.palette.color(QPalette.HighlightedText if is_selected else QPalette.Text))

        text_to_display = index.data(Qt.DisplayRole)
        if text_to_display is None: text_to_display = ""

        metrics = QFontMetrics(current_font)
        elided_text = metrics.elidedText(str(text_to_display), Qt.ElideRight, text_rect.width())

        if elided_text:
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_text)

        painter.restore()