import os
from PyQt5.QtWidgets import QMessageBox
from handlers.base_handler import BaseHandler
from utils import log_debug, convert_dots_to_spaces_from_editor # Додаємо, якщо ще не було
from tag_utils import replace_tags_based_on_original # Функція аналізу
# Потрібна функція, що просто застосовує словник
# Якщо її немає в tag_utils, можна додати або реалізувати тут локально

def apply_default_mappings_only(text_segment: str, default_mappings: dict) -> tuple[str, bool]:
    """
    Просто застосовує default_mappings до тексту, замінюючи [...] на {...}.
    Повертає (змінений_текст, чи_були_зміни).
    """
    if not default_mappings or not text_segment:
        return text_segment, False
    
    modified_segment = str(text_segment)
    changed = False
    for short_tag, full_tag in default_mappings.items():
        if short_tag in modified_segment:
            modified_segment = modified_segment.replace(short_tag, full_tag)
            changed = True
            # log_debug(f"Applied mapping: '{short_tag}' -> '{full_tag}'") 
    return modified_segment, changed


class AppActionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)

    def save_data_action(self, ask_confirmation=True):
        # ... (код без змін) ...
        log_debug(f"--> AppActionHandler: save_data_action called. ask_confirmation={ask_confirmation}, current unsaved={self.mw.unsaved_changes}")
        if self.mw.json_path and not self.mw.edited_json_path:
            self.mw.edited_json_path = self.mw._derive_edited_path(self.mw.json_path)
            self.ui_updater.update_statusbar_paths()
        current_block_idx_before_save = self.mw.current_block_idx; current_string_idx_before_save = self.mw.current_string_idx
        save_success = self.data_processor.save_current_edits(ask_confirmation=ask_confirmation)
        if save_success:
            self.ui_updater.update_title() 
            self.mw.is_programmatically_changing_text = True 
            if current_block_idx_before_save != -1:
                 self.mw.current_block_idx = current_block_idx_before_save 
                 self.mw.current_string_idx = current_string_idx_before_save
                 self.ui_updater.populate_strings_for_block(self.mw.current_block_idx) 
            else: self.ui_updater.populate_strings_for_block(-1)
            self.ui_updater.update_statusbar_paths() 
            self.mw.is_programmatically_changing_text = False 
        else: self.ui_updater.update_title() 
        return save_success

    def handle_close_event(self, event):
        # ... (код без змін) ...
        log_debug("--> AppActionHandler: handle_close_event called.")
        if self.mw.unsaved_changes:
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Save changes before exiting?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if self.save_data_action(ask_confirmation=True): event.accept()
                else: event.ignore()
            elif reply == QMessageBox.Discard: event.accept()
            else: event.ignore()
        else: event.accept()
        log_debug("<-- AppActionHandler: handle_close_event finished.")

    def _perform_tag_scan_for_block(self, block_idx: int, is_single_block_scan: bool = False) -> tuple[int, bool]:
        """
        Виконує сканування тегів для вказаного блоку.
        1. Примусово застосовує default_mappings до тексту з edited_data, оновлює edited_data.
        2. Аналізує оновлений текст на відповідність тегів оригіналу.
        3. Оновлює self.mw.problem_lines_per_block.
        Повертає (кількість проблемних рядків, чи були зроблені зміни в edited_data).
        """
        log_debug(f"AppActionHandler: Starting tag scan for block_idx: {block_idx}")
        if not (0 <= block_idx < len(self.mw.data)):
            log_debug(f"AppActionHandler: Invalid block_idx {block_idx} for scan.")
            return 0, False

        block_key = str(block_idx)
        current_block_problem_indices = set()
        changes_made_to_edited_data_in_this_block = False
        
        num_strings_in_block = len(self.mw.data[block_idx])

        for string_idx in range(num_strings_in_block):
            # Етап 1: Примусова нормалізація тегів у даних
            text_before_normalization, source = self.data_processor.get_current_string_text(block_idx, string_idx)
            
            normalized_text, was_normalized = apply_default_mappings_only(
                text_before_normalization,
                self.mw.default_tag_mappings
            )
            
            if was_normalized:
                log_debug(f"Rescan Blk{block_idx}-Str{string_idx}: Normalized tags. Before: '{text_before_normalization[:60]}...', After: '{normalized_text[:60]}...'")
                # Оновлюємо edited_data нормалізованим текстом
                self.data_processor.update_edited_data(block_idx, string_idx, normalized_text)
                changes_made_to_edited_data_in_this_block = True
                text_to_analyze = normalized_text # Для подальшого аналізу беремо вже нормалізований
            else:
                text_to_analyze = text_before_normalization # Нормалізація нічого не змінила
            
            # Етап 2: Аналіз на проблеми (вже з нормалізованим текстом)
            original_text_for_comparison = self.mw.data[block_idx][string_idx]

            # replace_tags_based_on_original тепер має аналізувати текст, де [...] вже замінені на {...}
            # Її завдання - перевірити кількість {...} та наявність залишків [...], якщо default_mappings не все покрили.
            _processed_text_after_analysis, tags_ok, tag_error_msg = replace_tags_based_on_original(
                text_to_analyze, # Передаємо текст, який вже пройшов default_mappings
                original_text_for_comparison,
                {} # Передаємо порожній словник, бо default_mappings вже застосовані
            )
            
            # log_debug(f"Rescan Blk{block_idx}-Str{string_idx}: Analysis result: tags_ok={tags_ok}, msg='{tag_error_msg}'")

            if not tags_ok:
                current_block_problem_indices.add(string_idx)
                # log_debug(f"AppActionHandler: Tag issue found in block {block_idx}, string {string_idx}: {tag_error_msg}")
        
        # Оновлюємо глобальний словник проблем
        if current_block_problem_indices:
            self.mw.problem_lines_per_block[block_key] = current_block_problem_indices
        elif block_key in self.mw.problem_lines_per_block: 
            del self.mw.problem_lines_per_block[block_key]
        
        # Оновлюємо відображення для цього блоку (лічильник та фон)
        if hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
            self.ui_updater.update_block_item_text_with_problem_count(block_idx)
        
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if is_single_block_scan and self.mw.current_block_idx == block_idx and preview_edit:
            log_debug(f"Rescan (single block): Refreshing preview for current block {block_idx}")
            # Важливо: populate_strings_for_block має викликатися ПІСЛЯ того, як edited_data оновлено,
            # щоб preview відобразив зміни і правильні проблемні підсвічування.
            # Оскільки is_programmatically_changing_text встановлюється вище, це має бути ОК.
            self.ui_updater.populate_strings_for_block(block_idx) 
        
        return len(current_block_problem_indices), changes_made_to_edited_data_in_this_block

    def rescan_tags_for_single_block(self, block_idx: int = -1):
        if block_idx == -1: block_idx = self.mw.current_block_idx
        if block_idx < 0:
            QMessageBox.information(self.mw, "Rescan Tags", "No block selected to rescan.")
            return
        log_debug(f"<<<<<<<<<< ACTION: Rescan Tags for Block {block_idx} Triggered >>>>>>>>>>")
        
        self.mw.is_programmatically_changing_text = True # Для оновлення edited_data та UI
        num_problems, changes_applied = self._perform_tag_scan_for_block(block_idx, is_single_block_scan=True)
        self.mw.is_programmatically_changing_text = False

        if changes_applied and not self.mw.unsaved_changes:
            self.mw.unsaved_changes = True
            self.ui_updater.update_title()

        if num_problems > 0:
            QMessageBox.information(self.mw, "Rescan Complete", 
                                    f"Block '{self.mw.block_names.get(str(block_idx), str(block_idx))}' has {num_problems} line(s) with tag issues (highlighted). "
                                    f"{'Known tags were auto-corrected.' if changes_applied else 'No data was changed by this scan.'}")
        else:
            QMessageBox.information(self.mw, "Rescan Complete", 
                                    f"No tag issues found in Block '{self.mw.block_names.get(str(block_idx), str(block_idx))}'. "
                                    f"{'Known tags might have been standardized.' if changes_applied else 'No changes made.'}")

    def rescan_all_tags(self):
        log_debug("<<<<<<<<<< ACTION: Rescan All Tags Triggered >>>>>>>>>>")
        if not self.mw.data:
            QMessageBox.information(self.mw, "Rescan All Tags", "No data loaded to rescan.")
            return

        total_problem_lines, total_problem_blocks = 0, 0
        any_changes_applied_globally = False
        
        self.mw.problem_lines_per_block.clear()
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'clearProblemLineHighlights'):
            preview_edit.clearProblemLineHighlights()
        if hasattr(self.ui_updater, 'clear_all_problem_block_highlights_and_text'):
            self.ui_updater.clear_all_problem_block_highlights_and_text()

        self.mw.is_programmatically_changing_text = True 
        for block_idx in range(len(self.mw.data)):
            num_block_problems, block_changes_applied = self._perform_tag_scan_for_block(block_idx, is_single_block_scan=False)
            if block_changes_applied: any_changes_applied_globally = True
            if num_block_problems > 0:
                total_problem_lines += num_block_problems; total_problem_blocks += 1
        
        # Оновлюємо preview для поточного блоку ПІСЛЯ всіх сканувань
        if self.mw.current_block_idx != -1:
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
        
        self.mw.is_programmatically_changing_text = False

        if any_changes_applied_globally and not self.mw.unsaved_changes:
            self.mw.unsaved_changes = True
            self.ui_updater.update_title()

        if total_problem_blocks > 0:
            QMessageBox.information(self.mw, "Rescan Complete", 
                                    f"Found {total_problem_lines} tag issue(s) across {total_problem_blocks} block(s).\n"
                                    "Known tags were auto-corrected. Please review highlighted items.")
        else:
            QMessageBox.information(self.mw, "Rescan Complete", 
                                    f"No tag issues found in any block. "
                                    f"{'Some known tags might have been standardized.' if any_changes_applied_globally else 'No changes made.'}")