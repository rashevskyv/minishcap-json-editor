from PyQt5.QtWidgets import QApplication, QMessageBox
from utils.logging_utils import log_debug
import copy
import os
import json
from ui.settings_dialog import SettingsDialog

class MainWindowActions:
    def __init__(self, main_window):
        self.mw = main_window
        self.helper = main_window.helper
    
    def open_settings_dialog(self):
        log_debug("<<<<<<<<<< ACTION: Open Settings Dialog Triggered >>>>>>>>>>")
        
        dialog = SettingsDialog(self.mw)
        
        if not dialog.exec_():
            log_debug("Settings dialog cancelled.")
            return

        new_settings = dialog.get_settings()
        
        font_file_changed = new_settings.get('default_font_file') != self.mw.default_font_file
        
        if dialog.plugin_changed_requires_restart or dialog.theme_changed_requires_restart or font_file_changed:
            log_debug(f"Restart required. Plugin change: {dialog.plugin_changed_requires_restart}, Theme change: {dialog.theme_changed_requires_restart}, Font file change: {font_file_changed}")
            
            self.mw.current_font_size = new_settings.get('font_size')
            self.mw.show_multiple_spaces_as_dots = new_settings.get('show_multiple_spaces_as_dots')
            self.mw.space_dot_color_hex = new_settings.get('space_dot_color_hex')
            self.mw.restore_unsaved_on_startup = new_settings.get('restore_unsaved_on_startup')
            self.mw.default_font_file = new_settings.get('default_font_file')

            self.mw.settings_manager.save_settings()

            self.mw.active_game_plugin = new_settings.get('active_game_plugin')
            self.mw.theme = new_settings.get('theme')
            log_debug(f"Set new active plugin: {self.mw.active_game_plugin}, theme: {self.mw.theme}, font file: {self.mw.default_font_file}")
            
            self.mw.settings_manager._save_global_settings()
            
            self.mw.is_restart_in_progress = True
            self.helper.restart_application()
        else:
            log_debug("Settings changed without restart. Applying settings.")
            
            initial_paths = (self.mw.json_path, self.mw.edited_json_path)
            restore_session_before = self.mw.restore_unsaved_on_startup

            for key, value in new_settings.items():
                if hasattr(self.mw, key):
                     setattr(self.mw, key, value)
            
            restore_session_after = self.mw.restore_unsaved_on_startup
            
            if restore_session_before and not restore_session_after and self.mw.unsaved_changes:
                reply = QMessageBox.question(self.mw, "Discard Unsaved Changes?",
                                             "You have disabled session restore.\nDo you want to discard the current unsaved changes now?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.mw.edited_data.clear()
                    self.mw.unsaved_changes = False
                    self.mw.helper.rebuild_unsaved_block_indices()
                    if hasattr(self.mw, 'ui_updater'):
                        self.mw.ui_updater.update_title()
                        self.mw.ui_updater.populate_blocks()
                        self.mw.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
                    if hasattr(self.mw, 'preview_text_edit'):
                        self.mw.preview_text_edit.viewport().update()
                    if hasattr(self.mw, 'edited_text_edit'):
                        self.mw.edited_text_edit.viewport().update()

                    log_debug("User discarded unsaved changes after disabling session restore.")

            self.mw.settings_manager.save_settings()

            self.mw.apply_font_size()
            self.mw.helper.reconfigure_all_highlighters()
            self.mw.helper.apply_text_wrap_settings()
            self.mw.ui_handler.update_editor_rules_properties()
            
            if dialog.rules_changed_requires_rescan:
                log_debug("Rules were changed. Triggering a full rescan of all issues.")
                QMessageBox.information(self.mw, "Settings Changed", "Rules have been updated. Rescanning all issues...")
                if hasattr(self.mw, 'app_action_handler'):
                    self.mw.app_action_handler.rescan_all_tags()


    def trigger_save_action(self):
        log_debug("<<<<<<<<<< ACTION: Save Triggered (via MainWindowActions) >>>>>>>>>>")
        if self.mw.app_action_handler.save_data_action(ask_confirmation=True):
             self.helper.rebuild_unsaved_block_indices()

    def trigger_revert_action(self):
        log_debug("<<<<<<<<<< ACTION: Revert Changes File Triggered (via MainWindowActions) >>>>>>>>>>")
        if self.mw.data_processor.revert_edited_file_to_original():
            log_debug("Revert successful, UI updated by DataStateProcessor.")
            self.helper.rebuild_unsaved_block_indices()
            if hasattr(self.mw.ui_updater, 'clear_all_problem_block_highlights_and_text'):
                self.mw.ui_updater.clear_all_problem_block_highlights_and_text()
        else: log_debug("Revert was cancelled or failed.")

    def trigger_undo_paste_action(self):
        log_debug("<<<<<<<<<< ACTION: Undo Paste Block Triggered (via MainWindowActions) >>>>>>>>>>")
        if not self.mw.can_undo_paste:
            QMessageBox.information(self.mw, "Undo Paste", "Nothing to undo for the last paste operation.")
            if hasattr(self.mw, 'statusBar'): self.mw.statusBar.showMessage("Nothing to undo for paste.", 2000)
            return

        block_to_refresh_ui_for = self.mw.before_paste_block_idx_affected

        keys_to_remove_from_edited_data = [k for k in self.mw.edited_data.keys() if k[0] == block_to_refresh_ui_for]
        for key_to_remove in keys_to_remove_from_edited_data:
            del self.mw.edited_data[key_to_remove]
        for key_snapshot, value_snapshot in self.mw.before_paste_edited_data_snapshot.items():
            self.mw.edited_data[key_snapshot] = value_snapshot
        
        keys_to_remove_from_problems = [k for k in self.mw.problems_per_subline.keys() if k[0] == block_to_refresh_ui_for]
        for key_to_remove in keys_to_remove_from_problems:
            del self.mw.problems_per_subline[key_to_remove]
        for key_snapshot, value_snapshot in self.mw.before_paste_problems_per_subline_snapshot.items():
            self.mw.problems_per_subline[key_snapshot] = value_snapshot.copy() 

        self.helper.rebuild_unsaved_block_indices() 
        self.mw.unsaved_changes = bool(self.mw.edited_data) 
        
        if hasattr(self.mw, 'title_status_bar_updater'):
            self.mw.title_status_bar_updater.update_title()
        elif hasattr(self.mw.ui_updater, 'update_title'):
             self.mw.ui_updater.update_title()

        self.mw.is_programmatically_changing_text = True 

        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'highlightManager'):
            preview_edit.highlightManager.clearAllProblemHighlights() 

        if hasattr(self.mw, 'block_list_updater'):
            self.mw.block_list_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)
        elif hasattr(self.mw.ui_updater, 'update_block_item_text_with_problem_count'):
            self.mw.ui_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)

        if hasattr(self.mw, 'preview_updater') and hasattr(self.mw.preview_updater, 'update_preview_for_block'):
            self.mw.preview_updater.update_preview_for_block(self.mw.current_block_idx)
        elif hasattr(self.mw.ui_updater, 'populate_strings_for_block'):
            self.mw.ui_updater.populate_strings_for_block(self.mw.current_block_idx)
        
        if hasattr(self.mw, 'editor_state_updater') and hasattr(self.mw.editor_state_updater, 'update_editor_content'):
             self.mw.editor_state_updater.update_editor_content()
        elif hasattr(self.mw.ui_updater, 'update_text_views'):
            self.mw.ui_updater.update_text_views()
        
        if self.mw.current_block_idx != block_to_refresh_ui_for:
            if hasattr(self.mw, 'block_list_updater'):
                self.mw.block_list_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)
            elif hasattr(self.mw.ui_updater, 'update_block_item_text_with_problem_count'):
                self.mw.ui_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)

        self.mw.is_programmatically_changing_text = False 
        self.mw.can_undo_paste = False
        if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(False)
        if hasattr(self.mw, 'statusBar'): self.mw.statusBar.showMessage("Last paste operation undone.", 2000)

    def trigger_reload_tag_mappings(self):
        log_debug("<<<<<<<<<< ACTION: Reload Tag Mappings Triggered (via MainWindowActions) >>>>>>>>>>")
        
        if not self.mw.settings_manager: return
        plugin_config_path = self.mw.settings_manager._get_plugin_config_path()
        if not plugin_config_path or not os.path.exists(plugin_config_path):
            QMessageBox.warning(self.mw, "Reload Error", "Plugin configuration file not found.")
            return

        try:
            with open(plugin_config_path, 'r', encoding='utf-8') as f:
                plugin_data = json.load(f)
            
            if "default_tag_mappings" in plugin_data:
                self.mw.default_tag_mappings = plugin_data["default_tag_mappings"]
                QMessageBox.information(self.mw, "Tag Mappings Reloaded", f"Default tag mappings reloaded from\n{os.path.basename(plugin_config_path)}.")
                if self.mw.current_block_idx != -1:
                    if QMessageBox.question(self.mw, "Rescan Block", "Rescan the current block with the new mappings?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
                        self.mw.app_action_handler.rescan_issues_for_single_block(self.mw.current_block_idx, use_default_mappings=True)
            else:
                QMessageBox.warning(self.mw, "Reload Error", "'default_tag_mappings' not found in plugin config.")

        except Exception as e:
            QMessageBox.critical(self.mw, "Reload Error", f"Failed to read plugin config:\n{e}")

    def handle_add_tag_mapping_request(self, bracket_tag: str, curly_tag: str):
        log_debug(f"MainWindowActions: Received request to map '{bracket_tag}' -> '{curly_tag}'")
        if not bracket_tag or not curly_tag:
            QMessageBox.warning(self.mw, "Add Tag Mapping Error", "Both tags must be non-empty.")
            return
        if not hasattr(self.mw, 'default_tag_mappings'): self.mw.default_tag_mappings = {}
        if bracket_tag in self.mw.default_tag_mappings and self.mw.default_tag_mappings[bracket_tag] == curly_tag:
            QMessageBox.information(self.mw, "Add Tag Mapping", f"Mapping '{bracket_tag}' -> '{curly_tag}' already exists.")
            return
        reply = QMessageBox.Yes
        if bracket_tag in self.mw.default_tag_mappings:
            reply = QMessageBox.question(self.mw, "Confirm Overwrite",
                                         f"Tag '{bracket_tag}' is already mapped to '{self.mw.default_tag_mappings[bracket_tag]}'.\n"
                                         f"Overwrite with '{curly_tag}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.mw.default_tag_mappings[bracket_tag] = curly_tag
            log_debug(f"  Added/Updated mapping: {bracket_tag} -> {curly_tag}. Total mappings: {len(self.mw.default_tag_mappings)}")
            QMessageBox.information(self.mw, "Tag Mapping Added",
                                    f"Mapping '{bracket_tag}' -> '{curly_tag}' has been added/updated.\n"
                                    "This change will be saved to the plugin's config file when settings are saved.")
            if self.mw.current_block_idx != -1:
                if QMessageBox.question(self.mw, "Rescan Block", "Rescan the current block with the new mapping now?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
                    self.mw.app_action_handler.rescan_issues_for_single_block(self.mw.current_block_idx, use_default_mappings=True)
        else: log_debug("  User cancelled overwrite or no action taken.")