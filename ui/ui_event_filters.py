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
            # Закоментуємо частину логування, щоб зменшити шум, але залишимо ключові моменти
            # log_debug(f"EventFilter KeyPress: Key {event.key()}, Modifiers: {event.modifiers()}, Text: '{event.text()}', Focused widget: {focused_widget.objectName() if focused_widget else 'None'}")

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
                log_debug("EventFilter: Ctrl+Up pressed - Navigate to previous problem string")
                if hasattr(self.mw, 'list_selection_handler'):
                    self.mw.list_selection_handler.navigate_to_problem_string(direction_down=False)
                return True # Перехоплюємо і обробляємо тільки Ctrl+Up
            elif is_ctrl_pressed and event.key() == Qt.Key_Down:
                log_debug("EventFilter: Ctrl+Down pressed - Navigate to next problem string")
                if hasattr(self.mw, 'list_selection_handler'):
                    self.mw.list_selection_handler.navigate_to_problem_string(direction_down=True)
                return True # Перехоплюємо і обробляємо тільки Ctrl+Down
            
        # Для всіх інших подій, включаючи KeyPress, які не були оброблені вище,
        # передаємо їх далі по ланцюжку.
        return super().eventFilter(obj, event)