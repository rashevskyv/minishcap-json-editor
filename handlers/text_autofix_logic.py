import re
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QTextCursor
from utils.utils import log_debug, calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN, convert_spaces_to_dots_for_display
from core.tag_utils import TAG_STATUS_OK, TAG_STATUS_CRITICAL, TAG_STATUS_MISMATCHED_CURLY, TAG_STATUS_UNRESOLVED_BRACKETS

# Regex for sentence-ending punctuation followed optionally by a double quote, anchored to the end
SENTENCE_END_PUNCTUATION_PATTERN = re.compile(r'([.,!?]["\']?)$')

class TextAutofixLogic:
    def __init__(self, main_window, data_processor, ui_updater):
        self.mw = main_window
        self.data_processor = data_processor
        self.ui_updater = ui_updater

    def _extract_first_word_with_tags(self, text: str) -> tuple[str, str]:
        if not text.strip():
            return "", text 

        first_word_text = ""
        remaining_text = text
        
        char_idx = 0
        while char_idx < len(text):
            char = text[char_idx]
            if char.isspace():
                if first_word_text: 
                    break
                else: 
                    first_word_text += char
                    char_idx += 1
                    continue
            
            is_tag_char = False
            for tag_match in ALL_TAGS_PATTERN.finditer(text[char_idx:]):
                if tag_match.start() == 0: 
                    tag_content = tag_match.group(0)
                    first_word_text += tag_content
                    char_idx += len(tag_content)
                    is_tag_char = True
                    break
            
            if is_tag_char:
                continue

            first_word_text += char
            char_idx += 1

        remaining_text = text[len(first_word_text):].lstrip()
        return first_word_text.rstrip(), remaining_text

    def _fix_empty_odd_sublines(self, text: str) -> str:
        sub_lines = text.split('\n')
        if len(sub_lines) <= 1:
            return text

        new_sub_lines = []
        for i, sub_line in enumerate(sub_lines):
            is_odd_subline = (i + 1) % 2 != 0
            text_no_tags = remove_all_tags(sub_line)
            stripped_text_no_tags = text_no_tags.strip()
            is_empty_or_zero = not stripped_text_no_tags or stripped_text_no_tags == "0"

            if is_odd_subline and is_empty_or_zero and len(sub_lines) > 1 :
                continue
            new_sub_lines.append(sub_line)
        
        if text and not new_sub_lines:
             return "" 
        
        joined_text = "\n".join(new_sub_lines)
        return joined_text

    def _fix_short_lines(self, text: str) -> str:
        sub_lines = text.split('\n')
        if len(sub_lines) <= 1:
            return text

        made_change_in_this_fix_pass = True 
        while made_change_in_this_fix_pass:
            made_change_in_this_fix_pass = False
            new_sub_lines = list(sub_lines) 
            i = len(new_sub_lines) - 2 
            while i >= 0:
                current_line = new_sub_lines[i]
                next_line = new_sub_lines[i+1]

                current_line_no_tags_stripped = remove_all_tags(current_line).strip()
                if not current_line_no_tags_stripped or SENTENCE_END_PUNCTUATION_PATTERN.search(current_line_no_tags_stripped):
                    i -= 1
                    continue

                first_word_next_raw, rest_of_next_line_raw = self._extract_first_word_with_tags(next_line)
                first_word_next_no_tags = remove_all_tags(first_word_next_raw).strip()

                if not first_word_next_no_tags:
                    i -= 1
                    continue
                
                width_current_line_rstripped = calculate_string_width(remove_all_tags(current_line.rstrip()), self.mw.font_map)
                width_first_word_next = calculate_string_width(first_word_next_no_tags, self.mw.font_map)
                space_width = calculate_string_width(" ", self.mw.font_map)
                
                if width_current_line_rstripped + space_width + width_first_word_next <= self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS:
                    new_current_line_parts = [current_line.rstrip()]
                    if current_line and not current_line.endswith(" "): 
                        new_current_line_parts.append(" ")
                    new_current_line_parts.append(first_word_next_raw)
                    
                    new_sub_lines[i] = "".join(new_current_line_parts)
                    new_sub_lines[i+1] = rest_of_next_line_raw

                    if not new_sub_lines[i+1].strip(): 
                        del new_sub_lines[i+1]
                    
                    made_change_in_this_fix_pass = True
                    sub_lines = list(new_sub_lines) 
                    break 
                i -= 1
            
            if not made_change_in_this_fix_pass:
                break 
                
        return "\n".join(sub_lines)

    def _fix_width_exceeded(self, text: str) -> str:
        sub_lines = text.split('\n')
        made_change_overall = False
        
        new_full_text_lines = []

        for line_idx, current_line_text in enumerate(sub_lines):
            current_processing_line = current_line_text
            temp_newly_created_lines_for_this_original_line = []

            while True: 
                line_width_no_tags = calculate_string_width(remove_all_tags(current_processing_line), self.mw.font_map)

                if line_width_no_tags <= self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS:
                    if current_processing_line or not temp_newly_created_lines_for_this_original_line or \
                       (not current_processing_line and line_idx < len(sub_lines) -1 ): 
                        temp_newly_created_lines_for_this_original_line.append(current_processing_line)
                    break 

                made_change_overall = True
                
                text_fits = ""
                
                line_parts = re.findall(r'(\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', current_processing_line)

                current_temp_width = 0
                last_fit_index = -1
                needs_space_before_next_part = False

                for i, part in enumerate(line_parts):
                    part_no_tags = remove_all_tags(part)
                    part_width = calculate_string_width(part_no_tags, self.mw.font_map)
                    
                    width_to_check = current_temp_width
                    current_needs_space_before = needs_space_before_next_part and not part.isspace() and text_fits and not text_fits.endswith(" ")

                    if current_needs_space_before:
                        width_to_check += calculate_string_width(" ", self.mw.font_map)
                    width_to_check += part_width

                    if width_to_check <= self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS:
                        if current_needs_space_before:
                            text_fits += " "
                        text_fits += part
                        current_temp_width = calculate_string_width(remove_all_tags(text_fits), self.mw.font_map) 
                        last_fit_index = i
                        if not part.isspace():
                            needs_space_before_next_part = True
                        else: 
                            needs_space_before_next_part = False
                    else:
                        break 
                
                if last_fit_index != -1 :
                    text_overflows = "".join(line_parts[last_fit_index + 1:]).lstrip()
                    temp_newly_created_lines_for_this_original_line.append(text_fits.rstrip())
                    current_processing_line = text_overflows
                    if not text_overflows and not current_processing_line: 
                        break
                else: 
                    if line_parts:
                        temp_newly_created_lines_for_this_original_line.append("") 
                        current_processing_line = "".join(line_parts).lstrip() 
                    else: 
                        temp_newly_created_lines_for_this_original_line.append(current_processing_line) 
                        break 
            
            new_full_text_lines.extend(temp_newly_created_lines_for_this_original_line)

        if made_change_overall:
            while new_full_text_lines and not new_full_text_lines[-1].strip() and len(new_full_text_lines) > 1:
                new_full_text_lines.pop()
            return "\n".join(new_full_text_lines)
            
        return text

    def _fix_blue_sublines(self, text: str) -> str:
        sub_lines = text.split('\n')
        if len(sub_lines) < 2: # Rule requires a next line
            return text

        new_sub_lines = []
        i = 0
        changed_in_pass = False
        while i < len(sub_lines):
            current_line_text = sub_lines[i]
            new_sub_lines.append(current_line_text)

            is_odd_subline = (i + 1) % 2 != 0
            if not is_odd_subline:
                i += 1
                continue

            text_no_tags = remove_all_tags(current_line_text)
            stripped_text_no_tags = text_no_tags.strip()

            if not stripped_text_no_tags or not stripped_text_no_tags[0].islower():
                i += 1
                continue
            
            if not SENTENCE_END_PUNCTUATION_PATTERN.search(stripped_text_no_tags):
                i += 1
                continue

            # Check next line
            if i + 1 < len(sub_lines):
                next_line_text = sub_lines[i+1]
                next_line_no_tags = remove_all_tags(next_line_text)
                stripped_next_line_no_tags = next_line_no_tags.strip()
                
                if stripped_next_line_no_tags: # Next line is NOT empty
                    # This is a "blue" line, add an empty line after it
                    new_sub_lines.append("")
                    changed_in_pass = True
            i += 1
        
        if changed_in_pass:
            return "\n".join(new_sub_lines)
        return text


    def auto_fix_current_string(self):
        log_debug(f"TextAutofixLogic.auto_fix_current_string: Called.")
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            QMessageBox.information(self.mw, "Auto-fix", "No string selected to fix.")
            return

        block_idx = self.mw.current_block_idx
        string_idx = self.mw.current_string_idx
        
        current_text, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        
        modified_text = str(current_text)
        max_iterations = 10 
        iterations = 0
        changes_were_made_by_autofix = False
        
        edited_text_edit = self.mw.edited_text_edit
        
        while iterations < max_iterations:
            made_change_in_this_pass = False
            iterations += 1
            log_debug(f"Auto-fix: Iteration {iterations} for string {block_idx}-{string_idx}")

            text_before_this_pass = str(modified_text)

            temp_text_after_empty_fix = self._fix_empty_odd_sublines(modified_text)
            if temp_text_after_empty_fix != modified_text:
                log_debug(f"  Change after empty_odd_fix: '{modified_text[:50]}' -> '{temp_text_after_empty_fix[:50]}'")
                modified_text = temp_text_after_empty_fix
                made_change_in_this_pass = True
            
            temp_text_after_blue_fix = self._fix_blue_sublines(modified_text)
            if temp_text_after_blue_fix != modified_text:
                log_debug(f"  Change after blue_sublines_fix: '{modified_text[:50]}' -> '{temp_text_after_blue_fix[:50]}'")
                modified_text = temp_text_after_blue_fix
                made_change_in_this_pass = True

            temp_text_after_short_fix = self._fix_short_lines(modified_text)
            if temp_text_after_short_fix != modified_text:
                log_debug(f"  Change after short_fix: '{modified_text[:50]}' -> '{temp_text_after_short_fix[:50]}'")
                modified_text = temp_text_after_short_fix
                made_change_in_this_pass = True
            
            temp_text_after_width_fix = self._fix_width_exceeded(modified_text)
            if temp_text_after_width_fix != modified_text:
                log_debug(f"  Change after width_fix: '{modified_text[:50]}' -> '{temp_text_after_width_fix[:50]}'")
                modified_text = temp_text_after_width_fix
                made_change_in_this_pass = True
            
            if not made_change_in_this_pass: # Якщо жоден з фіксів не змінив текст, виходимо
                break
        
        if iterations == max_iterations and made_change_in_this_pass:
            log_debug("Auto-fix: Max iterations reached, potential complex case or loop.")
            QMessageBox.warning(self.mw, "Auto-fix", "Auto-fix reached maximum iterations. Result might be incomplete.")

        final_text_to_apply = modified_text
        
        if final_text_to_apply != current_text:
            changes_were_made_by_autofix = True
            
            if edited_text_edit:
                text_for_display = convert_spaces_to_dots_for_display(final_text_to_apply, self.mw.show_multiple_spaces_as_dots)
                cursor = edited_text_edit.textCursor()
                cursor.beginEditBlock()
                cursor.select(QTextCursor.Document)
                cursor.insertText(text_for_display)
                cursor.endEditBlock()
                log_debug(f"Auto-fix: Text in edited_text_edit updated directly. Undo available: {edited_text_edit.document().isUndoAvailable()}")

            if self.data_processor.update_edited_data(block_idx, string_idx, final_text_to_apply):
                 self.ui_updater.update_title() 

            self.mw.is_programmatically_changing_text = True
            
            if self.mw.original_text_edit:
                original_text_raw = self.data_processor._get_string_from_source(block_idx, string_idx, self.mw.data, "original_data_for_autofix_view")
                original_text_for_display = convert_spaces_to_dots_for_display(str(original_text_raw), self.mw.show_multiple_spaces_as_dots)
                if self.mw.original_text_edit.toPlainText() != original_text_for_display:
                    self.mw.original_text_edit.setPlainText(original_text_for_display)

            self.mw.app_action_handler._perform_issues_scan_for_block(block_idx, is_single_block_scan=True, use_default_mappings_in_scan=False)
            self.ui_updater.populate_strings_for_block(block_idx) 
            self.ui_updater.update_status_bar()
            self.ui_updater.synchronize_original_cursor()
            
            self.mw.is_programmatically_changing_text = False
            
            if hasattr(self.mw, 'statusBar'):
                self.mw.statusBar.showMessage("Auto-fix applied to current string.", 2000)
        else:
            if hasattr(self.mw, 'statusBar'):
                self.mw.statusBar.showMessage("Auto-fix: No changes made.", 2000)

        log_debug(f"TextAutofixLogic.auto_fix_current_string: Finished.")