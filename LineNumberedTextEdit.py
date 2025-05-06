from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QHBoxLayout, QTextEdit, QStyle, QApplication, QMainWindow
from PyQt5.QtGui import (QPainter, QColor, QFont, QTextBlockFormat, 
                         QTextFormat, QPen, QMouseEvent, QTextCursor, 
                         QTextCharFormat)
from PyQt5.QtCore import Qt, QRect, QSize, QRectF, pyqtSignal, QTimer 
from utils import log_debug 
from syntax_highlighter import JsonTagHighlighter 
import re 
from typing import Optional, Tuple 

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
        self.widget_id = str(id(self))[-6:] 
        log_debug(f"LNET ({self.widget_id}): __init__")
        self.lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        
        self.updateLineNumberAreaWidth(0)
        
        font = QFont("Courier New", 10) 
        self.setFont(font)

        self.highlighter = JsonTagHighlighter(self.document())
        
        self.ensurePolished() 
        self.current_line_color = QColor("#E8F2FE") # Для editable поля (активний рядок курсору)
        self.linked_cursor_block_color = QColor("#F5F5F5") # Для рядка зв'язаного курсору в original
        self.linked_cursor_pos_color = QColor(Qt.blue).lighter(160) # Для позиції зв'язаного курсору
        self.problem_line_color = QColor(Qt.yellow).lighter(130) # Жовтий для проблемних рядків
        self.preview_selected_line_color = QColor("#DDEEFF") # Для вибраного рядка в preview
        self.tag_interaction_highlight_color = QColor(Qt.green).lighter(150)

        self._active_line_selections = [] 
        self._linked_cursor_selections = []
        self._problem_line_selections = [] 
        self._preview_selected_line_selections = []
        self._tag_interaction_selections = []
        
        log_debug(f"LNET ({self.widget_id}): Initialized selection lists")

    def _create_block_background_selection(self, block: QTextBlockFormat, color: QColor) -> Optional[QTextEdit.ExtraSelection]:
        """Створює ExtraSelection для підсвічування фону всього текстового блоку."""
        if not block.isValid():
            return None
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(color)
        # selection.format.setProperty(QTextFormat.FullWidthSelection, True) # Прибираємо це
        
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.BlockUnderCursor) # Виділяємо весь текст блоку
        selection.cursor = cursor
        return selection

    def _apply_all_extra_selections(self):
        # ... (код без змін) ...
        all_selections = []
        if self._active_line_selections: all_selections.extend(list(self._active_line_selections))
        if self._linked_cursor_selections: all_selections.extend(list(self._linked_cursor_selections))
        if self._preview_selected_line_selections: all_selections.extend(list(self._preview_selected_line_selections))
        if self._problem_line_selections: all_selections.extend(list(self._problem_line_selections))
        if self._tag_interaction_selections: all_selections.extend(list(self._tag_interaction_selections))
        problem_lines_debug = [s.cursor.blockNumber() for s in self._problem_line_selections]
        super().setExtraSelections(all_selections)


    def highlightCurrentLine(self): # Це для активного рядка в editable, тут FullWidthSelection може бути доречним
        new_selections = [] 
        if not self.isReadOnly(): 
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(self.current_line_color) 
            selection.format.setProperty(QTextFormat.FullWidthSelection, True) # Залишаємо для активного рядка
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            new_selections.append(selection)
        if self._active_line_selections != new_selections:
            self._active_line_selections = new_selections
            self._apply_all_extra_selections()

    def setLinkedCursorPosition(self, line_number: int, column_number: int):
        new_linked_selections = [] 
        doc = self.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                # Підсвічування всього блоку (рядка)
                line_sel = self._create_block_background_selection(block, self.linked_cursor_block_color)
                if line_sel:
                    new_linked_selections.append(line_sel)

                # Імітація позиції курсору
                line_text_length = len(block.text()); actual_column = min(column_number, line_text_length)
                pos_sel_obj = QTextEdit.ExtraSelection()
                cursor_for_pos = QTextCursor(block)
                cursor_for_pos.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, actual_column)
                
                pos_format = QTextCharFormat()
                pos_format.setBackground(self.linked_cursor_pos_color) 
                # Можна додати ще якийсь ефект, наприклад, жирний шрифт для імітації курсору
                # pos_format.setFontWeight(QFont.Bold)

                pos_sel_obj.format = pos_format
                
                temp_cursor_highlight = QTextCursor(cursor_for_pos)
                if actual_column < line_text_length: 
                    temp_cursor_highlight.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
                # Якщо курсор в кінці рядка, виділення 0 довжини, але з форматом
                # (деякі системи можуть не показувати фон для 0-довжини)
                # Альтернатива: виділяти попередній символ або спеціальний маркер
                # Для простоти, якщо в кінці, то cursor не KeepAnchor, а просто встановлюється на позицію.
                # І застосовуємо формат до цієї позиції (може не спрацювати для фону без виділення).
                # Спробуємо все ж виділяти 1 символ, якщо це не кінець тексту.
                # Якщо це кінець рядка, то виділення попереднього символу (як було) може бути кращим.
                elif actual_column == line_text_length and line_text_length > 0 : 
                    if temp_cursor_highlight.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1):
                         temp_cursor_highlight.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
                
                pos_sel_obj.cursor = temp_cursor_highlight
                if temp_cursor_highlight.hasSelection(): # Додаємо, тільки якщо щось виділено
                    new_linked_selections.append(pos_sel_obj)
        
        if self._linked_cursor_selections != new_linked_selections:
            self._linked_cursor_selections = new_linked_selections
            self._apply_all_extra_selections()


    def setPreviewSelectedLineHighlight(self, line_number: int):
        new_selections = []
        doc = self.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            selection = self._create_block_background_selection(block, self.preview_selected_line_color)
            if selection:
                new_selections.append(selection)
        
        if self._preview_selected_line_selections != new_selections:
            self._preview_selected_line_selections = new_selections
            self._apply_all_extra_selections()

    def clearPreviewSelectedLineHighlight(self):
        if self._preview_selected_line_selections:
            self._preview_selected_line_selections = []
            self._apply_all_extra_selections()
            
    def addProblemLineHighlight(self, line_number: int):
        doc = self.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                is_already_added = any(s.cursor.blockNumber() == line_number for s in self._problem_line_selections)
                if not is_already_added:
                    selection = self._create_block_background_selection(block, self.problem_line_color)
                    if selection:
                        self._problem_line_selections.append(selection)
                        log_debug(f"LNET ({self.widget_id}): Queued problem highlight for line {line_number}. Total problems: {len(self._problem_line_selections)}")

    def applyQueuedProblemHighlights(self): # Застосовує всі накопичені, включаючи проблемні
        log_debug(f"LNET ({self.widget_id}): applyQueuedProblemHighlights - applying/refreshing. Problems in queue: {len(self._problem_line_selections)}")
        self._apply_all_extra_selections()

    def clearProblemLineHighlights(self):
        if self._problem_line_selections:
            log_debug(f"LNET ({self.widget_id}): clearProblemLineHighlights. Had {len(self._problem_line_selections)} problems.")
        self._problem_line_selections = []
        self._apply_all_extra_selections()

    def hasProblemHighlight(self, line_number: Optional[int] = None) -> bool:
        # ... (код без змін) ...
        if line_number is not None: return any(s.cursor.blockNumber() == line_number for s in self._problem_line_selections)
        return bool(self._problem_line_selections)

    def setReadOnly(self, ro):
        super().setReadOnly(ro); self.highlightCurrentLine() 
        if ro: self._active_line_selections = []; self._apply_all_extra_selections()
        self.lineNumberArea.update()

    def lineNumberAreaWidth(self):
        digits = 1; max_val = max(1, self.blockCount())
        while max_val >= 10: max_val //= 10; digits += 1
        space = self.fontMetrics().horizontalAdvance('9') * (digits + 1) + 6 
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect: QRectF, dy: int):
        if dy: self.lineNumberArea.scroll(0, dy)
        else: self.lineNumberArea.update(0, 0, self.lineNumberArea.width(), self.lineNumberArea.height())
        if rect.contains(self.viewport().rect()): self.updateLineNumberAreaWidth(0)    

    def resizeEvent(self, event): 
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))
    
    def mousePressEvent(self, event: QMouseEvent): 
        super().mousePressEvent(event) 
        if event.button() == Qt.LeftButton:
            cursor_for_line_click = self.cursorForPosition(event.pos())
            line_no = cursor_for_line_click.blockNumber() 
            self.lineClicked.emit(line_no)

    def lineNumberAreaPaintEvent(self, event): 
        painter = QPainter(self.lineNumberArea); base_bg_color = self.palette().base().color()
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
                     painter.fillRect(line_num_rect, current_line_number_highlight_bg); painter.setPen(current_line_number_highlight_text) 
                elif (blockNumber + 1) % 2 == 0: painter.setPen(self.lineNumberArea.number_color)
                else: painter.fillRect(line_num_rect, self.lineNumberArea.odd_line_background); painter.setPen(self.lineNumberArea.number_color)
                painter.drawText(line_num_rect, Qt.AlignRight | Qt.AlignVCenter, number + " ") 
            block = block.next(); top = bottom
            bottom = top + int(self.blockBoundingRect(block).height()); blockNumber += 1