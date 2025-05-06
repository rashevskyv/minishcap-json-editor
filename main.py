import sys
import json
import os
import datetime # Імпортуємо datetime для логування
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QListWidgetItem,
    QInputDialog, QLabel, QFileDialog # Додано QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor
# Імпортуємо віджети та UI setup
from LineNumberedTextEdit import LineNumberedTextEdit
from ui_setup import setup_main_window_ui # Імпортуємо функцію налаштування UI
# Імпортуємо керування даними
from data_manager import load_json_file, save_json_file
# Імпортуємо обробники подій (тепер це головний оркестратор обробки)
from event_handlers import MainWindowEventHandlers # <--- Імпортуємо головний клас обробників
from utils import clean_newline_at_end

def log_debug(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")

class MainWindow(QMainWindow):
    SETTINGS_FILE = "settings.json" # Ім'я файлу налаштувань

    def __init__(self):
        log_debug("MainWindow initialized.")
        super().__init__()
        self.setWindowTitle("JSON Text Editor")
        self.setGeometry(100, 100, 1200, 700)

        # Шляхи та дані (початкові значення за замовчуванням)
        self.json_path = "Ukraine.json"
        self.edited_json_path = "ukranian_edited.json"
        self.data = []
        self.edited_file_data = []
        self.block_names = {} # Буде завантажено з налаштувань
        self.edited_data = {}
        self.current_block_idx = -1
        self.current_string_idx = -1
        self.unsaved_changes = False

        # Атрибути UI
        self.block_list_widget = None
        self.string_list_widget = None
        self.original_text_edit = None
        self.edited_text_edit = None
        self.statusBar = None
        self.pos_len_label = None
        self.selection_len_label = None
        # Додаємо нові атрибути для міток рядка стану
        self.original_path_label = None
        self.edited_path_label = None
        self.handlers = None

        # --- 1. Завантажуємо налаштування (шляхи та імена блоків) ---
        self.load_settings()

        # --- 2. Налаштовуємо UI ---
        log_debug("MainWindow: Calling setup_main_window_ui.")
        setup_main_window_ui(self) # Створює віджети ТА мітки в рядку стану
        log_debug("MainWindow: setup_main_window_ui finished.")

        # --- 3. Створюємо головний обробник подій ---
        log_debug("MainWindow: Creating MainWindowEventHandlers instance.")
        self.handlers = MainWindowEventHandlers(self)
        log_debug("MainWindow: MainWindowEventHandlers instance created.")

        # --- 4. Підключаємо сигнали до handlers ---
        log_debug("MainWindow: Connecting signals to handlers.")
        self.block_list_widget.currentItemChanged.connect(self.handlers.block_selected)
        self.block_list_widget.itemDoubleClicked.connect(self.handlers.rename_block)
        self.string_list_widget.currentItemChanged.connect(self.handlers.string_selected)
        self.edited_text_edit.textChanged.connect(self.handlers.text_edited)
        self.edited_text_edit.cursorPositionChanged.connect(self.handlers.update_status_bar)
        self.edited_text_edit.selectionChanged.connect(self.handlers.update_status_bar_selection)

        # Підключаємо дії меню
        menubar = self.menuBar()
        for action in menubar.actions():
            menu_title = action.text()
            if menu_title == '&Файл':
                for file_action in action.menu().actions():
                    action_text = file_action.text()
                    if action_text != 'Вихід': # Відключаємо всі, крім Вихід
                        try: file_action.triggered.disconnect()
                        except TypeError: pass

                    if action_text == '&Відкрити файл оригіналу...':
                        file_action.triggered.connect(self.open_original_file_dialog)
                    elif action_text == '&Зберегти зміни':
                        file_action.triggered.connect(self.handlers.save_data)
                    elif action_text == 'Зберегти зміни &як...':
                        file_action.triggered.connect(self.save_as_file_dialog)
                    elif action_text == 'Перезавантажити оригінал':
                        file_action.triggered.connect(self.reload_original_data_action)
                    log_debug(f"MainWindow: Connected File menu action: '{action_text}'.")

            elif menu_title == '&Редагування':
                 for edit_action in action.menu().actions():
                      if edit_action.text() == '&Вставити блок':
                           try: edit_action.triggered.disconnect()
                           except TypeError: pass
                           edit_action.triggered.connect(self.handlers.paste_block_text)
                           log_debug("MainWindow: Connected Edit menu action: '&Вставити блок'.")

        log_debug("MainWindow: Signal connections complete.")

        # --- 5. Завантажуємо дані з файлів ---
        log_debug("MainWindow: Loading initial data.")
        self.load_original_data()
        self.load_edited_data()
        log_debug("MainWindow: Initial data loading finished.")

        # --- 6. Заповнюємо початкові дані UI через handlers ---
        log_debug("MainWindow: Populating initial UI.")
        self.handlers.populate_blocks()
        self.handlers.clear_status_bar()
        self.handlers.update_title() # Оновлюємо заголовок з урахуванням шляхів
        self.handlers.update_statusbar_paths() # <--- ВИКЛИКАЄМО ОНОВЛЕННЯ ШЛЯХІВ
        log_debug("MainWindow initialization complete.")

    # --- Методи для роботи з налаштуваннями ---
    def load_settings(self):
        # ... (код load_settings без змін) ...
        log_debug(f"MainWindow: Loading settings from {self.SETTINGS_FILE}.")
        if os.path.exists(self.SETTINGS_FILE):
            try:
                with open(self.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                self.json_path = settings.get('original_file_path', self.json_path)
                self.edited_json_path = settings.get('edited_file_path', self.edited_json_path)
                loaded_block_names = settings.get('block_names', {})
                self.block_names = {int(k): v for k, v in loaded_block_names.items() if k.isdigit()}
                log_debug(f"MainWindow: Settings loaded. Original: '{self.json_path}', Edited: '{self.edited_json_path}', Block names: {len(self.block_names)} items.")
            except json.JSONDecodeError:
                log_debug(f"MainWindow: Error decoding JSON from {self.SETTINGS_FILE}. Using default settings.")
            except Exception as e:
                log_debug(f"MainWindow: Error loading settings from {self.SETTINGS_FILE}: {e}. Using default settings.")
        else:
            log_debug(f"MainWindow: Settings file {self.SETTINGS_FILE} not found. Using default settings.")


    def save_settings(self):
        # ... (код save_settings без змін) ...
        log_debug(f"MainWindow: Saving settings to {self.SETTINGS_FILE}.")
        settings = {
            'original_file_path': self.json_path,
            'edited_file_path': self.edited_json_path,
            'block_names': {str(k): v for k, v in self.block_names.items()}
        }
        try:
            with open(self.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
            log_debug("MainWindow: Settings saved successfully.")
        except Exception as e:
            log_debug(f"MainWindow: Error saving settings to {self.SETTINGS_FILE}: {e}")
            QMessageBox.warning(self, "Помилка збереження налаштувань",
                                f"Не вдалося зберегти налаштування у файл {self.SETTINGS_FILE}:\n{e}")


    # --- Методи для роботи з файлами ---

    def open_original_file_dialog(self):
        """Відкриває діалог вибору файлу оригіналу JSON."""
        log_debug("MainWindow: open_original_file_dialog called.")
        if self.unsaved_changes:
            reply = QMessageBox.question(self, 'Незбережені зміни',
                                         "Відкриття нового файлу призведе до втрати незбережених змін.\nПродовжити?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                log_debug("MainWindow: open_original_file_dialog cancelled by user due to unsaved changes.")
                return

        options = QFileDialog.Options()
        start_dir = os.path.dirname(self.json_path) if os.path.exists(self.json_path) else ""
        fileName, _ = QFileDialog.getOpenFileName(self, "Відкрити файл JSON оригіналу", start_dir,
                                                  "JSON Files (*.json);;All Files (*)", options=options)
        if fileName:
            log_debug(f"MainWindow: User selected original file: {fileName}")
            self.json_path = fileName
            base, ext = os.path.splitext(fileName)
            self.edited_json_path = f"{base}_edited{ext}"
            log_debug(f"MainWindow: New edited file path set to: {self.edited_json_path}")

            self.block_names = {}
            log_debug("MainWindow: Reset block names.")

            log_debug("MainWindow: Reloading data after opening new original file.")
            self.load_original_data()
            self.load_edited_data()

            if self.handlers:
                self.handlers.populate_blocks()
                self.handlers.block_selected(None, None)
                self.handlers.update_title()
                self.handlers.update_statusbar_paths() # <--- ОНОВЛЮЄМО ШЛЯХИ В СТАТУСІ
                self.handlers.clear_status_bar() # Очищаємо позицію/виділення

            self.save_settings() # Зберігаємо нові шляхи та порожні імена блоків

    def save_as_file_dialog(self):
        """Відкриває діалог збереження файлу змін."""
        log_debug("MainWindow: save_as_file_dialog called.")
        options = QFileDialog.Options()
        start_dir = os.path.dirname(self.edited_json_path) if os.path.exists(self.edited_json_path) else ""
        fileName, _ = QFileDialog.getSaveFileName(self, "Зберегти зміни як...", start_dir,
                                                  "JSON Files (*.json);;All Files (*)", options=options)
        if fileName:
            log_debug(f"MainWindow: User selected file to save as: {fileName}")
            if not fileName.lower().endswith('.json'):
                fileName += '.json'
                log_debug(f"MainWindow: Appended .json extension: {fileName}")

            old_edited_path = self.edited_json_path
            self.edited_json_path = fileName

            log_debug("MainWindow: Calling handlers.save_data(ask_confirmation=False) for Save As.")
            if self.handlers and self.handlers.save_data(ask_confirmation=False):
                self.handlers.update_title()
                self.handlers.update_statusbar_paths() # <--- ОНОВЛЮЄМО ШЛЯХИ В СТАТУСІ
                self.save_settings() # Зберігаємо новий шлях edited_json_path
                log_debug(f"MainWindow: Saved successfully to {fileName}.")
                QMessageBox.information(self, "Збережено як", f"Зміни успішно збережено у\n{fileName}")
            else:
                log_debug(f"MainWindow: Failed to save to {fileName}. Reverting edited_json_path.")
                self.edited_json_path = old_edited_path
                # Повідомлення про помилку вже мало бути показане
        else:
            log_debug("MainWindow: Save As dialog cancelled by user.")


    # Методи завантаження даних (без змін з попередньої версії)
    def load_original_data(self):
        """Завантажує дані з основного файлу JSON, використовуючи data_manager."""
        log_debug(f"MainWindow: Loading original data from {self.json_path}.")
        loaded_data, error_message = load_json_file(self.json_path, parent_widget=self, expected_type=list)
        if loaded_data is not None and isinstance(loaded_data, list): # Перевіряємо тип
             self.data = loaded_data
             log_debug(f"MainWindow: Original data loaded successfully. Size: {len(self.data)} blocks.")
             # Скидаємо незбережені зміни та прапорець при перезавантаженні оригіналу
             self.edited_data = {}
             self.unsaved_changes = False
             log_debug("MainWindow: Reset edited_data and unsaved_changes.")
        else:
            # Якщо була помилка або невірний тип, data буде порожнім списком
            self.data = []
            log_debug(f"MainWindow: Error loading original data or invalid format: {error_message}. Resetting data to [].")

        if error_message and "не знайдено" in error_message:
             log_debug(f"MainWindow: Original file not found: {error_message}.")
             # QMessageBox вже показано load_json_file

    def load_edited_data(self):
        """Завантажує дані з файлу зі змінами, використовуючи data_manager."""
        log_debug(f"MainWindow: Loading edited data from {self.edited_json_path}.")
        show_error_box = os.path.exists(self.edited_json_path)
        parent_for_errors = self if show_error_box else None
        loaded_data, error_message = load_json_file(self.edited_json_path, parent_widget=parent_for_errors, expected_type=list)

        if loaded_data is not None and isinstance(loaded_data, list): # Перевіряємо тип
             self.edited_file_data = loaded_data
             log_debug(f"MainWindow: Edited data loaded successfully. Size: {len(self.edited_file_data) if self.edited_file_data else 0}).")
        else:
            # Якщо була помилка або невірний тип, edited_file_data буде порожнім списком
            self.edited_file_data = []
            log_debug(f"MainWindow: Error loading edited data or invalid format: {error_message}. Resetting edited_file_data to [].")

        if not show_error_box and error_message and "не знайдено" in error_message:
             log_debug(f"MainWindow: Edited file not found: {error_message}. Will be created on save.")
        elif error_message and show_error_box:
             log_debug(f"MainWindow: Error loading existing edited file: {error_message}.")
             # QMessageBox вже показано load_json_file


    # --- Метод перезавантаження (підключений до меню) ---
    def reload_original_data_action(self):
        """Дія для перезавантаження оригінального файлу."""
        log_debug("MainWindow: reload_original_data_action called.")
        if self.unsaved_changes:
             reply = QMessageBox.question(self, 'Незбережені зміни',
                                          "Перезавантаження оригінального файлу призведе до втрати незбережених змін.\nПродовжити?",
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
             if reply == QMessageBox.No:
                 log_debug("MainWindow: reload_original_data_action cancelled by user due to unsaved changes.")
                 return

        log_debug("MainWindow: Proceeding with reload_original_data.")
        self.load_original_data()
        self.load_edited_data()

        if self.handlers:
            self.handlers.populate_blocks()
            self.handlers.block_selected(None, None)
            self.handlers.update_title()
            self.handlers.update_statusbar_paths() # <--- ОНОВЛЮЄМО ШЛЯХИ В СТАТУСІ
            self.handlers.clear_status_bar()
            QMessageBox.information(self, "Перезавантажено", f"Оригінальний файл {self.json_path} перезавантажено.")
            log_debug("MainWindow: reload_original_data_action finished successfully.")
        else:
             log_debug("MainWindow: Handlers not initialized, cannot complete UI update after reload.")
             QMessageBox.warning(self, "Помилка", "Не вдалося оновити UI після перезавантаження оригінального файлу.")


    def closeEvent(self, event):
        """Перенаправляє подію закриття до обробника ТА ЗБЕРІГАЄ НАЛАШТУВАННЯ."""
        log_debug("MainWindow: closeEvent called.")
        if self.handlers:
            self.handlers.closeEvent(event)
            if event.isAccepted():
                log_debug("MainWindow: closeEvent accepted. Saving settings.")
                self.save_settings()
            else:
                 log_debug("MainWindow: closeEvent ignored (e.g., user cancelled save). Settings not saved.")
        else:
            log_debug("MainWindow: Handlers not initialized during closeEvent. Accepting event without checking changes.")
            event.accept()
            # Налаштування не зберігаються, якщо програма закрилась до ініціалізації handlers


if __name__ == '__main__':
    import datetime
    def log_debug(message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] {message}")

    def clean_newline_at_end(text):
        """Видаляє \n наприкінці строки, якщо він є. Якщо строка лише '\n', повертає ''."""
        if text == "\n":
            return ""
        elif text.endswith("\n"):
            return text[:-1]
        return text

    log_debug("Application starting.")
    app = QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.show()
    log_debug("Application exec().")
    sys.exit(app.exec_())