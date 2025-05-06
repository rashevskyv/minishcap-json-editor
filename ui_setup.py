from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QAction, QStatusBar, QMenu
)
from PyQt5.QtCore import Qt
from LineNumberedTextEdit import LineNumberedTextEdit
from CustomListWidget import CustomListWidget
from utils import log_debug
from richtext_delegate import RichTextDelegate

def setup_main_window_ui(main_window):
    # ... (початок без змін) ...
    log_debug("setup_main_window_ui: Starting UI setup.")
    central_widget = QWidget(); main_window.setCentralWidget(central_widget)
    main_layout = QHBoxLayout(central_widget)
    left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
    left_layout.addWidget(QLabel("Blocks (double-click to rename):"))
    main_window.block_list_widget = CustomListWidget(); left_layout.addWidget(main_window.block_list_widget)
    main_window.right_splitter = QSplitter(Qt.Vertical)
    top_right_panel = QWidget(); top_right_layout = QVBoxLayout(top_right_panel)
    top_right_layout.addWidget(QLabel("Strings in block:"))
    main_window.preview_text_edit = LineNumberedTextEdit(main_window)
    main_window.preview_text_edit.setReadOnly(True)
    # Додаємо preview_text_edit у потрібний layout (наприклад, у верхню частину splitter)
    # Наприклад:
    # main_layout.addWidget(main_window.preview_text_edit)
    main_window.string_list_widget = CustomListWidget(); top_right_layout.addWidget(main_window.string_list_widget)
    main_window.right_splitter.addWidget(top_right_panel)
    main_window.bottom_right_splitter = QSplitter(Qt.Horizontal)
    bottom_left_panel = QWidget(); bottom_left_layout = QVBoxLayout(bottom_left_panel)
    bottom_left_layout.addWidget(QLabel("Original (Read-Only):"))
    main_window.original_text_edit = LineNumberedTextEdit(); main_window.original_text_edit.setReadOnly(True)
    bottom_left_layout.addWidget(main_window.original_text_edit); main_window.bottom_right_splitter.addWidget(bottom_left_panel)
    bottom_right_panel = QWidget(); bottom_right_layout = QVBoxLayout(bottom_right_panel)
    bottom_right_layout.addWidget(QLabel("Editable Text:"))
    main_window.edited_text_edit = LineNumberedTextEdit()
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

    # --- Menu ---
    menubar = main_window.menuBar()
    file_menu = menubar.addMenu('&File')

    main_window.open_action = QAction('&Open Original File...', main_window)
    file_menu.addAction(main_window.open_action)
    # --- NEW ACTION ---
    main_window.open_changes_action = QAction('Open &Changes File...', main_window)
    file_menu.addAction(main_window.open_changes_action)
    # --- END NEW ACTION ---
    file_menu.addSeparator()
    main_window.save_action = QAction('&Save Changes', main_window)
    main_window.save_action.setShortcut('Ctrl+S')
    file_menu.addAction(main_window.save_action)
    main_window.save_as_action = QAction('Save Changes &As...', main_window)
    file_menu.addAction(main_window.save_as_action)
    file_menu.addSeparator()
    main_window.reload_action = QAction('Reload Original', main_window)
    file_menu.addAction(main_window.reload_action)
    main_window.revert_action = QAction('&Revert Changes File to Original...', main_window)
    file_menu.addAction(main_window.revert_action)
    file_menu.addSeparator()
    main_window.exit_action = QAction('E&xit', main_window)
    main_window.exit_action.triggered.connect(main_window.close)
    file_menu.addAction(main_window.exit_action)

    edit_menu = menubar.addMenu('&Edit')
    main_window.paste_block_action = QAction('&Paste Block Text', main_window)
    main_window.paste_block_action.setShortcut('Ctrl+Shift+V')
    edit_menu.addAction(main_window.paste_block_action)
    main_window.string_list_widget.setItemDelegate(RichTextDelegate(main_window.string_list_widget))
    
    log_debug("setup_main_window_ui: UI setup complete.")