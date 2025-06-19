import datetime
import re
import os
from plugins.pokemon_fr.config import P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER


SPACE_DOT_SYMBOL = "·"
ALL_TAGS_PATTERN = re.compile(r'\[[^\]]*\]|\{[^}]*\}|' + re.escape(P_VISUAL_EDITOR_MARKER) + r'|' + re.escape(L_VISUAL_EDITOR_MARKER))
DEFAULT_CHAR_WIDTH_FALLBACK = 6

def remove_all_tags(text: str) -> str:
    if text is None:
        return ""
    return ALL_TAGS_PATTERN.sub("", text)

def calculate_string_width(text: str, font_map: dict, default_char_width: int = DEFAULT_CHAR_WIDTH_FALLBACK) -> int:
    if text is None or not font_map:
        return 0
    
    text_no_tags = remove_all_tags(text)
    total_width = 0
    for char_code in text_no_tags:
        char_data = font_map.get(char_code)
        if char_data and isinstance(char_data, dict) and 'width' in char_data:
            total_width += char_data['width']
        else:
            total_width += default_char_width
    return total_width

def convert_spaces_to_dots_for_display(text: str, enable_conversion: bool) -> str:
    if not enable_conversion or text is None:
        return text if text is not None else ""
    
    # Замінюємо 2+ пробіли
    processed_text = re.sub(r" {2,}", lambda m: SPACE_DOT_SYMBOL * len(m.group(0)), text)
    
    # Замінюємо пробіл на початку рядка (якщо за ним не йде ще один пробіл, оброблений вище)
    processed_text = re.sub(r"^ (?=[^ ])", SPACE_DOT_SYMBOL, processed_text)
    
    # Замінюємо пробіл в кінці рядка (якщо перед ним не стоїть пробіл)
    processed_text = re.sub(r"(?<![ ]) $", SPACE_DOT_SYMBOL, processed_text)
    
    return processed_text

def convert_dots_to_spaces_from_editor(text: str) -> str:
    if text is None:
        return ""
    return text.replace(SPACE_DOT_SYMBOL, " ")

def remove_curly_tags(text: str) -> str:
    if text is None:
        return ""
    return re.sub(r"\{[^}]*\}", "", text)

def convert_raw_to_display_text(raw_text: str, show_dots: bool, newline_char_for_preview: str = "") -> str:
    if raw_text is None:
        return ""
    
    text_with_dots = convert_spaces_to_dots_for_display(str(raw_text), show_dots)
    
    if newline_char_for_preview:
        text_with_dots = text_with_dots.replace('\n', newline_char_for_preview)
        
    return text_with_dots

def prepare_text_for_tagless_search(text: str, keep_original_case: bool = False) -> str:
    if text is None:
        return ""
    
    no_tags_text = ALL_TAGS_PATTERN.sub("", text)
    
    text_with_spaces_instead_of_newlines = no_tags_text.replace('\n', ' ')
    
    normalized_spaces_text = re.sub(r' {2,}', ' ', text_with_spaces_instead_of_newlines)
    
    stripped_text = normalized_spaces_text.strip()
    
    return stripped_text