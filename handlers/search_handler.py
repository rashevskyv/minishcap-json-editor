from handlers.base_handler import BaseHandler
from utils import log_debug, convert_spaces_to_dots_for_display, remove_curly_tags, convert_raw_to_display_text
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QTextCursor
from PyQt5.QtWidgets import QApplication

class SearchHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self.current_query = ""
        self.is_case_sensitive = False
        self.search_in_original = False
        self.last_found_block = -1
        self.last_found_string = -1
        self.last_found_char_pos_raw = -1 
        self.search_results = []
        self.current_search_index = -1
        
    def _get_text_for_search(self, block_idx: int, string_idx: int, search_in_original_flag: bool) -> str:
        text_to_search = ""
        if search_in_original_flag:
            if 0 <= block_idx < len(self.mw.data) and \
               isinstance(self.mw.data[block_idx], list) and \
               0 <= string_idx < len(self.mw.data[block_idx]):
                text_to_search = self.mw.data[block_idx][string_idx]
        else:
            text_to_search, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        
        return str(text_to_search) if text_to_search is not None else ""

    def reset_search(self, new_query: str = "", new_case_sensitive: bool = False, new_search_in_original: bool = False):
        log_debug(f"SearchHandler: Resetting search. Query: '{new_query}', Case: {new_case_sensitive}, Original: {new_search_in_original}")
        self.current_query = new_query
        self.is_case_sensitive = new_case_sensitive
        self.search_in_original = new_search_in_original
        self.last_found_block = -1
        self.last_found_string = -1
        self.last_found_char_pos_raw = -1
        self.current_search_results = []
        self.current_search_index = -1
        self.clear_all_search_highlights()
        self.mw.search_match_block_indices.clear()
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.viewport().update()
        if hasattr(self.mw, 'search_panel_widget'):
            self.mw.search_panel_widget.clear_status()


    def find_next(self, query: str, case_sensitive: bool, search_in_original: bool):
        log_debug(f"SearchHandler: find_next called. Q: '{query}', Case: {case_sensitive}, Original: {search_in_original}")
        
        if not query:
            if hasattr(self.mw, 'search_panel_widget'):
                self.mw.search_panel_widget.set_status_message("Введіть запит", is_error=True)
            return

        if (self.current_query != query or 
            self.is_case_sensitive != case_sensitive or 
            self.search_in_original != search_in_original):
            self.reset_search(query, case_sensitive, search_in_original)
        
        self.current_query = query 
        self.is_case_sensitive = case_sensitive
        self.search_in_original = search_in_original

        if not self.mw.data:
            if hasattr(self.mw, 'search_panel_widget'):
                self.mw.search_panel_widget.set_status_message("Немає даних для пошуку", is_error=True)
            return
        
        start_block_data_idx = self.last_found_block if self.last_found_block != -1 else 0
        start_string_data_idx = self.last_found_string if self.last_found_string != -1 else 0
        start_char_raw_offset = self.last_found_char_pos_raw + 1 if self.last_found_char_pos_raw != -1 else 0
        
        for b_idx in range(start_block_data_idx, len(self.mw.data)):
            if not isinstance(self.mw.data[b_idx], list):
                continue
            
            current_block_data_list = self.mw.data[b_idx]
            s_idx_start_loop_offset = start_string_data_idx if b_idx == start_block_data_idx else 0
            
            for s_idx in range(s_idx_start_loop_offset, len(current_block_data_list)):
                current_char_raw_search_offset = start_char_raw_offset if b_idx == start_block_data_idx and s_idx == start_string_data_idx else 0
                text_to_search_in_raw = self._get_text_for_search(b_idx, s_idx, self.search_in_original)
                
                compare_text_raw = text_to_search_in_raw
                compare_query_raw = self.current_query
                
                if not self.is_case_sensitive:
                    compare_text_raw = text_to_search_in_raw.lower()
                    compare_query_raw = self.current_query.lower()
                
                match_pos_raw = compare_text_raw.find(compare_query_raw, current_char_raw_search_offset)
                
                if match_pos_raw != -1:
                    log_debug(f"Found match in raw text at DataBlock {b_idx}, DataString {s_idx}, RawCharPos {match_pos_raw}")
                    self.last_found_block = b_idx
                    self.last_found_string = s_idx
                    self.last_found_char_pos_raw = match_pos_raw
                    
                    self._navigate_to_match(b_idx, s_idx, match_pos_raw, len(self.current_query))
                    if hasattr(self.mw, 'search_panel_widget'):
                        self.mw.search_panel_widget.set_status_message(f"Знайдено: Б{b_idx+1}, Р{s_idx+1}")
                    return
            
            start_string_data_idx = 0 
            start_char_raw_offset = 0   

        if hasattr(self.mw, 'search_panel_widget'):
            self.mw.search_panel_widget.set_status_message("Не знайдено (кінець)")
        self.last_found_block = -1 
        self.last_found_string = -1
        self.last_found_char_pos_raw = -1


    def find_previous(self, query: str, case_sensitive: bool, search_in_original: bool):
        log_debug(f"SearchHandler: find_previous called. Q: '{query}', Case: {case_sensitive}, Original: {search_in_original}")
        
        if not query:
            if hasattr(self.mw, 'search_panel_widget'):
                self.mw.search_panel_widget.set_status_message("Введіть запит", is_error=True)
            return

        if (self.current_query != query or 
            self.is_case_sensitive != case_sensitive or 
            self.search_in_original != search_in_original):
            self.reset_search(query, case_sensitive, search_in_original)

        self.current_query = query
        self.is_case_sensitive = case_sensitive
        self.search_in_original = search_in_original
            
        if not self.mw.data:
            if hasattr(self.mw, 'search_panel_widget'):
                self.mw.search_panel_widget.set_status_message("Немає даних для пошуку", is_error=True)
            return

        start_block_data_idx = self.last_found_block if self.last_found_block != -1 else len(self.mw.data) - 1
        start_string_data_idx = self.last_found_string if self.last_found_string != -1 else -1 
        start_char_raw_search_from = self.last_found_char_pos_raw -1 if self.last_found_char_pos_raw != -1 else -1 
        
        for b_idx in range(start_block_data_idx, -1, -1):
            if not isinstance(self.mw.data[b_idx], list):
                continue
            
            current_block_data_list = self.mw.data[b_idx]
            s_idx_start_loop_offset = (start_string_data_idx if b_idx == start_block_data_idx and start_string_data_idx != -1 
                                  else len(current_block_data_list) - 1)
            
            for s_idx in range(s_idx_start_loop_offset, -1, -1):
                text_to_search_in_raw = self._get_text_for_search(b_idx, s_idx, self.search_in_original)
                
                current_char_raw_search_from = (start_char_raw_search_from 
                                           if b_idx == start_block_data_idx and s_idx == start_string_data_idx and start_char_raw_search_from != -1
                                           else len(text_to_search_in_raw) -1 )

                compare_text_raw = text_to_search_in_raw
                compare_query_raw = self.current_query

                if not self.is_case_sensitive:
                    compare_text_raw = text_to_search_in_raw.lower()
                    compare_query_raw = self.current_query.lower()
                
                idx_raw = current_char_raw_search_from
                found_pos_raw = -1
                if not compare_query_raw: continue

                while idx_raw >= 0:
                    temp_pos_raw = compare_text_raw.rfind(compare_query_raw, 0, idx_raw + 1)
                    if temp_pos_raw != -1:
                        found_pos_raw = temp_pos_raw
                        break
                    idx_raw -=1 
                    if idx_raw < 0: break 
                
                if found_pos_raw != -1:
                    log_debug(f"Found (prev) match in raw text at DataBlock {b_idx}, DataString {s_idx}, RawCharPos {found_pos_raw}")
                    self.last_found_block = b_idx
                    self.last_found_string = s_idx
                    self.last_found_char_pos_raw = found_pos_raw
                    
                    self._navigate_to_match(b_idx, s_idx, found_pos_raw, len(self.current_query))
                    if hasattr(self.mw, 'search_panel_widget'):
                        self.mw.search_panel_widget.set_status_message(f"Знайдено: Б{b_idx+1}, Р{s_idx+1}")
                    return
            
            start_string_data_idx = -1 
            start_char_raw_search_from = -1   

        if hasattr(self.mw, 'search_panel_widget'):
             self.mw.search_panel_widget.set_status_message("Не знайдено (початок)")
        self.last_found_block = -1 
        self.last_found_string = -1
        self.last_found_char_pos_raw = -1

    def _find_nth_occurrence_in_display_text(self, display_text: str, display_query: str, target_occurrence: int, case_sensitive: bool) -> tuple[int, int]:
        current_occurrence = 0
        search_start_pos = 0
        
        text_to_scan = display_text
        query_to_scan = display_query
        if not case_sensitive:
            text_to_scan = display_text.lower()
            query_to_scan = display_query.lower()

        if not query_to_scan: return -1, -1

        while True:
            match_pos = text_to_scan.find(query_to_scan, search_start_pos)
            if match_pos == -1:
                return -1, -1 
            
            current_occurrence += 1
            if current_occurrence == target_occurrence:
                return match_pos, len(display_query) # Повертаємо довжину display_query
            
            search_start_pos = match_pos + 1 
            if search_start_pos >= len(text_to_scan): 
                return -1, -1

    def _calculate_qtextblock_and_pos_in_block(self, raw_text_line: str, char_pos_in_raw_string: int) -> tuple[int, int]:
        qtextblock_idx = 0
        pos_in_qtextblock = char_pos_in_raw_string
        
        last_newline_pos = -1
        current_pos = 0
        while current_pos < char_pos_in_raw_string:
            newline_found_at = raw_text_line.find('\n', current_pos)
            if newline_found_at != -1 and newline_found_at < char_pos_in_raw_string:
                qtextblock_idx += 1
                last_newline_pos = newline_found_at
                current_pos = newline_found_at + 1
            else:
                break 
        
        if last_newline_pos != -1:
            pos_in_qtextblock = char_pos_in_raw_string - (last_newline_pos + 1)
        
        return qtextblock_idx, pos_in_qtextblock

    def _navigate_to_match(self, block_idx_match_in_data, string_idx_match_in_data, char_pos_in_raw_string, match_length_in_raw_string):
        log_debug(f"Navigating to Data: B:{block_idx_match_in_data}, S:{string_idx_match_in_data}, RawC:{char_pos_in_raw_string}, RawL:{match_length_in_raw_string}")
        
        self.clear_all_search_highlights()

        if self.mw.current_block_idx != block_idx_match_in_data:
            self.mw.block_list_widget.setCurrentRow(block_idx_match_in_data)
        
        if self.mw.current_string_idx != string_idx_match_in_data or self.mw.current_block_idx != block_idx_match_in_data:
             self.mw.list_selection_handler.string_selected_from_preview(string_idx_match_in_data)
        
        QApplication.processEvents()

        # Цей "рядок даних" може містити \n
        raw_full_string_data = self._get_text_for_search(block_idx_match_in_data, string_idx_match_in_data, self.search_in_original)
        
        # 1. Визначаємо, в якому QTextBlock (після розбиття по \n) знаходиться наш збіг,
        #    і яка його позиція всередині цього QTextBlock.
        target_qtextblock_idx_in_editor, char_pos_in_target_qtextblock_raw = \
            self._calculate_qtextblock_and_pos_in_block(raw_full_string_data, char_pos_in_raw_string)
        
        log_debug(f"Match is in QTextBlk(editor): {target_qtextblock_idx_in_editor}, RawCharInBlk: {char_pos_in_target_qtextblock_raw}")

        # 2. Визначаємо, яке це за порядком входження запиту *всередині цього конкретного QTextBlock (сирого)*
        # Спочатку отримуємо текст цього конкретного QTextBlock з сирих даних
        raw_qtextblocks = raw_full_string_data.split('\n')
        if target_qtextblock_idx_in_editor >= len(raw_qtextblocks):
            log_debug(f"ERROR: target_qtextblock_idx_in_editor ({target_qtextblock_idx_in_editor}) is out of bounds for raw_qtextblocks (len {len(raw_qtextblocks)})")
            return
        
        raw_text_of_target_qtextblock = raw_qtextblocks[target_qtextblock_idx_in_editor]

        compare_raw_qtextblock_text = raw_text_of_target_qtextblock
        compare_raw_query_for_occurrence = self.current_query # Для original_text_edit, теги з запиту треба буде видалити нижче

        if not self.is_case_sensitive:
            compare_raw_qtextblock_text = raw_text_of_target_qtextblock.lower()
            compare_raw_query_for_occurrence = self.current_query.lower()

        occurrence_in_qtextblock_raw = 0
        temp_pos_qblk = -1
        search_offset_qblk = 0
        
        # Адаптуємо compare_raw_query_for_occurrence для original_text_edit
        temp_query_for_original = remove_curly_tags(compare_raw_query_for_occurrence) if self.search_in_original else compare_raw_query_for_occurrence

        if temp_query_for_original: # Використовуємо адаптований запит для підрахунку входжень
            while search_offset_qblk <= char_pos_in_target_qtextblock_raw:
                # Для original_text_edit, сам текст блоку теж має бути без тегів для коректного підрахунку
                text_for_occurrence_count = remove_curly_tags(compare_raw_qtextblock_text) if self.search_in_original else compare_raw_qtextblock_text
                
                temp_pos_qblk = text_for_occurrence_count.find(temp_query_for_original, search_offset_qblk)
                
                if temp_pos_qblk == -1 or temp_pos_qblk > char_pos_in_target_qtextblock_raw:
                    break
                occurrence_in_qtextblock_raw += 1
                if temp_pos_qblk == char_pos_in_target_qtextblock_raw: # Якщо знайшли точно на потрібній позиції
                    break
                search_offset_qblk = temp_pos_qblk + 1
        
        if occurrence_in_qtextblock_raw == 0 and temp_query_for_original:
            log_debug(f"ERROR: Could not determine occurrence_in_qtextblock_raw for match in raw_text_of_target_qtextblock ('{raw_text_of_target_qtextblock}') at raw_pos {char_pos_in_target_qtextblock_raw}")
            # Спробуємо знайти хоча б перше входження, якщо точне не вдалося
            occurrence_in_qtextblock_raw = 1 


        log_debug(f"Match is the {occurrence_in_qtextblock_raw}-th occurrence in its raw QTextBlock.")


        editors_to_process = [
            (self.mw.preview_text_edit, True, string_idx_match_in_data),  # string_idx_match_in_data для preview
            (self.mw.original_text_edit, False, target_qtextblock_idx_in_editor), 
            (self.mw.edited_text_edit, False, target_qtextblock_idx_in_editor)
        ]

        for editor, use_newline_symbol, widget_qtextblock_idx_to_use in editors_to_process:
            editor_name = editor.objectName() if editor.objectName() else "UnnamedEditor"
            
            if not editor or not hasattr(editor, 'highlightManager'):
                log_debug(f"Skipping editor {editor_name} (no highlightManager or editor is None)")
                continue
            
            if (editor == self.mw.original_text_edit or editor == self.mw.edited_text_edit) and \
               string_idx_match_in_data != self.mw.current_string_idx:
                log_debug(f"Skipping editor {editor_name} as its current data string ({self.mw.current_string_idx}) doesn't match found data string ({string_idx_match_in_data})")
                continue
            
            widget_block = editor.document().findBlockByNumber(widget_qtextblock_idx_to_use)
            if not widget_block.isValid():
                log_debug(f"Skipping editor {editor_name} (QTextBlock for index {widget_qtextblock_idx_to_use} is invalid)")
                continue
            
            text_in_widget_qtextblock = widget_block.text() 
            log_debug(f"Editor: {editor_name} (QTextBlk idx: {widget_qtextblock_idx_to_use}), text_in_widget_QTextBlk: '{text_in_widget_qtextblock[:100]}...'")

            query_for_this_editor_raw = self.current_query
            if editor == self.mw.original_text_edit: 
                query_for_this_editor_raw = remove_curly_tags(self.current_query)
            
            display_query_for_widget = convert_raw_to_display_text(
                query_for_this_editor_raw, 
                self.mw.show_multiple_spaces_as_dots,
                self.mw.newline_display_symbol if use_newline_symbol else ""
            )
            log_debug(f"Editor: {editor_name}, display_query_for_widget: '{display_query_for_widget}' (target occurrence: {occurrence_in_qtextblock_raw})")
            
            match_pos_in_widget_qtextblock, match_len_in_widget_qtextblock = self._find_nth_occurrence_in_display_text(
                text_in_widget_qtextblock, display_query_for_widget, occurrence_in_qtextblock_raw, self.is_case_sensitive
            )

            if match_pos_in_widget_qtextblock != -1:
                editor.highlightManager.add_search_match_highlight(widget_qtextblock_idx_to_use, match_pos_in_widget_qtextblock, match_len_in_widget_qtextblock)
                log_debug(f"Highlighting in {editor_name}: QTextBlk(widget):{widget_qtextblock_idx_to_use}, DispPosInBlk:{match_pos_in_widget_qtextblock}, DispLen:{match_len_in_widget_qtextblock}")
                
                cursor = QTextCursor(widget_block)
                cursor.setPosition(widget_block.position() + match_pos_in_widget_qtextblock + match_len_in_widget_qtextblock)
                cursor.clearSelection() 
                editor.setTextCursor(cursor)
                editor.ensureCursorVisible() 
            else:
                log_debug(f"Could not find {occurrence_in_qtextblock_raw}-th occurrence of query in {editor_name}'s QTextBlock idx {widget_qtextblock_idx_to_use}")

        self.mw.search_match_block_indices.add(block_idx_match_in_data)
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.viewport().update()

    def clear_all_search_highlights(self):
        log_debug("SearchHandler: Clearing all search highlights.")
        for editor in [self.mw.preview_text_edit, self.mw.original_text_edit, self.mw.edited_text_edit]:
            if editor and hasattr(editor, 'highlightManager'):
                editor.highlightManager.clear_search_match_highlights()