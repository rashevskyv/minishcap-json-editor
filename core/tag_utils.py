import re
from utils.utils import log_debug

TAG_STATUS_OK = "OK"
TAG_STATUS_CRITICAL = "CRITICAL_ERROR" 
TAG_STATUS_UNRESOLVED_BRACKETS = "UNRESOLVED_BRACKETS" 
TAG_STATUS_MISMATCHED_CURLY = "MISMATCHED_CURLY"     
TAG_STATUS_WARNING = "WARNING" 

ORIGINAL_PLAYER_TAG = "{Player}"
PLAYER_PSEUDO_TAG_FOR_COUNTING = "{PLAYER_CONSTRUCT_INTERNAL}" 

PLAYER_REPLACEMENT_CURLY_PATTERN = re.compile(
    r"(\{Color:[^}]+\}|Sound:[^}]+\}|Symbol:[^}]+\}|\{[^}:]+\})" 
    r"(\s*[^\{\[]+?\s*)" 
    r"(\{Color:[^}]+\}|Sound:[^}]+\}|Symbol:[^}]+\}|\{[^}:]+\}|\{\/c\})", 
    re.IGNORECASE
)
ANY_TAG_PATTERN = re.compile(r'\[[^\]]*\]|\{[^}]*\}')

def apply_default_mappings_only(text_segment: str, default_mappings: dict) -> tuple[str, bool]:
    if not default_mappings or not text_segment: return text_segment, False
    modified_segment = str(text_segment); changed = False
    sorted_keys = sorted(default_mappings.keys(), key=len, reverse=True)
    for short_tag in sorted_keys:
        full_tag = default_mappings[short_tag]
        if short_tag in modified_segment:
            modified_segment = modified_segment.replace(short_tag, full_tag); changed = True
    return modified_segment, changed

def analyze_tags_for_issues(processed_text: str, original_text: str, editor_player_tag:str = "[ІМ'Я ГРАВЦЯ]") -> tuple[str, str]:
    temp_processed_text = processed_text
    temp_original_text = original_text
    num_original_player_tags = temp_original_text.count(ORIGINAL_PLAYER_TAG)
    if num_original_player_tags > 0:
        processed_player_constructs_count = 0
        def collapse_player_construct_in_processed(match_obj):
            nonlocal processed_player_constructs_count
            if processed_player_constructs_count < num_original_player_tags:
                processed_player_constructs_count += 1
                return PLAYER_PSEUDO_TAG_FOR_COUNTING
            return match_obj.group(0)
        new_text = PLAYER_REPLACEMENT_CURLY_PATTERN.sub(collapse_player_construct_in_processed, temp_processed_text, count=num_original_player_tags)
        temp_processed_text = new_text 
        temp_original_text = temp_original_text.replace(ORIGINAL_PLAYER_TAG, PLAYER_PSEUDO_TAG_FOR_COUNTING)
    
    remaining_brackets = [
        tag for tag in ANY_TAG_PATTERN.findall(temp_processed_text) 
        if tag.startswith('[') and tag != editor_player_tag
    ]
    if remaining_brackets:
        error_msg = (f"Unresolved editor tags [...] found (excluding player placeholder): {remaining_brackets}.")
        return TAG_STATUS_UNRESOLVED_BRACKETS, error_msg 

    final_pasted_curly_tags = re.findall(r'\{[^}]*\}', temp_processed_text)
    original_tags_curly_all = re.findall(r'\{[^}]*\}', temp_original_text)
    if len(final_pasted_curly_tags) != len(original_tags_curly_all):
        error_msg = (f"Tag count mismatch for {{...}} tags. Processed (adj.): {len(final_pasted_curly_tags)} "
                     f"(tags: {final_pasted_curly_tags}), Original (adj.): {len(original_tags_curly_all)} (tags: {original_tags_curly_all}).\n"
                     f"Original processed: '{processed_text[:100]}...'\nOriginal original: '{original_text[:100]}...'")
        return TAG_STATUS_MISMATCHED_CURLY, error_msg
    return TAG_STATUS_OK, ""


def process_segment_tags_aggressively(
    segment_to_insert: str, 
    original_text_for_tags: str, 
    default_mappings: dict,
    editor_player_tag_const: str 
) -> tuple[str, str, str]:
    log_debug(f"Aggressive Processing V14 (default_mappings ignored for step 1): Input Segment='{segment_to_insert[:80]}', Original='{original_text_for_tags[:80]}'")
    
    current_segment_state = str(segment_to_insert)

    segment_had_slash00 = "/00" in current_segment_state
    original_had_slash00 = "/00" in original_text_for_tags
    if segment_had_slash00 and not original_had_slash00: current_segment_state = current_segment_state.replace("/00", "")
    elif segment_had_slash00 and original_had_slash00: return current_segment_state, TAG_STATUS_CRITICAL, "'/00' present in both."
    text_without_any_tags = re.sub(r'\[[^\]]*\]|\{[^}]*\}', '', current_segment_state)
    if '/' in text_without_any_tags: return current_segment_state, TAG_STATUS_CRITICAL, "Segment contains '/' outside of tags."

    segment_for_analysis = current_segment_state
    log_debug(f"  Segment prepared for analysis (default_mappings step bypassed): '{segment_for_analysis[:80]}'")

    status, msg = analyze_tags_for_issues(segment_for_analysis, original_text_for_tags, editor_player_tag_const)

    if status == TAG_STATUS_OK:
        log_debug(f"  - SUCCESS (OK on initial analysis): '{segment_for_analysis[:80]}'")
        return segment_for_analysis, TAG_STATUS_OK, msg 
    
    elif status == TAG_STATUS_UNRESOLVED_BRACKETS:
        log_debug(f"  - UNRESOLVED BRACKETS: {msg}. Attempting order-based replacement.")
        
        pasted_bracket_tags_remaining = re.findall(r'\[[^\]]*\]', segment_for_analysis) 
        original_curly_tags_list = re.findall(r'\{[^}]*\}', original_text_for_tags)

        if len(pasted_bracket_tags_remaining) == len(original_curly_tags_list):
            log_debug(f"    - Counts match for order-based: {len(pasted_bracket_tags_remaining)}")
            
            temp_segment = str(segment_for_analysis)
            current_curly_idx = 0
            def replace_bracket_by_order_func(match_obj):
                nonlocal current_curly_idx
                tag_to_replace = match_obj.group(0)
                if tag_to_replace != editor_player_tag_const: 
                    if current_curly_idx < len(original_curly_tags_list):
                        replacement_tag = original_curly_tags_list[current_curly_idx]
                        current_curly_idx +=1
                        log_debug(f"      Replacing '{tag_to_replace}' with '{replacement_tag}'")
                        return replacement_tag
                return tag_to_replace 
            
            segment_fully_replaced = re.sub(r'\[[^\]]*\]', replace_bracket_by_order_func, temp_segment)
            
            status_after_order, msg_after_order = analyze_tags_for_issues(segment_fully_replaced, original_text_for_tags, editor_player_tag_const)
            if status_after_order == TAG_STATUS_OK:
                log_debug(f"    - SUCCESS after order-based replacement: '{segment_fully_replaced[:80]}'")
                return segment_fully_replaced, TAG_STATUS_OK, "" 
            else: 
                log_debug(f"    - CRITICAL: Order-based failed final check: {msg_after_order}. Fallback to segment_for_analysis.")
                return segment_for_analysis, status_after_order, msg_after_order
        else: 
            log_debug(f"    - CRITICAL: Count mismatch for order-based. Left_Brackets={len(pasted_bracket_tags_remaining)}, Orig_Curly={len(original_curly_tags_list)}.")
            return segment_for_analysis, TAG_STATUS_UNRESOLVED_BRACKETS, msg 
            
    elif status == TAG_STATUS_MISMATCHED_CURLY:
        log_debug(f"  - WARNING (MISMATCHED_CURLY on initial analysis): {msg}")
        return segment_for_analysis, TAG_STATUS_WARNING, msg 
    else: 
        log_debug(f"  - {status} (from analyze_tags_for_issues): {msg}")
        return segment_for_analysis, status, msg