# --- START OF FILE handlers/app_action_handler.py ---
import os
from typing import Optional 
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QProgressDialog, QPlainTextEdit
from PyQt5.QtCore import Qt
from .base_handler import BaseHandler
from utils.logging_utils import log_debug, log_info
from utils.utils import convert_dots_to_spaces_from_editor, calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN, convert_spaces_to_dots_for_display
from core.tag_utils import apply_default_mappings_only
from core.data_manager import load_json_file, load_text_file
from plugins.base_game_rules import BaseGameRules

class AppActionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater, game_rules_plugin: Optional[BaseGameRules]): 
        super().__init__(main_window, data_processor, ui_updater)
        self.game_rules_plugin = game_rules_plugin

    def _perform_issues_scan_for_block(self, block_idx: int, is_single_block_scan: bool = False, use_default_mappings_in_scan: bool = False):
        if not self.mw.current_game_rules or not (0 <= block_idx < len(self.mw.data)):
            return

        keys_to_remove = [k for k in self.mw.problems_per_subline if k[0] == block_idx]
        for key in keys_to_remove:
            del self.mw.problems_per_subline[key]
        
        block_data = self.mw.data[block_idx]
        if not isinstance(block_data, list):
            return

        for string_idx, _ in enumerate(block_data):
            text, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
            text = str(text)

            analyzer = self.mw.current_game_rules.problem_analyzer
            all_problems_for_string = []
            
            font_map_for_string = self.mw.helper.get_font_map_for_string(block_idx, string_idx)
            string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
            width_threshold_for_string = string_meta.get("width", self.mw.line_width_warning_threshold_pixels)
            
            if hasattr(analyzer, 'analyze_data_string'):
                all_problems_for_string = analyzer.analyze_data_string(text, font_map_for_string, width_threshold_for_string)
            else:
                sublines = text.split('\n')
                for i, subline in enumerate(sublines):
                    next_subline = sublines[i+1] if i + 1 < len(sublines) else None
                    problems = analyzer.analyze_subline(
                        text=subline, next_text=next_subline, subline_number_in_data_string=i, qtextblock_number_in_editor=i,
                        is_last_subline_in_data_string=(i == len(sublines) - 1), editor_font_map=font_map_for_string,
                        editor_line_width_threshold=width_threshold_for_string,
                        full_data_string_text_for_logical_check=text
                    )
                    all_problems_for_string.append(problems)

            for i, problem_set in enumerate(all_problems_for_string):
                if problem_set:
                    self.mw.problems_per_subline[(block_idx, string_idx, i)] = problem_set


    def _perform_initial_silent_scan_all_issues(self):
        self.mw.problems_per_subline.clear()
        if not self.mw.data:
            return
        
        for block_idx in range(len(self.mw.data)):
            self._perform_issues_scan_for_block(block_idx)


    def save_data_action(self, ask_confirmation=True):
        if self.mw.json_path and not self.mw.edited_json_path:
            self.mw.edited_json_path = self._derive_edited_path(self.mw.json_path)
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
        if self.mw.unsaved_changes:
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Save changes before exiting?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.save_data_action(ask_confirmation=True): event.ignore()
                else: event.accept()
            elif reply == QMessageBox.Discard: event.accept()
            else: event.ignore()
        else: event.accept()
    
    def rescan_issues_for_single_block(self, block_idx: int = -1, show_message_on_completion: bool = True, use_default_mappings: bool = True):
        target_block_idx = block_idx if block_idx != -1 else self.mw.current_block_idx
        if target_block_idx == -1: return

        self._perform_issues_scan_for_block(target_block_idx, is_single_block_scan=True, use_default_mappings_in_scan=use_default_mappings)
        self.ui_updater.populate_blocks() 
        self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
        if show_message_on_completion:
            QMessageBox.information(self.mw, "Rescan Complete", f"Issue scan complete for block {target_block_idx}.")


    def rescan_all_tags(self): 
        log_info("Rescan All Issues action triggered.") 
        self._perform_initial_silent_scan_all_issues()
        self.ui_updater.populate_blocks()
        self.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
            
    def _derive_edited_path(self, original_path):
        if not original_path: return None
        dir_name = os.path.dirname(original_path)
        base, ext = os.path.splitext(os.path.basename(original_path))
        return os.path.join(dir_name, f"{base}_edited{ext}")

    def open_file_dialog_action(self):
        log_info("Open File Dialog action triggered.")
        if self.mw.unsaved_changes:
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Save before opening new file?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.save_data_action(ask_confirmation=True): return
            elif reply == QMessageBox.Cancel: return
        start_dir = os.path.dirname(self.mw.json_path) if self.mw.json_path else ""
        path, _ = QFileDialog.getOpenFileName(self.mw, "Open Original File", start_dir, "Supported Files (*.json *.txt);;JSON (*.json);;Text files (*.txt);;All (*)")
        if path:
            self.load_all_data_for_path(path, manually_set_edited_path=None, is_initial_load_from_settings=False)

    def open_changes_file_dialog_action(self):
        log_info("Open Changes File Dialog action triggered.")
        if not self.mw.json_path: QMessageBox.warning(self.mw, "Open Changes File", "Please open an original file first."); return
        start_dir = os.path.dirname(self.mw.edited_json_path) if self.mw.edited_json_path else (os.path.dirname(self.mw.json_path) if self.mw.json_path else "")
        path, _ = QFileDialog.getOpenFileName(self.mw, "Open Changes (Edited) File", start_dir, "Supported Files (*.json *.txt);;JSON Files (*.json);;Text Files (*.txt);;All Files (*)")
        if path:
            if self.mw.unsaved_changes:
                 reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Loading a new changes file will discard current unsaved edits. Proceed?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                 if reply == QMessageBox.No: return
            
            file_content, error = None, None
            file_extension = os.path.splitext(path)[1].lower()
            if file_extension == '.json':
                file_content, error = load_json_file(path, parent_widget=self.mw)
            elif file_extension == '.txt':
                file_content, error = load_text_file(path, parent_widget=self.mw)
            else:
                error = f"Unsupported file type: {file_extension}"

            if error: QMessageBox.critical(self.mw, "Load Error", f"Failed to load selected changes file:\n{path}\n\n{error}"); return
            if not self.mw.current_game_rules:
                QMessageBox.critical(self.mw, "Load Error", "No game plugin active to parse the file.")
                return

            new_edited_data, _ = self.mw.current_game_rules.load_data_from_json_obj(file_content)
            
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


    def save_as_dialog_action(self):
        log_info("Save As Dialog action triggered.")
        if not self.mw.json_path: QMessageBox.warning(self.mw, "Save As Error", "No original file open."); return
        current_edited_path = self.mw.edited_json_path if self.mw.edited_json_path else self._derive_edited_path(self.mw.json_path)
        if not current_edited_path: current_edited_path = os.path.join(os.path.dirname(self.mw.json_path) if self.mw.json_path else ".", "untitled_edited.json")
        new_edited_path, _ = QFileDialog.getSaveFileName(self.mw, "Save Changes As...", current_edited_path, "Supported Files (*.json *.txt);;JSON (*.json);;All (*)")
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

    def load_all_data_for_path(self, original_file_path, manually_set_edited_path=None, is_initial_load_from_settings=False):
        log_info(f"Loading all data for path: '{original_file_path}'")
        self.mw.is_programmatically_changing_text = True
        
        if not self.mw.current_game_rules:
            QMessageBox.critical(self.mw, "Load Error", "Cannot load file: No game plugin is active.")
            self.mw.is_programmatically_changing_text = False
            return

        file_content = None
        error = None
        file_extension = os.path.splitext(original_file_path)[1].lower()

        if file_extension == '.json':
            file_content, error = load_json_file(original_file_path, parent_widget=self.mw)
        elif file_extension == '.txt':
            file_content, error = load_text_file(original_file_path, parent_widget=self.mw)
        else:
            error = f"Unsupported file type: {file_extension}"

        if error:
            self.mw.json_path = None; self.mw.edited_json_path = None
            self.mw.data = []; self.mw.edited_data = {}; self.mw.edited_file_data = []
            self.mw.unsaved_changes = False
            self.ui_updater.update_title(); self.ui_updater.update_statusbar_paths()
            self.ui_updater.populate_blocks(); self.ui_updater.populate_strings_for_block(-1)
            self.mw.is_programmatically_changing_text = False
            QMessageBox.critical(self.mw, "Load Error", f"Failed to load: {original_file_path}\n{error}"); return

        data, block_names_from_plugin = self.mw.current_game_rules.load_data_from_json_obj(file_content)
        if not data and file_content is not None:
            QMessageBox.critical(self.mw, "Plugin Error", f"The active plugin '{self.mw.current_game_rules.get_display_name()}' could not parse the file:\n{original_file_path}")
            self.mw.json_path = None
            self.mw.data = []
            self.ui_updater.populate_blocks()
            self.ui_updater.populate_strings_for_block(-1)
            self.mw.is_programmatically_changing_text = False
            return

        self.mw.json_path = original_file_path
        self.mw.data = data
        if block_names_from_plugin:
            self.mw.block_names.update(block_names_from_plugin)
        
        self.mw.edited_data = {}
        self.mw.unsaved_changes = False
        
        self.mw.edited_json_path = manually_set_edited_path if manually_set_edited_path else self._derive_edited_path(self.mw.json_path)
        self.mw.edited_file_data = []
        if self.mw.edited_json_path and os.path.exists(self.mw.edited_json_path):
            edited_file_content = None
            edit_error = None
            edited_file_extension = os.path.splitext(self.mw.edited_json_path)[1].lower()

            if edited_file_extension == '.json':
                edited_file_content, edit_error = load_json_file(self.mw.edited_json_path, parent_widget=self.mw)
            elif edited_file_extension == '.txt':
                edited_file_content, edit_error = load_text_file(self.mw.edited_json_path, parent_widget=self.mw)

            if edit_error:
                QMessageBox.warning(self.mw, "Edited Load Warning", f"Could not load changes file: {self.mw.edited_json_path}\n{edit_error}")
            else:
                edited_data_from_file, _ = self.mw.current_game_rules.load_data_from_json_obj(edited_file_content)
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

    def reload_original_data_action(self):
        log_info("Reload Original action triggered.")
        if not self.mw.json_path: QMessageBox.information(self.mw, "Reload", "No file open."); return
        if self.mw.unsaved_changes:
            reply = QMessageBox.question(self.mw, 'Unsaved Changes', "Reloading will discard current unsaved edits in memory. Proceed?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return
        current_edited_path_before_reload = self.mw.edited_json_path
        self.load_all_data_for_path(self.mw.json_path, manually_set_edited_path=current_edited_path_before_reload, is_initial_load_from_settings=False)

    def calculate_widths_for_block_action(self, block_idx: int):
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
        
        for data_str_idx in range(num_strings):
            progress.setValue(data_str_idx)
            if progress.wasCanceled():
                log_info("Width calculation for block cancelled by user.")
                return

            current_text_data_line, source = self.data_processor.get_current_string_text(block_idx, data_str_idx)
            original_text_data_line = self.data_processor._get_string_from_source(block_idx, data_str_idx, self.mw.data, "width_calc_block_original_data")
            
            font_map_for_string = self.mw.helper.get_font_map_for_string(block_idx, data_str_idx)
            string_meta = self.mw.string_metadata.get((block_idx, data_str_idx), {})
            editor_warning_threshold = string_meta.get("width", self.mw.line_width_warning_threshold_pixels)

            line_report_parts = [f"Data Line {data_str_idx + 1}:"]
            
            sources_to_check = [
                ("Current", str(current_text_data_line), source),
                ("Original", str(original_text_data_line), "original_data")
            ]

            for title_prefix, text_to_analyze, text_source_info in sources_to_check:
                line_report_parts.append(f"  {title_prefix} (src:{text_source_info}):")
                logical_sublines = self.game_rules_plugin.problem_analyzer._get_sublines_from_data_string(text_to_analyze)
                
                game_like_text_no_newlines_rstripped = remove_all_tags(text_to_analyze.replace('\\n','').replace('\\p','').replace('\\l','')).rstrip()
                total_game_width = calculate_string_width(game_like_text_no_newlines_rstripped, font_map_for_string)
                game_status = "OK"
                if total_game_width > self.mw.game_dialog_max_width_pixels:
                    game_status = f"EXCEEDS GAME DIALOG LIMIT ({total_game_width - self.mw.game_dialog_max_width_pixels}px)"
                line_report_parts.append(f"    Total (game dialog, rstripped): {total_game_width}px ({game_status})")

                for subline_idx, sub_line_text in enumerate(logical_sublines):
                    sub_line_no_tags_rstripped = remove_all_tags(sub_line_text).rstrip()
                    width_px = calculate_string_width(sub_line_no_tags_rstripped, font_map_for_string)
                    
                    problems_per_subline_list = self.game_rules_plugin.problem_analyzer.analyze_data_string(text_to_analyze, font_map_for_string, editor_warning_threshold)
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
                             f"(Editor Warning Threshold: {self.mw.line_width_warning_threshold_pixels}px - can be overridden per string)\n"
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

    # ========== Project Management Methods ==========

    def create_new_project_action(self):
        """Create a new translation project."""
        from components.project_dialogs import NewProjectDialog
        log_info("Create New Project action triggered.")

        # Get available plugins
        plugins = {}
        plugins_dir = "plugins"
        if os.path.isdir(plugins_dir):
            for item in os.listdir(plugins_dir):
                item_path = os.path.join(plugins_dir, item)
                config_path = os.path.join(item_path, "config.json")
                if os.path.isdir(item_path) and os.path.exists(config_path):
                    try:
                        import json
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                        display_name = config_data.get("display_name", item)
                        plugins[display_name] = item
                    except Exception as e:
                        log_debug(f"Could not read config for plugin '{item}': {e}")

        dialog = NewProjectDialog(self.mw, available_plugins=plugins)
        if dialog.exec_() != dialog.Accepted:
            log_info("New project dialog cancelled.")
            return

        info = dialog.get_project_info()
        if not info:
            return

        # Create project using ProjectManager
        from core.project_manager import ProjectManager
        self.mw.project_manager = ProjectManager()

        success = self.mw.project_manager.create_new_project(
            project_dir=info['directory'],
            name=info['name'],
            plugin_name=info['plugin'],
            description=info['description']
        )

        if success:
            log_info(f"Project '{info['name']}' created successfully.")
            QMessageBox.information(
                self.mw,
                "Project Created",
                f"Project '{info['name']}' has been created at:\n{info['directory']}\n\n"
                f"You can now import blocks into this project."
            )

            # Enable project-specific actions
            if hasattr(self.mw, 'close_project_action'):
                self.mw.close_project_action.setEnabled(True)
            if hasattr(self.mw, 'import_block_action'):
                self.mw.import_block_action.setEnabled(True)
            if hasattr(self.mw, 'add_block_button'):
                self.mw.add_block_button.setEnabled(True)

            # Update UI
            self.ui_updater.update_title()
            self.ui_updater.populate_blocks()
        else:
            QMessageBox.critical(
                self.mw,
                "Project Creation Failed",
                f"Failed to create project at:\n{info['directory']}"
            )

    def open_project_action(self):
        """Open an existing translation project."""
        from PyQt5.QtWidgets import QFileDialog
        log_info("Open Project action triggered.")

        # Open file dialog directly
        start_dir = os.path.expanduser("~")
        project_path, _ = QFileDialog.getOpenFileName(
            self.mw,
            "Open Project",
            start_dir,
            "Project Files (*.uiproj);;All Files (*)"
        )

        if not project_path:
            log_info("Open project cancelled.")
            return

        # Load project using ProjectManager
        from core.project_manager import ProjectManager
        self.mw.project_manager = ProjectManager()

        success = self.mw.project_manager.load(project_path)

        if success:
            project = self.mw.project_manager.project
            log_info(f"Project '{project.name}' loaded successfully.")

            # Enable project-specific actions
            if hasattr(self.mw, 'close_project_action'):
                self.mw.close_project_action.setEnabled(True)
            if hasattr(self.mw, 'import_block_action'):
                self.mw.import_block_action.setEnabled(True)
            if hasattr(self.mw, 'add_block_button'):
                self.mw.add_block_button.setEnabled(True)

            # Update UI to show blocks
            self.ui_updater.update_title()
            self._populate_blocks_from_project()

            QMessageBox.information(
                self.mw,
                "Project Opened",
                f"Project '{project.name}' loaded successfully.\n\n"
                f"Plugin: {project.plugin_name}\n"
                f"Blocks: {len(project.blocks)}"
            )
        else:
            QMessageBox.critical(
                self.mw,
                "Project Load Failed",
                f"Failed to load project from:\n{project_path}"
            )

    def close_project_action(self):
        """Close the current project."""
        log_info("Close Project action triggered.")

        if self.mw.unsaved_changes:
            reply = QMessageBox.question(
                self.mw,
                'Unsaved Changes',
                "Save changes before closing project?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                if not self.save_data_action(ask_confirmation=False):
                    return
            elif reply == QMessageBox.Cancel:
                return

        # Clear project
        self.mw.project_manager = None

        # Clear UI
        self.mw.data = []
        self.mw.edited_data = {}
        self.mw.block_names = {}
        self.mw.current_block_idx = -1
        self.mw.current_string_idx = -1
        self.mw.unsaved_changes = False

        # Disable project-specific actions
        if hasattr(self.mw, 'close_project_action'):
            self.mw.close_project_action.setEnabled(False)
        if hasattr(self.mw, 'import_block_action'):
            self.mw.import_block_action.setEnabled(False)
        if hasattr(self.mw, 'add_block_button'):
            self.mw.add_block_button.setEnabled(False)

        # Update UI
        self.ui_updater.update_title()
        self.ui_updater.populate_blocks()
        self.ui_updater.populate_strings_for_block(-1)

        log_info("Project closed.")

    def import_block_action(self):
        """Import a new block into the current project."""
        from components.project_dialogs import ImportBlockDialog
        log_info("Import Block action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            QMessageBox.warning(
                self.mw,
                "No Project",
                "Please open or create a project first."
            )
            return

        dialog = ImportBlockDialog(self.mw, project_manager=self.mw.project_manager)
        if dialog.exec_() != dialog.Accepted:
            log_info("Import block dialog cancelled.")
            return

        info = dialog.get_block_info()
        if not info:
            return

        # Import block using ProjectManager
        block = self.mw.project_manager.add_block(
            name=info['name'],
            source_file_path=info['source_file'],
            translation_file_path=info.get('translation_file'),
            description=info['description']
        )

        if block:
            log_info(f"Block '{info['name']}' imported successfully.")

            # Update UI
            self._populate_blocks_from_project()

            QMessageBox.information(
                self.mw,
                "Block Imported",
                f"Block '{info['name']}' has been imported into the project."
            )
        else:
            QMessageBox.critical(
                self.mw,
                "Import Failed",
                f"Failed to import block from:\n{info['source_file']}"
            )

    def _populate_blocks_from_project(self):
        """Populate block list from current project and load data."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        # Clear current data
        self.mw.block_list_widget.clear()
        self.mw.data = []
        self.mw.edited_data = {}
        self.mw.block_names = {}

        # Load each block's data
        for block_idx, block in enumerate(self.mw.project_manager.project.blocks):
            # Add block name to block_names dict
            self.mw.block_names[str(block_idx)] = block.name

            # Get absolute paths for source and translation files
            source_path = self.mw.project_manager.get_absolute_path(block.source_file)
            translation_path = self.mw.project_manager.get_absolute_path(block.translation_file)

            # Load source data
            block_data = []
            if os.path.exists(source_path):
                file_extension = os.path.splitext(source_path)[1].lower()
                if file_extension == '.json':
                    file_content, error = load_json_file(source_path, parent_widget=self.mw)
                elif file_extension == '.txt':
                    file_content, error = load_text_file(source_path, parent_widget=self.mw)
                else:
                    log_warning(f"Unsupported file type for block {block.name}: {file_extension}")
                    self.mw.data.append([])
                    continue

                if error:
                    log_error(f"Failed to load block {block.name}: {error}")
                    self.mw.data.append([])
                    continue

                # Parse data using current game rules
                # The plugin returns a list of blocks (data strings), but for projects
                # each file represents ONE block, so we take the first block from the parsed result
                if self.mw.current_game_rules:
                    parsed_data, _ = self.mw.current_game_rules.load_data_from_json_obj(file_content)
                    # Take the first block from parsed data (index 0), which is the list of strings
                    block_data = parsed_data[0] if parsed_data and len(parsed_data) > 0 else []
                else:
                    log_warning(f"No game rules to parse block {block.name}")
            else:
                log_warning(f"Source file not found for block {block.name}: {source_path}")

            self.mw.data.append(block_data if block_data else [])

        # Load edited_file_data (for multi-block editing compatibility)
        self.mw.edited_file_data = []
        for block in self.mw.project_manager.project.blocks:
            translation_path = self.mw.project_manager.get_absolute_path(block.translation_file)
            edited_block_data = []

            if os.path.exists(translation_path):
                file_extension = os.path.splitext(translation_path)[1].lower()
                if file_extension == '.json':
                    file_content, error = load_json_file(translation_path, parent_widget=self.mw)
                elif file_extension == '.txt':
                    file_content, error = load_text_file(translation_path, parent_widget=self.mw)
                else:
                    self.mw.edited_file_data.append([])
                    continue

                if not error and self.mw.current_game_rules:
                    parsed_edited_data, _ = self.mw.current_game_rules.load_data_from_json_obj(file_content)
                    # Take the first block from parsed data (index 0), which is the list of strings
                    edited_block_data = parsed_edited_data[0] if parsed_edited_data and len(parsed_edited_data) > 0 else []

            self.mw.edited_file_data.append(edited_block_data if edited_block_data else [])

        # Update paths for old-style save/load compatibility
        if self.mw.data:
            # Use first block's paths as "current" file for legacy operations
            first_block = self.mw.project_manager.project.blocks[0]
            self.mw.json_path = self.mw.project_manager.get_absolute_path(first_block.source_file)
            self.mw.edited_json_path = self.mw.project_manager.get_absolute_path(first_block.translation_file)

        # Perform initial scan
        self._perform_initial_silent_scan_all_issues()

        # Update UI
        self.ui_updater.populate_blocks()
        self.ui_updater.update_statusbar_paths()

    def delete_block_action(self):
        """Delete the currently selected block from the project."""
        log_info("Delete Block action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            QMessageBox.warning(self.mw, "No Project", "No project is currently open.")
            return

        current_item = self.mw.block_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self.mw, "No Block Selected", "Please select a block to delete.")
            return

        block_idx = current_item.data(Qt.UserRole)
        if block_idx < 0 or block_idx >= len(self.mw.project_manager.project.blocks):
            QMessageBox.critical(self.mw, "Delete Error", "Invalid block index.")
            return

        block = self.mw.project_manager.project.blocks[block_idx]
        block_name = block.name

        # Confirm deletion
        reply = QMessageBox.question(
            self.mw,
            'Delete Block',
            f"Are you sure you want to delete block '{block_name}'?\n\n"
            f"This will remove the block from the project, but the source files will not be deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Remove block from project using block ID
        success = self.mw.project_manager.project.remove_block(block.id)
        if success:
            self.mw.project_manager.save()
            log_info(f"Block '{block_name}' removed from project.")

            # Update UI
            self._populate_blocks_from_project()

            QMessageBox.information(
                self.mw,
                "Block Deleted",
                f"Block '{block_name}' has been removed from the project."
            )
        else:
            QMessageBox.critical(self.mw, "Delete Error", "Failed to remove block.")

    def move_block_up_action(self):
        """Move the currently selected block up in the list."""
        log_info("Move Block Up action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        current_item = self.mw.block_list_widget.currentItem()
        if not current_item:
            return

        block_idx = current_item.data(Qt.UserRole)
        if block_idx <= 0:
            return  # Already at top

        # Swap blocks in project
        self.mw.project_manager.project.blocks[block_idx], self.mw.project_manager.project.blocks[block_idx - 1] = \
            self.mw.project_manager.project.blocks[block_idx - 1], self.mw.project_manager.project.blocks[block_idx]

        # Save project
        self.mw.project_manager.save()

        # Reload UI and reselect moved block
        self._populate_blocks_from_project()
        if self.mw.block_list_widget.count() > block_idx - 1:
            self.mw.block_list_widget.setCurrentRow(block_idx - 1)

        log_info(f"Block moved up from index {block_idx} to {block_idx - 1}.")

    def move_block_down_action(self):
        """Move the currently selected block down in the list."""
        log_info("Move Block Down action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        current_item = self.mw.block_list_widget.currentItem()
        if not current_item:
            return

        block_idx = current_item.data(Qt.UserRole)
        if block_idx >= len(self.mw.project_manager.project.blocks) - 1:
            return  # Already at bottom

        # Swap blocks in project
        self.mw.project_manager.project.blocks[block_idx], self.mw.project_manager.project.blocks[block_idx + 1] = \
            self.mw.project_manager.project.blocks[block_idx + 1], self.mw.project_manager.project.blocks[block_idx]

        # Save project
        self.mw.project_manager.save()

        # Reload UI and reselect moved block
        self._populate_blocks_from_project()
        if self.mw.block_list_widget.count() > block_idx + 1:
            self.mw.block_list_widget.setCurrentRow(block_idx + 1)

        log_info(f"Block moved down from index {block_idx} to {block_idx + 1}.")