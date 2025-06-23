import json
import os
import base64
from PyQt5.QtCore import QByteArray, QRect
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QFont
from utils.logging_utils import log_debug
from utils.constants import (
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD
)
from plugins.pokemon_fr.config import DEFAULT_AUTOFIX_SETTINGS, DEFAULT_DETECTION_SETTINGS

class SettingsManager:
    def __init__(self, main_window):
        self.mw = main_window
        self.settings_file_path = "settings.json"

    def _get_plugin_config_path(self):
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        if not plugin_name:
            return None
        return os.path.join("plugins", plugin_name, "config.json")

    def load_settings(self):
        log_debug(f"--> SettingsManager: load_settings from {self.settings_file_path}")
        self._load_global_settings()
        self._load_plugin_settings()
        self.load_font_map()

        self.mw.initial_load_path = getattr(self.mw, 'original_file_path', None)
        self.mw.initial_edited_load_path = getattr(self.mw, 'edited_file_path', None)

        if not self.mw.initial_load_path and not self.mw.json_path:
            log_debug("SettingsManager: No initial_load_path, ensuring UI is cleared.")
            if hasattr(self.mw, 'ui_updater'):
                self.mw.ui_updater.populate_blocks()
                self.mw.ui_updater.populate_strings_for_block(-1)

        log_debug("<-- SettingsManager: load_settings finished")

    def _load_global_settings(self):
        default_font_size = QFont().pointSize() if QFont().pointSize() > 0 else 10
        defaults = {
            "font_size": default_font_size,
            "active_game_plugin": "zelda_mc",
            "show_multiple_spaces_as_dots": True,
            "space_dot_color_hex": "#BBBBBB",
            "window_was_maximized": False,
            "window_normal_geometry": None,
            "main_splitter_state": None,
            "right_splitter_state": None,
            "bottom_right_splitter_state": None
        }
        for key, value in defaults.items():
            setattr(self.mw, key, value)
        
        self.mw.current_font_size = defaults['font_size']

        if not os.path.exists(self.settings_file_path):
            return

        try:
            with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)
            for key, value in settings_data.items():
                if hasattr(self.mw, key):
                    setattr(self.mw, key, value)
            self.mw.current_font_size = settings_data.get('font_size', default_font_size)
            self.mw.window_geometry_to_restore = settings_data.get("window_normal_geometry")
            self.mw.window_was_maximized_at_save = settings_data.get("window_was_maximized", False)
            log_debug("Global settings loaded.")
        except Exception as e:
            log_debug(f"Error loading global settings: {e}")

    def _load_plugin_settings(self):
        plugin_config_path = self._get_plugin_config_path()
        defaults = {
            "display_name": "Unknown Plugin", "default_tag_mappings": {}, "block_names": {}, "block_color_markers": {},
            "newline_display_symbol": "↵", "newline_css": "color: #A020F0; font-weight: bold;",
            "tag_css": "color: #808080; font-style: italic;",
            "bracket_tag_color_hex": "#FF8C00",
            "preview_wrap_lines": True, "editors_wrap_lines": False,
            "game_dialog_max_width_pixels": DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
            "line_width_warning_threshold_pixels": DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
            "original_file_path": None, "edited_file_path": None,
            "last_selected_block_index": -1, "last_selected_string_index": -1,
            "last_cursor_position_in_edited": 0, "last_edited_text_edit_scroll_value_v": 0,
            "last_edited_text_edit_scroll_value_h": 0, "last_preview_text_edit_scroll_value_v": 0,
            "last_original_text_edit_scroll_value_v": 0, "last_original_text_edit_scroll_value_h": 0,
            "search_history": [],
            "autofix_enabled": DEFAULT_AUTOFIX_SETTINGS.copy(),
            "detection_enabled": DEFAULT_DETECTION_SETTINGS.copy()
        }
        for key, value in defaults.items():
             if key not in ["block_names", "block_color_markers", "default_tag_mappings"]:
                setattr(self.mw, key, value)
        
        if not hasattr(self.mw, 'block_names'): self.mw.block_names = {}
        if not hasattr(self.mw, 'block_color_markers'): self.mw.block_color_markers = {}
        if not hasattr(self.mw, 'default_tag_mappings'): self.mw.default_tag_mappings = {}
        
        self.mw.search_history_to_save = []

        if not plugin_config_path or not os.path.exists(plugin_config_path):
            log_debug(f"Plugin config not found at '{plugin_config_path}'. Using defaults.")
            return

        try:
            with open(plugin_config_path, 'r', encoding='utf-8') as f:
                plugin_data = json.load(f)

            self.mw.block_names.update({str(k): v for k, v in plugin_data.get("block_names", {}).items()})
            self.mw.block_color_markers.update({k: set(v) for k, v in plugin_data.get("block_color_markers", {}).items()})
            self.mw.default_tag_mappings.update(plugin_data.get("default_tag_mappings", {}))
            
            for key, value in plugin_data.items():
                if key in ["block_names", "block_color_markers", "default_tag_mappings"]:
                    continue
                if hasattr(self.mw, key):
                     setattr(self.mw, key, value)
            
            self.mw.search_history_to_save = plugin_data.get("search_history", [])
            
            loaded_autofix = plugin_data.get("autofix_enabled", {})
            autofix_settings = DEFAULT_AUTOFIX_SETTINGS.copy()
            autofix_settings.update(loaded_autofix)
            self.mw.autofix_enabled = autofix_settings

            loaded_detection = plugin_data.get("detection_enabled", {})
            detection_settings = DEFAULT_DETECTION_SETTINGS.copy()
            detection_settings.update(loaded_detection)
            self.mw.detection_enabled = detection_settings

            log_debug(f"Plugin settings loaded from '{plugin_config_path}'.")
        except Exception as e:
            log_debug(f"Error loading plugin settings from '{plugin_config_path}': {e}")

    def save_settings(self):
        log_debug("Saving all settings...")
        self._save_global_settings()
        self._save_plugin_settings()

    def _save_global_settings(self):
        global_data = {}
        try:
            if os.path.exists(self.settings_file_path):
                with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                    global_data = json.load(f)
        except Exception as e:
             log_debug(f"Could not read existing global settings, will create a new one. Error: {e}")

        global_data.update({
            "font_size": self.mw.current_font_size,
            "active_game_plugin": self.mw.active_game_plugin,
            "show_multiple_spaces_as_dots": self.mw.show_multiple_spaces_as_dots,
            "space_dot_color_hex": self.mw.space_dot_color_hex,
            "window_was_maximized": self.mw.window_was_maximized_on_close
        })

        if self.mw.window_normal_geometry_on_close:
            geom = self.mw.window_normal_geometry_on_close
            global_data["window_normal_geometry"] = {"x": geom.x(), "y": geom.y(), "width": geom.width(), "height": geom.height()}
        
        try:
            if self.mw.main_splitter: global_data["main_splitter_state"] = base64.b64encode(self.mw.main_splitter.saveState().data()).decode('ascii')
            if self.mw.right_splitter: global_data["right_splitter_state"] = base64.b64encode(self.mw.right_splitter.saveState().data()).decode('ascii')
            if self.mw.bottom_right_splitter: global_data["bottom_right_splitter_state"] = base64.b64encode(self.mw.bottom_right_splitter.saveState().data()).decode('ascii')
        except Exception as e: log_debug(f"WARN: Failed to save splitter state(s): {e}")

        try:
            with open(self.settings_file_path, 'w', encoding='utf-8') as f:
                json.dump(global_data, f, indent=4, ensure_ascii=False)
            log_debug("Global settings saved.")
        except Exception as e:
            log_debug(f"ERROR saving global settings: {e}")

    def _save_plugin_settings(self):
        plugin_config_path = self._get_plugin_config_path()
        if not plugin_config_path: return

        plugin_data = {}
        try:
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, 'r', encoding='utf-8') as f:
                    plugin_data = json.load(f)
        except Exception as e:
            log_debug(f"Could not read existing plugin config, will create a new one. Error: {e}")

        plugin_data.update({
            "default_tag_mappings": self.mw.default_tag_mappings,
            "block_names": self.mw.block_names,
            "block_color_markers": {k: list(v) for k, v in self.mw.block_color_markers.items()},
            "newline_display_symbol": self.mw.newline_display_symbol,
            "newline_css": self.mw.newline_css,
            "tag_css": self.mw.tag_css,
            "bracket_tag_color_hex": self.mw.bracket_tag_color_hex,
            "preview_wrap_lines": self.mw.preview_wrap_lines,
            "editors_wrap_lines": self.mw.editors_wrap_lines,
            "game_dialog_max_width_pixels": self.mw.game_dialog_max_width_pixels,
            "line_width_warning_threshold_pixels": self.mw.line_width_warning_threshold_pixels,
            "original_file_path": self.mw.json_path,
            "edited_file_path": self.mw.edited_json_path,
            "last_selected_block_index": self.mw.last_selected_block_index,
            "last_selected_string_index": self.mw.last_selected_string_index,
            "last_cursor_position_in_edited": self.mw.last_cursor_position_in_edited,
            "last_edited_text_edit_scroll_value_v": self.mw.last_edited_text_edit_scroll_value_v,
            "last_edited_text_edit_scroll_value_h": self.mw.last_edited_text_edit_scroll_value_h,
            "last_preview_text_edit_scroll_value_v": self.mw.last_preview_text_edit_scroll_value_v,
            "last_original_text_edit_scroll_value_v": self.mw.last_original_text_edit_scroll_value_v,
            "last_original_text_edit_scroll_value_h": self.mw.last_original_text_edit_scroll_value_h,
            "search_history": self.mw.search_history_to_save,
            "autofix_enabled": self.mw.autofix_enabled,
            "detection_enabled": self.mw.detection_enabled
        })
        
        try:
            with open(plugin_config_path, 'w', encoding='utf-8') as f:
                json.dump(plugin_data, f, indent=4, ensure_ascii=False)
            log_debug(f"Plugin settings saved to '{plugin_config_path}'.")
        except Exception as e:
            log_debug(f"ERROR saving plugin settings to '{plugin_config_path}': {e}")
            QMessageBox.critical(self.mw, "Save Error", f"Could not save plugin configuration to\n{plugin_config_path}")

    def save_block_names(self):
        plugin_config_path = self._get_plugin_config_path()
        if not plugin_config_path:
            log_debug("save_block_names: Cannot save, no plugin config path found.")
            return

        plugin_data = {}
        try:
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, 'r', encoding='utf-8') as f:
                    plugin_data = json.load(f)
        except Exception as e:
            log_debug(f"Could not read existing plugin config at {plugin_config_path} to save block names. A new one will be created. Error: {e}")

        plugin_data["block_names"] = self.mw.block_names
        
        try:
            with open(plugin_config_path, 'w', encoding='utf-8') as f:
                json.dump(plugin_data, f, indent=4, ensure_ascii=False)
            log_debug(f"Block names saved successfully to '{plugin_config_path}'.")
        except Exception as e:
            log_debug(f"ERROR saving block names to '{plugin_config_path}': {e}")
            QMessageBox.critical(self.mw, "Save Error", f"Could not save block names to\n{plugin_config_path}")


    def load_font_map(self):
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        self.mw.font_map = {}
        if not plugin_name:
            return

        font_map_path = os.path.join("plugins", plugin_name, "font_map.json")
        log_debug(f"--> SettingsManager: Attempting to load font_map from plugin path: {font_map_path}")
        
        if not os.path.exists(font_map_path):
            log_debug(f"Font map file not found at '{font_map_path}'. Character width calculations will be disabled.")
            return

        try:
            with open(font_map_path, 'r', encoding='utf-8') as f:
                self.mw.font_map = json.load(f)
            log_debug(f"Successfully loaded font_map. Count: {len(self.mw.font_map)}")
        except Exception as e:
            log_debug(f"ERROR reading font map file '{font_map_path}': {e}.")
            self.mw.font_map = {}