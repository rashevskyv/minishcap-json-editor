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
        if is_target_for_debug:
            log_debug(f"    ORANGE_BUG_DEBUG (Analyzer): _check_empty_odd_subline_display_zmc: text='{repr(subline_text)}', qblk_num={subline_qtextblock_number_in_editor}, is_single_doc={is_single_subline_in_document}, is_logically_single_empty_ds={is_logically_single_and_empty_data_string}")

        if is_logically_single_and_empty_data_string:
            if is_target_for_debug: log_debug(f"      ORANGE_BUG_DEBUG (Analyzer): Data string is logically single and empty. Returning False.")
            return False

        if is_single_subline_in_document:
            if is_target_for_debug: log_debug(f"      ORANGE_BUG_DEBUG (Analyzer): Is single subline in document. Returning False.")
            return False

        is_odd_qtextblock_editor = (subline_qtextblock_number_in_editor + 1) % 2 != 0
        if is_target_for_debug: log_debug(f"      ORANGE_BUG_DEBUG (Analyzer): is_odd_qtextblock_editor: {is_odd_qtextblock_editor}")
        if not is_odd_qtextblock_editor:
            return False

        text_no_dots = convert_dots_to_spaces_from_editor(subline_text)
        if ALL_TAGS_PATTERN.search(text_no_dots):
            if is_target_for_debug: log_debug(f"      ORANGE_BUG_DEBUG (Analyzer): Contains tags. Returning False.")
            return False

        text_no_tags_for_empty_check = remove_all_tags(text_no_dots)
        stripped_text_no_tags_for_empty_check = text_no_tags_for_empty_check.strip()
        is_content_empty_or_zero = not stripped_text_no_tags_for_empty_check or stripped_text_no_tags_for_empty_check == "0"
        if is_target_for_debug: log_debug(f"      ORANGE_BUG_DEBUG (Analyzer): stripped_text_no_tags_for_empty_check='{repr(stripped_text_no_tags_for_empty_check)}', is_content_empty_or_zero={is_content_empty_or_zero}. Returning {is_content_empty_or_zero}")
        return is_content_empty_or_zero

    def _check_single_word_subline_zmc(self, subline_text: str) -> bool:
        text_no_tags = remove_all_tags(subline_text).strip()
        if not text_no_tags: # Порожній рядок не є одним словом
            return False
        
        # Розділяємо на "слова" (послідовності не-пробільних символів)
        words = text_no_tags.split()
        
        # Якщо слів більше одного, це не "одне слово"
        if len(words) > 1:
            return False
        
        # Якщо слів рівно одне, перевіряємо, чи це не просто розділовий знак
        if len(words) == 1:
            word = words[0]
            # Видаляємо кінцеві розділові знаки для перевірки, чи залишилося щось ще
            # Це допоможе відрізнити "слово." від просто "."
            # Патерн для слів (послідовність букв/цифр)
            word_content_pattern = re.compile(r'[\wа-яА-ЯіїІїЄєґҐ]+') 
            if word_content_pattern.search(word):
                return True # Є буквено-цифровий вміст, отже це слово

        return False


    def analyze_subline(self,
                        text: str,
                        next_text: Optional[str],
                        subline_number_in_data_string: int, # 0-based index of the logical subline within the data string
                        qtextblock_number_in_editor: int,   # 0-based index of the QTextBlock in the editor
                        is_last_subline_in_data_string: bool,
                        editor_font_map: dict,
                        editor_line_width_threshold: int,
                        full_data_string_text_for_logical_check: str,
                        is_target_for_debug: bool = False) -> Set[str]:

        if is_target_for_debug:
            log_debug(f"  ORANGE_BUG_DEBUG (Analyzer): analyze_subline: text='{repr(text)}', next_text='{repr(next_text)}', sub_num_data={subline_number_in_data_string}, qblk_num_edit={qtextblock_number_in_editor}, is_last_sub_data={is_last_subline_in_data_string}, full_ds_text='{repr(full_data_string_text_for_logical_check)}'")

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
            elif is_target_for_debug:
                 log_debug(f"    ORANGE_BUG_DEBUG (Analyzer): analyze_subline: Could not determine is_single_doc_block_for_display_check. Active editor or document missing.")

        is_logically_single_and_empty_data_string_check = (full_data_string_text_for_logical_check == "" and subline_number_in_data_string == 0 and is_last_subline_in_data_string)
        if is_target_for_debug:
            log_debug(f"    ORANGE_BUG_DEBUG (Analyzer): analyze_subline: is_logically_single_and_empty_data_string_check={is_logically_single_and_empty_data_string_check}")


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

        if is_target_for_debug: log_debug(f"    ORANGE_BUG_DEBUG (Analyzer): analyze_subline: is_odd_logical_subline={is_odd_logical_subline}, is_only_logical_subline_in_data_string={is_only_logical_subline_in_data_string}")

        if is_odd_logical_subline and not is_only_logical_subline_in_data_string:
            if not ALL_TAGS_PATTERN.search(text_with_spaces):
                text_no_tags_for_logical_empty_check = remove_all_tags(text_with_spaces)
                stripped_text_no_tags_for_logical_empty_check = text_no_tags_for_logical_empty_check.strip()
                is_content_empty_or_zero_logical = not stripped_text_no_tags_for_logical_empty_check or stripped_text_no_tags_for_logical_empty_check == "0"
                if is_target_for_debug: log_debug(f"    ORANGE_BUG_DEBUG (Analyzer): analyze_subline: LOGICAL CHECK: stripped_text_no_tags_for_logical_empty_check='{repr(stripped_text_no_tags_for_logical_empty_check)}', is_content_empty_or_zero_logical={is_content_empty_or_zero_logical}")
                if is_content_empty_or_zero_logical:
                    found_problems.add(self.problem_ids.PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL)
        
        # Перевірка на одне слово
        # Застосовуємо, якщо:
        # 1. Це НЕ перший логічний підрядок у рядку даних (subline_number_in_data_string > 0)
        # 2. І поточний логічний підрядок є непарним (is_odd_logical_subline)
        if subline_number_in_data_string > 0 and is_odd_logical_subline:
            if self._check_single_word_subline_zmc(text_with_spaces):
                found_problems.add(self.problem_ids.PROBLEM_SINGLE_WORD_SUBLINE)


        for tag_match in ALL_TAGS_PATTERN.finditer(text_with_spaces):
            tag = tag_match.group(0)
            if not self.tag_manager.is_tag_legitimate(tag):
                found_problems.add(self.problem_ids.PROBLEM_TAG_WARNING)
                log_debug(f"Found illegitimate tag '{tag}' in subline: '{text_with_spaces}'")
                break

        if is_target_for_debug: log_debug(f"  ORANGE_BUG_DEBUG (Analyzer): analyze_subline returning problems: {found_problems}")
        return found_problems