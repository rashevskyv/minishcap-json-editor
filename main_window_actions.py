from PyQt5.QtWidgets import QApplication, QMessageBox
from utils import log_debug
import copy
import os

class MainWindowActions:
    def __init__(self, main_window):
        self.mw = main_window
        self.helper = main_window.helper

    def trigger_save_action(self):
        log_debug("<<<<<<<<<< ACTION: Save Triggered (via MainWindowActions) >>>>>>>>>>")
        if self.mw.app_action_handler.save_data_action(ask_confirmation=True):
             self.helper.rebuild_unsaved_block_indices()

    def trigger_revert_action(self):
        log_debug("<<<<<<<<<< ACTION: Revert Changes File Triggered (via MainWindowActions) >>>>>>>>>>")
        if self.mw.data_processor.revert_edited_file_to_original():
            log_debug("Revert successful, UI updated by DataStateProcessor.")
            if hasattr(self.mw, 'critical_problem_lines_per_block'): self.mw.critical_problem_lines_per_block.clear()
            if hasattr(self.mw, 'warning_problem_lines_per_block'): self.mw.warning_problem_lines_per_block.clear()
            if hasattr(self.mw, 'width_exceeded_lines_per_block'): self.mw.width_exceeded_lines_per_block.clear()
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

        self.mw.edited_data = dict(self.mw.before_paste_edited_data_snapshot)
        self.mw.critical_problem_lines_per_block = copy.deepcopy(self.mw.before_paste_critical_problems_snapshot)
        self.mw.warning_problem_lines_per_block = copy.deepcopy(self.mw.before_paste_warning_problems_snapshot)
        self.mw.width_exceeded_lines_per_block = copy.deepcopy(self.mw.before_paste_width_exceeded_snapshot)

        self.helper.rebuild_unsaved_block_indices()
        self.mw.unsaved_changes = bool(self.mw.edited_data)
        self.mw.ui_updater.update_title()

        self.mw.is_programmatically_changing_text = True
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'clearAllProblemTypeHighlights'):
            preview_edit.clearAllProblemTypeHighlights()

        if hasattr(self.mw.ui_updater, 'update_block_item_text_with_problem_count'):
            self.mw.ui_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)

        self.mw.ui_updater.populate_strings_for_block(self.mw.current_block_idx)

        if self.mw.current_block_idx != block_to_refresh_ui_for:
            if hasattr(self.mw.ui_updater, 'update_block_item_text_with_problem_count'):
                self.mw.ui_updater.update_block_item_text_with_problem_count(block_to_refresh_ui_for)

        self.mw.is_programmatically_changing_text = False
        self.mw.can_undo_paste = False
        if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(False)
        if hasattr(self.mw, 'statusBar'): self.mw.statusBar.showMessage("Last paste operation undone.", 2000)

    def trigger_reload_tag_mappings(self):
        log_debug("<<<<<<<<<< ACTION: Reload Tag Mappings Triggered (via MainWindowActions) >>>>>>>>>>")
        if self.mw.settings_manager.reload_default_tag_mappings():
            QMessageBox.information(self.mw, "Tag Mappings Reloaded", "Default tag mappings have been reloaded from settings.json.")
            if self.mw.current_block_idx != -1:
                block_name = self.mw.block_names.get(str(self.mw.current_block_idx), f"Block {self.mw.current_block_idx}")
                if QMessageBox.question(self.mw, "Rescan Tags",
                                       f"Do you want to rescan tags in the current block ('{block_name}') with the new mappings now?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
                    self.mw.app_action_handler.rescan_issues_for_single_block(self.mw.current_block_idx, use_default_mappings=True)
            else:
                 if QMessageBox.question(self.mw, "Rescan Tags",
                                       "No block is currently selected. Do you want to rescan all tags in all blocks?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
                    self.mw.app_action_handler.rescan_all_tags()
        else: QMessageBox.warning(self.mw, "Reload Error", "Could not reload tag mappings. Check settings.json or console logs.")

    def handle_add_tag_mapping_request(self, bracket_tag: str, curly_tag: str):
        log_debug(f"MainWindowActions: Received request to map '{bracket_tag}' -> '{curly_tag}'")
        if not bracket_tag or not curly_tag:
            log_debug("  Error: Empty bracket_tag or curly_tag.")
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
                                    "This change will be saved to settings.json when the application is closed.")
            if self.mw.current_block_idx != -1:
                block_name = self.mw.block_names.get(str(self.mw.current_block_idx), f"Block {self.mw.current_block_idx}")
                if QMessageBox.question(self.mw, "Rescan Tags",
                                       f"Do you want to rescan tags in the current block ('{block_name}') with the new mapping now?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
                    self.mw.app_action_handler.rescan_issues_for_single_block(self.mw.current_block_idx, use_default_mappings=True)
        else: log_debug("  User cancelled overwrite or no action taken.")