import sys
import os
import json
import copy 
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QPlainTextEdit
from PyQt5.QtCore import Qt

from LineNumberArea import LineNumberArea # <--- Перевірити імпорт
from CustomListWidget import CustomListWidget
from ui_setup import setup_main_window_ui
from data_state_processor import DataStateProcessor
from ui_updater import UIUpdater
from settings_manager import SettingsManager

from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler
from handlers.app_action_handler import AppActionHandler

from utils import log_debug

EDITOR_PLAYER_TAG = "[ІМ'Я ГРАВЦЯ]"
ORIGINAL_PLAYER_TAG = "{Player}"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        log_debug("++++++++++++++++++++ MainWindow: Initializing ++++++++++++++++++++")
        
        self.EDITOR_PLAYER_TAG = EDITOR_PLAYER_TAG 
        self.ORIGINAL_PLAYER_TAG = ORIGINAL_PLAYER_TAG

        self.is_programmatically_changing_text = False
        self.json_path = None; self.edited_json_path = None
        self.data = []; self.edited_data = {}; self.edited_file_data = []
        self.block_names = {}; self.current_block_idx = -1; self.current_string_idx = -1
        self.unsaved_changes = False
        # --- Нова множина для відстеження незбережених блоків ---
        self.unsaved_block_indices = set() 
        # -------------------------------------------------------

        self.newline_display_symbol = "↵"
        self.newline_css = "color: #A020F0; font-weight: bold;"
        self.tag_css = "color: #808080; font-style: italic;"
        self.show_multiple_spaces_as_dots = True
        self.space_dot_color_hex = "#BBBBBB"
        self.preview_wrap_lines = True
        self.editors_wrap_lines = False
        self.bracket_tag_color_hex = "#FF8C00" 

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

        self.can_undo_paste = False
        self.before_paste_edited_data_snapshot = {}
        self.before_paste_block_idx_affected = -1
        self.before_paste_critical_problems_snapshot = {} 
        self.before_paste_warning_problems_snapshot = {}

        self.main_splitter = None; self.right_splitter = None; self.bottom_right_splitter = None
        self.open_action = None; self.open_changes_action = None; self.save_action = None;
        self.save_as_action = None; self.reload_action = None; self.revert_action = None;
        self.reload_tag_mappings_action = None 
        self.exit_action = None; self.paste_block_action = None;
        self.undo_typing_action = None; self.redo_typing_action = None;
        self.undo_paste_action = None
        self.rescan_all_tags_action = None

        log_debug("MainWindow: Initializing Core Components...")
        self.data_processor = DataStateProcessor(self)
        self.ui_updater = UIUpdater(self, self.data_processor)
        self.settings_manager = SettingsManager(self)

        log_debug("MainWindow: Initializing Handlers...")
        self.list_selection_handler = ListSelectionHandler(self, self.data_processor, self.ui_updater)
        self.editor_operation_handler = TextOperationHandler(self, self.data_processor, self.ui_updater)
        self.app_action_handler = AppActionHandler(self, self.data_processor, self.ui_updater) 

        log_debug("MainWindow: Setting up UI...")
        setup_main_window_ui(self) 

        log_debug("MainWindow: Connecting Signals...")
        self.connect_signals()

        log_debug("MainWindow: Loading Editor Settings via SettingsManager...")
        self.settings_manager.load_settings() 

        if not self.json_path:
             log_debug("MainWindow: No file auto-loaded, updating initial UI state.")
             self.ui_updater.update_title(); self.ui_updater.update_statusbar_paths()
             self.ui_updater.populate_blocks()
             self.ui_updater.populate_strings_for_block(-1)
             
        # Початкове заповнення unsaved_block_indices на основі edited_data, 
        # яке могло бути завантажене (хоча зараз логіка цього не передбачає, але про всяк випадок)
        self._rebuild_unsaved_block_indices()

        log_debug("++++++++++++++++++++ MainWindow: Initialization Complete ++++++++++++++++++++")

    # --- Новий метод для оновлення множини незбережених блоків ---
    def _rebuild_unsaved_block_indices(self):
        """Перебудовує множину індексів блоків з незбереженими змінами."""
        self.unsaved_block_indices.clear()
        for block_idx, _ in self.edited_data.keys():
            self.unsaved_block_indices.add(block_idx)
        log_debug(f"Rebuilt unsaved_block_indices: {self.unsaved_block_indices}")
        # Оновлюємо відображення списку блоків, щоб маркери з'явилися/зникли
        if hasattr(self, 'block_list_widget'):
             self.block_list_widget.viewport().update() # Примусове перемальовування списку
    # -----------------------------------------------------------------
        
    def connect_signals(self):
        # ... (без змін) ...
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
        log_debug("--> MainWindow: connect_signals() finished")


    def trigger_save_action(self):
        log_debug("<<<<<<<<<< ACTION: Save Triggered (via MainWindow proxy) >>>>>>>>>>")
        if self.app_action_handler.save_data_action(ask_confirmation=True):
             # Після успішного збереження перебудовуємо індекси (мають стати порожніми)
             self._rebuild_unsaved_block_indices()

    def trigger_revert_action(self):
        log_debug("<<<<<<<<<< ACTION: Revert Changes File Triggered >>>>>>>>>>")
        if self.data_processor.revert_edited_file_to_original():
            log_debug("Revert successful, UI updated by DataStateProcessor.")
            if hasattr(self, 'critical_problem_lines_per_block'): self.critical_problem_lines_per_block.clear()
            if hasattr(self, 'warning_problem_lines_per_block'): self.warning_problem_lines_per_block.clear()
            # Після відкату до оригіналу, незбережених змін немає
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
        
        # Запам'ятовуємо блок, який треба оновити
        block_to_refresh_ui_for = self.before_paste_block_idx_affected
        
        self.edited_data = dict(self.before_paste_edited_data_snapshot) 
        self.critical_problem_lines_per_block = copy.deepcopy(self.before_paste_critical_problems_snapshot)
        self.warning_problem_lines_per_block = copy.deepcopy(self.before_paste_warning_problems_snapshot)
        
        # Перебудовуємо індекси незбережених блоків після відновлення edited_data
        self._rebuild_unsaved_block_indices() 
        
        self.unsaved_changes = bool(self.edited_data) # Визначаємо unsaved_changes на основі edited_data
        # is_different_from_file логіка тут не потрібна, бо unsaved_changes це просто наявність edited_data
        
        self.ui_updater.update_title()
        
        self.is_programmatically_changing_text = True
        preview_edit = getattr(self, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'clearAllProblemTypeHighlights'): 
            # Очищаємо підсвічування проблем тільки для поточного блоку, бо інші могли мати проблеми до вставки
            preview_edit.clearCriticalProblemHighlights() 
            preview_edit.clearWarningLineHighlights()
        
        # Оновлюємо текст елемента списку (лічильники проблем)
        if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'): 
            self.ui_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)
        
        # Оновлюємо вміст preview
        self.ui_updater.populate_strings_for_block(self.current_block_idx) 
        
        # Оновлюємо лічильник проблем для сусіднього блоку, якщо він був зачеплений
        if self.current_block_idx != block_to_refresh_ui_for:
            if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'): 
                self.ui_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)
            
        self.is_programmatically_changing_text = False
        self.can_undo_paste = False
        if hasattr(self, 'undo_paste_action'): self.undo_paste_action.setEnabled(False)
        if hasattr(self, 'statusBar'): self.statusBar.showMessage("Last paste operation undone.", 2000)

    def trigger_reload_tag_mappings(self):
        # ... (без змін) ...
        log_debug("<<<<<<<<<< ACTION: Reload Tag Mappings Triggered >>>>>>>>>>")
        if self.settings_manager.reload_default_tag_mappings():
            QMessageBox.information(self, "Tag Mappings Reloaded", "Default tag mappings have been reloaded from settings.json.")
            if self.current_block_idx != -1:
                block_name = self.block_names.get(str(self.current_block_idx), f"Block {self.current_block_idx}")
                if QMessageBox.question(self, "Rescan Tags", 
                                       f"Do you want to rescan tags in the current block ('{block_name}') with the new mappings now?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
                    self.app_action_handler.rescan_tags_for_single_block(self.current_block_idx)
            else:
                 if QMessageBox.question(self, "Rescan Tags", 
                                       "No block is currently selected. Do you want to rescan all tags in all blocks?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes: 
                    self.app_action_handler.rescan_all_tags()
        else: QMessageBox.warning(self, "Reload Error", "Could not reload tag mappings. Check settings.json or console logs.")


    def handle_add_tag_mapping_request(self, bracket_tag: str, curly_tag: str):
        # ... (без змін) ...
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
                    self.app_action_handler.rescan_tags_for_single_block(self.current_block_idx)
        else: log_debug("  User cancelled overwrite or no action taken.")


    def load_all_data_for_path(self, original_file_path, manually_set_edited_path=None, is_initial_load_from_settings=False):
        self.app_action_handler.load_all_data_for_path(original_file_path, manually_set_edited_path, is_initial_load_from_settings)
        # Після завантаження нових даних, перебудовуємо індекси незбережених (будуть порожні)
        self._rebuild_unsaved_block_indices() 

    def _apply_text_wrap_settings(self):
        # ... (без змін) ...
        log_debug(f"Applying text wrap settings: Preview wrap: {self.preview_wrap_lines}, Editors wrap: {self.editors_wrap_lines}")
        preview_wrap_mode = QPlainTextEdit.WidgetWidth if self.preview_wrap_lines else QPlainTextEdit.NoWrap
        editors_wrap_mode = QPlainTextEdit.WidgetWidth if self.editors_wrap_lines else QPlainTextEdit.NoWrap
        if hasattr(self, 'preview_text_edit'): self.preview_text_edit.setLineWrapMode(preview_wrap_mode)
        if hasattr(self, 'original_text_edit'): self.original_text_edit.setLineWrapMode(editors_wrap_mode)
        if hasattr(self, 'edited_text_edit'): self.edited_text_edit.setLineWrapMode(editors_wrap_mode)


    def _reconfigure_all_highlighters(self):
        # ... (без змін) ...
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
        # Перевірка unsaved_changes тепер робиться в AppActionHandler
        self.app_action_handler.handle_close_event(event)
        if event.isAccepted():
            log_debug("Close accepted. Saving editor settings via SettingsManager.")
            self.settings_manager.save_settings() 
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