import json
import os
import datetime
import re # Імпортуємо модуль регулярних виразів
from PyQt5.QtWidgets import QMessageBox, QInputDialog, QApplication, QListWidgetItem
from PyQt5.QtCore import Qt
from data_state_processor import DataStateProcessor
from ui_updater import UIUpdater
from utils import log_debug, replace_tags_based_on_original
from utils import clean_newline_at_end

def log_debug(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


class MainWindowEventHandlers:
    def __init__(self, main_window):
        log_debug("MainWindowEventHandlers initialized.")
        self.mw = main_window
        self.data_processor = DataStateProcessor(self.mw)
        self.ui_updater = UIUpdater(self.mw, self.data_processor)
        self.mw.handlers = self
        log_debug("MainWindowEventHandlers setup complete.")


    # --- Методи, які безпосередньо підключені до сигналів UI ---
    # (populate_blocks, block_selected, string_selected, text_edited, rename_block - без змін)
    def populate_blocks(self):
        log_debug("[MainWindowEventHandlers] populate_blocks called (redirecting to UIUpdater).")
        self.ui_updater.populate_blocks()

    def block_selected(self, current, previous):
        log_debug(f"[MainWindowEventHandlers] block_selected called. Current: {current.text() if current else 'None'}, Previous: {previous.text() if previous else 'None'}")
        block_index = -1
        if current is not None:
            block_index = current.data(Qt.UserRole)
            log_debug(f"[MainWindowEventHandlers] block_selected: Selected block index is {block_index}.")
        self.mw.current_string_idx = -1
        log_debug("[MainWindowEventHandlers] block_selected: Resetting self.mw.current_string_idx.")
        self.ui_updater.populate_strings_for_block(block_index)

    def string_selected(self, current, previous):
        log_debug(f"[MainWindowEventHandlers] string_selected called. Current index: {current.data(Qt.UserRole) if current else 'None'}, Previous index: {previous.data(Qt.UserRole) if previous else 'None'}")
        try:
            self.mw.edited_text_edit.textChanged.disconnect(self.text_edited)
        except TypeError: pass

        original_text = ""
        edited_text_to_display = ""

        if current is None or self.mw.current_block_idx == -1:
            log_debug("[MainWindowEventHandlers] string_selected: No current item or block selected. Resetting.")
            self.mw.current_string_idx = -1
            self.mw.original_text_edit.setPlainText("")
            self.mw.edited_text_edit.setPlainText("")
        else:
            string_index = current.data(Qt.UserRole)
            if string_index is None:
                log_debug("[MainWindowEventHandlers] string_selected: Current item has no string index. Resetting.")
                self.mw.current_string_idx = -1
                self.mw.original_text_edit.setPlainText("")
                self.mw.edited_text_edit.setPlainText("")
            else:
                self.mw.current_string_idx = string_index
                edit_key = (self.mw.current_block_idx, self.mw.current_string_idx)
                log_debug(f"[MainWindowEventHandlers] string_selected: Selected string index is {self.mw.current_string_idx}. Edit key: {edit_key}")

                original_text = self.data_processor._get_string_from_source(self.mw.current_block_idx, self.mw.current_string_idx, self.mw.data, "original_data")
                if original_text is None:
                    original_text = "[ПОМИЛКА ІНДЕКСУ В ОРИГІНАЛІ]"
                    log_debug(f"[MainWindowEventHandlers] string_selected: Помилка: Неправильний індекс для оригінальних даних ({self.mw.current_block_idx}, {self.mw.current_string_idx}).")

                edited_text_to_display, source = self.data_processor.get_current_string_text(self.mw.current_block_idx, self.mw.current_string_idx)
                log_debug(f"[MainWindowEventHandlers] string_selected: Got text for editor (source: {source}).")

        self.mw.original_text_edit.setPlainText(original_text)
        self.mw.edited_text_edit.setPlainText(edited_text_to_display)

        self.mw.edited_text_edit.textChanged.connect(self.text_edited)

        self.ui_updater.update_status_bar()
        self.ui_updater.update_status_bar_selection()
        log_debug("[MainWindowEventHandlers] string_selected: Updated status bar. Finished.")

    def text_edited(self):
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            self.ui_updater.update_status_bar()
            self.ui_updater.update_status_bar_selection()
            return

        block_idx = self.mw.current_block_idx
        string_idx = self.mw.current_string_idx
        current_edited_text = self.mw.edited_text_edit.toPlainText()

        unsaved_status_changed = self.data_processor.update_edited_data(block_idx, string_idx, current_edited_text)

        if unsaved_status_changed:
             self.ui_updater.update_title()

        self.ui_updater.update_string_list_item_text(string_idx, current_edited_text)
        self.ui_updater.update_status_bar()
        self.ui_updater.update_status_bar_selection()

    def rename_block(self, item):
        log_debug(f"[MainWindowEventHandlers] rename_block called for item text: {item.text()}.")
        block_index = item.data(Qt.UserRole)
        if block_index is None:
            log_debug("[MainWindowEventHandlers] rename_block: Item has no associated block index.")
            return

        current_name = self.mw.block_names.get(block_index, f"Блок {block_index}")
        new_name, ok = QInputDialog.getText(self.mw, "Перейменувати блок",
                                            f"Введіть нову назву для '{current_name}':",
                                            text=current_name)

        if ok and new_name and new_name != current_name:
            self.mw.block_names[block_index] = new_name
            item.setText(new_name)
            log_debug(f"[MainWindowEventHandlers] rename_block: Block {block_index} renamed to '{new_name}'.")
            self.mw.save_settings()

    def _replace_tags_based_on_original(self, pasted_segment, original_text):
        """Замінює теги [...] на {} на основі порядку в оригіналі."""
        pasted_tags_content = re.findall(r'\[(.*?)\]', pasted_segment)
        original_tags_full = re.findall(r'\{.*?\}', original_text)

        if len(pasted_tags_content) != len(original_tags_full):
            log_debug(f"Warning: Tag count mismatch. Pasted: {len(pasted_tags_content)}, Original: {len(original_tags_full)}. Skipping tag replacement for this segment.")
            log_debug(f"  Pasted segment: {repr(pasted_segment)}")
            log_debug(f"  Original text: {repr(original_text)}")
            return pasted_segment

        modified_segment = pasted_segment
        pasted_tags_full = re.findall(r'\[.*?\]', pasted_segment)

        if len(pasted_tags_full) != len(original_tags_full):
             log_debug(f"Warning: Full tag count mismatch during replacement. Pasted: {len(pasted_tags_full)}, Original: {len(original_tags_full)}. Skipping.")
             return pasted_segment

        for i in range(len(pasted_tags_full)):
            tag_to_replace = pasted_tags_full[i]
            replacement_tag = original_tags_full[i]
            modified_segment = modified_segment.replace(tag_to_replace, replacement_tag, 1)

        log_debug(f"Tag replacement done. Result: {repr(modified_segment)}")
        return modified_segment


    def paste_block_text(self):
        """
        Отримує текст з буфера обміну, розділяє його за '{END}\n',
        замінює теги [...] на {} на основі оригіналу, обробляє порожні рядки,
        бере потрібну кількість сегментів та застосовує до поточного блоку.
        Після вставки автоматично зберігає зміни.
        """
        log_debug("[MainWindowEventHandlers] paste_block_text called.")
        if self.mw.current_block_idx == -1:
            QMessageBox.warning(self.mw, "Помилка вставки", "Будь ласка, виберіть блок у списку зліва.")
            log_debug("[MainWindowEventHandlers] paste_block_text: No block selected.")
            return

        start_string_idx = self.mw.current_string_idx if self.mw.current_string_idx != -1 else 0
        log_debug(f"[MainWindowEventHandlers] paste_block_text: Selected block {self.mw.current_block_idx}, starting string index {start_string_idx}.")

        clipboard = QApplication.clipboard()
        pasted_text = clipboard.text()

        if not pasted_text:
            QMessageBox.information(self.mw, "Вставка", "Буфер обміну порожній або містить нетекстові дані.")
            log_debug("[MainWindowEventHandlers] paste_block_text: Clipboard is empty.")
            return

        # Розділяємо текст за '{END}\n' (з урахуванням можливих \r\n)
        parsed_strings_raw = re.split(r'\{END\}\r?\n', pasted_text)
        log_debug(f"[MainWindowEventHandlers] paste_block_text: Parsed into {len(parsed_strings_raw)} segments using re.split('{{END}}\\r?\\n').")

        # Очищаємо початкові '\n' (крім першого сегмента) і готуємо фінальний список рядків
        parsed_strings_intermediate = []
        num_raw_segments = len(parsed_strings_raw)
        for i, segment in enumerate(parsed_strings_raw):
             if i > 0 and segment.startswith('\n'):
                 cleaned_segment = segment[1:]
             else:
                 cleaned_segment = segment

             # Видаляємо останній порожній сегмент, який створює split
             if i < num_raw_segments - 1 or cleaned_segment:
                 parsed_strings_intermediate.append(cleaned_segment)

        parsed_strings = parsed_strings_intermediate
        log_debug(f"[MainWindowEventHandlers] paste_block_text: Segments count after initial cleaning: {len(parsed_strings)}")

        block_idx = self.mw.current_block_idx
        if not (0 <= block_idx < len(self.mw.data)) or not isinstance(self.mw.data[block_idx], list):
             log_debug(f"[MainWindowEventHandlers] paste_block_text: Помилка: Оригінальний блок {block_idx} не існує або не є списком.")
             QMessageBox.warning(self.mw, "Помилка вставки", f"Оригінальні дані для блоку {block_idx} невалідні. Вставку не виконано.")
             return

        block_data_len = len(self.mw.data[block_idx])
        log_debug(f"[MainWindowEventHandlers] paste_block_text: Target block {block_idx} has {block_data_len} original strings.")

        if start_string_idx < 0 or start_string_idx >= block_data_len:
             log_debug(f"[MainWindowEventHandlers] paste_block_text: Помилка: Недійсний початковий індекс рядка {start_string_idx} для блоку {block_idx}.")
             QMessageBox.warning(self.mw, "Помилка вставки", f"Недійсний початковий індекс рядка {start_string_idx}. Вставку не виконано.")
             return

        num_target_slots = block_data_len - start_string_idx
        num_segments_from_paste = len(parsed_strings)
        num_segments_to_insert = min(num_segments_from_paste, num_target_slots)
        segments_to_use = parsed_strings[:num_segments_to_insert]

        log_debug(f"[MainWindowEventHandlers] paste_block_text: Available slots: {num_target_slots}. Segments from paste: {num_segments_from_paste}. Segments to insert: {num_segments_to_insert}.")

        if num_segments_from_paste > num_target_slots:
             QMessageBox.warning(self.mw, "Забагато сегментів",
                                f"Вставлений текст містить {num_segments_from_paste} значущих сегментів.\n"
                                f"Доступно лише {num_target_slots} місць для заміни, починаючи з рядка {start_string_idx}.\n"
                                f"Буде вставлено лише перші {num_target_slots} сегментів.")
        elif num_segments_from_paste < num_target_slots and num_segments_from_paste > 0:
              QMessageBox.warning(self.mw, "Замало сегментів",
                                f"Вставлений текст містить лише {num_segments_from_paste} значущих сегментів.\n"
                                f"Для заповнення блоку з рядка {start_string_idx} очікувалося {num_target_slots} сегментів.\n"
                                f"Буде вставлено лише {num_segments_from_paste} сегментів.")


        if num_segments_to_insert == 0:
             log_debug("[MainWindowEventHandlers] paste_block_text: No segments left to insert. Aborting.")
             QMessageBox.information(self.mw, "Вставка", "Після обробки не залишилося сегментів для вставки.")
             return

        changes_made_in_this_paste = False

        try:
            self.mw.edited_text_edit.textChanged.disconnect(self.text_edited)
        except TypeError: pass

        # Проходимося по сегментах, які будемо вставляти
        for i, segment_to_insert in enumerate(segments_to_use):
            orig_idx = start_string_idx + i
            # Ensure original index is valid before proceeding
            # (Added check for robustness, assuming self.mw.data[block_idx] is a list)
            if not (0 <= orig_idx < len(self.mw.data[block_idx])):
                log_debug(f"[MainWindowEventHandlers] paste_block_text: Skipping invalid original index {orig_idx} during paste loop.")
                continue # Skip this iteration if index is out of bounds

            original_text = self.mw.data[block_idx][orig_idx]
            # Use the function for tag replacement
            text_with_replaced_tags = replace_tags_based_on_original(segment_to_insert, original_text)
            final_text = text_with_replaced_tags.rstrip('\n')

            # Call update_edited_data and check if it resulted in a change for this item.
            # This assumes update_edited_data returns True if self.mw.edited_data was modified for this key, False otherwise.
            item_changed = self.data_processor.update_edited_data(block_idx, orig_idx, final_text)

            # Log the action based on the result from update_edited_data
            edit_key = (block_idx, orig_idx) # Define edit_key for logging if needed
            if item_changed:
                log_debug(f"[MainWindowEventHandlers] paste_block_text: Change detected/applied for {edit_key} by update_edited_data.")
                changes_made_in_this_paste = True # Aggregate changes if any item changed
            else:
                 log_debug(f"[MainWindowEventHandlers] paste_block_text: No effective change for {edit_key} by update_edited_data.")

            # The previous if/elif block checking final_text vs original_text and modifying
            # self.mw.edited_data directly is removed, as update_edited_data should handle this.

        # After the loop, update the overall unsaved status based on the final state of edited_data
        self.mw.unsaved_changes = bool(self.mw.edited_data)
        log_debug(f"[MainWindowEventHandlers] paste_block_text: After paste loop, unsaved_changes = {self.mw.unsaved_changes}, edited_data size = {len(self.mw.edited_data)}.")

        self.mw.edited_text_edit.textChanged.connect(self.text_edited)


        if changes_made_in_this_paste:
            # self.update_title() # This seems to be handled by ui_updater.update_title() in save_data
            log_debug("[MainWindowEventHandlers] paste_block_text: Changes were made during paste.")

            log_debug("[MainWindowEventHandlers] paste_block_text: Calling data_processor.save_current_edits(ask_confirmation=False).")
            save_success = self.data_processor.save_current_edits(ask_confirmation=False)
            log_debug(f"[MainWindowEventHandlers] paste_block_text: data_processor.save_current_edits returned {save_success}.")

            # Refresh UI after potential save
            current_b_idx = self.mw.current_block_idx
            # current_s_idx = self.mw.current_string_idx # No need to preserve index here, populate_strings resets selection
            log_debug(f"[MainWindowEventHandlers] paste_block_text: Re-populating UI for block {current_b_idx}.")
            self.ui_updater.populate_strings_for_block(current_b_idx) # This will update list and trigger string_selected if needed

            # Update title *after* save and UI refresh attempt
            self.ui_updater.update_title()

            if save_success:
                 QMessageBox.information(self.mw, "Вставка та Збереження", f"Успішно вставлено {num_segments_to_insert} сегментів тексту в блок {block_idx}, починаючи з рядка {start_string_idx} (теги замінено, кінцеві \\n/порожні рядки оброблено), та автоматично збережено у файл змін.")
                 log_debug("[MainWindowEventHandlers] paste_block_text: Showed success message for paste+autosave.")
            else:
                 QMessageBox.warning(self.mw, "Вставка (Помилка збереження)", f"Успішно вставлено {num_segments_to_insert} сегментів тексту в блок {block_idx}, починаючи з рядка {start_string_idx} (теги замінено, кінцеві \\n/порожні рядки оброблено), але АВТОМАТИЧНЕ ЗБЕРЕЖЕННЯ НЕ ВДАЛОСЯ. Незбережені зміни присутні.")
                 log_debug("[MainWindowEventHandlers] paste_block_text: Showed error message for paste+autosave.")
        else:
             QMessageBox.information(self.mw, "Вставка", "Вставлений текст (після обробки тегів та кінцевих \\n/порожніх рядків) ідентичний оригінальному тексту в цільових рядках. Зміни не застосовано.")
             log_debug("[MainWindowEventHandlers] paste_block_text: No changes made by paste. Showed info message.")

        log_debug("[MainWindowEventHandlers] paste_block_text: Finished.")


    def save_data(self, ask_confirmation=True):
        log_debug(f"[MainWindowEventHandlers] save_data called with ask_confirmation={ask_confirmation}.")
        save_success = self.data_processor.save_current_edits(ask_confirmation=ask_confirmation)
        log_debug(f"[MainWindowEventHandlers] save_data: data_processor.save_current_edits returned {save_success}.")
        if save_success:
            self.ui_updater.update_title()
            self.mw.save_settings()
            if self.mw.current_block_idx != -1:
                 self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
        return save_success

    def closeEvent(self, event):
        log_debug("[MainWindowEventHandlers] closeEvent called.")
        if self.mw.unsaved_changes:
            log_debug("[MainWindowEventHandlers] closeEvent: Unsaved changes detected.")
            reply = QMessageBox.question(self.mw, 'Незбережені зміни',
                                         "У вас є незбережені зміни. Зберегти їх перед виходом?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                         QMessageBox.Cancel)

            if reply == QMessageBox.Save:
                log_debug("[MainWindowEventHandlers] closeEvent: User chose Save.")
                if self.save_data(ask_confirmation=True): # Запитуємо підтвердження
                     event.accept()
                     log_debug("[MainWindowEventHandlers] closeEvent: Accepted after save success or discard in dialog.")
                else:
                     event.ignore()
                     log_debug("[MainWindowEventHandlers] closeEvent: Ignored after save failure or cancel in dialog.")
            elif reply == QMessageBox.Discard:
                log_debug("[MainWindowEventHandlers] closeEvent: User chose Discard. Accepted.")
                event.accept()
            else: # Cancel
                log_debug("[MainWindowEventHandlers] closeEvent: User chose Cancel. Ignored.")
                event.ignore()
        else:
            log_debug("[MainWindowEventHandlers] closeEvent: No unsaved changes. Accepted.")
            event.accept()


    # --- Допоміжні методи, що перенаправляють виклики до UIUpdater ---

    def update_title(self):
         self.ui_updater.update_title()

    def update_status_bar(self):
         self.ui_updater.update_status_bar()

    def update_status_bar_selection(self):
         self.ui_updater.update_status_bar_selection()

    def clear_status_bar(self):
         log_debug("[MainWindowEventHandlers] clear_status_bar called (redirecting to UIUpdater).")
         self.ui_updater.clear_status_bar()

    def update_statusbar_paths(self):
        log_debug("[MainWindowEventHandlers] update_statusbar_paths called (redirecting to UIUpdater).")
        self.ui_updater.update_statusbar_paths()