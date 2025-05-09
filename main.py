import sys
import os
import json
import copy
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QPlainTextEdit, QVBoxLayout
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QKeyEvent, QTextCursor # Додано QTextCursor

from LineNumberArea import LineNumberArea
from CustomListWidget import CustomListWidget
from ui_setup import setup_main_window_ui
from data_state_processor import DataStateProcessor
from ui_updater import UIUpdater
from settings_manager import SettingsManager
from search_panel import SearchPanelWidget

from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler
from handlers.app_action_handler import AppActionHandler
from handlers.search_handler import SearchHandler


from utils import log_debug, DEFAULT_CHAR_WIDTH_FALLBACK

EDITOR_PLAYER_TAG = "[ІМ'Я ГРАВЦЯ]"
ORIGINAL_PLAYER_TAG = "{Player}"
DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS = 240 
DEFAULT_LINE_WIDTH_WARNING_THRESHOLD_MAIN = 175


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        log_debug("++++++++++++++++++++ MainWindow: Initializing ++++++++++++++++++++")

        self.EDITOR_PLAYER_TAG = EDITOR_PLAYER_TAG
        self.ORIGINAL_PLAYER_TAG = ORIGINAL_PLAYER_TAG
        self.GAME_DIALOG_MAX_WIDTH_PIXELS = DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS 
        self.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = DEFAULT_LINE_WIDTH_WARNING_THRESHOLD_MAIN
        self.font_map = {} 

        self.is_programmatically_changing_text = False
        self.json_path = None; self.edited_json_path = None
        self.data = []; self.edited_data = {}; self.edited_file_data = []
        self.block_names = {}; self.current_block_idx = -1; self.current_string_idx = -1
        self.unsaved_changes = False
        self.unsaved_block_indices = set()

        # Атрибути для збереження стану UI
        self.last_selected_block_index = -1
        self.last_selected_string_index = -1
        self.last_cursor_position_in_edited = 0
        self.last_edited_text_edit_scroll_value_v = 0
        self.last_edited_text_edit_scroll_value_h = 0
        self.last_preview_text_edit_scroll_value_v = 0
        self.last_original_text_edit_scroll_value_v = 0
        self.last_original_text_edit_scroll_value_h = 0
        self.initial_load_path = None # Для шляху з settings.json
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

        log_debug("MainWindow: Initializing Core Components...")
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

        log_debug("MainWindow: Loading Editor Settings via SettingsManager...")
        self.settings_manager.load_settings() # Це встановить атрибути, такі як self.last_selected_block_index
        
        for editor_widget in [self.preview_text_edit, self.original_text_edit, self.edited_text_edit]:
            if editor_widget:
                editor_widget.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = self.LINE_WIDTH_WARNING_THRESHOLD_PIXELS
                editor_widget.font_map = self.font_map 
                editor_widget.GAME_DIALOG_MAX_WIDTH_PIXELS = self.GAME_DIALOG_MAX_WIDTH_PIXELS
                if hasattr(editor_widget, 'updateLineNumberAreaWidth'):
                    editor_widget.updateLineNumberAreaWidth(0)

        if self.initial_load_path:
            log_debug(f"MainWindow: Attempting to load initial file from settings: {self.initial_load_path}")
            self.app_action_handler.load_all_data_for_path(self.initial_load_path, self.initial_edited_load_path, is_initial_load_from_settings=True)
            # Відновлення стану після завантаження даних
            if self.data and 0 <= self.last_selected_block_index < len(self.data):
                self.block_list_widget.setCurrentRow(self.last_selected_block_index)
                # block_selected викличе populate_strings_for_block
                # Потрібно переконатися, що string_selected викликається після populate_strings_for_block
                QApplication.processEvents() # Даємо подіям обробитися
                if 0 <= self.last_selected_string_index < len(self.data[self.last_selected_block_index]):
                    self.list_selection_handler.string_selected_from_preview(self.last_selected_string_index)
                    QApplication.processEvents() 
                    if self.edited_text_edit:
                        doc_len = self.edited_text_edit.document().characterCount() -1 
                        pos_to_set = min(self.last_cursor_position_in_edited, doc_len if doc_len > 0 else 0)
                        cursor = self.edited_text_edit.textCursor()
                        cursor.setPosition(pos_to_set)
                        self.edited_text_edit.setTextCursor(cursor)
                        self.edited_text_edit.ensureCursorVisible()
                        # Відновлення скролу
                        self.edited_text_edit.verticalScrollBar().setValue(self.last_edited_text_edit_scroll_value_v)
                        self.edited_text_edit.horizontalScrollBar().setValue(self.last_edited_text_edit_scroll_value_h)
                        if self.preview_text_edit:
                            self.preview_text_edit.verticalScrollBar().setValue(self.last_preview_text_edit_scroll_value_v)
                        if self.original_text_edit:
                            self.original_text_edit.verticalScrollBar().setValue(self.last_original_text_edit_scroll_value_v)
                            self.original_text_edit.horizontalScrollBar().setValue(self.last_original_text_edit_scroll_value_h)

            log_debug(f"MainWindow: Restored selection to block {self.last_selected_block_index}, string {self.last_selected_string_index}, cursor {self.last_cursor_position_in_edited}")
        elif not self.json_path: # Якщо нічого не завантажено з settings і шляху немає
             log_debug("MainWindow: No file auto-loaded, updating initial UI state.")
             self.ui_updater.update_title(); self.ui_updater.update_statusbar_paths()
             self.ui_updater.populate_blocks()
             self.ui_updater.populate_strings_for_block(-1)


        if hasattr(self, 'search_history_to_save') and self.search_panel_widget:
            self.search_panel_widget.load_history(self.search_history_to_save)
            if self.search_history_to_save:
                last_query = self.search_history_to_save[0] 
                
                self.search_handler.current_query = last_query
                _, cs, so, it = self.search_panel_widget.get_search_parameters()
                self.search_handler.is_case_sensitive = cs
                self.search_handler.search_in_original = so
                self.search_handler.ignore_tags_newlines = it

            log_debug(f"Search history loaded into panel. Last query (if any) set in SearchHandler: {self.search_handler.current_query}")


        self._rebuild_unsaved_block_indices()

        log_debug("++++++++++++++++++++ MainWindow: Initialization Complete ++++++++++++++++++++")


    def _rebuild_unsaved_block_indices(self):
        self.unsaved_block_indices.clear()
        for block_idx, _ in self.edited_data.keys():
            self.unsaved_block_indices.add(block_idx)
        log_debug(f"Rebuilt unsaved_block_indices: {self.unsaved_block_indices}")
        if hasattr(self, 'block_list_widget'):
             self.block_list_widget.viewport().update()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_F3:
            if event.modifiers() & Qt.ShiftModifier:
                log_debug("Shift+F3 pressed - Find Previous")
                self.execute_find_previous_shortcut()
            else:
                log_debug("F3 pressed - Find Next")
                self.execute_find_next_shortcut()
        else:
            super().keyPressEvent(event)

    def execute_find_next_shortcut(self):
        query_to_use = ""
        case_sensitive_to_use = False
        search_in_original_to_use = False
        ignore_tags_to_use = True 

        if self.search_panel_widget.isVisible():
            query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use = self.search_panel_widget.get_search_parameters()
            if not query_to_use:
                self.search_panel_widget.set_status_message("Введіть запит для F3", is_error=True)
                self.search_panel_widget.focus_search_input()
                return
        else: 
            query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use = self.search_handler.get_current_search_params()
            if not query_to_use: 
                self.toggle_search_panel() 
                self.search_panel_widget.set_status_message("Введіть запит", is_error=True)
                return
        
        found = self.search_handler.find_next(query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use)
        if not found and not self.search_panel_widget.isVisible(): 
            QMessageBox.information(self, "Пошук", f"Не знайдено: \"{query_to_use}\"")


    def execute_find_previous_shortcut(self):
        query_to_use = ""
        case_sensitive_to_use = False
        search_in_original_to_use = False
        ignore_tags_to_use = True 

        if self.search_panel_widget.isVisible():
            query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use = self.search_panel_widget.get_search_parameters()
            if not query_to_use:
                self.search_panel_widget.set_status_message("Введіть запит для Shift+F3", is_error=True)
                self.search_panel_widget.focus_search_input()
                return
        else: 
            query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use = self.search_handler.get_current_search_params()
            if not query_to_use:
                self.toggle_search_panel()
                self.search_panel_widget.set_status_message("Введіть запит", is_error=True)
                return

        found = self.search_handler.find_previous(query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use)
        if not found and not self.search_panel_widget.isVisible():
            QMessageBox.information(self, "Пошук", f"Не знайдено: \"{query_to_use}\"")


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
            if hasattr(self, 'undo_typing_action'): self.edited_text_edit.undoAvailable.connect(self.undo_typing_action.setEnabled)
            if hasattr(self, 'redo_typing_action'): self.edited_text_edit.redoAvailable.connect(self.redo_typing_action.setEnabled)
            if hasattr(self.edited_text_edit, 'addTagMappingRequest'):
                self.edited_text_edit.addTagMappingRequest.connect(self.handle_add_tag_mapping_request)
                log_debug("Connected edited_text_edit.addTagMappingRequest signal.")
        if hasattr(self, 'paste_block_action'): self.paste_block_action.triggered.connect(self.editor_operation_handler.paste_block_text)
        if hasattr(self, 'open_action'): self.open_action.triggered.connect(self.app_action_handler.open_file_dialog_action)
        if hasattr(self, 'open_changes_action'): self.open_changes_action.triggered.connect(self.app_action_handler.open_changes_file_dialog_action)
        if hasattr(self, 'save_action'): self.save_action.triggered.connect(self.trigger_save_action)
        if hasattr(self, 'reload_action'): self.reload_action.triggered.connect(self.app_action_handler.reload_original_data_action)
        if hasattr(self, 'save_as_action'): self.save_as_action.triggered.connect(self.app_action_handler.save_as_dialog_action)
        if hasattr(self, 'revert_action'): self.revert_action.triggered.connect(self.trigger_revert_action)
        if hasattr(self, 'undo_paste_action'): self.undo_paste_action.triggered.connect(self.trigger_undo_paste_action)
        if hasattr(self, 'rescan_all_tags_action'): self.rescan_all_tags_action.triggered.connect(self.app_action_handler.rescan_all_tags)
        if hasattr(self, 'reload_tag_mappings_action'):
            self.reload_tag_mappings_action.triggered.connect(self.trigger_reload_tag_mappings)
            log_debug("Connected reload_tag_mappings_action.")
        if hasattr(self, 'find_action'):
            self.find_action.triggered.connect(self.toggle_search_panel)
            log_debug("Connected find_action.")
        if hasattr(self, 'search_panel_widget'):
            self.search_panel_widget.close_requested.connect(self.hide_search_panel)
            self.search_panel_widget.find_next_requested.connect(self.handle_panel_find_next)
            self.search_panel_widget.find_previous_requested.connect(self.handle_panel_find_previous)


        log_debug("--> MainWindow: connect_signals() finished")

    def handle_panel_find_next(self, query, case_sensitive, search_in_original, ignore_tags): 
        self.search_handler.find_next(query, case_sensitive, search_in_original, ignore_tags)

    def handle_panel_find_previous(self, query, case_sensitive, search_in_original, ignore_tags): 
        self.search_handler.find_previous(query, case_sensitive, search_in_original, ignore_tags)

    def toggle_search_panel(self):
        if self.search_panel_widget.isVisible():
            self.hide_search_panel()
        else:
            self.search_panel_widget.setVisible(True)
            last_query, case_sensitive, search_in_original, ignore_tags = self.search_handler.get_current_search_params()
            
            self.search_panel_widget.set_query(last_query if last_query else "")
            self.search_panel_widget.set_search_options(case_sensitive, search_in_original, ignore_tags)
            
            if hasattr(self, 'search_history_to_save'): 
                 self.search_panel_widget.load_history(self.search_history_to_save)
            else: 
                 self.search_panel_widget._update_combobox_items()


            self.search_panel_widget.focus_search_input()


    def hide_search_panel(self):
        self.search_panel_widget.setVisible(False)
        self.search_handler.clear_all_search_highlights()


    def trigger_save_action(self):
        log_debug("<<<<<<<<<< ACTION: Save Triggered (via MainWindow proxy) >>>>>>>>>>")
        if self.app_action_handler.save_data_action(ask_confirmation=True):
             self._rebuild_unsaved_block_indices()

    def trigger_revert_action(self):
        log_debug("<<<<<<<<<< ACTION: Revert Changes File Triggered >>>>>>>>>>")
        if self.data_processor.revert_edited_file_to_original():
            log_debug("Revert successful, UI updated by DataStateProcessor.")
            if hasattr(self, 'critical_problem_lines_per_block'): self.critical_problem_lines_per_block.clear()
            if hasattr(self, 'warning_problem_lines_per_block'): self.warning_problem_lines_per_block.clear()
            if hasattr(self, 'width_exceeded_lines_per_block'): self.width_exceeded_lines_per_block.clear()
            self._rebuild_unsaved_block_indices()
            if hasattr(self.ui_updater, 'clear_all_problem_block_highlights_and_text'):
                self.ui_updater.clear_all_problem_block_highlights_and_text()
        else: log_debug("Revert was cancelled or failed.")

    def trigger_undo_paste_action(self):
        log_debug("<<<<<<<<<< ACTION: Undo Paste Block Triggered >>>>>>>>>>")
        if not self.can_undo_paste:
            QMessageBox.information(self, "Undo Paste", "Nothing to undo for the last paste operation.")
            if hasattr(self, 'statusBar'): self.statusBar.showMessage("Nothing to undo for paste.", 2000)
            return

        block_to_refresh_ui_for = self.before_paste_block_idx_affected

        self.edited_data = dict(self.before_paste_edited_data_snapshot)
        self.critical_problem_lines_per_block = copy.deepcopy(self.before_paste_critical_problems_snapshot)
        self.warning_problem_lines_per_block = copy.deepcopy(self.before_paste_warning_problems_snapshot)
        self.width_exceeded_lines_per_block = copy.deepcopy(self.before_paste_width_exceeded_snapshot)

        self._rebuild_unsaved_block_indices()

        self.unsaved_changes = bool(self.edited_data)

        self.ui_updater.update_title()

        self.is_programmatically_changing_text = True
        preview_edit = getattr(self, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'clearAllProblemTypeHighlights'):
            preview_edit.clearAllProblemTypeHighlights() 

        if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
            self.ui_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)

        self.ui_updater.populate_strings_for_block(self.current_block_idx) 

        if self.current_block_idx != block_to_refresh_ui_for:
            if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
                self.ui_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)

        self.is_programmatically_changing_text = False
        self.can_undo_paste = False
        if hasattr(self, 'undo_paste_action'): self.undo_paste_action.setEnabled(False)
        if hasattr(self, 'statusBar'): self.statusBar.showMessage("Last paste operation undone.", 2000)

    def trigger_reload_tag_mappings(self):
        log_debug("<<<<<<<<<< ACTION: Reload Tag Mappings Triggered >>>>>>>>>>")
        if self.settings_manager.reload_default_tag_mappings():
            QMessageBox.information(self, "Tag Mappings Reloaded", "Default tag mappings have been reloaded from settings.json.")
            if self.current_block_idx != -1:
                block_name = self.block_names.get(str(self.current_block_idx), f"Block {self.current_block_idx}")
                if QMessageBox.question(self, "Rescan Tags",
                                       f"Do you want to rescan tags in the current block ('{block_name}') with the new mappings now?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
                    self.app_action_handler.rescan_issues_for_single_block(self.current_block_idx, use_default_mappings=True)
            else:
                 if QMessageBox.question(self, "Rescan Tags",
                                       "No block is currently selected. Do you want to rescan all tags in all blocks?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
                    self.app_action_handler.rescan_all_tags() # Цей метод тепер сканує все, але мапінги не застосовує до даних
        else: QMessageBox.warning(self, "Reload Error", "Could not reload tag mappings. Check settings.json or console logs.")


    def handle_add_tag_mapping_request(self, bracket_tag: str, curly_tag: str):
        log_debug(f"MainWindow: Received request to map '{bracket_tag}' -> '{curly_tag}'")
        if not bracket_tag or not curly_tag:
            log_debug("  Error: Empty bracket_tag or curly_tag.")
            QMessageBox.warning(self, "Add Tag Mapping Error", "Both tags must be non-empty.")
            return
        if not hasattr(self, 'default_tag_mappings'): self.default_tag_mappings = {}
        if bracket_tag in self.default_tag_mappings and self.default_tag_mappings[bracket_tag] == curly_tag:
            QMessageBox.information(self, "Add Tag Mapping", f"Mapping '{bracket_tag}' -> '{curly_tag}' already exists.")
            return
        reply = QMessageBox.Yes
        if bracket_tag in self.default_tag_mappings:
            reply = QMessageBox.question(self, "Confirm Overwrite",
                                         f"Tag '{bracket_tag}' is already mapped to '{self.default_tag_mappings[bracket_tag]}'.\n"
                                         f"Overwrite with '{curly_tag}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.default_tag_mappings[bracket_tag] = curly_tag
            log_debug(f"  Added/Updated mapping: {bracket_tag} -> {curly_tag}. Total mappings: {len(self.default_tag_mappings)}")
            QMessageBox.information(self, "Tag Mapping Added",
                                    f"Mapping '{bracket_tag}' -> '{curly_tag}' has been added/updated.\n"
                                    "This change will be saved to settings.json when the application is closed.")
            if self.current_block_idx != -1:
                block_name = self.block_names.get(str(self.current_block_idx), f"Block {self.current_block_idx}")
                if QMessageBox.question(self, "Rescan Tags",
                                       f"Do you want to rescan tags in the current block ('{block_name}') with the new mapping now?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
                    self.app_action_handler.rescan_issues_for_single_block(self.current_block_idx, use_default_mappings=True)
        else: log_debug("  User cancelled overwrite or no action taken.")


    def load_all_data_for_path(self, original_file_path, manually_set_edited_path=None, is_initial_load_from_settings=False):
        self.app_action_handler.load_all_data_for_path(original_file_path, manually_set_edited_path, is_initial_load_from_settings)
        self._rebuild_unsaved_block_indices()
        for editor_widget in [self.preview_text_edit, self.original_text_edit, self.edited_text_edit]:
            if editor_widget:
                editor_widget.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = self.LINE_WIDTH_WARNING_THRESHOLD_PIXELS
                editor_widget.font_map = self.font_map
                editor_widget.GAME_DIALOG_MAX_WIDTH_PIXELS = self.GAME_DIALOG_MAX_WIDTH_PIXELS
                if hasattr(editor_widget, 'updateLineNumberAreaWidth'): 
                    editor_widget.updateLineNumberAreaWidth(0)


    def _apply_text_wrap_settings(self):
        log_debug(f"Applying text wrap settings: Preview wrap: {self.preview_wrap_lines}, Editors wrap: {self.editors_wrap_lines}")
        preview_wrap_mode = QPlainTextEdit.WidgetWidth if self.preview_wrap_lines else QPlainTextEdit.NoWrap
        editors_wrap_mode = QPlainTextEdit.WidgetWidth if self.editors_wrap_lines else QPlainTextEdit.NoWrap
        if hasattr(self, 'preview_text_edit'): self.preview_text_edit.setLineWrapMode(preview_wrap_mode)
        if hasattr(self, 'original_text_edit'): self.original_text_edit.setLineWrapMode(editors_wrap_mode)
        if hasattr(self, 'edited_text_edit'): self.edited_text_edit.setLineWrapMode(editors_wrap_mode)


    def _reconfigure_all_highlighters(self):
        log_debug("MainWindow: Reconfiguring all highlighters...")
        common_args = {
            "newline_symbol": self.newline_display_symbol, "newline_css_str": self.newline_css,
            "tag_css_str": self.tag_css, "show_multiple_spaces_as_dots": self.show_multiple_spaces_as_dots,
            "space_dot_color_hex": self.space_dot_color_hex, "bracket_tag_color_hex": self.bracket_tag_color_hex
        }
        text_edits_with_highlighters = []
        if hasattr(self, 'preview_text_edit') and hasattr(self.preview_text_edit, 'highlighter'): text_edits_with_highlighters.append(self.preview_text_edit)
        if hasattr(self, 'original_text_edit') and hasattr(self.original_text_edit, 'highlighter'): text_edits_with_highlighters.append(self.original_text_edit)
        if hasattr(self, 'edited_text_edit') and hasattr(self.edited_text_edit, 'highlighter'): text_edits_with_highlighters.append(self.edited_text_edit)
        for text_edit in text_edits_with_highlighters:
            if text_edit.highlighter:
                text_edit.highlighter.reconfigure_styles(**common_args)
                text_edit.highlighter.rehighlight()
        log_debug("MainWindow: Highlighter reconfiguration attempt complete.")


    def closeEvent(self, event):
        log_debug("--> MainWindow: closeEvent received.")
        
        # Зберігаємо поточний стан перед закриттям
        self.last_selected_block_index = self.current_block_idx
        self.last_selected_string_index = self.current_string_idx
        if self.edited_text_edit:
            self.last_cursor_position_in_edited = self.edited_text_edit.textCursor().position()
            self.last_edited_text_edit_scroll_value_v = self.edited_text_edit.verticalScrollBar().value()
            self.last_edited_text_edit_scroll_value_h = self.edited_text_edit.horizontalScrollBar().value()
        if self.preview_text_edit:
            self.last_preview_text_edit_scroll_value_v = self.preview_text_edit.verticalScrollBar().value()
        if self.original_text_edit:
            self.last_original_text_edit_scroll_value_v = self.original_text_edit.verticalScrollBar().value()
            self.last_original_text_edit_scroll_value_h = self.original_text_edit.horizontalScrollBar().value()


        if self.search_panel_widget:
            self.search_history_to_save = self.search_panel_widget.get_history()
            log_debug(f"Preparing to save search history: {len(self.search_history_to_save)} items")

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