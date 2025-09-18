from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QAction, QStatusBar, QMenu, QPlainTextEdit, QToolBar,
    QStyle, QSpinBox, QPushButton, QSpacerItem, QSizePolicy, QComboBox
)
from PyQt5.QtCore import Qt, QSize
import os
from PyQt5.QtGui import QIcon, QFont, QFontMetrics, QKeySequence 
from components.LineNumberedTextEdit import LineNumberedTextEdit
from components.CustomListWidget import CustomListWidget
from utils.logging_utils import log_debug

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
    left_layout.addWidget(main_window.block_list_widget)
    left_layout.addSpacing(8)
    main_window.open_glossary_button = QPushButton('Glossary…')
    main_window.open_glossary_button.setToolTip('Open glossary')
    left_layout.addWidget(main_window.open_glossary_button)
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

    original_header_layout = QHBoxLayout()
    original_label = QLabel("Original (Read-Only):")
    original_header_layout.addWidget(original_label)
    original_header_layout.addStretch(1)
    bottom_left_layout.addLayout(original_header_layout)

    main_window.original_editor_top_spacer = QWidget()
    main_window.original_editor_top_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    main_window.original_editor_top_spacer.setFixedHeight(0)
    bottom_left_layout.addWidget(main_window.original_editor_top_spacer)

    main_window.original_text_edit = LineNumberedTextEdit(main_window)
    main_window.original_text_edit.setObjectName("original_text_edit")
    main_window.original_text_edit.setReadOnly(True)
    main_window.original_text_edit.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    bottom_left_layout.addWidget(main_window.original_text_edit)
    main_window.bottom_right_splitter.addWidget(bottom_left_panel)

    bottom_right_panel = QWidget()
    bottom_right_layout = QVBoxLayout(bottom_right_panel)
    
    editable_text_header_layout = QHBoxLayout()
    editable_text_label = QLabel("Editable Text:")
    editable_text_header_layout.addWidget(editable_text_label)
    
    spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
    editable_text_header_layout.addItem(spacer)
    
    main_window.navigate_up_button = QPushButton()
    main_window.navigate_up_button.setIcon(main_window.style().standardIcon(QStyle.SP_ArrowUp))
    main_window.navigate_up_button.setToolTip("Navigate to previous problem string (Ctrl+Up)")
    editable_text_header_layout.addWidget(main_window.navigate_up_button)

    main_window.navigate_down_button = QPushButton()
    main_window.navigate_down_button.setIcon(main_window.style().standardIcon(QStyle.SP_ArrowDown))
    main_window.navigate_down_button.setToolTip("Navigate to next problem string (Ctrl+Down)")
    editable_text_header_layout.addWidget(main_window.navigate_down_button)

    main_window.ai_translate_button = QPushButton("AI Translate")
    main_window.ai_translate_button = QPushButton('AI Translate')
    editable_text_header_layout.addWidget(main_window.ai_translate_button)

    main_window.ai_variation_button = QPushButton("AI Variation")
    main_window.ai_variation_button = QPushButton('AI Variation')
    editable_text_header_layout.addWidget(main_window.ai_variation_button)

    main_window.auto_fix_button = QPushButton("Auto-fix")
    main_window.auto_fix_button = QPushButton('Auto-fix')
    editable_text_header_layout.addWidget(main_window.auto_fix_button)
    
    bottom_right_layout.addLayout(editable_text_header_layout)

    string_settings_panel = QWidget()
    string_settings_layout = QHBoxLayout(string_settings_panel)
    string_settings_layout.setContentsMargins(0, 5, 0, 5)

    string_settings_layout.addWidget(QLabel("Font:"))
    main_window.font_combobox = QComboBox()
    string_settings_layout.addWidget(main_window.font_combobox)

    string_settings_layout.addWidget(QLabel("Width:"))
    main_window.width_spinbox = QSpinBox()
    main_window.width_spinbox.setRange(0, 10000)
    main_window.width_spinbox.setToolTip("Set custom width for this string (0 = use plugin default)")
    main_window.width_spinbox.setContextMenuPolicy(Qt.CustomContextMenu)
    
    def show_width_context_menu(pos):
        menu = QMenu()
        reset_action = menu.addAction("Reset to Plugin Default")
        action = menu.exec_(main_window.width_spinbox.mapToGlobal(pos))
        if action == reset_action:
            main_window.width_spinbox.setValue(main_window.line_width_warning_threshold_pixels)

    main_window.width_spinbox.customContextMenuRequested.connect(show_width_context_menu)
    string_settings_layout.addWidget(main_window.width_spinbox)
    
    main_window.apply_width_button = QPushButton("Apply")
    main_window.apply_width_button.setEnabled(False)
    string_settings_layout.addWidget(main_window.apply_width_button)
    
    string_settings_layout.addStretch(1)
    bottom_right_layout.addWidget(string_settings_panel)

    if hasattr(main_window, 'original_editor_top_spacer') and main_window.original_editor_top_spacer:
        header_heights = [
            main_window.ai_translate_button.sizeHint().height(),
            main_window.ai_variation_button.sizeHint().height(),
            main_window.navigate_up_button.sizeHint().height(),
            main_window.navigate_down_button.sizeHint().height(),
            main_window.auto_fix_button.sizeHint().height(),
        ]
        placeholder_height = max(header_heights) + string_settings_panel.sizeHint().height()
        main_window.original_editor_top_spacer.setFixedHeight(placeholder_height)

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
    main_window.plugin_status_label = QLabel("Plugin: [None]")
    main_window.original_path_label.setToolTip("Path to the original text file")
    main_window.edited_path_label.setToolTip("Path to the file where changes are saved")
    main_window.plugin_status_label.setToolTip("Currently active game plugin")

    main_window.status_label_part1 = QLabel("Pos: 000")
    main_window.status_label_part2 = QLabel("Line: 000/000")
    main_window.status_label_part3 = QLabel("Width: 0000px")
    
    font_for_metrics = QFont() 
    if main_window.font() and main_window.font().family(): 
        font_for_metrics = main_window.font()

    font_metrics = QFontMetrics(font_for_metrics) 
    main_window.status_label_part1.setMinimumWidth(font_metrics.horizontalAdvance("Sel: 000/000") + 15) 
    main_window.status_label_part2.setMinimumWidth(font_metrics.horizontalAdvance("Line: 000/000") + 15) 
    main_window.status_label_part3.setMinimumWidth(font_metrics.horizontalAdvance("Width: 0000px") + 10)
    
    main_window.statusBar.addWidget(main_window.original_path_label)
    main_window.statusBar.addWidget(QLabel("|"))
    main_window.statusBar.addWidget(main_window.edited_path_label)
    main_window.statusBar.addPermanentWidget(main_window.plugin_status_label)
    main_window.statusBar.addPermanentWidget(QLabel("|"))
    main_window.statusBar.addPermanentWidget(main_window.status_label_part1)
    main_window.statusBar.addPermanentWidget(QLabel("|")) 
    main_window.statusBar.addPermanentWidget(main_window.status_label_part2)
    main_window.statusBar.addPermanentWidget(QLabel("|")) 
    main_window.statusBar.addPermanentWidget(main_window.status_label_part3)


    menubar = main_window.menuBar()
    file_menu = menubar.addMenu('&File')
    style = main_window.style()

    open_icon = style.standardIcon(QStyle.SP_DialogOpenButton)
    save_icon = style.standardIcon(QStyle.SP_DialogSaveButton)
    reload_icon = style.standardIcon(QStyle.SP_BrowserReload)
    exit_icon = style.standardIcon(QStyle.SP_DialogCloseButton)
    settings_icon = style.standardIcon(QStyle.SP_ComputerIcon)

    main_window.open_action = QAction(open_icon, '&Open Original File...', main_window)
    file_menu.addAction(main_window.open_action)

    main_window.open_changes_action = QAction('Open &Changes File...', main_window)
    file_menu.addAction(main_window.open_changes_action)
    file_menu.addSeparator()

    main_window.save_action = QAction(save_icon, '&Save Changes', main_window)
    main_window.save_action.setShortcut('Ctrl+S')
    file_menu.addAction(main_window.save_action)

    main_window.save_as_action = QAction(QIcon.fromTheme("document-save-as"), 'Save Changes &As...', main_window)
    file_menu.addAction(main_window.save_as_action)
    file_menu.addSeparator()

    main_window.reload_action = QAction(reload_icon, 'Reload Original', main_window)
    file_menu.addAction(main_window.reload_action)

    main_window.revert_action = QAction(QIcon.fromTheme("document-revert"), '&Revert Changes File to Original...', main_window)
    file_menu.addAction(main_window.revert_action)
    file_menu.addSeparator()

    main_window.reload_tag_mappings_action = QAction(QIcon.fromTheme("preferences-system"), 'Reload &Tag Mappings from Settings', main_window)
    file_menu.addAction(main_window.reload_tag_mappings_action)
    file_menu.addSeparator()

    main_window.open_settings_action = QAction(settings_icon, '&Settings...', main_window)
    main_window.open_settings_action.setShortcut('Ctrl+P')
    file_menu.addAction(main_window.open_settings_action)
    file_menu.addSeparator()

    main_window.exit_action = QAction(exit_icon, 'E&xit', main_window)
    main_window.exit_action.triggered.connect(main_window.close)
    file_menu.addAction(main_window.exit_action)

    edit_menu = menubar.addMenu('&Edit')
    edit_menu.setObjectName('&Edit')

    tools_menu = menubar.addMenu('&Tools')
    tools_menu.setObjectName('&Tools')
    main_window.tools_menu = tools_menu

    # Helper to load semicircular undo/redo icons reliably across platforms
    def _icon_path(file_name: str) -> str:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(base_dir)
        return os.path.join(project_root, 'resources', 'icons', file_name)

    undo_local = _icon_path('undo.svg')
    redo_local = _icon_path('redo.svg')

    # Prefer bundled Oxygen-like SVGs for consistent curved look; fallback to theme or arrows
    undo_icon = QIcon(undo_local) if os.path.exists(undo_local) else QIcon.fromTheme("edit-undo", style.standardIcon(QStyle.SP_ArrowBack))
    redo_icon = QIcon(redo_local) if os.path.exists(redo_local) else QIcon.fromTheme("edit-redo", style.standardIcon(QStyle.SP_ArrowForward))
    find_icon = style.standardIcon(QStyle.SP_FileDialogContentsView)

    main_window.undo_typing_action = QAction(undo_icon, '&Undo Typing', main_window)
    main_window.undo_typing_action.setShortcut('Ctrl+Z')
    edit_menu.addAction(main_window.undo_typing_action)

    main_window.redo_typing_action = QAction(redo_icon, '&Redo Typing', main_window)
    main_window.redo_typing_action.setShortcuts([QKeySequence('Ctrl+Y'), QKeySequence('Ctrl+Shift+Z')])
    edit_menu.addAction(main_window.redo_typing_action)
    edit_menu.addSeparator()

    main_window.undo_paste_action = QAction(undo_icon, 'Undo &Paste Block', main_window)
    main_window.undo_paste_action.setEnabled(False)
    edit_menu.addAction(main_window.undo_paste_action)
    edit_menu.addSeparator()

    main_window.paste_block_action = QAction(QIcon.fromTheme("edit-paste"), '&Paste Block Text', main_window)
    main_window.paste_block_action.setShortcut('Ctrl+Shift+V')
    edit_menu.addAction(main_window.paste_block_action)
    edit_menu.addSeparator()

    main_window.find_action = QAction(find_icon, '&Find...', main_window)
    main_window.find_action.setShortcut('Ctrl+F')
    edit_menu.addAction(main_window.find_action)
    edit_menu.addSeparator()
    
    main_window.auto_fix_action = QAction(QIcon.fromTheme("document-edit"), "Auto-&fix Current String", main_window)
    main_window.auto_fix_action.setShortcut(QKeySequence("Ctrl+Shift+A")) 
    main_window.auto_fix_action.setToolTip("Automatically fix issues in the current string (Ctrl+Shift+A)")
    edit_menu.addAction(main_window.auto_fix_action)
    edit_menu.addSeparator()

    main_window.rescan_all_tags_action = QAction(QIcon.fromTheme("system-search"), 'Rescan All Issues', main_window)
    edit_menu.addAction(main_window.rescan_all_tags_action)


    main_window.main_toolbar = QToolBar("Main Toolbar")
    main_window.addToolBar(main_window.main_toolbar)
    # Slightly larger icon size for better readability
    main_window.main_toolbar.setIconSize(QSize(24, 24))

    main_window.main_toolbar.addAction(main_window.open_action)
    main_window.main_toolbar.addAction(main_window.save_action)
    main_window.main_toolbar.addSeparator()
    main_window.main_toolbar.addAction(main_window.undo_typing_action)
    main_window.main_toolbar.addAction(main_window.redo_typing_action)
    main_window.main_toolbar.addSeparator()
    main_window.main_toolbar.addAction(main_window.find_action)
    main_window.main_toolbar.addSeparator()
    main_window.main_toolbar.addAction(main_window.open_settings_action)

    main_window.setToolButtonStyle(Qt.ToolButtonIconOnly)

    log_debug("setup_main_window_ui: UI setup complete.")
