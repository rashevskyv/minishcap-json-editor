from typing import Optional, Set, List
import re

from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags

SENTENCE_END_PUNCTUATION_CHARS_PT = ['.', '!', '?']
OPTIONAL_TRAILING_CHARS_PT = ['"', "'"]

ANY_TAG_PATTERN_PT = re.compile(r'[[^]]*]')

def remove_all_tags_pt(text: str) -> str:
    if text is None:
        return ""
    return ANY_TAG_PATTERN_PT.sub("", text)


class ProblemAnalyzer:
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        self.mw = main_window_ref
        self.tag_manager = tag_manager_ref
        self.problem_definitions = problem_definitions_ref
        self.problem_ids = problem_ids_ref

    def _ends_with_sentence_punctuation_pt(self, text_no_tags_stripped: str) -> bool:
        if not text_no_tags_stripped:
            return False
        last_char = text_no_tags_stripped[-1]
        if last_char in OPTIONAL_TRAILING_CHARS_PT:
            if len(text_no_tags_stripped) > 1:
                char_before_last = text_no_tags_stripped[-2]
                return char_before_last in SENTENCE_END_PUNCTUATION_CHARS_PT
            return False
        return last_char in SENTENCE_END_PUNCTUATION_CHARS_PT

    def _check_short_line_pt(self, current_subline_text: str, next_subline_text: str, font_map: dict, threshold: int) -> bool:
        current_subline_no_tags_stripped = remove_all_tags_pt(current_subline_text).strip()
        if not current_subline_no_tags_stripped or self._ends_with_sentence_punctuation_pt(current_subline_no_tags_stripped):
            return False

        next_subline_no_tags_stripped = remove_all_tags_pt(next_subline_text).strip()
        if not next_subline_no_tags_stripped:
            return False

        first_word_next = next_subline_no_tags_stripped.split(maxsplit=1)[0]
        if not first_word_next:
            return False

        width_current_rstripped = calculate_string_width(current_subline_text.rstrip(), font_map)
        width_first_word_next = calculate_string_width(first_word_next, font_map)
        space_width = calculate_string_width(" ", font_map)

        return (threshold - width_current_rstripped) >= (width_first_word_next + space_width)

    def _check_single_word_subline_pt(self, subline_text: str) -> bool:
        text_no_tags = remove_all_tags_pt(subline_text).strip()
        if not text_no_tags: 
            return False
        
        words = text_no_tags.split()
        
        if len(words) > 1:
            return False
        
        if len(words) == 1:
            word = words[0]
            word_content_pattern = re.compile(r'[\wа-яА-ЯіїІїЄєґҐ]+') 
            if word_content_pattern.search(word):
                return True 

        return False

    def check_for_empty_first_line_of_page(self, text: str) -> List[int]:
        lines = text.split('\n')
        problem_lines = []
        lines_per_page = getattr(self.mw, 'lines_per_page', 4)

        log_debug(f"[EMPTY CHECK PT] Checking data string with {len(lines)} lines, lines_per_page={lines_per_page}")

        for i in range(len(lines)):
            if i % lines_per_page == 0:
                is_first_line_empty = not lines[i].strip()
                log_debug(f"[EMPTY CHECK PT] Line {i}: is_first_line_of_page=True, is_empty={is_first_line_empty}, text='{lines[i][:50]}...'\n")

                if is_first_line_empty:
                    page_lines = lines[i : i + lines_per_page]
                    if len(page_lines) > 1:
                        has_content_after = any(line.strip() for line in page_lines[1:])
                        log_debug(f"[EMPTY CHECK PT] Line {i}: has_content_after={has_content_after}")
                        if has_content_after:
                            log_debug(f"[EMPTY CHECK PT] Line {i}: *** PROBLEM DETECTED ***")
                            problem_lines.append(i)
                    else:
                        log_debug(f"[EMPTY CHECK PT] Line {i}: SKIP - page has only 1 line")

        log_debug(f"[EMPTY CHECK PT] Found {len(problem_lines)} problem lines: {problem_lines}")
        return problem_lines

    def analyze_data_string(self, data_string: str, font_map: dict, threshold: int) -> List[Set[str]]:
        sublines = data_string.split('\n')
        problems_per_subline = [set() for _ in sublines]
        
        empty_first_lines = self.check_for_empty_first_line_of_page(data_string)
        for line_idx in empty_first_lines:
            if line_idx < len(problems_per_subline):
                problems_per_subline[line_idx].add(self.problem_ids.PROBLEM_EMPTY_FIRST_LINE_OF_PAGE)

        for i, subline in enumerate(sublines):
            pixel_width_subline = calculate_string_width(subline.rstrip(), font_map)
            if pixel_width_subline > threshold:
                problems_per_subline[i].add(self.problem_ids.PROBLEM_WIDTH_EXCEEDED)
            
            next_subline = sublines[i + 1] if i + 1 < len(sublines) else None
            if next_subline is not None:
                if self._check_short_line_pt(subline, next_subline, font_map, threshold):
                    problems_per_subline[i].add(self.problem_ids.PROBLEM_SHORT_LINE)

            is_odd_logical_subline = (i + 1) % 2 != 0
            if i > 0 and is_odd_logical_subline:
                if self._check_single_word_subline_pt(subline):
                    problems_per_subline[i].add(self.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE)

            for tag_match in ANY_TAG_PATTERN_PT.finditer(subline):
                tag = tag_match.group(0)
                if not self.tag_manager.is_tag_legitimate(tag):
                    problems_per_subline[i].add(self.problem_ids.PROBLEM_TAG_WARNING)
                    break
        
        return problems_per_subline

    def analyze_subline(self, *args, **kwargs) -> Set[str]:
        # This method is kept for compatibility but the main logic is in analyze_data_string
        return set()
