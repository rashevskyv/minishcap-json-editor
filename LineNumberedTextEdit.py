from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QHBoxLayout, QTextEdit, QStyle, QApplication, QMainWindow
from PyQt5.QtGui import (QPainter, QColor, QFont, QTextBlockFormat, 
                         QTextFormat, QPen, QMouseEvent, QTextCursor, 
                         QTextCharFormat, QPaintEvent)
from PyQt5.QtCore import Qt, QRect, QSize, QRectF, pyqtSignal, QTimer, QPoint 
from utils import log_debug 
from syntax_highlighter import JsonTagHighlighter 
import re 
from typing import Optional, Tuple 

# Константи для тегу гравця (будуть отримані з MainWindow)
EDITOR_PLAYER_TAG_DEFAULT = "[ІМ'Я ГРАВЦЯ]"
ORIGINAL_PLAYER_TAG_DEFAULT = "{Player}"

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
    addTagMappingRequest = pyqtSignal(str, str) 

    def __init__(self, parent=None): 
        super().__init__(parent)
        self.widget_id = str(id(self))[-6:] 
        self.lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        
        if not self.isReadOnly():
            self.cursorPositionChanged.connect(self.highlightCurrentLine)
        
        self.updateLineNumberAreaWidth(0)
        
        font = QFont("Courier New", 10) 
        self.setFont(font)

        self.highlighter = JsonTagHighlighter(self.document())
        
        self.ensurePolished() 
        self.current_line_color = QColor("#E8F2FE") 
        self.linked_cursor_block_color = QColor("#F0F8FF") 
        self.linked_cursor_pos_color = QColor(Qt.blue).lighter(160) 
        
        self.critical_problem_line_color = QColor(Qt.yellow).lighter(130) 
        self.warning_problem_line_color = QColor("#DDDDDD") 

        self.preview_selected_line_color = QColor("#E6F7FF") 
        self.tag_interaction_highlight_color = QColor(Qt.green).lighter(150)

        self._active_line_selections = [] 
        self._linked_cursor_selections = []
        self._critical_problem_selections = []
        self._warning_problem_selections = []
        self._preview_selected_line_selections = []
        self._tag_interaction_selections = []
        
        self.character_limit_line_position = 35 
        self.character_limit_line_color = QColor(0, 0, 0, 70) 
        self.character_limit_line_width = 1
        
        # Отримуємо константи тегу гравця з батьківського вікна, якщо можливо
        self.editor_player_tag = EDITOR_PLAYER_TAG_DEFAULT
        self.original_player_tag = ORIGINAL_PLAYER_TAG_DEFAULT
        if parent and isinstance(parent, QMainWindow):
            self.editor_player_tag = getattr(parent, 'EDITOR_PLAYER_TAG', EDITOR_PLAYER_TAG_DEFAULT)
            self.original_player_tag = getattr(parent, 'ORIGINAL_PLAYER_TAG', ORIGINAL_PLAYER_TAG_DEFAULT)


    def _create_block_background_selection(self, block: QTextBlockFormat, color: QColor, use_full_width: bool = False) -> Optional[QTextEdit.ExtraSelection]:
        if not block.isValid(): return None
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(color)
        cursor = QTextCursor(block)
        if use_full_width: 
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = cursor 
            selection.cursor.clearSelection() 
        else: 
            cursor.select(QTextCursor.BlockUnderCursor) 
            selection.cursor = cursor
        return selection

    def get_tag_at_cursor(self, cursor: QTextCursor, pattern: str) -> Tuple[Optional[str], int, int]:
        block = cursor.block()
        if not block.isValid(): return None, -1, -1
        block_text = block.text()
        cursor_pos_in_text_block = cursor.position() - block.position() 
        for match in re.finditer(pattern, block_text):
            start, end = match.span()
            if start <= cursor_pos_in_text_block < end:
                return match.group(0), start, end
        return None, -1, -1
        
    def _momentary_highlight_tag(self, block, start_in_block, length):
        if not block.isValid(): return
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
            actual_main_window = self.window() # Більш надійний спосіб отримати MainWindow
            if not isinstance(actual_main_window, QMainWindow): return 

            if self.isReadOnly() and hasattr(actual_main_window, 'original_text_edit') and self == actual_main_window.original_text_edit:
                tag_text_curly, tag_start, tag_end = self.get_tag_at_cursor(text_cursor_at_click, r"\{[^}]*\}")
                if tag_text_curly:
                    text_to_copy = tag_text_curly
                    if tag_text_curly == self.original_player_tag: # Використовуємо атрибут класу
                        text_to_copy = self.editor_player_tag
                        log_debug(f"LNET ({self.widget_id} - original_text_edit): Copied '{self.original_player_tag}' as '{self.editor_player_tag}'")
                    else:
                        log_debug(f"LNET ({self.widget_id} - original_text_edit): Copied tag: {tag_text_curly}")
                    
                    QApplication.clipboard().setText(text_to_copy)
                    if hasattr(actual_main_window, 'statusBar'): 
                        actual_main_window.statusBar.showMessage(f"Copied to clipboard: {text_to_copy}", 2000)
                    self._momentary_highlight_tag(text_cursor_at_click.block(), tag_start, len(tag_text_curly))
                    event.accept(); return
            elif not self.isReadOnly() and hasattr(actual_main_window, 'edited_text_edit') and self == actual_main_window.edited_text_edit:
                clicked_bracket_tag, tag_start_in_block, _ = self.get_tag_at_cursor(text_cursor_at_click, r"\[[^\]]*\]")
                clipboard_text = QApplication.clipboard().text()

                if event.modifiers() & Qt.ControlModifier and clicked_bracket_tag:
                    if re.fullmatch(r"\{[^}]*\}", clipboard_text):
                        self.addTagMappingRequest.emit(clicked_bracket_tag, clipboard_text)
                        if hasattr(actual_main_window, 'statusBar'):
                            actual_main_window.statusBar.showMessage(f"Requested to map: {clicked_bracket_tag} -> {clipboard_text}", 3000)
                        self._momentary_highlight_tag(text_cursor_at_click.block(), tag_start_in_block, len(clicked_bracket_tag))
                        event.accept(); return 
                    else:
                        if hasattr(actual_main_window, 'statusBar'):
                            actual_main_window.statusBar.showMessage(f"Ctrl+Click: Clipboard does not contain a valid {{...}} tag to map with '{clicked_bracket_tag}'.", 3000)
                        event.accept(); return
                elif clicked_bracket_tag: 
                    is_curly_tag_in_clipboard = re.fullmatch(r"\{[^}]*\}", clipboard_text)
                    # Дозволяємо вставляти і наш спеціальний редакторський тег гравця
                    is_editor_player_tag_in_clipboard = (clipboard_text == self.editor_player_tag)

                    if is_curly_tag_in_clipboard or is_editor_player_tag_in_clipboard:
                        current_block = text_cursor_at_click.block(); modify_cursor = QTextCursor(current_block)
                        modify_cursor.setPosition(current_block.position() + tag_start_in_block)
                        modify_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(clicked_bracket_tag))
                        new_cursor_pos_in_block = tag_start_in_block + len(clipboard_text)
                        modify_cursor.beginEditBlock(); modify_cursor.insertText(clipboard_text); modify_cursor.endEditBlock()
                        final_cursor = QTextCursor(current_block); final_cursor.setPosition(current_block.position() + new_cursor_pos_in_block); self.setTextCursor(final_cursor)
                        if hasattr(actual_main_window, 'statusBar'): actual_main_window.statusBar.showMessage(f"Replaced '{clicked_bracket_tag}' with '{clipboard_text}'", 2000)
                        self._momentary_highlight_tag(current_block, tag_start_in_block, len(clipboard_text))
                    else:
                        if hasattr(actual_main_window, 'statusBar'): actual_main_window.statusBar.showMessage(f"Clipboard does not contain a valid tag for replacement.", 2000)
                    event.accept(); return

    # ... (решта коду без змін) ...
    def _apply_all_extra_selections(self):
        all_selections = []
        if self._active_line_selections: all_selections.extend(list(self._active_line_selections))
        if self._linked_cursor_selections: 
            all_selections.extend([s for s in self._linked_cursor_selections if s.format.property(QTextFormat.FullWidthSelection)])
        if self._preview_selected_line_selections: all_selections.extend(list(self._preview_selected_line_selections))
        if self._critical_problem_selections: all_selections.extend(list(self._critical_problem_selections))
        if self._warning_problem_selections: all_selections.extend(list(self._warning_problem_selections))
        if self._linked_cursor_selections: 
            all_selections.extend([s for s in self._linked_cursor_selections if not s.format.property(QTextFormat.FullWidthSelection)])
        if self._tag_interaction_selections: all_selections.extend(list(self._tag_interaction_selections))
        super().setExtraSelections(all_selections)

    def highlightCurrentLine(self): 
        new_selections = [] 
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(self.current_line_color) 
            selection.format.setProperty(QTextFormat.FullWidthSelection, True) 
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
                line_sel = self._create_block_background_selection(block, self.linked_cursor_block_color, use_full_width=True) 
                if line_sel: new_linked_selections.append(line_sel)
                line_text_length = len(block.text()); actual_column = min(column_number, line_text_length)
                pos_sel_obj = QTextEdit.ExtraSelection()
                cursor_for_pos = QTextCursor(block)
                cursor_for_pos.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, actual_column)
                pos_format = QTextCharFormat(); pos_format.setBackground(self.linked_cursor_pos_color) 
                pos_sel_obj.format = pos_format
                temp_cursor_highlight = QTextCursor(cursor_for_pos)
                if actual_column < line_text_length: 
                    temp_cursor_highlight.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
                elif actual_column == line_text_length and line_text_length > 0 : 
                    if temp_cursor_highlight.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1):
                         temp_cursor_highlight.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1) 
                if temp_cursor_highlight.hasSelection() or \
                   (actual_column == line_text_length and not temp_cursor_highlight.hasSelection() and line_text_length > 0):
                    pos_sel_obj.cursor = temp_cursor_highlight
                    if not temp_cursor_highlight.hasSelection() and actual_column == line_text_length:
                         pos_sel_obj.cursor.setPosition(cursor_for_pos.position()) 
                    new_linked_selections.append(pos_sel_obj)
        if self._linked_cursor_selections != new_linked_selections:
            self._linked_cursor_selections = new_linked_selections
            self._apply_all_extra_selections()

    def setPreviewSelectedLineHighlight(self, line_number: int): 
        new_selections = []
        doc = self.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            selection = self._create_block_background_selection(block, self.preview_selected_line_color, use_full_width=True)
            if selection: new_selections.append(selection)
        if self._preview_selected_line_selections != new_selections:
            self._preview_selected_line_selections = new_selections
            self._apply_all_extra_selections()

    def clearPreviewSelectedLineHighlight(self):
        if self._preview_selected_line_selections:
            self._preview_selected_line_selections = []
            self._apply_all_extra_selections()
            
    def addCriticalProblemHighlight(self, line_number: int):
        doc = self.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                is_already_added = any(s.cursor.blockNumber() == line_number for s in self._critical_problem_selections)
                if not is_already_added:
                    selection = self._create_block_background_selection(block, self.critical_problem_line_color, use_full_width=False)
                    if selection: self._critical_problem_selections.append(selection)

    def removeCriticalProblemHighlight(self, line_number: int) -> bool:
        removed = False; initial_len = len(self._critical_problem_selections)
        self._critical_problem_selections = [s for s in self._critical_problem_selections if s.cursor.blockNumber() != line_number]
        if len(self._critical_problem_selections) < initial_len: removed = True
        return removed

    def clearCriticalProblemHighlights(self):
        needs_update = bool(self._critical_problem_selections)
        self._critical_problem_selections = []
        if needs_update: self._apply_all_extra_selections()

    def hasCriticalProblemHighlight(self, line_number: Optional[int] = None) -> bool:
        if line_number is not None: return any(s.cursor.blockNumber() == line_number for s in self._critical_problem_selections)
        return bool(self._critical_problem_selections)

    def addWarningLineHighlight(self, line_number: int):
        doc = self.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                is_already_added = any(s.cursor.blockNumber() == line_number for s in self._warning_problem_selections)
                if not is_already_added:
                    selection = self._create_block_background_selection(block, self.warning_problem_line_color, use_full_width=False)
                    if selection: self._warning_problem_selections.append(selection)

    def removeWarningLineHighlight(self, line_number: int) -> bool:
        removed = False; initial_len = len(self._warning_problem_selections)
        self._warning_problem_selections = [s for s in self._warning_problem_selections if s.cursor.blockNumber() != line_number]
        if len(self._warning_problem_selections) < initial_len: removed = True
        return removed

    def clearWarningLineHighlights(self):
        needs_update = bool(self._warning_problem_selections)
        self._warning_problem_selections = []
        if needs_update: self._apply_all_extra_selections()

    def hasWarningLineHighlight(self, line_number: Optional[int] = None) -> bool:
        if line_number is not None: return any(s.cursor.blockNumber() == line_number for s in self._warning_problem_selections)
        return bool(self._warning_problem_selections)

    def applyQueuedHighlights(self): self._apply_all_extra_selections()
    def clearAllProblemTypeHighlights(self):
        cleared_critical = bool(self._critical_problem_selections); cleared_warning = bool(self._warning_problem_selections)
        self._critical_problem_selections = []; self._warning_problem_selections = []
        if cleared_critical or cleared_warning: self._apply_all_extra_selections()
    def addProblemLineHighlight(self, line_number: int): self.addCriticalProblemHighlight(line_number)
    def removeProblemLineHighlight(self, line_number: int) -> bool: return self.removeCriticalProblemHighlight(line_number)
    def clearProblemLineHighlights(self): self.clearCriticalProblemHighlights(); self.clearWarningLineHighlights()
    def hasProblemHighlight(self, line_number: Optional[int] = None) -> bool:
        return self.hasCriticalProblemHighlight(line_number) or self.hasWarningLineHighlight(line_number)

    def setReadOnly(self, ro):
        super().setReadOnly(ro)
        if not ro: self.highlightCurrentLine() 
        else: 
            self._active_line_selections = []
            self._apply_all_extra_selections() 
        self.viewport().update() 

    def lineNumberAreaWidth(self):
        digits = 1; max_val = max(1, self.blockCount())
        while max_val >= 10: max_val //= 10; digits += 1
        return self.fontMetrics().horizontalAdvance('9') * (digits + 1) + 6 

    def updateLineNumberAreaWidth(self, _): 
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)
        self.viewport().update() 

    def updateLineNumberArea(self, rect: QRectF, dy: int):
        if dy: self.lineNumberArea.scroll(0, dy)
        else: self.lineNumberArea.update(0, 0, self.lineNumberArea.width(), self.lineNumberArea.height())
        if rect.contains(self.viewport().rect()): self.updateLineNumberAreaWidth(0)    
    
    def resizeEvent(self, event): 
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))
        self.viewport().update()

    def paintEvent(self, event: QPaintEvent): 
        super().paintEvent(event) 
        if not self.isReadOnly():
            painter = QPainter(self.viewport())
            char_width = self.fontMetrics().horizontalAdvance('0') 
            text_margin = self.document().documentMargin() 
            x_pos = int(text_margin + (self.character_limit_line_position * char_width))
            x_pos -= self.horizontalScrollBar().value()
            pen = QPen(self.character_limit_line_color, self.character_limit_line_width)
            pen.setStyle(Qt.SolidLine) 
            painter.setPen(pen)
            painter.drawLine(x_pos, 0, x_pos, self.viewport().height())

    def mousePressEvent(self, event: QMouseEvent): 
        super().mousePressEvent(event) 
        if event.button() == Qt.LeftButton:
            self.lineClicked.emit(self.cursorForPosition(event.pos()).blockNumber())

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        base_bg_color = self.palette().base().color()
        if self.isReadOnly(): base_bg_color = self.palette().window().color().lighter(105) 
        painter.fillRect(event.rect(), base_bg_color)
        block = self.firstVisibleBlock(); blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        current_text_cursor_block_number = -1
        if not self.isReadOnly(): current_text_cursor_block_number = self.textCursor().blockNumber()
        active_ln_bg = self.current_line_color 
        active_ln_text = self.palette().text().color()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                line_num_rect = QRect(0, top, self.lineNumberArea.width(), int(self.blockBoundingRect(block).height()))
                if not self.isReadOnly() and blockNumber == current_text_cursor_block_number:
                     painter.fillRect(line_num_rect, active_ln_bg)
                     painter.setPen(active_ln_text) 
                elif (blockNumber + 1) % 2 == 0: painter.setPen(self.lineNumberArea.number_color)
                else: 
                    painter.fillRect(line_num_rect, self.lineNumberArea.odd_line_background)
                    painter.setPen(self.lineNumberArea.number_color)
                painter.drawText(line_num_rect, Qt.AlignRight | Qt.AlignVCenter, number + " ") 
            block = block.next(); top = bottom
            bottom = top + int(self.blockBoundingRect(block).height()); blockNumber += 1