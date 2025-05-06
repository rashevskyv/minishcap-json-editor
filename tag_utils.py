import re
from utils import log_debug

def replace_tags_based_on_original(pasted_segment: str, 
                                   original_text: str, 
                                   default_mappings: dict) -> tuple[str, bool, str]:
    """
    Замінює теги у pasted_segment.

    Стратегія:
    1. Якщо кількість тегів [...] у pasted_segment збігається з кількістю тегів {...}
       в original_text, виконується повна порядкова заміна.
    2. Якщо кількість НЕ збігається (це "проблема"):
       - У pasted_segment замінюються тільки ті теги [...], які є ключами
         в default_mappings, на їхні відповідники {...}.
       - Решта тегів [...] залишаються без змін.
       - Функція повертає success=False та повідомлення про невідповідність.

    Повертає:
        - modified_segment (str): Рядок з обробленими тегами.
        - success (bool): True, якщо була успішна повна порядкова заміна.
                          False, якщо кількість тегів не збіглася (навіть якщо
                          деякі теги були замінені по default_mappings).
        - error_message (str): Повідомлення про невідповідність кількості тегів,
                                якщо success is False.
    """
    log_debug(f"replace_tags_based_on_original: Pasted='{repr(pasted_segment)}', Original='{repr(original_text)}'")
    if default_mappings: # Логуємо тільки якщо словник є
        log_debug(f"Using default_mappings: {default_mappings}")

    pasted_tags_bracket = re.findall(r'\[.*?\]', pasted_segment)
    original_tags_curly = re.findall(r'\{.*?\}', original_text)
    
    num_pasted_bracket = len(pasted_tags_bracket)
    num_original_curly = len(original_tags_curly)

    log_debug(f"Found {num_pasted_bracket} tags [...] in pasted: {pasted_tags_bracket}")
    log_debug(f"Found {num_original_curly} tags {{...}} in original: {original_tags_curly}")

    # Стратегія 1: Кількість тегів збігається - повна порядкова заміна
    if num_pasted_bracket == num_original_curly:
        if num_pasted_bracket == 0: # Немає тегів
            log_debug("Strategy 1: No tags in either. Returning pasted segment as is (success).")
            return pasted_segment, True, ""
        
        log_debug("Strategy 1: Tag counts match. Attempting full sequential replacement.")
        modified_segment = pasted_segment
        # Робимо копію списку, щоб не змінювати оригінальний pasted_tags_bracket під час ітерації
        # хоча тут ми ітеруємо по індексах, тож це не критично.
        # Але для заміни краще мати чіткий список оригінальних тегів.
        
        # Щоб коректно замінювати, якщо теги [...] однакові, треба замінювати по одному
        current_pos = 0
        temp_segment_parts = []
        for i in range(num_pasted_bracket):
            tag_to_replace = pasted_tags_bracket[i]
            # Знаходимо перше входження цього тегу після current_pos
            match = re.search(re.escape(tag_to_replace), modified_segment[current_pos:])
            if match:
                start, end = match.span()
                start += current_pos
                end += current_pos
                
                temp_segment_parts.append(modified_segment[current_pos:start])
                temp_segment_parts.append(original_tags_curly[i])
                log_debug(f"Strategy 1: Sequentially replaced '{tag_to_replace}' with '{original_tags_curly[i]}'")
                current_pos = end
            else:
                # Такого не має бути, якщо pasted_tags_bracket зібрані з modified_segment
                log_debug(f"Strategy 1 Error: Could not find '{tag_to_replace}' for sequential replacement. This is unexpected.")
                # У цьому випадку краще повернути помилку, бо логіка порушена
                return pasted_segment, False, "Internal error during sequential tag replacement."

        temp_segment_parts.append(modified_segment[current_pos:])
        modified_segment = "".join(temp_segment_parts)

        log_debug(f"Strategy 1: Full sequential replacement result: '{repr(modified_segment)}'")
        return modified_segment, True, ""

    # Стратегія 2: Кількість тегів НЕ збігається - "проблемний" рядок
    # Замінюємо тільки ті теги, що є в default_mappings.
    # Решту [...] тегів залишаємо як є.
    # Повертаємо success=False, щоб позначити, що була невідповідність.
    else:
        error_msg = (f"Tag count mismatch. Pasted has {num_pasted_bracket} tags [...], "
                     f"original has {num_original_curly} tags ({{...}}). "
                     "Attempting to replace known tags from default mappings.")
        log_debug(f"Strategy 2: {error_msg}")
        
        modified_segment = pasted_segment
        if default_mappings:
            for short_tag, full_tag in default_mappings.items():
                if short_tag in modified_segment: # Перевіряємо, чи є такий тег у рядку
                    count_before = modified_segment.count(short_tag)
                    modified_segment = modified_segment.replace(short_tag, full_tag)
                    if count_before > 0:
                        log_debug(f"Strategy 2 (Default mapping): Replaced '{short_tag}' with '{full_tag}' (occurrences: {count_before}).")
        
        log_debug(f"Strategy 2: Result after default mappings (will be marked as problematic): '{repr(modified_segment)}'")
        # Повертаємо модифікований рядок, але з ознакою помилки через невідповідність кількості
        return modified_segment, False, error_msg 