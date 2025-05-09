import datetime
import re

log_debug_enabled = True 

def log_debug(message):
    if not log_debug_enabled:
        return
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] DEBUG: {message}")

SPACE_DOT_SYMBOL = "·" 
ALL_TAGS_PATTERN = re.compile(r'\[[^\]]*\]|\{[^}]*\}')

def convert_spaces_to_dots_for_display(text: str, enable_conversion: bool) -> str:
    if not enable_conversion or text is None:
        return text if text is not None else ""
    
    def replace_match(match):
        return SPACE_DOT_SYMBOL * len(match.group(0))

    processed_text = re.sub(r" {2,}", replace_match, text)
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

def prepare_text_for_tagless_search(text: str, keep_original_case: bool = False) -> str: # Додано параметр
    if text is None:
        return ""
    
    no_tags_text = ALL_TAGS_PATTERN.sub("", text)
    
    text_with_spaces_instead_of_newlines = no_tags_text.replace('\n', ' ')
    
    normalized_spaces_text = re.sub(r' {2,}', ' ', text_with_spaces_instead_of_newlines)
    
    stripped_text = normalized_spaces_text.strip()

    # Параметр keep_original_case тут не використовується, оскільки ця функція
    # лише готує текст, а чутливість до регістру враховується вже при самому пошуку.
    # Однак, якщо ми захочемо, щоб ця функція сама переводила в нижній регістр,
    # то параметр стане в пригоді. Поки що залишимо його для потенційного використання,
    # але сама функція не буде змінювати регістр.
    
    return stripped_text