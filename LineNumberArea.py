# LineNumberArea.py
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QRect, QSize

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor 
        
        self.odd_line_background = QColor(Qt.lightGray).lighter(115) 
        self.even_line_background = QColor(Qt.white) 
        self.number_color = QColor(Qt.darkGray) 
        
        self.active_number_color = QColor(Qt.white) 
        self.active_number_background_color = QColor(0, 0, 128) # Navy

        self.width_indicator_normal_color = QColor(Qt.green).lighter(130)
        self.width_indicator_warning_color = QColor(Qt.yellow).lighter(130)
        self.width_indicator_exceeded_color = QColor(Qt.red).lighter(130)
        self.width_indicator_bar_width = 4 # pixels

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event, painter_device=self)