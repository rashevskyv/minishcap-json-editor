from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtCore import QRect, QProcess
from utils.logging_utils import log_debug
import copy
import os
import sys

class MainWindowHelper:
    def __init__(self, main_window):
        self.mw = main_window

    def restart_application(self):
        log_debug("Restarting application...")
        self.mw.close()
        QProcess.startDetached(sys.executable, sys.argv)

    def rebuild_unsaved_block_indices(self):
        self.mw.unsaved_block_indices.clear()
        for block_idx, _ in self.mw.edited_data.keys():
            self.mw.unsaved_block_indices.add(block_idx)
        log_debug(f"Rebuilt unsaved_block_indices: {self.mw.unsaved_block_indices}")
        if hasattr(self.mw, 'block_list_widget'):
             self.mw.block_list_widget.viewport().update()

    def execute_find_next_shortcut(self):
        query_to_use = ""
        case_sensitive_to_use = False
        search_in_original_to_use = False
        ignore_tags_to_use = True

        if self.mw.search_panel_widget.isVisible():
            query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use = self.mw.search_panel_widget.get_search_parameters()
            if not query_to_use:
                self.mw.search_panel_widget.set_status_message("Введіть запит для F3", is_error=True)
                self.mw.search_panel_widget.focus_search_input()
                return
        else:
            query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use = self.mw.search_handler.get_current_search_params()
            if not query_to_use:
                self.toggle_search_panel()
                self.mw.search_panel_widget.set_status_message("Введіть запит", is_error=True)
                return

        found = self.mw.search_handler.find_next(query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use)
        if not found and not self.mw.search_panel_widget.isVisible():
            QMessageBox.information(self.mw, "Пошук", f"Не знайдено: \"{query_to_use}\"")

    def execute_find_previous_shortcut(self):
        query_to_use = ""
        case_sensitive_to_use = False
        search_in_original_to_use = False
        ignore_tags_to_use = True

        if self.mw.search_panel_widget.isVisible():
            query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use = self.mw.search_panel_widget.get_search_parameters()
            if not query_to_use:
                self.mw.search_panel_widget.set_status_message("Введіть запит для Shift+F3", is_error=True)
                self.mw.search_panel_widget.focus_search_input()
                return
        else:
            query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use = self.mw.search_handler.get_current_search_params()
            if not query_to_use:
                self.toggle_search_panel()
                self.mw.search_panel_widget.set_status_message("Введіть запит", is_error=True)
                return

        found = self.mw.search_handler.find_previous(query_to_use, case_sensitive_to_use, search_in_original_to_use, ignore_tags_to_use)
        if not found and not self.mw.search_panel_widget.isVisible():
            QMessageBox.information(self.mw, "Пошук", f"Не знайдено: \"{query_to_use}\"")

    def handle_panel_find_next(self, query, case_sensitive, search_in_original, ignore_tags):
        self.mw.search_handler.find_next(query, case_sensitive, search_in_original, ignore_tags)

    def handle_panel_find_previous(self, query, case_sensitive, search_in_original, ignore_tags):
        self.mw.search_handler.find_previous(query, case_sensitive, search_in_original, ignore_tags)

    def toggle_search_panel(self):
        if self.mw.search_panel_widget.isVisible():
            self.hide_search_panel()
        else:
            self.mw.search_panel_widget.setVisible(True)
            last_query, case_sensitive, search_in_original, ignore_tags = self.mw.search_handler.get_current_search_params()

            self.mw.search_panel_widget.set_query(last_query if last_query else "")
            self.mw.search_panel_widget.set_search_options(case_sensitive, search_in_original, ignore_tags)

            if hasattr(self.mw, 'search_history_to_save'):
                 self.mw.search_panel_widget.load_history(self.mw.search_history_to_save)
            else:
                 self.mw.search_panel_widget._update_combobox_items()
            self.mw.search_panel_widget.focus_search_input()

    def hide_search_panel(self):
        self.mw.search_panel_widget.setVisible(False)
        self.mw.search_handler.clear_all_search_highlights()

    def load_all_data_for_path(self, original_file_path, manually_set_edited_path=None, is_initial_load_from_settings=False):
        self.mw.app_action_handler.load_all_data_for_path(original_file_path, manually_set_edited_path, is_initial_load_from_settings)
        self.rebuild_unsaved_block_indices()
        for editor_widget in [self.mw.preview_text_edit, self.mw.original_text_edit, self.mw.edited_text_edit]:
            if editor_widget:
                editor_widget.line_width_warning_threshold_pixels = self.mw.line_width_warning_threshold_pixels
                editor_widget.font_map = self.mw.font_map
                editor_widget.game_dialog_max_width_pixels = self.mw.game_dialog_max_width_pixels
                if hasattr(editor_widget, 'updateLineNumberAreaWidth'):
                    editor_widget.updateLineNumberAreaWidth(0)

    def apply_text_wrap_settings(self):
        log_debug(f"Applying text wrap settings: Preview wrap: {self.mw.preview_wrap_lines}, Editors wrap: {self.mw.editors_wrap_lines}")
        preview_wrap_mode = self.mw.preview_text_edit.WidgetWidth if self.mw.preview_wrap_lines else self.mw.preview_text_edit.NoWrap
        editors_wrap_mode = self.mw.edited_text_edit.WidgetWidth if self.mw.editors_wrap_lines else self.mw.edited_text_edit.NoWrap
        if hasattr(self.mw, 'preview_text_edit'): self.mw.preview_text_edit.setLineWrapMode(preview_wrap_mode)
        if hasattr(self.mw, 'original_text_edit'): self.mw.original_text_edit.setLineWrapMode(editors_wrap_mode)
        if hasattr(self.mw, 'edited_text_edit'): self.mw.edited_text_edit.setLineWrapMode(editors_wrap_mode)

    def reconfigure_all_highlighters(self):
        log_debug("MainWindowHelper: Reconfiguring all highlighters...")
        common_args = {
            "newline_symbol": self.mw.newline_display_symbol, "newline_css_str": self.mw.newline_css,
            "tag_css_str": self.mw.tag_css, "show_multiple_spaces_as_dots": self.mw.show_multiple_spaces_as_dots,
            "space_dot_color_hex": self.mw.space_dot_color_hex, "bracket_tag_color_hex": self.mw.bracket_tag_color_hex
        }
        text_edits_with_highlighters = []
        if hasattr(self.mw, 'preview_text_edit') and hasattr(self.mw.preview_text_edit, 'highlighter'): text_edits_with_highlighters.append(self.mw.preview_text_edit)
        if hasattr(self.mw, 'original_text_edit') and hasattr(self.mw.original_text_edit, 'highlighter'): text_edits_with_highlighters.append(self.mw.original_text_edit)
        if hasattr(self.mw, 'edited_text_edit') and hasattr(self.mw.edited_text_edit, 'highlighter'): text_edits_with_highlighters.append(self.mw.edited_text_edit)
        for text_edit in text_edits_with_highlighters:
            if text_edit.highlighter:
                text_edit.highlighter.reconfigure_styles(**common_args)
                text_edit.highlighter.rehighlight()
        log_debug("MainWindowHelper: Highlighter reconfiguration attempt complete.")

    def prepare_to_close(self):
        log_debug("MainWindowHelper: prepare_to_close called.")
        self.mw.last_selected_block_index = self.mw.current_block_idx
        self.mw.last_selected_string_index = self.mw.current_string_idx
        
        log_debug(f"  [SAVE STATE] Block Idx: {self.mw.last_selected_block_index}, String Idx: {self.mw.last_selected_string_index}")

        if self.mw.edited_text_edit:
            self.mw.last_cursor_position_in_edited = self.mw.edited_text_edit.textCursor().position()
            self.mw.last_edited_text_edit_scroll_value_v = self.mw.edited_text_edit.verticalScrollBar().value()
            self.mw.last_edited_text_edit_scroll_value_h = self.mw.edited_text_edit.horizontalScrollBar().value()
            log_debug(f"  [SAVE STATE] Cursor Pos: {self.mw.last_cursor_position_in_edited}, Scroll V/H: {self.mw.last_edited_text_edit_scroll_value_v}/{self.mw.last_edited_text_edit_scroll_value_h}")
        
        if self.mw.preview_text_edit:
            self.mw.last_preview_text_edit_scroll_value_v = self.mw.preview_text_edit.verticalScrollBar().value()
        if self.mw.original_text_edit:
            self.mw.last_original_text_edit_scroll_value_v = self.mw.original_text_edit.verticalScrollBar().value()
            self.mw.last_original_text_edit_scroll_value_h = self.mw.original_text_edit.horizontalScrollBar().value()

        if self.mw.search_panel_widget:
            self.mw.search_history_to_save = self.mw.search_panel_widget.get_history()
            log_debug(f"MainWindowHelper: Updated search_history_to_save: {len(self.mw.search_history_to_save)} items")
        
        self.mw.window_was_maximized_on_close = self.mw.isMaximized()
        if self.mw.window_was_maximized_on_close:
            self.mw.window_normal_geometry_on_close = self.mw.normalGeometry()
        else:
            self.mw.window_normal_geometry_on_close = self.mw.geometry()


    def restore_state_after_settings_load(self):
        log_debug("MainWindowHelper: restore_state_after_settings_load called.")
        
        if hasattr(self.mw, 'window_geometry_to_restore') and self.mw.window_geometry_to_restore:
            geom_dict = self.mw.window_geometry_to_restore
            if all(k in geom_dict for k in ('x', 'y', 'width', 'height')):
                self.mw.setGeometry(geom_dict['x'], geom_dict['y'], geom_dict['width'], geom_dict['height'])
                log_debug(f"Restored window geometry from settings: {geom_dict}")
            if hasattr(self.mw, 'window_was_maximized_at_save') and self.mw.window_was_maximized_at_save:
                self.mw.showMaximized()
                log_debug("Window was maximized, restored to maximized state.")


        if self.mw.initial_load_path and os.path.exists(self.mw.initial_load_path):
            log_debug(f"MainWindowHelper: Attempting to load initial file from settings: {self.mw.initial_load_path}")
            self.mw.app_action_handler.load_all_data_for_path(self.mw.initial_load_path, self.mw.initial_edited_load_path, is_initial_load_from_settings=True)

            log_debug(f"  [RESTORE STATE] Attempting restore with Block Idx: {self.mw.last_selected_block_index}, String Idx: {self.mw.last_selected_string_index}")

            if self.mw.data and 0 <= self.mw.last_selected_block_index < len(self.mw.data):
                log_debug(f"  [RESTORE STATE] Block index {self.mw.last_selected_block_index} is valid. Setting current row...")
                self.mw.block_list_widget.currentItemChanged.disconnect()
                self.mw.block_list_widget.setCurrentRow(self.mw.last_selected_block_index)
                
                selected_item = self.mw.block_list_widget.item(self.mw.last_selected_block_index)
                if selected_item:
                    log_debug(f"  [RESTORE STATE] Manually calling block_selected for item '{selected_item.text()}'")
                    self.mw.list_selection_handler.block_selected(selected_item, None)
                else:
                    log_debug(f"  [RESTORE STATE] WARNING: Could not get item for row {self.mw.last_selected_block_index}")

                self.mw.block_list_widget.currentItemChanged.connect(self.mw.list_selection_handler.block_selected)
                QApplication.processEvents()
                
                if self.mw.current_block_idx == self.mw.last_selected_block_index and \
                   0 <= self.mw.last_selected_string_index < len(self.mw.data[self.mw.last_selected_block_index]):
                    log_debug(f"  [RESTORE STATE] String index {self.mw.last_selected_string_index} is valid. Calling string_selected_from_preview...")
                    self.mw.list_selection_handler.string_selected_from_preview(self.mw.last_selected_string_index)
                    QApplication.processEvents()
                    if self.mw.edited_text_edit:
                        doc_len = self.mw.edited_text_edit.document().characterCount() -1
                        pos_to_set = min(self.mw.last_cursor_position_in_edited, doc_len if doc_len >= 0 else 0)
                        
                        log_debug(f"  [RESTORE STATE] Setting cursor position. Target: {pos_to_set} (from saved {self.mw.last_cursor_position_in_edited}, doc len: {doc_len})")
                        cursor = self.mw.edited_text_edit.textCursor()
                        cursor.setPosition(pos_to_set)
                        self.mw.edited_text_edit.setTextCursor(cursor)
                        self.mw.edited_text_edit.ensureCursorVisible()
                        log_debug(f"  [RESTORE STATE] Cursor position set. Actual final position: {self.mw.edited_text_edit.textCursor().position()}")

                        log_debug(f"  [RESTORE STATE] Setting scollbars. Edited V/H: {self.mw.last_edited_text_edit_scroll_value_v}/{self.mw.last_edited_text_edit_scroll_value_h}, Preview V: {self.mw.last_preview_text_edit_scroll_value_v}, Original V/H: {self.mw.last_original_text_edit_scroll_value_v}/{self.mw.last_original_text_edit_scroll_value_h}")
                        self.mw.edited_text_edit.verticalScrollBar().setValue(self.mw.last_edited_text_edit_scroll_value_v)
                        self.mw.edited_text_edit.horizontalScrollBar().setValue(self.mw.last_edited_text_edit_scroll_value_h)
                        if self.mw.preview_text_edit:
                            self.mw.preview_text_edit.verticalScrollBar().setValue(self.mw.last_preview_text_edit_scroll_value_v)
                        if self.mw.original_text_edit:
                            self.mw.original_text_edit.verticalScrollBar().setValue(self.mw.last_original_text_edit_scroll_value_v)
                            self.mw.original_text_edit.horizontalScrollBar().setValue(self.mw.last_original_text_edit_scroll_value_h)
                    log_debug(f"MainWindowHelper: Restored selection to block {self.mw.last_selected_block_index}, string {self.mw.last_selected_string_index}, cursor {self.mw.last_cursor_position_in_edited}")
                else:
                    log_debug(f"MainWindowHelper: last_selected_string_index ({self.mw.last_selected_string_index}) is out of bounds for block {self.mw.last_selected_block_index}. Skipping string/cursor restore.")
            else:
                log_debug(f"MainWindowHelper: last_selected_block_index ({self.mw.last_selected_block_index}) is out of bounds or no data. Skipping selection restore.")
        elif not self.mw.json_path:
             log_debug("MainWindowHelper: No file auto-loaded, updating initial UI state.")
             self.mw.ui_updater.update_title(); self.mw.ui_updater.update_statusbar_paths()
             self.mw.ui_updater.populate_blocks()
             self.mw.ui_updater.populate_strings_for_block(-1)

        if hasattr(self.mw, 'search_history_to_save') and self.mw.search_panel_widget:
            self.mw.search_panel_widget.load_history(self.mw.search_history_to_save)
            if self.mw.search_history_to_save:
                last_query = self.mw.search_history_to_save[0]
                self.mw.search_handler.current_query = last_query
                _, cs, so, it = self.mw.search_panel_widget.get_search_parameters()
                self.mw.search_handler.is_case_sensitive = cs
                self.mw.search_handler.search_in_original = so
                self.mw.search_handler.ignore_tags_newlines = it
            log_debug(f"MainWindowHelper: Search history loaded into panel. Last query (if any) set in SearchHandler: {self.mw.search_handler.current_query}")