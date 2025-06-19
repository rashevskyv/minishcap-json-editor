from typing import Tuple, List
import re

from utils.utils import calculate_string_width, remove_all_tags
from .config import PROBLEM_WIDTH_EXCEEDED, PROBLEM_SHORT_LINE, PROBLEM_EMPTY_SUBLINE

class TextFixer:
    def __init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref):
        self.mw = main_window_ref
        self.tag_manager = tag_manager_ref
        self.problem_analyzer = problem_analyzer_ref
        self.newline_tags = ['\\n', '\\p', '\\l']

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

    def _fix_width_exceeded(self, text: str, font_map: dict, threshold: int) -> str:
        sublines = self._get_sublines_from_data_string(text)
        new_text_parts = []
        for subline_with_tag in sublines:
            text_part = subline_with_tag
            tag_part = ""
            for tag in self.newline_tags:
                if subline_with_tag.endswith(tag):
                    text_part = subline_with_tag[:-len(tag)]
                    tag_part = tag
                    break

            width = calculate_string_width(remove_all_tags(text_part), font_map)
            if width <= threshold:
                new_text_parts.append(subline_with_tag)
                continue

            words = text_part.split(' ')
            current_line = ""
            for word in words:
                if not current_line:
                    current_line = word
                    continue
                
                if calculate_string_width(remove_all_tags(current_line + ' ' + word), font_map) > threshold:
                    new_text_parts.append(current_line + "\\n")
                    current_line = word
                else:
                    current_line += ' ' + word
            
            new_text_parts.append(current_line + tag_part)
        
        return "".join(new_text_parts)

    def _fix_short_lines(self, text: str, font_map: dict, threshold: int) -> str:
        sublines = self._get_sublines_from_data_string(text)
        if len(sublines) < 2:
            return text
            
        i = 0
        while i < len(sublines) - 1:
            current_subline_with_tag = sublines[i]
            next_subline_with_tag = sublines[i+1]
            
            if self.problem_analyzer._check_short_line(current_subline_with_tag, next_subline_with_tag, font_map, threshold):
                text_part_current = re.sub(r'\\.$', '', current_subline_with_tag).rstrip()
                text_part_next = re.sub(r'\\.$', '', next_subline_with_tag)
                
                merged_text = text_part_current + " " + text_part_next
                
                next_tag = ""
                for tag in self.newline_tags:
                    if next_subline_with_tag.endswith(tag):
                        next_tag = tag
                        break
                
                sublines[i] = merged_text + next_tag
                sublines.pop(i + 1)
                # Не інкрементуємо i, щоб перевірити щойно об'єднаний рядок з наступним
            else:
                i += 1
            
        return "".join(sublines)

    def _fix_empty_sublines(self, text: str) -> str:
        pattern = r'(\\[nlp])(\s*)(\\[nlp])'
        
        def replace_func(match):
            return match.group(3)
        
        while re.search(pattern, text):
            text = re.sub(pattern, replace_func, text)
            
        return text

    def autofix_data_string(self,
                            data_string: str,
                            editor_font_map: dict,
                            editor_line_width_threshold: int) -> Tuple[str, bool]:
        
        original_text = str(data_string)
        modified_text = original_text
        
        autofix_config = getattr(self.mw, 'autofix_enabled', {})

        max_iterations = 5
        for _ in range(max_iterations):
            text_before_pass = modified_text
            
            if autofix_config.get(PROBLEM_EMPTY_SUBLINE, False):
                modified_text = self._fix_empty_sublines(modified_text)

            if autofix_config.get(PROBLEM_SHORT_LINE, False):
                modified_text = self._fix_short_lines(modified_text, editor_font_map, editor_line_width_threshold)
            
            if autofix_config.get(PROBLEM_WIDTH_EXCEEDED, False):
                modified_text = self._fix_width_exceeded(modified_text, editor_font_map, editor_line_width_threshold)

            if modified_text == text_before_pass:
                break
        
        return modified_text, modified_text != original_text