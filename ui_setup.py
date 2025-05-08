from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QAction, QStatusBar, QMenu, QPlainTextEdit, QToolBar, 
    QStyle 
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon 
from LineNumberedTextEdit import LineNumberedTextEdit
from CustomListWidget import CustomListWidget
from utils import log_debug

def setup_main_window_ui(main_window):
    log_debug("setup_main_window_ui: Starting UI setup.")
    central_widget = QWidget(); main_window.setCentralWidget(central_widget)
    main_layout = QHBoxLayout(central_widget)
    
    left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
    left_layout.addWidget(QLabel("Blocks (double-click to rename):"))
    main_window.block_list_widget = CustomListWidget(main_window)
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

    # --- Створення дій (Actions) з іконками ---
    menubar = main_window.menuBar()
    file_menu = menubar.addMenu('&File')
    style = main_window.style() # Отримуємо стиль для стандартних іконок

    # Використовуємо стандартні PyQt іконки, де це можливо
    open_icon = style.standardIcon(QStyle.SP_DialogOpenButton) 
    main_window.open_action = QAction(open_icon, '&Open Original File...', main_window)
    file_menu.addAction(main_window.open_action)
    
    # Для "Open Changes" немає прямого аналогу, залишаємо без іконки поки що
    main_window.open_changes_action = QAction('Open &Changes File...', main_window) 
    file_menu.addAction(main_window.open_changes_action)
    file_menu.addSeparator()
    
    save_icon = style.standardIcon(QStyle.SP_DialogSaveButton)
    main_window.save_action = QAction(save_icon, '&Save Changes', main_window)
    main_window.save_action.setShortcut('Ctrl+S'); file_menu.addAction(main_window.save_action)
    
    # Для "Save As" немає прямого аналогу в стандартних SP_, використовуємо fromTheme (може не спрацювати)
    main_window.save_as_action = QAction(QIcon.fromTheme("document-save-as"), 'Save Changes &As...', main_window)
    file_menu.addAction(main_window.save_as_action)
    file_menu.addSeparator()

    reload_icon = style.standardIcon(QStyle.SP_BrowserReload)
    main_window.reload_action = QAction(reload_icon, 'Reload Original', main_window) 
    file_menu.addAction(main_window.reload_action)
    
    # Для "Revert" немає аналогу, використовуємо fromTheme
    main_window.revert_action = QAction(QIcon.fromTheme("document-revert"), '&Revert Changes File to Original...', main_window) 
    file_menu.addAction(main_window.revert_action)
    file_menu.addSeparator()
    
    # Для "Reload Tag Mappings" використовуємо fromTheme
    main_window.reload_tag_mappings_action = QAction(QIcon.fromTheme("preferences-system"), 'Reload &Tag Mappings from Settings', main_window) 
    file_menu.addAction(main_window.reload_tag_mappings_action)
    file_menu.addSeparator()

    exit_icon = style.standardIcon(QStyle.SP_DialogCloseButton) # Або SP_DialogCancelButton
    main_window.exit_action = QAction(exit_icon, 'E&xit', main_window)
    main_window.exit_action.triggered.connect(main_window.close); file_menu.addAction(main_window.exit_action)

    edit_menu = menubar.addMenu('&Edit')
    undo_icon = style.standardIcon(QStyle.SP_ArrowBack) # Використовуємо стандартну стрілку назад для Undo
    main_window.undo_typing_action = QAction(undo_icon, '&Undo Typing', main_window)
    main_window.undo_typing_action.setShortcut('Ctrl+Z')
    edit_menu.addAction(main_window.undo_typing_action)
    
    redo_icon = style.standardIcon(QStyle.SP_ArrowForward) # Стандартну стрілку вперед для Redo
    main_window.redo_typing_action = QAction(redo_icon, '&Redo Typing', main_window)
    main_window.redo_typing_action.setShortcut('Ctrl+Y') 
    edit_menu.addAction(main_window.redo_typing_action)
    edit_menu.addSeparator()

    # Для "Undo Paste" використовуємо ту ж іконку Undo
    main_window.undo_paste_action = QAction(undo_icon, 'Undo &Paste Block', main_window) 
    main_window.undo_paste_action.setShortcut('Ctrl+Shift+Z') 
    main_window.undo_paste_action.setEnabled(False) 
    edit_menu.addAction(main_window.undo_paste_action)
    edit_menu.addSeparator()
    
    # Для "Paste" немає стандартної іконки SP_, використовуємо fromTheme
    main_window.paste_block_action = QAction(QIcon.fromTheme("edit-paste"), '&Paste Block Text', main_window) 
    main_window.paste_block_action.setShortcut('Ctrl+Shift+V')
    edit_menu.addAction(main_window.paste_block_action)
    edit_menu.addSeparator()

    # Для "Rescan" немає стандартної іконки SP_, використовуємо fromTheme
    main_window.rescan_all_tags_action = QAction(QIcon.fromTheme("system-search"), 'Rescan All Tags for Issues', main_window) 
    edit_menu.addAction(main_window.rescan_all_tags_action)
        
    # --- Створення панелі інструментів (Toolbar) ---
    toolbar = QToolBar("Main Toolbar")
    main_window.addToolBar(toolbar)
    # Додаємо тільки ті дії, для яких ми впевнені в іконках
    # toolbar.addAction(main_window.open_action) # Забираємо Open
    toolbar.addAction(main_window.save_action) # Додаємо Save
    toolbar.addSeparator()
    toolbar.addAction(main_window.undo_typing_action) # Додаємо Undo
    toolbar.addAction(main_window.redo_typing_action) # Додаємо Redo
    # toolbar.addAction(main_window.undo_paste_action) # Забираємо Undo Paste (та ж іконка)
    # toolbar.addAction(main_window.paste_block_action) # Забираємо Paste (іконка може бути відсутня)
    # toolbar.addSeparator()
    # toolbar.addAction(main_window.rescan_all_tags_action) # Забираємо Rescan (іконка може бути відсутня)
    # toolbar.addAction(main_window.reload_tag_mappings_action) # Забираємо Reload Mappings (іконка може бути відсутня)

    # Встановлюємо стиль "Тільки іконки"
    main_window.setToolButtonStyle(Qt.ToolButtonIconOnly) 
    
    log_debug("setup_main_window_ui: UI setup complete.")