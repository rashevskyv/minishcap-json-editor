# --- START OF FILE ui/updaters/preview_updater.py ---
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QTextCursor
from utils.utils import log_debug, convert_spaces_to_dots_for_display
from .base_ui_updater import BaseUIUpdater

class PreviewUpdater(BaseUIUpdater):
    def __init__(self, main_window, data_processor):
        super().__init__(main_window, data_processor)

    def populate_strings_for_block(self, block_idx: int):
        log_debug(f"[PreviewUpdater] populate_strings_for_block for block_idx: {block_idx}. Current string_idx: {self.mw.current_string_idx}")
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit:
            log_debug("[PreviewUpdater] preview_text_edit not found.")
            return

        old_preview_scrollbar_value = preview_edit.verticalScrollBar().value()
        
        # Зберігаємо поточний стан, щоб уникнути рекурсії або зайвих оновлень
        # Цей прапор вже встановлюється у викликаючих методах (наприклад, block_selected)
        # was_programmatically_changing = self.mw.is_programmatically_changing_text
        # self.mw.is_programmatically_changing_text = True 
        
        if hasattr(preview_edit, 'highlightManager'): 
            preview_edit.highlightManager.clearAllProblemHighlights() # Очищаємо тільки для preview

        preview_lines = []
        if block_idx < 0 or not self.mw.data or block_idx >= len(self.mw.data) or not isinstance(self.mw.data[block_idx], list):
            if preview_edit.toPlainText() != "": # Очищаємо тільки якщо є що очищати
                 preview_edit.setPlainText("")
            if hasattr(preview_edit, 'lineNumberArea'): 
                preview_edit.lineNumberArea.update()
            # self.mw.is_programmatically_changing_text = was_programmatically_changing
            return
        
        for i in range(len(self.mw.data[block_idx])):
            text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, i)
            # Використовуємо self.mw.current_game_rules для отримання представлення тексту, якщо воно визначено
            if self.mw.current_game_rules and hasattr(self.mw.current_game_rules, 'get_text_representation_for_preview'):
                preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
            else: # Fallback, якщо немає плагіна або методу
                text_with_converted_spaces = convert_spaces_to_dots_for_display(str(text_for_preview_raw), self.mw.show_multiple_spaces_as_dots)
                preview_line_text = text_with_converted_spaces.replace('\n', getattr(self.mw, "newline_display_symbol", "↵"))
            preview_lines.append(preview_line_text)
        
        current_preview_text = "\n".join(preview_lines)
        if preview_edit.toPlainText() != current_preview_text:
             preview_edit.setPlainText(current_preview_text)
        
        if self.mw.current_string_idx != -1 and \
           hasattr(preview_edit, 'highlightManager') and \
           0 <= self.mw.current_string_idx < preview_edit.document().blockCount(): 
            preview_edit.highlightManager.setPreviewSelectedLineHighlight(self.mw.current_string_idx)
        elif hasattr(preview_edit, 'highlightManager'): # Якщо рядок не вибрано, знімаємо підсвітку
             preview_edit.highlightManager.clearPreviewSelectedLineHighlight()


        preview_edit.verticalScrollBar().setValue(old_preview_scrollbar_value)
        
        if hasattr(preview_edit, 'lineNumberArea'): 
            preview_edit.lineNumberArea.update()

        # self.mw.is_programmatically_changing_text = was_programmatically_changing
        log_debug("[PreviewUpdater] populate_strings_for_block: Finished.")