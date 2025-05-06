from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QHBoxLayout, QTextEdit
from PyQt5.QtGui import QPainter, QColor, QFont, QTextBlockFormat, QTextFormat, QPen
from PyQt5.QtCore import Qt, QRect, QSize, QRectF # QRectF for floating point precision if needed
from utils import log_debug 

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor
        # Define background colors
        self.odd_line_background = QColor(Qt.lightGray).lighter(115) # Keep the light gray for odd lines
        self.even_line_background = QColor(Qt.white) # White for even lines
        self.number_color = QColor(Qt.black) # Text color for numbers

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

    def lineNumberAreaWidth(self):
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        space = 5 + self.fontMetrics().horizontalAdvance('9') * digits + 5 # Slightly more padding maybe
        return space

    def updateLineNumberAreaWidth(self, _=None):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        # This update on viewport containment can sometimes cause excessive repaints.
        # If performance issues arise, consider removing or optimizing this part.
        # if rect.contains(self.viewport().rect()):
        #     self.updateLineNumberAreaWidth()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        # No need to fill the entire background first, as each line will draw its own.
        # painter.fillRect(event.rect(), QColor(Qt.lightGray).lighter(110)) # Remove this generic fill

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        line_height = self.blockBoundingRect(block).height() # Get height directly from block rect
        area_width = self.lineNumberArea.width()
        right_margin = 3 

        # Ensure we paint the area below the last line if needed
        last_block_bottom = bottom 

        while block.isValid() and top <= event.rect().bottom():
            # Check if the block is within the vertical area that needs repainting
            if block.isVisible() and bottom >= event.rect().top():
                
                # --- BACKGROUND ALTERNATION ---
                line_rect = QRectF(0, top, area_width, line_height) # Use QRectF for precision
                if (blockNumber + 1) % 2 == 0: # Even line number
                    painter.fillRect(line_rect, self.lineNumberArea.even_line_background)
                else: # Odd line number
                    painter.fillRect(line_rect, self.lineNumberArea.odd_line_background)
                # --- END BACKGROUND ALTERNATION ---

                # --- DRAW LINE NUMBER ---
                number = str(blockNumber + 1)
                painter.setPen(self.lineNumberArea.number_color) # Use the defined number color (black)
                # Use fontMetrics().height() for drawing text, not blockBoundingRect height if variable line heights are possible
                font_height = self.fontMetrics().height() 
                painter.drawText(0, int(top), area_width - right_margin, int(font_height), Qt.AlignRight, number)
                # --- END DRAW LINE NUMBER ---

            block = block.next()
            if block.isValid():
                 block_rect = self.blockBoundingRect(block)
                 top = bottom
                 bottom = top + block_rect.height()
                 line_height = block_rect.height() # Update line_height in case it varies
                 last_block_bottom = bottom # Keep track of the bottom of the last processed block
            blockNumber += 1
            
        # Fill the remaining area below the last line (if any) within the event rect 
        # with the default odd color to avoid visual glitches when scrolling fast.
        remaining_rect = QRectF(0, last_block_bottom, area_width, event.rect().bottom() - last_block_bottom)
        if remaining_rect.height() > 0:
             painter.fillRect(remaining_rect, self.lineNumberArea.odd_line_background)


    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor("#E8F2FE") # A light blue often used for highlighting
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def setReadOnly(self, ro):
        super().setReadOnly(ro)
        self.highlightCurrentLine()