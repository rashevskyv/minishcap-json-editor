import datetime
import re
import os

log_debug_enabled = True
LOG_FILE_PATH = "app_debug.log"

if log_debug_enabled:
    try:
        with open(LOG_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(f"Log started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
            f.write("=" * 50 + "\n")
    except Exception as e:
        print(f"CRITICAL: Could not initialize log file {LOG_FILE_PATH}: {e}")
        log_debug_enabled = False


def log_debug(message):
    if not log_debug_enabled:
        return
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    try:
        with open(LOG_FILE_PATH, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] DEBUG: {message}\n")
    except Exception as e:
        print(f"ERROR writing to log file {LOG_FILE_PATH}: {e}. Message: {message}")

SPACE_DOT_SYMBOL = "·"
ALL_TAGS_PATTERN = re.compile(r'\[[^\]]*\]|\{[^}]*\}')
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

def prepare_text_for_tagless_search(text: str, keep_original_case: bool = False) -> str:
    if text is None:
        return ""
    
    no_tags_text = ALL_TAGS_PATTERN.sub("", text)
    
    text_with_spaces_instead_of_newlines = no_tags_text.replace('\n', ' ')
    
    normalized_spaces_text = re.sub(r' {2,}', ' ', text_with_spaces_instead_of_newlines)
    
    stripped_text = normalized_spaces_text.strip()
    
    return stripped_text