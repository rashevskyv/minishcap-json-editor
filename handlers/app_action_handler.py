import os
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from handlers.base_handler import BaseHandler
from utils import log_debug, convert_dots_to_spaces_from_editor
from tag_utils import apply_default_mappings_only, analyze_tags_for_issues, \
                      TAG_STATUS_OK, TAG_STATUS_UNRESOLVED_BRACKETS, TAG_STATUS_MISMATCHED_CURLY
from data_manager import load_json_file


class AppActionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        if not hasattr(self.mw, 'critical_problem_lines_per_block'):
            self.mw.critical_problem_lines_per_block = {} 
        if not hasattr(self.mw, 'warning_problem_lines_per_block'):
            self.mw.warning_problem_lines_per_block = {}  

    def _perform_initial_silent_scan(self):
        if not self.mw.data:
            log_debug("AppActionHandler._perform_initial_silent_scan: No data to scan.")
            return
        
        log_debug("AppActionHandler: Performing initial silent tag scan...")
        self.mw.is_programmatically_changing_text = True 
        
        any_changes_applied_globally = False 
        for block_idx in range(len(self.mw.data)):
            _num_crit, _num_warn, block_changes_applied = self._perform_tag_scan_for_block(block_idx, is_single_block_scan=False, use_default_mappings_in_scan=False) 
            if block_changes_applied:
                any_changes_applied_globally = True
        
        if any_changes_applied_globally and not self.mw.unsaved_changes:
            log_debug("AppActionHandler: Tags were standardized during initial silent scan (this path might be rare if use_default_mappings_in_scan=False).")

        self.ui_updater.populate_blocks()
        if self.mw.current_block_idx != -1:
            self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
            
        self.mw.is_programmatically_changing_text = False
        log_debug("AppActionHandler: Initial silent tag scan complete.")


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

    def _perform_tag_scan_for_block(self, block_idx: int, is_single_block_scan: bool = False, use_default_mappings_in_scan: bool = False) -> tuple[int, int, bool]: 
        log_debug(f"AppActionHandler: Starting tag scan for block_idx: {block_idx}, use_default_mappings: {use_default_mappings_in_scan}")
        if not (0 <= block_idx < len(self.mw.data)):
            log_debug(f"AppActionHandler: Invalid block_idx {block_idx} for scan.")
            return 0, 0, False

        block_key = str(block_idx)
        current_block_critical_indices = set()
        current_block_warning_indices = set()
        changes_made_to_edited_data_in_this_block = False
        
        num_strings_in_block = len(self.mw.data[block_idx])

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
            
            tag_status, tag_error_msg = analyze_tags_for_issues(
                text_to_analyze,
                original_text_for_comparison,
                self.mw.EDITOR_PLAYER_TAG 
            )
            
            if tag_status == TAG_STATUS_UNRESOLVED_BRACKETS: 
                current_block_critical_indices.add(string_idx)
            elif tag_status == TAG_STATUS_MISMATCHED_CURLY: 
                current_block_warning_indices.add(string_idx)
        
        if current_block_critical_indices:
            self.mw.critical_problem_lines_per_block[block_key] = current_block_critical_indices
        elif block_key in self.mw.critical_problem_lines_per_block: 
            del self.mw.critical_problem_lines_per_block[block_key]

        if current_block_warning_indices:
            self.mw.warning_problem_lines_per_block[block_key] = current_block_warning_indices
        elif block_key in self.mw.warning_problem_lines_per_block:
            del self.mw.warning_problem_lines_per_block[block_key]
        
        if is_single_block_scan and hasattr(self.ui_updater, 'update_block_item_text_with_problem_count'):
            self.ui_updater.update_block_item_text_with_problem_count(block_idx) 
        
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if is_single_block_scan and self.mw.current_block_idx == block_idx and preview_edit:
            self.ui_updater.populate_strings_for_block(block_idx) 
        
        return len(current_block_critical_indices), len(current_block_warning_indices), changes_made_to_edited_data_in_this_block

    # Додаємо параметр show_message
    def rescan_tags_for_single_block(self, block_idx: int = -1, show_message: bool = True): 
        if block_idx == -1: block_idx = self.mw.current_block_idx
        if block_idx < 0:
            if show_message: # Показуємо повідомлення тільки якщо show_message=True
                QMessageBox.information(self.mw, "Rescan Tags", "No block selected to rescan.")
            return
            
        log_debug(f"<<<<<<<<<< ACTION: Rescan Tags for Block {block_idx} Triggered (with default_mappings) >>>>>>>>>>") 
        self.mw.is_programmatically_changing_text = True
        num_critical, num_warnings, changes_applied = self._perform_tag_scan_for_block(block_idx, is_single_block_scan=True, use_default_mappings_in_scan=True) 
        self.mw.is_programmatically_changing_text = False
            
        if show_message: # Показуємо повідомлення тільки якщо show_message=True
            block_name_str = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
            message_parts = []
            if num_critical > 0: message_parts.append(f"{num_critical} line(s) with unresolved '[...]' tags (critical, yellow).")
            if num_warnings > 0: message_parts.append(f"{num_warnings} line(s) with mismatched '{{...}}' tag counts (warning, gray).")
            
            if not message_parts: 
                message = f"No tag issues found in Block '{block_name_str}'."
                if changes_applied: message += "\nKnown editor tags were standardized using default mappings."
                QMessageBox.information(self.mw, "Rescan Complete", message)
            else:
                title = "Rescan Complete with Issues"
                summary = f"Block '{block_name_str}':\n" + "\n".join(message_parts)
                if changes_applied: summary += "\nKnown editor tags were standardized using default mappings where possible."
                QMessageBox.warning(self.mw, title, summary)

    def rescan_all_tags(self): 
        log_debug("<<<<<<<<<< ACTION: Rescan All Tags Triggered (NO default_mappings applied to data) >>>>>>>>>>") 
        if not self.mw.data:
            QMessageBox.information(self.mw, "Rescan All Tags", "No data loaded to rescan.")
            return
        
        self.mw.critical_problem_lines_per_block.clear()
        self.mw.warning_problem_lines_per_block.clear()
        
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'clearAllProblemTypeHighlights'): 
            preview_edit.clearAllProblemTypeHighlights()
        
        if hasattr(self.ui_updater, 'clear_all_problem_block_highlights_and_text'):
             self.ui_updater.clear_all_problem_block_highlights_and_text() 

        self._perform_initial_silent_scan() 

        total_critical_lines = sum(len(s) for s in self.mw.critical_problem_lines_per_block.values())
        total_warning_lines = sum(len(s) for s in self.mw.warning_problem_lines_per_block.values())
        total_blocks_with_critical = sum(1 for s in self.mw.critical_problem_lines_per_block.values() if s)
        total_blocks_with_warning = sum(1 for s in self.mw.warning_problem_lines_per_block.values() if s)
        
        message_parts = []
        if total_blocks_with_critical > 0: message_parts.append(f"Found {total_critical_lines} critical tag issue(s) (unresolved '[...]') across {total_blocks_with_critical} block(s).")
        if total_blocks_with_warning > 0: message_parts.append(f"Found {total_warning_lines} warning(s) (mismatched '{{...}}') across {total_blocks_with_warning} block(s).")
        
        if not message_parts:
            message = "No tag issues found in any block based on current data state."
            QMessageBox.information(self.mw, "Rescan Complete", message)
        else:
            title = "Rescan Complete with Issues/Warnings"
            summary = "\n".join(message_parts)
            QMessageBox.warning(self.mw, title, summary)
            
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
            
            self.mw.critical_problem_lines_per_block.clear()
            self.mw.warning_problem_lines_per_block.clear()
            if hasattr(self.ui_updater, 'clear_all_problem_block_highlights_and_text'):
                 self.ui_updater.clear_all_problem_block_highlights_and_text()

            self._perform_initial_silent_scan() 
            
            self.ui_updater.update_title()
            self.ui_updater.update_statusbar_paths()
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
            if not is_initial_load_from_settings : 
                self.mw.critical_problem_lines_per_block.clear()
                self.mw.warning_problem_lines_per_block.clear()
            self.ui_updater.update_title(); self.ui_updater.update_statusbar_paths()
            self.ui_updater.populate_blocks(); self.ui_updater.populate_strings_for_block(-1)
            if not is_initial_load_from_settings and hasattr(self.ui_updater, 'clear_all_problem_block_highlights_and_text'): 
                self.ui_updater.clear_all_problem_block_highlights_and_text()
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
        
        if not is_initial_load_from_settings:
            log_debug("AppActionHandler: Not initial load from settings. Clearing problems before scan.")
            self.mw.critical_problem_lines_per_block.clear()
            self.mw.warning_problem_lines_per_block.clear()
            if hasattr(self.ui_updater, 'clear_all_problem_block_highlights_and_text'):
                 self.ui_updater.clear_all_problem_block_highlights_and_text()
        
        if hasattr(self.mw, 'undo_paste_action'): self.mw.can_undo_paste = False; self.mw.undo_paste_action.setEnabled(False)
        
        self.mw.block_list_widget.clear() 
        if hasattr(self.mw, 'preview_text_edit'): self.mw.preview_text_edit.clear()
        if hasattr(self.mw, 'original_text_edit'): self.mw.original_text_edit.clear()
        if hasattr(self.mw, 'edited_text_edit'): self.mw.edited_text_edit.clear()
        
        self.ui_updater.update_title(); self.ui_updater.update_statusbar_paths()
        
        if not is_initial_load_from_settings and self.mw.data:
            self._perform_initial_silent_scan() 
        else:
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