import json
import os
import datetime
from PyQt5.QtWidgets import QMessageBox
from data_manager import load_json_file, save_json_file # Імпортуємо функції завантаження/збереження

def log_debug(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")

class DataStateProcessor:
    def __init__(self, main_window):
        log_debug("DataStateProcessor initialized.")
        self.mw = main_window # Посилання на головне вікно

    def _get_string_from_source(self, block_idx, string_idx, source_data, source_name):
        """Допоміжний метод для безпечного отримання рядка з джерела даних."""
        if 0 <= block_idx < len(source_data) and \
           isinstance(source_data[block_idx], list) and \
           0 <= string_idx < len(source_data[block_idx]):
            return source_data[block_idx][string_idx]
        # log_debug(f"[_get_string_from_source] Index ({block_idx}, {string_idx}) out of bounds for {source_name}.")
        return None # Повертаємо None, якщо індекс недійсний або структура невірна

    def get_current_string_text(self, block_idx, string_idx):
        """
        Повертає поточний текст для заданого рядка:
        1. З незбережених змін (self.mw.edited_data)
        2. Зі збережених змін (self.mw.edited_file_data)
        3. З оригінальних даних (self.mw.data)
        Повертає текст та джерело ("edited_data", "edited_file_data", "original_data", "error").
        """
        edit_key = (block_idx, string_idx)

        if edit_key in self.mw.edited_data:
            # log_debug(f"[DataStateProcessor] get_current_string_text: Found in edited_data for key {edit_key}.")
            return self.mw.edited_data[edit_key], "edited_data"

        text = self._get_string_from_source(block_idx, string_idx, self.mw.edited_file_data, "edited_file_data")
        if text is not None:
            # log_debug(f"[DataStateProcessor] get_current_string_text: Found in edited_file_data for key {edit_key}.")
            return text, "edited_file_data"

        text = self._get_string_from_source(block_idx, string_idx, self.mw.data, "original_data")
        if text is not None:
            # log_debug(f"[DataStateProcessor] get_current_string_text: Found in original_data for key {edit_key}.")
            return text, "original_data"

        log_debug(f"[DataStateProcessor] get_current_string_text: Помилка: Індекс ({block_idx}, {string_idx}) поза межами всіх джерел даних.")
        return "[ПОМИЛКА ДАНИХ]", "error"

    def update_edited_data(self, block_idx, string_idx, new_text):
        """Оновлює стан edited_data та визначає, чи змінився unsaved_changes."""
        log_debug(f"[DataStateProcessor] update_edited_data called for ({block_idx}, {string_idx}). New text length: {len(new_text)}")
        edit_key = (block_idx, string_idx)
        old_unsaved_changes = self.mw.unsaved_changes # Зберігаємо старий стан

        original_text = self._get_string_from_source(block_idx, string_idx, self.mw.data, "original_data")
        if original_text is None:
            log_debug(f"[DataStateProcessor] Помилка: Не вдалося отримати оригінальний текст для порівняння ({block_idx}, {string_idx}). Зміна буде записана, але стан 'unsaved' може бути неточним.")
            # Якщо оригінал недоступний, будь-яка зміна вважається значущою, якщо вона відрізняється від того, що вже є в edited_data
            if self.mw.edited_data.get(edit_key) != new_text:
                self.mw.edited_data[edit_key] = new_text
            # unsaved_changes може змінитися пізніше, якщо edited_data перестане бути порожнім
        elif new_text != original_text:
            # Зміна є, записуємо або оновлюємо в edited_data
            if self.mw.edited_data.get(edit_key) != new_text:
                log_debug(f"[DataStateProcessor] Text for ({block_idx}, {string_idx}) changed from original. Updating edited_data.")
                self.mw.edited_data[edit_key] = new_text
        elif edit_key in self.mw.edited_data:
            # Зміна стала ідентичною оригіналу, видаляємо з edited_data
            log_debug(f"[DataStateProcessor] Text for ({block_idx}, {string_idx}) reverted to original. Removing from edited_data.")
            del self.mw.edited_data[edit_key]

        # Оновлюємо стан unsaved_changes
        self.mw.unsaved_changes = bool(self.mw.edited_data)
        log_debug(f"[DataStateProcessor] After update, unsaved_changes = {self.mw.unsaved_changes}, edited_data size = {len(self.mw.edited_data)}.")

        return self.mw.unsaved_changes != old_unsaved_changes # Повертаємо True, якщо unsaved_changes змінився

    def save_current_edits(self, ask_confirmation=True):
        """Зберігає поточні та попередні зміни у файл ukranian_edited.json."""
        log_debug(f"[DataStateProcessor] save_current_edits called with ask_confirmation={ask_confirmation}.")
        has_pending_edits = bool(self.mw.edited_data)
        log_debug(f"[DataStateProcessor] save_current_edits: has_pending_edits = {has_pending_edits}.")

        save_needed = has_pending_edits # Потрібно зберігати, якщо є зміни в edited_data
        prompt_user_to_clean = False

        if not save_needed and os.path.exists(self.mw.edited_json_path):
             prompt_user_to_clean = True
             log_debug(f"[DataStateProcessor] save_current_edits: No pending edits, but {self.mw.edited_json_path} exists. Prompting user to clean.")


        if prompt_user_to_clean:
             if ask_confirmation:
                 reply = QMessageBox.question(self.mw, 'Збереження змін',
                                                f"Незбережених змін немає.\nФайл змін {self.mw.edited_json_path} вже існує.\nОновити його до поточної (ідентичної оригіналу) версії даних?",
                                                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                                                QMessageBox.No)
                 if reply == QMessageBox.Yes:
                      save_needed = "clean" # Потрібно зберегти, щоб очистити файл
                      log_debug("[DataStateProcessor] save_current_edits: User chose Yes to clean file.")
                 elif reply == QMessageBox.No:
                     log_debug("[DataStateProcessor] save_current_edits: User chose No to clean file. Returning True.")
                     return True # Нічого не зберігали, але дія "збереження" не була скасована
                 else: # Cancel
                     log_debug("[DataStateProcessor] save_current_edits: User chose Cancel. Returning False.")
                     return False # Користувач скасував дію
             else:
                 # Автоматичне збереження (ask_confirmation=False) при відсутності pending_edits не призводить до "очищення" файлу.
                 log_debug("[DataStateProcessor] save_current_edits: No pending edits and ask_confirmation=False. Skipping save.")
                 return True # Вважаємо успіхом


        elif not save_needed and not os.path.exists(self.mw.edited_json_path):
             # Немає змін і файл змін не існує. Нічого зберігати.
             log_debug(f"[DataStateProcessor] save_current_edits: No pending edits, and {self.mw.edited_json_path} does not exist.")
             if ask_confirmation:
                 QMessageBox.information(self.mw, "Збереження", "Незбережених змін немає для збереження.")
             return True # Вважаємо успіхом


        # Якщо save_needed True (є pending_edits) або save_needed "clean"
        if save_needed:
            if ask_confirmation and save_needed != "clean": # Виправлено синтаксис Warning: "is not"
                reply = QMessageBox.question(self.mw, 'Збереження змін',
                                             f"Зберегти всі поточні зміни у файл\n{self.mw.edited_json_path}?\nЦе оновить файл, зберігаючи попередні зміни та додаючи нові.",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    log_debug("[DataStateProcessor] save_current_edits: User chose No to save pending edits. Returning False.")
                    return False # Користувач обрав не зберігати
                # Якщо reply == QMessageBox.Yes, продовжуємо
                # Якщо ask_confirmation = False, продовжуємо без діалогу

            log_debug("[DataStateProcessor] save_current_edits: Proceeding with saving.")
            try:
                # 1. Створюємо вихідні дані.
                # Якщо режим "clean", просто копіюємо оригінал.
                # Якщо є pending_edits, спочатку застосовуємо старі збережені зміни до копії оригіналу,
                # а потім застосовуємо поточні pending_edits.

                if save_needed == "clean":
                    output_data = json.loads(json.dumps(self.mw.data))
                    log_debug("[DataStateProcessor] save_current_edits: Preparing output data for cleaning file (copy of original).")
                else: # save_needed is True (has_pending_edits)
                    log_debug("[DataStateProcessor] save_current_edits: Preparing output data by merging existing and pending edits.")
                    # Копіюємо оригінал як базу
                    output_data = json.loads(json.dumps(self.mw.data))
                    log_debug(f"[DataStateProcessor] save_current_edits: Created copy of original data (size: {len(output_data)}).")

                    # Завантажуємо і застосовуємо старі збережені зміни з existing_edited_data до output_data
                    existing_edited_data, _ = load_json_file(self.mw.edited_json_path, parent_widget=None, expected_type=list)
                    log_debug(f"[DataStateProcessor] save_current_edits: Loaded existing edited data (size: {len(existing_edited_data) if existing_edited_data else 0}).")

                    if existing_edited_data:
                        log_debug("[DataStateProcessor] save_current_edits: Merging existing edited data into output data.")
                        for b_idx, block in enumerate(existing_edited_data):
                             try:
                                 if 0 <= b_idx < len(self.mw.data) and isinstance(output_data[b_idx], list):
                                     if isinstance(block, list):
                                         for s_idx, text in enumerate(block):
                                             # Apply if different from original AND fits in the output structure
                                             if 0 <= s_idx < len(self.mw.data[b_idx]) and text != self.mw.data[b_idx][s_idx]:
                                                if 0 <= s_idx < len(output_data[b_idx]):
                                                    output_data[b_idx][s_idx] = text
                             except Exception as e:
                                 log_debug(f"save_current_edits: Error processing existing_edited_data for block {b_idx}: {e}")

                    # Застосовуємо поточні незбережені зміни з self.mw.edited_data.
                    log_debug(f"[DataStateProcessor] save_current_edits: Merging {len(self.mw.edited_data)} pending edits into output data.")
                    for (b_idx, s_idx), edited_text in self.mw.edited_data.items():
                        try:
                            if 0 <= b_idx < len(self.mw.data) and 0 <= s_idx < len(self.mw.data[b_idx]):
                                if isinstance(output_data[b_idx], list) and 0 <= s_idx < len(output_data[b_idx]):
                                     output_data[b_idx][s_idx] = edited_text
                                else:
                                     log_debug(f"save_current_edits: Warning: Line {s_idx} in block {b_idx} from edited_data is outside output data structure ({len(output_data[b_idx])} lines). Skipping.")
                            else:
                                 log_debug(f"save_current_edits: Error: Invalid index ({b_idx}, {s_idx}) in edited_data (beyond original data size). Skipping.")

                        except IndexError:
                            log_debug(f"save_current_edits: Error: Invalid index ({b_idx}, {s_idx}) when applying pending edits.")
                        except Exception as e:
                            log_debug(f"save_current_edits: Unknown error when applying pending edits ({b_idx}, {s_idx}): {e}")


                # 3. Зберігаємо результат.
                log_debug(f"[DataStateProcessor] save_current_edits: Calling save_json_file for {self.mw.edited_json_path}.")
                if save_json_file(self.mw.edited_json_path, output_data, parent_widget=self.mw):
                    log_debug("[DataStateProcessor] save_current_edits: File saved successfully.")
                    self.mw.unsaved_changes = False # Тепер зміни збережені
                    self.mw.edited_data = {} # Очищаємо поточні незбережені зміни
                    self.mw.edited_file_data = output_data # Оновлюємо завантажені дані зміненого файлу
                    # update_title викликається у ActionHandlers після успіху
                    if ask_confirmation and save_needed != "clean": # Виправлено синтаксис Warning: "is not"
                         QMessageBox.information(self.mw, "Збережено", f"Зміни успішно збережено у\n{self.mw.edited_json_path}")
                    elif save_needed == "clean": # Повідомлення про очищення файла
                         QMessageBox.information(self.mw, "Збережено", f"Файл змін {self.mw.edited_json_path} оновлено до оригінальної версії.")

                    return True # Збереження успішне
                else:
                    # Якщо збереження не вдалося, unsaved_changes залишається True (бо edited_data не був очищений),
                    # і closeEvent побачить це і запитає знову.
                    log_debug("[DataStateProcessor] save_current_edits: File saving failed. Returning False.")
                    return False # Збереження не успішне

            except Exception as e:
                QMessageBox.critical(self.mw, "Помилка збереження", f"Сталася непередбачена помилка під час підготовки даних для збереження:\n{e}")
                log_debug(f"[DataStateProcessor] save_current_edits: Uncaught exception during data preparation: {e}")
                return False
        else:
             # Цей випадок не повинен траплятись, якщо логіка коректна (якщо save_needed False, ми повертаємо True раніше)
             log_debug("[DataStateProcessor] save_current_edits: Reached unexpected state. Returning True.")
             return True # Немає змін, нічого зберігати