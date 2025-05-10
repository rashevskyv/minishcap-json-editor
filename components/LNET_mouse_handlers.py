from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu
from PyQt5.QtGui import QTextCursor, QMouseEvent
from PyQt5.QtCore import Qt, QPoint
import re
from typing import Optional, Tuple

from utils.utils import log_debug

class LNETMouseHandlers:
    def __init__(self, editor): # editor - це LineNumberedTextEdit
        self.editor = editor

    def _wrap_selection_with_color(self, color_name: str):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            return

        selected_text = cursor.selectedText()
        
        prefix_tag = f"{{Color:{color_name.capitalize()}}}"
        suffix_tag = "{Color:White}"
        
        new_text = f"{prefix_tag}{selected_text}{suffix_tag}"
        
        cursor.insertText(new_text)
        log_debug(f"Wrapped selection with {color_name}. New text: {new_text[:50]}...")

    def copy_tag_to_clipboard(self, tag_text_curly):
         # self.editor тут - це LineNumberedTextEdit (original_text_edit)
         actual_main_window = self.editor.window()
         if not isinstance(actual_main_window, QMainWindow): return

         text_to_copy = tag_text_curly
         # Доступ до editor_player_tag та original_player_tag через self.editor
         if tag_text_curly == self.editor.original_player_tag: 
             text_to_copy = self.editor.editor_player_tag
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

    def showContextMenu(self, pos: QPoint): # pos - це координати кліку відносно віджета self.editor
        log_debug(f"LNETMouseHandlers: showContextMenu for editor: {self.editor.objectName()} at pos {pos}")
        menu = self.editor.createStandardContextMenu()
        
        # Викликаємо метод самого редактора для заповнення меню
        if hasattr(self.editor, 'populateContextMenu'):
            self.editor.populateContextMenu(menu, pos) # Передаємо pos
        else:
            log_debug(f"LNETMouseHandlers: Editor {self.editor.objectName()} has no populateContextMenu method.")

        log_debug(f"LNETMouseHandlers: Executing menu for {self.editor.objectName()}.")
        menu.exec_(self.editor.mapToGlobal(pos))


    def mouseReleaseEvent(self, event: QMouseEvent):
        self.editor.super_mouseReleaseEvent(event) # Викликаємо батьківський метод з LineNumberedTextEdit
        if event.button() == Qt.LeftButton:
            text_cursor_at_click = self.editor.cursorForPosition(event.pos())
            actual_main_window = self.editor.window()
            if not isinstance(actual_main_window, QMainWindow): return

            if self.editor.isReadOnly() and hasattr(actual_main_window, 'original_text_edit') and self.editor == actual_main_window.original_text_edit:
                tag_text_curly, tag_start, tag_end = self.get_tag_at_cursor(text_cursor_at_click, r"\{[^}]*\}")
                if tag_text_curly:
                    self.copy_tag_to_clipboard(tag_text_curly)
                    self.editor._momentary_highlight_tag(text_cursor_at_click.block(), tag_start, len(tag_text_curly))
                    event.accept(); return
            elif not self.editor.isReadOnly() and hasattr(actual_main_window, 'edited_text_edit') and self.editor == actual_main_window.edited_text_edit:
                clicked_bracket_tag, tag_start_in_block, _ = self.get_tag_at_cursor(text_cursor_at_click, r"\[[^\]]*\]")
                clipboard_text = QApplication.clipboard().text()
                if event.modifiers() & Qt.ControlModifier and clicked_bracket_tag:
                    if re.fullmatch(r"\{[^}]*\}", clipboard_text):
                        self.editor.addTagMappingRequest.emit(clicked_bracket_tag, clipboard_text)
                        if hasattr(actual_main_window, 'statusBar'):
                            actual_main_window.statusBar.showMessage(f"Requested to map: {clicked_bracket_tag} -> {clipboard_text}", 3000)
                        self.editor._momentary_highlight_tag(text_cursor_at_click.block(), tag_start_in_block, len(clicked_bracket_tag))
                        event.accept(); return
                    else:
                        if hasattr(actual_main_window, 'statusBar'):
                             actual_main_window.statusBar.showMessage(f"Ctrl+Click: Clipboard does not contain a valid {{...}} tag to map with '{clicked_bracket_tag}'.", 3000)
                        event.accept(); return
                elif clicked_bracket_tag:
                    is_curly_tag_in_clipboard = re.fullmatch(r"\{[^}]*\}", clipboard_text)
                    # Доступ до editor_player_tag через self.editor
                    is_editor_player_tag_in_clipboard = (clipboard_text == self.editor.editor_player_tag) 
                    if is_curly_tag_in_clipboard or is_editor_player_tag_in_clipboard:
                        current_block = text_cursor_at_click.block(); modify_cursor = QTextCursor(current_block)
                        modify_cursor.setPosition(current_block.position() + tag_start_in_block)
                        modify_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(clicked_bracket_tag))
                        new_cursor_pos_in_block = tag_start_in_block + len(clipboard_text)
                        modify_cursor.beginEditBlock(); modify_cursor.insertText(clipboard_text); modify_cursor.endEditBlock()
                        final_cursor = QTextCursor(current_block); final_cursor.setPosition(current_block.position() + new_cursor_pos_in_block); self.editor.setTextCursor(final_cursor)
                        if hasattr(actual_main_window, 'statusBar'): actual_main_window.statusBar.showMessage(f"Replaced '{clicked_bracket_tag}' with '{clipboard_text}'", 2000)
                        self.editor._momentary_highlight_tag(current_block, tag_start_in_block, len(clipboard_text))
                    else:
                        if hasattr(actual_main_window, 'statusBar'): actual_main_window.statusBar.showMessage(f"Clipboard does not contain a valid tag for replacement.", 2000)
                    event.accept(); return

    def mousePressEvent(self, event: QMouseEvent):
        self.editor.super_mousePressEvent(event) # Викликаємо батьківський метод з LineNumberedTextEdit
        if event.button() == Qt.LeftButton:
             cursor = self.editor.cursorForPosition(event.pos())
             block_number = cursor.blockNumber()
             self.editor.lineClicked.emit(block_number)