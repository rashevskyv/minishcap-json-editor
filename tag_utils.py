import re
from utils import log_debug # Changed from .utils

def replace_tags_based_on_original(pasted_segment, original_text):
    log_debug(f"replace_tags_based_on_original: Called with pasted_segment='{repr(pasted_segment)}', original_text='{repr(original_text)}'")

    pasted_tags_content = re.findall(r'\[(.*?)\]', pasted_segment)
    original_tags_full = re.findall(r'\{.*?\}', original_text)
    log_debug(f"Found {len(pasted_tags_content)} content tags in pasted segment: {pasted_tags_content}")
    log_debug(f"Found {len(original_tags_full)} full tags in original text: {original_tags_full}")

    if len(pasted_tags_content) != len(original_tags_full):
        log_debug(f"Warning: Tag count mismatch. Pasted content tags: {len(pasted_tags_content)}, Original full tags: {len(original_tags_full)}. Skipping tag replacement for this segment.")
        return pasted_segment

    modified_segment = pasted_segment
    pasted_tags_full = re.findall(r'\[.*?\]', pasted_segment)
    log_debug(f"Found {len(pasted_tags_full)} full tags in pasted segment: {pasted_tags_full}")


    if len(pasted_tags_full) != len(original_tags_full):
        log_debug(f"Warning: Full tag count mismatch during replacement. Pasted full tags: {len(pasted_tags_full)}, Original full tags: {len(original_tags_full)}. Skipping.")
        return pasted_segment

    for i in range(len(pasted_tags_full)):
        tag_to_replace = pasted_tags_full[i]
        replacement_tag = original_tags_full[i]
        log_debug(f"Replacing '{tag_to_replace}' with '{replacement_tag}'")
        modified_segment = modified_segment.replace(tag_to_replace, replacement_tag, 1)

    log_debug(f"Tag replacement done. Result: '{repr(modified_segment)}'")
    return modified_segment