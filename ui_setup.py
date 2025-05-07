from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QAction, QStatusBar, QMenu, QPlainTextEdit, QToolBar 
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon 
from LineNumberedTextEdit import LineNumberedTextEdit
from CustomListWidget import CustomListWidget # Переконайтеся, що цей файл існує і коректний
from utils import log_debug

def setup_main_window_ui(main_window):
    log_debug("setup_main_window_ui: Starting UI setup.")
    central_widget = QWidget(); main_window.setCentralWidget(central_widget)
    main_layout = QHBoxLayout(central_widget)
    # ... (решта UI як раніше) ...
    left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
    left_layout.addWidget(QLabel("Blocks (double-click to rename):"))
    main_window.block_list_widget = CustomListWidget(main_window) # Передаємо main_window як батька і для доступу
    left_layout.addWidget(main_window.block_list_widget)
    main_window.right_splitter = QSplitter(Qt.Vertical) 
    top_right_panel = QWidget(); top_right_layout = QVBoxLayout(top_right_panel) 
    top_right_layout.addWidget(QLabel("Strings in block (click line to select):")) 
    main_window.preview_text_edit = LineNumberedTextEdit(main_window) 
    main_window.preview_text_edit.setReadOnly(True)
    main_window.preview_text_edit.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    top_right_layout.addWidget(main_window.preview_text_edit) 
    main_window.right_splitter.addWidget(top_right_panel) 
    main_window.bottom_right_splitter = QSplitter(Qt.Horizontal)
    bottom_left_panel = QWidget(); bottom_left_layout = QVBoxLayout(bottom_left_panel)
    bottom_left_layout.addWidget(QLabel("Original (Read-Only):"))
    main_window.original_text_edit = LineNumberedTextEdit(main_window) 
    main_window.original_text_edit.setReadOnly(True)
    main_window.original_text_edit.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    bottom_left_layout.addWidget(main_window.original_text_edit); main_window.bottom_right_splitter.addWidget(bottom_left_panel)
    bottom_right_panel = QWidget(); bottom_right_layout = QVBoxLayout(bottom_right_panel)
    bottom_right_layout.addWidget(QLabel("Editable Text:"))
    main_window.edited_text_edit = LineNumberedTextEdit(main_window) 
    bottom_right_layout.addWidget(main_window.edited_text_edit); main_window.bottom_right_splitter.addWidget(bottom_right_panel)
    main_window.right_splitter.addWidget(main_window.bottom_right_splitter)
    main_window.right_splitter.setSizes([150, 450]); main_window.bottom_right_splitter.setSizes([400, 400])
    main_window.main_splitter = QSplitter(Qt.Horizontal)
    main_window.main_splitter.addWidget(left_panel); main_window.main_splitter.addWidget(main_window.right_splitter)
    main_window.main_splitter.setSizes([200, 800])
    main_layout.addWidget(main_window.main_splitter)
    main_window.statusBar = QStatusBar(); main_window.setStatusBar(main_window.statusBar)
    main_window.original_path_label = QLabel("Original: [not specified]"); main_window.edited_path_label = QLabel("Changes: [not specified]")
    main_window.original_path_label.setToolTip("Path to the original text file"); main_window.edited_path_label.setToolTip("Path to the file where changes are saved")
    main_window.pos_len_label = QLabel("0/0"); main_window.selection_len_label = QLabel("Sel: 0")
    main_window.statusBar.addWidget(main_window.original_path_label); main_window.statusBar.addWidget(QLabel("|")); main_window.statusBar.addWidget(main_window.edited_path_label)
    main_window.statusBar.addPermanentWidget(main_window.pos_len_label); main_window.statusBar.addPermanentWidget(main_window.selection_len_label)

    menubar = main_window.menuBar()
    file_menu = menubar.addMenu('&File')
    main_window.open_action = QAction('&Open Original File...', main_window); file_menu.addAction(main_window.open_action)
    main_window.open_changes_action = QAction('Open &Changes File...', main_window); file_menu.addAction(main_window.open_changes_action)
    file_menu.addSeparator()
    main_window.save_action = QAction('&Save Changes', main_window); main_window.save_action.setShortcut('Ctrl+S'); file_menu.addAction(main_window.save_action)
    main_window.save_as_action = QAction('Save Changes &As...', main_window); file_menu.addAction(main_window.save_as_action)
    file_menu.addSeparator()
    main_window.reload_action = QAction('Reload Original', main_window); file_menu.addAction(main_window.reload_action)
    main_window.revert_action = QAction('&Revert Changes File to Original...', main_window); file_menu.addAction(main_window.revert_action)
    file_menu.addSeparator()
    main_window.exit_action = QAction('E&xit', main_window); main_window.exit_action.triggered.connect(main_window.close); file_menu.addAction(main_window.exit_action)

    edit_menu = menubar.addMenu('&Edit')
    main_window.undo_typing_action = QAction(QIcon.fromTheme("edit-undo"), '&Undo Typing', main_window); main_window.undo_typing_action.setShortcut('Ctrl+Z')
    # Підключення до edited_text_edit.undo буде в connect_signals або тут, якщо edited_text_edit вже створений
    edit_menu.addAction(main_window.undo_typing_action)
    
    main_window.redo_typing_action = QAction(QIcon.fromTheme("edit-redo"), '&Redo Typing', main_window); main_window.redo_typing_action.setShortcut('Ctrl+Y') 
    edit_menu.addAction(main_window.redo_typing_action)
    edit_menu.addSeparator()
    
    main_window.undo_paste_action = QAction(QIcon.fromTheme("edit-undo"), 'Undo &Paste Block', main_window)
    main_window.undo_paste_action.setShortcut('Ctrl+Shift+Z') 
    main_window.undo_paste_action.setEnabled(False) 
    edit_menu.addAction(main_window.undo_paste_action)
    edit_menu.addSeparator()
    
    main_window.paste_block_action = QAction('&Paste Block Text', main_window)
    main_window.paste_block_action.setShortcut('Ctrl+Shift+V')
    edit_menu.addAction(main_window.paste_block_action)
    edit_menu.addSeparator()

    # --- НОВА ДІЯ ДЛЯ ПЕРЕСКАНУВАННЯ ВСІХ ТЕГІВ ---
    main_window.rescan_all_tags_action = QAction('Rescan All Tags for Issues', main_window)
    # Можна додати іконку QIcon.fromTheme("system-search") або "document-revert"
    edit_menu.addAction(main_window.rescan_all_tags_action)
    # --- КІНЕЦЬ НОВОЇ ДІЇ ---
        
    toolbar = QToolBar("Main Toolbar")
    main_window.addToolBar(toolbar)
    toolbar.addAction(main_window.open_action)
    toolbar.addAction(main_window.save_action)
    toolbar.addSeparator()
    toolbar.addAction(main_window.undo_typing_action) 
    toolbar.addAction(main_window.redo_typing_action) 
    toolbar.addAction(main_window.undo_paste_action)
    toolbar.addSeparator()
    toolbar.addAction(main_window.rescan_all_tags_action) # Додаємо на панель інструментів

    log_debug("setup_main_window_ui: UI setup complete.")