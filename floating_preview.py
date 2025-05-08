# Додаємо QApplication до імпортів
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication 
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, pyqtSignal

from LineNumberedTextEdit import LineNumberedTextEdit
from utils import remove_all_tags, convert_spaces_to_dots_for_display

class FloatingPreviewWindow(QWidget):
    windowClosed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.WindowTitleHint | Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Tagless Preview")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5) 

        self.preview_edit = LineNumberedTextEdit(self)
        self.preview_edit.setObjectName("FloatingTaglessPreviewEdit")
        self.preview_edit.setReadOnly(True)
        preview_palette = self.preview_edit.palette()
        preview_palette.setColor(preview_palette.Base, QColor("#E0E0E0")) 
        self.preview_edit.setPalette(preview_palette)
        self.preview_edit.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        layout.addWidget(self.preview_edit)

        self.resize(300, 400) 

        self._show_dots = True
        self._newline_symbol = "↵"


    def updateContent(self, original_text_with_tags: str, show_dots: bool, newline_symbol: str):
        self._show_dots = show_dots
        self._newline_symbol = newline_symbol
        
        text_without_tags = remove_all_tags(str(original_text_with_tags))
        text_for_display = convert_spaces_to_dots_for_display(text_without_tags, self._show_dots)
        text_for_display = text_for_display.replace('\n', self._newline_symbol)
        
        scrollbar_value = self.preview_edit.verticalScrollBar().value()
        current_text = self.preview_edit.toPlainText()
        
        if current_text != text_for_display:
             main_window = self.parent() 
             was_changing = False
             if main_window and hasattr(main_window, 'is_programmatically_changing_text'):
                 was_changing = main_window.is_programmatically_changing_text
                 main_window.is_programmatically_changing_text = True

             self.preview_edit.setPlainText(text_for_display)
             
             if main_window and hasattr(main_window, 'is_programmatically_changing_text'):
                  main_window.is_programmatically_changing_text = was_changing 

        self.preview_edit.verticalScrollBar().setValue(scrollbar_value)

    def updateLineHighlight(self, line_number: int):
         if hasattr(self.preview_edit, 'highlightManager'):
              self.preview_edit.highlightManager.setLinkedCursorPosition(line_number, -1)

    def closeEvent(self, event):
        self.windowClosed.emit() 
        # Ховаємо вікно замість закриття, щоб його можна було показати знову
        event.ignore() 
        self.hide()


    def showEvent(self, event):
        super().showEvent(event)
        # Перевіряємо, чи є батьківське вікно перед доступом до desktop
        if self.parent():
            main_geo = self.parent().geometry()
            my_geo = self.geometry()
            # Використовуємо екран, на якому знаходиться головне вікно
            screen = QApplication.screenAt(self.parent().pos()) 
            if not screen: # Якщо раптом не вдалося визначити екран
                 screen_geo = QApplication.desktop().availableGeometry(self)
            else:
                 screen_geo = screen.availableGeometry()

            new_x = main_geo.x() + main_geo.width()
            if new_x + my_geo.width() > screen_geo.x() + screen_geo.width():
                 new_x = main_geo.x() - my_geo.width()
                 if new_x < screen_geo.x(): 
                      new_x = screen_geo.x() + screen_geo.width() - my_geo.width()

            new_y = main_geo.y() 
            if new_y < screen_geo.y(): new_y = screen_geo.y()
            if new_y + my_geo.height() > screen_geo.y() + screen_geo.height():
                  new_y = screen_geo.y() + screen_geo.height() - my_geo.height()

            self.move(new_x, new_y)