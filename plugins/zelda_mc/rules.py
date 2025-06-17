from PyQt5.QtGui import QColor, QTextCharFormat, QFont
from PyQt5.QtCore import Qt
from typing import Optional, Set, Dict, Any, Tuple, List
import re
import json
import os

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug

from .config import (
    PROBLEM_DEFINITIONS,
    DEFAULT_TAG_MAPPINGS_ZMC,
    PROBLEM_WIDTH_EXCEEDED,
    PROBLEM_SHORT_LINE,
    PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL,
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY,
    PROBLEM_TAG_WARNING,
    PROBLEM_SINGLE_WORD_SUBLINE
)
from .tag_manager import TagManager
from .problem_analyzer import ProblemAnalyzer
from .text_fixer import TextFixer
from .tag_logic import process_segment_tags_aggressively_zmc
from .tag_checker_handler import TagCheckerHandler

class ProblemIDs: 
    PROBLEM_WIDTH_EXCEEDED = PROBLEM_WIDTH_EXCEEDED
    PROBLEM_SHORT_LINE = PROBLEM_SHORT_LINE
    PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL = PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY
    PROBLEM_TAG_WARNING = PROBLEM_TAG_WARNING
    PROBLEM_SINGLE_WORD_SUBLINE = "ZMC_SINGLE_WORD_SUBLINE"

class GameRules(BaseGameRules):

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.problem_definitions_cache = PROBLEM_DEFINITIONS
        self.tag_manager = TagManager(main_window_ref)
        self.problem_analyzer = ProblemAnalyzer(main_window_ref, self.tag_manager,
                                                self.problem_definitions_cache, ProblemIDs)
        self.text_fixer = TextFixer(main_window_ref, self.tag_manager, self.problem_analyzer)

    def get_display_name(self) -> str:
        return "The Legend of Zelda: The Minish Cap"

    def get_default_tag_mappings(self) -> Dict[str, str]:
        mappings = dict(DEFAULT_TAG_MAPPINGS_ZMC)
        if self.mw and hasattr(self.mw, 'EDITOR_PLAYER_TAG') and hasattr(self.mw, 'ORIGINAL_PLAYER_TAG'):
            mappings[self.mw.EDITOR_PLAYER_TAG] = self.mw.ORIGINAL_PLAYER_TAG
        return mappings

    def get_tag_checker_handler(self) -> Optional[TagCheckerHandler]:
        return TagCheckerHandler(self.mw)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        return self.tag_manager.get_syntax_highlighting_rules()

    def get_legitimate_tags(self) -> Set[str]:
        return self.tag_manager.get_legitimate_tags()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return self.tag_manager.is_tag_legitimate(tag_to_check)

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        return self.problem_definitions_cache

    def get_short_problem_name(self, problem_id: str) -> str:
        if problem_id == PROBLEM_WIDTH_EXCEEDED: return "Width"
        if problem_id == PROBLEM_SHORT_LINE: return "Short"
        if problem_id == PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL: return "EmptyOddL"
        if problem_id == PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: return "EmptyOddD"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE: return "1Word"
        return super().get_short_problem_name(problem_id)

    def get_plugin_actions(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': 'check_tags_mismatch',
                'text': 'Check Tags Mismatch',
                'tooltip': 'Check for tags mismatch between original and translation',
                'shortcut': None, 
                'handler': self.mw.trigger_check_tags_action,
                'toolbar': True,
                'menu': 'Tools'
            }
        ]

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
        return self.problem_analyzer.analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor,
            is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold,
            full_data_string_text_for_logical_check, is_target_for_debug
        )

    def autofix_data_string(self,
                            data_string: str,
                            editor_font_map: dict,
                            editor_line_width_threshold: int) -> Tuple[str, bool]:
        return self.text_fixer.autofix_data_string(
            data_string, editor_font_map, editor_line_width_threshold
        )
    
    def process_pasted_segment(self,
                               segment_to_insert: str,
                               original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return process_segment_tags_aggressively_zmc(
            segment_to_insert,
            original_text_for_tags,
            editor_player_tag_const
        )
    
    def get_base_game_rules_class(self):
        return BaseGameRules