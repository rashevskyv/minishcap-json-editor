import re
from PyQt5.QtGui import QTextBlock
from PyQt5.QtWidgets import QMainWindow
from utils.utils import log_debug, calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, SPACE_DOT_SYMBOL, ALL_TAGS_PATTERN

SENTENCE_END_PUNCTUATION_PATTERN = re.compile(r'[.,!?](?:["\']|")?$')

class LNETPaintHelpers:
    def __init__(self, editor):
        self.editor = editor

    def _map_no_tag_index_to_raw_text_index(self, raw_qtextline_text: str, line_text_segment_no_tags: str, target_no_tag_index_in_segment: int) -> int:
        if target_no_tag_index_in_segment == 0:
            current_idx = 0
            while current_idx < len(raw_qtextline_text):
                char = raw_qtextline_text[current_idx]
                if char.isspace() or char == SPACE_DOT_SYMBOL:
                    current_idx += 1
                    continue
                is_tag_char = False
                for tag_match in ALL_TAGS_PATTERN.finditer(raw_qtextline_text[current_idx:]):
                    if tag_match.start() == 0:
                        tag_content = tag_match.group(0)
                        current_idx += len(tag_content)
                        is_tag_char = True
                        break
                if is_tag_char:
                    continue
                return current_idx
            return 0

        words_no_tags = list(re.finditer(r'\S+', line_text_segment_no_tags))
        target_word_text_no_tags = ""
        current_word_idx_no_tags = -1

        for i, word_match_no_tags in enumerate(words_no_tags):
            if word_match_no_tags.start() == target_no_tag_index_in_segment:
                target_word_text_no_tags = word_match_no_tags.group(0)
                current_word_idx_no_tags = i
                break

        if not target_word_text_no_tags :
            return min(target_no_tag_index_in_segment, len(raw_qtextline_text) -1 if raw_qtextline_text else 0)

        target_word_occurrence_count = 0
        for i in range(current_word_idx_no_tags + 1):
            if words_no_tags[i].group(0) == target_word_text_no_tags:
                target_word_occurrence_count += 1

        actual_word_occurrence_in_raw = 0
        for raw_match in re.finditer(r'\S+', raw_qtextline_text):
            raw_word_from_match = raw_match.group(0)
            raw_word_with_spaces = convert_dots_to_spaces_from_editor(raw_word_from_match)
            cleaned_word_for_comparison = remove_all_tags(raw_word_with_spaces)

            if cleaned_word_for_comparison == target_word_text_no_tags:
                actual_word_occurrence_in_raw += 1
                if actual_word_occurrence_in_raw == target_word_occurrence_count:
                    return raw_match.start()

        return min(target_no_tag_index_in_segment, len(raw_qtextline_text) -1 if raw_qtextline_text else 0)

    def _check_new_blue_rule_for_text_lines(self, current_line_text: str, next_line_text: str, line_number: int) -> bool:
        is_odd_line = (line_number + 1) % 2 != 0
        if not is_odd_line:
            return False

        current_line_no_tags = remove_all_tags(current_line_text)
        stripped_current_text = current_line_no_tags.strip()

        if not stripped_current_text:
            return False

        starts_lowercase = stripped_current_text[0].islower()
        if not starts_lowercase:
            return False

        main_window_ref = self.editor.window()
        ends_punctuation = False
        if isinstance(main_window_ref, QMainWindow) and hasattr(main_window_ref, 'editor_operation_handler') \
           and hasattr(main_window_ref.editor_operation_handler, 'autofix_logic'):
            if hasattr(main_window_ref.editor_operation_handler.autofix_logic, '_ends_with_sentence_punctuation'):
                ends_punctuation = main_window_ref.editor_operation_handler.autofix_logic._ends_with_sentence_punctuation(stripped_current_text)
            else:
                # Fallback or log if method is missing in autofix_logic
                log_debug("LNETPaintHelpers: autofix_logic._ends_with_sentence_punctuation not found.")
                # Default to False or implement a basic check here if necessary
                ends_punctuation = SENTENCE_END_PUNCTUATION_PATTERN.search(stripped_current_text) is not None


        if not ends_punctuation:
            return False

        next_line_no_tags = remove_all_tags(next_line_text)
        stripped_next_text = next_line_no_tags.strip()
        is_next_line_not_empty = bool(stripped_next_text)

        return is_next_line_not_empty

    def _check_new_blue_rule(self, current_q_block: QTextBlock, next_q_block: QTextBlock) -> bool:
        if not current_q_block.isValid():
            return False

        current_q_block_text_raw_dots = current_q_block.text()
        current_q_block_text_spaces = convert_dots_to_spaces_from_editor(current_q_block_text_raw_dots)

        next_q_block_text_raw_dots = ""
        if next_q_block.isValid():
            next_q_block_text_raw_dots = next_q_block.text()
        next_q_block_text_spaces = convert_dots_to_spaces_from_editor(next_q_block_text_raw_dots)
        
        # Pass current_q_block.blockNumber() as line_number to the text-based checker
        return self._check_new_blue_rule_for_text_lines(current_q_block_text_spaces, next_q_block_text_spaces, current_q_block.blockNumber())


    def _is_qtextblock_potentially_short_for_paint(self, current_q_block: QTextBlock, next_q_block: QTextBlock) -> bool:
        if not self.editor.font_map: return False
        if not current_q_block.isValid() or not next_q_block.isValid(): return False

        main_window_ref = self.editor.window()
        ends_with_punctuation_func = None
        if isinstance(main_window_ref, QMainWindow) and hasattr(main_window_ref, 'editor_operation_handler') \
           and hasattr(main_window_ref.editor_operation_handler, 'autofix_logic'):
            if hasattr(main_window_ref.editor_operation_handler.autofix_logic, '_ends_with_sentence_punctuation'):
                ends_with_punctuation_func = main_window_ref.editor_operation_handler.autofix_logic._ends_with_sentence_punctuation
            else:
                log_debug("LNETPaintHelpers: autofix_logic._ends_with_sentence_punctuation not found for short check.")
                # Fallback or log if method is missing in autofix_logic
                ends_with_punctuation_func = lambda text: SENTENCE_END_PUNCTUATION_PATTERN.search(text) is not None


        max_width_for_short_check_paint = self.editor.LINE_WIDTH_WARNING_THRESHOLD_PIXELS
        space_width_editor = calculate_string_width(" ", self.editor.font_map)

        current_q_block_text_raw_dots = current_q_block.text()
        current_q_block_text_spaces = convert_dots_to_spaces_from_editor(current_q_block_text_raw_dots)
        current_sub_line_clean_stripped = remove_all_tags(current_q_block_text_spaces).strip()

        if not current_sub_line_clean_stripped: return False
        if ends_with_punctuation_func and ends_with_punctuation_func(current_sub_line_clean_stripped): return False

        next_q_block_text_raw_dots = next_q_block.text()
        next_q_block_text_spaces = convert_dots_to_spaces_from_editor(next_q_block_text_raw_dots)
        next_sub_line_clean_stripped_editor = remove_all_tags(next_q_block_text_spaces).strip()

        if not next_sub_line_clean_stripped_editor: return False

        first_word_next_editor = next_sub_line_clean_stripped_editor.split(maxsplit=1)[0] if next_sub_line_clean_stripped_editor else ""
        if not first_word_next_editor: return False

        first_word_next_width_editor = calculate_string_width(first_word_next_editor, self.editor.font_map)
        if first_word_next_width_editor <= 0: return False

        current_qblock_pixel_width_rstripped = calculate_string_width(remove_all_tags(current_q_block_text_spaces).rstrip(), self.editor.font_map)
        remaining_width_for_qblock_editor = max_width_for_short_check_paint - current_qblock_pixel_width_rstripped

        if remaining_width_for_qblock_editor >= (first_word_next_width_editor + space_width_editor):
            return True

        return False