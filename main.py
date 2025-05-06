import sys
import os
import json 
import base64 
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt, QByteArray 

from LineNumberedTextEdit import LineNumberedTextEdit
from CustomListWidget import CustomListWidget
from ui_setup import setup_main_window_ui
from data_state_processor import DataStateProcessor
from ui_updater import UIUpdater # Ensure UIUpdater is correctly imported
from data_manager import load_json_file

from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler
from handlers.app_action_handler import AppActionHandler

from utils import log_debug

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        log_debug("++++++++++++++++++++ MainWindow: Initializing ++++++++++++++++++++")
        self.is_programmatically_changing_text = False 
        self.json_path = None; self.edited_json_path = None
        self.data = []; self.edited_data = {}; self.edited_file_data = []
        self.block_names = {}; self.current_block_idx = -1; self.current_string_idx = -1
        self.unsaved_changes = False; self.settings_file_path = "settings.json"
        
        # Initialize style-related attributes with defaults before load_editor_settings
        self.newline_display_symbol = "↵"
        self.newline_css = "color: #A020F0; font-weight: bold;"
        self.tag_css = "color: #808080; font-style: italic;"
        self.show_multiple_spaces_as_dots = True 
        self.space_dot_color_hex = "#BBBBBB" 

        self.main_splitter = None; self.right_splitter = None; self.bottom_right_splitter = None
        self.open_action = None; self.open_changes_action = None; self.save_action = None; 
        self.save_as_action = None; self.reload_action = None; self.revert_action = None; 
        self.exit_action = None; self.paste_block_action = None; 

        log_debug("MainWindow: Initializing Core Components...")
        self.data_processor = DataStateProcessor(self)
        self.ui_updater = UIUpdater(self, self.data_processor)
        log_debug("MainWindow: Initializing Handlers...")
        self.list_selection_handler = ListSelectionHandler(self, self.data_processor, self.ui_updater)
        self.editor_operation_handler = TextOperationHandler(self, self.data_processor, self.ui_updater)
        self.app_action_handler = AppActionHandler(self, self.data_processor, self.ui_updater)
        
        log_debug("MainWindow: Setting up UI...")
        setup_main_window_ui(self) 
        
        log_debug("MainWindow: Connecting Signals...")
        self.connect_signals()
        log_debug("MainWindow: Loading Editor Settings...")
        self.load_editor_settings() 
        
        if not self.json_path:
             log_debug("MainWindow: No file auto-loaded, updating initial UI state.")
             self.ui_updater.update_title(); self.ui_updater.update_statusbar_paths()
             self.ui_updater.populate_blocks(); self.ui_updater.populate_strings_for_block(-1) 
        
        log_debug("++++++++++++++++++++ MainWindow: Initialization Complete ++++++++++++++++++++")

    def connect_signals(self):
        log_debug("--> MainWindow: connect_signals() started")
        if hasattr(self, 'block_list_widget'):
            self.block_list_widget.currentItemChanged.connect(self.list_selection_handler.block_selected)
            self.block_list_widget.itemDoubleClicked.connect(self.list_selection_handler.rename_block)
        
        if hasattr(self, 'preview_text_edit') and hasattr(self.preview_text_edit, 'lineClicked'):
            self.preview_text_edit.lineClicked.connect(self.list_selection_handler.string_selected_from_preview)
            log_debug("Connected preview_text_edit.lineClicked signal.")
        
        if hasattr(self, 'edited_text_edit'):
            self.edited_text_edit.textChanged.connect(self.editor_operation_handler.text_edited)
            self.edited_text_edit.cursorPositionChanged.connect(self.ui_updater.update_status_bar)
            self.edited_text_edit.selectionChanged.connect(self.ui_updater.update_status_bar_selection)
            log_debug("Connected edited_text_edit signals.")
        
        if hasattr(self, 'paste_block_action'): self.paste_block_action.triggered.connect(self.editor_operation_handler.paste_block_text); log_debug("Connected paste_block_action.")
        if hasattr(self, 'open_action'): self.open_action.triggered.connect(self.open_file_dialog_action); log_debug("Connected open_action.")
        if hasattr(self, 'open_changes_action'): 
            self.open_changes_action.triggered.connect(self.open_changes_file_dialog_action) 
            log_debug("Connected open_changes_action.")
        if hasattr(self, 'save_action'): self.save_action.triggered.connect(self.trigger_save_action); log_debug("Connected save_action.")
        if hasattr(self, 'reload_action'): self.reload_action.triggered.connect(self.reload_original_data_action); log_debug("Connected reload_action.")
        if hasattr(self, 'save_as_action'): self.save_as_action.triggered.connect(self.save_as_dialog_action); log_debug("Connected save_as_action.")
        if hasattr(self, 'revert_action'): self.revert_action.triggered.connect(self.trigger_revert_action); log_debug("Connected revert_action.")
        
        log_debug("--> MainWindow: connect_signals() finished")

    def trigger_save_action(self):
        log_debug("<<<<<<<<<< ACTION: Save Triggered >>>>>>>>>>")
        self.app_action_handler.save_data_action(ask_confirmation=True) 

    def trigger_revert_action(self):
        log_debug("<<<<<<<<<< ACTION: Revert Changes File Triggered >>>>>>>>>>")
        if self.data_processor.revert_edited_file_to_original():
            log_debug("Revert successful, UI updated by DataStateProcessor.")
        else:
            log_debug("Revert was cancelled or failed.")


    def open_changes_file_dialog_action(self):
        log_debug("--> ACTION: Open Changes File Dialog Triggered")
        if not self.json_path:
            QMessageBox.warning(self, "Open Changes File", "Please open an original file first.")
            log_debug("<-- ACTION: Open Changes File finished (No original open).")
            return
            
        start_dir = os.path.dirname(self.edited_json_path) if self.edited_json_path else (os.path.dirname(self.json_path) if self.json_path else "")
            
        log_debug(f"Opening file dialog for changes file, starting directory: '{start_dir}'")
        path, _ = QFileDialog.getOpenFileName(self, "Open Changes (Edited) JSON File", start_dir, "JSON Files (*.json);;All Files (*)")

        if path:
            log_debug(f"User selected changes file: {path}")
            
            if self.unsaved_changes:
                 reply = QMessageBox.question(self, 'Unsaved Changes',
                                             "Loading a new changes file will discard current unsaved edits. Proceed?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                 if reply == QMessageBox.No:
                     log_debug("User cancelled loading changes file due to unsaved edits.")
                     log_debug("<-- ACTION: Open Changes File finished (Cancelled).")
                     return

            new_edited_data, error = load_json_file(path, parent_widget=self, expected_type=list)
            if error:
                QMessageBox.critical(self, "Load Error", f"Failed to load selected changes file:\n{path}\n\n{error}")
                log_debug(f"Error loading selected changes file: {error}")
                log_debug("<-- ACTION: Open Changes File finished (Load Error).")
                return

            log_debug("Successfully loaded new changes file data. Updating state...")
            self.edited_json_path = path 
            self.edited_file_data = new_edited_data 
            self.edited_data = {} 
            self.unsaved_changes = False 

            self.ui_updater.update_title()
            self.ui_updater.update_statusbar_paths()
            
            log_debug("Refreshing UI after loading new changes file...")
            selected_block_idx = self.current_block_idx 
            # selected_string_idx = self.current_string_idx # Not directly used here, populate_strings handles it

            # self.is_programmatically_changing_text = True # Handled by ui_updater methods
            self.ui_updater.populate_strings_for_block(selected_block_idx) 
            # self.is_programmatically_changing_text = False
            log_debug("UI refreshed.")

        else:
            log_debug("User cancelled changes file dialog.")
        log_debug("<-- ACTION: Open Changes File finished.")

    def _derive_edited_path(self, original_path):
        if not original_path: return None
        base, ext = os.path.splitext(os.path.basename(original_path))
        dir_name = os.path.dirname(original_path)
        if not dir_name: dir_name = "." 
        return os.path.join(dir_name, f"{base}_edited{ext}")

    def open_file_dialog_action(self):
        log_debug("--> ACTION: Open File Dialog Triggered")
        if self.unsaved_changes:
            reply = QMessageBox.question(self, 'Unsaved Changes', "Save before opening new file?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.app_action_handler.save_data_action(ask_confirmation=True): return
            elif reply == QMessageBox.Cancel: return
        start_dir = os.path.dirname(self.json_path) if self.json_path else ""
        path, _ = QFileDialog.getOpenFileName(self, "Open Original JSON", start_dir, "JSON (*.json);;All (*)")
        if path: self.load_all_data_for_path(path)
        else: log_debug("User cancelled file dialog.")
        log_debug("<-- ACTION: Open File Dialog Finished")
            
    def save_as_dialog_action(self):
        log_debug("--> ACTION: Save As Dialog Triggered")
        if not self.json_path: QMessageBox.warning(self, "Save As Error", "No original file open."); return
        current_edited_path = self.edited_json_path if self.edited_json_path else self._derive_edited_path(self.json_path)
        if not current_edited_path: current_edited_path = "" 
        new_edited_path, _ = QFileDialog.getSaveFileName(self, "Save Changes As...", current_edited_path, "JSON (*.json);;All (*)")
        if new_edited_path:
            original_edited_path_backup = self.edited_json_path
            self.edited_json_path = new_edited_path
            save_success = self.app_action_handler.save_data_action(ask_confirmation=False) 
            if save_success: 
                QMessageBox.information(self, "Saved As", f"Changes saved to:\n{self.edited_json_path}")
                self.ui_updater.update_statusbar_paths() 
            else: 
                QMessageBox.critical(self, "Save As Error", f"Failed to save to:\n{self.edited_json_path}")
                self.edited_json_path = original_edited_path_backup 
                self.ui_updater.update_statusbar_paths()
        else: log_debug("Save As cancelled by user.")
        log_debug("<-- ACTION: Save As Finished")

    def load_all_data_for_path(self, original_file_path, manually_set_edited_path=None):
        log_debug(f"--> MainWindow: load_all_data_for_path START. Original: '{original_file_path}', Manual Edit Path: '{manually_set_edited_path}'")
        # self.is_programmatically_changing_text = True; # Handled by ui_updater methods
        data, error = load_json_file(original_file_path, parent_widget=self, expected_type=list)
        if error:
            log_debug(f"ERROR loading original: {error}"); QMessageBox.critical(self, "Load Error", f"Failed: {original_file_path}\n{error}")
            self.json_path = None; self.edited_json_path = None; self.data = []
            self.edited_data = {}; self.edited_file_data = []; self.unsaved_changes = False
            self.ui_updater.update_title(); self.ui_updater.update_statusbar_paths()
            self.ui_updater.populate_blocks(); self.ui_updater.populate_strings_for_block(-1)
            # self.is_programmatically_changing_text = False;
            log_debug("<-- MainWindow: load_all_data_for_path FINISHED (Error)")
            return
        self.json_path = original_file_path; self.data = data
        self.edited_data = {}; self.unsaved_changes = False
        self.edited_json_path = manually_set_edited_path if manually_set_edited_path else self._derive_edited_path(self.json_path)
        
        self.edited_file_data = [] 
        if self.edited_json_path and os.path.exists(self.edited_json_path):
            edited_data_from_file, edit_error = load_json_file(self.edited_json_path, parent_widget=self, expected_type=list)
            if edit_error: 
                QMessageBox.warning(self, "Edited Load Warning", f"Could not load changes file: {self.edited_json_path}\n{edit_error}\n\nNo existing changes will be applied from this file.")
            else: self.edited_file_data = edited_data_from_file
            
        self.current_block_idx = -1; self.current_string_idx = -1 
        
        self.block_list_widget.clear()
        if hasattr(self, 'preview_text_edit'): self.preview_text_edit.clear() 
        self.original_text_edit.clear(); self.edited_text_edit.clear()

        self.ui_updater.populate_blocks() 
        self.ui_updater.update_title(); self.ui_updater.update_statusbar_paths()
        
        if self.block_list_widget.count() > 0: 
            self.block_list_widget.setCurrentRow(0) 
        else: 
            self.ui_updater.populate_strings_for_block(-1) 
            
        # self.is_programmatically_changing_text = False;
        log_debug(f"<-- MainWindow: load_all_data_for_path FINISHED (Success)")

    def reload_original_data_action(self):
        log_debug("--> ACTION: Reload Original Triggered")
        if not self.json_path: QMessageBox.information(self, "Reload", "No file open."); return
        if self.unsaved_changes:
            reply = QMessageBox.question(self, 'Unsaved Changes', "Reloading will discard current unsaved edits in memory. Proceed?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: log_debug("<-- ACTION: Reload Aborted"); return
        
        current_edited_path = self.edited_json_path 
        self.load_all_data_for_path(self.json_path, manually_set_edited_path=current_edited_path)
        log_debug("<-- ACTION: Reload Original Finished")

    def _reconfigure_all_highlighters(self):
        log_debug("MainWindow: Reconfiguring all highlighters...")
        common_args = {
            "newline_symbol": self.newline_display_symbol,
            "newline_css_str": self.newline_css,
            "tag_css_str": self.tag_css,
            "show_multiple_spaces_as_dots": self.show_multiple_spaces_as_dots,
            "space_dot_color_hex": self.space_dot_color_hex
        }
        text_edits_with_highlighters = []
        if hasattr(self, 'preview_text_edit') and hasattr(self.preview_text_edit, 'highlighter'):
            text_edits_with_highlighters.append(self.preview_text_edit)
        if hasattr(self, 'original_text_edit') and hasattr(self.original_text_edit, 'highlighter'):
            text_edits_with_highlighters.append(self.original_text_edit)
        if hasattr(self, 'edited_text_edit') and hasattr(self.edited_text_edit, 'highlighter'):
            text_edits_with_highlighters.append(self.edited_text_edit)

        for text_edit in text_edits_with_highlighters:
            if text_edit.highlighter: # Check if highlighter exists
                log_debug(f"Reconfiguring highlighter for {text_edit}...")
                text_edit.highlighter.reconfigure_styles(**common_args)
                text_edit.highlighter.rehighlight()
            else:
                log_debug(f"Highlighter not found for {text_edit}")
        log_debug("MainWindow: Highlighter reconfiguration attempt complete.")


    def load_editor_settings(self):
        log_debug(f"--> MainWindow: load_editor_settings from {self.settings_file_path}")
        
        # Use attributes initialized in __init__ as defaults
        default_settings = {
            "newline_display_symbol": self.newline_display_symbol,
            "newline_css": self.newline_css,
            "tag_css": self.tag_css,
            "show_multiple_spaces_as_dots": self.show_multiple_spaces_as_dots,
            "space_dot_color_hex": self.space_dot_color_hex
            # Add other settings here if they also have __init__ defaults
        }

        if not os.path.exists(self.settings_file_path): 
            log_debug("Settings file not found. Using defaults and attempting to reconfigure highlighters with defaults.")
            self._reconfigure_all_highlighters() 
            return
            
        try:
            with open(self.settings_file_path, 'r', encoding='utf-8') as f: settings_data = json.load(f)
        except Exception as e: 
            log_debug(f"ERROR reading settings: {e}. Using defaults and attempting to reconfigure highlighters with defaults.")
            self._reconfigure_all_highlighters() 
            return

        window_geom = settings_data.get("window_geometry")
        if window_geom and isinstance(window_geom, dict) and all(k in window_geom for k in ('x', 'y', 'width', 'height')):
            try: self.setGeometry(window_geom['x'], window_geom['y'], window_geom['width'], window_geom['height'])
            except Exception as e: log_debug(f"WARN: Failed to restore window geometry: {e}")
        
        try:
            if self.main_splitter and "main_splitter_state" in settings_data: self.main_splitter.restoreState(QByteArray(base64.b64decode(settings_data["main_splitter_state"])))
            if self.right_splitter and "right_splitter_state" in settings_data: self.right_splitter.restoreState(QByteArray(base64.b64decode(settings_data["right_splitter_state"])))
            if self.bottom_right_splitter and "bottom_right_splitter_state" in settings_data: self.bottom_right_splitter.restoreState(QByteArray(base64.b64decode(settings_data["bottom_right_splitter_state"])))
        except Exception as e: log_debug(f"WARN: Failed to restore splitter state(s): {e}")
        
        self.block_names = {str(k): v for k, v in settings_data.get("block_names", {}).items()}
        
        self.newline_display_symbol = settings_data.get("newline_display_symbol", default_settings["newline_display_symbol"])
        self.newline_css = settings_data.get("newline_css", default_settings["newline_css"])
        self.tag_css = settings_data.get("tag_css", default_settings["tag_css"])
        self.show_multiple_spaces_as_dots = settings_data.get("show_multiple_spaces_as_dots", default_settings["show_multiple_spaces_as_dots"])
        self.space_dot_color_hex = settings_data.get("space_dot_color_hex", default_settings["space_dot_color_hex"])
        
        log_debug(f"Loaded styles: nl_sym='{self.newline_display_symbol}', nl_css='{self.newline_css}', tag_css='{self.tag_css}', show_spaces='{self.show_multiple_spaces_as_dots}', space_color='{self.space_dot_color_hex}'")

        self._reconfigure_all_highlighters()

        last_original_file = settings_data.get("original_file_path"); last_edited_file = settings_data.get("edited_file_path")
        
        if last_original_file and os.path.exists(last_original_file):
            effective_edited_path = last_edited_file if last_edited_file and os.path.exists(last_edited_file) else None
            self.load_all_data_for_path(last_original_file, manually_set_edited_path=effective_edited_path)
        elif last_original_file: 
            log_debug(f"Last file '{last_original_file}' not found.")
        
        log_debug("<-- MainWindow: load_editor_settings finished")

    def save_editor_settings(self):
        log_debug(f"--> MainWindow: save_editor_settings to {self.settings_file_path}")
        settings_data = {"block_names": {str(k): v for k, v in self.block_names.items()}}
        geom = self.geometry(); settings_data["window_geometry"] = {"x": geom.x(), "y": geom.y(), "width": geom.width(), "height": geom.height()}
        
        settings_data["newline_display_symbol"] = self.newline_display_symbol
        settings_data["newline_css"] = self.newline_css
        settings_data["tag_css"] = self.tag_css
        settings_data["show_multiple_spaces_as_dots"] = self.show_multiple_spaces_as_dots
        settings_data["space_dot_color_hex"] = self.space_dot_color_hex
        
        try:
            if self.main_splitter: settings_data["main_splitter_state"] = base64.b64encode(self.main_splitter.saveState().data()).decode('ascii')
            if self.right_splitter: settings_data["right_splitter_state"] = base64.b64encode(self.right_splitter.saveState().data()).decode('ascii')
            if self.bottom_right_splitter: settings_data["bottom_right_splitter_state"] = base64.b64encode(self.bottom_right_splitter.saveState().data()).decode('ascii')
        except Exception as e: log_debug(f"WARN: Failed to save splitter state(s): {e}")
        
        if self.json_path: settings_data["original_file_path"] = self.json_path
        if self.edited_json_path: settings_data["edited_file_path"] = self.edited_json_path
        
        try:
            with open(self.settings_file_path, 'w', encoding='utf-8') as f: json.dump(settings_data, f, indent=4, ensure_ascii=False)
        except Exception as e: log_debug(f"ERROR saving settings: {e}")
        log_debug("<-- MainWindow: save_editor_settings finished")

    def closeEvent(self, event):
        log_debug("--> MainWindow: closeEvent received.")
        self.app_action_handler.handle_close_event(event) 
        if event.isAccepted(): 
            log_debug("Close accepted. Saving editor settings.")
            self.save_editor_settings()
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