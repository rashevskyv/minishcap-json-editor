from typing import Optional, Set, List, Tuple
import re

from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags

from .config import (PROBLEM_WIDTH_EXCEEDED, PROBLEM_SHORT_LINE, PROBLEM_EMPTY_SUBLINE,
                     PROBLEM_SINGLE_WORD_SUBLINE, PROBLEM_TAG_WARNING)

SENTENCE_END_PUNCTUATION_CHARS = ['.', '!', '?']
TAG_PATTERN = re.compile(r"(\{[^}]*\})")

class ProblemAnalyzer:
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        self.mw = main_window_ref
        self.tag_manager = tag_manager_ref
        self.problem_definitions = problem_definitions_ref
        self.problem_ids = {
            'WIDTH': PROBLEM_WIDTH_EXCEEDED,
            'SHORT': PROBLEM_SHORT_LINE,
            'EMPTY': PROBLEM_EMPTY_SUBLINE,
            'SINGLE': PROBLEM_SINGLE_WORD_SUBLINE,
            'TAG': PROBLEM_TAG_WARNING,
        }

    def _split_by_newlines(self, text: str) -> List[str]:
        return re.split(r'(\\n|\\p|\\l)', text)

    def _get_sublines_from_data_string(self, data_string: str) -> List[str]:
        parts = self._split_by_newlines(data_string)
        sublines = []
        if not parts:
            return []
        
        current_subline = parts[0]
        
        for i in range(1, len(parts), 2):
            tag = parts[i]
            text_after = parts[i+1] if i + 1 < len(parts) else ""
            
            sublines.append(current_subline + tag)
            current_subline = text_after

        if current_subline or not sublines:
            sublines.append(current_subline)

        return [s for s in sublines if s]

    def _ends_with_sentence_punctuation(self, text_no_tags_stripped: str) -> bool:
        if not text_no_tags_stripped:
            return False
        return text_no_tags_stripped[-1] in SENTENCE_END_PUNCTUATION_CHARS

    def _check_short_line(self, current_subline: str, next_subline: str, font_map: dict, threshold: int) -> bool:
        current_subline_no_tags_stripped = remove_all_tags(current_subline).strip()
        if not current_subline_no_tags_stripped or self._ends_with_sentence_punctuation(current_subline_no_tags_stripped):
            return False

        next_subline_no_tags_stripped = remove_all_tags(next_subline).strip()
        if not next_subline_no_tags_stripped:
            return False

        first_word_next = next_subline_no_tags_stripped.split(maxsplit=1)[0]
        if not first_word_next:
            return False

        width_current = calculate_string_width(remove_all_tags(current_subline), font_map)
        width_first_word_next = calculate_string_width(first_word_next, font_map)
        space_width = calculate_string_width(" ", font_map)

        return (threshold - width_current) >= (width_first_word_next + space_width)

    def _check_single_word_subline(self, subline_text: str) -> bool:
        text_no_tags = remove_all_tags(subline_text).strip()
        if not text_no_tags:
            return False
        
        words = text_no_tags.split()
        if len(words) > 1:
            return False
        
        if len(words) == 1:
            word_content_pattern = re.compile(r'[\wа-яА-ЯіїІїЄєґҐ]+') 
            if word_content_pattern.search(words[0]):
                return True
        return False

    def analyze_data_string(self, data_string: str, font_map: dict, threshold: int) -> List[Set[str]]:
        problems_per_subline_idx = []
        if not data_string:
            return [set()]

        sublines = self._get_sublines_from_data_string(data_string)
        is_only_one_subline_in_total = len(sublines) == 1
        
        for i, subline_with_tag in enumerate(sublines):
            found_problems = set()
            text_part = re.sub(r'\\.$', '', subline_with_tag)

            if (text_part.count('{') != text_part.count('}')) or (text_part.count('[') != text_part.count(']')):
                found_problems.add(self.problem_ids['TAG'])
            
            if not remove_all_tags(text_part).strip():
                if i < len(sublines) - 1 or len(sublines) == 1 and not data_string:
                    found_problems.add(self.problem_ids['EMPTY'])
            
            width = calculate_string_width(remove_all_tags(text_part), font_map)
            if width > threshold:
                found_problems.add(self.problem_ids['WIDTH'])
            
            if i + 1 < len(sublines):
                next_subline_with_tag = sublines[i+1]
                if self._check_short_line(text_part, next_subline_with_tag, font_map, threshold):
                    found_problems.add(self.problem_ids['SHORT'])

            if not is_only_one_subline_in_total and self._check_single_word_subline(text_part):
                found_problems.add(self.problem_ids['SINGLE'])

            problems_per_subline_idx.append(found_problems)
            
        return problems_per_subline_idx

    def analyze_subline(self, text: str, **kwargs) -> Set[str]:
        return set()