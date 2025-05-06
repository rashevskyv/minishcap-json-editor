from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QHBoxLayout, QTextEdit, QStyle
from PyQt5.QtGui import (QPainter, QColor, QFont, QTextBlockFormat, 
                         QTextFormat, QPen, QMouseEvent, QTextCursor, 
                         QTextCharFormat)
from PyQt5.QtCore import Qt, QRect, QSize, QRectF, pyqtSignal 
from utils import log_debug 
from syntax_highlighter import JsonTagHighlighter 

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
        self.widget_id = str(id(self))[-6:] # Для ідентифікації в логах
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
        self.current_line_color = QColor("#E8F2FE") 
        self.linked_cursor_block_color = QColor("#F5F5F5") 
        self.linked_cursor_pos_color = QColor(Qt.blue).lighter(160) 
        self.problem_line_color = QColor(Qt.yellow).lighter(130) 
        self.preview_selected_line_color = QColor("#DDEEFF") 

        self._active_line_selections = [] 
        self._linked_cursor_selections = []
        self._problem_line_selections = [] 
        self._preview_selected_line_selections = [] 
        log_debug(f"LNET ({self.widget_id}): Initialized selection lists: "
                  f"active={len(self._active_line_selections)}, "
                  f"linked={len(self._linked_cursor_selections)}, "
                  f"preview_sel={len(self._preview_selected_line_selections)}, "
                  f"problem={len(self._problem_line_selections)}")


    def _apply_all_extra_selections(self):
        all_selections = []
        if self._active_line_selections: 
            all_selections.extend(list(self._active_line_selections))
        if self._linked_cursor_selections: 
            all_selections.extend(list(self._linked_cursor_selections))
        if self._preview_selected_line_selections: 
            all_selections.extend(list(self._preview_selected_line_selections))
        if self._problem_line_selections: 
            all_selections.extend(list(self._problem_line_selections))
        
        problem_lines = [s.cursor.blockNumber() for s in self._problem_line_selections]
        log_debug(f"LNET ({self.widget_id}): _apply_all_extra_selections. "
                  f"Total: {len(all_selections)}. "
                  f"Active: {len(self._active_line_selections)}, "
                  f"Linked: {len(self._linked_cursor_selections)}, "
                  f"PreviewSel: {len(self._preview_selected_line_selections)}, "
                  f"Problem: {len(self._problem_line_selections)} (lines: {problem_lines})")
        super().setExtraSelections(all_selections)

    def highlightCurrentLine(self):
        # ... (код методу) ...
        new_selections = [] 
        if not self.isReadOnly(): 
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(self.current_line_color) 
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            new_selections.append(selection)
        if self._active_line_selections != new_selections:
            log_debug(f"LNET ({self.widget_id}): highlightCurrentLine - updating active line.")
            self._active_line_selections = new_selections
            self._apply_all_extra_selections()

    def setLinkedCursorPosition(self, line_number: int, column_number: int):
        # ... (код методу) ...
        new_selections = [] 
        doc = self.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                line_sel = QTextEdit.ExtraSelection()
                line_sel.format.setBackground(self.linked_cursor_block_color)
                line_sel.format.setProperty(QTextFormat.FullWidthSelection, True)
                line_sel.cursor = QTextCursor(block)
                new_selections.append(line_sel)
                line_text_length = len(block.text()); actual_column = min(column_number, line_text_length)
                pos_sel = QTextEdit.ExtraSelection()
                cursor_for_pos = QTextCursor(block)
                cursor_for_pos.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, actual_column)
                pos_format = QTextCharFormat(); pos_format.setBackground(self.linked_cursor_pos_color) 
                pos_sel.format = pos_format
                temp_cursor_highlight = QTextCursor(cursor_for_pos)
                if actual_column < line_text_length: 
                    temp_cursor_highlight.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
                    pos_sel.cursor = temp_cursor_highlight 
                    new_selections.append(pos_sel)
                elif actual_column == line_text_length and line_text_length > 0 : 
                    prev_char_cursor = QTextCursor(cursor_for_pos)
                    if prev_char_cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1):
                         prev_char_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1) 
                         pos_sel.cursor = prev_char_cursor
                         new_selections.append(pos_sel)
        if self._linked_cursor_selections != new_selections:
            log_debug(f"LNET ({self.widget_id}): setLinkedCursorPosition - updating to line {line_number}, col {column_number}.")
            self._linked_cursor_selections = new_selections
            self._apply_all_extra_selections()

    def setPreviewSelectedLineHighlight(self, line_number: int):
        # ... (код методу) ...
        new_selections = []
        doc = self.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                selection = QTextEdit.ExtraSelection()
                selection.format.setBackground(self.preview_selected_line_color)
                selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                selection.cursor = QTextCursor(block)
                new_selections.append(selection)
        if self._preview_selected_line_selections != new_selections:
            log_debug(f"LNET ({self.widget_id}): setPreviewSelectedLineHighlight - updating to line {line_number}.")
            self._preview_selected_line_selections = new_selections
            self._apply_all_extra_selections()

    def clearPreviewSelectedLineHighlight(self):
        if self._preview_selected_line_selections:
            log_debug(f"LNET ({self.widget_id}): clearPreviewSelectedLineHighlight.")
            self._preview_selected_line_selections = []
            self._apply_all_extra_selections()
            
    def addProblemLineHighlight(self, line_number: int):
        log_debug(f"LNET ({self.widget_id}): Attempting to add problem highlight for line {line_number}. Current problems: {len(self._problem_line_selections)}")
        doc = self.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                is_already_added = any(
                    s.cursor.blockNumber() == line_number and \
                    s.format.background() == self.problem_line_color \
                    for s in self._problem_line_selections
                )
                if not is_already_added:
                    selection = QTextEdit.ExtraSelection()
                    selection.format.setBackground(self.problem_line_color)
                    selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                    selection.cursor = QTextCursor(block)
                    self._problem_line_selections.append(selection)
                    log_debug(f"LNET ({self.widget_id}): Queued problem highlight for line {line_number}. Total problems queued: {len(self._problem_line_selections)}")
                    # НЕ викликаємо _apply_all_extra_selections тут, робимо це один раз ззовні
                else:
                    log_debug(f"LNET ({self.widget_id}): Problem highlight for line {line_number} already exists.")


    def applyQueuedProblemHighlights(self):
        if self._problem_line_selections:
            log_debug(f"LNET ({self.widget_id}): applyQueuedProblemHighlights - applying {len(self._problem_line_selections)} problem highlights.")
            self._apply_all_extra_selections()
        else:
            log_debug(f"LNET ({self.widget_id}): applyQueuedProblemHighlights - no problem highlights to apply.")


    def clearProblemLineHighlights(self):
        if self._problem_line_selections:
            log_debug(f"LNET ({self.widget_id}): clearProblemLineHighlights. Had {len(self._problem_line_selections)} problems.")
            self._problem_line_selections = []
            self._apply_all_extra_selections()
        # else:
            # log_debug(f"LNET ({self.widget_id}): clearProblemLineHighlights - no problems to clear.")


    def setReadOnly(self, ro):
        # ... (код методу) ...
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
            cursor = self.cursorForPosition(event.pos()); line_no = cursor.blockNumber() 
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
                     painter.fillRect(line_num_rect, current_line_number_highlight_bg)
                     painter.setPen(current_line_number_highlight_text) 
                elif (blockNumber + 1) % 2 == 0: painter.setPen(self.lineNumberArea.number_color)
                else: painter.fillRect(line_num_rect, self.lineNumberArea.odd_line_background); painter.setPen(self.lineNumberArea.number_color)
                painter.drawText(line_num_rect, Qt.AlignRight | Qt.AlignVCenter, number + " ") 
            block = block.next(); top = bottom
            bottom = top + int(self.blockBoundingRect(block).height()); blockNumber += 1