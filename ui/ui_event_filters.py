from PyQt5.QtCore import QObject, QEvent, Qt
from PyQt5.QtWidgets import QApplication
from utils import log_debug

class MainWindowEventFilter(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            focused_widget = QApplication.focusWidget()
            
            is_ctrl_pressed = event.modifiers() & Qt.ControlModifier

            if event.key() == Qt.Key_F3:
                if event.modifiers() & Qt.ShiftModifier:
                    log_debug("EventFilter: Shift+F3 pressed - Find Previous")
                    self.mw.execute_find_previous_shortcut()
                    return True 
                else:
                    log_debug("EventFilter: F3 pressed - Find Next")
                    self.mw.execute_find_next_shortcut()
                    return True
            elif is_ctrl_pressed and event.key() == Qt.Key_Up:
                log_debug(f"EventFilter: Ctrl+Up pressed. Focused: {focused_widget.objectName() if focused_widget else 'None'}. Calling navigate_to_problem_string(direction_down=False)")
                if hasattr(self.mw, 'list_selection_handler'):
                    self.mw.list_selection_handler.navigate_to_problem_string(direction_down=False)
                return True 
            elif is_ctrl_pressed and event.key() == Qt.Key_Down:
                log_debug(f"EventFilter: Ctrl+Down pressed. Focused: {focused_widget.objectName() if focused_widget else 'None'}. Calling navigate_to_problem_string(direction_down=True)")
                if hasattr(self.mw, 'list_selection_handler'):
                    self.mw.list_selection_handler.navigate_to_problem_string(direction_down=True)
                return True 
            
        return super().eventFilter(obj, event)