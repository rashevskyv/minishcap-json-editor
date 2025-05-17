from PyQt5.QtGui import QColor
from typing import Optional, Set, Dict, Any, Tuple

class BaseGameRules:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError("Subclasses must implement get_problem_definitions")

    def analyze_subline(self, 
                        text: str, 
                        next_text: Optional[str], 
                        subline_number_in_data_string: int, 
                        qtextblock_number_in_editor: int,
                        is_last_subline_in_data_string: bool,
                        editor_font_map: dict, 
                        editor_line_width_threshold: int) -> Set[str]:
        raise NotImplementedError("Subclasses must implement analyze_subline")

    def analyze_data_string(self, 
                            data_string: str,
                            original_data_string_for_tags: str, # <--- Новий аргумент
                            editor_player_tag_const: str,       # <--- Новий аргумент
                            editor_font_map: dict, 
                            editor_line_width_threshold: int) -> Set[str]:
        raise NotImplementedError("Subclasses must implement analyze_data_string")

    def autofix_data_string(self, 
                            data_string: str, 
                            editor_font_map: dict, 
                            editor_line_width_threshold: int) -> Tuple[str, bool]:
        raise NotImplementedError("Subclasses must implement autofix_data_string")

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        return data_string_subline

    def get_text_representation_for_preview(self, data_string: str) -> str:
        return data_string.replace('\n', getattr(self.mw, "newline_display_symbol", "↵")) if self.mw else data_string.replace('\n', "↵")