import sys
import os
import json
import copy
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QPlainTextEdit, QVBoxLayout, QSpinBox, QWidget
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QKeyEvent, QTextCursor, QKeySequence, QFont

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


from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler
from handlers.app_action_handler import AppActionHandler
from handlers.search_handler import SearchHandler


from utils.utils import log_debug, DEFAULT_CHAR_WIDTH_FALLBACK
from constants import (
    EDITOR_PLAYER_TAG, ORIGINAL_PLAYER_TAG,
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
    GENERAL_APP_FONT_FAMILY, MONOSPACE_EDITOR_FONT_FAMILY, DEFAULT_APP_FONT_SIZE
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        log_debug("++++++++++++++++++++ MainWindow: Initializing ++++++++++++++++++++")

        self.EDITOR_PLAYER_TAG = EDITOR_PLAYER_TAG
        self.ORIGINAL_PLAYER_TAG = ORIGINAL_PLAYER_TAG
        self.GAME_DIALOG_MAX_WIDTH_PIXELS = DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS
        self.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = DEFAULT_LINE_WIDTH_WARNING_THRESHOLD
        self.font_map = {}

        self.current_font_size = DEFAULT_APP_FONT_SIZE
        self.general_font_family = GENERAL_APP_FONT_FAMILY
        self.editor_font_family = MONOSPACE_EDITOR_FONT_FAMILY


        self.is_programmatically_changing_text = False
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


        self.newline_display_symbol = "↵"
        self.newline_css = "color: #A020F0; font-weight: bold;"
        self.tag_css = "color: #808080; font-style: italic;"
        self.show_multiple_spaces_as_dots = True
        self.space_dot_color_hex = "#BBBBBB"
        self.preview_wrap_lines = True
        self.editors_wrap_lines = False
        self.bracket_tag_color_hex = "#FF8C00"
        self.search_history_to_save = []


        self.default_tag_mappings = {
            "[red]": "{Color:Red}",
            "[blue]": "{Color:Blue}",
            "[green]": "{Color:Green}",
            "[/c]": "{Color:White}",
            "[unk10]": "{Symbol:10}",
            self.EDITOR_PLAYER_TAG: self.ORIGINAL_PLAYER_TAG
        }
        self.critical_problem_lines_per_block = {}
        self.warning_problem_lines_per_block = {}
        self.width_exceeded_lines_per_block = {}

        self.can_undo_paste = False
        self.before_paste_edited_data_snapshot = {}
        self.before_paste_block_idx_affected = -1
        self.before_paste_critical_problems_snapshot = {}
        self.before_paste_warning_problems_snapshot = {}
        self.before_paste_width_exceeded_snapshot = {}

        self.search_match_block_indices = set()
        self.current_search_results = []
        self.current_search_index = -1


        self.main_splitter = None; self.right_splitter = None; self.bottom_right_splitter = None
        self.open_action = None; self.open_changes_action = None; self.save_action = None;
        self.save_as_action = None; self.reload_action = None; self.revert_action = None;
        self.reload_tag_mappings_action = None
        self.exit_action = None; self.paste_block_action = None;
        self.undo_typing_action = None; self.redo_typing_action = None;
        self.undo_paste_action = None
        self.rescan_all_tags_action = None
        self.find_action = None
        self.main_vertical_layout = None
        self.font_size_spinbox = None

        log_debug("MainWindow: Initializing Core Components...")
        self.helper = MainWindowHelper(self)
        self.actions = MainWindowActions(self)
        self.data_processor = DataStateProcessor(self)
        self.ui_updater = UIUpdater(self, self.data_processor)
        self.settings_manager = SettingsManager(self)


        log_debug("MainWindow: Initializing Handlers...")
        self.list_selection_handler = ListSelectionHandler(self, self.data_processor, self.ui_updater)
        self.editor_operation_handler = TextOperationHandler(self, self.data_processor, self.ui_updater)
        self.app_action_handler = AppActionHandler(self, self.data_processor, self.ui_updater)
        self.search_handler = SearchHandler(self, self.data_processor, self.ui_updater)


        log_debug("MainWindow: Setting up UI...")
        setup_main_window_ui(self)

        self.search_panel_widget = SearchPanelWidget(self)
        self.main_vertical_layout.insertWidget(0, self.search_panel_widget)
        self.search_panel_widget.setVisible(False)


        log_debug("MainWindow: Connecting Signals...")
        self.connect_signals()

        self.event_filter = MainWindowEventFilter(self)
        self.installEventFilter(self.event_filter)


        log_debug("MainWindow: Loading Editor Settings via SettingsManager...")
        self.settings_manager.load_settings()
        log_debug(f"MainWindow: After SettingsManager.load_settings(), self.current_font_size = {self.current_font_size}, general_family = {self.general_font_family}, editor_family = {self.editor_font_family}")
        if self.font_size_spinbox:
            self.font_size_spinbox.setValue(self.current_font_size)


        log_debug(f"MainWindow: After load_settings, self.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = {self.LINE_WIDTH_WARNING_THRESHOLD_PIXELS}")
        log_debug(f"MainWindow: After load_settings, self.initial_load_path = {self.initial_load_path}")
        log_debug(f"MainWindow: After load_settings, self.initial_edited_load_path = {self.initial_edited_load_path}")


        for editor_widget in [self.preview_text_edit, self.original_text_edit, self.edited_text_edit]:
            if editor_widget:
                editor_widget.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = self.LINE_WIDTH_WARNING_THRESHOLD_PIXELS
                log_debug(f"MainWindow: Set {editor_widget.objectName()}.LINE_WIDTH_WARNING_THRESHOLD_PIXELS to {editor_widget.LINE_WIDTH_WARNING_THRESHOLD_PIXELS}")
                editor_widget.font_map = self.font_map
                editor_widget.GAME_DIALOG_MAX_WIDTH_PIXELS = self.GAME_DIALOG_MAX_WIDTH_PIXELS
                if hasattr(editor_widget, 'updateLineNumberAreaWidth'):
                    editor_widget.updateLineNumberAreaWidth(0)

        self.helper.restore_state_after_settings_load()
        self.helper.rebuild_unsaved_block_indices()

        log_debug("++++++++++++++++++++ MainWindow: Initialization Complete ++++++++++++++++++++")


    def _rebuild_unsaved_block_indices(self):
        self.helper.rebuild_unsaved_block_indices()

    def keyPressEvent(self, event: QKeyEvent):
        log_debug("MainWindow keyPressEvent: This should not be called if eventFilter is working.")
        super().keyPressEvent(event)


    def execute_find_next_shortcut(self):
        self.helper.execute_find_next_shortcut()

    def execute_find_previous_shortcut(self):
        self.helper.execute_find_previous_shortcut()


    def connect_signals(self):
        log_debug("--> MainWindow: connect_signals() started")
        if hasattr(self, 'block_list_widget'):
            self.block_list_widget.currentItemChanged.connect(self.list_selection_handler.block_selected)
            self.block_list_widget.itemDoubleClicked.connect(self.list_selection_handler.rename_block)
        if hasattr(self, 'preview_text_edit') and hasattr(self.preview_text_edit, 'lineClicked'):
            self.preview_text_edit.lineClicked.connect(self.list_selection_handler.string_selected_from_preview)
        if hasattr(self, 'edited_text_edit'):
            self.edited_text_edit.textChanged.connect(self.editor_operation_handler.text_edited)
            self.edited_text_edit.cursorPositionChanged.connect(self.ui_updater.update_status_bar)
            self.edited_text_edit.selectionChanged.connect(self.ui_updater.update_status_bar_selection)
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
        if hasattr(self, 'font_size_spinbox') and self.font_size_spinbox:
            self.font_size_spinbox.valueChanged.connect(self.change_font_size_action)

        log_debug("--> MainWindow: connect_signals() finished")

    def change_font_size_action(self, new_size: int):
        log_debug(f"MainWindow: change_font_size_action called with size {new_size}")
        if self.current_font_size != new_size:
            self.current_font_size = new_size
            log_debug(f"MainWindow: self.current_font_size is now {self.current_font_size}")
            self.apply_font_size()

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
            self.block_list_widget, self.search_panel_widget, self.statusBar
        ]

        labels_in_status_bar = [self.original_path_label, self.edited_path_label, self.pos_len_label, self.selection_len_label]
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
            if not self.unsaved_changes :
                log_debug("Close accepted (no unsaved changes). Saving editor settings via SettingsManager.")
                self.settings_manager.save_settings()
            else:
                 log_debug("Close accepted (unsaved changes were handled). Settings should have been saved by AppActionHandler or by user choice during handle_close_event.")
            super().closeEvent(event)
        else:
            log_debug("Close ignored by user or handler.")
        log_debug("<-- MainWindow: closeEvent finished.")

if __name__ == '__main__':
    log_debug("================= Application Start =================")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    log_debug("Starting Qt event loop...")
    exit_code = app.exec_()
    log_debug(f"Qt event loop finished with exit code: {exit_code}")
    log_debug("================= Application End =================")
    sys.exit(exit_code)