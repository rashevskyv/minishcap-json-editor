import json
import os
import datetime
import re # Імпортуємо модуль регулярних виразів
from PyQt5.QtWidgets import QMessageBox, QInputDialog, QApplication, QListWidgetItem
from PyQt5.QtCore import Qt
# Імпортуємо класи обробників даних та UI
from data_state_processor import DataStateProcessor
from ui_updater import UIUpdater

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


    def paste_block_text(self):
        """
        Отримує текст з буфера обміну, розділяє його за '{END}\n',
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

        # --- Логіка розділення за '{END}\n' (з урахуванням можливих \r\n) ---
        # Використовуємо re.split для врахування \r\n
        # Розділяємо за {END}, за яким слідує необов'язковий \r і обов'язковий \n
        parsed_strings = re.split(r'\{END\}\r?\n', pasted_text)
        log_debug(f"[MainWindowEventHandlers] paste_block_text: Parsed into {len(parsed_strings)} segments using re.split('{{END}}\\r?\\n').")

        # !!! Важливо: split залишить початкові \n, якщо вони були перед першим {END}\n
        # Потрібно видалити ОДИН початковий \n з кожного сегмента, КРІМ першого, якщо він там є
        # А також видалити кінцеві \n, якщо вони залишились після останнього {END}\n у вхідному тексті
        cleaned_strings = []
        num_raw_segments = len(parsed_strings)
        for i, segment in enumerate(parsed_strings):
             # Видаляємо початковий \n, якщо це не перший сегмент
             if i > 0 and segment.startswith('\n'):
                 cleaned_segment = segment[1:]
             else:
                 cleaned_segment = segment

             # Видаляємо кінцевий \n, якщо це ОСТАННІЙ сегмент
             # (split не залишає кінцевий роздільник, тому останній \n може бути тільки якщо він був в оригіналі)
             # if i == num_raw_segments - 1 and cleaned_segment.endswith('\n'):
             #      cleaned_segment = cleaned_segment[:-1]
             # UPDATE: Логіка вище неправильна. Після split('{END}\n'), кінцевий \n вже видалено.
             # Треба перевірити, чи НЕ ТРЕБА видаляти кінцеві \n з сегментів ПЕРЕД останнім {END}\n?
             # Згідно з вашим бажаним результатом, кінцеві \n мають залишатися.
             # Тому додаткове очищення кінцевих \n не потрібне.

             # Додаємо сегмент, якщо це не останній порожній сегмент
             # (що може статися, якщо текст закінчувався на {END}\n)
             if i < num_raw_segments - 1 or cleaned_segment:
                 cleaned_strings.append(cleaned_segment)


        parsed_strings = cleaned_strings # Використовуємо очищений список
        log_debug(f"[MainWindowEventHandlers] paste_block_text: Final segments count after cleaning: {len(parsed_strings)}")
        # for idx, s in enumerate(parsed_strings):
        #      log_debug(f" Final Segment {idx}: {repr(s)}")


        block_idx = self.mw.current_block_idx
        if not (0 <= block_idx < len(self.mw.data)) or not isinstance(self.mw.data[block_idx], list):
             log_debug(f"[MainWindowEventHandlers] paste_block_text: Помилка: Оригінальний блок {block_idx} не існує або не є списком.")
             QMessageBox.warning(self.mw, "Помилка вставки", f"Оригінальні дані для блоку {block_idx} невалідні. Вставку не виконано.")
             return

        block_data_len = len(self.mw.data[block_idx])
        log_debug(f"[MainWindowEventHandlers] paste_block_text: Target block {block_idx} has {block_data_len} original strings.")

        num_segments_to_insert = len(parsed_strings)

        # Перевірка розміру
        if start_string_idx < 0 or start_string_idx >= block_data_len:
             log_debug(f"[MainWindowEventHandlers] paste_block_text: Помилка: Недійсний початковий індекс рядка {start_string_idx} для блоку {block_idx}.")
             QMessageBox.warning(self.mw, "Помилка вставки", f"Недійсний початковий індекс рядка {start_string_idx}. Вставку не виконано.")
             return

        num_target_slots = block_data_len - start_string_idx
        if num_segments_to_insert > num_target_slots:
             QMessageBox.warning(self.mw, "Забагато сегментів",
                                f"Вставлений текст містить {num_segments_to_insert} значущих сегментів.\n"
                                f"Доступно лише {num_target_slots} місць для заміни, починаючи з рядка {start_string_idx}.\n"
                                f"Буде вставлено лише перші {num_target_slots} сегментів.")
             segments_to_use = parsed_strings[:num_target_slots] # Обрізаємо до доступного розміру
             num_segments_to_insert = len(segments_to_use) # Оновлюємо кількість для вставки
        elif num_segments_to_insert < num_target_slots:
              QMessageBox.warning(self.mw, "Замало сегментів",
                                f"Вставлений текст містить лише {num_segments_to_insert} значущих сегментів.\n"
                                f"Для заповнення блоку з рядка {start_string_idx} очікувалося {num_target_slots} сегментів.\n"
                                f"Буде вставлено лише {num_segments_to_insert} сегментів.")
              segments_to_use = parsed_strings # Використовуємо всі доступні сегменти
        else:
            segments_to_use = parsed_strings # Кількість збігається

        log_debug(f"[MainWindowEventHandlers] paste_block_text: Will actually insert {num_segments_to_insert} segments.")

        if num_segments_to_insert == 0:
             log_debug("[MainWindowEventHandlers] paste_block_text: No segments left to insert. Aborting.")
             QMessageBox.information(self.mw, "Вставка", "Після обробки не залишилося сегментів для вставки.")
             return

        changes_made_in_this_paste = False

        try:
            self.mw.edited_text_edit.textChanged.disconnect(self.text_edited)
        except TypeError: pass

        # Проходимося по сегментах, які будемо вставляти
        for i, new_text in enumerate(segments_to_use):
            target_idx = start_string_idx + i
            edit_key = (block_idx, target_idx)

            original_text = self.data_processor._get_string_from_source(block_idx, target_idx, self.mw.data, "original_data")

            if original_text is None:
                log_debug(f"[ActionHandlers] paste_block_text: Помилка: Неправильний індекс при отриманні оригінального тексту для вставки ({block_idx}, {target_idx}). Пропуск цього сегмента.")
                continue

            # Порівнюємо новий текст з оригінальним
            if new_text != original_text:
                if self.mw.edited_data.get(edit_key) != new_text:
                    log_debug(f"[MainWindowEventHandlers] paste_block_text: Text for {edit_key} is different from original. Updating edited_data.")
                    self.mw.edited_data[edit_key] = new_text
                    changes_made_in_this_paste = True
            elif edit_key in self.mw.edited_data:
                 log_debug(f"[MainWindowEventHandlers] paste_block_text: Text for {edit_key} is same as original. Removing from edited_data.")
                 del self.mw.edited_data[edit_key]
                 changes_made_in_this_paste = True

        self.mw.unsaved_changes = bool(self.mw.edited_data)
        log_debug(f"[MainWindowEventHandlers] paste_block_text: After paste loop, unsaved_changes = {self.mw.unsaved_changes}, edited_data size = {len(self.mw.edited_data)}.")

        self.mw.edited_text_edit.textChanged.connect(self.text_edited)


        if changes_made_in_this_paste:
            self.update_title()
            log_debug("[MainWindowEventHandlers] paste_block_text: Changes were made, updating title.")

            log_debug("[MainWindowEventHandlers] paste_block_text: Calling data_processor.save_current_edits(ask_confirmation=False).")
            save_success = self.data_processor.save_current_edits(ask_confirmation=False)
            log_debug(f"[MainWindowEventHandlers] paste_block_text: data_processor.save_current_edits returned {save_success}.")

            current_b_idx = self.mw.current_block_idx
            current_s_idx = self.mw.current_string_idx
            log_debug(f"[MainWindowEventHandlers] paste_block_text: Re-populating UI for block {current_b_idx}, preserving string index {current_s_idx}.")
            self.ui_updater.populate_strings_for_block(current_b_idx)

            if save_success:
                 QMessageBox.information(self.mw, "Вставка та Збереження", f"Успішно вставлено {num_segments_to_insert} сегментів тексту в блок {block_idx}, починаючи з рядка {start_string_idx}, та автоматично збережено у файл змін.")
                 log_debug("[MainWindowEventHandlers] paste_block_text: Showed success message for paste+autosave.")
            else:
                 QMessageBox.warning(self.mw, "Вставка (Помилка збереження)", f"Успішно вставлено {num_segments_to_insert} сегментів тексту в блок {block_idx}, починаючи з рядка {start_string_idx}, але АВТОМАТИЧНЕ ЗБЕРЕЖЕННЯ НЕ ВДАЛОСЯ. Незбережені зміни присутні.")
                 log_debug("[MainWindowEventHandlers] paste_block_text: Showed error message for paste+autosave.")
        else:
             QMessageBox.information(self.mw, "Вставка", "Вставлений текст ідентичний оригінальному тексту в цільових рядках. Зміни не застосовано.")
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