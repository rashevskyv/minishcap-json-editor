# --- START OF FILE core/data_manager.py ---
import json
import os
from PyQt5.QtWidgets import QMessageBox
from utils.logging_utils import log_debug

def load_json_file(file_path, parent_widget=None):
    log_debug(f"load_json_file: Attempting to load '{file_path}'")
    data = None
    error_message = None

    if not os.path.exists(file_path):
        error_message = f"File {file_path} not found."
        log_debug(f"load_json_file: Error - {error_message}")
        return data, error_message

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log_debug(f"load_json_file: Successfully loaded '{file_path}'.")
    except json.JSONDecodeError as e:
        error_message = f"Failed to load {file_path}.\nCheck the file format.\n{e}"
        log_debug(f"load_json_file: JSONDecodeError in '{file_path}': {e}")
        if parent_widget:
            QMessageBox.critical(parent_widget, "Load Error", error_message)
    except Exception as e:
        error_message = f"An unknown error occurred while loading {file_path}: {e}"
        log_debug(f"load_json_file: Unknown error loading '{file_path}': {e}")
        if parent_widget:
            QMessageBox.critical(parent_widget, "Error", error_message)

    return data, error_message

def save_json_file(file_path, data_to_save, parent_widget=None):
    log_debug(f"save_json_file: Attempting to save data to '{file_path}'.")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        log_debug(f"save_json_file: Data successfully saved to '{file_path}'")
        return True
    except Exception as e:
        error_message = f"Failed to save data to file {file_path}.\n{e}"
        log_debug(f"save_json_file: Error saving to '{file_path}': {e}")
        if parent_widget:
            QMessageBox.critical(parent_widget, "Save Error", error_message)
        return False

def load_text_file(file_path, parent_widget=None):
    log_debug(f"load_text_file: Attempting to load '{file_path}'")
    content = None
    error_message = None

    if not os.path.exists(file_path):
        error_message = f"File {file_path} not found."
        log_debug(f"load_text_file: Error - {error_message}")
        return content, error_message

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        log_debug(f"load_text_file: Successfully loaded '{file_path}' with UTF-8.")
    except UnicodeDecodeError:
        log_debug(f"load_text_file: UTF-8 decoding failed for '{file_path}'. Trying UTF-16.")
        try:
            with open(file_path, 'r', encoding='utf-16') as f:
                content = f.read()
            log_debug(f"load_text_file: Successfully loaded '{file_path}' with UTF-16.")
        except Exception as e:
            error_message = f"Failed to load {file_path} with both UTF-8 and UTF-16.\n{e}"
            log_debug(f"load_text_file: Unknown error loading '{file_path}' with UTF-16: {e}")
            if parent_widget:
                QMessageBox.critical(parent_widget, "Error", error_message)
    except Exception as e:
        error_message = f"An unknown error occurred while loading {file_path}: {e}"
        log_debug(f"load_text_file: Unknown error loading '{file_path}': {e}")
        if parent_widget:
            QMessageBox.critical(parent_widget, "Error", error_message)

    return content, error_message

def save_text_file(file_path, text_content, parent_widget=None):
    log_debug(f"save_text_file: Attempting to save text content to '{file_path}'.")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
        log_debug(f"save_text_file: Text content successfully saved to '{file_path}'")
        return True
    except Exception as e:
        error_message = f"Failed to save text content to file {file_path}.\n{e}"
        log_debug(f"save_text_file: Error saving to '{file_path}': {e}")
        if parent_widget:
            QMessageBox.critical(parent_widget, "Save Error", error_message)
        return False