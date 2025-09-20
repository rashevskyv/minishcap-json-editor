import os

# --- Конфігурація ---
# Файли та директорії, які потрібно виключити з обробки.
EXCLUDE_FILES = {'tree.py', 'tree.txt', '.gitignore'}
EXCLUDE_DIRS = {'__pycache__', '.git', 'font_tool', 'venv'}

# Нова конфігурація: розширення файлів, до яких потрібно додавати заголовок.
# Задано у вигляді кортежу для використання з методом .endswith()
TARGET_EXTENSIONS = ('.py', '.md')


def add_header_if_missing(file_path, root_dir):
    """
    Перевіряє, чи є у файлі заголовок-коментар із його шляхом.
    Якщо заголовок відсутній, він додається на початок файлу.
    """
    try:
        # Обчислюємо відносний шлях, який буде вставлено в коментар.
        relative_path = os.path.relpath(file_path, root_dir).replace('\\', '/')
        expected_header = f"# --- START OF FILE {relative_path} ---\n"

        # Намагаємося прочитати файл у кодуванні utf-8.
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content_lines = f.readlines()
        except UnicodeDecodeError:
            # Якщо файл не є текстовим, нічого з ним не робимо.
            return

        # Якщо файл порожній або заголовок вже існує, нічого не робимо.
        if not content_lines or content_lines[0] == expected_header:
            return

        # Якщо заголовок відсутній, готуємо новий вміст і перезаписуємо файл.
        new_content = [expected_header] + content_lines
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_content)
        
        print(f"Додано заголовок до: {relative_path}")

    except Exception as e:
        print(f"Помилка при обробці файлу {file_path}: {e}")


def tree(dir_path, root_dir, prefix="", log_file=None, is_last=True, root=True):
    """
    Рекурсивно генерує структуру дерева каталогів, обробляє файли
    з цільовими розширеннями та підраховує рядки коду в .py файлах.
    Повертає загальну кількість рядків коду.
    """
    lines_count = 0
    entries = [e for e in os.listdir(dir_path) if e not in EXCLUDE_FILES and e not in EXCLUDE_DIRS]
    entries = sorted(entries, key=lambda x: (not os.path.isdir(os.path.join(dir_path, x)), x.lower()))
    
    for idx, entry in enumerate(entries):
        path = os.path.join(dir_path, entry)
        
        # Запис у лог-файл tree.txt (як і раніше).
        if log_file:
            connector = "└── " if idx == len(entries) - 1 else "├── "
            line = ("" if root else prefix) + connector + entry
            log_file.write(line + "\n")
        
        if os.path.isdir(path):
            # Якщо це директорія, продовжуємо обхід і додаємо рядки з піддиректорій.
            extension = "    " if idx == len(entries) - 1 else "│   "
            lines_count += tree(path, root_dir, prefix + extension, log_file, idx == len(entries) - 1, False)
        else:
            # Якщо це файл, перевіряємо його розширення для додавання заголовка.
            if path.lower().endswith(TARGET_EXTENSIONS):
                add_header_if_missing(path, root_dir)

            # --- НОВИЙ БЛОК: Підрахунок рядків для .py файлів ---
            if path.lower().endswith('.py'):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        lines_count += len(f.readlines())
                except Exception as e:
                    print(f"Не вдалося підрахувати рядки у файлі {path}: {e}")

    return lines_count


if __name__ == "__main__":
    # Визначаємо кореневу директорію, де лежить скрипт.
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    total_lines = 0
    # Запускаємо процес.
    with open(os.path.join(root_dir, "tree.txt"), "w", encoding="utf-8") as log:
        # Функція tree тепер повертає загальну кількість рядків,
        # яку ми зберігаємо у змінну total_lines.
        total_lines = tree(root_dir, root_dir=root_dir, log_file=log)
        
    print("\nГенерацію дерева каталогів завершено. Перевірте 'tree.txt'.")
    print(f"Перевірку та оновлення заголовків для файлів {TARGET_EXTENSIONS} завершено.")
    # --- НОВИЙ РЯДОК: Виводимо результат підрахунку в консоль ---
    print(f"Загальна кількість рядків коду в .py файлах: {total_lines}")