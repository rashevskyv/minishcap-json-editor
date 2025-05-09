from PyQt5.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem 
from PyQt5.QtGui import QPainter, QColor, QPalette, QBrush, QPen, QFontMetrics, QFont
from PyQt5.QtCore import QRect, Qt, QPoint, QSize, QModelIndex # <<< ДОДАНО QModelIndex та QSize
from utils import log_debug

class CustomListItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.list_widget = parent 
        self.indicator_width = 3 
        self.indicator_spacing = 1 
        self.fixed_number_area_width = 30 
        self.number_area_padding_right_to_indicators = 2 
        self.text_left_margin_after_indicators = 5 
        self.indicator_v_offset = 2 

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        default_hint = super().sizeHint(option, index)
        
        # Використовуємо шрифт з опцій для розрахунку висоти
        font_to_use = option.font
        if not font_to_use.family(): # Якщо шрифт не валідний, використовуємо стандартний
            font_for_metrics = QFont()
        else:
            font_for_metrics = font_to_use

        fm = QFontMetrics(font_for_metrics)
        min_height = fm.height() + 6 # Додаємо трохи більше відступу (наприклад, по 3 зверху і знизу)
        
        # Ширина може бути стандартною, або можна розрахувати, якщо потрібно, 
        # наприклад, додавши ширину номерної зони та індикаторів до ширини тексту
        # Поки що залишимо стандартну ширину + місце для наших елементів
        calculated_width = self.fixed_number_area_width + \
                           self.number_area_padding_right_to_indicators + \
                           (self.indicator_width + self.indicator_spacing) * 3 + \
                           self.text_left_margin_after_indicators + \
                           fm.horizontalAdvance(str(index.data(Qt.DisplayRole))) + 20 # Додатковий запас

        return QSize(max(default_hint.width(), calculated_width), max(default_hint.height(), min_height))


    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        # log_debug(f"Delegate paint: item {index.row()}, rect: {option.rect}, text: '{index.data(Qt.DisplayRole)}', selected: {option.state & QStyle.State_Selected}")
        painter.save()

        palette = option.palette
        
        current_element_bg_color = palette.base().color()
        if option.state & QStyle.State_Selected:
            current_element_bg_color = palette.highlight().color()
        
        painter.fillRect(option.rect, current_element_bg_color)

        item_rect = option.rect
        
        number_area_bg = QColor("#F0F0F0") 
        number_text_color = QColor(Qt.black) 
        if option.state & QStyle.State_Selected:
             number_area_bg = palette.highlight().color().darker(105) 
             number_text_color = palette.highlightedText().color()

        active_indicator_color = QColor(Qt.blue) 
        unsaved_indicator_color = QColor(Qt.red) 
        critical_tag_indicator_color = QColor(Qt.yellow).darker(125) 
        warning_tag_indicator_color = QColor(Qt.darkGray) 
        width_exceeded_indicator_color = QColor(255, 120, 120) 

        is_selected = option.state & QStyle.State_Selected
        block_idx_data = index.data(Qt.UserRole) 
        
        is_active_block = False
        has_unsaved_changes_in_block = False
        has_critical_tag_issues = False
        has_warning_tag_issues = False
        has_width_exceeded_issues = False

        main_window = None
        if self.list_widget:
            main_window = self.list_widget.window()
        
        if main_window and block_idx_data is not None:
            block_key = str(block_idx_data)
            if hasattr(main_window, 'current_block_idx'):
                is_active_block = (main_window.current_block_idx == block_idx_data)
            if hasattr(main_window, 'unsaved_block_indices'):
                 has_unsaved_changes_in_block = block_idx_data in main_window.unsaved_block_indices
            if hasattr(main_window, 'critical_problem_lines_per_block'):
                has_critical_tag_issues = bool(main_window.critical_problem_lines_per_block.get(block_key))
            if hasattr(main_window, 'warning_problem_lines_per_block'):
                has_warning_tag_issues = bool(main_window.warning_problem_lines_per_block.get(block_key))
            if hasattr(main_window, 'width_exceeded_lines_per_block'):
                has_width_exceeded_issues = bool(main_window.width_exceeded_lines_per_block.get(block_key))
        
        number_rect = QRect(item_rect.left(), item_rect.top(), self.fixed_number_area_width, item_rect.height())
        painter.fillRect(number_rect, number_area_bg)

        painter.setPen(number_text_color)
        current_font = option.font
        if not current_font.family(): current_font = QFont()
        painter.setFont(current_font)
        painter.drawText(number_rect, Qt.AlignCenter | Qt.TextShowMnemonic, str(index.row() + 1))

        current_indicator_x = number_rect.right() + self.number_area_padding_right_to_indicators
        indicator_colors_to_draw = []
        if is_active_block: indicator_colors_to_draw.append(active_indicator_color)
        if has_unsaved_changes_in_block: indicator_colors_to_draw.append(unsaved_indicator_color)
        
        if has_critical_tag_issues: 
            indicator_colors_to_draw.append(critical_tag_indicator_color)
        elif has_warning_tag_issues: 
            indicator_colors_to_draw.append(warning_tag_indicator_color) 
        
        if has_width_exceeded_issues:
            if not (has_critical_tag_issues or has_warning_tag_issues):
                 indicator_colors_to_draw.append(width_exceeded_indicator_color)
            elif width_exceeded_indicator_color not in indicator_colors_to_draw and len(indicator_colors_to_draw) < 3:
                 indicator_colors_to_draw.append(width_exceeded_indicator_color)

        actual_indicator_start_x = current_indicator_x
        for color in indicator_colors_to_draw:
            indicator_rect = QRect(actual_indicator_start_x, 
                                   item_rect.top() + self.indicator_v_offset, 
                                   self.indicator_width, 
                                   item_rect.height() - 2 * self.indicator_v_offset) 
            painter.fillRect(indicator_rect, color)
            actual_indicator_start_x += self.indicator_width + self.indicator_spacing
        
        text_start_x = number_rect.right() + self.number_area_padding_right_to_indicators 
        if indicator_colors_to_draw: 
            text_start_x = actual_indicator_start_x 
        text_start_x += self.text_left_margin_after_indicators

        text_rect = QRect(text_start_x, item_rect.top(), 
                          item_rect.width() - text_start_x - 2, 
                          item_rect.height()) 
        
        text_color_for_name_final = palette.text().color()
        if is_selected:
            text_color_for_name_final = palette.highlightedText().color()
        painter.setPen(text_color_for_name_final)
            
        text_to_display = index.data(Qt.DisplayRole) 
        if text_to_display is None: text_to_display = ""
        
        metrics = QFontMetrics(current_font) # Використовуємо той самий шрифт, що і для номера
        elided_text = metrics.elidedText(str(text_to_display), Qt.ElideRight, text_rect.width())
        
        if elided_text:
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_text)

        painter.restore()