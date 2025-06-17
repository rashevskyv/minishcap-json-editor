from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QMenu, QAction
from PyQt5.QtCore import Qt, QPoint, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from utils.logging_utils import log_debug
from .CustomListItemDelegate import CustomListItemDelegate

class CustomListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        log_debug(f"CustomListWidget INITIALIZED, parent: {parent}") 
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        self.setUniformItemSizes(False) 
        
        delegate = CustomListItemDelegate(self)
        self.setItemDelegate(delegate)
        log_debug(f"CustomListWidget: Item delegate set to {delegate}") 

        self.color_marker_definitions = {
            "red": QColor(Qt.red),
            "green": QColor(Qt.green),
            "blue": QColor(Qt.blue),
            # Можна додати більше кольорів тут
        }

    def _create_color_icon(self, color: QColor, size: int = 12) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen) 
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return QIcon(pixmap)

    def create_item(self, text, data, role=Qt.UserRole):
        item = QListWidgetItem(text)
        item.setData(role, data)
        return item
    
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
        
        menu.addSeparator()

        current_markers = main_window.get_block_color_markers(block_idx)
        for color_name, q_color in self.color_marker_definitions.items():
            action = QAction(self._create_color_icon(q_color), f"Mark {color_name.capitalize()}", menu)
            action.setCheckable(True)
            action.setChecked(color_name in current_markers)
            action.triggered.connect(lambda checked, b_idx=block_idx, c_name=color_name: main_window.toggle_block_color_marker(b_idx, c_name))
            menu.addAction(action)
        
        menu.addSeparator()

        if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'rescan_issues_for_single_block'):
            rescan_action = menu.addAction(f"Rescan Issues in '{block_name}'")
            rescan_action.triggered.connect(lambda checked=False, idx=block_idx: main_window.app_action_handler.rescan_issues_for_single_block(idx))
            
        if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'calculate_widths_for_block_action'):
            calc_widths_action = menu.addAction(f"Calculate Line Widths for Block '{block_name}'")
            calc_widths_action.triggered.connect(lambda checked=False, idx=block_idx: main_window.app_action_handler.calculate_widths_for_block_action(idx))
        
        menu.exec_(self.mapToGlobal(pos))