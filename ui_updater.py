import datetime
import os # Потрібен для отримання імені файлу
from PyQt5.QtWidgets import QListWidgetItem
from PyQt5.QtCore import Qt

def log_debug(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


class UIUpdater:
    def __init__(self, main_window, data_processor):
        log_debug("UIUpdater initialized.")
        self.mw = main_window # Посилання на головне вікно
        self.data_processor = data_processor # Посилання на обробник стану даних

    def populate_blocks(self):
        # ... (код populate_blocks без змін) ...
        log_debug("[UIUpdater] populate_blocks called.")
        self.mw.block_list_widget.clear()
        if not self.mw.data:
            log_debug("[UIUpdater] populate_blocks: No original data loaded.")
            return
        for i in range(len(self.mw.data)):
            display_name = self.mw.block_names.get(i, f"Блок {i}")
            item = self.mw.block_list_widget.create_item(display_name, i)
            self.mw.block_list_widget.addItem(item)
        log_debug(f"[UIUpdater] populate_blocks: Added {len(self.mw.data)} blocks.")


    def populate_strings_for_block(self, block_idx):
        # ... (код populate_strings_for_block без змін) ...
        log_debug(f"[UIUpdater] populate_strings_for_block called for block_idx: {block_idx}")
        try:
            self.mw.string_list_widget.currentItemChanged.disconnect(self.mw.handlers.string_selected)
        except TypeError: pass

        self.mw.string_list_widget.clear()
        self.mw.original_text_edit.clear()
        self.mw.edited_text_edit.clear()

        if block_idx == -1 or not (0 <= block_idx < len(self.mw.data)):
            log_debug(f"[UIUpdater] populate_strings_for_block: Invalid block_idx {block_idx} or no data. Resetting.")
            self.mw.current_block_idx = -1
            self.mw.current_string_idx = -1
            self.clear_status_bar()
            try:
                self.mw.string_list_widget.currentItemChanged.connect(self.mw.handlers.string_selected)
            except TypeError: pass
            return

        self.mw.current_block_idx = block_idx
        block_data = self.mw.data[self.mw.current_block_idx]
        log_debug(f"[UIUpdater] populate_strings_for_block: Processing block {block_idx} with {len(block_data)} strings.")


        if isinstance(block_data, list):
            current_string_item_to_select = None
            for i in range(len(block_data)):
                text_for_display, source = self.data_processor.get_current_string_text(self.mw.current_block_idx, i)
                display_text_repr = repr(text_for_display)
                if len(display_text_repr) > 60:
                    display_text_repr = display_text_repr[:57] + '...'
                item = self.mw.string_list_widget.create_item(f"{i}: {display_text_repr}", i)
                self.mw.string_list_widget.addItem(item)
                if i == self.mw.current_string_idx:
                    current_string_item_to_select = item
                    log_debug(f"[UIUpdater] populate_strings_for_block: Found item to re-select for index {i}.")

            if current_string_item_to_select:
                self.mw.string_list_widget.blockSignals(True)
                self.mw.string_list_widget.setCurrentItem(current_string_item_to_select)
                self.mw.string_list_widget.blockSignals(False)
            else:
                log_debug("[UIUpdater] populate_strings_for_block: No item to re-select. Resetting current string index.")
                self.mw.current_string_idx = -1
                self.clear_status_bar()

        else:
            log_debug(f"[UIUpdater] populate_strings_for_block: Помилка: Блок {self.mw.current_block_idx} не є списком.")
            self.mw.current_block_idx = -1
            self.mw.current_string_idx = -1
            self.clear_status_bar()

        try:
            self.mw.string_list_widget.currentItemChanged.connect(self.mw.handlers.string_selected)
        except TypeError: pass
        log_debug("[UIUpdater] populate_strings_for_block: Finished.")

    def update_string_list_item_text(self, string_idx, new_text_for_preview):
        # ... (код update_string_list_item_text без змін) ...
        log_debug(f"[UIUpdater] update_string_list_item_text called for index {string_idx}.")
        item = self.mw.string_list_widget.item(string_idx)
        if item:
            display_text_repr = repr(new_text_for_preview)
            if len(display_text_repr) > 60:
                display_text_repr = display_text_repr[:57] + '...'
            item.setText(f"{string_idx}: {display_text_repr}")
            log_debug(f"[UIUpdater] update_string_list_item_text: Updated list item {string_idx} preview.")
        else:
            log_debug(f"[UIUpdater] update_string_list_item_text: Item {string_idx} not found in list.")


    def update_status_bar(self):
        # ... (код update_status_bar без змін) ...
        if not self.mw.edited_text_edit or not self.mw.pos_len_label:
            return
        cursor = self.mw.edited_text_edit.textCursor()
        block = cursor.block()
        pos_in_block = cursor.position() - block.position()
        line_len = len(block.text())
        self.mw.pos_len_label.setText(f"{pos_in_block}/{line_len}")


    def update_status_bar_selection(self):
        # ... (код update_status_bar_selection без змін) ...
        if not self.mw.edited_text_edit or not self.mw.selection_len_label:
            return
        cursor = self.mw.edited_text_edit.textCursor()
        selection_len = abs(cursor.selectionStart() - cursor.selectionEnd())
        self.mw.selection_len_label.setText(f"{selection_len}")


    def clear_status_bar(self):
        # ... (код clear_status_bar без змін) ...
        log_debug("[UIUpdater] clear_status_bar called.")
        if self.mw.pos_len_label:
            self.mw.pos_len_label.setText("")
        if self.mw.selection_len_label:
            self.mw.selection_len_label.setText("0")

    def update_title(self):
        # ... (код update_title без змін) ...
        log_debug("[UIUpdater] update_title called.")
        title = "JSON Text Editor"
        # Додаємо ім'я відкритого файлу оригіналу до заголовка
        if self.mw.json_path:
            title += f" - [{os.path.basename(self.mw.json_path)}]"
        if self.mw.unsaved_changes:
            title += " *"
        self.mw.setWindowTitle(title)
        log_debug(f"[UIUpdater] update_title: Title set to '{title}'.")

    def update_statusbar_paths(self):
        """Оновлює мітки шляхів до файлів в рядку стану."""
        log_debug("[UIUpdater] update_statusbar_paths called.")
        if self.mw.original_path_label:
            orig_filename = os.path.basename(self.mw.json_path) if self.mw.json_path else "[не вказано]"
            self.mw.original_path_label.setText(f"Оригінал: {orig_filename}")
            self.mw.original_path_label.setToolTip(self.mw.json_path if self.mw.json_path else "Шлях до файлу з оригінальним текстом")
            log_debug(f"[UIUpdater] update_statusbar_paths: Original path set to '{orig_filename}'.")

        if self.mw.edited_path_label:
            edited_filename = os.path.basename(self.mw.edited_json_path) if self.mw.edited_json_path else "[не вказано]"
            self.mw.edited_path_label.setText(f"Зміни: {edited_filename}")
            self.mw.edited_path_label.setToolTip(self.mw.edited_json_path if self.mw.edited_json_path else "Шлях до файлу, куди зберігаються зміни")
            log_debug(f"[UIUpdater] update_statusbar_paths: Edited path set to '{edited_filename}'.")