# LineNumberArea.py
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QRect, QSize

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        # Зберігаємо посилання на редактор, якому належить ця область
        self.codeEditor = editor 
        
        # Стандартні кольори області нумерації
        self.odd_line_background = QColor(Qt.lightGray).lighter(115) 
        self.even_line_background = QColor(Qt.white) # Часто збігається з базовим фоном
        self.number_color = QColor(Qt.darkGray) 
        
        # Кольори для підсвічування активного рядка в зоні нумерації
        self.active_number_color = QColor(Qt.white) 
        self.active_number_background_color = QColor(0, 0, 128) # Navy

    def sizeHint(self):
        # Розрахунок ширини делегуємо редактору
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        # Малювання також делегуємо редактору, передаючи себе як QPainter device
        self.codeEditor.lineNumberAreaPaintEvent(event, painter_device=self) 