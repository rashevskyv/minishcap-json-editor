from handlers.base_handler import BaseHandler
from utils import log_debug, convert_spaces_to_dots_for_display, remove_curly_tags, convert_raw_to_display_text, prepare_text_for_tagless_search
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QTextCursor
from PyQt5.QtWidgets import QApplication
import re

class SearchHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self.current_query = ""
        self.is_case_sensitive = False
        self.search_in_original = False
        self.ignore_tags_newlines = True 
        self.last_found_block = -1
        self.last_found_string = -1
        self.last_found_char_pos_raw = -1 
        self.search_results = []
        self.current_search_index = -1
        
    def get_current_search_params(self) -> tuple[str, bool, bool, bool]:
        return self.current_query, self.is_case_sensitive, self.search_in_original, self.ignore_tags_newlines

    def _get_text_for_search(self, block_idx: int, string_idx: int, search_in_original_flag: bool, ignore_tags_flag: bool) -> str:
        text_to_process = ""
        if search_in_original_flag:
            if 0 <= block_idx < len(self.mw.data) and \
               isinstance(self.mw.data[block_idx], list) and \
               0 <= string_idx < len(self.mw.data[block_idx]):
                text_to_process = self.mw.data[block_idx][string_idx]
        else:
            text_to_process, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        
        text_to_process = str(text_to_process) if text_to_process is not None else ""

        if ignore_tags_flag:
            return prepare_text_for_tagless_search(text_to_process)
        return text_to_process

    def reset_search(self, new_query: str = "", new_case_sensitive: bool = False, new_search_in_original: bool = False, new_ignore_tags: bool = True):
        log_debug(f"SearchHandler: Resetting search. Q: '{new_query}', Case: {new_case_sensitive}, Orig: {new_search_in_original}, IgnoreTags: {new_ignore_tags}")
        
        self.current_query = new_query 
        self.is_case_sensitive = new_case_sensitive
        self.search_in_original = new_search_in_original
        self.ignore_tags_newlines = new_ignore_tags

        self.last_found_block = -1
        self.last_found_string = -1
        self.last_found_char_pos_raw = -1
        self.current_search_results = []
        self.current_search_index = -1
        self.clear_all_search_highlights()
        self.mw.search_match_block_indices.clear()
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.viewport().update()
        if hasattr(self.mw, 'search_panel_widget') and self.mw.search_panel_widget.isVisible(): 
            self.mw.search_panel_widget.clear_status()

    def _find_in_text(self, text_to_search_in: str, query_to_find: str, start_offset: int, case_sensitive: bool, find_reverse: bool = False) -> int:
        compare_text = text_to_search_in
        compare_query = query_to_find
        if not case_sensitive:
            compare_text = text_to_search_in.lower()
            compare_query = query_to_find.lower()
        
        if not compare_query: return -1

        if find_reverse:
            return compare_text.rfind(compare_query, 0, start_offset + 1) 
        else:
            return compare_text.find(compare_query, start_offset)


    def find_next(self, query: str, case_sensitive: bool, search_in_original: bool, ignore_tags: bool) -> bool:
        log_debug(f"SearchHandler: find_next. Q: '{query}', Case: {case_sensitive}, Orig: {search_in_original}, IgnoreTags: {ignore_tags}")
        
        effective_query = prepare_text_for_tagless_search(query) if ignore_tags else query
        if not effective_query: 
            if hasattr(self.mw, 'search_panel_widget') and self.mw.search_panel_widget.isVisible():
                self.mw.search_panel_widget.set_status_message("Введіть запит", is_error=True)
            return False

        if (self.current_query != query or 
            self.is_case_sensitive != case_sensitive or 
            self.search_in_original != search_in_original or
            self.ignore_tags_newlines != ignore_tags):
            self.last_found_block = -1; self.last_found_string = -1; self.last_found_char_pos_raw = -1
        
        self.current_query = query 
        self.is_case_sensitive = case_sensitive
        self.search_in_original = search_in_original
        self.ignore_tags_newlines = ignore_tags

        if not self.mw.data: return False
        
        start_block_data_idx = self.last_found_block if self.last_found_block != -1 else 0
        start_string_data_idx = self.last_found_string if self.last_found_string != -1 else 0
        start_char_offset = self.last_found_char_pos_raw + 1 if self.last_found_char_pos_raw != -1 else 0
        
        for b_idx in range(start_block_data_idx, len(self.mw.data)):
            if not isinstance(self.mw.data[b_idx], list): continue
            
            s_idx_start_loop_offset = start_string_data_idx if b_idx == start_block_data_idx else 0
            for s_idx in range(s_idx_start_loop_offset, len(self.mw.data[b_idx])):
                current_char_search_offset = start_char_offset if b_idx == start_block_data_idx and s_idx == start_string_data_idx else 0
                
                text_for_search = self._get_text_for_search(b_idx, s_idx, self.search_in_original, self.ignore_tags_newlines)
                
                match_pos_in_search_text = self._find_in_text(text_for_search, effective_query, current_char_search_offset, self.is_case_sensitive)
                
                if match_pos_in_search_text != -1:
                    log_debug(f"Found match in {'processed' if ignore_tags else 'raw'} text at DataB {b_idx}, DataS {s_idx}, SearchTextPos {match_pos_in_search_text}")
                    self.last_found_block = b_idx
                    self.last_found_string = s_idx
                    self.last_found_char_pos_raw = match_pos_in_search_text 
                    
                    self._navigate_to_match(b_idx, s_idx, match_pos_in_search_text, len(effective_query), self.ignore_tags_newlines)
                    if hasattr(self.mw, 'search_panel_widget') and self.mw.search_panel_widget.isVisible():
                        self.mw.search_panel_widget.set_status_message(f"Знайдено: Б{b_idx+1}, Р{s_idx+1}")
                    return True 
            
            start_string_data_idx = 0 
            start_char_offset = 0   

        if hasattr(self.mw, 'search_panel_widget') and self.mw.search_panel_widget.isVisible():
            self.mw.search_panel_widget.set_status_message("Не знайдено (кінець)")
        self.last_found_block = -1; self.last_found_string = -1; self.last_found_char_pos_raw = -1
        return False 

    def find_previous(self, query: str, case_sensitive: bool, search_in_original: bool, ignore_tags: bool) -> bool:
        log_debug(f"SearchHandler: find_previous. Q: '{query}', Case: {case_sensitive}, Orig: {search_in_original}, IgnoreTags: {ignore_tags}")

        effective_query = prepare_text_for_tagless_search(query) if ignore_tags else query
        if not effective_query:
            if hasattr(self.mw, 'search_panel_widget') and self.mw.search_panel_widget.isVisible():
                self.mw.search_panel_widget.set_status_message("Введіть запит", is_error=True)
            return False

        if (self.current_query != query or 
            self.is_case_sensitive != case_sensitive or 
            self.search_in_original != search_in_original or
            self.ignore_tags_newlines != ignore_tags):
            self.last_found_block = -1; self.last_found_string = -1; self.last_found_char_pos_raw = -1

        self.current_query = query
        self.is_case_sensitive = case_sensitive
        self.search_in_original = search_in_original
        self.ignore_tags_newlines = ignore_tags
            
        if not self.mw.data: return False

        start_block_data_idx = self.last_found_block if self.last_found_block != -1 else len(self.mw.data) - 1
        start_string_data_idx = self.last_found_string if self.last_found_string != -1 else -1 
        start_char_search_from = self.last_found_char_pos_raw -1 if self.last_found_char_pos_raw != -1 else -1 
        
        for b_idx in range(start_block_data_idx, -1, -1):
            if not isinstance(self.mw.data[b_idx], list): continue
            
            s_idx_start_loop_offset = (start_string_data_idx if b_idx == start_block_data_idx and start_string_data_idx != -1 
                                  else len(self.mw.data[b_idx]) - 1)
            
            for s_idx in range(s_idx_start_loop_offset, -1, -1):
                text_for_search = self._get_text_for_search(b_idx, s_idx, self.search_in_original, self.ignore_tags_newlines)
                
                current_char_search_from = (start_char_search_from 
                                           if b_idx == start_block_data_idx and s_idx == start_string_data_idx and start_char_search_from != -1
                                           else len(text_for_search) -1 )
                
                match_pos_in_search_text = self._find_in_text(text_for_search, effective_query, current_char_search_from, self.is_case_sensitive, find_reverse=True)
                
                if match_pos_in_search_text != -1:
                    log_debug(f"Found (prev) match in {'processed' if ignore_tags else 'raw'} text at DataB {b_idx}, DataS {s_idx}, SearchTextPos {match_pos_in_search_text}")
                    self.last_found_block = b_idx
                    self.last_found_string = s_idx
                    self.last_found_char_pos_raw = match_pos_in_search_text
                    
                    self._navigate_to_match(b_idx, s_idx, match_pos_in_search_text, len(effective_query), self.ignore_tags_newlines)
                    if hasattr(self.mw, 'search_panel_widget') and self.mw.search_panel_widget.isVisible():
                        self.mw.search_panel_widget.set_status_message(f"Знайдено: Б{b_idx+1}, Р{s_idx+1}")
                    return True 
            
            start_string_data_idx = -1 
            start_char_search_from = -1   

        if hasattr(self.mw, 'search_panel_widget') and self.mw.search_panel_widget.isVisible():
             self.mw.search_panel_widget.set_status_message("Не знайдено (початок)")
        self.last_found_block = -1; self.last_found_string = -1; self.last_found_char_pos_raw = -1
        return False 

    def _find_nth_occurrence_in_display_text(self, display_text: str, display_query: str, target_occurrence: int, case_sensitive: bool) -> tuple[int, int]:
        current_occurrence = 0; search_start_pos = 0
        text_to_scan = display_text; query_to_scan = display_query
        if not case_sensitive:
            text_to_scan = display_text.lower(); query_to_scan = display_query.lower()
        if not query_to_scan: return -1, -1
        while True:
            match_pos = text_to_scan.find(query_to_scan, search_start_pos)
            if match_pos == -1: return -1, -1 
            current_occurrence += 1
            if current_occurrence == target_occurrence: return match_pos, len(display_query) 
            search_start_pos = match_pos + 1 
            if search_start_pos >= len(text_to_scan): return -1, -1

    def _calculate_qtextblock_and_pos_in_block(self, raw_text_line_with_newlines: str, char_pos_in_raw_string_with_newlines: int) -> tuple[int, int]:
        qtextblock_idx = 0; pos_in_qtextblock = char_pos_in_raw_string_with_newlines
        last_newline_pos = -1; current_pos = 0
        while current_pos < char_pos_in_raw_string_with_newlines:
            newline_found_at = raw_text_line_with_newlines.find('\n', current_pos)
            if newline_found_at != -1 and newline_found_at < char_pos_in_raw_string_with_newlines:
                qtextblock_idx += 1; last_newline_pos = newline_found_at; current_pos = newline_found_at + 1
            else: break 
        if last_newline_pos != -1: pos_in_qtextblock = char_pos_in_raw_string_with_newlines - (last_newline_pos + 1)
        return qtextblock_idx, pos_in_qtextblock

    def _navigate_to_match(self, block_idx_match_in_data, string_idx_match_in_data, 
                           char_pos_in_search_text: int, match_len_in_search_text: int, 
                           was_search_tagless_and_newline_agnostic: bool):
        log_debug(f"Navigating. Data: B:{block_idx_match_in_data}, S:{string_idx_match_in_data}. SearchTextPos:{char_pos_in_search_text}, SearchTextLen:{match_len_in_search_text}, TaglessNLSearch:{was_search_tagless_and_newline_agnostic}")
        self.clear_all_search_highlights()
        if self.mw.current_block_idx != block_idx_match_in_data: self.mw.block_list_widget.setCurrentRow(block_idx_match_in_data)
        if self.mw.current_string_idx != string_idx_match_in_data or self.mw.current_block_idx != block_idx_match_in_data:
             self.mw.list_selection_handler.string_selected_from_preview(string_idx_match_in_data)
        QApplication.processEvents()

        if was_search_tagless_and_newline_agnostic:
            temp_query_for_words = self.current_query
            # Регістр для слів запиту вже враховано в self.is_case_sensitive при пошуку
            query_words_for_display_search = prepare_text_for_tagless_search(temp_query_for_words, keep_original_case=True).split()

            if not query_words_for_display_search: return

            for editor in [self.mw.preview_text_edit, self.mw.original_text_edit, self.mw.edited_text_edit]:
                editor_name = editor.objectName() if editor.objectName() else "UnnamedEditor"
                if not editor or not hasattr(editor, 'highlightManager'): continue
                
                if (editor == self.mw.original_text_edit or editor == self.mw.edited_text_edit) and \
                   string_idx_match_in_data != self.mw.current_string_idx:
                    log_debug(f"TaglessSearch: Skipping {editor_name}, string mismatch for original/edited.")
                    continue

                found_overall_match_in_editor = False
                # Для preview ми обробляємо один QTextBlock, для original/edited - потенційно декілька
                qtextblock_start_idx = string_idx_match_in_data if editor == self.mw.preview_text_edit else 0
                qtextblock_end_idx = string_idx_match_in_data if editor == self.mw.preview_text_edit else editor.document().blockCount() - 1

                for current_widget_qblock_idx in range(qtextblock_start_idx, qtextblock_end_idx + 1):
                    widget_block = editor.document().findBlockByNumber(current_widget_qblock_idx)
                    if not widget_block.isValid(): continue
                    text_in_widget_qtextblock = widget_block.text()

                    # Шукаємо перше слово
                    first_word_display = convert_raw_to_display_text(query_words_for_display_search[0], self.mw.show_multiple_spaces_as_dots, self.mw.newline_display_symbol if editor == self.mw.preview_text_edit else "")
                    if editor == self.mw.original_text_edit: first_word_display = remove_curly_tags(first_word_display)
                    
                    current_search_offset_in_qblock = 0
                    while current_search_offset_in_qblock < len(text_in_widget_qtextblock):
                        start_pos = self._find_in_text(text_in_widget_qtextblock, first_word_display, current_search_offset_in_qblock, self.is_case_sensitive)
                        if start_pos == -1: break # Перше слово не знайдено в цьому блоці з поточного offset

                        highlight_start_qblock_idx = current_widget_qblock_idx
                        highlight_start_pos_in_qblock = start_pos
                        highlight_end_qblock_idx = current_widget_qblock_idx
                        highlight_end_pos_in_qblock_end_of_word = start_pos + len(first_word_display)
                        
                        all_words_found_sequentially = True
                        if len(query_words_for_display_search) > 1:
                            temp_offset_for_next_words = highlight_end_pos_in_qblock_end_of_word
                            temp_current_qblock_for_next_words = current_widget_qblock_idx

                            for i in range(1, len(query_words_for_display_search)):
                                next_word_orig = query_words_for_display_search[i]
                                next_word_display = convert_raw_to_display_text(next_word_orig, self.mw.show_multiple_spaces_as_dots, self.mw.newline_display_symbol if editor == self.mw.preview_text_edit else "")
                                if editor == self.mw.original_text_edit: next_word_display = remove_curly_tags(next_word_display)

                                found_current_next_word = False
                                for j in range(temp_current_qblock_for_next_words, editor.document().blockCount()):
                                    block_to_search_next_word = editor.document().findBlockByNumber(j)
                                    if not block_to_search_next_word.isValid(): all_words_found_sequentially=False; break
                                    text_of_block_to_search_next = block_to_search_next_word.text()
                                    
                                    search_from_in_next_block = temp_offset_for_next_words if j == temp_current_qblock_for_next_words else 0
                                    
                                    next_pos = self._find_in_text(text_of_block_to_search_next, next_word_display, search_from_in_next_block, self.is_case_sensitive)
                                    if next_pos != -1:
                                        highlight_end_qblock_idx = j
                                        highlight_end_pos_in_qblock_end_of_word = next_pos + len(next_word_display)
                                        temp_current_qblock_for_next_words = j
                                        temp_offset_for_next_words = highlight_end_pos_in_qblock_end_of_word
                                        found_current_next_word = True
                                        break 
                                    elif j == temp_current_qblock_for_next_words : # Якщо не знайдено в залишку поточного блоку, то далі немає сенсу шукати цю послідовність
                                        all_words_found_sequentially=False; break
                                if not found_current_next_word: all_words_found_sequentially=False
                                if not all_words_found_sequentially: break
                        
                        if all_words_found_sequentially:
                            log_debug(f"TaglessSearch Highlight Range for {editor_name}: StartBlk:{highlight_start_qblock_idx} StartPos:{highlight_start_pos_in_qblock} EndBlk:{highlight_end_qblock_idx} EndPos:{highlight_end_pos_in_qblock_end_of_word}")
                            for i in range(highlight_start_qblock_idx, highlight_end_qblock_idx + 1):
                                start_char = highlight_start_pos_in_qblock if i == highlight_start_qblock_idx else 0
                                current_block_for_highlight_text = editor.document().findBlockByNumber(i).text()
                                end_char = highlight_end_pos_in_qblock_end_of_word if i == highlight_end_qblock_idx else len(current_block_for_highlight_text)
                                length_to_highlight = end_char - start_char
                                if length_to_highlight > 0 :
                                    editor.highlightManager.add_search_match_highlight(i, start_char, length_to_highlight)
                            
                            scroll_to_block_nav = editor.document().findBlockByNumber(highlight_start_qblock_idx)
                            cursor_nav = QTextCursor(scroll_to_block_nav)
                            cursor_nav.setPosition(scroll_to_block_nav.position() + highlight_start_pos_in_qblock)
                            editor.setTextCursor(cursor_nav); editor.ensureCursorVisible()
                            found_overall_match_in_editor = True; break 
                        else: # Якщо не всі слова знайдені послідовно, пробуємо знайти перше слово далі
                            current_search_offset_in_qblock = start_pos + 1 
                    
                    if found_overall_match_in_editor: break # Знайшли в цьому редакторі, переходимо до наступного
        else: 
            # Точне підсвічування (попередня логіка) - тут є помилка з визначенням is_original_editor_and_search_original_precise
            # Поки що закоментуємо цю гілку, щоб зосередитися на tagless search
            raw_full_string_data = self._get_text_for_search(block_idx_match_in_data, string_idx_match_in_data, self.search_in_original, False)
            target_qtextblock_idx_in_editor, char_pos_in_target_qtextblock_raw = \
                self._calculate_qtextblock_and_pos_in_block(raw_full_string_data, char_pos_in_search_text) 
            log_debug(f"PreciseSearch: Match is in QTextBlk(editor): {target_qtextblock_idx_in_editor}, RawCharInBlk: {char_pos_in_target_qtextblock_raw}")
            raw_qtextblocks = raw_full_string_data.split('\n')
            if target_qtextblock_idx_in_editor >= len(raw_qtextblocks):
                log_debug(f"ERROR: PreciseSearch: target_qtextblock_idx_in_editor out of bounds."); return
            raw_text_of_target_qtextblock = raw_qtextblocks[target_qtextblock_idx_in_editor]
            compare_raw_qtextblock_text = raw_text_of_target_qtextblock
            compare_raw_query_for_occurrence_base = self.current_query
            if not self.is_case_sensitive:
                compare_raw_qtextblock_text = raw_text_of_target_qtextblock.lower()
                compare_raw_query_for_occurrence_base = self.current_query.lower()
            occurrence_in_qtextblock_raw = 0; temp_pos_qblk = -1; search_offset_qblk = 0
            
            effective_query_for_occ_count = compare_raw_query_for_occurrence_base
            text_for_occ_count = compare_raw_qtextblock_text
            
            # Визначаємо, чи потрібно видаляти теги для підрахунку входжень (тільки для original_text_edit при пошуку в оригіналі)
            if self.search_in_original and self.mw.original_text_edit.objectName() == "original_text_edit": # Припускаємо, що editor - це original_text_edit
                 effective_query_for_occ_count = remove_curly_tags(effective_query_for_occ_count)
                 text_for_occ_count = remove_curly_tags(text_for_occ_count)

            if effective_query_for_occ_count: 
                while search_offset_qblk <= char_pos_in_target_qtextblock_raw:
                    temp_pos_qblk = text_for_occ_count.find(effective_query_for_occ_count, search_offset_qblk)
                    if temp_pos_qblk == -1 or temp_pos_qblk > char_pos_in_target_qtextblock_raw: break
                    occurrence_in_qtextblock_raw += 1
                    if temp_pos_qblk == char_pos_in_target_qtextblock_raw: break
                    search_offset_qblk = temp_pos_qblk + 1
            if occurrence_in_qtextblock_raw == 0 and effective_query_for_occ_count: occurrence_in_qtextblock_raw = 1 
            log_debug(f"PreciseSearch: Match is the {occurrence_in_qtextblock_raw}-th occ in its raw QTextBlock.")
            editors_to_process_precise = [(self.mw.preview_text_edit, True, string_idx_match_in_data),(self.mw.original_text_edit, False, target_qtextblock_idx_in_editor),(self.mw.edited_text_edit, False, target_qtextblock_idx_in_editor)]
            for editor_precise, use_newline_symbol, widget_qtextblock_idx_to_use in editors_to_process_precise:
                editor_name_precise = editor_precise.objectName(); 
                if not editor_precise or not hasattr(editor_precise, 'highlightManager'): continue
                if (editor_precise == self.mw.original_text_edit or editor_precise == self.mw.edited_text_edit) and string_idx_match_in_data != self.mw.current_string_idx: continue
                widget_block_precise = editor_precise.document().findBlockByNumber(widget_qtextblock_idx_to_use)
                if not widget_block_precise.isValid(): continue
                text_in_widget_qtextblock_precise = widget_block_precise.text()
                query_for_this_editor_raw_precise = self.current_query
                if editor_precise == self.mw.original_text_edit: query_for_this_editor_raw_precise = remove_curly_tags(self.current_query)
                display_query_for_widget_precise = convert_raw_to_display_text(query_for_this_editor_raw_precise, self.mw.show_multiple_spaces_as_dots, self.mw.newline_display_symbol if use_newline_symbol else "")
                match_pos_in_widget_qtextblock_precise, match_len_in_widget_qtextblock_precise = self._find_nth_occurrence_in_display_text(text_in_widget_qtextblock_precise, display_query_for_widget_precise, occurrence_in_qtextblock_raw, self.is_case_sensitive)
                if match_pos_in_widget_qtextblock_precise != -1:
                    editor_precise.highlightManager.add_search_match_highlight(widget_qtextblock_idx_to_use, match_pos_in_widget_qtextblock_precise, match_len_in_widget_qtextblock_precise)
                    log_debug(f"Precise Highlighting in {editor_name_precise}: QBlk(widget):{widget_qtextblock_idx_to_use}, DispPosInBlk:{match_pos_in_widget_qtextblock_precise}, DispLen:{match_len_in_widget_qtextblock_precise}")
                    cursor_precise = QTextCursor(widget_block_precise); cursor_precise.setPosition(widget_block_precise.position() + match_pos_in_widget_qtextblock_precise + match_len_in_widget_qtextblock_precise); cursor_precise.clearSelection(); editor_precise.setTextCursor(cursor_precise); editor_precise.ensureCursorVisible()
                else: log_debug(f"PreciseSearch: Could not find {occurrence_in_qtextblock_raw}-th occ of query '{display_query_for_widget_precise}' in {editor_name_precise} QTextBlock idx {widget_qtextblock_idx_to_use} (text: '{text_in_widget_qtextblock_precise[:50]}...')")


        self.mw.search_match_block_indices.add(block_idx_match_in_data)
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.viewport().update()

    def clear_all_search_highlights(self):
        log_debug("SearchHandler: Clearing all search highlights.")
        for editor in [self.mw.preview_text_edit, self.mw.original_text_edit, self.mw.edited_text_edit]:
            if editor and hasattr(editor, 'highlightManager'):
                editor.highlightManager.clear_search_match_highlights()