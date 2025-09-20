# --- START OF FILE ui/ui_event_filters.py ---
from PyQt5.QtCore import QObject, QEvent, Qt
from PyQt5.QtWidgets import QApplication, QWidget
from utils.logging_utils import log_debug

class TextEditEventFilter(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            is_ctrl_pressed = event.modifiers() & Qt.ControlModifier
            
            if obj is self.mw.preview_text_edit:
                if event.key() == Qt.Key_Up and not is_ctrl_pressed:
                    current_row = self.mw.current_string_idx
                    if current_row > 0:
                        self.mw.list_selection_handler.string_selected_from_preview(current_row - 1)
                    return True
                elif event.key() == Qt.Key_Down and not is_ctrl_pressed:
                    current_row = self.mw.current_string_idx
                    if self.mw.current_block_idx != -1 and current_row < len(self.mw.data[self.mw.current_block_idx]) - 1:
                        self.mw.list_selection_handler.string_selected_from_preview(current_row + 1)
                    return True

            if is_ctrl_pressed:
                if event.key() == Qt.Key_Up:
                    log_debug(f"TextEditEventFilter: Ctrl+Up captured on {obj.objectName()}. Calling navigation.")
                    if hasattr(self.mw, 'list_selection_handler'):
                        self.mw.list_selection_handler.navigate_to_problem_string(direction_down=False)
                    return True
                elif event.key() == Qt.Key_Down:
                    log_debug(f"TextEditEventFilter: Ctrl+Down captured on {obj.objectName()}. Calling navigation.")
                    if hasattr(self.mw, 'list_selection_handler'):
                        self.mw.list_selection_handler.navigate_to_problem_string(direction_down=True)
                    return True
                    
        return super().eventFilter(obj, event)

class MainWindowEventFilter(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_F3:
                if event.modifiers() & Qt.ShiftModifier:
                    log_debug("EventFilter: Shift+F3 pressed - Find Previous")
                    self.mw.execute_find_previous_shortcut()
                    return True 
                else:
                    log_debug("EventFilter: F3 pressed - Find Next")
                    self.mw.execute_find_next_shortcut()
                    return True
            
        return super().eventFilter(obj, event)