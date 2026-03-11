# --- START OF FILE main.py ---
import sys
import os
import json
import re
import importlib
import inspect
import argparse
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QLabel, QComboBox, QSpinBox, QPushButton
from PyQt5.QtCore import Qt, QSize, QEvent, QTimer, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QKeyEvent
from typing import Optional, Dict, Tuple, Set

from ui.ui_setup import setup_main_window_ui
from ui.ui_event_filters import MainWindowEventFilter, TextEditEventFilter
from ui.ui_updater import UIUpdater
from ui.updaters.string_settings_updater import StringSettingsUpdater
from components.editor.line_numbered_text_edit import LineNumberedTextEdit
from components.custom_list_widget import CustomListWidget
from components.search_panel import SearchPanelWidget
from ui.themes import DARK_THEME_STYLESHEET, LIGHT_THEME_STYLESHEET

from handlers.app_action_handler import AppActionHandler
from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler
from handlers.search_handler import SearchHandler
from handlers.string_settings_handler import StringSettingsHandler

from handlers.translation_handler import TranslationHandler
from handlers.text_analysis_handler import TextAnalysisHandler
from handlers.ai_chat_handler import AIChatHandler

from core.settings_manager import SettingsManager
from core.data_state_processor import DataStateProcessor
from core.translation.config import build_default_translation_config
from core.spellchecker_manager import SpellcheckerManager
from core.project_manager import ProjectManager

from plugins.base_game_rules import BaseGameRules

from utils.logging_utils import log_info, log_warning, log_error
from utils.constants import (
    EDITOR_PLAYER_TAG, ORIGINAL_PLAYER_TAG,
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
    GENERAL_APP_FONT_FAMILY, MONOSPACE_EDITOR_FONT_FAMILY, DEFAULT_APP_FONT_SIZE,
    LT_PREVIEW_SELECTED_LINE_COLOR, DT_PREVIEW_SELECTED_LINE_COLOR
)
from utils.utils import ALL_TAGS_PATTERN

from ui.settings_dialog import SettingsDialog
from components.custom_list_item_delegate import CustomListItemDelegate

from ui.main_window.main_window_helper import MainWindowHelper
from ui.main_window.main_window_actions import MainWindowActions
from ui.main_window.main_window_ui_handler import MainWindowUIHandler
from ui.main_window.main_window_plugin_handler import MainWindowPluginHandler
from ui.main_window.main_window_event_handler import MainWindowEventHandler
from ui.main_window.main_window_block_handler import MainWindowBlockHandler


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        log_info("Initializing main window...")

        self.EDITOR_PLAYER_TAG = EDITOR_PLAYER_TAG
        self.ORIGINAL_PLAYER_TAG = ORIGINAL_PLAYER_TAG
        
        self.general_font_family = GENERAL_APP_FONT_FAMILY
        self.editor_font_family = MONOSPACE_EDITOR_FONT_FAMILY
        self.display_name = ""

        self.is_adjusting_cursor = False
        self.is_adjusting_selection = False
        self.is_programmatically_changing_text = False
        self.is_restart_in_progress = False
        self.is_closing = False
        self.is_loading_data = False
        self.is_saving_data = False
        self.is_reverting_data = False
        self.is_reloading_data = False
        self.is_pasting_block = False
        self.is_undoing_paste = False
        self.is_auto_fixing = False
        self.is_checking_tags = False
        self.is_renaming_block = False
        self.is_rebuilding_indices = False
        self.is_updating_ui = False
        self.is_updating_status_bar = False
        self.is_updating_title = False
        self.is_updating_block_list = False
        self.is_updating_preview = False
        self.is_updating_edited = False
        self.is_updating_highlighters = False
        self.is_updating_font = False
        self.is_updating_theme = False
        self.is_updating_settings = False
        self.is_updating_plugin = False
        self.is_updating_tag_mappings = False
        self.is_updating_tag_colors = False
        self.is_updating_tag_patterns = False
        self.is_updating_tag_checkers = False
        self.is_updating_text_fixers = False
        self.is_updating_problem_analyzers = False
        self.is_updating_import_rules = False
        self.is_updating_game_rules = False
        self.is_updating_search_panel = False
        self.is_updating_search_results = False
        self.is_updating_search_history = False
        self.is_updating_search_settings = False
        self.is_updating_search_state = False
        self.is_updating_search_ui = False
        self.is_updating_search_panel_ui = False
        self.is_updating_search_panel_state = False
        self.is_updating_search_panel_settings = False
        self.is_updating_search_panel_history = False
        self.is_updating_search_panel_results = False
        self.is_updating_search_panel_ui_state = False

        # Project management
        self.project_manager = None  # Will be initialized when project is created/opened

        # Legacy data structures (still used internally)
        self.json_path = None; self.edited_json_path = None
        self.data = []; self.edited_data = {}; self.edited_file_data = []
        self.block_names = {}; self.current_block_idx = -1; self.current_string_idx = -1
        self.unsaved_changes = False
        self.unsaved_block_indices = set()
        self.problems_per_subline = {}
        
        self.last_selected_block_index = -1
        self.last_selected_string_index = -1
        self.last_cursor_position_in_edited = 0
        self.previous_cursor_pos = 0
        self.last_edited_text_edit_scroll_value_v = 0
        self.last_edited_text_edit_scroll_value_h = 0
        self.last_preview_text_edit_scroll_value_v = 0
        self.last_original_text_edit_scroll_value_v = 0
        self.last_original_text_edit_scroll_value_h = 0

        self.initial_load_path = None
        self.initial_edited_load_path = None

        self.window_was_maximized_on_close = False
        self.window_normal_geometry_on_close: QRect = None

        self.newline_display_symbol = "↵"
        self.newline_color_rgba = "#A020F0"
        self.newline_bold = True
        self.newline_italic = False
        self.newline_underline = False
        
        self.tag_color_rgba = "#FF8C00"
        self.tag_bold = True
        self.tag_italic = False
        self.tag_underline = False

        self.newline_css = "color: #A020F0; font-weight: bold;"
        self.tag_css = "color: rgba(128, 128, 128, 128); font-style: italic;"
        self.space_dot_color_hex = "#BBBBBB"
        self.preview_wrap_lines = True
        self.editors_wrap_lines = False
        self.bracket_tag_color_hex = "#FF8C00"
        self.search_history_to_save = []

        self.default_tag_mappings = {}
        
        self.block_color_markers = {}
        self.string_metadata = {}
        self.default_font_file = ""
        self.autofix_enabled = {}
        self.detection_enabled = {}
        self.translation_config = build_default_translation_config()

        self.can_undo_paste = False
        self.before_paste_edited_data_snapshot = {}
        self.before_paste_block_idx_affected = -1

        self.search_match_block_indices = set()
        self.current_search_results = []
        self.current_search_index = -1


        self.main_splitter = None; self.right_splitter = None; self.bottom_right_splitter = None
        self.open_action = None; self.open_changes_action = None; self.save_action = None;
        self.save_as_action = None; self.reload_action = None; self.revert_action = None;
        self.reload_tag_mappings_action = None; self.open_settings_action = None;
        self.exit_action = None; self.paste_block_action = None;
        self.undo_typing_action = None; self.redo_typing_action = None;
        self.undo_paste_action = None
        self.rescan_all_tags_action = None
        self.find_action = None
        self.auto_fix_action = None
        self.open_ai_chat_action = None
        self.main_vertical_layout = None
        self.auto_fix_button = None 
        self.ai_translate_button = None
        self.ai_variation_button = None
        self.font_combobox: QComboBox = None
        self.width_spinbox: QSpinBox = None
        self.apply_width_button: QPushButton = None
        
        self.status_label_part1: QLabel = None
        self.status_label_part2: QLabel = None
        self.status_label_part3: QLabel = None
        self.plugin_status_label: QLabel = None

        self.current_game_rules: Optional[BaseGameRules] = None 
        self.tag_checker_handler = None 
        self.plugin_actions = {}

        self.font_map = {}
        self.all_font_maps = {}

        self.settings_manager = SettingsManager(self)
        self.settings_manager.load_settings()

        self.helper = MainWindowHelper(self)
        self.actions = MainWindowActions(self)
        self.data_processor = DataStateProcessor(self)
        self.ui_updater = UIUpdater(self, self.data_processor)
        self.string_settings_updater = StringSettingsUpdater(self, self.data_processor)
        self.spellchecker_manager = SpellcheckerManager(self)

        self.ui_handler = MainWindowUIHandler(self)
        self.plugin_handler = MainWindowPluginHandler(self)
        self.event_handler = MainWindowEventHandler(self)
        self.block_handler = MainWindowBlockHandler(self)

        self.plugin_handler.load_game_plugin() 
        if self.current_game_rules:
            self.default_tag_mappings = self.current_game_rules.get_default_tag_mappings()

        self.list_selection_handler = ListSelectionHandler(self, self.data_processor, self.ui_updater)
        self.editor_operation_handler = TextOperationHandler(self, self.data_processor, self.ui_updater)
        self.app_action_handler = AppActionHandler(self, self.data_processor, self.ui_updater, self.current_game_rules) 
        self.search_handler = SearchHandler(self, self.data_processor, self.ui_updater)
        self.string_settings_handler = StringSettingsHandler(self, self.data_processor, self.ui_updater)
        self.translation_handler = TranslationHandler(self, self.data_processor, self.ui_updater)
        self.text_analysis_handler = TextAnalysisHandler(self, self.data_processor, self.ui_updater)
        self.ai_chat_handler = AIChatHandler(self, self.data_processor, self.ui_updater)


        setup_main_window_ui(self)

        if hasattr(self, 'open_glossary_button'):
            self.open_glossary_button.clicked.connect(self.translation_handler.show_glossary_dialog)

        if hasattr(self, 'translation_handler'):
            self.translation_handler.initialize_glossary_highlighting()

            # Load glossary words into spellchecker after glossary is initialized
            if hasattr(self, 'spellchecker_manager') and self.spellchecker_manager:
                self.spellchecker_manager.reload_glossary_words()

        if hasattr(self, 'text_analysis_handler'):
            self.text_analysis_handler.ensure_menu_action()

        log_info("Initializing dynamic UI from plugin...")
        self.plugin_handler.setup_plugin_ui()

        self.search_panel_widget = SearchPanelWidget(self)
        self.main_vertical_layout.insertWidget(0, self.search_panel_widget)
        self.search_panel_widget.setVisible(False)


        self.event_handler.connect_signals()

        self.event_filter = MainWindowEventFilter(self)
        self.installEventFilter(self.event_filter)
        
        self.text_edit_filter = TextEditEventFilter(self)
        self.preview_text_edit.installEventFilter(self.text_edit_filter)
        self.original_text_edit.installEventFilter(self.text_edit_filter)
        self.edited_text_edit.installEventFilter(self.text_edit_filter)


        self.ui_updater.update_plugin_status_label()

        for editor_widget in [self.preview_text_edit, self.original_text_edit, self.edited_text_edit]:
            if editor_widget:
                editor_widget.line_width_warning_threshold_pixels = self.line_width_warning_threshold_pixels
                editor_widget.font_map = self.font_map
                editor_widget.game_dialog_max_width_pixels = self.game_dialog_max_width_pixels
                
                if hasattr(editor_widget, 'updateLineNumberAreaWidth'):
                    editor_widget.updateLineNumberAreaWidth(0)

        self.helper.restore_state_after_settings_load()
        self.ui_handler.apply_font_size()
        self.helper.apply_text_wrap_settings()
        self.string_settings_updater.update_font_combobox()
        self.string_settings_updater.update_string_settings_panel()

        self.helper.rebuild_unsaved_block_indices()

        # Initialize spellchecker state
        log_info(f"Checking spellchecker initialization: has spellchecker_enabled={hasattr(self, 'spellchecker_enabled')}, has spellchecker_manager={hasattr(self, 'spellchecker_manager')}")
        if hasattr(self, 'spellchecker_manager'):
            spellchecker_enabled = getattr(self, 'spellchecker_enabled', False)
            spellchecker_language = getattr(self, 'spellchecker_language', 'uk')
            log_info(f"Initializing spellchecker: enabled={spellchecker_enabled}, language={spellchecker_language}")
            log_info(f"Spellchecker manager hunspell object: {self.spellchecker_manager.hunspell is not None}")
            if self.spellchecker_manager.hunspell:
                log_info(f"Spellchecker dictionary language: {self.spellchecker_manager.language}")
            self.spellchecker_manager.set_enabled(spellchecker_enabled)
            log_info(f"Spellchecker initialization complete. Manager enabled state: {self.spellchecker_manager.enabled}")
        else:
            log_info("Spellchecker manager not found, skipping initialization")

        # Update recent projects menu
        if hasattr(self, 'project_action_handler') and hasattr(self.project_action_handler, '_update_recent_projects_menu'):
            self.project_action_handler._update_recent_projects_menu()

        QTimer.singleShot(100, self.ui_handler.force_focus)

        log_info("Main window initialization complete.")
    
    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)

    # --- Settings Properties ---
    @property
    def current_font_size(self): return self.settings_manager.get('font_size', DEFAULT_APP_FONT_SIZE)
    @current_font_size.setter
    def current_font_size(self, val): self.settings_manager.set('font_size', val)

    @property
    def active_game_plugin(self): return self.settings_manager.get('active_game_plugin', "zelda_mc")
    @active_game_plugin.setter
    def active_game_plugin(self, val): self.settings_manager.set('active_game_plugin', val)

    @property
    def show_multiple_spaces_as_dots(self): return self.settings_manager.get('show_multiple_spaces_as_dots', True)
    @show_multiple_spaces_as_dots.setter
    def show_multiple_spaces_as_dots(self, val): self.settings_manager.set('show_multiple_spaces_as_dots', val)

    @property
    def theme(self): return self.settings_manager.get('theme', "auto")
    @theme.setter
    def theme(self, val): self.settings_manager.set('theme', val)

    @property
    def restore_unsaved_on_startup(self): return self.settings_manager.get('restore_unsaved_on_startup', False)
    @restore_unsaved_on_startup.setter
    def restore_unsaved_on_startup(self, val): self.settings_manager.set('restore_unsaved_on_startup', val)

    @property
    def game_dialog_max_width_pixels(self): return self.settings_manager.get('game_dialog_max_width_pixels', DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS)
    @game_dialog_max_width_pixels.setter
    def game_dialog_max_width_pixels(self, val): self.settings_manager.set('game_dialog_max_width_pixels', val)

    @property
    def line_width_warning_threshold_pixels(self): return self.settings_manager.get('line_width_warning_threshold_pixels', DEFAULT_LINE_WIDTH_WARNING_THRESHOLD)
    @line_width_warning_threshold_pixels.setter
    def line_width_warning_threshold_pixels(self, val): self.settings_manager.set('line_width_warning_threshold_pixels', val)


    def closeEvent(self, event):
        self.event_handler.closeEvent(event)

    def build_glossary_with_ai(self, block_idx=None):
        log_info("Build Glossary with AI action triggered.")
        from handlers.translation.glossary_builder_handler import GlossaryBuilderHandler

        target_block_idx = block_idx if block_idx is not None else self.current_block_idx

        if target_block_idx == -1:
            QMessageBox.information(self, "Build Glossary", "Please select a block first.")
            return
        
        handler = GlossaryBuilderHandler(self)
        handler.build_glossary_for_block(target_block_idx)


if __name__ == '__main__':
    log_info("================= Application Start =================")
    app = QApplication(sys.argv)
    
    temp_settings = {}
    try:
        with open("settings.json", 'r') as f:
            temp_settings = json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        log_warning(f"Error reading settings.json for theme: {e}")
        
    theme_to_apply = temp_settings.get("theme", "auto")
    MainWindowUIHandler.apply_theme(app, theme_to_apply)

    window = MainWindow()
    window.show()
    log_info("Starting Qt event loop...")
    exit_code = app.exec_()
    log_info(f"Qt event loop finished with exit code: {exit_code}")
    log_info("================= Application End =================")
    sys.exit(exit_code)