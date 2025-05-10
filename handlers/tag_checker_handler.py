import re
from typing import Optional, List, Tuple
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtGui import QTextCursor

from utils.utils import log_debug
from constants import ORIGINAL_PLAYER_TAG

PLAYER_REPLACEMENT_CURLY_PATTERN_STR = r"\{Color:Green\}Лінк\w*\{Color:White\}"
PLAYER_REPLACEMENT_CURLY_PATTERN_COMPILED = re.compile(PLAYER_REPLACEMENT_CURLY_PATTERN_STR, re.IGNORECASE)
GENERIC_TAG_PATTERN = re.compile(r"\{[^}]*\}")


class TagCheckerHandler:
    def __init__(self, main_window):
        self.mw = main_window
        self.data_processor = main_window.data_processor
        self.original_text_edit = main_window.original_text_edit
        self.preview_text_edit = main_window.preview_text_edit 

        self.current_search_state = {
            'block_idx': -1,
            'string_idx': -1,
            'original_tag_idx_in_current_string': 0,
        }
        self.search_start_point = {'block_idx': -1, 'string_idx': -1}
        self.currently_highlighted_mismatch = {
            'block_idx': -1, # Блок, де була остання невідповідність
            'string_idx': -1, # Рядок, де була остання невідповідність
            'qtextblock_idx': -1, # QTextBlock в original_text_edit
            'start_char_in_qtextblock': -1, # Позиція символу в QTextBlock
            'length': -1, # Довжина тегу
            'tag_text': '' # Текст тегу
        }
        self.is_search_active = False # Чи триває зараз активний пошук (був зупинений на розбіжності)

    def _get_initial_search_indices(self) -> tuple[int, int]:
        # Визначає, з якого блоку/рядка починати абсолютно новий пошук
        # або пошук після завершення повного кола.
        # Намагається взяти поточний активний рядок в UI.
        current_block_idx_ui = self.mw.current_block_idx
        current_string_idx_ui = self.mw.current_string_idx

        if current_block_idx_ui == -1: # Якщо жоден блок не обрано
            current_block_idx_ui = 0
            current_string_idx_ui = 0
        elif current_string_idx_ui == -1: # Якщо блок обрано, але не рядок
            current_string_idx_ui = 0
        
        # Перевірка на вихід за межі
        if not self.mw.data or current_block_idx_ui >= len(self.mw.data):
            log_debug(f"TagChecker: _get_initial_search_indices - No data or block_idx {current_block_idx_ui} out of bounds. Returning 0,0")
            return 0,0
        
        current_block_data = self.mw.data[current_block_idx_ui]
        if not isinstance(current_block_data, list) or current_string_idx_ui >= len(current_block_data):
             log_debug(f"TagChecker: _get_initial_search_indices - Block data not list or string_idx {current_string_idx_ui} out of bounds for block {current_block_idx_ui}. Returning {current_block_idx_ui},0")
             return current_block_idx_ui, 0

        return current_block_idx_ui, current_string_idx_ui

    def _get_tags_from_string(self, text: str) -> list[tuple[str, int, int]]:
        tags = []
        if text is None: return tags
        for match in GENERIC_TAG_PATTERN.finditer(text):
            tags.append((match.group(0), match.start(), match.end()))
        return tags

    def _find_tag_in_translation(self, original_tag_text: str, translation_line_text: str, used_translation_tag_matches: list[tuple[int, int]]) -> tuple[bool, Optional[tuple[int,int]]]:
        
        def is_match_used(match_start, match_end, used_matches):
            for used_start_existing, used_end_existing in used_matches:
                if match_start == used_start_existing and match_end == used_end_existing:
                    return True
            return False

        if original_tag_text == ORIGINAL_PLAYER_TAG:
            for match in PLAYER_REPLACEMENT_CURLY_PATTERN_COMPILED.finditer(translation_line_text):
                if not is_match_used(match.start(), match.end(), used_translation_tag_matches):
                    return True, (match.start(), match.end())
            return False, None
        else:
            current_pos = 0
            while current_pos < len(translation_line_text):
                try:
                    match_pos = translation_line_text.index(original_tag_text, current_pos)
                    match_start = match_pos
                    match_end = match_pos + len(original_tag_text)
                    if not is_match_used(match_start, match_end, used_translation_tag_matches):
                        is_a_tag_in_translation = False
                        for trans_match in GENERIC_TAG_PATTERN.finditer(translation_line_text):
                            if trans_match.start() == match_start and trans_match.end() == match_end and trans_match.group(0) == original_tag_text:
                                is_a_tag_in_translation = True
                                break
                        if is_a_tag_in_translation:
                            return True, (match_start, match_end)
                    current_pos = match_end 
                except ValueError:
                    break 
            return False, None


    def _highlight_mismatched_tag(self, original_block_idx_data: int, original_string_idx_data: int, 
                                  tag_text: str, tag_start_char_in_string_data: int, tag_end_char_in_string_data: int):
        self._remove_mismatch_highlight() # Знімаємо попереднє, якщо було
        
        # Переконуємося, що UI показує правильний рядок
        if self.mw.current_block_idx != original_block_idx_data or \
           self.mw.current_string_idx != original_string_idx_data:
            log_debug(f"TagChecker: _highlight_mismatched_tag - UI (B{self.mw.current_block_idx},S{self.mw.current_string_idx}) "
                      f"doesn't match mismatch location (B{original_block_idx_data},S{original_string_idx_data}). Syncing UI first.")
            self.mw.current_block_idx = original_block_idx_data
            self.mw.list_selection_handler.string_selected_from_preview(original_string_idx_data)
            QApplication.processEvents() # Чекаємо, доки UI оновиться

        # Тепер, коли UI синхронізовано, original_text_edit має показувати потрібний рядок
        raw_text_of_displayed_original_line = self.mw.data[original_block_idx_data][original_string_idx_data]
        
        qtextblock_idx_in_displayed_editor = 0 
        char_pos_in_qtextblock_for_displayed_editor = tag_start_char_in_string_data
        
        last_newline_pos = -1
        current_pos_scan = 0
        while current_pos_scan < tag_start_char_in_string_data:
            newline_found_at = raw_text_of_displayed_original_line.find('\n', current_pos_scan)
            if newline_found_at != -1 and newline_found_at < tag_start_char_in_string_data:
                qtextblock_idx_in_displayed_editor += 1
                last_newline_pos = newline_found_at
                current_pos_scan = newline_found_at + 1
            else:
                break
        if last_newline_pos != -1:
            char_pos_in_qtextblock_for_displayed_editor = tag_start_char_in_string_data - (last_newline_pos + 1)

        length = tag_end_char_in_string_data - tag_start_char_in_string_data

        if self.mw.original_text_edit and hasattr(self.mw.original_text_edit, 'highlightManager'):
            self.mw.original_text_edit.highlightManager.add_search_match_highlight(
                qtextblock_idx_in_displayed_editor, char_pos_in_qtextblock_for_displayed_editor, length
            )
            self.currently_highlighted_mismatch = {
                'block_idx': original_block_idx_data,
                'string_idx': original_string_idx_data,
                'qtextblock_idx': qtextblock_idx_in_displayed_editor, 
                'start_char_in_qtextblock': char_pos_in_qtextblock_for_displayed_editor,
                'length': length,
                'tag_text': tag_text
            }
            log_debug(f"Highlighted mismatch: {self.currently_highlighted_mismatch}")
            
            doc = self.mw.original_text_edit.document()
            block_to_scroll = doc.findBlockByNumber(qtextblock_idx_in_displayed_editor)
            if block_to_scroll.isValid():
                cursor = QTextCursor(block_to_scroll)
                cursor.setPosition(block_to_scroll.position() + char_pos_in_qtextblock_for_displayed_editor)
                self.mw.original_text_edit.setTextCursor(cursor)
                self.mw.original_text_edit.ensureCursorVisible()
        else:
            log_debug(f"TagChecker: _highlight_mismatched_tag - original_text_edit or highlightManager not available.")

    def _remove_mismatch_highlight(self):
        if self.currently_highlighted_mismatch['block_idx'] != -1:
            if self.mw.original_text_edit and hasattr(self.mw.original_text_edit, 'highlightManager'):
                self.mw.original_text_edit.highlightManager.clear_search_match_highlights()
            self.currently_highlighted_mismatch = {
                'block_idx': -1, 'string_idx': -1, 'qtextblock_idx': -1,
                'start_char_in_qtextblock': -1, 'length': -1, 'tag_text': ''
            }
            log_debug("Removed mismatch highlight")

    def _reset_search_state_and_ui(self):
        self.current_search_state = {'block_idx': -1, 'string_idx': -1, 'original_tag_idx_in_current_string': 0}
        self.search_start_point = {'block_idx': -1, 'string_idx': -1}
        self.is_search_active = False
        self._remove_mismatch_highlight()

    def _show_completion_popup(self, all_ok_during_run: bool):
        # all_ok_during_run: True якщо не було жодної зупинки на підсвічування
        if all_ok_during_run:
            QMessageBox.information(self.mw, "Перевірка тегів завершена", "Всі теги на місці!")
        else:
            QMessageBox.warning(self.mw, "Перевірка тегів завершена", 
                                "Перевірку завершено. Були виявлені розбіжності по тегам, які були проігноровані або виправлені.")
        self._reset_search_state_and_ui()

    def start_or_continue_check(self):
        log_debug(f"TagChecker: start_or_continue_check. is_search_active: {self.is_search_active}, Highlighted: {self.currently_highlighted_mismatch['block_idx']!=-1}")
        if not self.mw.data:
            QMessageBox.information(self.mw, "Помилка", "Немає даних для перевірки.")
            self._reset_search_state_and_ui()
            return

        if self.currently_highlighted_mismatch['block_idx'] != -1:
            self._remove_mismatch_highlight()
            # Продовжуємо з НАСТУПНОГО тегу після того, що був підсвічений
            self.current_search_state['original_tag_idx_in_current_string'] += 1
            log_debug(f"TagChecker: Resuming after mismatch. Next original tag index: {self.current_search_state['original_tag_idx_in_current_string']}")
        elif not self.is_search_active: # Початок абсолютно нового пошуку
            start_b_idx, start_s_idx = self._get_initial_search_indices()
            self.current_search_state = {
                'block_idx': start_b_idx,
                'string_idx': start_s_idx,
                'original_tag_idx_in_current_string': 0
            }
            self.search_start_point = {'block_idx': start_b_idx, 'string_idx': start_s_idx}
            log_debug(f"TagChecker: New search initiated. Start: B{start_b_idx}, S{start_s_idx}")
        # Якщо is_search_active=True і немає highlighted_mismatch, це означає,
        # що ми завершили коло і починаємо нове, або це помилковий стан.
        # _reset_search_state_and_ui в _show_completion_popup має скинути is_search_active.

        self.is_search_active = True # Позначаємо, що пошук триває/розпочато
        
        num_blocks = len(self.mw.data)
        processed_at_least_one_tag_this_call = False
        mismatch_found_in_this_run = False


        while True: # Внутрішній цикл для перебору
            b_idx_current_iter = self.current_search_state['block_idx']
            s_idx_current_iter = self.current_search_state['string_idx']
            tag_orig_idx_current_iter = self.current_search_state['original_tag_idx_in_current_string']

            # Перевірка на завершення повного кола
            # Це має спрацювати, коли ми повернулися до search_start_point *і* tag_orig_idx_current_iter = 0
            # *і* ми вже щось обробили (processed_at_least_one_tag_this_call)
            if processed_at_least_one_tag_this_call and \
               b_idx_current_iter == self.search_start_point['block_idx'] and \
               s_idx_current_iter == self.search_start_point['string_idx'] and \
               tag_orig_idx_current_iter == 0:
                log_debug("TagChecker: Full circle completed.")
                self._show_completion_popup(not mismatch_found_in_this_run)
                return 
            
            processed_at_least_one_tag_this_call = True # Позначаємо, що ми пройшли хоча б одну ітерацію

            # Валідація індексів
            if b_idx_current_iter < 0 or b_idx_current_iter >= num_blocks:
                log_debug(f"TagChecker: Invalid block index {b_idx_current_iter} encountered. Resetting.")
                self._show_completion_popup(not mismatch_found_in_this_run)
                return

            current_block_original_data = self.mw.data[b_idx_current_iter]
            if not isinstance(current_block_original_data, list) or \
               s_idx_current_iter < 0 or s_idx_current_iter >= len(current_block_original_data):
                # Перехід до наступного блоку
                self.current_search_state['block_idx'] = (b_idx_current_iter + 1) % num_blocks
                self.current_search_state['string_idx'] = 0
                self.current_search_state['original_tag_idx_in_current_string'] = 0
                log_debug(f"TagChecker: End of block {b_idx_current_iter} or invalid string index. Moving to B{self.current_search_state['block_idx']}, S0")
                continue # До наступної ітерації while

            original_row_text_data = current_block_original_data[s_idx_current_iter]
            translation_row_text_data, _ = self.data_processor.get_current_string_text(b_idx_current_iter, s_idx_current_iter)
            
            original_tags_with_pos_list = self._get_tags_from_string(original_row_text_data)

            if not original_tags_with_pos_list or tag_orig_idx_current_iter >= len(original_tags_with_pos_list):
                # Немає тегів в оригіналі для поточного рядка або всі теги цього рядка вже перевірені
                self.current_search_state['string_idx'] += 1
                self.current_search_state['original_tag_idx_in_current_string'] = 0
                log_debug(f"TagChecker: No more tags in B{b_idx_current_iter},S{s_idx_current_iter} or all checked for this string. Moving to S{self.current_search_state['string_idx']}")
                continue # До наступної ітерації while
            
            # Отримуємо поточний тег оригіналу для перевірки
            current_orig_tag_text, current_orig_tag_start, current_orig_tag_end = original_tags_with_pos_list[tag_orig_idx_current_iter]
            
            # Збираємо "використані" теги в перекладі для ПОПЕРЕДНІХ тегів оригіналу ЦЬОГО Ж рядка
            used_translation_tag_matches_for_current_original_row = []
            for i in range(tag_orig_idx_current_iter): 
                prev_orig_tag_text_iter, _, _ = original_tags_with_pos_list[i]
                found_prev_iter, prev_match_span_iter = self._find_tag_in_translation(
                    prev_orig_tag_text_iter, 
                    translation_row_text_data, 
                    used_translation_tag_matches_for_current_original_row # Передаємо список, який оновлюється
                )
                if found_prev_iter and prev_match_span_iter:
                    used_translation_tag_matches_for_current_original_row.append(prev_match_span_iter)
            
            # Перевіряємо поточний тег оригіналу
            found_current_tag, _ = self._find_tag_in_translation(
                current_orig_tag_text, 
                translation_row_text_data, 
                used_translation_tag_matches_for_current_original_row
            )
            
            if found_current_tag:
                log_debug(f"TagChecker: Match! B{b_idx_current_iter},S{s_idx_current_iter}. Tag '{current_orig_tag_text}' (orig_idx {tag_orig_idx_current_iter}).")
                self.current_search_state['original_tag_idx_in_current_string'] += 1 
                # Продовжуємо з наступним тегом оригіналу в цьому ж рядку (наступна ітерація while)
            else:
                # Тег не знайдено!
                log_debug(f"TagChecker: Mismatch! B{b_idx_current_iter},S{s_idx_current_iter}. Original Tag (idx {tag_orig_idx_current_iter}) '{current_orig_tag_text}' "
                          f"not found in translation '{translation_row_text_data}'. "
                          f"Used translation tags for previous original tags in this row: {used_translation_tag_matches_for_current_original_row}")
                
                mismatch_found_in_this_run = True
                # Оновлюємо UI, щоб показати рядок з розбіжністю
                if self.mw.current_block_idx != b_idx_current_iter or \
                   self.mw.current_string_idx != s_idx_current_iter:
                    log_debug(f"TagChecker: Syncing UI to mismatch location B{b_idx_current_iter}, S{s_idx_current_iter} before highlight.")
                    self.mw.current_block_idx = b_idx_current_iter
                    self.mw.list_selection_handler.string_selected_from_preview(s_idx_current_iter)
                    QApplication.processEvents()
                
                self._highlight_mismatched_tag(b_idx_current_iter, s_idx_current_iter, current_orig_tag_text, current_orig_tag_start, current_orig_tag_end)
                
                # self.is_search_active залишається True. Стан (b_idx, s_idx, tag_orig_idx) збережено.
                # Виходимо з функції, щоб чекати наступного кліку користувача.
                return 