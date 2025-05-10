from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QAction, QStatusBar, QMenu, QPlainTextEdit, QToolBar,
    QStyle, QSpinBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QFont
from components.LineNumberedTextEdit import LineNumberedTextEdit
from components.CustomListWidget import CustomListWidget
from utils.utils import log_debug

def setup_main_window_ui(main_window):
    log_debug("setup_main_window_ui: Starting UI setup.")
    central_widget = QWidget(); main_window.setCentralWidget(central_widget)
    main_window.main_vertical_layout = QVBoxLayout(central_widget)

    main_window.main_splitter = QSplitter(Qt.Horizontal)

    left_panel = QWidget()
    left_layout = QVBoxLayout(left_panel)
    left_layout.addWidget(QLabel("Blocks (double-click to rename):"))
    main_window.block_list_widget = CustomListWidget(main_window)
    left_layout.addWidget(main_window.block_list_widget)

    main_window.right_splitter = QSplitter(Qt.Vertical)

    top_right_panel = QWidget()
    top_right_layout = QVBoxLayout(top_right_panel)
    top_right_layout.addWidget(QLabel("Strings in block (click line to select):"))
    main_window.preview_text_edit = LineNumberedTextEdit(main_window)
    main_window.preview_text_edit.setObjectName("preview_text_edit")
    main_window.preview_text_edit.setReadOnly(True)
    main_window.preview_text_edit.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    top_right_layout.addWidget(main_window.preview_text_edit)
    main_window.right_splitter.addWidget(top_right_panel)

    main_window.bottom_right_splitter = QSplitter(Qt.Horizontal)

    bottom_left_panel = QWidget()
    bottom_left_layout = QVBoxLayout(bottom_left_panel)
    bottom_left_layout.addWidget(QLabel("Original (Read-Only):"))
    main_window.original_text_edit = LineNumberedTextEdit(main_window)
    main_window.original_text_edit.setObjectName("original_text_edit")
    main_window.original_text_edit.setReadOnly(True)
    main_window.original_text_edit.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    bottom_left_layout.addWidget(main_window.original_text_edit)
    main_window.bottom_right_splitter.addWidget(bottom_left_panel)

    bottom_right_panel = QWidget()
    bottom_right_layout = QVBoxLayout(bottom_right_panel)
    bottom_right_layout.addWidget(QLabel("Editable Text:"))
    main_window.edited_text_edit = LineNumberedTextEdit(main_window)
    main_window.edited_text_edit.setObjectName("edited_text_edit")
    bottom_right_layout.addWidget(main_window.edited_text_edit)
    main_window.bottom_right_splitter.addWidget(bottom_right_panel)

    main_window.right_splitter.addWidget(main_window.bottom_right_splitter)
    main_window.right_splitter.setSizes([150, 450])
    main_window.bottom_right_splitter.setSizes([400, 400])

    main_window.main_splitter.addWidget(left_panel)
    main_window.main_splitter.addWidget(main_window.right_splitter)
    main_window.main_splitter.setSizes([200, 800])

    main_window.main_vertical_layout.addWidget(main_window.main_splitter)


    main_window.statusBar = QStatusBar()
    main_window.setStatusBar(main_window.statusBar)
    main_window.original_path_label = QLabel("Original: [not specified]")
    main_window.edited_path_label = QLabel("Changes: [not specified]")
    main_window.original_path_label.setToolTip("Path to the original text file")
    main_window.edited_path_label.setToolTip("Path to the file where changes are saved")
    main_window.pos_len_label = QLabel("0 (0/0)")
    main_window.selection_len_label = QLabel("Sel: 0")

    main_window.statusBar.addWidget(main_window.original_path_label)
    main_window.statusBar.addWidget(QLabel("|"))
    main_window.statusBar.addWidget(main_window.edited_path_label)
    main_window.statusBar.addPermanentWidget(main_window.pos_len_label)
    main_window.statusBar.addPermanentWidget(main_window.selection_len_label)


    menubar = main_window.menuBar()
    file_menu = menubar.addMenu('&File')
    style = main_window.style()


    open_icon = style.standardIcon(QStyle.SP_DialogOpenButton)
    main_window.open_action = QAction(open_icon, '&Open Original File...', main_window)
    file_menu.addAction(main_window.open_action)

    main_window.open_changes_action = QAction('Open &Changes File...', main_window)
    file_menu.addAction(main_window.open_changes_action)
    file_menu.addSeparator()

    save_icon = style.standardIcon(QStyle.SP_DialogSaveButton)
    main_window.save_action = QAction(save_icon, '&Save Changes', main_window)
    main_window.save_action.setShortcut('Ctrl+S')
    file_menu.addAction(main_window.save_action)

    main_window.save_as_action = QAction(QIcon.fromTheme("document-save-as"), 'Save Changes &As...', main_window)
    file_menu.addAction(main_window.save_as_action)
    file_menu.addSeparator()

    reload_icon = style.standardIcon(QStyle.SP_BrowserReload)
    main_window.reload_action = QAction(reload_icon, 'Reload Original', main_window)
    file_menu.addAction(main_window.reload_action)

    main_window.revert_action = QAction(QIcon.fromTheme("document-revert"), '&Revert Changes File to Original...', main_window)
    file_menu.addAction(main_window.revert_action)
    file_menu.addSeparator()

    main_window.reload_tag_mappings_action = QAction(QIcon.fromTheme("preferences-system"), 'Reload &Tag Mappings from Settings', main_window)
    file_menu.addAction(main_window.reload_tag_mappings_action)
    file_menu.addSeparator()

    exit_icon = style.standardIcon(QStyle.SP_DialogCloseButton)
    main_window.exit_action = QAction(exit_icon, 'E&xit', main_window)
    main_window.exit_action.triggered.connect(main_window.close)
    file_menu.addAction(main_window.exit_action)

    edit_menu = menubar.addMenu('&Edit')
    undo_icon = style.standardIcon(QStyle.SP_ArrowBack)
    main_window.undo_typing_action = QAction(undo_icon, '&Undo Typing', main_window)
    main_window.undo_typing_action.setShortcut('Ctrl+Z')
    edit_menu.addAction(main_window.undo_typing_action)

    redo_icon = style.standardIcon(QStyle.SP_ArrowForward)
    main_window.redo_typing_action = QAction(redo_icon, '&Redo Typing', main_window)
    main_window.redo_typing_action.setShortcut('Ctrl+Y')
    edit_menu.addAction(main_window.redo_typing_action)
    edit_menu.addSeparator()

    main_window.undo_paste_action = QAction(undo_icon, 'Undo &Paste Block', main_window)
    main_window.undo_paste_action.setShortcut('Ctrl+Shift+Z')
    main_window.undo_paste_action.setEnabled(False)
    edit_menu.addAction(main_window.undo_paste_action)
    edit_menu.addSeparator()

    main_window.paste_block_action = QAction(QIcon.fromTheme("edit-paste"), '&Paste Block Text', main_window)
    main_window.paste_block_action.setShortcut('Ctrl+Shift+V')
    edit_menu.addAction(main_window.paste_block_action)
    edit_menu.addSeparator()

    find_icon = style.standardIcon(QStyle.SP_FileDialogContentsView)
    main_window.find_action = QAction(find_icon, '&Find...', main_window)
    main_window.find_action.setShortcut('Ctrl+F')
    edit_menu.addAction(main_window.find_action)
    edit_menu.addSeparator()

    main_window.rescan_all_tags_action = QAction(QIcon.fromTheme("system-search"), 'Rescan All Tags for Issues', main_window)
    edit_menu.addAction(main_window.rescan_all_tags_action)


    toolbar = QToolBar("Main Toolbar")
    main_window.addToolBar(toolbar)

    toolbar.addAction(main_window.open_action)
    toolbar.addAction(main_window.save_action)
    toolbar.addSeparator()
    toolbar.addAction(main_window.undo_typing_action)
    toolbar.addAction(main_window.redo_typing_action)
    toolbar.addSeparator()
    toolbar.addAction(main_window.find_action)
    toolbar.addSeparator()

    font_size_label = QLabel("Font Size:")
    toolbar.addWidget(font_size_label)
    main_window.font_size_spinbox = QSpinBox(main_window)
    main_window.font_size_spinbox.setMinimum(6)
    main_window.font_size_spinbox.setMaximum(24)
    default_font_size_val = QFont().pointSize()
    if default_font_size_val <= 0 : default_font_size_val = 10
    main_window.font_size_spinbox.setValue(default_font_size_val)
    toolbar.addWidget(main_window.font_size_spinbox)


    main_window.setToolButtonStyle(Qt.ToolButtonIconOnly)

    log_debug("setup_main_window_ui: UI setup complete.")