import os
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QProgressDialog, QPlainTextEdit
from PyQt5.QtCore import Qt
from .base_handler import BaseHandler
from utils.utils import log_debug, convert_dots_to_spaces_from_editor, calculate_string_width, remove_all_tags
from core.tag_utils import apply_default_mappings_only, analyze_tags_for_issues, \
                      TAG_STATUS_OK, TAG_STATUS_UNRESOLVED_BRACKETS, TAG_STATUS_MISMATCHED_CURLY
from core.data_manager import load_json_file


class AppActionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        if not hasattr(self.mw, 'critical_problem_lines_per_block'):
            self.mw.critical_problem_lines_per_block = {}
        if not hasattr(self.mw, 'warning_problem_lines_per_block'):
            self.mw.warning_problem_lines_per_block = {}
        if not hasattr(self.mw, 'width_exceeded_lines_per_block'):
            self.mw.width_exceeded_lines_per_block = {}
        if not hasattr(self.mw, 'short_lines_per_block'):
            self.mw.short_lines_per_block = {}

    def _get_first_word_width(self, text: str) -> int:
        if not text:
            return 0
        stripped_text = remove_all_tags(text.lstrip())
        first_word = stripped_text.split(maxsplit=1)[0] if stripped_text else ""
        return calculate_string_width(first_word, self.mw.font_map)

    def _perform_issues_scan_for_block(self, block_idx: int, is_single_block_scan: bool = False, use_default_mappings_in_scan: bool = False) -> tuple[int, int, int, int, bool]:
        if not (0 <= block_idx < len(self.mw.data)):
            return 0, 0, 0, 0, False

        block_key = str(block_idx)
        current_block_critical_indices = set()
        current_block_warning_indices = set()
        current_block_width_exceeded_indices = set()
        current_block_short_line_indices = set()
        changes_made_to_edited_data_in_this_block = False
        
        num_strings_in_block = len(self.mw.data[block_idx])
        space_width = calculate_string_width(" ", self.mw.font_map)
        sentence_end_chars = ('.', '!', '?')
        max_width_for_short_check = self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS

        for string_idx in range(num_strings_in_block):
            text_before_processing, source = self.data_processor.get_current_string_text(block_idx, string_idx)
            text_to_analyze = text_before_processing
            
            if use_default_mappings_in_scan:
                normalized_text, was_normalized = apply_default_mappings_only(
                    text_before_processing,
                    self.mw.default_tag_mappings
                )
                if was_normalized:
                    if self.data_processor.update_edited_data(block_idx, string_idx, normalized_text):
                        self.ui_updater.update_title()
                    changes_made_to_edited_data_in_this_block = True
                    text_to_analyze = normalized_text
            
            original_text_for_comparison = self.mw.data[block_idx][string_idx]
            tag_status, _ = analyze_tags_for_issues(text_to_analyze, original_text_for_comparison, self.mw.EDITOR_PLAYER_TAG)
            if tag_status == TAG_STATUS_UNRESOLVED_BRACKETS: current_block_critical_indices.add(string_idx)
            elif tag_status == TAG_STATUS_MISMATCHED_CURLY: current_block_warning_indices.add(string_idx)
            
            sub_lines = str(text_to_analyze).split('\n')
            line_exceeds_width_flag = False
            data_string_is_short_flag = False

            if len(sub_lines) > 1:
                for sub_line_idx, sub_line_text in enumerate(sub_lines):
                    pixel_width_current_sub = calculate_string_width(remove_all_tags(sub_line_text), self.mw.font_map)
                    if pixel_width_current_sub > self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS:
                        line_exceeds_width_flag = True

                    if sub_line_idx < len(sub_lines) - 1:
                        current_sub_line_clean_stripped = remove_all_tags(sub_line_text).strip()
                        if not current_sub_line_clean_stripped:
                            continue 
                        if current_sub_line_clean_stripped.endswith(sentence_end_chars):
                            continue
                        
                        next_sub_line_text = sub_lines[sub_line_idx + 1]
                        next_sub_line_clean_stripped = remove_all_tags(next_sub_line_text).strip()
                        if not next_sub_line_clean_stripped:
                            continue

                        first_word_next_sub_line = next_sub_line_clean_stripped.split(maxsplit=1)[0] if next_sub_line_clean_stripped else ""
                        if not first_word_next_sub_line:
                            continue
                        
                        first_word_next_width = calculate_string_width(first_word_next_sub_line, self.mw.font_map)
                        if first_word_next_width > 0:
                            remaining_width = max_width_for_short_check - pixel_width_current_sub
                            if remaining_width >= (first_word_next_width + space_width):
                                data_string_is_short_flag = True
                                break 
            else: 
                if sub_lines:
                    pixel_width_current_sub = calculate_string_width(remove_all_tags(sub_lines[0]), self.mw.font_map)
                    if pixel_width_current_sub > self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS:
                        line_exceeds_width_flag = True
            
            if line_exceeds_width_flag:
                current_block_width_exceeded_indices.add(string_idx)
            if data_string_is_short_flag:
                current_block_short_line_indices.add(string_idx)


        if current_block_critical_indices: self.mw.critical_problem_lines_per_block[block_key] = current_block_critical_indices
        elif block_key in self.mw.critical_problem_lines_per_block: del self.mw.critical_problem_lines_per_block[block_key]

        if current_block_warning_indices: self.mw.warning_problem_lines_per_block[block_key] = current_block_warning_indices
        elif block_key in self.mw.warning_problem_lines_per_block: del self.mw.warning_problem_lines_per_block[block_key]

        if current_block_width_exceeded_indices: self.mw.width_exceeded_lines_per_block[block_key] = current_block_width_exceeded_indices
        elif block_key in self.mw.width_exceeded_lines_per_block: del self.mw.width_exceeded_lines_per_block[block_key]
        
        if current_block_short_line_indices: self.mw.short_lines_per_block[block_key] = current_block_short_line_indices
        elif block_key in self.mw.short_lines_per_block: del self.mw.short_lines_per_block[block_key]
        
        if is_single_block_scan and hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
            self.ui_updater.update_block_item_text_with_problem_count(block_idx)
        
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if is_single_block_scan and self.mw.current_block_idx == block_idx and preview_edit:
            self.ui_updater.populate_strings_for_block(block_idx)
        
        return len(current_block_critical_indices), len(current_block_warning_indices), len(current_block_width_exceeded_indices), len(current_block_short_line_indices), changes_made_to_edited_data_in_this_block

    def _perform_initial_silent_scan_all_issues(self):
        if not self.mw.data:
            log_debug("AppActionHandler._perform_initial_silent_scan_all_issues: No data to scan.")
            return
        
        log_debug("AppActionHandler: Performing initial silent scan for ALL issues (tags, width, short lines)...")
        self.mw.is_programmatically_changing_text = True
        
        self.mw.critical_problem_lines_per_block.clear()
        self.mw.warning_problem_lines_per_block.clear()
        self.mw.width_exceeded_lines_per_block.clear()
        self.mw.short_lines_per_block.clear()
        
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'clearAllProblemTypeHighlights'):
            preview_edit.clearAllProblemTypeHighlights()
        if hasattr(self.ui_updater, 'clear_all_problem_block_highlights_and_text'):
             self.ui_updater.clear_all_problem_block_highlights_and_text()

        any_changes_applied_globally = False
        for block_idx in range(len(self.mw.data)):
            _num_crit, _num_warn, _num_width, _num_short, block_changes_applied = self._perform_issues_scan_for_block(block_idx, is_single_block_scan=False, use_default_mappings_in_scan=False)
            if block_changes_applied:
                any_changes_applied_globally = True
        
        if any_changes_applied_globally and not self.mw.unsaved_changes:
            log_debug("AppActionHandler: Data was modified during initial silent scan (e.g., by default tag mappings). This should not happen if use_default_mappings_in_scan=False.")
            
        self.mw.is_programmatically_changing_text = False
        log_debug("AppActionHandler: Initial silent scan for ALL issues complete.")


    def save_data_action(self, ask_confirmation=True):
        log_debug(f"--> AppActionHandler: save_data_action called. ask_confirmation={ask_confirmation}, current unsaved={self.mw.unsaved_changes}")
        if self.mw.json_path and not self.mw.edited_json_path:
            self.mw.edited_json_path = self._derive_edited_path(self.mw.json_path)
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
    
    def rescan_issues_for_single_block(self, block_idx: int = -1, show_message_on_completion: bool = True, use_default_mappings: bool = True):
        if block_idx == -1: block_idx = self.mw.current_block_idx
        if block_idx < 0:
            if show_message_on_completion:
                QMessageBox.information(self.mw, "Rescan Issues", "No block selected to rescan.")
            return
            
        log_debug(f"<<<<<<<<<< ACTION: Rescan Issues for Block {block_idx} Triggered. use_default_mappings={use_default_mappings} >>>>>>>>>>")
        self.mw.is_programmatically_changing_text = True
        num_critical, num_warnings, num_width_exceeded, num_short, changes_applied = self._perform_issues_scan_for_block(block_idx, is_single_block_scan=True, use_default_mappings_in_scan=use_default_mappings)
        self.mw.is_programmatically_changing_text = False
            
        if show_message_on_completion:
            block_name_str = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
            message_parts = []
            if num_critical > 0: message_parts.append(f"{num_critical} line(s) with critical tag issues.")
            if num_warnings > 0: message_parts.append(f"{num_warnings} line(s) with tag warnings.")
            if num_width_exceeded > 0: message_parts.append(f"{num_width_exceeded} line(s) exceed width limit ({self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS}px).")
            if num_short > 0: message_parts.append(f"{num_short} line(s) are potentially too short.")
            
            if not message_parts:
                message = f"No issues found in Block '{block_name_str}'."
                if changes_applied: message += "\nKnown editor tags were standardized using default mappings."
                QMessageBox.information(self.mw, "Rescan Complete", message)
            else:
                title = "Rescan Complete with Issues/Warnings"
                summary = f"Block '{block_name_str}':\n" + "\n".join(message_parts)
                if changes_applied: summary += "\nKnown editor tags were standardized using default mappings where possible."
                QMessageBox.warning(self.mw, title, summary)

    def rescan_all_tags(self):
        log_debug("<<<<<<<<<< ACTION: Rescan All Tags (and Widths/Shorts) Triggered >>>>>>>>>>")
        if not self.mw.data:
            QMessageBox.information(self.mw, "Rescan All Issues", "No data loaded to rescan.")
            return
        
        self._perform_initial_silent_scan_all_issues()

        total_critical_lines = sum(len(s) for s in self.mw.critical_problem_lines_per_block.values())
        total_warning_lines = sum(len(s) for s in self.mw.warning_problem_lines_per_block.values())
        total_width_exceeded_lines = sum(len(s) for s in self.mw.width_exceeded_lines_per_block.values())
        total_short_lines = sum(len(s) for s in self.mw.short_lines_per_block.values())

        total_blocks_with_critical = sum(1 for s in self.mw.critical_problem_lines_per_block.values() if s)
        total_blocks_with_warning = sum(1 for s in self.mw.warning_problem_lines_per_block.values() if s)
        total_blocks_with_width = sum(1 for s in self.mw.width_exceeded_lines_per_block.values() if s)
        total_blocks_with_short = sum(1 for s in self.mw.short_lines_per_block.values() if s)
        
        message_parts = []
        if total_blocks_with_critical > 0: message_parts.append(f"Found {total_critical_lines} critical tag issue(s) across {total_blocks_with_critical} block(s).")
        if total_blocks_with_warning > 0: message_parts.append(f"Found {total_warning_lines} tag warning(s) across {total_blocks_with_warning} block(s).")
        if total_blocks_with_width > 0: message_parts.append(f"Found {total_width_exceeded_lines} line(s) exceeding width limit across {total_blocks_with_width} block(s).")
        if total_blocks_with_short > 0: message_parts.append(f"Found {total_short_lines} potentially short line(s) across {total_blocks_with_short} block(s).")
        
        if not message_parts:
            message = "No issues (tags, width, or short lines) found in any block based on current data state."
            QMessageBox.information(self.mw, "Rescan Complete", message)
        else:
            title = "Rescan Complete with Issues/Warnings"
            summary = "\n".join(message_parts)
            QMessageBox.warning(self.mw, title, summary)
        
        self.ui_updater.populate_blocks()
        if self.mw.current_block_idx != -1:
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
        else:
            self.ui_updater.populate_strings_for_block(-1)


            
    def _derive_edited_path(self, original_path):
        if not original_path: return None
        dir_name = os.path.dirname(original_path)
        base, ext = os.path.splitext(os.path.basename(original_path))
        return os.path.join(dir_name, f"{base}_edited{ext}")

    def open_file_dialog_action(self):
        log_debug("--> AppActionHandler: Open File Dialog Triggered")
        if self.mw.unsaved_changes:
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Save before opening new file?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.save_data_action(ask_confirmation=True): return
            elif reply == QMessageBox.Cancel: return
        start_dir = os.path.dirname(self.mw.json_path) if self.mw.json_path else ""
        path, _ = QFileDialog.getOpenFileName(self.mw, "Open Original JSON", start_dir, "JSON (*.json);;All (*)")
        if path:
            self.load_all_data_for_path(path, manually_set_edited_path=None, is_initial_load_from_settings=False)
        log_debug("<-- AppActionHandler: Open File Dialog Finished")

    def open_changes_file_dialog_action(self):
        log_debug("--> AppActionHandler: Open Changes File Dialog Triggered")
        if not self.mw.json_path: QMessageBox.warning(self.mw, "Open Changes File", "Please open an original file first."); return
        start_dir = os.path.dirname(self.mw.edited_json_path) if self.mw.edited_json_path else (os.path.dirname(self.mw.json_path) if self.mw.json_path else "")
        path, _ = QFileDialog.getOpenFileName(self.mw, "Open Changes (Edited) JSON File", start_dir, "JSON Files (*.json);;All Files (*)")
        if path:
            if self.mw.unsaved_changes:
                 reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Loading a new changes file will discard current unsaved edits. Proceed?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                 if reply == QMessageBox.No: return
            
            new_edited_data, error = load_json_file(path, parent_widget=self.mw, expected_type=list)
            if error: QMessageBox.critical(self.mw, "Load Error", f"Failed to load selected changes file:\n{path}\n\n{error}"); return
            
            self.mw.edited_json_path = path
            self.mw.edited_file_data = new_edited_data
            self.mw.edited_data = {}
            self.mw.unsaved_changes = False
            
            self._perform_initial_silent_scan_all_issues()
            
            self.ui_updater.update_title()
            self.ui_updater.update_statusbar_paths()
            self.ui_updater.populate_blocks()
            if self.mw.block_list_widget.count() > 0 and self.mw.current_block_idx == -1:
                 self.mw.block_list_widget.setCurrentRow(0)
            else:
                 self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)


        log_debug("<-- AppActionHandler: Open Changes File finished.")

    def save_as_dialog_action(self):
        log_debug("--> AppActionHandler: Save As Dialog Triggered")
        if not self.mw.json_path: QMessageBox.warning(self.mw, "Save As Error", "No original file open."); return
        current_edited_path = self.mw.edited_json_path if self.mw.edited_json_path else self._derive_edited_path(self.mw.json_path)
        if not current_edited_path: current_edited_path = os.path.join(os.path.dirname(self.mw.json_path) if self.mw.json_path else ".", "untitled_edited.json")
        new_edited_path, _ = QFileDialog.getSaveFileName(self.mw, "Save Changes As...", current_edited_path, "JSON (*.json);;All (*)")
        if new_edited_path:
            original_edited_path_backup = self.mw.edited_json_path
            self.mw.edited_json_path = new_edited_path
            save_success = self.save_data_action(ask_confirmation=False)
            if save_success:
                QMessageBox.information(self.mw, "Saved As", f"Changes saved to:\n{self.mw.edited_json_path}")
                self.ui_updater.update_statusbar_paths()
            else:
                QMessageBox.critical(self.mw, "Save As Error", f"Failed to save to:\n{self.mw.edited_json_path}")
                self.mw.edited_json_path = original_edited_path_backup
                self.ui_updater.update_statusbar_paths()
        log_debug("<-- AppActionHandler: Save As Finished")

    def load_all_data_for_path(self, original_file_path, manually_set_edited_path=None, is_initial_load_from_settings=False):
        log_debug(f"--> AppActionHandler: load_all_data_for_path START. Original: '{original_file_path}', Manual Edit Path: '{manually_set_edited_path}', InitialLoad: {is_initial_load_from_settings}")
        self.mw.is_programmatically_changing_text = True
        
        data, error = load_json_file(original_file_path, parent_widget=self.mw, expected_type=list)
        if error:
            self.mw.json_path = None; self.mw.edited_json_path = None
            self.mw.data = []; self.mw.edited_data = {}; self.mw.edited_file_data = []
            self.mw.unsaved_changes = False
            self.mw.critical_problem_lines_per_block.clear()
            self.mw.warning_problem_lines_per_block.clear()
            self.mw.width_exceeded_lines_per_block.clear()
            self.mw.short_lines_per_block.clear()
            self.ui_updater.update_title(); self.ui_updater.update_statusbar_paths()
            self.ui_updater.populate_blocks(); self.ui_updater.populate_strings_for_block(-1)
            self.mw.is_programmatically_changing_text = False
            QMessageBox.critical(self.mw, "Load Error", f"Failed to load: {original_file_path}\n{error}"); return

        self.mw.json_path = original_file_path
        self.mw.data = data
        self.mw.edited_data = {}
        self.mw.unsaved_changes = False
        
        self.mw.edited_json_path = manually_set_edited_path if manually_set_edited_path else self._derive_edited_path(self.mw.json_path)
        self.mw.edited_file_data = []
        if self.mw.edited_json_path and os.path.exists(self.mw.edited_json_path):
            edited_data_from_file, edit_error = load_json_file(self.mw.edited_json_path, parent_widget=self.mw, expected_type=list)
            if edit_error:
                QMessageBox.warning(self.mw, "Edited Load Warning", f"Could not load changes file: {self.mw.edited_json_path}\n{edit_error}")
            else:
                self.mw.edited_file_data = edited_data_from_file
        
        self.mw.current_block_idx = -1; self.mw.current_string_idx = -1
        
        if hasattr(self.mw, 'undo_paste_action'): self.mw.can_undo_paste = False; self.mw.undo_paste_action.setEnabled(False)
        
        self.mw.block_list_widget.clear()
        if hasattr(self.mw, 'preview_text_edit'): self.mw.preview_text_edit.clear()
        if hasattr(self.mw, 'original_text_edit'): self.mw.original_text_edit.clear()
        if hasattr(self.mw, 'edited_text_edit'): self.mw.edited_text_edit.clear()
        
        if is_initial_load_from_settings:
            log_debug("Initial load from settings: Assuming problem data is from settings or will be calculated if missing.")
            problem_keys_to_check_in_mw = ['width_exceeded_lines_per_block', 'short_lines_per_block', 
                                           'critical_problem_lines_per_block', 'warning_problem_lines_per_block']
            needs_full_scan = False
            for key in problem_keys_to_check_in_mw:
                if not hasattr(self.mw, key) or not getattr(self.mw, key):
                    log_debug(f"{key} data not found in settings or empty, performing full scan.")
                    needs_full_scan = True
                    break
            if needs_full_scan:
                self.mw.is_programmatically_changing_text = True
                self._perform_initial_silent_scan_all_issues()
                self.mw.is_programmatically_changing_text = False


        else: 
            log_debug("Not initial load from settings: Performing full scan for all issues.")
            self._perform_initial_silent_scan_all_issues()
        
        self.ui_updater.update_title(); self.ui_updater.update_statusbar_paths()
        self.ui_updater.populate_blocks()

        if self.mw.block_list_widget.count() > 0:
            self.mw.block_list_widget.setCurrentRow(0)
        else:
            self.ui_updater.populate_strings_for_block(-1)
            
        self.mw.is_programmatically_changing_text = False
        log_debug(f"<-- AppActionHandler: load_all_data_for_path FINISHED (Success)")

    def reload_original_data_action(self):
        log_debug("--> AppActionHandler: Reload Original Triggered")
        if not self.mw.json_path: QMessageBox.information(self.mw, "Reload", "No file open."); return
        if self.mw.unsaved_changes:
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Reloading will discard current unsaved edits in memory. Proceed?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return
        current_edited_path_before_reload = self.mw.edited_json_path
        self.load_all_data_for_path(self.mw.json_path, manually_set_edited_path=current_edited_path_before_reload, is_initial_load_from_settings=False)
        log_debug("<-- AppActionHandler: Reload Original Finished")

    def calculate_widths_for_block_action(self, block_idx: int):
        log_debug(f"--> AppActionHandler: calculate_widths_for_block_action. Block: {block_idx}")
        if block_idx < 0 or not self.mw.data or block_idx >= len(self.mw.data) or not isinstance(self.mw.data[block_idx], list):
            QMessageBox.warning(self.mw, "Calculate Widths Error", "Invalid block selected or no data.")
            return

        if not self.mw.font_map:
             QMessageBox.warning(self.mw, "Calculate Widths Error", "Font map is not loaded. Cannot calculate widths.")
             return

        num_strings = len(self.mw.data[block_idx])
        if num_strings == 0:
            QMessageBox.information(self.mw, "Calculate Line Widths", f"Block {self.mw.block_names.get(str(block_idx),str(block_idx))} is empty.")
            return

        progress = QProgressDialog(f"Calculating widths for block {self.mw.block_names.get(str(block_idx),str(block_idx))}...", "Cancel", 0, num_strings, self.mw)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        results = []
        # Use LINE_WIDTH_WARNING_THRESHOLD_PIXELS as the max width for short line calculation
        max_width_for_short_check_report = self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS
        editor_warning_threshold = self.mw.LINE_WIDTH_WARNING_THRESHOLD_PIXELS # This is the same, but for clarity
        space_width = calculate_string_width(" ", self.mw.font_map)
        sentence_end_chars = ('.', '!', '?')
        
        for i in range(num_strings): # i is data_line_index
            progress.setValue(i)
            if progress.wasCanceled():
                log_debug("Width calculation for block cancelled by user.")
                return

            current_text_data, source = self.data_processor.get_current_string_text(block_idx, i)
            original_text_data = self.data_processor._get_string_from_source(block_idx, i, self.mw.data, "width_calc_block_original_data")
            
            line_report_parts = [f"Data Line {i+1}:"]

            line_report_parts.append(f"  Current (src:{source}):")
            current_data_string_sub_lines = str(current_text_data).split('\n')
            # Total width for game dialog should still use GAME_DIALOG_MAX_WIDTH_PIXELS if that's its purpose
            current_total_game_width = calculate_string_width(remove_all_tags(str(current_text_data).replace('\n','')), self.mw.font_map)
            game_status_current = "OK"
            if current_total_game_width > self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS: 
                game_status_current = f"EXCEEDS GAME LIMIT ({current_total_game_width - self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS}px)"
            line_report_parts.append(f"    Total (game dialog): {current_total_game_width}px ({game_status_current})")

            for j, sub_line in enumerate(current_data_string_sub_lines): # j is sub_line_index
                sub_line_no_tags = remove_all_tags(sub_line)
                width_px = calculate_string_width(sub_line_no_tags, self.mw.font_map)
                editor_status = "OK"
                short_status = ""
                if width_px > editor_warning_threshold: editor_status = f"EXCEEDS EDITOR THRESHOLD ({width_px - editor_warning_threshold}px)"
                
                if len(current_data_string_sub_lines) > 1 and j < len(current_data_string_sub_lines) - 1:
                    current_sub_line_clean_stripped_rpt = remove_all_tags(sub_line).strip()
                    if current_sub_line_clean_stripped_rpt and not current_sub_line_clean_stripped_rpt.endswith(sentence_end_chars):
                        next_sub_line_text_rpt = current_data_string_sub_lines[j+1]
                        next_sub_line_clean_stripped_rpt = remove_all_tags(next_sub_line_text_rpt).strip()
                        if next_sub_line_clean_stripped_rpt:
                            first_word_next_sub_line_rpt = next_sub_line_clean_stripped_rpt.split(maxsplit=1)[0] if next_sub_line_clean_stripped_rpt else ""
                            if first_word_next_sub_line_rpt:
                                first_word_next_width_rpt = calculate_string_width(first_word_next_sub_line_rpt, self.mw.font_map)
                                if first_word_next_width_rpt > 0:
                                    remaining_width_rpt = max_width_for_short_check_report - width_px
                                    if remaining_width_rpt >= (first_word_next_width_rpt + space_width):
                                        short_status = f"SHORT (can fit {first_word_next_width_rpt+space_width}px into {max_width_for_short_check_report}px, has {remaining_width_rpt}px left)"
                
                line_report_parts.append(f"    Sub {j+1}: {width_px}px (Editor: {editor_status}) {short_status} '{sub_line_no_tags[:30]}...'")


            line_report_parts.append(f"  Original:")
            original_data_string_sub_lines = str(original_text_data).split('\n')
            original_total_game_width = calculate_string_width(remove_all_tags(str(original_text_data).replace('\n','')), self.mw.font_map)
            game_status_original = "OK"
            if original_total_game_width > self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS: 
                game_status_original = f"EXCEEDS GAME LIMIT ({original_total_game_width - self.mw.GAME_DIALOG_MAX_WIDTH_PIXELS}px)"
            line_report_parts.append(f"    Total (game dialog): {original_total_game_width}px ({game_status_original})")

            for j, sub_line in enumerate(original_data_string_sub_lines): # j is sub_line_index
                sub_line_no_tags = remove_all_tags(sub_line)
                width_px = calculate_string_width(sub_line_no_tags, self.mw.font_map)
                editor_status = "OK"
                short_status_orig = ""
                if width_px > editor_warning_threshold: editor_status = f"EXCEEDS EDITOR THRESHOLD ({width_px - editor_warning_threshold}px)"

                if len(original_data_string_sub_lines) > 1 and j < len(original_data_string_sub_lines) -1:
                    original_sub_line_clean_stripped_rpt = remove_all_tags(sub_line).strip()
                    if original_sub_line_clean_stripped_rpt and not original_sub_line_clean_stripped_rpt.endswith(sentence_end_chars):
                        next_original_sub_line_text_rpt = original_data_string_sub_lines[j+1]
                        next_original_sub_line_clean_stripped_rpt = remove_all_tags(next_original_sub_line_text_rpt).strip()
                        if next_original_sub_line_clean_stripped_rpt:
                            first_word_next_original_sub_line_rpt = next_original_sub_line_clean_stripped_rpt.split(maxsplit=1)[0] if next_original_sub_line_clean_stripped_rpt else ""
                            if first_word_next_original_sub_line_rpt:
                                first_word_next_original_width_rpt = calculate_string_width(first_word_next_original_sub_line_rpt, self.mw.font_map)
                                if first_word_next_original_width_rpt > 0:
                                    remaining_width_orig_rpt = max_width_for_short_check_report - width_px
                                    if remaining_width_orig_rpt >= (first_word_next_original_width_rpt + space_width):
                                        short_status_orig = f"SHORT (can fit {first_word_next_original_width_rpt+space_width}px into {max_width_for_short_check_report}px, has {remaining_width_orig_rpt}px left)"
                
                line_report_parts.append(f"    Sub {j+1}: {width_px}px (Editor: {editor_status}) {short_status_orig} '{sub_line_no_tags[:30]}...'")
            
            results.append("\n".join(line_report_parts))
        
        progress.setValue(num_strings)

        if not results:
            QMessageBox.information(self.mw, "Calculate Line Widths", f"Block {self.mw.block_names.get(str(block_idx),str(block_idx))} processed. No lines found or calculation error.")
            return
            
        result_text_title = (f"Widths for Block {self.mw.block_names.get(str(block_idx), str(block_idx))}\n"
                             f"(Max Game Dialog Width for Short Check: {max_width_for_short_check_report}px, Editor Warning Threshold: {editor_warning_threshold}px)\n")
        result_text = result_text_title + "\n" + "\n\n".join(results)
        
        result_dialog = QMessageBox(self.mw)
        result_dialog.setWindowTitle("Line Widths Report")
        result_dialog.setTextFormat(Qt.PlainText)
        result_dialog.setText(result_text)
        result_dialog.setIcon(QMessageBox.Information)
        result_dialog.setStandardButtons(QMessageBox.Ok)
        result_dialog.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        text_edit_for_size = result_dialog.findChild(QPlainTextEdit)
        if text_edit_for_size:
            text_edit_for_size.setMinimumWidth(700)
            text_edit_for_size.setMinimumHeight(500)
        result_dialog.exec_()

        log_debug(f"<-- AppActionHandler: calculate_widths_for_block_action finished for block {block_idx}")