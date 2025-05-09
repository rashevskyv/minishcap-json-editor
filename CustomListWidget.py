from PyQt5.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem 
from PyQt5.QtGui import QPainter, QColor, QPalette, QBrush, QPen
from PyQt5.QtCore import QRect, Qt, QPoint
from PyQt5.QtWidgets import QListWidget # Or whatever base class you intend to use

class CustomListItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.list_widget = parent 

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()

        selected_color = option.palette.highlight().color()
        base_color = option.palette.base().color()
        selected_text_color = option.palette.highlightedText().color()
        text_color = option.palette.text().color()
        number_area_bg_color = QColor("#f0f0f0")
        number_area_pen_color = QColor("#888")
        active_indicator_color = QColor(Qt.blue) 
        unsaved_indicator_color = QColor(Qt.red) 
        
        critical_problem_bg_color = QColor(Qt.yellow).lighter(150) 
        warning_problem_bg_color = QColor(Qt.lightGray).lighter(110) 
        width_problem_bg_color = QColor(Qt.red).lighter(130) # Такий самий, як в TextHighlightManager

        is_selected = option.state & QStyle.State_Selected
        block_idx = index.data(Qt.UserRole) 
        is_active = False # Чи є цей блок поточним активним блоком у MainWindow
        has_critical_problem_tags = False
        has_warning_problem_tags = False
        has_width_problem = False
        has_unsaved_changes = False

        main_window = None
        if self.list_widget:
            main_window = self.list_widget.window()
        
        if main_window and hasattr(main_window, 'current_block_idx'):
            is_active = (main_window.current_block_idx == block_idx)
        
        if main_window and block_idx is not None:
            block_key = str(block_idx)
            if hasattr(main_window, 'critical_problem_lines_per_block'):
                has_critical_problem_tags = bool(main_window.critical_problem_lines_per_block.get(block_key))
            if hasattr(main_window, 'warning_problem_lines_per_block'):
                has_warning_problem_tags = bool(main_window.warning_problem_lines_per_block.get(block_key))
            if hasattr(main_window, 'width_problem_lines_per_block'):
                has_width_problem = bool(main_window.width_problem_lines_per_block.get(block_key))
            if hasattr(main_window, 'unsaved_block_indices'):
                 has_unsaved_changes = block_idx in main_window.unsaved_block_indices

        current_bg_color_for_item = base_color # Базовий фон
        
        # Визначення фону на основі проблем (пріоритет: критичні теги > проблеми ширини > попередження тегів)
        if has_critical_problem_tags:
            current_bg_color_for_item = critical_problem_bg_color
        elif has_width_problem: # Проблеми ширини мають вищий пріоритет, ніж попередження тегів
            current_bg_color_for_item = width_problem_bg_color
        elif has_warning_problem_tags:
            current_bg_color_for_item = warning_problem_bg_color
            
        if is_selected: # Якщо елемент вибраний, використовуємо колір вибору
            painter.fillRect(option.rect, selected_color)
        else:
            painter.fillRect(option.rect, current_bg_color_for_item)


        indicator_width = 4 
        total_indicator_width = 0 
        number_area_width = 36 
        
        current_indicator_left = option.rect.left()

        if is_active: # Індикатор активності малюється завжди, якщо блок активний
            indicator_rect = QRect(current_indicator_left, option.rect.top(), indicator_width, option.rect.height())
            painter.fillRect(indicator_rect, active_indicator_color)
            current_indicator_left += indicator_width
            total_indicator_width += indicator_width

        if has_unsaved_changes:
             indicator_rect = QRect(current_indicator_left, option.rect.top(), indicator_width, option.rect.height())
             painter.fillRect(indicator_rect, unsaved_indicator_color)
             current_indicator_left += indicator_width
             total_indicator_width += indicator_width

        number_rect = QRect(option.rect.left() + total_indicator_width, option.rect.top(), number_area_width, option.rect.height())
        
        painter.fillRect(number_rect, number_area_bg_color) # Зона номера завжди має свій фон
        
        painter.setPen(number_area_pen_color)
        painter.drawText(number_rect, Qt.AlignCenter, str(index.row() + 1))

        text_left_margin = total_indicator_width + number_area_width + 4 
        text_rect = QRect(option.rect.left() + text_left_margin, option.rect.top(), option.rect.width() - text_left_margin - 4, option.rect.height()) 
        
        current_text_color = text_color
        if is_selected:
            current_text_color = selected_text_color
            
        painter.setPen(current_text_color)
        text = index.data(Qt.DisplayRole) 
        metrics = painter.fontMetrics()
        elided_text = metrics.elidedText(text, Qt.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided_text)

        painter.restore()


from PyQt5.QtWidgets import QListWidget # Or whatever base class you intend to use
from PyQt5.QtWidgets import QListWidgetItem, QStyledItemDelegate, QStyleOptionViewItem, QApplication
from PyQt5.QtGui import QColor, QPalette, QBrush, QPen
from PyQt5.QtCore import Qt, QEvent, QModelIndex

class CustomListWidgetDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.list_widget = parent 

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()

        selected_color = option.palette.highlight().color()
        base_color = option.palette.base().color()
        selected_text_color = option.palette.highlightedText().color()
        text_color = option.palette.text().color()
        number_area_bg_color = QColor("#f0f0f0")
        number_area_pen_color = QColor("#888")
        active_indicator_color = QColor(Qt.blue) 
        unsaved_indicator_color = QColor(Qt.red) 
        
        critical_problem_bg_color = QColor(Qt.yellow).lighter(150) 
        warning_problem_bg_color = QColor(Qt.lightGray).lighter(110) 
        width_problem_bg_color = QColor(Qt.red).lighter(130) # Такий самий, як в TextHighlightManager

        is_selected = option.state & QStyle.State_Selected
        block_idx = index.data(Qt.UserRole) 
        is_active = False # Чи є цей блок поточним активним блоком у MainWindow
        has_critical_problem_tags = False
        has_warning_problem_tags = False
        has_width_problem = False
        has_unsaved_changes = False

        main_window = None
        if self.list_widget:
            main_window = self.list_widget.window()
        
        if main_window and hasattr(main_window, 'current_block_idx'):
            is_active = (main_window.current_block_idx == block_idx)
        
        if main_window and block_idx is not None:
            block_key = str(block_idx)
            if hasattr(main_window, 'critical_problem_lines_per_block'):
                has_critical_problem_tags = bool(main_window.critical_problem_lines_per_block.get(block_key))
            if hasattr(main_window, 'warning_problem_lines_per_block'):
                has_warning_problem_tags = bool(main_window.warning_problem_lines_per_block.get(block_key))
            if hasattr(main_window, 'width_problem_lines_per_block'):
                has_width_problem = bool(main_window.width_problem_lines_per_block.get(block_key))
            if hasattr(main_window, 'unsaved_block_indices'):
                 has_unsaved_changes = block_idx in main_window.unsaved_block_indices

        current_bg_color_for_item = base_color # Базовий фон
        
        # Визначення фону на основі проблем (пріоритет: критичні теги > проблеми ширини > попередження тегів)
        if has_critical_problem_tags:
            current_bg_color_for_item = critical_problem_bg_color
        elif has_width_problem: # Проблеми ширини мають вищий пріоритет, ніж попередження тегів
            current_bg_color_for_item = width_problem_bg_color
        elif has_warning_problem_tags:
            current_bg_color_for_item = warning_problem_bg_color
            
        if is_selected: # Якщо елемент вибраний, використовуємо колір вибору
            painter.fillRect(option.rect, selected_color)
        else:
            painter.fillRect(option.rect, current_bg_color_for_item)


        indicator_width = 4 
        total_indicator_width = 0 
        number_area_width = 36 
        
        current_indicator_left = option.rect.left()

        if is_active: # Індикатор активності малюється завжди, якщо блок активний
            indicator_rect = QRect(current_indicator_left, option.rect.top(), indicator_width, option.rect.height())
            painter.fillRect(indicator_rect, active_indicator_color)
            current_indicator_left += indicator_width
            total_indicator_width += indicator_width

        if has_unsaved_changes:
             indicator_rect = QRect(current_indicator_left, option.rect.top(), indicator_width, option.rect.height())
             painter.fillRect(indicator_rect, unsaved_indicator_color)
             current_indicator_left += indicator_width
             total_indicator_width += indicator_width

        number_rect = QRect(option.rect.left() + total_indicator_width, option.rect.top(), number_area_width, option.rect.height())
        
        painter.fillRect(number_rect, number_area_bg_color) # Зона номера завжди має свій фон
        
        painter.setPen(number_area_pen_color)
        painter.drawText(number_rect, Qt.AlignCenter, str(index.row() + 1))

        text_left_margin = total_indicator_width + number_area_width + 4 
        text_rect = QRect(option.rect.left() + text_left_margin, option.rect.top(), option.rect.width() - text_left_margin - 4, option.rect.height()) 
        
        current_text_color = text_color
        if is_selected:
            current_text_color = selected_text_color
            
        painter.setPen(current_text_color)
        text = index.data(Qt.DisplayRole) 
        metrics = painter.fontMetrics()
        elided_text = metrics.elidedText(text, Qt.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided_text)

        painter.restore()


from PyQt5.QtWidgets import QListWidget # Or whatever base class you intend to use

class CustomListWidget(QListWidget):  # Ensure this name matches exactly
    def __init__(self, parent=None):
        super().__init__(parent)
        # Your custom list widget initialization code here
        # ...

    # Other methods for your custom list widget
    # ...

    # Add the create_item method here
    def create_item(self, text: str, index_data):
        item = QListWidgetItem(text)
        # You might want to store the index_data (which is 'i' in populate_blocks)
        # with the item for later retrieval, e.g., using setData.
        item.setData(Qt.UserRole, index_data)
        self.addItem(item)
        return item

    def update_item_visuals(self, item_index):
        # ... existing code ...
        pass

# Make sure there are no typos in the class name "CustomListWidget"