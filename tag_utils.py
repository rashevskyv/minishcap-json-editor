import re
from utils import log_debug

# PLAYER_PLACEHOLDER_TAG_IN_PASTED та ORIGINAL_PLAYER_NAME_PATTERN більше не потрібні тут,
# оскільки ця функція тепер отримує текст, де [...] вже мали бути замінені.
# Якщо потрібна спеціальна логіка для {Player} (вже у фігурних дужках), 
# вона має бути тут або в AppActionHandler._perform_tag_scan_for_block до цього виклику.

def replace_tags_based_on_original(processed_pasted_segment: str, # Текст після default_mappings
                                   original_text: str, 
                                   default_tag_mappings_from_settings: dict # Можемо ігнорувати, бо вже застосовано
                                   ) -> tuple[str, bool, str]:
    """
    Аналізує processed_pasted_segment (де [...] мали бути замінені на {...})
    на відповідність тегів з original_text.

    Повертає:
        - processed_pasted_segment (str): Вхідний сегмент (не змінюється тут).
        - success (bool): True, якщо не залишилося [...] тегів І кількість тегів {...} збігається.
        - error_message (str): Повідомлення про помилку.
    """
    # log_debug(f"Analyze Tags: ProcessedPasted='{processed_pasted_segment[:80]}...', Original='{original_text[:80]}...'")

    remaining_pasted_bracket_tags = re.findall(r'\[.*?\]', processed_pasted_segment)
    final_pasted_curly_tags = re.findall(r'\{.*?\}', processed_pasted_segment)
    original_tags_curly_all = re.findall(r'\{.*?\}', original_text)

    num_remaining_bracket = len(remaining_pasted_bracket_tags)
    num_final_pasted_curly = len(final_pasted_curly_tags)
    num_original_curly = len(original_tags_curly_all)

    if num_remaining_bracket > 0:
        error_msg = (f"Unresolved tags [...] found: {remaining_pasted_bracket_tags}.")
        log_debug(f"TAG_UTIL_ANALYZE_ERROR (Unresolved brackets): {error_msg} in '{processed_pasted_segment[:80]}...'")
        return processed_pasted_segment, False, error_msg

    if num_final_pasted_curly == num_original_curly:
        # log_debug(f"Tag analysis: Counts for {{...}} match ({num_final_pasted_curly}). Success.")
        return processed_pasted_segment, True, ""
    else:
        error_msg = (f"Tag count mismatch for {{...}} tags. Processed has {num_final_pasted_curly}, "
                     f"original has {num_original_curly}.")
        log_debug(f"TAG_UTIL_ANALYZE_ERROR (Final Mismatch): {error_msg} for processed='{processed_pasted_segment[:80]}...', original='{original_text[:80]}...'")
        return processed_pasted_segment, False, error_msg