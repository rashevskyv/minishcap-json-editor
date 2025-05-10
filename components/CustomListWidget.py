from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QMenu
from PyQt5.QtCore import Qt, QPoint, QSize
from utils.utils import log_debug
from .CustomListItemDelegate import CustomListItemDelegate

class CustomListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        log_debug(f"CustomListWidget INITIALIZED, parent: {parent}") 
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # Важливо для кастомного малювання з різними висотами/ширинами
        self.setUniformItemSizes(False) 
        
        delegate = CustomListItemDelegate(self)
        self.setItemDelegate(delegate)
        log_debug(f"CustomListWidget: Item delegate set to {delegate}") 

    def create_item(self, text, data, role=Qt.UserRole):
        item = QListWidgetItem(text)
        item.setData(role, data)
        # Встановлюємо мінімальний розмір для кожного елемента, щоб делегату було де малювати
        # Висота може залежати від шрифту, тут приклад
        # item.setSizeHint(QSize(100, 20)) # Мінімальна ширина 100, висота 20
        return item
    
    # sizeHint для самого CustomListWidget, якщо потрібно
    # def sizeHint(self):
    #     s = super().sizeHint()
    #     # Можна спробувати збільшити, якщо елементи невидимі
    #     # s.setHeight(max(s.height(), self.count() * 20)) 
    #     return s

    def show_context_menu(self, pos: QPoint):
        item = self.itemAt(pos)
        if not item:
            return
    
        block_idx = item.data(Qt.UserRole)
        main_window = self.window()
        block_name = item.text() 
        if hasattr(main_window, 'block_names'):
             block_name = main_window.block_names.get(str(block_idx), f"Block {block_idx}") 
    
        menu = QMenu(self)
        
        rename_action = menu.addAction(f"Rename '{block_name}'")
        if hasattr(main_window, 'list_selection_handler') and hasattr(main_window.list_selection_handler, 'rename_block'):
            rename_action.triggered.connect(lambda checked=False, item_to_rename=item: main_window.list_selection_handler.rename_block(item_to_rename))
        
        if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'rescan_issues_for_single_block'):
            rescan_action = menu.addAction(f"Rescan Issues in '{block_name}'")
            rescan_action.triggered.connect(lambda checked=False, idx=block_idx: main_window.app_action_handler.rescan_issues_for_single_block(idx))
            
        if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'calculate_widths_for_block_action'):
            calc_widths_action = menu.addAction(f"Calculate Line Widths for Block '{block_name}'")
            calc_widths_action.triggered.connect(lambda checked=False, idx=block_idx: main_window.app_action_handler.calculate_widths_for_block_action(idx))
        
        menu.exec_(self.mapToGlobal(pos))