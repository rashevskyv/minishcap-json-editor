import sys
import os
import json
import copy
import re
import importlib 
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QPlainTextEdit, QVBoxLayout, QSpinBox, QWidget, QLabel, QAction, QMenu
from PyQt5.QtCore import Qt, QEvent, QRect, QTimer
from PyQt5.QtGui import QKeyEvent, QTextCursor, QKeySequence, QFont, QPalette, QColor
from typing import Optional, Dict, Set, Tuple


from components.LineNumberArea import LineNumberArea
from components.CustomListWidget import CustomListWidget
from ui.ui_setup import setup_main_window_ui
from core.data_state_processor import DataStateProcessor
from ui.ui_updater import UIUpdater
from core.settings_manager import SettingsManager
from components.search_panel import SearchPanelWidget
from ui.ui_event_filters import MainWindowEventFilter
from main_window_helper import MainWindowHelper
from main_window_actions import MainWindowActions
from ui.themes import DARK_THEME_STYLESHEET, LIGHT_THEME_STYLESHEET


from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler
from handlers.app_action_handler import AppActionHandler
from handlers.search_handler import SearchHandler


from utils.logging_utils import log_debug
from utils.utils import DEFAULT_CHAR_WIDTH_FALLBACK, ALL_TAGS_PATTERN
from utils.constants import (
    EDITOR_PLAYER_TAG, ORIGINAL_PLAYER_TAG,
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
    GENERAL_APP_FONT_FAMILY, MONOSPACE_EDITOR_FONT_FAMILY, DEFAULT_APP_FONT_SIZE,
    LT_PREVIEW_SELECTED_LINE_COLOR, DT_PREVIEW_SELECTED_LINE_COLOR
)
from plugins.base_game_rules import BaseGameRules


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        log_debug("++++++++++++++++++++ MainWindow: Initializing ++++++++++++++++++++")

        self.EDITOR_PLAYER_TAG = EDITOR_PLAYER_TAG
        self.ORIGINAL_PLAYER_TAG = ORIGINAL_PLAYER_TAG
        self.game_dialog_max_width_pixels = DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS
        self.line_width_warning_threshold_pixels = DEFAULT_LINE_WIDTH_WARNING_THRESHOLD
        self.font_map = {}

        self.current_font_size = DEFAULT_APP_FONT_SIZE
        self.general_font_family = GENERAL_APP_FONT_FAMILY
        self.editor_font_family = MONOSPACE_EDITOR_FONT_FAMILY
        self.active_game_plugin = "zelda_mc"
        self.display_name = ""
        self.theme = "auto"

        self.is_programmatically_changing_text = False
        self.is_adjusting_cursor = False
        self.is_adjusting_selection = False
        self.json_path = None; self.edited_json_path = None
        self.data = []; self.edited_data = {}; self.edited_file_data = []
        self.block_names = {}; self.current_block_idx = -1; self.current_string_idx = -1
        self.unsaved_changes = False
        self.unsaved_block_indices = set()
        
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
        
        self.problems_per_subline: Dict[Tuple[int, int, int], Set[str]] = {}
        self.block_color_markers = {}
        self.autofix_enabled = {}
        self.detection_enabled = {}

        self.can_undo_paste = False
        self.before_paste_edited_data_snapshot = {}
        self.before_paste_block_idx_affected = -1
        self.before_paste_problems_per_subline_snapshot: Dict[Tuple[int, int, int], Set[str]] = {}


        self.search_match_block_indices = set()
        self.current_search_results = []
        self.current_search_index = -1
        self.is_restart_in_progress = False


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

        log_debug("MainWindow: Loading game plugin...")
        self.load_game_plugin() 
        if self.current_game_rules:
            self.default_tag_mappings = self.current_game_rules.get_default_tag_mappings()

        log_debug("MainWindow: Initializing Handlers (Pre-UI setup)...")
        self.list_selection_handler = ListSelectionHandler(self, self.data_processor, self.ui_updater)
        self.editor_operation_handler = TextOperationHandler(self, self.data_processor, self.ui_updater)
        self.app_action_handler = AppActionHandler(self, self.data_processor, self.ui_updater, self.current_game_rules) 
        self.search_handler = SearchHandler(self, self.data_processor, self.ui_updater)


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

        self.helper.rebuild_unsaved_block_indices()

        QTimer.singleShot(100, self.force_focus)

        log_debug("++++++++++++++++++++ MainWindow: Initialization Complete ++++++++++++++++++++")
    
    def force_focus(self):
        log_debug("Forcing window focus.")
        self.activateWindow()
        self.raise_()

    def setup_plugin_ui(self):
        if not self.current_game_rules:
            return
            
        self.tag_checker_handler = self.current_game_rules.get_tag_checker_handler()
        if self.tag_checker_handler:
            log_debug(f"TagCheckerHandler of type {type(self.tag_checker_handler).__name__} was provided by the plugin.")

        plugin_actions_data = self.current_game_rules.get_plugin_actions()
        for action_data in plugin_actions_data:
            action_name = action_data.get('name')
            if not action_name: continue
            
            action = QAction(action_data.get('text', action_name), self)
            if 'tooltip' in action_data: action.setToolTip(action_data['tooltip'])
            if 'shortcut' in action_data: action.setShortcut(QKeySequence(action_data['shortcut']))
            if 'handler' in action_data: action.triggered.connect(action_data['handler'])
            
            self.plugin_actions[action_name] = action

            if action_data.get('menu'):
                menu_name = action_data.get('menu')
                target_menu = self.menuBar().findChild(QMenu, f"&{menu_name}")
                if not target_menu:
                    target_menu = self.menuBar().addMenu(f"&{menu_name}")
                target_menu.addAction(action)

            if action_data.get('toolbar'):
                if hasattr(self, 'main_toolbar'):
                    self.main_toolbar.addAction(action)

    def load_game_plugin(self):
        log_debug("--> MainWindow: load_game_plugin called.")
        
        plugin_name_to_load = self.active_game_plugin
        log_debug(f"    Attempting to load plugin: '{plugin_name_to_load}'")


        try:
            module_path = f"plugins.{plugin_name_to_load}.rules"
            log_debug(f"    Importing module: {module_path}")
            if module_path in sys.modules:
                del sys.modules[module_path]
                if f"plugins.{plugin_name_to_load}.config" in sys.modules: 
                    del sys.modules[f"plugins.{plugin_name_to_load}.config"]
                if f"plugins.{plugin_name_to_load}.tag_checker_handler" in sys.modules:
                    del sys.modules[f"plugins.{plugin_name_to_load}.tag_checker_handler"]

            game_rules_module = importlib.import_module(module_path)
            
            if hasattr(game_rules_module, 'GameRules') and issubclass(getattr(game_rules_module, 'GameRules'), BaseGameRules):
                GameRulesClass = getattr(game_rules_module, 'GameRules')
                self.current_game_rules = GameRulesClass(main_window_ref=self)
                log_debug(f"    Successfully loaded and instantiated game rules: {GameRulesClass.__name__} from {module_path}")
            else:
                log_debug(f"    ERROR: Class 'GameRules' not found or not a subclass of BaseGameRules in module {module_path}")
                self._load_fallback_rules()

        except ImportError as e:
            log_debug(f"    ERROR: Could not import game plugin module {module_path}: {e}")
            self._load_fallback_rules()
        except Exception as e:
            log_debug(f"    ERROR: Unexpected error loading game plugin {module_path}: {e}")
            self._load_fallback_rules()
        log_debug("<-- MainWindow: load_game_plugin finished.")


    def _load_fallback_rules(self):
        log_debug("    --> MainWindow: _load_fallback_rules called.")
        try:
            from plugins.base_game_rules import BaseGameRules 
            self.current_game_rules = BaseGameRules(main_window_ref=self)
            log_debug("        Loaded fallback BaseGameRules.")
        except Exception as e:
            log_debug(f"        CRITICAL ERROR: Could not load fallback game rules: {e}")
            self.current_game_rules = None 
        log_debug("    <-- MainWindow: _load_fallback_rules finished.")


    def get_block_color_markers(self, block_idx: int) -> set:
        return self.block_color_markers.get(str(block_idx), set())

    def toggle_block_color_marker(self, block_idx: int, color_name: str):
        block_key = str(block_idx)
        if block_key not in self.block_color_markers:
            self.block_color_markers[block_key] = set()

        if color_name in self.block_color_markers[block_key]:
            self.block_color_markers[block_key].remove(color_name)
            if not self.block_color_markers[block_key]: 
                del self.block_color_markers[block_key]
        else:
            self.block_color_markers[block_key].add(color_name)
        
        log_debug(f"Toggled marker '{color_name}' for block {block_idx}. Current markers: {self.block_color_markers.get(block_key)}")
        
        if hasattr(self, 'block_list_widget'):
            item = self.block_list_widget.item(block_idx)
            if item:
                self.block_list_widget.update(self.block_list_widget.indexFromItem(item)) 


    def _rebuild_unsaved_block_indices(self):
        self.helper.rebuild_unsaved_block_indices()

    def keyPressEvent(self, event: QKeyEvent):
        log_debug("MainWindow keyPressEvent: This should not be called if eventFilter is working.")
        super().keyPressEvent(event)


    def execute_find_next_shortcut(self):
        self.helper.execute_find_next_shortcut()

    def execute_find_previous_shortcut(self):
        self.helper.execute_find_previous_shortcut()
    
    def trigger_check_tags_action(self):
        if self.tag_checker_handler:
            self.tag_checker_handler.start_or_continue_check()

    def handle_edited_cursor_position_changed(self):
        if self.is_adjusting_cursor or self.is_programmatically_changing_text:
            return

        editor = self.edited_text_edit
        cursor = editor.textCursor()

        if not cursor.hasSelection():
            self.is_adjusting_cursor = True
            
            current_block = cursor.block()
            pos_in_block = cursor.positionInBlock()
            block_text = current_block.text()
            
            for match in ALL_TAGS_PATTERN.finditer(block_text):
                tag_start, tag_end = match.span()
                if tag_start < pos_in_block < tag_end:
                    new_cursor_pos_abs = current_block.position() + tag_end
                    cursor.setPosition(new_cursor_pos_abs)
                    editor.setTextCursor(cursor)
                    log_debug(f"Cursor was inside tag '{match.group(0)}' at rel_pos {pos_in_block}, moved to abs_pos {new_cursor_pos_abs} (rel_pos {tag_end})")
                    break 
            self.is_adjusting_cursor = False
        
        self.ui_updater.update_status_bar()


    def handle_edited_selection_changed(self):
        if self.is_adjusting_selection or self.is_programmatically_changing_text:
            self.ui_updater.update_status_bar_selection() 
            return

        editor = self.edited_text_edit
        cursor = editor.textCursor()

        if not cursor.hasSelection():
            self.ui_updater.update_status_bar_selection() 
            return

        self.is_adjusting_selection = True
        
        doc = editor.document()
        anchor_abs = cursor.anchor()
        position_abs = cursor.position()
        
        anchor_block = doc.findBlock(anchor_abs)
        position_block = doc.findBlock(position_abs)

        if anchor_block.blockNumber() != position_block.blockNumber():
            log_debug("Selection spans multiple blocks. No adjustment.")
            self.is_adjusting_selection = False
            self.ui_updater.update_status_bar_selection()
            return
            
        current_block = anchor_block
        block_text = current_block.text()
        
        original_anchor_rel = anchor_abs - current_block.position()
        original_position_rel = position_abs - current_block.position()
        
        current_sel_start_rel = min(original_anchor_rel, original_position_rel)
        current_sel_end_rel = max(original_anchor_rel, original_position_rel)

        new_sel_start_rel = current_sel_start_rel
        new_sel_end_rel = current_sel_end_rel
        
        adjusted = False

        for match in ALL_TAGS_PATTERN.finditer(block_text):
            tag_start, tag_end = match.span()
            
            if tag_start < current_sel_start_rel < tag_end:
                new_sel_start_rel = min(new_sel_start_rel, tag_start)
                adjusted = True
            
            if tag_start < current_sel_end_rel < tag_end:
                new_sel_end_rel = max(new_sel_end_rel, tag_end)
                adjusted = True
        
        if new_sel_start_rel > new_sel_end_rel :
            log_debug(f"Warning: sel_start ({new_sel_start_rel}) > sel_end ({new_sel_end_rel}) after adjustment attempt. Reverting to original selection for this event.")
            new_sel_start_rel = current_sel_start_rel
            new_sel_end_rel = current_sel_end_rel
            adjusted = False


        if adjusted and (new_sel_start_rel != current_sel_start_rel or new_sel_end_rel != current_sel_end_rel):
            log_debug(f"Original sel: {current_sel_start_rel}-{current_sel_end_rel}. Proposed new: {new_sel_start_rel}-{new_sel_end_rel}")
            
            new_cursor = QTextCursor(current_block)
            
            final_anchor_abs = current_block.position() + (new_sel_start_rel if original_anchor_rel == current_sel_start_rel else new_sel_end_rel)
            final_position_abs = current_block.position() + (new_sel_end_rel if original_anchor_rel == current_sel_start_rel else new_sel_start_rel)

            new_cursor.setPosition(final_anchor_abs)
            new_cursor.setPosition(final_position_abs, QTextCursor.KeepAnchor)
            
            editor.setTextCursor(new_cursor)
            log_debug("Selection adjusted to encompass full tags.")
        
        self.is_adjusting_selection = False
        self.ui_updater.update_status_bar_selection()


    def connect_signals(self):
        log_debug("--> MainWindow: connect_signals() started")
        if hasattr(self, 'open_settings_action'): self.open_settings_action.triggered.connect(self.actions.open_settings_dialog)
        if hasattr(self, 'block_list_widget'):
            self.block_list_widget.currentItemChanged.connect(self.list_selection_handler.block_selected)
            self.block_list_widget.itemDoubleClicked.connect(self.list_selection_handler.rename_block)
        if hasattr(self, 'preview_text_edit') and hasattr(self.preview_text_edit, 'lineClicked'):
            self.preview_text_edit.lineClicked.connect(self.list_selection_handler.string_selected_from_preview)
        if hasattr(self, 'edited_text_edit'):
            self.edited_text_edit.textChanged.connect(self.editor_operation_handler.text_edited)
            self.edited_text_edit.cursorPositionChanged.connect(self.handle_edited_cursor_position_changed)
            self.edited_text_edit.selectionChanged.connect(self.handle_edited_selection_changed)
            if hasattr(self, 'undo_typing_action'):
                self.edited_text_edit.undoAvailable.connect(self.undo_typing_action.setEnabled)
                self.undo_typing_action.triggered.connect(self.edited_text_edit.undo)
            if hasattr(self, 'redo_typing_action'):
                self.edited_text_edit.redoAvailable.connect(self.redo_typing_action.setEnabled)
                self.redo_typing_action.triggered.connect(self.edited_text_edit.redo)
            if hasattr(self.edited_text_edit, 'addTagMappingRequest'):
                self.edited_text_edit.addTagMappingRequest.connect(self.actions.handle_add_tag_mapping_request)
        if hasattr(self, 'paste_block_action'): self.paste_block_action.triggered.connect(self.editor_operation_handler.paste_block_text)
        if hasattr(self, 'open_action'): self.open_action.triggered.connect(self.app_action_handler.open_file_dialog_action)
        if hasattr(self, 'open_changes_action'): self.open_changes_action.triggered.connect(self.app_action_handler.open_changes_file_dialog_action)
        if hasattr(self, 'save_action'): self.save_action.triggered.connect(self.actions.trigger_save_action)
        if hasattr(self, 'reload_action'): self.reload_action.triggered.connect(self.app_action_handler.reload_original_data_action)
        if hasattr(self, 'save_as_action'): self.save_as_action.triggered.connect(self.app_action_handler.save_as_dialog_action)
        if hasattr(self, 'revert_action'): self.revert_action.triggered.connect(self.actions.trigger_revert_action)
        if hasattr(self, 'undo_paste_action'): self.undo_paste_action.triggered.connect(self.actions.trigger_undo_paste_action)
        if hasattr(self, 'rescan_all_tags_action'): self.rescan_all_tags_action.triggered.connect(self.app_action_handler.rescan_all_tags)
        if hasattr(self, 'reload_tag_mappings_action'):
            self.reload_tag_mappings_action.triggered.connect(self.actions.trigger_reload_tag_mappings)
        if hasattr(self, 'find_action'):
            self.find_action.triggered.connect(self.helper.toggle_search_panel)
        if hasattr(self, 'search_panel_widget'):
            self.search_panel_widget.close_requested.connect(self.helper.hide_search_panel)
            self.search_panel_widget.find_next_requested.connect(self.helper.handle_panel_find_next)
            self.search_panel_widget.find_previous_requested.connect(self.helper.handle_panel_find_previous)
        
        if hasattr(self, 'auto_fix_button') and self.auto_fix_button:
            self.auto_fix_button.clicked.connect(self.editor_operation_handler.auto_fix_current_string)
        if hasattr(self, 'auto_fix_action') and self.auto_fix_action: 
            self.auto_fix_action.triggered.connect(self.editor_operation_handler.auto_fix_current_string)


        log_debug("--> MainWindow: connect_signals() finished")

    def apply_font_size(self):
        log_debug(f"MainWindow: Applying font. General: Family='{self.general_font_family}', Editor: Family='{self.editor_font_family}', Size={self.current_font_size}")
        if self.current_font_size <= 0:
            log_debug("MainWindow: Invalid font size, skipping application.")
            return

        general_font = QFont(self.general_font_family, self.current_font_size)
        editor_font = QFont(self.editor_font_family, self.current_font_size)

        QApplication.setFont(general_font)

        editor_widgets = [self.preview_text_edit, self.original_text_edit, self.edited_text_edit]
        general_ui_widgets = [
            self.block_list_widget, self.search_panel_widget, self.statusBar, self.auto_fix_button
        ]

        labels_in_status_bar = [self.original_path_label, self.edited_path_label, 
                                self.status_label_part1, self.status_label_part2, self.status_label_part3]
        general_ui_widgets.extend(labels_in_status_bar)

        if self.search_panel_widget:
            general_ui_widgets.extend([
                self.search_panel_widget.search_query_edit,
                self.search_panel_widget.find_next_button,
                self.search_panel_widget.find_previous_button,
                self.search_panel_widget.case_sensitive_checkbox,
                self.search_panel_widget.search_in_original_checkbox,
                self.search_panel_widget.ignore_tags_newlines_checkbox,
                self.search_panel_widget.status_label,
                self.search_panel_widget.close_search_panel_button
            ])
        
        if self.main_splitter:
            for i in range(self.main_splitter.count()):
                widget = self.main_splitter.widget(i)
                if widget not in editor_widgets and widget not in general_ui_widgets:
                    general_ui_widgets.append(widget)
                    for child_widget in widget.findChildren(QWidget):
                         if child_widget not in editor_widgets and child_widget not in general_ui_widgets:
                             general_ui_widgets.append(child_widget)


        for widget in editor_widgets:
            if widget:
                try:
                    widget.setFont(editor_font)
                    if hasattr(widget, 'updateGeometry'): widget.updateGeometry()
                    if hasattr(widget, 'adjustSize'): widget.adjustSize()
                    if hasattr(widget, 'updateLineNumberAreaWidth'):
                        widget.updateLineNumberAreaWidth(0)
                    widget.viewport().update()
                except Exception as e:
                    log_debug(f"Error applying editor font to widget {widget.objectName() if hasattr(widget, 'objectName') else type(widget)}: {e}")

        for widget in general_ui_widgets:
            if widget and widget not in editor_widgets:
                try:
                    widget.setFont(general_font)
                    if hasattr(widget, 'updateGeometry'): widget.updateGeometry()
                    if hasattr(widget, 'adjustSize'): widget.adjustSize()
                    if isinstance(widget, CustomListWidget):
                        widget.viewport().update()
                except Exception as e:
                    log_debug(f"Error applying general font to widget {widget.objectName() if hasattr(widget, 'objectName') else type(widget)}: {e}")


        if self.block_list_widget and self.block_list_widget.itemDelegate():
            self.block_list_widget.itemDelegate().deleteLater()
            from components.CustomListItemDelegate import CustomListItemDelegate
            new_delegate = CustomListItemDelegate(self.block_list_widget)
            self.block_list_widget.setItemDelegate(new_delegate)
            self.block_list_widget.viewport().update()

        self.ui_updater.update_text_views()
        self.ui_updater.populate_blocks()
        self.ui_updater.populate_strings_for_block(self.current_block_idx)


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
        self.helper.apply_text_wrap_settings()


    def _reconfigure_all_highlighters(self):
        self.helper.reconfigure_all_highlighters()


    def closeEvent(self, event):
        log_debug("--> MainWindow: closeEvent received.")
        self.helper.prepare_to_close()
        self.app_action_handler.handle_close_event(event)

        if event.isAccepted():
            if not self.unsaved_changes and not self.is_restart_in_progress:
                log_debug("Close accepted (no unsaved changes, not a restart). Saving editor settings via SettingsManager.")
                self.settings_manager.save_settings()
            else:
                 log_debug("Close accepted. Settings save skipped due to unsaved changes (handled by dialog) or restart in progress.")
            super().closeEvent(event)
        else:
            log_debug("Close ignored by user or handler.")
        log_debug("<-- MainWindow: closeEvent finished.")

def apply_theme(app, theme_name: str):
    if theme_name == "dark":
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(46, 46, 46))
        palette.setColor(QPalette.WindowText, QColor(224, 224, 224))
        palette.setColor(QPalette.Base, QColor(37, 37, 37))
        palette.setColor(QPalette.AlternateBase, QColor(74, 74, 74))
        palette.setColor(QPalette.ToolTipBase, QColor(46, 46, 46))
        palette.setColor(QPalette.ToolTipText, QColor(224, 224, 224))
        palette.setColor(QPalette.Text, QColor(224, 224, 224))
        palette.setColor(QPalette.Button, QColor(74, 74, 74))
        palette.setColor(QPalette.ButtonText, QColor(224, 224, 224))
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(DT_PREVIEW_SELECTED_LINE_COLOR))
        palette.setColor(QPalette.HighlightedText, Qt.white)
        app.setPalette(palette)
        app.setStyleSheet(DARK_THEME_STYLESHEET)
        log_debug("Applied Dark Theme.")
    else: # 'auto' or 'light'
        palette = QPalette()
        palette.setColor(QPalette.Highlight, QColor(LT_PREVIEW_SELECTED_LINE_COLOR))
        palette.setColor(QPalette.HighlightedText, QColor(Qt.black))
        app.setPalette(palette)
        app.setStyleSheet(LIGHT_THEME_STYLESHEET)
        log_debug("Applied Light Theme.")


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
    apply_theme(app, theme_to_apply)

    window = MainWindow()
    window.show()
    log_debug("Starting Qt event loop...")
    exit_code = app.exec_()
    log_debug(f"Qt event loop finished with exit code: {exit_code}")
    log_debug("================= Application End =================")
    sys.exit(exit_code)