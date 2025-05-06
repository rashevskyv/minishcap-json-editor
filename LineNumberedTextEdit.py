from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QHBoxLayout, QTextEdit, QStyle
from PyQt5.QtGui import (QPainter, QColor, QFont, QTextBlockFormat, 
                         QTextFormat, QPen, QMouseEvent, QTextCursor, 
                         QTextCharFormat) # <--- ДОДАНО QTextCharFormat СЮДИ
from PyQt5.QtCore import Qt, QRect, QSize, QRectF, pyqtSignal 
from utils import log_debug 
from syntax_highlighter import JsonTagHighlighter 

class LineNumberArea(QWidget):
    # ... (код без змін) ...
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
        self.lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        
        self.updateLineNumberAreaWidth(0)
        
        font = QFont("Courier New", 10) 
        self.setFont(font)

        self.highlighter = JsonTagHighlighter(self.document())
        
        self.ensurePolished() 
        self.current_line_color = QColor("#E8F2FE") 
        self.linked_cursor_block_color = QColor("#F5F5F5") 
        self.linked_cursor_pos_color = QColor(Qt.darkGray) 
        # Альтернативний колір для позиції курсору, якщо darkGray занадто темний:
        # self.linked_cursor_pos_color = QColor(Qt.blue).lighter(160) 


        self._active_line_selections = [] 
        self._linked_cursor_selections = [] 

    def _apply_all_extra_selections(self):
        all_selections = []
        if self._linked_cursor_selections: 
            all_selections.extend(self._linked_cursor_selections)
        if self._active_line_selections: 
            all_selections.extend(self._active_line_selections)
        super().setExtraSelections(all_selections)


    def highlightCurrentLine(self):
        self._active_line_selections = [] 
        if not self.isReadOnly(): 
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(self.current_line_color) 
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            self._active_line_selections.append(selection)
        self._apply_all_extra_selections()

    def setLinkedCursorPosition(self, line_number: int, column_number: int):
        self._linked_cursor_selections = [] 
        doc = self.document()

        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                line_selection = QTextEdit.ExtraSelection()
                line_selection.format.setBackground(self.linked_cursor_block_color)
                line_selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                line_selection.cursor = QTextCursor(block)
                self._linked_cursor_selections.append(line_selection)

                line_text_length = len(block.text()) 
                actual_column = min(column_number, line_text_length)

                cursor_pos_selection = QTextEdit.ExtraSelection()
                
                cursor_for_pos = QTextCursor(block)
                cursor_for_pos.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, actual_column)
                
                # Тут створюється QTextCharFormat, тому він має бути імпортований
                pos_format = QTextCharFormat() 
                pos_format.setBackground(self.linked_cursor_pos_color) 
                
                cursor_pos_selection.format = pos_format
                cursor_pos_selection.cursor = cursor_for_pos 
                
                temp_cursor_for_highlight = QTextCursor(cursor_for_pos)
                
                if actual_column < line_text_length: 
                    temp_cursor_for_highlight.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
                    cursor_pos_selection.cursor = temp_cursor_for_highlight 
                    self._linked_cursor_selections.append(cursor_pos_selection)
                elif actual_column == line_text_length and line_text_length > 0 : # Курсор в кінці не порожнього рядка
                    # Для імітації курсору в кінці рядка, виділяємо попередній символ
                    # або можна спробувати інший підхід (наприклад, вертикальна лінія, якщо можливо)
                    # Поки що, для простоти, виділимо останній символ, якщо він є
                    # Або можна намалювати вузький прямокутник на позиції курсора (складніше)
                    # Спробуємо встановити курсор для ExtraSelection на позицію *після* символу,
                    # але з форматом, що імітує вертикальну лінію (не стандартно)
                    # або просто виділимо попередній символ, якщо це краще
                    prev_char_cursor = QTextCursor(cursor_for_pos)
                    if prev_char_cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, 1):
                        cursor_pos_selection.cursor = prev_char_cursor
                        self._linked_cursor_selections.append(cursor_pos_selection)

        self._apply_all_extra_selections()


    def setReadOnly(self, ro):
        super().setReadOnly(ro)
        self.highlightCurrentLine() 
        if ro: 
            self._active_line_selections = []
            self._apply_all_extra_selections()
        self.lineNumberArea.update()

    # ... (решта методів без змін) ...
    def lineNumberAreaWidth(self):
        digits = 1; max_val = max(1, self.blockCount())
        while max_val >= 10: max_val //= 10; digits += 1
        space = self.fontMetrics().horizontalAdvance('9') * (digits + 1) + 6 
        return space
    def updateLineNumberAreaWidth(self, _): self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)
    def updateLineNumberArea(self, rect, dy):
        if dy: self.lineNumberArea.scroll(0, dy)
        else: self.lineNumberArea.update(0, 0, self.lineNumberArea.width(), self.lineNumberArea.height())
        if rect.contains(self.viewport().rect()): self.updateLineNumberAreaWidth(0)    
    def resizeEvent(self, event):
        super().resizeEvent(event); cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))
    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event) 
        if event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos()); line_no = cursor.blockNumber() 
            self.lineClicked.emit(line_no)
    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        base_bg_color = self.palette().base().color()
        if self.isReadOnly(): base_bg_color = self.palette().window().color().lighter(105) 
        painter.fillRect(event.rect(), base_bg_color)
        block = self.firstVisibleBlock(); blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        current_text_cursor_block_number = self.textCursor().blockNumber()
        current_line_number_highlight_bg = self.current_line_color 
        current_line_number_highlight_text = self.palette().text().color() 
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                line_num_rect = QRect(0, top, self.lineNumberArea.width(), int(self.blockBoundingRect(block).height()))
                if not self.isReadOnly() and blockNumber == current_text_cursor_block_number:
                     painter.fillRect(line_num_rect, current_line_number_highlight_bg)
                     painter.setPen(current_line_number_highlight_text) 
                elif (blockNumber + 1) % 2 == 0: painter.setPen(self.lineNumberArea.number_color)
                else: 
                    painter.fillRect(line_num_rect, self.lineNumberArea.odd_line_background)
                    painter.setPen(self.lineNumberArea.number_color)
                painter.drawText(line_num_rect, Qt.AlignRight | Qt.AlignVCenter, number + " ") 
            block = block.next(); top = bottom
            bottom = top + int(self.blockBoundingRect(block).height()); blockNumber += 1