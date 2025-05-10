from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu
from PyQt5.QtGui import QTextCursor, QMouseEvent
from PyQt5.QtCore import Qt, QPoint
import re
from typing import Optional, Tuple

from utils.utils import log_debug

class LNETMouseHandlers:
    def __init__(self, editor):
        self.editor = editor

    def showContextMenu(self, pos: QPoint):
        menu = self.editor.createStandardContextMenu()
        menu.addSeparator()

        main_window = self.editor.window()
        if not isinstance(main_window, QMainWindow): return
        if not hasattr(main_window, 'data_processor'): return
        if not hasattr(main_window, 'editor_operation_handler'): return

        is_preview_widget = hasattr(main_window, 'preview_text_edit') and self.editor == main_window.preview_text_edit

        if is_preview_widget:
            current_block_idx_data = main_window.current_block_idx
            clicked_cursor = self.editor.cursorForPosition(pos)
            clicked_data_line_number = clicked_cursor.blockNumber()

            if current_block_idx_data < 0 or clicked_data_line_number < 0 :
                 menu.exec_(self.editor.mapToGlobal(pos))
                 return

            if hasattr(main_window, 'paste_block_action'):
                paste_block_action = menu.addAction("Paste Block Text Here")
                paste_block_action.triggered.connect(main_window.editor_operation_handler.paste_block_text)
                paste_block_action.setEnabled(QApplication.clipboard().text() != "")

            if hasattr(main_window, 'undo_paste_action'):
                 undo_paste_action = menu.addAction("Undo Last Paste Block")
                 undo_paste_action.triggered.connect(main_window.actions.trigger_undo_paste_action)
                 undo_paste_action.setEnabled(main_window.can_undo_paste)

            menu.addSeparator()

            revert_line_action = menu.addAction(f"Revert Data Line {clicked_data_line_number + 1} to Original")
            if hasattr(main_window.editor_operation_handler, 'revert_single_line'):
                revert_line_action.triggered.connect(lambda checked=False, line=clicked_data_line_number: main_window.editor_operation_handler.revert_single_line(line))

                is_revertable = False
                original_text_for_revert_check = main_window.data_processor._get_string_from_source(current_block_idx_data, clicked_data_line_number, main_window.data, "original_for_revert_check")
                if original_text_for_revert_check is not None:
                     current_text, _ = main_window.data_processor.get_current_string_text(current_block_idx_data, clicked_data_line_number)
                     if current_text != original_text_for_revert_check:
                          is_revertable = True
                revert_line_action.setEnabled(is_revertable)
            else:
                 revert_line_action.setEnabled(False)

            calc_width_action = menu.addAction(f"Calculate Width for Data Line {clicked_data_line_number + 1}")
            if hasattr(main_window, 'editor_operation_handler') and hasattr(main_window.editor_operation_handler, 'calculate_width_for_data_line_action'):
                calc_width_action.triggered.connect(lambda checked=False, line_idx=clicked_data_line_number: main_window.editor_operation_handler.calculate_width_for_data_line_action(line_idx))
            else:
                calc_width_action.setEnabled(False)


        is_original_widget = hasattr(main_window, 'original_text_edit') and self.editor == main_window.original_text_edit
        if is_original_widget:
             tag_text_curly, _, _ = self.get_tag_at_cursor(self.editor.cursorForPosition(pos), r"\{[^}]*\}")
             if tag_text_curly:
                  copy_tag_action = menu.addAction(f"Copy Tag: {tag_text_curly}")
                  copy_tag_action.triggered.connect(lambda checked=False, tag=tag_text_curly: self.copy_tag_to_clipboard(tag))

        menu.exec_(self.editor.mapToGlobal(pos))

    def copy_tag_to_clipboard(self, tag_text_curly):
         actual_main_window = self.editor.window()
         if not isinstance(actual_main_window, QMainWindow): return

         text_to_copy = tag_text_curly
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

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.editor.super_mouseReleaseEvent(event)
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
        self.editor.super_mousePressEvent(event)
        if event.button() == Qt.LeftButton:
             cursor = self.editor.cursorForPosition(event.pos())
             block_number = cursor.blockNumber()
             self.editor.lineClicked.emit(block_number)