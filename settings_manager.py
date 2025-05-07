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
                # Після перезавантаження мапінгів, можливо, варто скинути старі проблеми,
                # оскільки критерії могли змінитися. Або залишити це на розсуд Rescan.
                # self.mw.critical_problem_lines_per_block.clear()
                # self.mw.warning_problem_lines_per_block.clear()
                # self.mw.ui_updater.clear_all_problem_block_highlights_and_text()
                return True
            else:
                log_debug("WARN: 'default_tag_mappings' in settings is not a dictionary or missing. Using previous values.")
                return False
        except Exception as e:
            log_debug(f"ERROR reading settings file '{self.settings_file_path}' for tag mappings: {e}.")
            return False

    def load_settings(self):
        log_debug(f"--> SettingsManager: load_settings from {self.settings_file_path}")

        default_settings_values = {
            "newline_display_symbol": getattr(self.mw, 'newline_display_symbol', "↵"),
            "newline_css": getattr(self.mw, 'newline_css', "color: #A020F0; font-weight: bold;"),
            "tag_css": getattr(self.mw, 'tag_css', "color: #808080; font-style: italic;"),
            "show_multiple_spaces_as_dots": getattr(self.mw, 'show_multiple_spaces_as_dots', True),
            "space_dot_color_hex": getattr(self.mw, 'space_dot_color_hex', "#BBBBBB"),
            "preview_wrap_lines": getattr(self.mw, 'preview_wrap_lines', True),
            "editors_wrap_lines": getattr(self.mw, 'editors_wrap_lines', False),
            "default_tag_mappings": dict(self.initial_default_tag_mappings),
            "bracket_tag_color_hex": getattr(self.mw, 'bracket_tag_color_hex', "#FFA500"),
            # За замовчуванням порожні словники для нових типів проблем
            "critical_problem_lines_per_block": {}, 
            "warning_problem_lines_per_block": {}
        }

        settings_data = {}
        if not os.path.exists(self.settings_file_path):
            log_debug(f"Settings file '{self.settings_file_path}' not found. Using default values.")
            for key, value in default_settings_values.items():
                setattr(self.mw, key, value)
        else:
            try:
                with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                    settings_data = json.load(f)

                # ... (код для геометрії, сплітерів, назв блоків, стилів без змін) ...
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
                self.mw.newline_display_symbol = settings_data.get("newline_display_symbol", default_settings_values["newline_display_symbol"])
                self.mw.newline_css = settings_data.get("newline_css", default_settings_values["newline_css"])
                self.mw.tag_css = settings_data.get("tag_css", default_settings_values["tag_css"])
                self.mw.show_multiple_spaces_as_dots = settings_data.get("show_multiple_spaces_as_dots", default_settings_values["show_multiple_spaces_as_dots"])
                self.mw.space_dot_color_hex = settings_data.get("space_dot_color_hex", default_settings_values["space_dot_color_hex"])
                self.mw.preview_wrap_lines = settings_data.get("preview_wrap_lines", default_settings_values["preview_wrap_lines"])
                self.mw.editors_wrap_lines = settings_data.get("editors_wrap_lines", default_settings_values["editors_wrap_lines"])
                self.mw.bracket_tag_color_hex = settings_data.get("bracket_tag_color_hex", default_settings_values["bracket_tag_color_hex"])
                
                loaded_mappings = settings_data.get("default_tag_mappings", default_settings_values["default_tag_mappings"])
                if isinstance(loaded_mappings, dict): self.mw.default_tag_mappings = loaded_mappings
                else: self.mw.default_tag_mappings = default_settings_values["default_tag_mappings"]
                
                # Завантаження нових словників проблем
                crit_problems = settings_data.get("critical_problem_lines_per_block", default_settings_values["critical_problem_lines_per_block"])
                if isinstance(crit_problems, dict):
                    self.mw.critical_problem_lines_per_block = {k: set(v) for k, v in crit_problems.items() if isinstance(v, list)}
                else: self.mw.critical_problem_lines_per_block = {}

                warn_problems = settings_data.get("warning_problem_lines_per_block", default_settings_values["warning_problem_lines_per_block"])
                if isinstance(warn_problems, dict):
                    self.mw.warning_problem_lines_per_block = {k: set(v) for k, v in warn_problems.items() if isinstance(v, list)}
                else: self.mw.warning_problem_lines_per_block = {}
            
            except Exception as e:
                log_debug(f"ERROR reading settings file '{self.settings_file_path}': {e}. Using all default values.")
                for key, value in default_settings_values.items(): setattr(self.mw, key, value)
        
        log_debug(f"Loaded settings. Critical problems: {len(self.mw.critical_problem_lines_per_block)}, Warning problems: {len(self.mw.warning_problem_lines_per_block)}")

        self.mw._apply_text_wrap_settings()
        self.mw._reconfigure_all_highlighters()

        last_original_file = settings_data.get("original_file_path")
        last_edited_file = settings_data.get("edited_file_path")
        
        if last_original_file and os.path.exists(last_original_file):
            effective_edited_path = last_edited_file if last_edited_file and os.path.exists(last_edited_file) else None
            self.mw.load_all_data_for_path(last_original_file,
                                           manually_set_edited_path=effective_edited_path,
                                           is_initial_load_from_settings=True) # Це запустить populate_blocks і т.д.
        elif last_original_file:
            log_debug(f"Last file '{last_original_file}' not found.")
            if not self.mw.json_path: self.mw.ui_updater.populate_blocks(); self.mw.ui_updater.populate_strings_for_block(-1)
        elif not self.mw.json_path: self.mw.ui_updater.populate_blocks(); self.mw.ui_updater.populate_strings_for_block(-1)

        log_debug("<-- SettingsManager: load_settings finished")

    def save_settings(self):
        log_debug(f"--> SettingsManager: save_settings to {self.settings_file_path}")
        
        current_file_settings = {}
        if os.path.exists(self.settings_file_path):
            try:
                with open(self.settings_file_path, 'r', encoding='utf-8') as f: current_file_settings = json.load(f)
            except Exception as e: log_debug(f"WARN: Could not read existing settings file before saving: {e}.")

        settings_data = {}
        if "default_tag_mappings" in current_file_settings: # Зберігаємо default_tag_mappings з файлу
            settings_data["default_tag_mappings"] = current_file_settings["default_tag_mappings"]
        
        # ... (код для збереження геометрії, сплітерів, назв блоків, стилів без змін) ...
        settings_data["block_names"] = {str(k): v for k, v in self.mw.block_names.items()}
        geom = self.mw.geometry(); settings_data["window_geometry"] = {"x": geom.x(), "y": geom.y(), "width": geom.width(), "height": geom.height()}
        settings_data["newline_display_symbol"] = self.mw.newline_display_symbol; settings_data["newline_css"] = self.mw.newline_css
        settings_data["tag_css"] = self.mw.tag_css; settings_data["show_multiple_spaces_as_dots"] = self.mw.show_multiple_spaces_as_dots
        settings_data["space_dot_color_hex"] = self.mw.space_dot_color_hex; settings_data["preview_wrap_lines"] = self.mw.preview_wrap_lines
        settings_data["editors_wrap_lines"] = self.mw.editors_wrap_lines; settings_data["bracket_tag_color_hex"] = self.mw.bracket_tag_color_hex
        
        # Зберігаємо нові словники проблем
        crit_to_save = {k: list(v) for k, v in self.mw.critical_problem_lines_per_block.items()}
        settings_data["critical_problem_lines_per_block"] = crit_to_save
        warn_to_save = {k: list(v) for k, v in self.mw.warning_problem_lines_per_block.items()}
        settings_data["warning_problem_lines_per_block"] = warn_to_save
        
        try: # ... (збереження стану сплітерів без змін) ...
            if self.mw.main_splitter: settings_data["main_splitter_state"] = base64.b64encode(self.mw.main_splitter.saveState().data()).decode('ascii')
            if self.mw.right_splitter: settings_data["right_splitter_state"] = base64.b64encode(self.mw.right_splitter.saveState().data()).decode('ascii')
            if self.mw.bottom_right_splitter: settings_data["bottom_right_splitter_state"] = base64.b64encode(self.mw.bottom_right_splitter.saveState().data()).decode('ascii')
        except Exception as e: log_debug(f"WARN: Failed to save splitter state(s): {e}")

        if self.mw.json_path: settings_data["original_file_path"] = self.mw.json_path
        if self.mw.edited_json_path: settings_data["edited_file_path"] = self.mw.edited_json_path
            
        try:
            with open(self.settings_file_path, 'w', encoding='utf-8') as f: json.dump(settings_data, f, indent=4, ensure_ascii=False)
        except Exception as e: log_debug(f"ERROR saving settings: {e}")
        log_debug("<-- SettingsManager: save_settings finished")