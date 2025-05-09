import json
import os
import base64
from PyQt5.QtCore import QByteArray
from PyQt5.QtWidgets import QMessageBox 
from utils import log_debug

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
            "game_dialog_max_width_pixels": getattr(self.mw, 'GAME_DIALOG_MAX_WIDTH_PIXELS', 240),
            "line_width_warning_threshold_pixels": getattr(self.mw, 'LINE_WIDTH_WARNING_THRESHOLD_PIXELS', 175),
        }
        
        settings_data = {}
        self.mw.critical_problem_lines_per_block = {}
        self.mw.warning_problem_lines_per_block = {}
        self.mw.width_exceeded_lines_per_block = {} # Ініціалізація
        self.mw.search_history_to_save = [] 

        if not os.path.exists(self.settings_file_path):
            log_debug(f"Settings file '{self.settings_file_path}' not found. Using default values for core settings.")
            for key, value in default_settings_values.items():
                setattr(self.mw, key, value)
            self.mw.search_history_to_save = default_settings_values["search_history"]
            self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS = default_settings_values["game_dialog_max_width_pixels"]
            self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = default_settings_values["line_width_warning_threshold_pixels"]
        else:
            try:
                with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                    settings_data = json.load(f)
                
                window_geom = settings_data.get("window_geometry")
                if window_geom and isinstance(window_geom, dict) and all(k in window_geom for k in ('x', 'y', 'width', 'height')):
                    try: self.mw.setGeometry(window_geom['x'], window_geom['y'], window_geom['width'], window_geom['height'])
                    except Exception as e: log_debug(f"WARN: Failed to restore window geometry: {e}")
                try:
                    if self.mw.main_splitter and "main_splitter_state" in settings_data: self.mw.main_splitter.restoreState(QByteArray(base64.b64decode(settings_data["main_splitter_state"])))
                    if self.mw.right_splitter and "right_splitter_state" in settings_data: self.mw.right_splitter.restoreState(QByteArray(base64.b64decode(settings_data["right_splitter_state"])))
                    if self.mw.bottom_right_splitter and "bottom_right_splitter_state" in settings_data: self.mw.bottom_right_splitter.restoreState(QByteArray(base64.b64decode(settings_data["bottom_right_splitter_state"])))
                except Exception as e: log_debug(f"WARN: Failed to restore splitter state(s): {e}")
                
                self.mw.block_names = {str(k): v for k, v in settings_data.get("block_names", {}).items()}
                for key, default_value in default_settings_values.items():
                    setattr(self.mw, key, settings_data.get(key, default_value))
                
                self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS = settings_data.get("game_dialog_max_width_pixels", default_settings_values["game_dialog_max_width_pixels"])
                self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = settings_data.get("line_width_warning_threshold_pixels", default_settings_values["line_width_warning_threshold_pixels"])
                
                loaded_search_history = settings_data.get("search_history", [])
                if isinstance(loaded_search_history, list):
                    self.mw.search_history_to_save = loaded_search_history
                    log_debug(f"Loaded search_history from settings: {len(self.mw.search_history_to_save)} items.")
                else:
                    self.mw.search_history_to_save = []
                    log_debug("WARN: 'search_history' in settings is not a list. Using empty list.")


                crit_problems = settings_data.get("critical_problem_lines_per_block")
                if isinstance(crit_problems, dict): 
                    self.mw.critical_problem_lines_per_block = {k: set(v) for k, v in crit_problems.items() if isinstance(v, list)}
                    log_debug(f"Loaded critical_problem_lines_per_block from settings: {len(self.mw.critical_problem_lines_per_block)} entries.")
                else:
                    log_debug(f"No valid critical_problem_lines_per_block in settings or key missing. Initialized empty.")

                warn_problems = settings_data.get("warning_problem_lines_per_block")
                if isinstance(warn_problems, dict):
                    self.mw.warning_problem_lines_per_block = {k: set(v) for k, v in warn_problems.items() if isinstance(v, list)}
                    log_debug(f"Loaded warning_problem_lines_per_block from settings: {len(self.mw.warning_problem_lines_per_block)} entries.")
                else:
                    log_debug(f"No valid warning_problem_lines_per_block in settings or key missing. Initialized empty.")
                
                width_problems = settings_data.get("width_exceeded_lines_per_block") # Завантаження
                if isinstance(width_problems, dict):
                    self.mw.width_exceeded_lines_per_block = {k: set(v) for k, v in width_problems.items() if isinstance(v, list)}
                    log_debug(f"Loaded width_exceeded_lines_per_block from settings: {len(self.mw.width_exceeded_lines_per_block)} entries.")
                else:
                    log_debug(f"No valid width_exceeded_lines_per_block in settings or key missing. Initialized empty.")

            except Exception as e:
                log_debug(f"ERROR reading settings file '{self.settings_file_path}': {e}. Using all default values for core settings.")
                for key, value in default_settings_values.items(): setattr(self.mw, key, value)
                self.mw.critical_problem_lines_per_block = {} 
                self.mw.warning_problem_lines_per_block = {}
                self.mw.width_exceeded_lines_per_block = {}
                self.mw.search_history_to_save = default_settings_values["search_history"]
                self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS = default_settings_values["game_dialog_max_width_pixels"]
                self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = default_settings_values["line_width_warning_threshold_pixels"]
        
        log_debug(f"Settings loaded. Initial critical problems: {len(self.mw.critical_problem_lines_per_block)}, Initial warning problems: {len(self.mw.warning_problem_lines_per_block)}, Initial width problems: {len(self.mw.width_exceeded_lines_per_block)}")
        
        self.mw._apply_text_wrap_settings()
        self.mw._reconfigure_all_highlighters()
        
        last_original_file = settings_data.get("original_file_path")
        last_edited_file = settings_data.get("edited_file_path")
        
        if last_original_file and os.path.exists(last_original_file):
            effective_edited_path = last_edited_file if last_edited_file and os.path.exists(last_edited_file) else None
            self.mw.load_all_data_for_path(last_original_file, manually_set_edited_path=effective_edited_path, is_initial_load_from_settings=True)
            
            # Перевірка необхідності початкового сканування (включно з шириною)
            if not self.mw.critical_problem_lines_per_block and \
               not self.mw.warning_problem_lines_per_block and \
               not self.mw.width_exceeded_lines_per_block and \
               self.mw.data:
                log_debug("SettingsManager: Problem line data (tags & width) was not in settings or empty. Performing initial scan.")
                if hasattr(self.mw, 'app_action_handler') and hasattr(self.mw.app_action_handler, '_perform_initial_silent_scan_all_issues'):
                     self.mw.app_action_handler._perform_initial_silent_scan_all_issues() # Новий метод
                else:
                    log_debug("SettingsManager: _perform_initial_silent_scan_all_issues not found in AppActionHandler. Skipping initial scan.")

        elif last_original_file:
            log_debug(f"Last file '{last_original_file}' not found.")
            if not self.mw.json_path: self.mw.ui_updater.populate_blocks(); self.mw.ui_updater.populate_strings_for_block(-1)
        elif not self.mw.json_path: self.mw.ui_updater.populate_blocks(); self.mw.ui_updater.populate_strings_for_block(-1)
        
        log_debug("<-- SettingsManager: load_settings finished")

    def save_settings(self):
        log_debug(f"--> SettingsManager: save_settings to {self.settings_file_path}")
        settings_data = {} 
        settings_data["default_tag_mappings"] = self.mw.default_tag_mappings
        settings_data["block_names"] = {str(k): v for k, v in self.mw.block_names.items()}
        geom = self.mw.geometry(); settings_data["window_geometry"] = {"x": geom.x(), "y": geom.y(), "width": geom.width(), "height": geom.height()}
        settings_data["newline_display_symbol"] = self.mw.newline_display_symbol; settings_data["newline_css"] = self.mw.newline_css
        settings_data["tag_css"] = self.mw.tag_css; settings_data["show_multiple_spaces_as_dots"] = self.mw.show_multiple_spaces_as_dots
        settings_data["space_dot_color_hex"] = self.mw.space_dot_color_hex; settings_data["preview_wrap_lines"] = self.mw.preview_wrap_lines
        settings_data["editors_wrap_lines"] = self.mw.editors_wrap_lines; settings_data["bracket_tag_color_hex"] = self.mw.bracket_tag_color_hex 
        settings_data["game_dialog_max_width_pixels"] = self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS
        settings_data["line_width_warning_threshold_pixels"] = self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS
        
        if hasattr(self.mw, 'search_history_to_save') and isinstance(self.mw.search_history_to_save, list):
            settings_data["search_history"] = self.mw.search_history_to_save
            log_debug(f"Saving search_history: {len(self.mw.search_history_to_save)} items.")
        else:
            log_debug("No search_history_to_save found or not a list, not saving search history.")


        try: 
            if self.mw.main_splitter: settings_data["main_splitter_state"] = base64.b64encode(self.mw.main_splitter.saveState().data()).decode('ascii')
            if self.mw.right_splitter: settings_data["right_splitter_state"] = base64.b64encode(self.mw.right_splitter.saveState().data()).decode('ascii')
            if self.mw.bottom_right_splitter: settings_data["bottom_right_splitter_state"] = base64.b64encode(self.mw.bottom_right_splitter.saveState().data()).decode('ascii')
        except Exception as e: log_debug(f"WARN: Failed to save splitter state(s): {e}")
        
        if self.mw.json_path: settings_data["original_file_path"] = self.mw.json_path
        if self.mw.edited_json_path: settings_data["edited_file_path"] = self.mw.edited_json_path

        if not self.mw.unsaved_changes:
            crit_to_save = {k: list(v) for k, v in self.mw.critical_problem_lines_per_block.items() if v} 
            if crit_to_save : settings_data["critical_problem_lines_per_block"] = crit_to_save
            
            warn_to_save = {k: list(v) for k, v in self.mw.warning_problem_lines_per_block.items() if v} 
            if warn_to_save : settings_data["warning_problem_lines_per_block"] = warn_to_save

            width_exceeded_to_save = {k: list(v) for k, v in self.mw.width_exceeded_lines_per_block.items() if v} # Збереження
            if width_exceeded_to_save: settings_data["width_exceeded_lines_per_block"] = width_exceeded_to_save

            log_debug(f"Saving problem line data because unsaved_changes is False. Crit entries: {len(crit_to_save)}, Warn entries: {len(warn_to_save)}, Width entries: {len(width_exceeded_to_save)}")
        else:
            log_debug("Not saving problem line data because unsaved_changes is True.")
            settings_data.pop("critical_problem_lines_per_block", None)
            settings_data.pop("warning_problem_lines_per_block", None)
            settings_data.pop("width_exceeded_lines_per_block", None) # Не зберігаємо, якщо є незбережені зміни

        try:
            with open(self.settings_file_path, 'w', encoding='utf-8') as f: json.dump(settings_data, f, indent=4, ensure_ascii=False)
        except Exception as e: log_debug(f"ERROR saving settings: {e}")
        log_debug("<-- SettingsManager: save_settings finished")