# --- START OF FILE plugins/base_game_rules.py ---
from typing import List, Tuple, Dict, Optional, Any, Set
from PyQt5.QtGui import QTextCharFormat
import json

class BaseGameRules:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref

    def load_data_from_json_obj(self, json_data: Any) -> Tuple[list, dict]:
        if isinstance(json_data, list):
            return json_data, {}
        return [], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        return data
    
    def get_enter_char(self) -> str:
        return '\n'
        
    def get_shift_enter_char(self) -> str:
        return '\n'

    def get_ctrl_enter_char(self) -> str:
        return '\n'

    def convert_editor_text_to_data(self, text: str) -> str:
        return text

    def get_display_name(self) -> str:
        if self.mw and hasattr(self.mw, 'display_name'):
            return self.mw.display_name
        return "Base Game (No Plugin)"

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        return {}

    def analyze_subline(self,
                        text: str,
                        next_text: Optional[str],
                        subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int,
                        is_last_subline_in_data_string: bool,
                        editor_font_map: dict,
                        editor_line_width_threshold: int,
                        full_data_string_text_for_logical_check: str,
                        is_target_for_debug: bool = False) -> Set[str]:
        return set()

    def autofix_data_string(self,
                            data_string: str,
                            editor_font_map: dict,
                            editor_line_width_threshold: int) -> Tuple[str, bool]:
        return data_string, False

    def process_pasted_segment(self,
                               segment_to_insert: str,
                               original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return segment_to_insert, "OK", ""
        
    def get_base_game_rules_class(self):
        return BaseGameRules

    def get_default_tag_mappings(self) -> Dict[str, str]:
        return {}
    
    def get_tag_checker_handler(self) -> Optional[Any]:
        return None
        
    def get_short_problem_name(self, problem_id: str) -> str:
        problem_definitions = self.get_problem_definitions()
        return problem_definitions.get(problem_id, {}).get("name", problem_id)

    def get_plugin_actions(self) -> List[Dict[str, Any]]:
        return []

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        return data_string_subline

    def get_text_representation_for_preview(self, data_string: str) -> str:
        return data_string.replace('\n', getattr(self.mw, "newline_display_symbol", "↵")) if self.mw else data_string.replace('\n', "↵")

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        return []

    def get_legitimate_tags(self) -> Set[str]:
        return set()

    def get_context_menu_actions(self, editor_widget, selected_text: Optional[str]) -> List[Dict[str, Any]]:
        return []

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int) -> Optional[int]:
        return None