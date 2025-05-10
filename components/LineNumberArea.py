from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QRect, QSize

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor 
        
        self.odd_line_background = QColor(Qt.lightGray).lighter(115) 
        self.even_line_background = QColor(Qt.white) 
        self.number_color = QColor(Qt.darkGray) # Використовується, якщо не чорний
        
        self.active_number_color = QColor(Qt.white) # Не використовується, якщо текст завжди чорний
        self.active_number_background_color = QColor(0, 0, 128) # Використовується для фону активного рядка, якщо ввімкнено

        self.width_indicator_exceeded_color = QColor(Qt.red).lighter(130) 

        self.preview_critical_indicator_color = QColor(Qt.yellow).darker(125)
        self.preview_warning_indicator_color = QColor(Qt.darkGray)
        self.preview_width_exceeded_indicator_color = QColor(255, 120, 120) 
        self.preview_indicator_width = 5 # Ширина смужки індикатора для preview
        self.preview_indicator_spacing = 2

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event, painter_device=self)