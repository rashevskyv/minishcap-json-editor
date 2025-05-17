from PyQt5.QtGui import QColor
from typing import Optional, Set, Dict, Any, Tuple
import re

from plugins.base_game_rules import BaseGameRules
from utils.utils import log_debug, calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN, convert_dots_to_spaces_from_editor

from .config import (
    PROBLEM_DEFINITIONS,
    PROBLEM_WIDTH_EXCEEDED,
    PROBLEM_SHORT_LINE, PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL,
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY
)

SENTENCE_END_PUNCTUATION_CHARS_ZMC = ['.', '!', '?']
OPTIONAL_TRAILING_CHARS_ZMC = ['"', "'"]
WORD_CHAR_PATTERN_ZMC = re.compile(r"^[a-zA-Zа-яА-ЯіїєґІЇЄҐ]$") 
ANY_TAG_RE_PATTERN_ZMC = r"(\{[^}]*\}|\[[^\]]*\])" 
COLOR_WHITE_TAG_PATTERN_ZMC = re.compile(r"\{Color:White\}", re.IGNORECASE) 
PUNCTUATION_PATTERN_ZMC = re.compile(r"^[,\.!?]$") 


class GameRules(BaseGameRules):

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.problem_definitions_cache = PROBLEM_DEFINITIONS

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        return self.problem_definitions_cache

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

    def _check_empty_odd_subline_display_zmc(self, subline_text: str, subline_qtextblock_number_in_editor: int, is_single_subline_in_document: bool) -> bool:
        if is_single_subline_in_document: # Do not flag if it's the only subline
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


    def analyze_subline(self,
                        text: str, 
                        next_text: Optional[str], 
                        subline_number_in_data_string: int, 
                        qtextblock_number_in_editor: int,
                        is_last_subline_in_data_string: bool,
                        editor_font_map: dict, 
                        editor_line_width_threshold: int) -> Set[str]:
        
        found_problems = set()
        text_with_spaces = convert_dots_to_spaces_from_editor(text)
        next_text_with_spaces = convert_dots_to_spaces_from_editor(next_text) if next_text is not None else None

        text_no_tags_rstripped = remove_all_tags(text_with_spaces).rstrip()
        pixel_width_subline = calculate_string_width(text_no_tags_rstripped, editor_font_map)
        if pixel_width_subline > editor_line_width_threshold:
            found_problems.add(PROBLEM_WIDTH_EXCEEDED)

        is_single_doc_block_for_display_check = False
        if self.mw:
            active_editor = self.mw.edited_text_edit 
            if hasattr(self.mw, 'original_text_edit') and self.mw.original_text_edit and self.mw.original_text_edit.hasFocus(): 
                active_editor = self.mw.original_text_edit
            
            if active_editor and hasattr(active_editor, 'document') and active_editor.document():
                 is_single_doc_block_for_display_check = (active_editor.document().blockCount() == 1) 
        
        if self._check_empty_odd_subline_display_zmc(text, qtextblock_number_in_editor, is_single_doc_block_for_display_check):
             found_problems.add(PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY)

        if next_text_with_spaces is not None: 
            if self._check_short_line_zmc(text_with_spaces, next_text_with_spaces, editor_font_map, editor_line_width_threshold):
                found_problems.add(PROBLEM_SHORT_LINE)
        
        is_odd_logical_subline = (subline_number_in_data_string + 1) % 2 != 0
        is_only_logical_subline = is_last_subline_in_data_string and subline_number_in_data_string == 0

        if is_odd_logical_subline and not is_only_logical_subline:
            if not ALL_TAGS_PATTERN.search(text_with_spaces):
                text_no_tags_for_logical_empty_check = remove_all_tags(text_with_spaces)
                stripped_text_no_tags_for_logical_empty_check = text_no_tags_for_logical_empty_check.strip()
                is_content_empty_or_zero_logical = not stripped_text_no_tags_for_logical_empty_check or stripped_text_no_tags_for_logical_empty_check == "0"
                if is_content_empty_or_zero_logical:
                    found_problems.add(PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL)

        return found_problems

    def _fix_empty_odd_sublines_zmc(self, text: str) -> Tuple[str, bool]:
        sub_lines = text.split('\n')
        if len(sub_lines) <= 1: # No logical odd empty if only one subline
            return text, False
            
        new_sub_lines = []
        made_change = False
        for i, sub_line in enumerate(sub_lines):
            is_odd_subline = (i + 1) % 2 != 0
            if ALL_TAGS_PATTERN.search(sub_line):
                new_sub_lines.append(sub_line)
                continue
            text_no_tags = remove_all_tags(sub_line) 
            stripped_text_no_tags = text_no_tags.strip()
            is_empty_or_zero = not stripped_text_no_tags or stripped_text_no_tags == "0"
            
            # Only remove if it's an odd subline AND it's not the *only* subline in the entire data string
            if is_odd_subline and is_empty_or_zero:
                made_change = True
                continue 
            new_sub_lines.append(sub_line)
            
        if not made_change:
            return text, False
            
        if text and not new_sub_lines: # If all sublines were removed (e.g. "\n0\n")
             return "", True # Return empty string, indicating a change

        final_text_list = []
        # Remove consecutive empty lines that might result from deletion
        for i in range(len(new_sub_lines)):
            if i > 0 and not new_sub_lines[i].strip() and not new_sub_lines[i-1].strip():
                continue
            final_text_list.append(new_sub_lines[i])
        
        # If the result is a single empty subline, but original had content, it's a change
        if len(final_text_list) == 1 and not final_text_list[0].strip() and text.strip():
             joined_text = "\n".join(final_text_list) # Will be ""
             return joined_text, True # It changed from non-empty to empty

        joined_text = "\n".join(final_text_list)
        return joined_text, joined_text != text
        
    def _extract_first_word_with_tags_zmc(self, text: str) -> tuple[str, str]:
        if not text.strip():
            return "", text 
        first_word_text = ""
        char_idx = 0
        while char_idx < len(text):
            char = text[char_idx]
            if char.isspace():
                if first_word_text: 
                    break
                else: 
                    first_word_text += char
                    char_idx += 1
                    continue
            is_tag_char = False
            for tag_match in ALL_TAGS_PATTERN.finditer(text[char_idx:]):
                if tag_match.start() == 0: 
                    tag_content = tag_match.group(0)
                    first_word_text += tag_content
                    char_idx += len(tag_content)
                    is_tag_char = True
                    break
            if is_tag_char:
                continue
            first_word_text += char
            char_idx += 1
        remaining_text = text[len(first_word_text):].lstrip()
        return first_word_text.rstrip(), remaining_text

    def _fix_short_lines_zmc(self, text: str, font_map: dict, threshold: int) -> Tuple[str, bool]:
        sub_lines = text.split('\n')
        if len(sub_lines) <= 1:
            return text, False
        original_text = text
        made_change_in_this_fix_pass = True 
        while made_change_in_this_fix_pass:
            made_change_in_this_fix_pass = False
            new_sub_lines = list(sub_lines) 
            i = len(new_sub_lines) - 2 
            while i >= 0:
                current_line = new_sub_lines[i]
                next_line = new_sub_lines[i+1]
                if self._check_short_line_zmc(current_line, next_line, font_map, threshold):
                    first_word_next_raw, rest_of_next_line_raw = self._extract_first_word_with_tags_zmc(next_line)
                    current_line_rstripped = current_line.rstrip()
                    merged_line = current_line_rstripped
                    if current_line_rstripped and first_word_next_raw:
                        needs_space = False
                        if not current_line_rstripped.endswith(" ") and not first_word_next_raw.startswith(" "):
                            last_char_current = current_line_rstripped[-1]
                            first_char_next = first_word_next_raw[0]
                            is_current_ends_tag = last_char_current in ['}', ']']
                            is_next_starts_tag = first_char_next in ['{', '[']
                            is_next_starts_word_char = WORD_CHAR_PATTERN_ZMC.match(first_char_next) is not None
                            if is_current_ends_tag and is_next_starts_word_char: needs_space = True
                            elif not is_current_ends_tag and not is_next_starts_tag: needs_space = True
                            elif not is_current_ends_tag and is_next_starts_tag: needs_space = True
                        if needs_space:
                            merged_line += " "
                    merged_line += first_word_next_raw
                    new_sub_lines[i] = merged_line
                    new_sub_lines[i+1] = rest_of_next_line_raw
                    if not new_sub_lines[i+1].strip() and len(new_sub_lines) > i + 1 : 
                        del new_sub_lines[i+1]
                    made_change_in_this_fix_pass = True
                    sub_lines = list(new_sub_lines) 
                    break 
                i -= 1
            if not made_change_in_this_fix_pass:
                break 
        final_text = "\n".join(sub_lines)
        return final_text, final_text != original_text

    def _fix_width_exceeded_zmc(self, text: str, font_map: dict, threshold: int) -> Tuple[str, bool]:
        sub_lines = text.split('\n')
        made_change_overall = False
        new_full_text_lines = []
        for line_idx, current_line_text in enumerate(sub_lines):
            current_processing_line = current_line_text
            temp_newly_created_lines_for_this_original_line = []
            while True: 
                line_width_no_tags = calculate_string_width(remove_all_tags(current_processing_line), font_map)
                if line_width_no_tags <= threshold:
                    if current_processing_line or not temp_newly_created_lines_for_this_original_line or \
                       (not current_processing_line and line_idx < len(sub_lines) -1 ): 
                        temp_newly_created_lines_for_this_original_line.append(current_processing_line)
                    break 
                made_change_overall = True
                text_fits = ""
                line_parts = re.findall(r'(\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', current_processing_line)
                current_temp_width = 0
                last_fit_index = -1
                needs_space_before_next_part = False
                for i, part in enumerate(line_parts):
                    part_no_tags = remove_all_tags(part)
                    part_width = calculate_string_width(part_no_tags, font_map)
                    width_to_check = current_temp_width
                    current_needs_space_before = needs_space_before_next_part and not part.isspace() and text_fits and not text_fits.endswith(" ")
                    if current_needs_space_before:
                        width_to_check += calculate_string_width(" ", font_map)
                    width_to_check += part_width
                    if width_to_check <= threshold:
                        if current_needs_space_before: text_fits += " "
                        text_fits += part
                        current_temp_width = calculate_string_width(remove_all_tags(text_fits), font_map) 
                        last_fit_index = i
                        needs_space_before_next_part = not part.isspace()
                    else: break 
                if last_fit_index != -1 :
                    text_overflows = "".join(line_parts[last_fit_index + 1:]).lstrip()
                    temp_newly_created_lines_for_this_original_line.append(text_fits.rstrip())
                    current_processing_line = text_overflows
                    if not text_overflows: break
                else: 
                    if line_parts:
                        temp_newly_created_lines_for_this_original_line.append("") 
                        current_processing_line = "".join(line_parts).lstrip() 
                    else: 
                        temp_newly_created_lines_for_this_original_line.append(current_processing_line) 
                        break 
            new_full_text_lines.extend(temp_newly_created_lines_for_this_original_line)
        if made_change_overall:
            while new_full_text_lines and not new_full_text_lines[-1].strip() and len(new_full_text_lines) > 1:
                new_full_text_lines.pop()
            final_text = "\n".join(new_full_text_lines)
            return final_text, final_text != text
        return text, False

    def _fix_leading_spaces_in_sublines_zmc(self, text: str) -> Tuple[str, bool]:
        sub_lines = text.split('\n')
        fixed_sub_lines = []
        changed = False
        for sub_line_idx, sub_line in enumerate(sub_lines):
            if sub_line.startswith(" ") and not sub_line.startswith("  "):
                fixed_sub_lines.append(sub_line[1:])
                changed = True
            else:
                fixed_sub_lines.append(sub_line)
        if changed:
            final_text = "\n".join(fixed_sub_lines)
            return final_text, final_text != text
        return text, False

    def _cleanup_spaces_around_tags_zmc(self, text: str) -> Tuple[str, bool]:
        original_text = text
        text_changed_this_function_call = False
        pattern = re.compile(f"(?P<tag>{ANY_TAG_RE_PATTERN_ZMC})(?P<space> )(?P<after_space>.)?")
        current_pos = 0
        result_parts = []
        last_processed_end = 0
        while current_pos < len(text):
            match = pattern.search(text, current_pos)
            if not match:
                result_parts.append(text[last_processed_end:])
                break
            tag_match_start_pos = match.start("tag")
            result_parts.append(text[last_processed_end:tag_match_start_pos])
            tag_content = match.group("tag")
            space_content = match.group("space") 
            char_after_space_content = match.group("after_space") if match.group("after_space") is not None else ""
            result_parts.append(tag_content) 
            is_color_white = COLOR_WHITE_TAG_PATTERN_ZMC.fullmatch(tag_content)
            should_remove_space = False
            if is_color_white:
                if char_after_space_content and PUNCTUATION_PATTERN_ZMC.match(char_after_space_content):
                    should_remove_space = True
            else: should_remove_space = True
            if not should_remove_space: result_parts.append(space_content) 
            else: text_changed_this_function_call = True
            last_processed_end = match.start("after_space") if char_after_space_content else match.end("space")
            current_pos = last_processed_end
        final_text = "".join(result_parts)
        return final_text, final_text != original_text

    def autofix_data_string(self,
                            data_string: str,
                            editor_font_map: dict,
                            editor_line_width_threshold: int) -> Tuple[str, bool]:
        log_debug(f"ZeldaMC Rules: autofix_data_string for: '{data_string[:70]}...'")
        original_text = str(data_string)
        modified_text = original_text
        
        max_iterations = 10
        iterations = 0
        changed_overall_in_all_passes = False

        while iterations < max_iterations:
            text_before_this_full_pass = modified_text
            iterations += 1
            made_change_in_this_full_pass = False
            
            modified_text, changed = self._fix_empty_odd_sublines_zmc(modified_text)
            if changed: made_change_in_this_full_pass = True
            
            modified_text, changed = self._fix_short_lines_zmc(modified_text, editor_font_map, editor_line_width_threshold)
            if changed: made_change_in_this_full_pass = True
            
            modified_text, changed = self._fix_width_exceeded_zmc(modified_text, editor_font_map, editor_line_width_threshold)
            if changed: made_change_in_this_full_pass = True

            modified_text, changed = self._cleanup_spaces_around_tags_zmc(modified_text)
            if changed: made_change_in_this_full_pass = True

            modified_text, changed = self._fix_leading_spaces_in_sublines_zmc(modified_text)
            if changed: made_change_in_this_full_pass = True

            if not made_change_in_this_full_pass: 
                break 
            
            if made_change_in_this_full_pass: 
                 changed_overall_in_all_passes = True


        log_debug(f"ZeldaMC Rules: autofix_data_string completed. Iterations: {iterations}, Changed: {changed_overall_in_all_passes}")
        return modified_text, changed_overall_in_all_passes