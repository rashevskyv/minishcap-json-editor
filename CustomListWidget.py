from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QMenu
from PyQt5.QtCore import Qt, QPoint
from utils import log_debug 

class CustomListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        log_debug(f"CustomListWidget initialized with parent: {parent}")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def create_item(self, text, data, role=Qt.UserRole):
        item = QListWidgetItem(text)
        item.setData(role, data)
        return item

    def show_context_menu(self, pos: QPoint):
        item = self.itemAt(pos)
        if not item:
            return

        block_idx = item.data(Qt.UserRole)
        block_name = item.text().split(" (")[0] # Отримуємо чисту назву блоку

        menu = QMenu(self)
        
        rename_action = menu.addAction(f"Rename '{block_name}'")
        # Потрібно отримати доступ до MainWindow або його методу
        main_window = self.window() # Спроба отримати батьківське вікно
        if hasattr(main_window, 'list_selection_handler') and hasattr(main_window.list_selection_handler, 'rename_block'):
            rename_action.triggered.connect(lambda: main_window.list_selection_handler.rename_block(item))
        
        # Дія для пересканування тегів у цьому блоці
        if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'rescan_tags_for_single_block'):
            rescan_action = menu.addAction(f"Rescan Tags in '{block_name}'")
            rescan_action.triggered.connect(lambda: main_window.app_action_handler.rescan_tags_for_single_block(block_idx))
            
            # Перевіряємо, чи є проблеми в цьому блоці, щоб активувати/деактивувати дію
            has_problems = False
            if hasattr(main_window, 'problem_lines_per_block'):
                has_problems = bool(main_window.problem_lines_per_block.get(str(block_idx)))
            
            # Можна деактивувати, якщо немає проблем, або залишити активною завжди
            # rescan_action.setEnabled(has_problems) # Наприклад
            
        # Можна додати інші дії
        
        menu.exec_(self.mapToGlobal(pos))