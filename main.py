import sys
import os
import json
import re
import importlib
import inspect
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
from components.LineNumberedTextEdit import LineNumberedTextEdit
from components.CustomListWidget import CustomListWidget
from components.search_panel import SearchPanelWidget
from ui.themes import DARK_THEME_STYLESHEET, LIGHT_THEME_STYLESHEET

from handlers.app_action_handler import AppActionHandler
from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler
from handlers.search_handler import SearchHandler
from handlers.string_settings_handler import StringSettingsHandler

from core.settings_manager import SettingsManager
from core.data_state_processor import DataStateProcessor

from plugins.base_game_rules import BaseGameRules

from utils.logging_utils import log_debug, log_info, log_warning, log_error
from utils.constants import (
    EDITOR_PLAYER_TAG, ORIGINAL_PLAYER_TAG,
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
    GENERAL_APP_FONT_FAMILY, MONOSPACE_EDITOR_FONT_FAMILY, DEFAULT_APP_FONT_SIZE,
    LT_PREVIEW_SELECTED_LINE_COLOR, DT_PREVIEW_SELECTED_LINE_COLOR
)
from utils.utils import ALL_TAGS_PATTERN

from ui.settings_dialog import SettingsDialog
from components.CustomListItemDelegate import CustomListItemDelegate

from main_window_helper import MainWindowHelper
from main_window_actions import MainWindowActions
from main_window_ui_handler import MainWindowUIHandler
from main_window_plugin_handler import MainWindowPluginHandler
from main_window_event_handler import MainWindowEventHandler
from main_window_block_handler import MainWindowBlockHandler


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        log_debug("++++++++++++++++++++ MainWindow: Initializing ++++++++++++++++++++")

        self.EDITOR_PLAYER_TAG = EDITOR_PLAYER_TAG
        self.ORIGINAL_PLAYER_TAG = ORIGINAL_PLAYER_TAG
        self.game_dialog_max_width_pixels = DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS
        self.line_width_warning_threshold_pixels = DEFAULT_LINE_WIDTH_WARNING_THRESHOLD
        self.font_map = {}
        self.all_font_maps = {}

        self.current_font_size = DEFAULT_APP_FONT_SIZE
        self.general_font_family = GENERAL_APP_FONT_FAMILY
        self.editor_font_family = MONOSPACE_EDITOR_FONT_FAMILY
        self.active_game_plugin = "zelda_mc"
        self.display_name = ""
        self.theme = "auto"
        self.restore_unsaved_on_startup = False

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

        self.json_path = None; self.edited_json_path = None
        self.data = []; self.edited_data = {}; self.edited_file_data = []
        self.block_names = {}; self.current_block_idx = -1; self.current_string_idx = -1
        self.unsaved_changes = False
        self.unsaved_block_indices = set()
        self.problems_per_subline = {}
        
        self.last_selected_block_index = -1
        self.last_selected_string_index = -1
        self.last_cursor_position_in_edited = 0
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
        self.newline_css = "color: #A020F0; font-weight: bold;"
        self.tag_css = "color: #808080; font-style: italic;"
        self.show_multiple_spaces_as_dots = True
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

        self.can_undo_paste = False
        self.before_paste_edited_data_snapshot = {}
        self.before_paste_block_idx_affected = -1

        self.search_match_block_indices = set()
        self.current_search_results = []
        self.current_search_index = -1


        self.main_splitter = None; self.right_splitter = None; self.bottom_right_splitter = None
        self.open_action = None; self.open_changes_action = None; self.save_action = None;
        self.save_as_action = None; self.reload_action = None; self.revert_action = None;
        self.reload_tag_mappings_action = None; self.open_settings_action = None
        self.exit_action = None; self.paste_block_action = None;
        self.undo_typing_action = None; self.redo_typing_action = None;
        self.undo_paste_action = None
        self.rescan_all_tags_action = None
        self.find_action = None
        self.auto_fix_action = None 
        self.main_vertical_layout = None
        self.auto_fix_button = None 
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


        log_debug("MainWindow: Initializing Core Components...")
        self.settings_manager = SettingsManager(self)
        self.settings_manager.load_settings()

        self.helper = MainWindowHelper(self)
        self.actions = MainWindowActions(self)
        self.data_processor = DataStateProcessor(self)
        self.ui_updater = UIUpdater(self, self.data_processor)
        self.string_settings_updater = StringSettingsUpdater(self, self.data_processor)

        self.ui_handler = MainWindowUIHandler(self)
        self.plugin_handler = MainWindowPluginHandler(self)
        self.event_handler = MainWindowEventHandler(self)
        self.block_handler = MainWindowBlockHandler(self)

        log_debug("MainWindow: Loading game plugin...")
        self.load_game_plugin() 
        if self.current_game_rules:
            self.default_tag_mappings = self.current_game_rules.get_default_tag_mappings()

        log_debug("MainWindow: Initializing Handlers (Pre-UI setup)...")
        self.list_selection_handler = ListSelectionHandler(self, self.data_processor, self.ui_updater)
        self.editor_operation_handler = TextOperationHandler(self, self.data_processor, self.ui_updater)
        self.app_action_handler = AppActionHandler(self, self.data_processor, self.ui_updater, self.current_game_rules) 
        self.search_handler = SearchHandler(self, self.data_processor, self.ui_updater)
        self.string_settings_handler = StringSettingsHandler(self, self.data_processor, self.ui_updater)


        log_debug("MainWindow: Setting up UI...")
        setup_main_window_ui(self)

        log_debug("MainWindow: Initializing Handlers and dynamic UI from plugin (Post-UI setup)...")
        self.setup_plugin_ui()

        self.search_panel_widget = SearchPanelWidget(self)
        self.main_vertical_layout.insertWidget(0, self.search_panel_widget)
        self.search_panel_widget.setVisible(False)


        log_debug("MainWindow: Connecting Signals...")
        self.connect_signals()

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
        self.apply_font_size()
        self.helper.apply_text_wrap_settings()
        self.string_settings_updater.update_font_combobox()
        self.string_settings_updater.update_string_settings_panel()

        self.helper.rebuild_unsaved_block_indices()

        QTimer.singleShot(100, self.force_focus)

        log_debug("++++++++++++++++++++ MainWindow: Initialization Complete ++++++++++++++++++++")
    
    def force_focus(self):
        self.ui_handler.force_focus()

    def setup_plugin_ui(self):
        self.plugin_handler.setup_plugin_ui()

    def load_game_plugin(self):
        self.plugin_handler.load_game_plugin()


    def get_block_color_markers(self, block_idx: int) -> set:
        return self.block_handler.get_block_color_markers(block_idx)

    def toggle_block_color_marker(self, block_idx: int, color_name: str):
        self.block_handler.toggle_block_color_marker(block_idx, color_name) 

    def _rebuild_unsaved_block_indices(self):
        self.block_handler.rebuild_unsaved_block_indices()

    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)


    def execute_find_next_shortcut(self):
        self.helper.execute_find_next_shortcut()

    def execute_find_previous_shortcut(self):
        self.helper.execute_find_previous_shortcut()
    
    def trigger_check_tags_action(self):
        self.plugin_handler.trigger_check_tags_action()

    def handle_edited_cursor_position_changed(self):
        self.event_handler.handle_edited_cursor_position_changed()


    def handle_edited_selection_changed(self):
        self.event_handler.handle_edited_selection_changed()


    def connect_signals(self):
        self.event_handler.connect_signals()

    def apply_font_size(self):
        self.ui_handler.apply_font_size()


    def handle_panel_find_next(self, query, case_sensitive, search_in_original, ignore_tags):
        self.helper.handle_panel_find_next(query, case_sensitive, search_in_original, ignore_tags)

    def handle_panel_find_previous(self, query, case_sensitive, search_in_original, ignore_tags):
        self.helper.handle_panel_find_previous(query, case_sensitive, search_in_original, ignore_tags)

    def toggle_search_panel(self):
        self.helper.toggle_search_panel()

    def hide_search_panel(self):
        self.helper.hide_search_panel()


    def load_all_data_for_path(self, original_file_path, manually_set_edited_path=None, is_initial_load_from_settings=False):
        self.helper.load_all_data_for_path(original_file_path, manually_set_edited_path, is_initial_load_from_settings)


    def _apply_text_wrap_settings(self):
        self.ui_handler.apply_text_wrap_settings()


    def _reconfigure_all_highlighters(self):
        self.ui_handler.reconfigure_all_highlighters()


    def closeEvent(self, event):
        self.event_handler.closeEvent(event)


if __name__ == '__main__':
    log_debug("================= Application Start =================")
    app = QApplication(sys.argv)
    
    temp_settings = {}
    try:
        with open("settings.json", 'r') as f:
            temp_settings = json.load(f)
    except FileNotFoundError:
        log_debug("settings.json not found, using default theme.")
    except Exception as e:
        log_debug(f"Error reading settings.json for theme: {e}")
        
    theme_to_apply = temp_settings.get("theme", "auto")
    MainWindowUIHandler.apply_theme(app, theme_to_apply)

    window = MainWindow()
    window.show()
    log_debug("Starting Qt event loop...")
    exit_code = app.exec_()
    log_debug(f"Qt event loop finished with exit code: {exit_code}")
    log_debug("================= Application End =================")
    sys.exit(exit_code)