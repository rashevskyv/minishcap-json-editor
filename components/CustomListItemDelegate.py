from PyQt5.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem
from PyQt5.QtGui import QPainter, QColor, QPalette, QBrush, QPen, QFontMetrics, QFont
from PyQt5.QtCore import QRect, Qt, QPoint, QSize, QModelIndex
from utils.utils import log_debug

class CustomListItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.list_widget = parent
        self.indicator_strip_width = 3 # Ширина однієї смужки-індикатора
        self.indicator_strip_spacing = 2 # Відстань між смужками
        self.max_indicators = 3 # Максимальна кількість індикаторів, які будемо показувати одночасно
        
        self.fixed_number_area_width_base_font_size = 10
        self.fixed_number_area_width_base_pixels = 30
        
        self.padding_after_number_area = 3 # Відступ після зони номера
        self.padding_after_indicator_zone = 5 # Відступ після зони індикаторів до тексту
        self.indicator_v_offset = 2 # Вертикальний відступ для індикаторів

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

    def _get_indicator_zone_width(self) -> int:
        return (self.indicator_strip_width * self.max_indicators) + \
               (self.indicator_strip_spacing * (self.max_indicators -1 if self.max_indicators > 0 else 0))


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
        indicator_zone_total_width = self._get_indicator_zone_width()

        calculated_width = current_number_area_width + \
                           self.padding_after_number_area + \
                           indicator_zone_total_width + \
                           self.padding_after_indicator_zone + \
                           fm.horizontalAdvance(str(index.data(Qt.DisplayRole))) + 20

        return QSize(max(default_hint.width(), calculated_width), max(default_hint.height(), min_height))


    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()

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
             number_area_bg = palette.highlight().color().darker(110) # Трохи темніше для контрасту з виділенням
             number_text_color = palette.highlightedText().color()

        # Кольори індикаторів (можна винести в константи, якщо використовуються ще десь)
        unsaved_indicator_color = QColor(Qt.red)
        critical_tag_indicator_color = QColor(Qt.yellow).darker(125)
        warning_tag_indicator_color = QColor(Qt.darkGray)
        width_exceeded_indicator_color = QColor(255, 120, 120) # Pinkish red
        short_line_indicator_color = QColor(0, 180, 0) # A bit darker green

        block_idx_data = index.data(Qt.UserRole)
        
        has_unsaved_changes_in_block = False
        has_critical_tag_issues = False
        has_warning_tag_issues = False
        has_width_exceeded_issues = False
        has_short_line_issues = False

        main_window = None
        if self.list_widget:
            main_window = self.list_widget.window()

        if main_window and block_idx_data is not None:
            block_key = str(block_idx_data)
            # is_active_block тепер не потрібен для індикатора
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

        # Малювання номера блоку
        number_rect = QRect(item_rect.left(), item_rect.top(), current_number_area_width, item_rect.height())
        painter.fillRect(number_rect, number_area_bg)
        painter.setPen(number_text_color)
        current_font = option.font
        if not current_font.family(): current_font = QFont()
        painter.setFont(current_font)
        painter.drawText(number_rect, Qt.AlignCenter | Qt.TextShowMnemonic, str(index.row() + 1))

        # Визначення зони для індикаторів
        indicator_zone_x_start = number_rect.right() + self.padding_after_number_area
        indicator_zone_total_width = self._get_indicator_zone_width()
        
        # Збираємо кольори індикаторів, які потрібно намалювати
        indicator_colors_to_draw = []
        if has_unsaved_changes_in_block: indicator_colors_to_draw.append(unsaved_indicator_color)
        
        if has_critical_tag_issues:
            indicator_colors_to_draw.append(critical_tag_indicator_color)
        elif has_warning_tag_issues: # Показуємо warning тільки якщо немає critical
            indicator_colors_to_draw.append(warning_tag_indicator_color)
        
        if has_width_exceeded_issues:
            if len(indicator_colors_to_draw) < self.max_indicators:
                 indicator_colors_to_draw.append(width_exceeded_indicator_color)
        
        if has_short_line_issues:
            if len(indicator_colors_to_draw) < self.max_indicators:
                 indicator_colors_to_draw.append(short_line_indicator_color)
        
        # Малювання індикаторів у зоні
        current_indicator_x = indicator_zone_x_start
        for i, color in enumerate(indicator_colors_to_draw):
            if i >= self.max_indicators: break # Не малюємо більше, ніж дозволено
            indicator_rect = QRect(current_indicator_x,
                                   item_rect.top() + self.indicator_v_offset,
                                   self.indicator_strip_width,
                                   item_rect.height() - 2 * self.indicator_v_offset)
            painter.fillRect(indicator_rect, color)
            current_indicator_x += self.indicator_strip_width + self.indicator_strip_spacing

        # Визначення зони для тексту назви блоку
        text_start_x = indicator_zone_x_start + indicator_zone_total_width + self.padding_after_indicator_zone
        
        text_rect = QRect(text_start_x, item_rect.top(),
                          item_rect.width() - text_start_x - 2, # -2 для невеликого правого відступу
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