from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QHBoxLayout, QTextEdit, QStyle
from PyQt5.QtGui import QPainter, QColor, QFont, QTextBlockFormat, QTextFormat, QPen, QMouseEvent
from PyQt5.QtCore import Qt, QRect, QSize, QRectF, pyqtSignal 
from utils import log_debug 
from syntax_highlighter import JsonTagHighlighter # Ensure this import is correct

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor
        self.odd_line_background = QColor(Qt.lightGray).lighter(115) 
        self.even_line_background = QColor(Qt.white) 
        self.number_color = QColor(Qt.darkGray) 

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)


class LineNumberedTextEdit(QPlainTextEdit):
    lineClicked = pyqtSignal(int) 

    def __init__(self, parent=None): 
        super().__init__(parent)
        # self.main_window_instance = parent if hasattr(parent, 'settings_file_path') else None 
        # main_window_instance is not directly needed here anymore if reconfigure is done by MainWindow

        self.lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        
        self.updateLineNumberAreaWidth(0)
        
        font = QFont("Courier New", 10) 
        self.setFont(font)

        # Instantiate the highlighter. MainWindow will configure it.
        self.highlighter = JsonTagHighlighter(self.document())
        log_debug(f"Applied JsonTagHighlighter to LineNumberedTextEdit instance: {self}")
        
        self.ensurePolished() 
        self.current_line_color = QColor("#E8F2FE") 
        log_debug(f"Set current_line_color for editable fields to: {self.current_line_color.name()}")


    def lineNumberAreaWidth(self):
        digits = 1
        max_val = max(1, self.blockCount())
        while max_val >= 10:
            max_val //= 10
            digits += 1
        # Add a bit more space for padding if numbers are close to edge
        space = self.fontMetrics().horizontalAdvance('9') * (digits + 1) + 6 
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            # Update the whole visible area of the line number bar for simplicity
            self.lineNumberArea.update(0, 0, self.lineNumberArea.width(), self.lineNumberArea.height())
            # self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height()) # Original
        if rect.contains(self.viewport().rect()): # If the whole viewport is affected
            self.updateLineNumberAreaWidth(0)     # Recalculate width

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))
    
    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event) 
        if event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            line_no = cursor.blockNumber() 
            self.lineClicked.emit(line_no)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        
        base_bg_color = self.palette().base().color()
        if self.isReadOnly():
             base_bg_color = self.palette().window().color().lighter(105) 
        painter.fillRect(event.rect(), base_bg_color)

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        # Align top with the block's bounding geometry top
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        
        current_text_cursor_block_number = self.textCursor().blockNumber()
        
        current_line_number_highlight_bg = self.current_line_color 
        current_line_number_highlight_text = self.palette().text().color() 
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                
                # Rectangle for the current line number's background and text
                line_num_rect = QRect(0, top, self.lineNumberArea.width(), int(self.blockBoundingRect(block).height()))

                if not self.isReadOnly() and blockNumber == current_text_cursor_block_number:
                     painter.fillRect(line_num_rect, current_line_number_highlight_bg)
                     painter.setPen(current_line_number_highlight_text) 
                elif (blockNumber + 1) % 2 == 0: 
                    # For even lines, if base_bg_color is already "even" color, no need to fill again
                    # painter.fillRect(line_num_rect, self.lineNumberArea.even_line_background) 
                    painter.setPen(self.lineNumberArea.number_color)
                else: 
                    painter.fillRect(line_num_rect, self.lineNumberArea.odd_line_background)
                    painter.setPen(self.lineNumberArea.number_color)
                
                # Draw text centered vertically within the line_num_rect height
                painter.drawText(line_num_rect, Qt.AlignRight | Qt.AlignVCenter, number + " ") # Add a little padding from right edge
            
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly(): 
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(self.current_line_color) 
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def setReadOnly(self, ro):
        super().setReadOnly(ro)
        self.highlightCurrentLine() 
        self.lineNumberArea.update() 

    # The reconfigure_highlighter_styles method is removed from here.
    # MainWindow now directly accesses self.highlighter.reconfigure_styles()
    # and self.highlighter.rehighlight().