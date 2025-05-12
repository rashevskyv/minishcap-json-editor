from PyQt5.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem
from PyQt5.QtGui import QPainter, QColor, QPalette, QBrush, QPen, QFontMetrics, QFont
from PyQt5.QtCore import QRect, Qt, QPoint, QSize, QModelIndex
from utils.utils import log_debug
from components.LNET_constants import EMPTY_ODD_SUBLINE_COLOR 

class CustomListItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.list_widget = parent
        
        self.problem_indicator_strip_width = 3 
        self.problem_indicator_strip_spacing = 2 
        self.max_problem_indicators = 3 

        self.color_marker_size = 8 
        self.color_marker_spacing = 3
        self.max_color_markers = 3 
        
        self.fixed_number_area_width_base_font_size = 10
        self.fixed_number_area_width_base_pixels = 30
        
        self.padding_after_number_area = 3 
        self.padding_after_color_marker_zone = 2
        self.padding_after_problem_indicator_zone = 5 
        self.indicator_v_offset = 2 

        # Кольори для маркерів (можна синхронізувати з CustomListWidget або передавати)
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

        palette = option.palette
        is_selected = option.state & QStyle.State_Selected

        current_element_bg_color = palette.base().color()
        if is_selected:
            current_element_bg_color = palette.highlight().color()

        painter.fillRect(option.rect, current_element_bg_color)

        item_rect = option.rect
        current_number_area_width = self._get_current_number_area_width(option)

        number_area_bg = QColor("#F0F0F0") 
        number_text_color = QColor(Qt.black)
        if is_selected:
             number_area_bg = palette.highlight().color().darker(110) 
             number_text_color = palette.highlightedText().color()
        
        # Кольори для індикаторів проблем
        unsaved_indicator_color = QColor(Qt.red).darker(120) # Зробимо трохи темнішим для контрасту з маркером
        critical_tag_indicator_color = QColor(Qt.yellow).darker(125)
        warning_tag_indicator_color = QColor(Qt.gray) # Змінено для кращого розрізнення
        width_exceeded_indicator_color = QColor(255, 120, 120) 
        short_line_indicator_color = QColor(0, 180, 0) 
        empty_odd_indicator_color = EMPTY_ODD_SUBLINE_COLOR 

        block_idx_data = index.data(Qt.UserRole)
        
        has_unsaved_changes_in_block = False
        has_critical_tag_issues = False
        has_warning_tag_issues = False
        has_width_exceeded_issues = False
        has_short_line_issues = False
        has_empty_odd_unisingle_issues = False
        active_color_markers_for_block = set()

        main_window = None
        if self.list_widget:
            main_window = self.list_widget.window()

        if main_window and block_idx_data is not None:
            block_key = str(block_idx_data)
            if hasattr(main_window, 'unsaved_block_indices'):
                 has_unsaved_changes_in_block = block_idx_data in main_window.unsaved_block_indices
            if hasattr(main_window, 'critical_problem_lines_per_block'):
                has_critical_tag_issues = bool(main_window.critical_problem_lines_per_block.get(block_key))
            if hasattr(main_window, 'warning_problem_lines_per_block'):
                has_warning_tag_issues = bool(main_window.warning_problem_lines_per_block.get(block_key))
            if hasattr(main_window, 'width_exceeded_lines_per_block'):
                has_width_exceeded_issues = bool(main_window.width_exceeded_lines_per_block.get(block_key))
            if hasattr(main_window, 'short_lines_per_block'):
                has_short_line_issues = bool(main_window.short_lines_per_block.get(block_key))
            if hasattr(main_window, 'empty_odd_unisingle_subline_problem_strings'): 
                has_empty_odd_unisingle_issues = bool(main_window.empty_odd_unisingle_subline_problem_strings.get(block_key))
            if hasattr(main_window, 'get_block_color_markers'):
                active_color_markers_for_block = main_window.get_block_color_markers(block_idx_data)


        number_rect = QRect(item_rect.left(), item_rect.top(), current_number_area_width, item_rect.height())
        painter.fillRect(number_rect, number_area_bg)
        painter.setPen(number_text_color)
        current_font = option.font
        if not current_font.family(): current_font = QFont()
        painter.setFont(current_font)
        painter.drawText(number_rect, Qt.AlignCenter | Qt.TextShowMnemonic, str(index.row() + 1))

        # Малювання кольорових маркерів (кружечків)
        color_marker_zone_x_start = number_rect.right() + self.padding_after_number_area
        color_marker_zone_total_width = self._get_color_marker_zone_width()
        
        current_color_marker_x = color_marker_zone_x_start
        sorted_active_markers = sorted(list(active_color_markers_for_block)) # Для стабільного порядку

        for i, color_name in enumerate(sorted_active_markers):
            if i >= self.max_color_markers: break
            q_color = self.marker_qcolors.get(color_name)
            if q_color:
                marker_y = item_rect.top() + (item_rect.height() - self.color_marker_size) // 2
                painter.setBrush(q_color)
                painter.setPen(Qt.NoPen) 
                painter.drawEllipse(current_color_marker_x, marker_y, self.color_marker_size, self.color_marker_size)
                current_color_marker_x += self.color_marker_size + self.color_marker_spacing
        
        # Малювання індикаторів проблем (смужок)
        problem_indicator_zone_x_start = color_marker_zone_x_start + color_marker_zone_total_width + \
                                         (self.padding_after_color_marker_zone if color_marker_zone_total_width > 0 else 0)
        
        problem_indicator_colors_to_draw = []
        if has_unsaved_changes_in_block: problem_indicator_colors_to_draw.append(unsaved_indicator_color)
        
        if has_critical_tag_issues:
            problem_indicator_colors_to_draw.append(critical_tag_indicator_color)
        elif has_warning_tag_issues: 
            problem_indicator_colors_to_draw.append(warning_tag_indicator_color)
        
        if has_empty_odd_unisingle_issues: 
            if len(problem_indicator_colors_to_draw) < self.max_problem_indicators:
                 problem_indicator_colors_to_draw.append(empty_odd_indicator_color)

        if has_width_exceeded_issues:
            if len(problem_indicator_colors_to_draw) < self.max_problem_indicators:
                 problem_indicator_colors_to_draw.append(width_exceeded_indicator_color)
        
        if has_short_line_issues:
            if len(problem_indicator_colors_to_draw) < self.max_problem_indicators:
                 problem_indicator_colors_to_draw.append(short_line_indicator_color)
        
        current_problem_indicator_x = problem_indicator_zone_x_start
        problem_indicator_zone_total_width = self._get_problem_indicator_zone_width()

        for i, color in enumerate(problem_indicator_colors_to_draw):
            if i >= self.max_problem_indicators: break 
            indicator_rect = QRect(current_problem_indicator_x,
                                   item_rect.top() + self.indicator_v_offset,
                                   self.problem_indicator_strip_width,
                                   item_rect.height() - 2 * self.indicator_v_offset)
            painter.fillRect(indicator_rect, color)
            current_problem_indicator_x += self.problem_indicator_strip_width + self.problem_indicator_strip_spacing

        text_start_x = problem_indicator_zone_x_start + \
                       (problem_indicator_zone_total_width if problem_indicator_zone_total_width > 0 else -self.padding_after_problem_indicator_zone) + \
                       self.padding_after_problem_indicator_zone
        
        text_rect = QRect(text_start_x, item_rect.top(),
                          item_rect.width() - text_start_x - 2, 
                          item_rect.height())

        text_color_for_name_final = palette.text().color()
        if is_selected:
            text_color_for_name_final = palette.highlightedText().color()
        painter.setPen(text_color_for_name_final)

        text_to_display = index.data(Qt.DisplayRole)
        if text_to_display is None: text_to_display = ""

        metrics = QFontMetrics(current_font)
        elided_text = metrics.elidedText(str(text_to_display), Qt.ElideRight, text_rect.width())

        if elided_text:
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_text)

        painter.restore()