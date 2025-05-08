from PyQt5.QtWidgets import (QWidget, QPlainTextEdit, QHBoxLayout, QTextEdit, 
                             QStyle, QApplication, QMainWindow, QMenu) 
from PyQt5.QtGui import (QPainter, QColor, QFont, QTextBlockFormat, 
                         QTextFormat, QPen, QMouseEvent, QTextCursor, 
                         QTextCharFormat, QPaintEvent)
from PyQt5.QtCore import Qt, QRect, QSize, QRectF, pyqtSignal, QTimer, QPoint 
from LineNumberArea import LineNumberArea 
from TextHighlightManager import TextHighlightManager 
from utils import log_debug 
from syntax_highlighter import JsonTagHighlighter 
import re 
from typing import Optional, Tuple 

EDITOR_PLAYER_TAG_DEFAULT = "[ІМ'Я ГРАВЦЯ]"
ORIGINAL_PLAYER_TAG_DEFAULT = "{Player}"

class LineNumberedTextEdit(QPlainTextEdit):
    lineClicked = pyqtSignal(int) 
    addTagMappingRequest = pyqtSignal(str, str) 

    def __init__(self, parent=None): 
        super().__init__(parent)
        self.widget_id = str(id(self))[-6:] 
        self.lineNumberArea = LineNumberArea(self)
        
        self.current_line_color = QColor("#E8F2FE") 
        self.linked_cursor_block_color = QColor("#F0F8FF") 
        self.linked_cursor_pos_color = QColor(Qt.blue).lighter(160) 
        self.preview_selected_line_color = QColor("#E6F7FF") 
        self.critical_problem_line_color = QColor(Qt.yellow).lighter(130) 
        self.warning_problem_line_color = QColor("#DDDDDD") 
        self.tag_interaction_highlight_color = QColor(Qt.green).lighter(150)

        self.highlightManager = TextHighlightManager(self) 

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        
        if not self.isReadOnly():
            self.cursorPositionChanged.connect(self.highlightManager.updateCurrentLineHighlight)
        else:
            self.setContextMenuPolicy(Qt.CustomContextMenu)
            self.customContextMenuRequested.connect(self.showContextMenu)
        
        self.updateLineNumberAreaWidth(0)
        
        font = QFont("Courier New", 10) 
        self.setFont(font)

        self.highlighter = JsonTagHighlighter(self.document())
        
        self.ensurePolished() 
                        
        self.character_limit_line_position = 35 
        self.character_limit_line_color = QColor(0, 0, 0, 70) 
        self.character_limit_line_width = 1
        
        self.editor_player_tag = EDITOR_PLAYER_TAG_DEFAULT
        self.original_player_tag = ORIGINAL_PLAYER_TAG_DEFAULT
        if parent and isinstance(parent, QMainWindow):
            self.editor_player_tag = getattr(parent, 'EDITOR_PLAYER_TAG', EDITOR_PLAYER_TAG_DEFAULT)
            self.original_player_tag = getattr(parent, 'ORIGINAL_PLAYER_TAG', ORIGINAL_PLAYER_TAG_DEFAULT)

    def showContextMenu(self, pos: QPoint):
        menu = self.createStandardContextMenu()
        menu.addSeparator()

        main_window = self.window()
        if not isinstance(main_window, QMainWindow): return
        if not hasattr(main_window, 'data_processor'): return # Потрібен DataProcessor
        if not hasattr(main_window, 'editor_operation_handler'): return # Потрібен TextOperationHandler

        is_preview_widget = hasattr(main_window, 'preview_text_edit') and self == main_window.preview_text_edit
        
        if is_preview_widget:
            current_block_idx = main_window.current_block_idx
            clicked_cursor = self.cursorForPosition(pos)
            clicked_line_number = clicked_cursor.blockNumber()
            
            # Перевіряємо, чи індекси валідні
            if current_block_idx < 0 or clicked_line_number < 0 : 
                 menu.exec_(self.mapToGlobal(pos)) # Показуємо стандартне меню, якщо не вибрано рядок/блок
                 return

            if hasattr(main_window, 'paste_block_action'):
                paste_block_action = menu.addAction("Paste Block Text Here")
                paste_block_action.triggered.connect(main_window.editor_operation_handler.paste_block_text)
                paste_block_action.setEnabled(QApplication.clipboard().text() != "")

            if hasattr(main_window, 'undo_paste_action'):
                 undo_paste_action = menu.addAction("Undo Last Paste Block")
                 undo_paste_action.triggered.connect(main_window.trigger_undo_paste_action)
                 undo_paste_action.setEnabled(main_window.can_undo_paste)

            menu.addSeparator()

            revert_line_action = menu.addAction(f"Revert Line {clicked_line_number + 1} to Original")
            if hasattr(main_window.editor_operation_handler, 'revert_single_line'):
                revert_line_action.triggered.connect(lambda checked=False, line=clicked_line_number: main_window.editor_operation_handler.revert_single_line(line))
                
                # --- Оновлена логіка активації ---
                is_revertable = False
                # Отримуємо оригінальний текст
                original_text = main_window.data_processor._get_string_from_source(current_block_idx, clicked_line_number, main_window.data, "original_for_revert_check")
                if original_text is not None:
                     # Отримуємо поточний текст (з урахуванням усіх джерел)
                     current_text, _ = main_window.data_processor.get_current_string_text(current_block_idx, clicked_line_number)
                     # Якщо поточний текст відрізняється від оригінального, можна скасувати
                     if current_text != original_text:
                          is_revertable = True
                revert_line_action.setEnabled(is_revertable)
                # ---------------------------------
            else:
                 revert_line_action.setEnabled(False) 

        # Тут можна додати дії для original_text_edit
        is_original_widget = hasattr(main_window, 'original_text_edit') and self == main_window.original_text_edit
        if is_original_widget:
             tag_text_curly, _, _ = self.get_tag_at_cursor(self.cursorForPosition(pos), r"\{[^}]*\}")
             if tag_text_curly:
                  copy_tag_action = menu.addAction(f"Copy Tag: {tag_text_curly}")
                  copy_tag_action.triggered.connect(lambda checked=False, tag=tag_text_curly: self.copy_tag_to_clipboard(tag))


        menu.exec_(self.mapToGlobal(pos))
        
    # Допоміжна функція для копіювання тегу з original_text_edit
    def copy_tag_to_clipboard(self, tag_text_curly):
         actual_main_window = self.window()
         if not isinstance(actual_main_window, QMainWindow): return
         
         text_to_copy = tag_text_curly
         if tag_text_curly == self.original_player_tag: 
             text_to_copy = self.editor_player_tag
             log_debug(f"LNET ({self.widget_id} - original_text_edit context): Copied '{self.original_player_tag}' as '{self.editor_player_tag}'")
         else:
             log_debug(f"LNET ({self.widget_id} - original_text_edit context): Copied tag: {tag_text_curly}")
             
         QApplication.clipboard().setText(text_to_copy)
         if hasattr(actual_main_window, 'statusBar'): 
             actual_main_window.statusBar.showMessage(f"Copied to clipboard: {text_to_copy}", 2000)


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
        self.highlightManager.momentaryHighlightTag(block, start_in_block, length)

    def _apply_all_extra_selections(self):
        self.highlightManager.applyHighlights()

    def mouseReleaseEvent(self, event: QMouseEvent): 
        super().mouseReleaseEvent(event) 
        if event.button() == Qt.LeftButton:
            text_cursor_at_click = self.cursorForPosition(event.pos())
            actual_main_window = self.window() 
            if not isinstance(actual_main_window, QMainWindow): return 

            if self.isReadOnly() and hasattr(actual_main_window, 'original_text_edit') and self == actual_main_window.original_text_edit:
                tag_text_curly, tag_start, tag_end = self.get_tag_at_cursor(text_cursor_at_click, r"\{[^}]*\}")
                if tag_text_curly:
                    self.copy_tag_to_clipboard(tag_text_curly) # Використовуємо нову функцію
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

    def addCriticalProblemHighlight(self, line_number: int):
        self.highlightManager.addCriticalProblemHighlight(line_number)

    def removeCriticalProblemHighlight(self, line_number: int) -> bool:
        return self.highlightManager.removeCriticalProblemHighlight(line_number)

    def clearCriticalProblemHighlights(self):
        self.highlightManager.clearCriticalProblemHighlights()

    def hasCriticalProblemHighlight(self, line_number: Optional[int] = None) -> bool:
        return self.highlightManager.hasCriticalProblemHighlight(line_number)

    def addWarningLineHighlight(self, line_number: int):
        self.highlightManager.addWarningLineHighlight(line_number)

    def removeWarningLineHighlight(self, line_number: int) -> bool:
        return self.highlightManager.removeWarningLineHighlight(line_number)

    def clearWarningLineHighlights(self):
        self.highlightManager.clearWarningLineHighlights()

    def hasWarningLineHighlight(self, line_number: Optional[int] = None) -> bool:
        return self.highlightManager.hasWarningLineHighlight(line_number)
        
    def setPreviewSelectedLineHighlight(self, line_number: int): 
        self.highlightManager.setPreviewSelectedLineHighlight(line_number)

    def clearPreviewSelectedLineHighlight(self):
        self.highlightManager.clearPreviewSelectedLineHighlight()

    def setLinkedCursorPosition(self, line_number: int, column_number: int):
        self.highlightManager.setLinkedCursorPosition(line_number, column_number)

    def applyQueuedHighlights(self): 
        self.highlightManager.applyHighlights() 

    def clearAllProblemTypeHighlights(self):
        self.highlightManager.clearAllProblemHighlights()
        
    def addProblemLineHighlight(self, line_number: int): self.addCriticalProblemHighlight(line_number)
    def removeProblemLineHighlight(self, line_number: int) -> bool: return self.removeCriticalProblemHighlight(line_number)
    def clearProblemLineHighlights(self): self.clearAllProblemTypeHighlights()
    def hasProblemHighlight(self, line_number: Optional[int] = None) -> bool:
        return self.highlightManager.hasCriticalProblemHighlight(line_number) or self.highlightManager.hasWarningLineHighlight(line_number)

    def setReadOnly(self, ro):
        super().setReadOnly(ro)
        self.highlightManager.clearAllHighlights() 
        if not ro:
             self.highlightManager.updateCurrentLineHighlight()
             # Якщо стає Editable, вимикаємо контекстне меню (воно має стандартні дії)
             self.setContextMenuPolicy(Qt.DefaultContextMenu)
             try:
                  self.customContextMenuRequested.disconnect(self.showContextMenu)
             except TypeError:
                  pass
        else:
             self.setContextMenuPolicy(Qt.CustomContextMenu)
             try:
                 self.customContextMenuRequested.disconnect(self.showContextMenu)
             except TypeError: 
                 pass
             self.customContextMenuRequested.connect(self.showContextMenu)

        self.viewport().update() 

    def lineNumberAreaWidth(self):
        digits = 1; max_val = max(1, self.blockCount())
        while max_val >= 10: max_val //= 10; digits += 1
        return self.fontMetrics().horizontalAdvance('9') * (digits) + 10 

    def updateLineNumberAreaWidth(self, _): 
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)
        self.lineNumberArea.update() 

    def updateLineNumberArea(self, rect: QRectF, dy: int):
        if dy: self.lineNumberArea.scroll(0, dy)
        else: self.lineNumberArea.update(0, 0, self.lineNumberArea.width(), self.lineNumberArea.height())
        self.updateLineNumberAreaWidth(0)    
    
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
            x_pos = int(self.document().documentMargin() + (self.character_limit_line_position * char_width))
            x_pos -= self.horizontalScrollBar().value()
            pen = QPen(self.character_limit_line_color, self.character_limit_line_width)
            pen.setStyle(Qt.SolidLine) 
            painter.setPen(pen)
            painter.drawLine(x_pos, 0, x_pos, self.viewport().height())

    def mousePressEvent(self, event: QMouseEvent): 
        super().mousePressEvent(event) 
        if event.button() == Qt.LeftButton:
             cursor = self.cursorForPosition(event.pos())
             block_number = cursor.blockNumber()
             self.lineClicked.emit(block_number)

    def lineNumberAreaPaintEvent(self, event, painter_device): 
        painter = QPainter(painter_device) 
        
        base_bg_color = self.palette().base().color()
        if self.isReadOnly():
             base_bg_color = self.palette().window().color().lighter(105)
        painter.fillRect(event.rect(), base_bg_color)

        edited_active_block = -1
        preview_active_block = -1
        original_active_block = -1

        if self.highlightManager._active_line_selections:
             edited_active_block = self.highlightManager._active_line_selections[0].cursor.blockNumber()
        if self.highlightManager._preview_selected_line_selections:
             preview_active_block = self.highlightManager._preview_selected_line_selections[0].cursor.blockNumber()
        if self.highlightManager._linked_cursor_selections:
            for sel in self.highlightManager._linked_cursor_selections:
                if sel.format.property(QTextFormat.FullWidthSelection):
                     original_active_block = sel.cursor.blockNumber()
                     break
        
        active_bg_color = self.lineNumberArea.active_number_background_color 
        active_text_color = self.lineNumberArea.active_number_color 
        odd_bg_color = self.lineNumberArea.odd_line_background
        number_color = self.lineNumberArea.number_color

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        area_width = self.lineNumberAreaWidth() 

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                line_num_rect = QRect(0, top, area_width - 3, int(self.blockBoundingRect(block).height())) 

                is_line_active = ( (edited_active_block == blockNumber) or \
                                   (preview_active_block == blockNumber) or \
                                   (original_active_block == blockNumber) )

                if is_line_active:
                     painter.fillRect(line_num_rect.adjusted(0, 0, 3, 0), active_bg_color) 
                     painter.setPen(active_text_color) 
                elif (blockNumber + 1) % 2 == 0: 
                    painter.setPen(number_color)
                else: 
                    painter.fillRect(line_num_rect.adjusted(0, 0, 3, 0), odd_bg_color) 
                    painter.setPen(number_color)
                
                painter.drawText(line_num_rect, Qt.AlignRight | Qt.AlignVCenter, number) 

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1