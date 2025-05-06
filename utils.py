import datetime
import re

def log_debug(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")

def replace_tags_based_on_original(pasted_segment, original_text):
    pasted_tags_content = re.findall(r'\[(.*?)\]', pasted_segment)
    original_tags_full = re.findall(r'\{.*?\}', original_text)

    if len(pasted_tags_content) != len(original_tags_full):
        log_debug(f"Warning: Tag count mismatch. Pasted: {len(pasted_tags_content)}, Original: {len(original_tags_full)}. Skipping tag replacement for this segment.")
        log_debug(f"  Pasted segment: {repr(pasted_segment)}")
        log_debug(f"  Original text: {repr(original_text)}")
        return pasted_segment

    modified_segment = pasted_segment
    pasted_tags_full = re.findall(r'\[.*?\]', pasted_segment)

    if len(pasted_tags_full) != len(original_tags_full):
        log_debug(f"Warning: Full tag count mismatch during replacement. Pasted: {len(pasted_tags_full)}, Original: {len(original_tags_full)}. Skipping.")
        return pasted_segment

    for i in range(len(pasted_tags_full)):
        tag_to_replace = pasted_tags_full[i]
        replacement_tag = original_tags_full[i]
        modified_segment = modified_segment.replace(tag_to_replace, replacement_tag, 1)

    log_debug(f"Tag replacement done. Result: {repr(modified_segment)}")
    return modified_segment


def clean_newline_at_end(text):
    """Removes \n at the end of a string, if present. If the string is only '\n', returns ''."""
    if text == "\n":
        return ""
    elif text.endswith("\n"):
        return text[:-1]
    return text