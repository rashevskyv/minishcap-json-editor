from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QHBoxLayout, QTextEdit
from PyQt5.QtGui import QPainter, QColor, QFont, QTextBlockFormat, QTextFormat, QPen
from PyQt5.QtCore import Qt, QRect, QSize, QRectF 
from utils import log_debug 
from syntax_highlighter import JsonTagHighlighter # <<< IMPORT

class LineNumberArea(QWidget):
    # ... (LineNumberArea class remains the same) ...
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor
        self.odd_line_background = QColor(Qt.lightGray).lighter(115) 
        self.even_line_background = QColor(Qt.white) 
        self.number_color = QColor(Qt.black) 

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)


class LineNumberedTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        font = QFont("Courier New", 10)
        self.setFont(font)
        self.lineNumberArea.setFont(font)

        # --- APPLY SYNTAX HIGHLIGHTER ---
        self.highlighter = JsonTagHighlighter(self.document())
        log_debug("Applied JsonTagHighlighter to LineNumberedTextEdit.")
        # --- END APPLY SYNTAX HIGHLIGHTER ---

    # ... (rest of LineNumberedTextEdit methods remain the same) ...
    def lineNumberAreaWidth(self):
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10: max_num //= 10; digits += 1
        space = 5 + self.fontMetrics().horizontalAdvance('9') * digits + 5
        return space

    def updateLineNumberAreaWidth(self, _=None): 
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy: self.lineNumberArea.scroll(0, dy)
        else: self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        # if rect.contains(self.viewport().rect()): self.updateLineNumberAreaWidth() # Optional

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        line_height = self.blockBoundingRect(block).height() 
        area_width = self.lineNumberArea.width()
        right_margin = 3 
        last_block_bottom = bottom 

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                line_rect = QRectF(0, top, area_width, line_height)
                if (blockNumber + 1) % 2 == 0: painter.fillRect(line_rect, self.lineNumberArea.even_line_background)
                else: painter.fillRect(line_rect, self.lineNumberArea.odd_line_background)
                number = str(blockNumber + 1)
                painter.setPen(self.lineNumberArea.number_color) 
                font_height = self.fontMetrics().height() 
                painter.drawText(0, int(top), area_width - right_margin, int(font_height), Qt.AlignRight, number)
            block = block.next()
            if block.isValid():
                 block_rect = self.blockBoundingRect(block)
                 top = bottom; bottom = top + block_rect.height(); line_height = block_rect.height()
                 last_block_bottom = bottom 
            blockNumber += 1
            
        remaining_rect = QRectF(0, last_block_bottom, area_width, event.rect().bottom() - last_block_bottom)
        if remaining_rect.height() > 0: painter.fillRect(remaining_rect, self.lineNumberArea.odd_line_background)

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor("#E8F2FE") 
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def setReadOnly(self, ro):
        super().setReadOnly(ro)
        self.highlightCurrentLine()