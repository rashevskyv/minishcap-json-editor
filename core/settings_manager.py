import json
import os
import base64
from PyQt5.QtCore import QByteArray, QRect
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QFont
from utils.utils import log_debug
from constants import (
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD
)

class SettingsManager:
    def __init__(self, main_window):
        self.mw = main_window
        self.settings_file_path = "settings.json"
        self.font_map_file_path = "font_map.json"
        self.initial_default_tag_mappings = dict(getattr(self.mw, 'default_tag_mappings', {}))

    def reload_default_tag_mappings(self) -> bool:
        log_debug(f"--> SettingsManager: reload_default_tag_mappings from {self.settings_file_path}")
        if not os.path.exists(self.settings_file_path):
            log_debug(f"Settings file '{self.settings_file_path}' not found. Cannot reload tag mappings.")
            return False
        try:
            with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)
            loaded_mappings = settings_data.get("default_tag_mappings")
            if isinstance(loaded_mappings, dict):
                self.mw.default_tag_mappings = loaded_mappings
                log_debug(f"Successfully reloaded default_tag_mappings. Count: {len(self.mw.default_tag_mappings)}")
                return True
            else:
                log_debug("WARN: 'default_tag_mappings' in settings is not a dictionary or missing. Using previous values.")
                return False
        except Exception as e:
            log_debug(f"ERROR reading settings file '{self.settings_file_path}' for tag mappings: {e}.")
            return False

    def load_font_map(self):
        log_debug(f"--> SettingsManager: load_font_map from {self.font_map_file_path}")
        if not os.path.exists(self.font_map_file_path):
            log_debug(f"Font map file '{self.font_map_file_path}' not found. Font map will be empty.")
            self.mw.font_map = {}
            QMessageBox.warning(self.mw, "Font Map Error", f"Font map file '{self.font_map_file_path}' not found. Character width calculations will be inaccurate.")
            return False
        try:
            with open(self.font_map_file_path, 'r', encoding='utf-8') as f:
                font_map_data = json.load(f)
            if isinstance(font_map_data, dict):
                self.mw.font_map = font_map_data
                log_debug(f"Successfully loaded font_map. Count: {len(self.mw.font_map)}")
                return True
            else:
                log_debug("WARN: Font map in settings is not a dictionary or missing. Font map will be empty.")
                self.mw.font_map = {}
                QMessageBox.warning(self.mw, "Font Map Error", f"Font map file '{self.font_map_file_path}' has incorrect format. Expected a dictionary.")
                return False
        except Exception as e:
            log_debug(f"ERROR reading font map file '{self.font_map_file_path}': {e}.")
            self.mw.font_map = {}
            QMessageBox.critical(self.mw, "Font Map Load Error", f"Error loading font map file '{self.font_map_file_path}':\n{e}")
            return False

    def load_settings(self):
        log_debug(f"--> SettingsManager: load_settings from {self.settings_file_path}")

        self.load_font_map()

        default_font_size = QFont().pointSize()
        if default_font_size <= 0: default_font_size = 10
        log_debug(f"SettingsManager: Initial default_font_size (from QFont or 10): {default_font_size}")


        default_settings_values = {
            "newline_display_symbol": getattr(self.mw, 'newline_display_symbol', "↵"),
            "newline_css": getattr(self.mw, 'newline_css', "color: #A020F0; font-weight: bold;"),
            "tag_css": getattr(self.mw, 'tag_css', "color: #808080; font-style: italic;"),
            "show_multiple_spaces_as_dots": getattr(self.mw, 'show_multiple_spaces_as_dots', True),
            "space_dot_color_hex": getattr(self.mw, 'space_dot_color_hex', "#BBBBBB"),
            "preview_wrap_lines": getattr(self.mw, 'preview_wrap_lines', True),
            "editors_wrap_lines": getattr(self.mw, 'editors_wrap_lines', False),
            "default_tag_mappings": dict(self.initial_default_tag_mappings),
            "bracket_tag_color_hex": getattr(self.mw, 'bracket_tag_color_hex', "#FF8C00"),
            "search_history": [],
            "game_dialog_max_width_pixels": getattr(self.mw, 'GAME_DIALOG_MAX_WIDTH_PIXELS', DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS),
            "line_width_warning_threshold_pixels": getattr(self.mw, 'LINE_WIDTH_WARNING_THRESHOLD_PIXELS', DEFAULT_LINE_WIDTH_WARNING_THRESHOLD),
            "last_selected_block_index": -1,
            "last_selected_string_index": -1,
            "last_cursor_position_in_edited": 0,
            "last_edited_text_edit_scroll_value_v": 0,
            "last_edited_text_edit_scroll_value_h": 0,
            "last_preview_text_edit_scroll_value_v": 0,
            "last_original_text_edit_scroll_value_v": 0,
            "last_original_text_edit_scroll_value_h": 0,
            "font_size": default_font_size,
            "window_was_maximized": False, 
            "window_normal_geometry": None,
            "block_color_markers": {}
        }

        settings_data = {}
        self.mw.block_color_markers = {} # Initialize here before loop
        self.mw.search_history_to_save = [] # Initialize here before loop

        temp_original_file_path = None
        temp_edited_file_path = None

        for key, value in default_settings_values.items():
            setattr(self.mw, key, value)
        log_debug(f"SettingsManager: Applied all default values. self.mw.current_font_size is now {self.mw.current_font_size} (from defaults)")


        if not os.path.exists(self.settings_file_path):
            log_debug(f"Settings file '{self.settings_file_path}' not found. Using default values already set.")
            setattr(self.mw, "original_file_path", None)
            setattr(self.mw, "edited_file_path", None)
            self.mw.window_geometry_to_restore = None 
            self.mw.window_was_maximized_at_save = False 
        else:
            try:
                with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                    settings_data = json.load(f)
                log_debug(f"SettingsManager: Successfully parsed settings.json. Content keys: {list(settings_data.keys())}")

                temp_original_file_path = settings_data.get("original_file_path")
                temp_edited_file_path = settings_data.get("edited_file_path")
                
                self.mw.window_geometry_to_restore = settings_data.get("window_normal_geometry") 
                self.mw.window_was_maximized_at_save = settings_data.get("window_was_maximized", False) 

                try:
                    if self.mw.main_splitter and "main_splitter_state" in settings_data: self.mw.main_splitter.restoreState(QByteArray(base64.b64decode(settings_data["main_splitter_state"])))
                    if self.mw.right_splitter and "right_splitter_state" in settings_data: self.mw.right_splitter.restoreState(QByteArray(base64.b64decode(settings_data["right_splitter_state"])))
                    if self.mw.bottom_right_splitter and "bottom_right_splitter_state" in settings_data: self.mw.bottom_right_splitter.restoreState(QByteArray(base64.b64decode(settings_data["bottom_right_splitter_state"])))
                except Exception as e: log_debug(f"WARN: Failed to restore splitter state(s): {e}")

                self.mw.block_names = {str(k): v for k, v in settings_data.get("block_names", {}).items()}


                for key_from_defaults, _ in default_settings_values.items():
                    if key_from_defaults in ["window_normal_geometry", "window_was_maximized"]: 
                        continue
                    if key_from_defaults in settings_data:
                        value_from_file = settings_data[key_from_defaults]
                        if key_from_defaults == "font_size":
                            log_debug(f"SettingsManager: Found 'font_size' in settings file: {value_from_file}. Current self.mw.current_font_size: {self.mw.current_font_size}")
                            if isinstance(value_from_file, int) and value_from_file > 0:
                                self.mw.current_font_size = value_from_file
                                log_debug(f"SettingsManager: Set self.mw.current_font_size to {self.mw.current_font_size} from file.")
                            else:
                                log_debug(f"SettingsManager: Invalid 'font_size' in file ({value_from_file}), keeping default: {self.mw.current_font_size}")
                        elif key_from_defaults == "block_color_markers":
                            if isinstance(value_from_file, dict):
                                self.mw.block_color_markers = {k: set(v) for k, v in value_from_file.items() if isinstance(v, list)}
                            else:
                                self.mw.block_color_markers = {}
                        else:
                            setattr(self.mw, key_from_defaults, value_from_file)


                setattr(self.mw, "original_file_path", temp_original_file_path)
                setattr(self.mw, "edited_file_path", temp_edited_file_path)


                lw_threshold_key = "line_width_warning_threshold_pixels"
                if lw_threshold_key in settings_data:
                    val = settings_data[lw_threshold_key]
                    if isinstance(val, int):
                         self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = val

                log_debug(f"SettingsManager: Final MainWindow.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = {self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS}")

                loaded_search_history = settings_data.get("search_history", [])
                if isinstance(loaded_search_history, list):
                    self.mw.search_history_to_save = loaded_search_history
                else: self.mw.search_history_to_save = []

                # Old problem dictionaries are no longer loaded
                # self.mw.critical_problem_lines_per_block = {}
                # self.mw.warning_problem_lines_per_block = {}
                # self.mw.width_exceeded_lines_per_block = {}
                # self.mw.short_lines_per_block = {}


            except json.JSONDecodeError as e:
                log_debug(f"ERROR reading or parsing settings file '{self.settings_file_path}': {e}. Using ALL default values set initially.")
                self.mw.window_geometry_to_restore = None
                self.mw.window_was_maximized_at_save = False
            except Exception as e:
                log_debug(f"UNEXPECTED ERROR while processing settings file '{self.settings_file_path}': {e}. Using ALL default values set initially.")
                self.mw.window_geometry_to_restore = None
                self.mw.window_was_maximized_at_save = False


        log_debug(f"SettingsManager: After potential load from file, self.mw.current_font_size is {self.mw.current_font_size}")
        self.mw.apply_font_size()


        log_debug(f"Settings loaded. Last block: {getattr(self.mw, 'last_selected_block_index', -1)}, string: {getattr(self.mw, 'last_selected_string_index', -1)}")
        log_debug(f"Settings loaded. Original path from mw: '{getattr(self.mw, 'original_file_path', None)}', Edited path from mw: '{getattr(self.mw, 'edited_file_path', None)}'")

        self.mw._apply_text_wrap_settings()
        self.mw._reconfigure_all_highlighters()

        self.mw.initial_load_path = getattr(self.mw, 'original_file_path', None)
        self.mw.initial_edited_load_path = getattr(self.mw, 'edited_file_path', None)

        if not self.mw.initial_load_path and not self.mw.json_path:
            log_debug("SettingsManager: No initial_load_path from settings and no current json_path, ensuring UI is cleared.")
            if hasattr(self.mw, 'ui_updater'):
                self.mw.ui_updater.populate_blocks() 
                self.mw.ui_updater.populate_strings_for_block(-1)

        log_debug("<-- SettingsManager: load_settings finished")

    def save_settings(self):
        log_debug(f"--> SettingsManager: save_settings to {self.settings_file_path}")
        settings_data = {}
        keys_to_save = [
            "default_tag_mappings", "block_names", "newline_display_symbol", "newline_css",
            "tag_css", "show_multiple_spaces_as_dots", "space_dot_color_hex",
            "preview_wrap_lines", "editors_wrap_lines", "bracket_tag_color_hex",
            "game_dialog_max_width_pixels", "line_width_warning_threshold_pixels",
            "search_history",
            "last_selected_block_index", "last_selected_string_index",
            "last_cursor_position_in_edited",
            "last_edited_text_edit_scroll_value_v", "last_edited_text_edit_scroll_value_h",
            "last_preview_text_edit_scroll_value_v",
            "last_original_text_edit_scroll_value_v", "last_original_text_edit_scroll_value_h",
            "font_size", "block_color_markers"
        ]

        for key in keys_to_save:
            if key == "search_history":
                if hasattr(self.mw, 'search_history_to_save'):
                    settings_data[key] = self.mw.search_history_to_save
            elif key == "font_size":
                 settings_data[key] = getattr(self.mw, 'current_font_size', QFont().pointSize() if QFont().pointSize() > 0 else 10)
                 log_debug(f"SettingsManager: Saving font_size: {settings_data[key]} (from self.mw.current_font_size: {self.mw.current_font_size})")
            elif key == "block_color_markers":
                if hasattr(self.mw, 'block_color_markers'):
                     settings_data[key] = {k: list(v) for k, v in self.mw.block_color_markers.items()}
            elif hasattr(self.mw, key):
                settings_data[key] = getattr(self.mw, key)

        if hasattr(self.mw, 'json_path'):
            settings_data["original_file_path"] = self.mw.json_path
        else:
            settings_data["original_file_path"] = None

        if hasattr(self.mw, 'edited_json_path'):
            settings_data["edited_file_path"] = self.mw.edited_json_path
        else:
            settings_data["edited_file_path"] = None

        log_debug(f"Saving paths: original_file_path='{settings_data.get('original_file_path')}', edited_file_path='{settings_data.get('edited_file_path')}'")

        settings_data["window_was_maximized"] = self.mw.window_was_maximized_on_close
        if self.mw.window_normal_geometry_on_close:
            geom = self.mw.window_normal_geometry_on_close
            settings_data["window_normal_geometry"] = {"x": geom.x(), "y": geom.y(), "width": geom.width(), "height": geom.height()}
        else: 
            geom = self.mw.geometry()
            settings_data["window_normal_geometry"] = {"x": geom.x(), "y": geom.y(), "width": geom.width(), "height": geom.height()}


        try:
            if self.mw.main_splitter: settings_data["main_splitter_state"] = base64.b64encode(self.mw.main_splitter.saveState().data()).decode('ascii')
            if self.mw.right_splitter: settings_data["right_splitter_state"] = base64.b64encode(self.mw.right_splitter.saveState().data()).decode('ascii')
            if self.mw.bottom_right_splitter: settings_data["bottom_right_splitter_state"] = base64.b64encode(self.mw.bottom_right_splitter.saveState().data()).decode('ascii')
        except Exception as e: log_debug(f"WARN: Failed to save splitter state(s): {e}")

        # Old problem dictionaries are no longer saved
        # if not self.mw.unsaved_changes:
        #     settings_data["critical_problem_lines_per_block"] = {k: list(v) for k, v in self.mw.critical_problem_lines_per_block.items() if v}
        #     # ... and so on for other old problem dicts
        # else:
        #     log_debug("Not saving problem line data dictionaries because unsaved_changes is True.")

        try:
            with open(self.settings_file_path, 'w', encoding='utf-8') as f: json.dump(settings_data, f, indent=4, ensure_ascii=False)
        except Exception as e: log_debug(f"ERROR saving settings: {e}")
        log_debug("<-- SettingsManager: save_settings finished")