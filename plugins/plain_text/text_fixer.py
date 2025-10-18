# --- START OF FILE plugins/plain_text/text_fixer.py ---
from typing import Optional, Set, Dict, Any, Tuple
import re

from utils.logging_utils import log_debug
from .problem_analyzer import ANY_TAG_PATTERN_WW, remove_all_tags_ww

WORD_CHAR_PATTERN_ZWW = re.compile(r"^[a-zA-Zа-яА-ЯіїєґІЇЄҐ]$")
CLOSING_COLOR_TAG_WW = "[/C]"
PUNCTUATION_PATTERN_ZWW = re.compile(r"^[,\.!?]$")

class TextFixer:
    def __init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref):
        self.mw = main_window_ref
        self.tag_manager = tag_manager_ref 
        self.problem_analyzer = problem_analyzer_ref

    def _fix_empty_odd_sublines_zww(self, text: str) -> Tuple[str, bool]:
        sub_lines = text.split('\n')
        if len(sub_lines) <= 1:
            return text, False
        new_sub_lines = []
        made_change = False
        for i, sub_line in enumerate(sub_lines):
            is_odd_subline = (i + 1) % 2 != 0
            if ANY_TAG_PATTERN_WW.search(sub_line):
                new_sub_lines.append(sub_line)
                continue
            text_no_tags = remove_all_tags_ww(sub_line)
            stripped_text_no_tags = text_no_tags.strip()
            is_empty_or_zero = not stripped_text_no_tags or stripped_text_no_tags == "0"
            if is_odd_subline and is_empty_or_zero:
                made_change = True
                continue
            new_sub_lines.append(sub_line)
        if not made_change:
            return text, False
        if text and not new_sub_lines:
            return "", True
        final_text_list = []
        for i in range(len(new_sub_lines)):
            if i > 0 and not new_sub_lines[i].strip() and not new_sub_lines[i-1].strip():
                continue
            final_text_list.append(new_sub_lines[i])
        joined_text = "\n".join(final_text_list)
        return joined_text, joined_text != text

    def _extract_first_word_with_tags_zww(self, text: str) -> tuple[str, str]:
        if not text.strip(): return "", text
        first_word_text = ""
        char_idx = 0
        while char_idx < len(text):
            char = text[char_idx]
            if char.isspace():
                if first_word_text: break
                else: first_word_text += char; char_idx += 1; continue
            is_tag_char = False
            for tag_match in ANY_TAG_PATTERN_WW.finditer(text[char_idx:]):
                if tag_match.start() == 0:
                    tag_content = tag_match.group(0)
                    first_word_text += tag_content
                    char_idx += len(tag_content)
                    is_tag_char = True
                    break
            if is_tag_char: continue
            first_word_text += char
            char_idx += 1
        remaining_text = text[len(first_word_text):].lstrip()
        return first_word_text.rstrip(), remaining_text

    def _fix_short_lines_zww(self, text: str, font_map: dict, threshold: int) -> Tuple[str, bool]:
        sub_lines = text.split('\n')
        if len(sub_lines) <= 1: return text, False
        original_text = text
        made_change_in_this_fix_pass = True
        while made_change_in_this_fix_pass:
            made_change_in_this_fix_pass = False
            new_sub_lines = list(sub_lines)
            i = len(new_sub_lines) - 2
            while i >= 0:
                current_line = new_sub_lines[i]
                next_line = new_sub_lines[i+1]
                
                if self.problem_analyzer._check_short_line_zww(current_line, next_line, font_map, threshold):
                    first_word_next_raw, rest_of_next_line_raw = self._extract_first_word_with_tags_zww(next_line)
                    current_line_rstripped = current_line.rstrip()
                    merged_line = current_line_rstripped
                    if current_line_rstripped and first_word_next_raw:
                        needs_space = False
                        if not current_line_rstripped.endswith(" ") and not first_word_next_raw.startswith(" "):
                            last_char_current = current_line_rstripped[-1]
                            first_char_next = first_word_next_raw[0]
                            is_current_ends_tag = last_char_current == ']'
                            is_next_starts_tag = first_char_next == '['
                            is_next_starts_word_char = WORD_CHAR_PATTERN_ZWW.match(first_char_next) is not None
                            if is_current_ends_tag and is_next_starts_word_char: needs_space = True
                            elif not is_current_ends_tag and not is_next_starts_tag: needs_space = True
                            elif not is_current_ends_tag and is_next_starts_tag: needs_space = True
                        if needs_space: merged_line += " "
                    merged_line += first_word_next_raw
                    new_sub_lines[i] = merged_line
                    new_sub_lines[i+1] = rest_of_next_line_raw
                    if not new_sub_lines[i+1].strip() and len(new_sub_lines) > i + 1 :
                        del new_sub_lines[i+1]
                    made_change_in_this_fix_pass = True
                    sub_lines = list(new_sub_lines)
                    break
                i -= 1
            if not made_change_in_this_fix_pass: break
        final_text = "\n".join(sub_lines)
        return final_text, final_text != original_text

    def _fix_width_exceeded_zww(self, text: str, font_map: dict, threshold: int) -> Tuple[str, bool]:
        original_text = text
        sub_lines = text.split('\n')
        
        made_change = False
        final_lines = []

        for line in sub_lines:
            while self.mw.current_game_rules.calculate_string_width_override(line, font_map) > threshold:
                made_change = True
                line_parts = re.findall(r'(\[[^\]]*\]|\S+|\s+)', line)
                
                best_split_point = -1
                for j in range(len(line_parts) - 1, 0, -1):
                    line_part_one = "".join(line_parts[:j]).rstrip()
                    if self.mw.current_game_rules.calculate_string_width_override(line_part_one, font_map) <= threshold:
                        best_split_point = j
                        break
                
                if best_split_point == -1 and len(line_parts) > 1:
                    best_split_point = 1

                if best_split_point != -1:
                    line1 = "".join(line_parts[:best_split_point]).rstrip()
                    line2 = "".join(line_parts[best_split_point:]).lstrip()
                    final_lines.append(line1)
                    line = line2 
                else:
                    final_lines.append(line)
                    line = ""
                    break
            
            if line:
                final_lines.append(line)

        if not made_change:
            return original_text, False

        final_text = "\n".join(final_lines)
        return final_text, True

    def _cleanup_spaces_around_tags_zww(self, text: str) -> Tuple[str, bool]:
        original_text = text
        pattern = re.compile(f"(?P<tag>{ANY_TAG_PATTERN_WW.pattern})(?P<space> )(?P<after_space>.)?")
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
            
            is_closing_tag = tag_content.lower() == CLOSING_COLOR_TAG_WW.lower()
            
            should_remove_space = False
            if is_closing_tag:
                if char_after_space_content and PUNCTUATION_PATTERN_ZWW.match(char_after_space_content):
                    should_remove_space = True
            else: 
                should_remove_space = True

            if not should_remove_space: 
                result_parts.append(space_content)

            last_processed_end = match.start("after_space") if char_after_space_content else match.end("space")
            current_pos = last_processed_end
            
        final_text = "".join(result_parts)
        return final_text, final_text != original_text

    def fix_empty_first_line_of_page(self, text: str) -> Tuple[str, bool]:
        lines = text.split('\n')
        problem_indices = self.problem_analyzer.check_for_empty_first_line_of_page(text)
        if not problem_indices:
            return text, False

        indices_to_remove = set(problem_indices)
        
        new_lines = [line for i, line in enumerate(lines) if i not in indices_to_remove]
        
        new_text = '\n'.join(new_lines)
        return new_text, new_text != text

    def autofix_data_string(self,
                            data_string: str,
                            editor_font_map: dict,
                            editor_line_width_threshold: int) -> Tuple[str, bool]:
        
        original_text = str(data_string)
        
        text_after_page_fix, page_fix_changed = self.fix_empty_first_line_of_page(original_text)
        
        modified_text, changed = self._fix_empty_odd_sublines_zww(text_after_page_fix)
        
        max_iterations = 10
        for _ in range(max_iterations):
            text_before_pass = modified_text
            
            merged_text, changed_merge = self._fix_short_lines_zww(modified_text, editor_font_map, editor_line_width_threshold)
            splitted_text, changed_split = self._fix_width_exceeded_zww(merged_text, editor_font_map, editor_line_width_threshold)
            
            modified_text = splitted_text
            if not changed_merge and not changed_split:
                break
        
        cleaned_text, _ = self._cleanup_spaces_around_tags_zww(modified_text)
        
        return cleaned_text, cleaned_text != original_text