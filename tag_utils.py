import re
from utils import log_debug 

# Статуси, які може повертати функція аналізу
TAG_STATUS_OK = "OK"
TAG_STATUS_UNRESOLVED_BRACKETS = "UNRESOLVED_BRACKETS" # Є [...]
TAG_STATUS_MISMATCHED_CURLY = "MISMATCHED_CURLY"     # Немає [...], але кількість {...} не збігається

def apply_default_mappings_only(text_segment: str, default_mappings: dict) -> tuple[str, bool]:
    if not default_mappings or not text_segment:
        return text_segment, False
    
    modified_segment = str(text_segment)
    changed = False
    for short_tag, full_tag in default_mappings.items():
        if short_tag in modified_segment:
            # Замінюємо всі входження, щоб коректно обробляти кілька однакових тегів
            modified_segment = modified_segment.replace(short_tag, full_tag)
            changed = True
            # log_debug(f"TagUtils: Applied mapping: '{short_tag}' -> '{full_tag}'")
    return modified_segment, changed


def analyze_tags_for_issues(processed_text: str, original_text: str) -> tuple[str, str]:
    """
    Аналізує processed_text (де [...] ВЖЕ МАЛИ БУТИ замінені на {...})
    на наявність залишкових [...] тегів та відповідність кількості {...} тегів з original_text.

    Args:
        processed_text (str): Текст після застосування default_mappings.
        original_text (str): Оригінальний текст для порівняння кількості {...} тегів.

    Returns:
        tuple[str, str]: Кортеж, що містить:
                         - Статус (TAG_STATUS_OK, TAG_STATUS_UNRESOLVED_BRACKETS, TAG_STATUS_MISMATCHED_CURLY).
                         - Повідомлення про помилку/деталі (може бути порожнім для OK).
    """
    remaining_pasted_bracket_tags = re.findall(r'\[[^\]]*\]', processed_text)
    final_pasted_curly_tags = re.findall(r'\{[^}]*\}', processed_text)
    original_tags_curly_all = re.findall(r'\{[^}]*\}', original_text)

    num_remaining_bracket = len(remaining_pasted_bracket_tags)
    num_final_pasted_curly = len(final_pasted_curly_tags)
    num_original_curly = len(original_tags_curly_all)

    if num_remaining_bracket > 0:
        error_msg = (f"Unresolved editor tags [...] found: {remaining_pasted_bracket_tags}.")
        log_debug(f"TAG_UTIL_ANALYZE_ERROR (Unresolved brackets): {error_msg} in '{processed_text[:80]}...'")
        return TAG_STATUS_UNRESOLVED_BRACKETS, error_msg

    if num_final_pasted_curly != num_original_curly:
        error_msg = (f"Tag count mismatch for game engine tags {{...}}. Processed has {num_final_pasted_curly} "
                     f"(tags: {final_pasted_curly_tags}), original has {num_original_curly} (tags: {original_tags_curly_all}).")
        log_debug(f"TAG_UTIL_ANALYZE_ERROR (Curly Mismatch): {error_msg} for processed='{processed_text[:80]}...', original='{original_text[:80]}...'")
        return TAG_STATUS_MISMATCHED_CURLY, error_msg
    
    return TAG_STATUS_OK, ""


# replace_tags_based_on_original - стара назва, замінимо її логіку
# Тепер ця функція буде лише обгорткою, якщо потрібно зберегти стару сигнатуру десь,
# або її можна повністю замінити на analyze_tags_for_issues у всіх місцях виклику.
# Для чистоти коду, краще замінити виклики.
# Я залишу її поки що закоментованою, якщо вона десь ще використовується з очікуванням старої сигнатури.
# def replace_tags_based_on_original(processed_pasted_segment: str, 
#                                    original_text: str, 
#                                    default_tag_mappings_from_settings: dict 
#                                    ) -> tuple[str, bool, str]:
#     status, error_message = analyze_tags_for_issues(processed_pasted_segment, original_text)
#     success = (status == TAG_STATUS_OK)
#     return processed_pasted_segment, success, error_message