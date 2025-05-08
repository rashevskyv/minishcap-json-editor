from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QMenu
from PyQt5.QtCore import Qt, QPoint
from utils import log_debug 
# Імпортуємо делегат
from CustomListItemDelegate import CustomListItemDelegate 

class CustomListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        log_debug(f"CustomListWidget initialized with parent: {parent}")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        # Встановлюємо кастомний делегат
        self.setItemDelegate(CustomListItemDelegate(self))

    def create_item(self, text, data, role=Qt.UserRole):
        item = QListWidgetItem(text)
        item.setData(role, data)
        return item

    def show_context_menu(self, pos: QPoint):
        item = self.itemAt(pos)
        if not item:
            return

        block_idx = item.data(Qt.UserRole)
        # Спробуємо отримати чисту назву блоку надійніше
        main_window = self.window()
        block_name = item.text() # Початковий текст
        if hasattr(main_window, 'block_names'):
             block_name = main_window.block_names.get(str(block_idx), f"Block {block_idx}") # Беремо назву з даних, якщо є

        menu = QMenu(self)
        
        rename_action = menu.addAction(f"Rename '{block_name}'")
        if hasattr(main_window, 'list_selection_handler') and hasattr(main_window.list_selection_handler, 'rename_block'):
            # Передаємо саме item, rename_block сам розбереться з індексом і текстом
            rename_action.triggered.connect(lambda checked=False, item=item: main_window.list_selection_handler.rename_block(item))
        
        if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'rescan_tags_for_single_block'):
            rescan_action = menu.addAction(f"Rescan Tags in '{block_name}' (use default mappings)")
            rescan_action.triggered.connect(lambda checked=False, idx=block_idx: main_window.app_action_handler.rescan_tags_for_single_block(idx))
            
        menu.exec_(self.mapToGlobal(pos))