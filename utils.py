# utils.py
import datetime
import re

log_debug_enabled = True # Можна керувати цим глобально

def log_debug(message):
    if not log_debug_enabled:
        return
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] DEBUG: {message}")

# Функція clean_newline_at_end ВИДАЛЕНА

SPACE_DOT_SYMBOL = "·" # U+00B7 MIDDLE DOT

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