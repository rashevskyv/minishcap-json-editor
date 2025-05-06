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
        self.current_line_color = QColor("#E8F2FE") 
        self.linked_cursor_block_color = QColor("#F5F5F5") 
        self.linked_cursor_pos_color = QColor(Qt.blue).lighter(160) 
        self.problem_line_color = QColor(Qt.yellow).lighter(130) 
        self.preview_selected_line_color = QColor("#DDEEFF") 
        self.tag_interaction_highlight_color = QColor(Qt.green).lighter(150)

        self._active_line_selections = [] 
        self._linked_cursor_selections = []
        self._problem_line_selections = [] 
        self._preview_selected_line_selections = []
        self._tag_interaction_selections = []
        
        log_debug(f"LNET ({self.widget_id}): Initialized selection lists")

    def _create_block_background_selection(self, block: QTextBlockFormat, color: QColor) -> Optional[QTextEdit.ExtraSelection]:
        if not block.isValid():
            return None
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(color)
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.BlockUnderCursor)
        selection.cursor = cursor
        return selection

    def get_tag_at_cursor(self, cursor: QTextCursor, pattern: str) -> Tuple[Optional[str], int, int]:
        block = cursor.block()
        if not block.isValid():
            return None, -1, -1
            
        block_text = block.text()
        cursor_pos_in_text_block = cursor.position() - block.position() 
        
        for match in re.finditer(pattern, block_text):
            start, end = match.span()
            if start <= cursor_pos_in_text_block < end:
                return match.group(0), start, end
        return None, -1, -1

    def _momentary_highlight_tag(self, block, start_in_block, length):
        if not block.isValid():
            return

        self.clearTagInteractionHighlight()
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(self.tag_interaction_highlight_color)
        
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + start_in_block)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        selection.cursor = cursor
        
        self._tag_interaction_selections.append(selection)
        self._apply_all_extra_selections()
        
        QTimer.singleShot(300, self.clearTagInteractionHighlight)

    def clearTagInteractionHighlight(self):
        if self._tag_interaction_selections:
            self._tag_interaction_selections = []
            self._apply_all_extra_selections()

    def mouseReleaseEvent(self, event: QMouseEvent): 
        super().mouseReleaseEvent(event) 

        if event.button() == Qt.LeftButton:
            text_cursor_at_click = self.cursorForPosition(event.pos())
            
            actual_main_window = self
            while hasattr(actual_main_window, 'parent') and actual_main_window.parent() is not None \
                  and not isinstance(actual_main_window, QMainWindow):
                actual_main_window = actual_main_window.parent()
            
            if not isinstance(actual_main_window, QMainWindow):
                log_debug(f"LNET ({self.widget_id}): Could not find QMainWindow parent for tag click handling.")
                # Не викликаємо lineClicked тут, бо це не для вибору рядка
                return 

            # Логіка для original_text_edit (копіювання тегу {...})
            if self.isReadOnly() and hasattr(actual_main_window, 'original_text_edit') and self == actual_main_window.original_text_edit:
                tag_text, tag_start, tag_end = self.get_tag_at_cursor(text_cursor_at_click, r"\{[^}]*\}")
                if tag_text:
                    clipboard = QApplication.clipboard()
                    clipboard.setText(tag_text)
                    log_debug(f"LNET ({self.widget_id} - original_text_edit): Copied tag to clipboard: {tag_text}")
                    if hasattr(actual_main_window, 'statusBar'):
                        actual_main_window.statusBar.showMessage(f"Copied: {tag_text}", 2000)
                    self._momentary_highlight_tag(text_cursor_at_click.block(), tag_start, len(tag_text))
                    event.accept() # Подія оброблена, не передавати далі для вибору рядка
                    return
            
            # Логіка для edited_text_edit (заміна тегу [...] на тег з буфера)
            elif not self.isReadOnly() and hasattr(actual_main_window, 'edited_text_edit') and self == actual_main_window.edited_text_edit:
                clicked_tag_text, tag_start_in_block_text, tag_end_in_block_text = self.get_tag_at_cursor(text_cursor_at_click, r"\[[^\]]*\]")
                
                if clicked_tag_text:
                    clipboard = QApplication.clipboard()
                    clipboard_text = clipboard.text()
                    
                    if re.fullmatch(r"\{[^}]*\}", clipboard_text):
                        log_debug(f"LNET ({self.widget_id} - edited_text_edit): Clicked on editable tag '{clicked_tag_text}'. Clipboard has valid tag '{clipboard_text}'. Replacing.")
                        
                        current_block = text_cursor_at_click.block()
                        modify_cursor = QTextCursor(current_block)
                        modify_cursor.setPosition(current_block.position() + tag_start_in_block_text)
                        modify_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(clicked_tag_text))
                        
                        new_cursor_pos_in_block = tag_start_in_block_text + len(clipboard_text)

                        modify_cursor.beginEditBlock()
                        modify_cursor.insertText(clipboard_text)
                        modify_cursor.endEditBlock()

                        final_cursor = QTextCursor(current_block)
                        final_cursor.setPosition(current_block.position() + new_cursor_pos_in_block)
                        self.setTextCursor(final_cursor)
                        
                        if hasattr(actual_main_window, 'statusBar'):
                             actual_main_window.statusBar.showMessage(f"Replaced '{clicked_tag_text}' with '{clipboard_text}'", 2000)
                        self._momentary_highlight_tag(current_block, tag_start_in_block_text, len(clipboard_text))
                    else:
                        log_debug(f"LNET ({self.widget_id} - edited_text_edit): Clicked on editable tag '{clicked_tag_text}', but clipboard content ('{clipboard_text}') is not a valid {{...}} tag.")
                        if hasattr(actual_main_window, 'statusBar'):
                             actual_main_window.statusBar.showMessage(f"Clipboard does not contain a valid {{...}} tag.", 2000)
                    event.accept() # Подія оброблена
                    return
        # Якщо клік не був на тегу (або умови не виконались), то не викликаємо lineClicked звідси
        # lineClicked емітується з mousePressEvent

    def _apply_all_extra_selections(self):
        all_selections = []
        if self._active_line_selections: all_selections.extend(list(self._active_line_selections))
        if self._linked_cursor_selections: all_selections.extend(list(self._linked_cursor_selections))
        if self._preview_selected_line_selections: all_selections.extend(list(self._preview_selected_line_selections))
        if self._problem_line_selections: all_selections.extend(list(self._problem_line_selections))
        if self._tag_interaction_selections: all_selections.extend(list(self._tag_interaction_selections))
        
        problem_lines_debug = [s.cursor.blockNumber() for s in self._problem_line_selections]
        # log_debug(f"LNET ({self.widget_id}): _apply_all_extra_selections. Total: {len(all_selections)}. Problems: {len(self._problem_line_selections)} (lines: {problem_lines_debug})")
        super().setExtraSelections(all_selections)

    def highlightCurrentLine(self):
        new_selections = [] 
        if not self.isReadOnly(): 
            selection = QTextEdit.ExtraSelection(); selection.format.setBackground(self.current_line_color) 
            selection.format.setProperty(QTextFormat.FullWidthSelection, True); selection.cursor = self.textCursor()
            selection.cursor.clearSelection(); new_selections.append(selection)
        if self._active_line_selections != new_selections: self._active_line_selections = new_selections; self._apply_all_extra_selections()

    def setLinkedCursorPosition(self, line_number: int, column_number: int):
        new_selections = [] ; doc = self.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                line_sel = self._create_block_background_selection(block, self.linked_cursor_block_color)
                if line_sel: new_selections.append(line_sel)

                line_text_length = len(block.text()); actual_column = min(column_number, line_text_length)
                pos_sel_obj = QTextEdit.ExtraSelection(); cursor_for_pos = QTextCursor(block)
                cursor_for_pos.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, actual_column)
                pos_format = QTextCharFormat(); pos_format.setBackground(self.linked_cursor_pos_color) 
                pos_sel_obj.format = pos_format; temp_cursor_highlight = QTextCursor(cursor_for_pos)
                if actual_column < line_text_length: 
                    temp_cursor_highlight.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
                elif actual_column == line_text_length and line_text_length > 0 : 
                    if temp_cursor_highlight.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1):
                         temp_cursor_highlight.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1) 
                
                if temp_cursor_highlight.hasSelection() or (actual_column == line_text_length and line_text_length > 0 and not temp_cursor_highlight.hasSelection()): # Для кінця рядка
                    pos_sel_obj.cursor = temp_cursor_highlight
                    if not temp_cursor_highlight.hasSelection() and actual_column == line_text_length : # Для курсору в кінці рядка
                         pos_sel_obj.cursor.clearSelection() # Немає виділення, але курсор встановлений
                         pos_sel_obj.cursor.setPosition(cursor_for_pos.position()) # Встановлюємо позицію

                    new_selections.append(pos_sel_obj)

        if self._linked_cursor_selections != new_selections: self._linked_cursor_selections = new_selections; self._apply_all_extra_selections()

    def setPreviewSelectedLineHighlight(self, line_number: int):
        new_selections = []; doc = self.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            selection = self._create_block_background_selection(block, self.preview_selected_line_color)
            if selection: new_selections.append(selection)
        if self._preview_selected_line_selections != new_selections: self._preview_selected_line_selections = new_selections; self._apply_all_extra_selections()

    def clearPreviewSelectedLineHighlight(self):
        if self._preview_selected_line_selections: self._preview_selected_line_selections = []; self._apply_all_extra_selections()
            
    def addProblemLineHighlight(self, line_number: int):
        doc = self.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                is_already_added = any(s.cursor.blockNumber() == line_number for s in self._problem_line_selections)
                if not is_already_added:
                    selection = self._create_block_background_selection(block, self.problem_line_color)
                    if selection:
                        self._problem_line_selections.append(selection); log_debug(f"LNET ({self.widget_id}): Queued problem highlight for line {line_number}. Total problems: {len(self._problem_line_selections)}")

    def removeProblemLineHighlight(self, line_number: int) -> bool:
        removed = False; initial_len = len(self._problem_line_selections)
        self._problem_line_selections = [s for s in self._problem_line_selections if s.cursor.blockNumber() != line_number]
        if len(self._problem_line_selections) < initial_len:
            log_debug(f"LNET ({self.widget_id}): Marked line {line_number} for removal from problem highlights. Problems left: {len(self._problem_line_selections)}")
            removed = True
        return removed

    def applyQueuedProblemHighlights(self):
        log_debug(f"LNET ({self.widget_id}): applyQueuedProblemHighlights - applying/refreshing. Problems in queue: {len(self._problem_line_selections)}")
        self._apply_all_extra_selections()

    def clearProblemLineHighlights(self):
        if self._problem_line_selections: log_debug(f"LNET ({self.widget_id}): clearProblemLineHighlights. Had {len(self._problem_line_selections)} problems.")
        self._problem_line_selections = []; self._apply_all_extra_selections()

    def hasProblemHighlight(self, line_number: Optional[int] = None) -> bool:
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
            # Цей клік завжди емітує lineClicked для загальної функціональності вибору рядка
            cursor_for_line_click = self.cursorForPosition(event.pos())
            line_no = cursor_for_line_click.blockNumber() 
            self.lineClicked.emit(line_no)
            # Специфічна обробка кліків на теги тепер у mouseReleaseEvent, щоб уникнути конфліктів

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