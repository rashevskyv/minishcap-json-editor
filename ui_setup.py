from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QSplitter,
    QLabel, QAction, QStatusBar, QMenu, QApplication
)
from PyQt5.QtCore import Qt
# Імпортуємо LineNumberedTextEdit
from LineNumberedTextEdit import LineNumberedTextEdit
# Імпортуємо кастомний QListWidget
from CustomListWidget import CustomListWidget

def setup_main_window_ui(main_window):
    """Налаштовує UI для головного вікна, СТВОРЮЮЧИ віджети."""
    # ... (попередній код створення віджетів без змін) ...

    central_widget = QWidget()
    main_window.setCentralWidget(central_widget)
    main_layout = QHBoxLayout(central_widget)

    # --- Ліва панель (Список блоків) ---
    left_panel = QWidget()
    left_layout = QVBoxLayout(left_panel)
    left_layout.addWidget(QLabel("Блоки (подвійний клік для перейменування):"))
    main_window.block_list_widget = CustomListWidget()
    left_layout.addWidget(main_window.block_list_widget)

    # --- Права панель (Розділена) ---
    right_splitter = QSplitter(Qt.Vertical)

    # --- Верхня права панель (Список рядків) ---
    top_right_panel = QWidget()
    top_right_layout = QVBoxLayout(top_right_panel)
    top_right_layout.addWidget(QLabel("Рядки в блоці:"))
    main_window.string_list_widget = CustomListWidget()
    top_right_layout.addWidget(main_window.string_list_widget)
    right_splitter.addWidget(top_right_panel)

    # --- Нижня права панель (Розділена) ---
    bottom_right_splitter = QSplitter(Qt.Horizontal)

    # --- Нижнє ліве поле (Оригінал) ---
    bottom_left_panel = QWidget()
    bottom_left_layout = QVBoxLayout(bottom_left_panel)
    bottom_left_layout.addWidget(QLabel("Оригінал (Read-Only):"))
    main_window.original_text_edit = LineNumberedTextEdit()
    main_window.original_text_edit.setReadOnly(True)
    bottom_left_layout.addWidget(main_window.original_text_edit)
    bottom_right_splitter.addWidget(bottom_left_panel)

    # --- Нижнє праве поле (Редагований текст) ---
    bottom_right_panel = QWidget()
    bottom_right_layout = QVBoxLayout(bottom_right_panel)
    bottom_right_layout.addWidget(QLabel("Редагований текст:"))
    main_window.edited_text_edit = LineNumberedTextEdit()
    bottom_right_layout.addWidget(main_window.edited_text_edit)
    bottom_right_splitter.addWidget(bottom_right_panel)

    right_splitter.addWidget(bottom_right_splitter)
    right_splitter.setSizes([200, 500])
    bottom_right_splitter.setSizes([500, 500])

    # --- Головний спліттер ---
    main_splitter = QSplitter(Qt.Horizontal)
    main_splitter.addWidget(left_panel)
    main_splitter.addWidget(right_splitter)
    main_splitter.setSizes([250, 950])

    main_layout.addWidget(main_splitter)

    # --- Рядок стану ---
    main_window.statusBar = QStatusBar()
    main_window.setStatusBar(main_window.statusBar)

    # Створюємо мітки для шляхів (з початковими плейсхолдерами)
    main_window.original_path_label = QLabel("Оригінал: [не вказано]")
    main_window.edited_path_label = QLabel("Зміни: [не вказано]")
    main_window.original_path_label.setToolTip("Шлях до файлу з оригінальним текстом")
    main_window.edited_path_label.setToolTip("Шлях до файлу, куди зберігаються зміни")

    # Мітки для позиції курсора та виділення
    main_window.pos_len_label = QLabel("")
    main_window.selection_len_label = QLabel("0")

    # Додаємо мітки до рядка стану (ліворуч)
    main_window.statusBar.addWidget(main_window.original_path_label)
    main_window.statusBar.addWidget(QLabel("|")) # Роздільник
    main_window.statusBar.addWidget(main_window.edited_path_label)

    # Додаємо постійні мітки до рядка стану (праворуч)
    main_window.statusBar.addPermanentWidget(main_window.pos_len_label)
    main_window.statusBar.addPermanentWidget(main_window.selection_len_label)


    # --- Меню ---
    # (Створення меню та дій залишається без змін)
    menubar = main_window.menuBar()
    file_menu = menubar.addMenu('&Файл')

    open_action = QAction('&Відкрити файл оригіналу...', main_window)
    file_menu.addAction(open_action)
    file_menu.addSeparator()
    save_action = QAction('&Зберегти зміни', main_window)
    save_action.setShortcut('Ctrl+S')
    file_menu.addAction(save_action)
    save_as_action = QAction('Зберегти зміни &як...', main_window)
    file_menu.addAction(save_as_action)
    file_menu.addSeparator()
    reload_action = QAction('Перезавантажити оригінал', main_window)
    file_menu.addAction(reload_action)
    file_menu.addSeparator()
    exit_action = QAction('Вихід', main_window)
    exit_action.triggered.connect(main_window.close)
    file_menu.addAction(exit_action)

    edit_menu = menubar.addMenu('&Редагування')
    paste_block_action = QAction('&Вставити блок', main_window)
    paste_block_action.setShortcut('Ctrl+Shift+V')
    edit_menu.addAction(paste_block_action)