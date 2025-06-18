from typing import Dict, Any, Tuple, Set, Optional, List
from collections import OrderedDict
from PyQt5.QtGui import QTextCharFormat, QColor, QFont
from plugins.base_game_rules import BaseGameRules
from .config import (PROBLEM_DEFINITIONS, DEFAULT_TAG_MAPPINGS_POKEMON_FR, 
                     P_NEWLINE_MARKER, L_NEWLINE_MARKER, P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER)
from .tag_manager import TagManager
from .problem_analyzer import ProblemAnalyzer
from utils.logging_utils import log_debug
from utils.utils import convert_spaces_to_dots_for_display
import re

class GameRules(BaseGameRules):
    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.original_keys = []
        
        self.tag_manager = TagManager(main_window_ref)
        self.problem_analyzer = ProblemAnalyzer(main_window_ref, self.tag_manager, PROBLEM_DEFINITIONS, {})

    def load_data_from_json_obj(self, json_data: Any) -> Tuple[list, dict]:
        if not isinstance(json_data, dict):
            return [], {}
        
        self.original_keys = []
        app_data = []
        block_names = {}
        
        sorted_blocks = sorted(json_data.items())

        for i, (block_name, string_obj) in enumerate(sorted_blocks):
            if isinstance(string_obj, dict):
                string_list = list(string_obj.values())
                key_list = list(string_obj.keys())
                
                app_data.append(string_list)
                self.original_keys.append(key_list)
                block_names[str(i)] = block_name
            else:
                log_debug(f"[PokemonFR Plugin] Skipping block '{block_name}' because its value is not a dictionary.")
        
        return app_data, block_names

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if not self.original_keys or len(self.original_keys) != len(data):
            raise ValueError("Original keys for Pokemon data are missing or mismatched. Cannot save.")
            
        output_json = OrderedDict()
        for i, block_data in enumerate(data):
            block_name = block_names.get(str(i))
            if not block_name or i >= len(self.original_keys):
                log_debug(f"[PokemonFR Plugin] Skipping block index {i} during save due to missing name or keys.")
                continue 
            
            keys_for_block = self.original_keys[i]
            if len(keys_for_block) != len(block_data):
                raise ValueError(f"Mismatch in number of strings for block '{block_name}'. Expected {len(keys_for_block)}, got {len(block_data)}. Cannot save.")

            string_obj = OrderedDict()
            for j, string_value in enumerate(block_data):
                key = keys_for_block[j]
                string_obj[key] = string_value
            
            output_json[block_name] = string_obj
            
        return output_json
        
    def get_text_representation_for_preview(self, data_string: str) -> str:
        newline_symbol = getattr(self.mw, "newline_display_symbol", "↵")
        
        processed_string = str(data_string).replace('\\p', P_NEWLINE_MARKER)
        processed_string = processed_string.replace('\\l', L_NEWLINE_MARKER)
        processed_string = processed_string.replace('\\n', newline_symbol)
        
        return convert_spaces_to_dots_for_display(processed_string, self.mw.show_multiple_spaces_as_dots)

    def get_enter_char(self) -> str:
        return '\n'

    def get_shift_enter_char(self) -> str:
        return f"{P_VISUAL_EDITOR_MARKER}\n"

    def get_ctrl_enter_char(self) -> str:
        return f"{L_VISUAL_EDITOR_MARKER}\n"

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        processed = str(data_string_subline).replace('\\p', f"{P_VISUAL_EDITOR_MARKER}\n")
        processed = processed.replace('\\l', f"{L_VISUAL_EDITOR_MARKER}\n")
        processed = processed.replace('\\n', '\n')
        return processed

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        return self.tag_manager.get_syntax_highlighting_rules()

    def get_display_name(self) -> str:
        return "Pokémon FireRed/LeafGreen"

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        return PROBLEM_DEFINITIONS

    def get_default_tag_mappings(self) -> Dict[str, str]:
        return DEFAULT_TAG_MAPPINGS_POKEMON_FR

    def analyze_subline(self, *args, **kwargs) -> Set[str]:
        return self.problem_analyzer.analyze_subline(*args, **kwargs)

    def autofix_data_string(self, data_string: str, *args, **kwargs) -> Tuple[str, bool]:
        return data_string, False

    def process_pasted_segment(self, segment_to_insert: str, *args, **kwargs) -> Tuple[str, str, str]:
        return segment_to_insert, "OK", ""