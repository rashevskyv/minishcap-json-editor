import os
import re
from typing import Any, Tuple, Dict, List, Set, Optional

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, convert_spaces_to_dots_for_display

from .config import (
    PROBLEM_DEFINITIONS,
    PROBLEM_TAG_WARNING,
    PROBLEM_WIDTH_EXCEEDED,
    PROBLEM_SHORT_LINE,
    PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL,
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY,
    PROBLEM_SINGLE_WORD_SUBLINE
)
from .tag_manager import TagManager
from .problem_analyzer import ProblemAnalyzer
from .text_fixer import TextFixer
from .tag_logic import process_segment_tags_aggressively_zww

class ProblemIDs:
    PROBLEM_TAG_WARNING = PROBLEM_TAG_WARNING
    PROBLEM_WIDTH_EXCEEDED = PROBLEM_WIDTH_EXCEEDED
    PROBLEM_SHORT_LINE = PROBLEM_SHORT_LINE
    PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL = PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY
    PROBLEM_SINGLE_WORD_SUBLINE = PROBLEM_SINGLE_WORD_SUBLINE

class GameRules(BaseGameRules):
    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.problem_definitions_cache = PROBLEM_DEFINITIONS
        self.tag_manager = TagManager(main_window_ref)
        self.problem_analyzer = ProblemAnalyzer(main_window_ref, self.tag_manager,
                                                self.problem_definitions_cache, ProblemIDs)
        self.text_fixer = TextFixer(main_window_ref, self.tag_manager, self.problem_analyzer)

    def load_data_from_json_obj(self, file_content: Any) -> Tuple[list, dict]:
        log_debug(f"Wind Waker Plugin: Starting load_data_from_json_obj. Input type: {type(file_content)}")
        if not isinstance(file_content, str):
            log_debug(f"Wind Waker Plugin: Expected file content as a string, but got {type(file_content)}")
            return [], {}

        log_debug(f"Wind Waker Plugin: File content (first 200 chars): {file_content[:200]}")

        strings = re.split(r'\{END\}\r?\n', file_content)
        log_debug(f"Wind Waker Plugin: Split by '{{END}}' resulted in {len(strings)} segments.")

        if len(strings) <= 1:
            log_debug("Wind Waker Plugin: WARNING - separator '{END}' not found or file is empty.")

        if strings and (not strings[-1] or strings[-1].isspace()):
            log_debug(f"Wind Waker Plugin: Popping last empty segment. Original last segment: '{strings[-1]}'")
            strings.pop()
            
        processed_strings = [s.strip().replace('\r\n', '\n').replace('\r', '\n') for s in strings]
        log_debug(f"Wind Waker Plugin: After processing, {len(processed_strings)} strings remain.")

        data_for_app = [processed_strings]
        
        block_name = "Block 0"
        if self.mw and self.mw.json_path:
            block_name = os.path.basename(self.mw.json_path)
            
        block_names = {"0": block_name}
        
        log_debug(f"Wind Waker Plugin: Loaded {len(processed_strings)} strings from TXT file into one block named '{block_name}'.")
        
        if not processed_strings:
            log_debug("Wind Waker Plugin: CRITICAL - No strings were processed. Returning empty data.")

        return data_for_app, block_names

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if not data or not isinstance(data[0], list):
            log_debug(f"Wind Waker Plugin: Save data is in unexpected format. Expected list of lists.")
            return ""

        strings_to_save = data[0]
        
        content_parts = []
        for s in strings_to_save:
            content_parts.append(s + "{END}\n")
        
        content = "\n".join(content_parts)
        
        if content:
            content += "\n"
            
        return content

    def get_display_name(self) -> str:
        return "Zelda: The Wind Waker"

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        return self.problem_definitions_cache

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, Any]]:
        return self.tag_manager.get_syntax_highlighting_rules()
        
    def get_legitimate_tags(self) -> Set[str]:
        return self.tag_manager.get_legitimate_tags()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return self.tag_manager.is_tag_legitimate(tag_to_check)

    def analyze_subline(self, text: str, next_text: Optional[str], subline_number_in_data_string: int, qtextblock_number_in_editor: int, is_last_subline_in_data_string: bool, editor_font_map: dict, editor_line_width_threshold: int, full_data_string_text_for_logical_check: str, is_target_for_debug: bool = False) -> set:
        return self.problem_analyzer.analyze_subline(
            text=text,
            next_text=next_text,
            subline_number_in_data_string=subline_number_in_data_string,
            qtextblock_number_in_editor=qtextblock_number_in_editor,
            is_last_subline_in_data_string=is_last_subline_in_data_string,
            editor_font_map=editor_font_map,
            editor_line_width_threshold=editor_line_width_threshold,
            full_data_string_text_for_logical_check=full_data_string_text_for_logical_check,
            is_target_for_debug=is_target_for_debug
        )

    def autofix_data_string(self, data_string: str, editor_font_map: dict, editor_line_width_threshold: int) -> Tuple[str, bool]:
        return self.text_fixer.autofix_data_string(
            data_string=data_string,
            editor_font_map=editor_font_map,
            editor_line_width_threshold=editor_line_width_threshold
        )

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str, editor_player_tag_const: str) -> Tuple[str, str, str]:
        return process_segment_tags_aggressively_zww(
            segment_to_insert=segment_to_insert,
            original_text_for_tags=original_text_for_tags,
            editor_player_tag_const=editor_player_tag_const
        )

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        return calculate_string_width(text, font_map, default_char_width)
        
    def get_short_problem_name(self, problem_id: str) -> str:
        if problem_id == PROBLEM_WIDTH_EXCEEDED: return "Width"
        if problem_id == PROBLEM_SHORT_LINE: return "Short"
        if problem_id == PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL: return "EmptyOddL"
        if problem_id == PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: return "EmptyOddD"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE: return "1Word"
        return super().get_short_problem_name(problem_id)
        
    def get_text_representation_for_preview(self, data_string: str) -> str:
        newline_symbol = getattr(self.mw, "newline_display_symbol", "↵")
        processed_string = str(data_string).replace('\n', newline_symbol)
        return convert_spaces_to_dots_for_display(processed_string, self.mw.show_multiple_spaces_as_dots)

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        return str(data_string_subline)
        
    def convert_editor_text_to_data(self, text: str) -> str:
        return text
        
    def get_enter_char(self) -> str: return '\n'
    def get_shift_enter_char(self) -> str: return '\n'
    def get_ctrl_enter_char(self) -> str: return '\n'