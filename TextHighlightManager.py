# TextHighlightManager.py
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtGui import QColor, QTextBlockFormat, QTextFormat, QTextCursor, QTextCharFormat
from PyQt5.QtCore import QTimer
from typing import Optional, List, Tuple
import re

class TextHighlightManager:
    def __init__(self, editor):
        self.editor = editor # Зберігаємо посилання на LineNumberedTextEdit
        
        # Списки для зберігання виділень
        self._active_line_selections = [] 
        self._linked_cursor_selections = []
        self._critical_problem_selections = []
        self._warning_problem_selections = []
        self._preview_selected_line_selections = []
        self._tag_interaction_selections = []
        
        # Таймер для тимчасового підсвічування
        self._tag_highlight_timer = QTimer()
        self._tag_highlight_timer.setSingleShot(True)
        self._tag_highlight_timer.timeout.connect(self.clearTagInteractionHighlight)

    # --- Допоміжна функція ---
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
            # Для проблем краще виділяти весь текст блоку, а не тільки фон
            cursor.select(QTextCursor.BlockUnderCursor) 
            selection.cursor = cursor
        return selection

    # --- Метод для застосування всіх виділень ---
    def applyHighlights(self):
        """Збирає всі активні виділення та застосовує їх до редактора."""
        all_selections = []
        # Порядок важливий для накладання кольорів
        if self._active_line_selections: all_selections.extend(list(self._active_line_selections)) 
        if self._linked_cursor_selections: 
            all_selections.extend([s for s in self._linked_cursor_selections if s.format.property(QTextFormat.FullWidthSelection)]) 
        if self._preview_selected_line_selections: all_selections.extend(list(self._preview_selected_line_selections)) 
        
        if self._critical_problem_selections: all_selections.extend(list(self._critical_problem_selections))
        if self._warning_problem_selections: all_selections.extend(list(self._warning_problem_selections))
        
        if self._linked_cursor_selections: 
            all_selections.extend([s for s in self._linked_cursor_selections if not s.format.property(QTextFormat.FullWidthSelection)]) 
        if self._tag_interaction_selections: all_selections.extend(list(self._tag_interaction_selections)) 
        
        self.editor.setExtraSelections(all_selections)
        # Після застосування оновлюємо і LineNumberArea
        self.editor.lineNumberArea.update()

    # --- Методи для керування різними типами підсвічування ---

    # Активний рядок в редагованому полі
    def updateCurrentLineHighlight(self): 
        new_selections = [] 
        # Цей метод викликається тільки для редагованого поля
        if not self.editor.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            # Використовуємо колір з редактора
            selection.format.setBackground(self.editor.current_line_color) 
            selection.format.setProperty(QTextFormat.FullWidthSelection, True) 
            selection.cursor = self.editor.textCursor()
            selection.cursor.clearSelection()
            new_selections.append(selection)
            
        if list(self._active_line_selections) != list(new_selections):
            self._active_line_selections = new_selections
            self.applyHighlights()

    def clearCurrentLineHighlight(self):
        if self._active_line_selections:
             self._active_line_selections = []
             self.applyHighlights()

    # Зв'язаний курсор (для original_text_edit)
    def setLinkedCursorPosition(self, line_number: int, column_number: int): 
        new_linked_selections = [] 
        doc = self.editor.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                # Використовуємо кольори з редактора
                line_sel = self._create_block_background_selection(block, self.editor.linked_cursor_block_color, use_full_width=True) 
                if line_sel: new_linked_selections.append(line_sel)
                
                line_text_length = len(block.text()); actual_column = min(column_number, line_text_length)
                pos_sel_obj = QTextEdit.ExtraSelection()
                cursor_for_pos = QTextCursor(block)
                cursor_for_pos.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, actual_column)
                pos_format = QTextCharFormat(); pos_format.setBackground(self.editor.linked_cursor_pos_color) 
                pos_sel_obj.format = pos_format
                temp_cursor_highlight = QTextCursor(cursor_for_pos)
                if actual_column < line_text_length: 
                    temp_cursor_highlight.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
                elif actual_column == line_text_length and line_text_length > 0 : 
                    if temp_cursor_highlight.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1):
                         temp_cursor_highlight.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1) 

                if temp_cursor_highlight.hasSelection(): 
                    pos_sel_obj.cursor = temp_cursor_highlight
                    new_linked_selections.append(pos_sel_obj)
                elif actual_column == 0 and line_text_length == 0:
                     pass 

        if list(self._linked_cursor_selections) != list(new_linked_selections):
            self._linked_cursor_selections = new_linked_selections
            self.applyHighlights()

    def clearLinkedCursorPosition(self):
         if self._linked_cursor_selections:
              self._linked_cursor_selections = []
              self.applyHighlights()

    # Виділення рядка в прев'ю
    def setPreviewSelectedLineHighlight(self, line_number: int): 
        new_selections = []
        doc = self.editor.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            # Використовуємо колір з редактора
            selection = self._create_block_background_selection(block, self.editor.preview_selected_line_color, use_full_width=True)
            if selection: new_selections.append(selection)
            
        if list(self._preview_selected_line_selections) != list(new_selections):
            self._preview_selected_line_selections = new_selections
            self.applyHighlights()

    def clearPreviewSelectedLineHighlight(self):
        if self._preview_selected_line_selections:
            self._preview_selected_line_selections = []
            self.applyHighlights()

    # Критичні проблеми
    def addCriticalProblemHighlight(self, line_number: int):
        doc = self.editor.document()
        needs_update = False
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                is_already_added = any(s.cursor.blockNumber() == line_number for s in self._critical_problem_selections)
                if not is_already_added:
                    selection = self._create_block_background_selection(block, self.editor.critical_problem_line_color, use_full_width=False) 
                    if selection: 
                        self._critical_problem_selections.append(selection)
                        needs_update = True
        if needs_update:
             self.applyHighlights()

    def removeCriticalProblemHighlight(self, line_number: int) -> bool:
        removed = False; initial_len = len(self._critical_problem_selections)
        self._critical_problem_selections = [s for s in self._critical_problem_selections if s.cursor.blockNumber() != line_number]
        if len(self._critical_problem_selections) < initial_len: 
            removed = True
            self.applyHighlights()
        return removed

    def clearCriticalProblemHighlights(self):
        needs_update = bool(self._critical_problem_selections)
        self._critical_problem_selections = []
        if needs_update: self.applyHighlights()

    def hasCriticalProblemHighlight(self, line_number: Optional[int] = None) -> bool:
        if line_number is not None: return any(s.cursor.blockNumber() == line_number for s in self._critical_problem_selections)
        return bool(self._critical_problem_selections)

    # Попередження
    def addWarningLineHighlight(self, line_number: int):
        doc = self.editor.document()
        needs_update = False
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                is_already_added = any(s.cursor.blockNumber() == line_number for s in self._warning_problem_selections)
                if not is_already_added:
                    selection = self._create_block_background_selection(block, self.editor.warning_problem_line_color, use_full_width=False) 
                    if selection: 
                        self._warning_problem_selections.append(selection)
                        needs_update = True
        if needs_update:
             self.applyHighlights()

    def removeWarningLineHighlight(self, line_number: int) -> bool:
        removed = False; initial_len = len(self._warning_problem_selections)
        self._warning_problem_selections = [s for s in self._warning_problem_selections if s.cursor.blockNumber() != line_number]
        if len(self._warning_problem_selections) < initial_len: 
            removed = True
            self.applyHighlights()
        return removed

    def clearWarningLineHighlights(self):
        needs_update = bool(self._warning_problem_selections)
        self._warning_problem_selections = []
        if needs_update: self.applyHighlights()

    def hasWarningLineHighlight(self, line_number: Optional[int] = None) -> bool:
        if line_number is not None: return any(s.cursor.blockNumber() == line_number for s in self._warning_problem_selections)
        return bool(self._warning_problem_selections)

    # Взаємодія з тегами
    def momentaryHighlightTag(self, block, start_in_block, length):
        if not block.isValid(): return
        self.clearTagInteractionHighlight() # Очищаємо попереднє, якщо є
        selection = QTextEdit.ExtraSelection()
        # Використовуємо колір з редактора
        selection.format.setBackground(self.editor.tag_interaction_highlight_color)
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + start_in_block)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        selection.cursor = cursor
        self._tag_interaction_selections.append(selection)
        self.applyHighlights()
        self._tag_highlight_timer.start(300) # Запускаємо таймер для очищення

    def clearTagInteractionHighlight(self):
        if self._tag_interaction_selections:
            self._tag_interaction_selections = []
            self.applyHighlights()

    # Загальні методи очищення
    def clearAllProblemHighlights(self):
        needs_update = bool(self._critical_problem_selections) or bool(self._warning_problem_selections)
        self._critical_problem_selections = []
        self._warning_problem_selections = []
        if needs_update: self.applyHighlights()
        
    def clearAllHighlights(self):
        """Очищає всі типи виділень."""
        self._active_line_selections = [] 
        self._linked_cursor_selections = []
        self._critical_problem_selections = []
        self._warning_problem_selections = []
        self._preview_selected_line_selections = []
        self._tag_interaction_selections = []
        self.applyHighlights() # Застосовуємо порожній список