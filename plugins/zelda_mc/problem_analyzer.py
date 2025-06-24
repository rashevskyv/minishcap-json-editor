from typing import Optional, Set, Dict, Any
import re

from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, ALL_TAGS_PATTERN

SENTENCE_END_PUNCTUATION_CHARS_ZMC = ['.', '!', '?']
OPTIONAL_TRAILING_CHARS_ZMC = ['"', "'"]


class ProblemAnalyzer:
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        self.mw = main_window_ref
        self.tag_manager = tag_manager_ref
        self.problem_definitions = problem_definitions_ref
        self.problem_ids = problem_ids_ref

    def _ends_with_sentence_punctuation_zmc(self, text_no_tags_stripped: str) -> bool:
        if not text_no_tags_stripped:
            return False
        last_char = text_no_tags_stripped[-1]
        if last_char in OPTIONAL_TRAILING_CHARS_ZMC:
            if len(text_no_tags_stripped) > 1:
                char_before_last = text_no_tags_stripped[-2]
                return char_before_last in SENTENCE_END_PUNCTUATION_CHARS_ZMC
            return False
        return last_char in SENTENCE_END_PUNCTUATION_CHARS_ZMC

    def _check_short_line_zmc(self, current_subline_text: str, next_subline_text: str, font_map: dict, threshold: int) -> bool:
        current_subline_no_tags_stripped = remove_all_tags(current_subline_text).strip()
        if not current_subline_no_tags_stripped or self._ends_with_sentence_punctuation_zmc(current_subline_no_tags_stripped):
            return False

        next_subline_no_tags_stripped = remove_all_tags(next_subline_text).strip()
        if not next_subline_no_tags_stripped:
            return False

        first_word_next = next_subline_no_tags_stripped.split(maxsplit=1)[0]
        if not first_word_next:
            return False

        text_for_width_calc_current = convert_dots_to_spaces_from_editor(current_subline_text.rstrip())
        text_for_width_calc_next_word = convert_dots_to_spaces_from_editor(first_word_next)

        width_current_rstripped = calculate_string_width(remove_all_tags(text_for_width_calc_current), font_map)
        width_first_word_next = calculate_string_width(remove_all_tags(text_for_width_calc_next_word), font_map)
        space_width = calculate_string_width(" ", font_map)

        return (threshold - width_current_rstripped) >= (width_first_word_next + space_width)

    def _check_empty_odd_subline_display_zmc(self,
                                             subline_text: str,
                                             subline_qtextblock_number_in_editor: int,
                                             is_single_subline_in_document: bool,
                                             is_logically_single_and_empty_data_string: bool,
                                             is_target_for_debug: bool = False) -> bool:
        if is_logically_single_and_empty_data_string:
            return False

        if is_single_subline_in_document:
            return False

        is_odd_qtextblock_editor = (subline_qtextblock_number_in_editor + 1) % 2 != 0
        if not is_odd_qtextblock_editor:
            return False

        text_no_dots = convert_dots_to_spaces_from_editor(subline_text)
        if ALL_TAGS_PATTERN.search(text_no_dots):
            return False

        text_no_tags_for_empty_check = remove_all_tags(text_no_dots)
        stripped_text_no_tags_for_empty_check = text_no_tags_for_empty_check.strip()
        is_content_empty_or_zero = not stripped_text_no_tags_for_empty_check or stripped_text_no_tags_for_empty_check == "0"
        return is_content_empty_or_zero

    def _check_single_word_subline_zmc(self, subline_text: str) -> bool:
        text_no_tags = remove_all_tags(subline_text).strip()
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

        found_problems = set()
        text_with_spaces = convert_dots_to_spaces_from_editor(text)
        next_text_with_spaces = convert_dots_to_spaces_from_editor(next_text) if next_text is not None else None

        text_no_tags_rstripped = remove_all_tags(text_with_spaces).rstrip()
        pixel_width_subline = calculate_string_width(text_no_tags_rstripped, editor_font_map)
        if pixel_width_subline > editor_line_width_threshold:
            found_problems.add(self.problem_ids.PROBLEM_WIDTH_EXCEEDED)

        is_single_doc_block_for_display_check = False
        if self.mw:
            active_editor = getattr(self.mw, 'edited_text_edit', None)
            original_text_edit = getattr(self.mw, 'original_text_edit', None)
            if original_text_edit and original_text_edit.hasFocus():
                active_editor = original_text_edit

            if active_editor and hasattr(active_editor, 'document') and active_editor.document():
                 is_single_doc_block_for_display_check = (active_editor.document().blockCount() == 1)

        is_logically_single_and_empty_data_string_check = (full_data_string_text_for_logical_check == "" and subline_number_in_data_string == 0 and is_last_subline_in_data_string)

        if self._check_empty_odd_subline_display_zmc(text, 
                                                     qtextblock_number_in_editor,
                                                     is_single_doc_block_for_display_check,
                                                     is_logically_single_and_empty_data_string_check,
                                                     is_target_for_debug):
             found_problems.add(self.problem_ids.PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY)

        if next_text_with_spaces is not None:
            if self._check_short_line_zmc(text_with_spaces, next_text_with_spaces, editor_font_map, editor_line_width_threshold):
                found_problems.add(self.problem_ids.PROBLEM_SHORT_LINE)

        is_odd_logical_subline = (subline_number_in_data_string + 1) % 2 != 0
        is_only_logical_subline_in_data_string = (subline_number_in_data_string == 0 and is_last_subline_in_data_string)

        if is_odd_logical_subline and not is_only_logical_subline_in_data_string:
            if not ALL_TAGS_PATTERN.search(text_with_spaces):
                text_no_tags_for_logical_empty_check = remove_all_tags(text_with_spaces)
                stripped_text_no_tags_for_logical_empty_check = text_no_tags_for_logical_empty_check.strip()
                is_content_empty_or_zero_logical = not stripped_text_no_tags_for_logical_empty_check or stripped_text_no_tags_for_logical_empty_check == "0"
                if is_content_empty_or_zero_logical:
                    found_problems.add(self.problem_ids.PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL)
        
        if subline_number_in_data_string > 0 and is_odd_logical_subline:
            if self._check_single_word_subline_zmc(text_with_spaces):
                found_problems.add(self.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE)


        for tag_match in ALL_TAGS_PATTERN.finditer(text_with_spaces):
            tag = tag_match.group(0)
            if not self.tag_manager.is_tag_legitimate(tag):
                found_problems.add(self.problem_ids.PROBLEM_TAG_WARNING)
                break

        return found_problems