# --- START OF FILE handlers/main_window_event_handler.py ---
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt5.QtGui import QTextCursor, QKeyEvent
from PyQt5.QtCore import Qt
from utils.logging_utils import log_debug, log_info
from utils.utils import ALL_TAGS_PATTERN

if TYPE_CHECKING:
    from main import MainWindow

class MainWindowEventHandler:
    def __init__(self, main_window: MainWindow):
        self.mw = main_window

    def connect_signals(self):
        if hasattr(self.mw, 'open_settings_action'): self.mw.open_settings_action.triggered.connect(self.mw.actions.open_settings_dialog)
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.currentItemChanged.connect(self.mw.list_selection_handler.block_selected)
            self.mw.block_list_widget.itemDoubleClicked.connect(self.mw.list_selection_handler.rename_block)
        
        if hasattr(self.mw, 'preview_text_edit'):
            if hasattr(self.mw.preview_text_edit, 'lineClicked'):
                self.mw.preview_text_edit.lineClicked.connect(self.mw.list_selection_handler.string_selected_from_preview)
            self.mw.preview_text_edit.selectionChanged.connect(self.mw.list_selection_handler.handle_preview_selection_changed)

        if hasattr(self.mw, 'edited_text_edit'):
            self.mw.edited_text_edit.textChanged.connect(self.mw.editor_operation_handler.text_edited)
            self.mw.edited_text_edit.cursorPositionChanged.connect(self.handle_edited_cursor_position_changed)
            self.mw.edited_text_edit.selectionChanged.connect(self.handle_edited_selection_changed)
            if hasattr(self.mw, 'undo_typing_action'):
                self.mw.edited_text_edit.undoAvailable.connect(self.mw.undo_typing_action.setEnabled)
                self.mw.undo_typing_action.triggered.connect(self.mw.edited_text_edit.undo)
            if hasattr(self.mw, 'redo_typing_action'):
                self.mw.edited_text_edit.redoAvailable.connect(self.mw.redo_typing_action.setEnabled)
                self.mw.redo_typing_action.triggered.connect(self.mw.edited_text_edit.redo)
            if hasattr(self.mw.edited_text_edit, 'addTagMappingRequest'):
                self.mw.edited_text_edit.addTagMappingRequest.connect(self.mw.actions.handle_add_tag_mapping_request)
        if hasattr(self.mw, 'paste_block_action'): self.mw.paste_block_action.triggered.connect(self.mw.editor_operation_handler.paste_block_text)
        if hasattr(self.mw, 'open_action'): self.mw.open_action.triggered.connect(self.mw.app_action_handler.open_file_dialog_action)
        if hasattr(self.mw, 'open_changes_action'): self.mw.open_changes_action.triggered.connect(self.mw.app_action_handler.open_changes_file_dialog_action)
        if hasattr(self.mw, 'save_action'): self.mw.save_action.triggered.connect(self.mw.actions.trigger_save_action)
        if hasattr(self.mw, 'reload_action'): self.mw.reload_action.triggered.connect(self.mw.app_action_handler.reload_original_data_action)
        if hasattr(self.mw, 'save_as_action'): self.mw.save_as_action.triggered.connect(self.mw.app_action_handler.save_as_dialog_action)
        if hasattr(self.mw, 'revert_action'): self.mw.revert_action.triggered.connect(self.mw.actions.trigger_revert_action)
        if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.triggered.connect(self.mw.actions.trigger_undo_paste_action)
        if hasattr(self.mw, 'rescan_all_tags_action'): self.mw.rescan_all_tags_action.triggered.connect(self.mw.app_action_handler.rescan_all_tags)
        if hasattr(self.mw, 'reload_tag_mappings_action'):
            self.mw.reload_tag_mappings_action.triggered.connect(self.mw.actions.trigger_reload_tag_mappings)
        if hasattr(self.mw, 'find_action'):
            self.mw.find_action.triggered.connect(self.mw.helper.toggle_search_panel)
        if hasattr(self.mw, 'open_ai_chat_action'):
            self.mw.open_ai_chat_action.triggered.connect(self.mw.ai_chat_handler.show_chat_window)
        if hasattr(self.mw, 'search_panel_widget'):
            self.mw.search_panel_widget.close_requested.connect(self.mw.helper.hide_search_panel)
            self.mw.search_panel_widget.find_next_requested.connect(self.mw.helper.handle_panel_find_next)
            self.mw.search_panel_widget.find_previous_requested.connect(self.mw.helper.handle_panel_find_previous)
        
        if hasattr(self.mw, 'ai_translate_button') and self.mw.ai_translate_button:
            self.mw.ai_translate_button.clicked.connect(self.mw.translation_handler.translate_current_string)
        if hasattr(self.mw, 'ai_variation_button') and self.mw.ai_variation_button:
            self.mw.ai_variation_button.clicked.connect(self.mw.translation_handler.generate_variation_for_current_string)
        if hasattr(self.mw, 'auto_fix_button') and self.mw.auto_fix_button:
            self.mw.auto_fix_button.clicked.connect(self.mw.editor_operation_handler.auto_fix_current_string)
        if hasattr(self.mw, 'auto_fix_action') and self.mw.auto_fix_action: 
            self.mw.auto_fix_action.triggered.connect(self.mw.editor_operation_handler.auto_fix_current_string)
            
        if hasattr(self.mw, 'navigate_up_button'):
            self.mw.navigate_up_button.clicked.connect(lambda: self.mw.list_selection_handler.navigate_to_problem_string(direction_down=False))
        if hasattr(self.mw, 'navigate_down_button'):
            self.mw.navigate_down_button.clicked.connect(lambda: self.mw.list_selection_handler.navigate_to_problem_string(direction_down=True))
        
        if hasattr(self.mw, 'font_combobox'):
            self.mw.font_combobox.currentIndexChanged.connect(self.mw.string_settings_handler.on_font_changed)
        if hasattr(self.mw, 'width_spinbox'):
            self.mw.width_spinbox.valueChanged.connect(self.mw.string_settings_handler.on_width_changed)
        if hasattr(self.mw, 'apply_width_button'):
            self.mw.apply_width_button.clicked.connect(self.mw.string_settings_handler.apply_settings_change)

    def keyPressEvent(self, event: QKeyEvent):
        super(self.mw.__class__, self.mw).keyPressEvent(event)
        
    def closeEvent(self, event):
        log_info("Close event received.")
        self.mw.helper.prepare_to_close()
        self.mw.app_action_handler.handle_close_event(event)
        
        if event.isAccepted():
            if not self.mw.unsaved_changes and not self.mw.is_restart_in_progress:
                self.mw.settings_manager.save_settings()
            super(self.mw.__class__, self.mw).closeEvent(event)

    def handle_edited_cursor_position_changed(self):
        if self.mw.is_adjusting_cursor or self.mw.is_programmatically_changing_text:
            return

        editor = self.mw.edited_text_edit
        cursor = editor.textCursor()
        current_pos = cursor.position()
        last_pos = self.mw.previous_cursor_pos
        moved_right = current_pos > last_pos

        if not cursor.hasSelection():
            self.mw.is_adjusting_cursor = True
            
            current_block = cursor.block()
            pos_in_block = cursor.positionInBlock()
            block_text = current_block.text()
            
            for match in ALL_TAGS_PATTERN.finditer(block_text):
                tag_start, tag_end = match.span()
                if tag_start < pos_in_block < tag_end:
                    if moved_right or abs(current_pos - last_pos) > 1: # Moved right or jumped (e.g., click)
                        new_cursor_pos_abs = current_block.position() + tag_end
                    else: # Moved left
                        new_cursor_pos_abs = current_block.position() + tag_start
                    
                    cursor.setPosition(new_cursor_pos_abs)
                    editor.setTextCursor(cursor)
                    break 
            self.mw.is_adjusting_cursor = False
        
        self.mw.previous_cursor_pos = editor.textCursor().position()
        self.mw.ui_updater.update_status_bar()

    def handle_edited_selection_changed(self):
        if self.mw.is_adjusting_selection or self.mw.is_programmatically_changing_text:
            self.mw.ui_updater.update_status_bar_selection() 
            return

        editor = self.mw.edited_text_edit
        cursor = editor.textCursor()

        if not cursor.hasSelection():
            self.mw.ui_updater.update_status_bar_selection() 
            return

        self.mw.is_adjusting_selection = True
        
        doc = editor.document()
        anchor_abs = cursor.anchor()
        position_abs = cursor.position()
        
        anchor_block = doc.findBlock(anchor_abs)
        position_block = doc.findBlock(position_abs)

        if anchor_block.blockNumber() != position_block.blockNumber():
            self.mw.is_adjusting_selection = False
            self.mw.ui_updater.update_status_bar_selection()
            return
            
        current_block = anchor_block
        block_text = current_block.text()
        
        original_anchor_rel = anchor_abs - current_block.position()
        original_position_rel = position_abs - current_block.position()
        
        current_sel_start_rel = min(original_anchor_rel, original_position_rel)
        current_sel_end_rel = max(original_anchor_rel, original_position_rel)

        new_sel_start_rel = current_sel_start_rel
        new_sel_end_rel = current_sel_end_rel
        
        adjusted = False

        for match in ALL_TAGS_PATTERN.finditer(block_text):
            tag_start, tag_end = match.span()
            
            if tag_start < current_sel_start_rel < tag_end:
                new_sel_start_rel = min(new_sel_start_rel, tag_start)
                adjusted = True
            
            if tag_start < current_sel_end_rel < tag_end:
                new_sel_end_rel = max(new_sel_end_rel, tag_end)
                adjusted = True
        
        if new_sel_start_rel > new_sel_end_rel :
            new_sel_start_rel = current_sel_start_rel
            new_sel_end_rel = current_sel_end_rel
            adjusted = False


        if adjusted and (new_sel_start_rel != current_sel_start_rel or new_sel_end_rel != current_sel_end_rel):
            new_cursor = QTextCursor(current_block)
            
            final_anchor_abs = current_block.position() + (new_sel_start_rel if original_anchor_rel == current_sel_start_rel else new_sel_end_rel)
            final_position_abs = current_block.position() + (new_sel_end_rel if original_anchor_rel == current_sel_start_rel else new_sel_start_rel)

            new_cursor.setPosition(final_anchor_abs)
            new_cursor.setPosition(final_position_abs, QTextCursor.KeepAnchor)
            
            editor.setTextCursor(new_cursor)
        
        self.mw.is_adjusting_selection = False
        self.mw.ui_updater.update_status_bar_selection()