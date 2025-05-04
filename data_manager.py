import json
import os
from PyQt5.QtWidgets import QMessageBox

def load_json_file(file_path, parent_widget=None, expected_type=list):
    """
    Завантажує дані з JSON-файлу.

    Args:
        file_path (str): Шлях до файлу JSON.
        parent_widget (QWidget, optional): Батьківський віджет для QMessageBox. Defaults to None.
        expected_type (type, optional): Очікуваний тип даних верхнього рівня (наприклад, list або dict). Defaults to list.

    Returns:
        tuple: Кортеж (data, error_message).
               data: Завантажені дані (очікуваного типу) або порожній екземпляр типу у разі помилки.
               error_message: Повідомлення про помилку або None, якщо все гаразд.
    """
    data = expected_type() # Повернемо порожній список/словник у разі помилки
    error_message = None

    if not os.path.exists(file_path):
        error_message = f"Файл {file_path} не знайдено."
        print(error_message)
        # Не показуємо QMessageBox тут, щоб дозволити обробку в головному вікні
        return data, error_message

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        if not isinstance(loaded_data, expected_type):
            error_message = f"Файл {file_path} має невірний формат (очікується {expected_type.__name__})."
            print(f"Помилка: {error_message}")
            if parent_widget:
                QMessageBox.warning(parent_widget, "Помилка формату", error_message)
        else:
            data = loaded_data # Успішно завантажено
    except json.JSONDecodeError as e:
        error_message = f"Не вдалося завантажити {file_path}.\nПеревірте формат файлу.\n{e}"
        print(f"Помилка декодування JSON в {file_path}: {e}")
        if parent_widget:
            QMessageBox.critical(parent_widget, "Помилка завантаження", error_message)
    except Exception as e:
        error_message = f"Сталася невідома помилка при завантаженні {file_path}: {e}"
        print(f"Невідома помилка при завантаженні {file_path}: {e}")
        if parent_widget:
            QMessageBox.critical(parent_widget, "Помилка", error_message)

    return data, error_message

def save_json_file(file_path, data_to_save, parent_widget=None):
    """
    Зберігає дані у JSON-файл.

    Args:
        file_path (str): Шлях до файлу для збереження.
        data_to_save: Дані для збереження.
        parent_widget (QWidget, optional): Батьківський віджет для QMessageBox. Defaults to None.

    Returns:
        bool: True, якщо збереження пройшло успішно, інакше False.
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        print(f"Дані успішно збережено у {file_path}")
        return True
    except Exception as e:
        error_message = f"Не вдалося зберегти дані у файл {file_path}.\n{e}"
        print(f"Помилка збереження: {e}")
        if parent_widget:
            QMessageBox.critical(parent_widget, "Помилка збереження", error_message)
        return False