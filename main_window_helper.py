# --- START OF FILE handlers/main_window_helper.py ---
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtCore import QRect, QProcess
from utils.logging_utils import log_debug, log_info
import copy
import os
import sys

if TYPE_CHECKING:
    from main import MainWindow

class MainWindowHelper:
    def __init__(self, main_window: MainWindow):
        self.mw = main_window

    def get_font_map_for_string(self, block_idx: int, string_idx: int) -> dict:
        metadata_key = (block_idx, string_idx)
        string_meta = self.mw.string_metadata.get(metadata_key, {})
        
        custom_font_file = string_meta.get("font_file")
        if custom_font_file and custom_font_file in self.mw.all_font_maps:
            return self.mw.all_font_maps[custom_font_file]
            
        return self.mw.font_map

    def restart_application(self):
        log_info("Restarting application...")
        self.mw.close()
        QProcess.startDetached(sys.executable, sys.argv)

    def rebuild_unsaved_block_indices(self):
        self.mw.unsaved_block_indices.clear()
        for block_idx, _ in self.mw.edited_data.keys():
            self.mw.unsaved_block_indices.add(block_idx)
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
        preview_wrap_mode = self.mw.preview_text_edit.WidgetWidth if self.mw.preview_wrap_lines else self.mw.preview_text_edit.NoWrap
        editors_wrap_mode = self.mw.edited_text_edit.WidgetWidth if self.mw.editors_wrap_lines else self.mw.edited_text_edit.NoWrap
        if hasattr(self.mw, 'preview_text_edit'): self.mw.preview_text_edit.setLineWrapMode(preview_wrap_mode)
        if hasattr(self.mw, 'original_text_edit'): self.mw.original_text_edit.setLineWrapMode(editors_wrap_mode)
        if hasattr(self.mw, 'edited_text_edit'): self.mw.edited_text_edit.setLineWrapMode(editors_wrap_mode)

    def reconfigure_all_highlighters(self):
        # Compose newline CSS
        nl_color = getattr(self.mw, 'newline_color_rgba', "#A020F0")
        nl_css_parts = [f"color: {nl_color}"]
        if getattr(self.mw, 'newline_bold', True): nl_css_parts.append("font-weight: bold")
        if getattr(self.mw, 'newline_italic', False): nl_css_parts.append("font-style: italic")
        if getattr(self.mw, 'newline_underline', False): nl_css_parts.append("text-decoration: underline")
        newline_css_str = "; ".join(nl_css_parts) + ";"

        common_args = {
            "newline_symbol": self.mw.newline_display_symbol, "newline_css_str": newline_css_str,
            "tag_css_str": "", "show_multiple_spaces_as_dots": self.mw.show_multiple_spaces_as_dots,
            "space_dot_color_hex": self.mw.space_dot_color_hex, "bracket_tag_color_hex": getattr(self.mw, 'tag_color_rgba', "#FF8C00")
        }
        text_edits_with_highlighters = []
        if hasattr(self.mw, 'preview_text_edit') and hasattr(self.mw.preview_text_edit, 'highlighter'): text_edits_with_highlighters.append(self.mw.preview_text_edit)
        if hasattr(self.mw, 'original_text_edit') and hasattr(self.mw.original_text_edit, 'highlighter'): text_edits_with_highlighters.append(self.mw.original_text_edit)
        if hasattr(self.mw, 'edited_text_edit') and hasattr(self.mw.edited_text_edit, 'highlighter'): text_edits_with_highlighters.append(self.mw.edited_text_edit)
        for text_edit in text_edits_with_highlighters:
            if text_edit.highlighter:
                text_edit.highlighter.reconfigure_styles(**common_args)
                text_edit.highlighter.rehighlight()

    def prepare_to_close(self):
        self.mw.last_selected_block_index = self.mw.current_block_idx
        self.mw.last_selected_string_index = self.mw.current_string_idx
        
        if self.mw.edited_text_edit:
            self.mw.last_cursor_position_in_edited = self.mw.edited_text_edit.textCursor().position()
            self.mw.last_edited_text_edit_scroll_value_v = self.mw.edited_text_edit.verticalScrollBar().value()
            self.mw.last_edited_text_edit_scroll_value_h = self.mw.edited_text_edit.horizontalScrollBar().value()
        
        if self.mw.preview_text_edit:
            self.mw.last_preview_text_edit_scroll_value_v = self.mw.preview_text_edit.verticalScrollBar().value()
        if self.mw.original_text_edit:
            self.mw.last_original_text_edit_scroll_value_v = self.mw.original_text_edit.verticalScrollBar().value()
            self.mw.last_original_text_edit_scroll_value_h = self.mw.original_text_edit.horizontalScrollBar().value()

        if self.mw.search_panel_widget:
            self.mw.search_history_to_save = self.mw.search_panel_widget.get_history()
        
        self.mw.window_was_maximized_on_close = self.mw.isMaximized()
        if self.mw.window_was_maximized_on_close:
            self.mw.window_normal_geometry_on_close = self.mw.normalGeometry()
        else:
            self.mw.window_normal_geometry_on_close = self.mw.geometry()


    def restore_state_after_settings_load(self):
        log_info("Restoring state after settings load.")
        
        if hasattr(self.mw, 'window_geometry_to_restore') and self.mw.window_geometry_to_restore:
            geom_dict = self.mw.window_geometry_to_restore
            if all(k in geom_dict for k in ('x', 'y', 'width', 'height')):
                self.mw.setGeometry(geom_dict['x'], geom_dict['y'], geom_dict['width'], geom_dict['height'])
            if hasattr(self.mw, 'window_was_maximized_at_save') and self.mw.window_was_maximized_at_save:
                self.mw.showMaximized()

        # Priority 1: Auto-open last project from recent projects
        if hasattr(self.mw, 'recent_projects') and self.mw.recent_projects and hasattr(self.mw, 'app_action_handler'):
            last_project_path = self.mw.recent_projects[0]
            if os.path.exists(last_project_path):
                log_info(f"Auto-opening last project from recent projects: {last_project_path}")
                if hasattr(self.mw.app_action_handler, '_open_recent_project'):
                    self.mw.app_action_handler._open_recent_project(last_project_path)
                else:
                    log_info("app_action_handler._open_recent_project not available")
            else:
                log_info(f"Last project path does not exist: {last_project_path}")
        # Priority 2: Auto-open last file if no projects
        elif self.mw.initial_load_path and os.path.exists(self.mw.initial_load_path):
            log_info(f"Attempting to load initial file from settings: {self.mw.initial_load_path}")
            self.mw.app_action_handler.load_all_data_for_path(self.mw.initial_load_path, self.mw.initial_edited_load_path, is_initial_load_from_settings=True)

            if self.mw.data and 0 <= self.mw.last_selected_block_index < len(self.mw.data):
                self.mw.block_list_widget.currentItemChanged.disconnect()
                self.mw.block_list_widget.setCurrentRow(self.mw.last_selected_block_index)

                selected_item = self.mw.block_list_widget.item(self.mw.last_selected_block_index)
                if selected_item:
                    self.mw.list_selection_handler.block_selected(selected_item, None)

                self.mw.block_list_widget.currentItemChanged.connect(self.mw.list_selection_handler.block_selected)
                QApplication.processEvents()

                if self.mw.current_block_idx == self.mw.last_selected_block_index and \
                   0 <= self.mw.last_selected_string_index < len(self.mw.data[self.mw.last_selected_block_index]):
                    self.mw.list_selection_handler.string_selected_from_preview(self.mw.last_selected_string_index)
                    QApplication.processEvents()
                    if self.mw.edited_text_edit:
                        doc_len = self.mw.edited_text_edit.document().characterCount() -1
                        pos_to_set = min(self.mw.last_cursor_position_in_edited, doc_len if doc_len >= 0 else 0)

                        cursor = self.mw.edited_text_edit.textCursor()
                        cursor.setPosition(pos_to_set)
                        self.mw.edited_text_edit.setTextCursor(cursor)
                        self.mw.edited_text_edit.ensureCursorVisible()

                        self.mw.edited_text_edit.verticalScrollBar().setValue(self.mw.last_edited_text_edit_scroll_value_v)
                        self.mw.edited_text_edit.horizontalScrollBar().setValue(self.mw.last_edited_text_edit_scroll_value_h)
                        if self.mw.preview_text_edit:
                            self.mw.preview_text_edit.verticalScrollBar().setValue(self.mw.last_preview_text_edit_scroll_value_v)
                        if self.mw.original_text_edit:
                            self.mw.original_text_edit.verticalScrollBar().setValue(self.mw.last_original_text_edit_scroll_value_v)
                            self.mw.original_text_edit.horizontalScrollBar().setValue(self.mw.last_original_text_edit_scroll_value_h)
        # Priority 3: No file or project to load
        elif not self.mw.json_path:
             log_info("No file auto-loaded, updating initial UI state.")
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