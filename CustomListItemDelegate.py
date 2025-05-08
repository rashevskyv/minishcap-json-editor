# Додаємо QStyleOptionViewItem до імпортів з QtWidgets
from PyQt5.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem 
from PyQt5.QtGui import QPainter, QColor, QPalette, QBrush, QPen
from PyQt5.QtCore import QRect, Qt, QPoint

class CustomListItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.list_widget = parent 

    # Виправляємо тип хінт для 'option'
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index): 
        painter.save()

        # --- Визначення кольорів ---
        selected_color = option.palette.highlight().color()
        base_color = option.palette.base().color()
        selected_text_color = option.palette.highlightedText().color()
        text_color = option.palette.text().color()
        number_area_bg_color = QColor("#f0f0f0")
        number_area_pen_color = QColor("#888")
        active_indicator_color = QColor(Qt.blue) 
        critical_problem_color = QColor(Qt.yellow).lighter(150) 
        warning_problem_color = QColor(Qt.lightGray).lighter(110) 
        
        # --- Визначення стану ---
        is_selected = option.state & QStyle.State_Selected
        block_idx = index.data(Qt.UserRole) 
        is_active = False
        has_critical_problem = False
        has_warning_problem = False

        main_window = None
        if self.list_widget:
            main_window = self.list_widget.window()
        
        if main_window and hasattr(main_window, 'current_block_idx'):
            is_active = (main_window.current_block_idx == block_idx)
        
        if main_window and block_idx is not None:
            block_key = str(block_idx)
            if hasattr(main_window, 'critical_problem_lines_per_block'):
                has_critical_problem = bool(main_window.critical_problem_lines_per_block.get(block_key))
            if hasattr(main_window, 'warning_problem_lines_per_block'):
                has_warning_problem = bool(main_window.warning_problem_lines_per_block.get(block_key)) and not has_critical_problem

        # --- Малювання фону ---
        current_bg_color = base_color
        # Спочатку перевіряємо виділення, бо воно має найвищий пріоритет візуально
        if is_selected:
            current_bg_color = selected_color
        elif has_critical_problem:
             current_bg_color = critical_problem_color
        elif has_warning_problem:
             current_bg_color = warning_problem_color
             
        painter.fillRect(option.rect, current_bg_color)

        # --- Малювання зони нумерації та індикатора ---
        number_area_width = 36 
        number_rect = QRect(option.rect.left(), option.rect.top(), number_area_width, option.rect.height())
        
        painter.fillRect(number_rect, number_area_bg_color)
        
        if is_active:
            indicator_width = 4
            indicator_rect = QRect(option.rect.left(), option.rect.top(), indicator_width, option.rect.height())
            painter.fillRect(indicator_rect, active_indicator_color)
            number_rect.setLeft(number_rect.left() + indicator_width)
            number_rect.setWidth(number_rect.width() - indicator_width)

        painter.setPen(number_area_pen_color)
        painter.drawText(number_rect, Qt.AlignCenter, str(index.row() + 1))

        # --- Малювання тексту ---
        text_rect = QRect(option.rect.left() + number_area_width + 4, option.rect.top(), option.rect.width() - number_area_width - 8, option.rect.height()) 
        # Визначаємо колір тексту залежно від виділення *після* малювання фону
        current_text_color = text_color
        if is_selected:
            current_text_color = selected_text_color
            
        painter.setPen(current_text_color)
        text = index.data(Qt.DisplayRole) 
        metrics = painter.fontMetrics()
        elided_text = metrics.elidedText(text, Qt.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided_text)

        painter.restore()