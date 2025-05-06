# tag_utils.py
import re
from utils import log_debug

def replace_tags_based_on_original(pasted_segment: str, original_text: str) -> tuple[str, bool, str]:
    """
    Замінює теги [...] у pasted_segment на теги {...} з original_text.

    Повертає:
        - modified_segment (str): Рядок з заміненими тегами (або оригінальний pasted_segment, якщо заміна не вдалася).
        - success (bool): True, якщо всі теги успішно замінені, інакше False.
        - error_message (str): Повідомлення про помилку, якщо success is False.
    """
    log_debug(f"replace_tags_based_on_original: Called with pasted_segment='{repr(pasted_segment)}', original_text='{repr(original_text)}'")

    # Шукаємо теги [...] у вставленому тексті. Ми очікуємо, що це повні теги.
    pasted_tags_full = re.findall(r'\[.*?\]', pasted_segment)
    original_tags_full = re.findall(r'\{.*?\}', original_text)
    
    num_pasted_tags = len(pasted_tags_full)
    num_original_tags = len(original_tags_full)

    log_debug(f"Found {num_pasted_tags} tags [...] in pasted: {pasted_tags_full}")
    log_debug(f"Found {num_original_tags} tags {{...}} in original: {original_tags_full}")

    if num_pasted_tags == 0 and num_original_tags == 0:
        log_debug("No tags in pasted and original. Returning as is.")
        return pasted_segment, True, "" # Немає тегів для заміни, вважаємо успіхом

    if num_pasted_tags != num_original_tags:
        error_msg = (f"Tag count mismatch. Pasted has {num_pasted_tags} tags ([...]), "
                     f"original has {num_original_tags} tags ({{...}}). "
                     "Cannot reliably replace tags.")
        log_debug(f"Warning: {error_msg}")
        return pasted_segment, False, error_msg

    # Якщо кількість тегів збігається (і не нульова)
    modified_segment = pasted_segment
    for i in range(num_pasted_tags):
        tag_to_replace = pasted_tags_full[i]
        replacement_tag = original_tags_full[i]
        # Робимо заміну лише першого входження, щоб уникнути проблем, якщо теги однакові
        modified_segment = modified_segment.replace(tag_to_replace, replacement_tag, 1)
        log_debug(f"Replaced '{tag_to_replace}' with '{replacement_tag}'")

    log_debug(f"Tag replacement successful. Result: '{repr(modified_segment)}'")
    return modified_segment, True, ""