import re
from PyQt5.QtWidgets import QMessageBox, QApplication
from handlers.base_handler import BaseHandler
from utils import log_debug, clean_newline_at_end, convert_dots_to_spaces_from_editor # Додано імпорт
from tag_utils import replace_tags_based_on_original

class TextOperationHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)

    def text_edited(self):
        if self.mw.is_programmatically_changing_text: return 

        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            # self.ui_updater.update_status_bar(); self.ui_updater.update_status_bar_selection() # Ці методи викликаються в update_text_views
            return

        block_idx = self.mw.current_block_idx
        string_idx = self.mw.current_string_idx
        
        # Отримуємо текст з UI (він може містити крапки замість пробілів)
        text_from_ui_with_dots = self.mw.edited_text_edit.toPlainText() 
        
        # --- КОНВЕРТУЄМО КРАПКИ НАЗАД В ПРОБІЛИ ---
        # Робимо це тільки якщо відображення крапок було увімкнене
        if self.mw.show_multiple_spaces_as_dots:
            actual_text_with_spaces = convert_dots_to_spaces_from_editor(text_from_ui_with_dots)
        else:
            actual_text_with_spaces = text_from_ui_with_dots
        # --- КІНЕЦЬ КОНВЕРТАЦІЇ ---

        unsaved_status_changed = self.data_processor.update_edited_data(block_idx, string_idx, actual_text_with_spaces)
        
        if unsaved_status_changed: 
            # log_debug(f"Unsaved status changed to: {self.mw.unsaved_changes}. Updating title.")
            self.ui_updater.update_title()
        
        # Оновлюємо preview_text_edit (список рядків)
        # Це поле вже оновлюється через populate_strings_for_block при зміні даних,
        # але якщо ми хочемо миттєвого оновлення поточного рядка в preview без повного перемальовування:
        # self.ui_updater.update_string_list_item_text(string_idx, actual_text_with_spaces) 
        # Однак, update_string_list_item_text був для старого QListWidget.
        # Для QPlainTextEdit (preview_text_edit) потрібно оновити відповідний рядок.
        # Простіше оновити весь preview, якщо ця зміна важлива для негайного відображення.
        # Або, якщо зміни незначні, покластися на наступний виклик populate_strings_for_block.
        # Поки що не будемо тут напряму оновлювати preview_text_edit, щоб уникнути складнощів.
        # ui_updater.populate_strings_for_block буде викликаний при збереженні або зміні блоку/рядка.

        # Статус бар оновлюється автоматично, оскільки edited_text_edit.textChanged вже викликав cursorPositionChanged
        # self.ui_updater.update_status_bar()
        # self.ui_updater.update_status_bar_selection()
        pass # Логіка оновлення статус бару вже підключена до сигналів edited_text_edit

    def paste_block_text(self):
        # ... (цей метод потребуватиме уваги, якщо вставлений текст також має оброблятися
        #      щодо пробілів/крапок, але поки що залишимо його без змін у цій частині) ...
        log_debug("--> TextOperationHandler: paste_block_text triggered.")
        if self.mw.current_block_idx == -1:
            QMessageBox.warning(self.mw, "Paste Error", "Please select a block.")
            log_debug("<-- TextOperationHandler: paste_block_text finished (No block selected).")
            return

        start_string_idx = self.mw.current_string_idx if self.mw.current_string_idx != -1 else 0
        pasted_text_raw = QApplication.clipboard().text() # Оригінальний текст з буфера обміну
        if not pasted_text_raw:
            QMessageBox.information(self.mw, "Paste", "Clipboard empty.")
            log_debug("<-- TextOperationHandler: paste_block_text finished (Clipboard empty).")
            return

        log_debug("Processing clipboard text for paste...")
        # Тут ми не конвертуємо крапки в pasted_text_raw, бо очікуємо, що там пробіли
        parsed_strings_raw = re.split(r'\{END\}\r?\n', pasted_text_raw)
        parsed_strings_intermediate = []
        num_raw_segments = len(parsed_strings_raw)
        for i, segment in enumerate(parsed_strings_raw):
            cleaned_segment = segment[1:] if i > 0 and segment.startswith('\n') else segment
            if i < num_raw_segments - 1 or cleaned_segment: parsed_strings_intermediate.append(cleaned_segment)
        
        # parsed_strings містять реальні пробіли
        parsed_strings = [s for s in parsed_strings_intermediate if s] # Видаляємо порожні рядки після split, якщо вони не потрібні
        
        log_debug(f"Found {len(parsed_strings)} segments after cleaning.")

        block_idx = self.mw.current_block_idx
        if not (0 <= block_idx < len(self.mw.data)) or not isinstance(self.mw.data[block_idx], list):
             QMessageBox.warning(self.mw, "Paste Error", f"Block data invalid for {block_idx}.")
             return
             
        block_data_len = len(self.mw.data[block_idx])
        # Дозволити вставку в порожній блок, якщо start_string_idx = 0
        if not (0 <= start_string_idx < block_data_len) and not (block_data_len == 0 and start_string_idx == 0) :
             QMessageBox.warning(self.mw, "Paste Error", f"Invalid start index {start_string_idx} for block of length {block_data_len}.")
             return
             
        num_target_slots = block_data_len - start_string_idx if block_data_len > 0 else len(parsed_strings) # Якщо блок порожній, вставляємо все
        if block_data_len == 0 and start_string_idx == 0:
            num_target_slots = len(parsed_strings)


        num_segments_to_insert = min(len(parsed_strings), num_target_slots) if num_target_slots > 0 else len(parsed_strings)
        if num_target_slots == 0 and len(parsed_strings) > 0 and block_data_len > 0 : # Немає місця для вставки в існуючий блок
            QMessageBox.warning(self.mw, "Paste Warning", "Not enough space in the current block to paste all segments from the starting position.")
            # Можна або нічого не робити, або вставити скільки влізе
            # Поки що, якщо немає місця, нічого не робимо, якщо не порожній блок
            if num_segments_to_insert == 0: return


        segments_to_use = parsed_strings[:num_segments_to_insert]
        log_debug(f"Will insert {num_segments_to_insert} segments starting at index {start_string_idx}.")
        if num_segments_to_insert == 0 and len(parsed_strings) > 0 :
             QMessageBox.information(self.mw, "Paste", "No segments to insert (possibly due to block limits or empty clipboard content after parsing).")
             return
        if not segments_to_use: # Якщо після всіх фільтрів нічого не залишилося
            QMessageBox.information(self.mw, "Paste", "No valid segments found to insert.")
            return

        effective_changes_applied = False
        self.mw.is_programmatically_changing_text = True # Групове оновлення
        for i, segment_to_insert_raw in enumerate(segments_to_use):
            current_target_string_idx = start_string_idx + i
            if current_target_string_idx >= block_data_len and block_data_len == 0 : # Якщо блок був порожній, ми "розширюємо" його
                # Це складна логіка, якщо дані - список фіксованої довжини. 
                # Припускаємо, що update_edited_data може обробляти нові індекси, якщо структура даних це дозволяє
                # Або нам треба буде тут модифікувати self.mw.data / self.mw.edited_file_data
                # Для JSON списку це нормально, просто додаються елементи.
                pass # update_edited_data має впоратися
            elif current_target_string_idx >= block_data_len: # Вийшли за межі існуючих слотів
                log_debug(f"Paste Warning: Target index {current_target_string_idx} out of bounds for block of length {block_data_len}. Stopping paste here.")
                break # Зупиняємо вставку, якщо вийшли за межі існуючих слотів (крім випадку порожнього блоку)


            original_text_for_tags = ""
            if 0 <= current_target_string_idx < len(self.mw.data[block_idx]): # Перевірка для self.mw.data
                 original_text_for_tags = self.mw.data[block_idx][current_target_string_idx]
            
            text_with_replaced_tags = replace_tags_based_on_original(segment_to_insert_raw, original_text_for_tags)
            final_text_to_apply = text_with_replaced_tags.rstrip('\n') # Зберігаємо без зайвих \n в кінці
            
            item_changed_unsaved_status = self.data_processor.update_edited_data(block_idx, current_target_string_idx, final_text_to_apply)
            
            # Перевірка, чи дійсно щось змінилося
            current_val_in_edited_data = self.mw.edited_data.get((block_idx, current_target_string_idx))
            original_text_at_idx = self.data_processor._get_string_from_source(block_idx, current_target_string_idx, self.mw.data, "original_data")
            
            if current_val_in_edited_data is not None or \
               (original_text_at_idx is not None and final_text_to_apply != original_text_at_idx) or \
               (original_text_at_idx is None and final_text_to_apply): # Якщо оригінал був None, а ми щось вставили
                effective_changes_applied = True
        
        self.mw.is_programmatically_changing_text = False # Кінець групового оновлення

        if effective_changes_applied:
            log_debug("Effective changes detected from paste, auto-saving and refreshing UI.")
            # Збереження викличе оновлення UI, включаючи populate_strings_for_block
            save_success = self.mw.app_action_handler.save_data_action(ask_confirmation=False) 
            msg_verb = "Pasted and saved." if save_success else "Pasted, but auto-save FAILED."
            QMessageBox.information(self.mw, "Paste Operation", f"{num_segments_to_insert} segment(s) processed. {msg_verb}")
        else:
             log_debug("No effective changes detected from paste operation.")
             QMessageBox.information(self.mw, "Paste", "Pasted text resulted in no changes to the data.")
             # Навіть якщо змін немає, варто оновити вигляд, щоб він був консистентним
             self.mw.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
             self.mw.ui_updater.update_title()

        log_debug("<-- TextOperationHandler: paste_block_text finished.")