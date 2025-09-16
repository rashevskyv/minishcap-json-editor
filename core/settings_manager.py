import json
import os
import base64
from PyQt5.QtCore import QByteArray, QRect, QTimer
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QFont
from utils.logging_utils import log_debug
from utils.constants import (
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD
)
from plugins.pokemon_fr.config import DEFAULT_AUTOFIX_SETTINGS, DEFAULT_DETECTION_SETTINGS
from core.translation.config import build_default_translation_config, merge_translation_config

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
        self.load_all_font_maps()

        self.mw.initial_load_path = getattr(self.mw, 'original_file_path', None)
        self.mw.initial_edited_load_path = getattr(self.mw, 'edited_file_path', None)
        
        if self.mw.restore_unsaved_on_startup:
            self.load_unsaved_session()

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
            "bottom_right_splitter_state": None,
            "theme": "auto",
            "restore_unsaved_on_startup": False
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
            "string_metadata": {}, "default_font_file": "",
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
            "translation_config": build_default_translation_config(),
            "autofix_enabled": DEFAULT_AUTOFIX_SETTINGS.copy(),
            "detection_enabled": DEFAULT_DETECTION_SETTINGS.copy()
        }
        for key, value in defaults.items():
             if key not in ["block_names", "block_color_markers", "default_tag_mappings", "string_metadata"]:
                setattr(self.mw, key, value)
        # Ensure new style fields exist
        if not hasattr(self.mw, 'tag_color_rgba'): self.mw.tag_color_rgba = "#FF8C00"
        if not hasattr(self.mw, 'tag_bold'): self.mw.tag_bold = True
        if not hasattr(self.mw, 'tag_italic'): self.mw.tag_italic = False
        if not hasattr(self.mw, 'tag_underline'): self.mw.tag_underline = False
        if not hasattr(self.mw, 'newline_color_rgba'): self.mw.newline_color_rgba = "#A020F0"
        if not hasattr(self.mw, 'newline_bold'): self.mw.newline_bold = True
        if not hasattr(self.mw, 'newline_italic'): self.mw.newline_italic = False
        if not hasattr(self.mw, 'newline_underline'): self.mw.newline_underline = False
        
        if not hasattr(self.mw, 'block_names'): self.mw.block_names = {}
        if not hasattr(self.mw, 'block_color_markers'): self.mw.block_color_markers = {}
        if not hasattr(self.mw, 'default_tag_mappings'): self.mw.default_tag_mappings = {}
        if not hasattr(self.mw, 'string_metadata'): self.mw.string_metadata = {}
        
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
            
            loaded_metadata_str_keys = plugin_data.get("string_metadata", {})
            try:
                self.mw.string_metadata = {eval(k): v for k, v in loaded_metadata_str_keys.items()}
            except Exception as e:
                log_debug(f"Error deserializing string_metadata keys: {e}. Metadata will be empty.")
                self.mw.string_metadata = {}
            
            for key, value in plugin_data.items():
                if key in ["block_names", "block_color_markers", "default_tag_mappings", "string_metadata"]:
                    continue
                if hasattr(self.mw, key):
                     setattr(self.mw, key, value)

            # Migrate legacy CSS-based settings to new style fields if needed
            if not hasattr(self.mw, 'tag_color_rgba') or not getattr(self.mw, 'tag_color_rgba', None):
                legacy_color = plugin_data.get('bracket_tag_color_hex') or '#FF8C00'
                self.mw.tag_color_rgba = legacy_color
            if not hasattr(self.mw, 'tag_bold'):
                # legacy: bracket tags were bold by default
                self.mw.tag_bold = True
            if not hasattr(self.mw, 'tag_italic'):
                legacy_tag_css = plugin_data.get('tag_css', '')
                self.mw.tag_italic = 'italic' in legacy_tag_css.lower() if isinstance(legacy_tag_css, str) else False
            if not hasattr(self.mw, 'tag_underline'):
                legacy_tag_css = plugin_data.get('tag_css', '')
                self.mw.tag_underline = 'underline' in legacy_tag_css.lower() if isinstance(legacy_tag_css, str) else False

            if not hasattr(self.mw, 'newline_color_rgba') or not getattr(self.mw, 'newline_color_rgba', None):
                legacy_nl_css = plugin_data.get('newline_css', '')
                # simple color extraction
                nl_color = '#A020F0'
                if isinstance(legacy_nl_css, str) and '#' in legacy_nl_css:
                    try:
                        hexpart = legacy_nl_css.split('#',1)[1].split(';',1)[0].strip()
                        if len(hexpart) >= 6:
                            nl_color = f"#{hexpart[:6]}"
                    except Exception:
                        pass
                self.mw.newline_color_rgba = nl_color
            if not hasattr(self.mw, 'newline_bold'):
                legacy_nl_css = plugin_data.get('newline_css', '')
                self.mw.newline_bold = 'bold' in legacy_nl_css.lower() if isinstance(legacy_nl_css, str) else True
            if not hasattr(self.mw, 'newline_italic'):
                legacy_nl_css = plugin_data.get('newline_css', '')
                self.mw.newline_italic = 'italic' in legacy_nl_css.lower() if isinstance(legacy_nl_css, str) else False
            if not hasattr(self.mw, 'newline_underline'):
                legacy_nl_css = plugin_data.get('newline_css', '')
                self.mw.newline_underline = 'underline' in legacy_nl_css.lower() if isinstance(legacy_nl_css, str) else False
            
            self.mw.search_history_to_save = plugin_data.get("search_history", [])
            
            loaded_autofix = plugin_data.get("autofix_enabled", {})
            autofix_settings = DEFAULT_AUTOFIX_SETTINGS.copy()
            autofix_settings.update(loaded_autofix)
            self.mw.autofix_enabled = autofix_settings

            loaded_detection = plugin_data.get("detection_enabled", {})
            detection_settings = DEFAULT_DETECTION_SETTINGS.copy()
            detection_settings.update(loaded_detection)
            self.mw.detection_enabled = detection_settings

            loaded_translation = plugin_data.get("translation_config", {})
            if isinstance(loaded_translation, dict):
                self.mw.translation_config = merge_translation_config(
                    build_default_translation_config(), loaded_translation
                )
            else:
                self.mw.translation_config = build_default_translation_config()

            log_debug(f"Plugin settings loaded from '{plugin_config_path}'.")
            log_debug(f"  [LOAD STATE] Loaded Block Idx: {self.mw.last_selected_block_index}, String Idx: {self.mw.last_selected_string_index}, Cursor Pos: {self.mw.last_cursor_position_in_edited}")
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
            "window_was_maximized": self.mw.window_was_maximized_on_close,
            "theme": getattr(self.mw, 'theme', 'auto'),
            "restore_unsaved_on_startup": self.mw.restore_unsaved_on_startup
        })

        if self.mw.restore_unsaved_on_startup and self.mw.edited_data:
            serializable_edited_data = {str(k): v for k, v in self.mw.edited_data.items()}
            global_data["unsaved_session_data"] = serializable_edited_data
        elif "unsaved_session_data" in global_data:
            del global_data["unsaved_session_data"]

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

        plugin_data_to_save = {
            "default_tag_mappings": self.mw.default_tag_mappings,
            "block_names": self.mw.block_names,
            "block_color_markers": {k: list(v) for k, v in self.mw.block_color_markers.items()},
            "string_metadata": {str(k): v for k, v in self.mw.string_metadata.items()},
            "default_font_file": self.mw.default_font_file,
            "newline_display_symbol": self.mw.newline_display_symbol,
            # New style fields
            "tag_color_rgba": getattr(self.mw, 'tag_color_rgba', "#FF8C00"),
            "tag_bold": getattr(self.mw, 'tag_bold', True),
            "tag_italic": getattr(self.mw, 'tag_italic', False),
            "tag_underline": getattr(self.mw, 'tag_underline', False),
            "newline_color_rgba": getattr(self.mw, 'newline_color_rgba', "#A020F0"),
            "newline_bold": getattr(self.mw, 'newline_bold', True),
            "newline_italic": getattr(self.mw, 'newline_italic', False),
            "newline_underline": getattr(self.mw, 'newline_underline', False),
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
            "detection_enabled": self.mw.detection_enabled,
            "translation_config": self.mw.translation_config
        }
        
        plugin_data.update(plugin_data_to_save)
        
        log_debug(f"  [SAVE STATE TO DICT] Block Idx: {plugin_data_to_save['last_selected_block_index']}, String Idx: {plugin_data_to_save['last_selected_string_index']}, Cursor Pos: {plugin_data_to_save['last_cursor_position_in_edited']}")

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

    def load_unsaved_session(self):
        log_debug("Attempting to load unsaved session data...")
        if not os.path.exists(self.settings_file_path):
            return
        
        try:
            with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)
            
            if settings_data.get("restore_unsaved_on_startup", False):
                session_data_str_keys = settings_data.get("unsaved_session_data")
                if session_data_str_keys and isinstance(session_data_str_keys, dict):
                    deserialized_data = {eval(k): v for k, v in session_data_str_keys.items()}
                    self.mw.edited_data = deserialized_data
                    self.mw.unsaved_changes = bool(self.mw.edited_data)
                    log_debug(f"Successfully loaded {len(self.mw.edited_data)} unsaved items from session.")
                    if self.mw.unsaved_changes:
                        QTimer.singleShot(0, self.mw.helper.rebuild_unsaved_block_indices)
                        QTimer.singleShot(0, self.mw.ui_updater.update_title)
                        QTimer.singleShot(0, self.mw.ui_updater.populate_blocks)
            else:
                log_debug("Restore unsaved session is disabled in settings. Skipping load.")

        except Exception as e:
            log_debug(f"Error loading unsaved session data: {e}")

    def _parse_new_font_format(self, font_data):
        """Парсить новий формат файлу шрифту і повертає font_map."""
        font_map = {}
        if not isinstance(font_data, dict) or "glyphs" not in font_data:
            log_debug("New font format error: 'glyphs' key not found or data is not a dict.")
            return font_map
        
        for glyph_info in font_data["glyphs"]:
            char = glyph_info.get("char")
            width_info = glyph_info.get("width")
            if char and isinstance(width_info, dict) and "char" in width_info:
                font_map[char] = {"width": width_info["char"]}
        
        return font_map

    def load_all_font_maps(self):
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        self.mw.font_map = {}
        self.mw.all_font_maps = {}

        if not plugin_name:
            log_debug("No active plugin. Character width calculations will use fallback.")
            return

        fonts_dir = os.path.join("plugins", plugin_name, "fonts")
        if not os.path.isdir(fonts_dir):
            log_debug(f"Fonts directory not found at '{fonts_dir}'.")
            return
        
        log_debug(f"--> SettingsManager: Loading all font maps from: {fonts_dir}")
        for filename in os.listdir(fonts_dir):
            if not filename.lower().endswith(".json"):
                continue

            font_map_path = os.path.join(fonts_dir, filename)
            try:
                with open(font_map_path, 'r', encoding='utf-8') as f:
                    raw_font_data = json.load(f)

                if "signature" in raw_font_data and raw_font_data["signature"] == "FFNT":
                    parsed_map = self._parse_new_font_format(raw_font_data)
                else:
                    parsed_map = raw_font_data
                
                self.mw.all_font_maps[filename] = parsed_map
                log_debug(f"  Successfully loaded and parsed font map '{filename}'. Count: {len(parsed_map)}")

            except Exception as e:
                log_debug(f"  ERROR reading or parsing font map file '{filename}': {e}.")

        default_font_filename = getattr(self.mw, 'default_font_file', None)
        if default_font_filename and default_font_filename in self.mw.all_font_maps:
            self.mw.font_map = self.mw.all_font_maps[default_font_filename]
            log_debug(f"Set default font_map to '{default_font_filename}'.")
        elif self.mw.all_font_maps:
            first_font = next(iter(self.mw.all_font_maps))
            self.mw.font_map = self.mw.all_font_maps[first_font]
            log_debug(f"Default font file not found, using first available font as default: '{first_font}'.")
        else:
            log_debug("No font maps loaded for the plugin.")


