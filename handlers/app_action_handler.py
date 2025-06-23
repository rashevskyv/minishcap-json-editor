import os
from typing import Optional 
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QProgressDialog, QPlainTextEdit
from PyQt5.QtCore import Qt
from .base_handler import BaseHandler
from utils.logging_utils import log_debug
from utils.utils import convert_dots_to_spaces_from_editor, calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN, convert_spaces_to_dots_for_display
from core.tag_utils import apply_default_mappings_only
from core.data_manager import load_json_file
from plugins.base_game_rules import BaseGameRules

class AppActionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater, game_rules_plugin: Optional[BaseGameRules]): 
        super().__init__(main_window, data_processor, ui_updater)
        self.game_rules_plugin = game_rules_plugin
        if not hasattr(self.mw, 'problems_per_subline'):
            self.mw.problems_per_subline = {}

    def _get_first_word_width(self, text: str) -> int: 
        if not text or not self.mw.font_map: 
            return 0
        stripped_text = remove_all_tags(text.lstrip())
        first_word = stripped_text.split(maxsplit=1)[0] if stripped_text else ""
        return calculate_string_width(first_word, self.mw.font_map)

    def _perform_issues_scan_for_block(self, block_idx: int, is_single_block_scan: bool = False, use_default_mappings_in_scan: bool = False, target_string_idx_for_debug: int = -1):
        if not self.game_rules_plugin:
            return
        
        if not (0 <= block_idx < len(self.mw.data)):
            return

        detection_config = getattr(self.mw, 'detection_enabled', {})

        changes_made_to_edited_data_in_this_block = False
        
        keys_to_remove_from_problems = [
            (b_idx, ds_idx, sl_idx) 
            for b_idx, ds_idx, sl_idx in self.mw.problems_per_subline.keys() 
            if b_idx == block_idx
        ]
        for key_to_remove in keys_to_remove_from_problems:
            del self.mw.problems_per_subline[key_to_remove]

        num_strings_in_block = len(self.mw.data[block_idx])
        if not isinstance(self.mw.data[block_idx], list):
            return

        for data_string_idx in range(num_strings_in_block):
            current_data_string_text, _ = self.data_processor.get_current_string_text(block_idx, data_string_idx)
            current_data_string_text_with_spaces = convert_dots_to_spaces_from_editor(str(current_data_string_text))
            
            logical_sublines = current_data_string_text_with_spaces.split('\n')
            
            for subline_local_idx, logical_subline_text in enumerate(logical_sublines):
                next_logical_subline_text = logical_sublines[subline_local_idx + 1] if subline_local_idx + 1 < len(logical_sublines) else None
                
                subline_problems = self.game_rules_plugin.analyze_subline(
                    text=logical_subline_text, 
                    next_text=next_logical_subline_text,
                    subline_number_in_data_string=subline_local_idx, 
                    qtextblock_number_in_editor=subline_local_idx,
                    is_last_subline_in_data_string=(subline_local_idx == len(logical_sublines) - 1),
                    editor_font_map=self.mw.font_map,
                    editor_line_width_threshold=self.mw.line_width_warning_threshold_pixels,
                    full_data_string_text_for_logical_check=current_data_string_text_with_spaces, 
                    is_target_for_debug=False
                )
                
                filtered_problems = {
                    problem_id for problem_id in subline_problems 
                    if detection_config.get(problem_id, True)
                }

                problem_key = (block_idx, data_string_idx, subline_local_idx)
                if filtered_problems:
                    self.mw.problems_per_subline[problem_key] = filtered_problems
                elif problem_key in self.mw.problems_per_subline:
                    del self.mw.problems_per_subline[problem_key]
        
        return changes_made_to_edited_data_in_this_block


    def _perform_initial_silent_scan_all_issues(self):
        if not self.mw.data:
            return
        
        self.mw.is_programmatically_changing_text = True
        
        self.mw.problems_per_subline.clear() 
        
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'highlightManager'):
            preview_edit.highlightManager.clearAllProblemHighlights()

        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if edited_edit and hasattr(edited_edit, 'highlightManager'): 
            edited_edit.highlightManager.clearAllProblemHighlights()
        
        if hasattr(self.ui_updater, 'clear_all_problem_block_highlights_and_text'):
             self.ui_updater.clear_all_problem_block_highlights_and_text() 

        any_changes_applied_globally = False
        for block_idx in range(len(self.mw.data)):
            block_changes_applied = self._perform_issues_scan_for_block(block_idx, is_single_block_scan=False, use_default_mappings_in_scan=False)
            if block_changes_applied:
                any_changes_applied_globally = True
        
        if any_changes_applied_globally and not self.mw.unsaved_changes:
            log_debug("AppActionHandler: Data was modified during initial silent scan. This is unexpected if use_default_mappings_in_scan=False.")
            
        self.mw.is_programmatically_changing_text = False


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
                if not self.save_data_action(ask_confirmation=True): event.ignore()
                else: event.accept()
            elif reply == QMessageBox.Discard: event.accept()
            else: event.ignore()
        else: event.accept()
        log_debug("<-- AppActionHandler: handle_close_event finished.")
    
    def rescan_issues_for_single_block(self, block_idx: int = -1, show_message_on_completion: bool = True, use_default_mappings: bool = True):
        if not self.game_rules_plugin:
             QMessageBox.warning(self.mw, "Rescan Error", "Game rules plugin not loaded. Cannot rescan.")
             return

        if block_idx == -1: block_idx = self.mw.current_block_idx
        if block_idx < 0:
            if show_message_on_completion:
                QMessageBox.information(self.mw, "Rescan Issues", "No block selected to rescan.")
            return
            
        log_debug(f"<<<<<<<<<< ACTION: Rescan Issues for Block {block_idx} Triggered. use_default_mappings={use_default_mappings} >>>>>>>>>>")
        self.mw.is_programmatically_changing_text = True
        
        self._perform_issues_scan_for_block(block_idx, is_single_block_scan=True, use_default_mappings_in_scan=use_default_mappings)
        self.mw.is_programmatically_changing_text = False
            
        if show_message_on_completion:
            block_name_str = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
            problem_definitions = self.game_rules_plugin.get_problem_definitions()
            
            problem_counts_for_report = {pid: 0 for pid in problem_definitions.keys()}
            data_strings_with_problem_counts = {pid: set() for pid in problem_definitions.keys()}

            if 0 <= block_idx < len(self.mw.data) and isinstance(self.mw.data[block_idx], list):
                for data_string_idx_iter in range(len(self.mw.data[block_idx])):
                    for subline_local_idx_iter_check in range(1000): 
                        problem_key_iter = (block_idx, data_string_idx_iter, subline_local_idx_iter_check)
                        if problem_key_iter in self.mw.problems_per_subline:
                            subline_problems = self.mw.problems_per_subline[problem_key_iter]
                            for problem_id in subline_problems:
                                if problem_id in problem_counts_for_report:
                                    problem_counts_for_report[problem_id] +=1
                                    data_strings_with_problem_counts[problem_id].add(data_string_idx_iter)
                        else:
                            if subline_local_idx_iter_check > 0 : 
                                 if (block_idx, data_string_idx_iter, subline_local_idx_iter_check -1) not in self.mw.problems_per_subline:
                                     break 
                            elif subline_local_idx_iter_check == 0: 
                                 pass 
                            break 

            message_parts = []
            sorted_problem_ids_for_display = sorted(
                problem_counts_for_report.keys(),
                key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
            )
            for problem_id in sorted_problem_ids_for_display:
                count_sublines = problem_counts_for_report.get(problem_id, 0)
                if count_sublines > 0 and problem_id in problem_definitions:
                    short_name = self.game_rules_plugin.get_short_problem_name(problem_id)
                    num_data_strings_affected = len(data_strings_with_problem_counts[problem_id])
                    message_parts.append(f"{count_sublines} x '{short_name}' (in {num_data_strings_affected} data string(s))")

            if not message_parts:
                message = f"No issues (defined by current game plugin) found in Block '{block_name_str}'."
                QMessageBox.information(self.mw, "Rescan Complete", message)
            else:
                title = f"Rescan Complete for Block '{block_name_str}'"
                summary = "Found issues:\n" + "\n".join(message_parts)
                QMessageBox.warning(self.mw, title, summary)

    def rescan_all_tags(self): 
        if not self.game_rules_plugin:
             QMessageBox.warning(self.mw, "Rescan Error", "Game rules plugin not loaded. Cannot rescan.")
             return
        log_debug("<<<<<<<<<< ACTION: Rescan All Issues Triggered >>>>>>>>>>") 
        if not self.mw.data:
            QMessageBox.information(self.mw, "Rescan All Issues", "No data loaded to rescan.")
            return
        
        self._perform_initial_silent_scan_all_issues() 

        problem_definitions = self.game_rules_plugin.get_problem_definitions()
        
        sublines_with_problem_counts = {problem_id: 0 for problem_id in problem_definitions.keys()}
        blocks_with_problem_counts = {problem_id: set() for problem_id in problem_definitions.keys()}
        data_strings_with_problem_counts = {problem_id: set() for problem_id in problem_definitions.keys()}

        for (block_idx_iter, ds_idx_iter, sl_idx_iter), problem_ids_set in self.mw.problems_per_subline.items():
            for problem_id in problem_ids_set:
                if problem_id in sublines_with_problem_counts:
                    sublines_with_problem_counts[problem_id] +=1 
                    blocks_with_problem_counts[problem_id].add(block_idx_iter)
                    data_strings_with_problem_counts[problem_id].add((block_idx_iter, ds_idx_iter))

        message_parts = []
        sorted_problem_ids_for_display = sorted(
            sublines_with_problem_counts.keys(),
            key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
        )

        for problem_id in sorted_problem_ids_for_display:
            total_sublines_with_problem = sublines_with_problem_counts.get(problem_id, 0)
            if total_sublines_with_problem > 0 and problem_id in problem_definitions:
                short_name = self.game_rules_plugin.get_short_problem_name(problem_id)
                num_blocks_affected = len(blocks_with_problem_counts[problem_id])
                num_data_strings_affected = len(data_strings_with_problem_counts[problem_id])
                message_parts.append(f"Found {total_sublines_with_problem} subline(s) with '{short_name}' in {num_data_strings_affected} data string(s) across {num_blocks_affected} block(s).")
        
        if not message_parts:
            message = "No issues (defined by current game plugin) found in any block based on current data state."
            QMessageBox.information(self.mw, "Rescan Complete", message)
        else:
            title = "Rescan All Blocks Complete"
            summary = "Found issues:\n" + "\n".join(message_parts)
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
            
            json_obj, error = load_json_file(path, parent_widget=self.mw)
            if error: QMessageBox.critical(self.mw, "Load Error", f"Failed to load selected changes file:\n{path}\n\n{error}"); return
            if not self.mw.current_game_rules:
                QMessageBox.critical(self.mw, "Load Error", "No game plugin active to parse the file.")
                return

            new_edited_data, _ = self.mw.current_game_rules.load_data_from_json_obj(json_obj)
            
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
        
        if not self.mw.current_game_rules:
            QMessageBox.critical(self.mw, "Load Error", "Cannot load file: No game plugin is active.")
            self.mw.is_programmatically_changing_text = False
            return

        json_obj, error = load_json_file(original_file_path, parent_widget=self.mw)
        if error:
            self.mw.json_path = None; self.mw.edited_json_path = None
            self.mw.data = []; self.mw.edited_data = {}; self.mw.edited_file_data = []
            self.mw.unsaved_changes = False
            self.mw.problems_per_subline.clear()
            self.ui_updater.update_title(); self.ui_updater.update_statusbar_paths()
            self.ui_updater.populate_blocks(); self.ui_updater.populate_strings_for_block(-1)
            self.mw.is_programmatically_changing_text = False
            QMessageBox.critical(self.mw, "Load Error", f"Failed to load: {original_file_path}\n{error}"); return

        data, block_names_from_plugin = self.mw.current_game_rules.load_data_from_json_obj(json_obj)
        if not data and json_obj is not None:
            QMessageBox.critical(self.mw, "Plugin Error", f"The active plugin '{self.mw.current_game_rules.get_display_name()}' could not parse the file:\n{original_file_path}")
            self.mw.json_path = None
            self.mw.data = []
            self.ui_updater.populate_blocks()
            self.ui_updater.populate_strings_for_block(-1)
            self.mw.is_programmatically_changing_text = False
            return

        self.mw.json_path = original_file_path
        self.mw.data = data
        
        final_block_names = {}
        if block_names_from_plugin:
            final_block_names.update(block_names_from_plugin)
        final_block_names.update(self.mw.block_names)
        self.mw.block_names = final_block_names
        
        self.mw.edited_data = {}
        self.mw.unsaved_changes = False
        
        self.mw.edited_json_path = manually_set_edited_path if manually_set_edited_path else self._derive_edited_path(self.mw.json_path)
        self.mw.edited_file_data = []
        if self.mw.edited_json_path and os.path.exists(self.mw.edited_json_path):
            edited_json_obj, edit_error = load_json_file(self.mw.edited_json_path, parent_widget=self.mw)
            if edit_error:
                QMessageBox.warning(self.mw, "Edited Load Warning", f"Could not load changes file: {self.mw.edited_json_path}\n{edit_error}")
            else:
                edited_data_from_file, _ = self.mw.current_game_rules.load_data_from_json_obj(edited_json_obj)
                self.mw.edited_file_data = edited_data_from_file
        
        self.mw.current_block_idx = -1; self.mw.current_string_idx = -1
        
        if hasattr(self.mw, 'undo_paste_action'): self.mw.can_undo_paste = False; self.mw.undo_paste_action.setEnabled(False)
        
        self.mw.block_list_widget.clear()
        if hasattr(self.mw, 'preview_text_edit'): self.mw.preview_text_edit.clear()
        if hasattr(self, 'mw.original_text_edit'): self.mw.original_text_edit.clear()
        if hasattr(self, 'mw.edited_text_edit'): self.mw.edited_text_edit.clear()
        
        self._perform_initial_silent_scan_all_issues()
        
        self.ui_updater.update_title(); self.ui_updater.update_statusbar_paths()
        self.ui_updater.populate_blocks()

        if self.mw.block_list_widget.count() > 0:
            if not is_initial_load_from_settings: 
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
        if not self.game_rules_plugin:
            QMessageBox.warning(self.mw, "Calculate Widths Error", "Game rules plugin not loaded.")
            return


        num_strings = len(self.mw.data[block_idx])
        if num_strings == 0:
            QMessageBox.information(self.mw, "Calculate Line Widths", f"Block {self.mw.block_names.get(str(block_idx),str(block_idx))} is empty.")
            return

        progress = QProgressDialog(f"Calculating widths for block {self.mw.block_names.get(str(block_idx),str(block_idx))}...", "Cancel", 0, num_strings, self.mw)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        results = []
        problem_definitions = self.game_rules_plugin.get_problem_definitions()
        
        editor_warning_threshold = self.mw.line_width_warning_threshold_pixels
        
        for data_str_idx in range(num_strings):
            progress.setValue(data_str_idx)
            if progress.wasCanceled():
                log_debug("Width calculation for block cancelled by user.")
                return

            current_text_data_line, source = self.data_processor.get_current_string_text(block_idx, data_str_idx)
            original_text_data_line = self.data_processor._get_string_from_source(block_idx, data_str_idx, self.mw.data, "width_calc_block_original_data")
            
            line_report_parts = [f"Data Line {data_str_idx + 1}:"]
            
            sources_to_check = [
                ("Current", str(current_text_data_line), source),
                ("Original", str(original_text_data_line), "original_data")
            ]

            for title_prefix, text_to_analyze, text_source_info in sources_to_check:
                line_report_parts.append(f"  {title_prefix} (src:{text_source_info}):")
                logical_sublines = self.game_rules_plugin.problem_analyzer._get_sublines_from_data_string(text_to_analyze)
                
                game_like_text_no_newlines_rstripped = remove_all_tags(text_to_analyze.replace('\\n','').replace('\\p','').replace('\\l','')).rstrip()
                total_game_width = calculate_string_width(game_like_text_no_newlines_rstripped, self.mw.font_map)
                game_status = "OK"
                if total_game_width > self.mw.game_dialog_max_width_pixels:
                    game_status = f"EXCEEDS GAME DIALOG LIMIT ({total_game_width - self.mw.game_dialog_max_width_pixels}px)"
                line_report_parts.append(f"    Total (game dialog, rstripped): {total_game_width}px ({game_status})")

                for subline_idx, sub_line_text in enumerate(logical_sublines):
                    sub_line_no_tags_rstripped = remove_all_tags(sub_line_text).rstrip()
                    width_px = calculate_string_width(sub_line_no_tags_rstripped, self.mw.font_map)
                    
                    problems_per_subline_list = self.game_rules_plugin.problem_analyzer.analyze_data_string(text_to_analyze, self.mw.font_map, editor_warning_threshold)
                    current_subline_problems = problems_per_subline_list[subline_idx] if subline_idx < len(problems_per_subline_list) else set()
                    
                    statuses = []
                    for prob_id in current_subline_problems:
                        if prob_id in problem_definitions:
                            statuses.append(problem_definitions[prob_id]['name'])
                    
                    status_str = ", ".join(statuses) if statuses else "OK"
                    line_report_parts.append(f"    Sub {subline_idx+1} (rstripped): {width_px}px ({status_str}) '{sub_line_no_tags_rstripped[:30]}...'")
                if title_prefix == "Current": line_report_parts.append("")


            results.append("\n".join(line_report_parts))
        
        progress.setValue(num_strings)

        if not results:
            QMessageBox.information(self.mw, "Calculate Line Widths", f"Block {self.mw.block_names.get(str(block_idx),str(block_idx))} processed. No lines found or calculation error.")
            return
            
        result_text_title = (f"Widths for Block {self.mw.block_names.get(str(block_idx), str(block_idx))}\n"
                             f"(Editor Warning Threshold: {editor_warning_threshold}px)\n"
                             f"(Game Dialog Max Width (for total only): {self.mw.game_dialog_max_width_pixels}px)\n")
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