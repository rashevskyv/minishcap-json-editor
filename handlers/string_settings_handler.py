# --- START OF FILE handlers/string_settings_handler.py ---
from .base_handler import BaseHandler
from utils.utils import log_debug

class StringSettingsHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        
    def _apply_and_rescan(self):
        log_debug("--- Applying string settings and performing full block refresh ---")
        
        current_block_idx = self.mw.current_block_idx

        if current_block_idx != -1:
            log_debug(f"Refreshing UI for block {current_block_idx}")
            self.mw.app_action_handler._perform_issues_scan_for_block(current_block_idx)
            self.mw.ui_updater.populate_blocks()
            self.mw.ui_updater.populate_strings_for_block(current_block_idx)
            
            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_string_settings_panel()
        else:
            log_debug("No block selected, only updating settings panel.")
            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_string_settings_panel()

    def on_font_changed(self, index):
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            return

        key = (self.mw.current_block_idx, self.mw.current_string_idx)
        current_meta = self.mw.string_metadata.get(key, {})
        current_font = current_meta.get("font_file")

        selected_data = self.mw.font_combobox.itemData(index)
        new_font = None
        if selected_data != "default":
            new_font = selected_data
            
        if current_font != new_font:
            self.mw.apply_width_button.setEnabled(True)
        else:
            # Якщо повернули до того ж значення, що і було, кнопка стає неактивною
            current_width = current_meta.get("width")
            spinbox_width = self.mw.width_spinbox.value()
            if (not current_width and spinbox_width == self.mw.line_width_warning_threshold_pixels) or \
               (current_width and spinbox_width == current_width):
                self.mw.apply_width_button.setEnabled(False)

    def on_width_changed(self, value):
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            return

        key = (self.mw.current_block_idx, self.mw.current_string_idx)
        current_meta = self.mw.string_metadata.get(key, {})
        current_width = current_meta.get("width")

        new_width = value
        
        is_width_changed = False
        if current_width is None: # Було дефолтне значення
            if new_width != self.mw.line_width_warning_threshold_pixels:
                is_width_changed = True
        else: # Було кастомне значення
            if new_width != current_width:
                is_width_changed = True

        if is_width_changed:
            self.mw.apply_width_button.setEnabled(True)
        else:
            # Якщо ширину повернули до початкового стану, перевіряємо стан шрифту
            current_font = current_meta.get("font_file")
            selected_font_data = self.mw.font_combobox.currentData()
            new_font = selected_font_data if selected_font_data != "default" else None
            if current_font == new_font:
                 self.mw.apply_width_button.setEnabled(False)


    def apply_settings_change(self):
        if self.mw.current_block_idx == -1 or self.mw.current_string_idx == -1:
            return

        key = (self.mw.current_block_idx, self.mw.current_string_idx)
        
        # Застосовуємо шрифт
        selected_font_data = self.mw.font_combobox.currentData()
        if key not in self.mw.string_metadata: self.mw.string_metadata[key] = {}
        
        if selected_font_data == "default":
            if "font_file" in self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]["font_file"]
        else:
            self.mw.string_metadata[key]["font_file"] = selected_font_data

        # Застосовуємо ширину
        new_width = self.mw.width_spinbox.value()
        if new_width == 0 or new_width == self.mw.line_width_warning_threshold_pixels:
             if "width" in self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]["width"]
        else:
            self.mw.string_metadata[key]["width"] = new_width
            
        # Очищуємо порожні метадані
        if not self.mw.string_metadata[key]:
            del self.mw.string_metadata[key]
            
        log_debug(f"Applied and updated string_metadata for {key}: {self.mw.string_metadata.get(key)}")
        
        current_string_idx_before_rescan = self.mw.current_string_idx
        self._apply_and_rescan()
        self.mw.list_selection_handler.string_selected_from_preview(current_string_idx_before_rescan)


    def apply_font_to_range(self, start_line, end_line, font_file):
        block_idx = self.mw.current_block_idx
        if block_idx == -1:
            return
            
        log_debug(f"Applying font '{font_file}' to lines {start_line}-{end_line} in block {block_idx}")
        for line_idx in range(start_line, end_line + 1):
            key = (block_idx, line_idx)
            if key not in self.mw.string_metadata:
                if font_file == "default": continue
                self.mw.string_metadata[key] = {}
            
            if font_file == "default":
                if "font_file" in self.mw.string_metadata[key]:
                    del self.mw.string_metadata[key]["font_file"]
            else:
                self.mw.string_metadata[key]["font_file"] = font_file
            
            if not self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]
        
        self._apply_and_rescan()

    def apply_font_to_lines(self, line_indices, font_file):
        block_idx = self.mw.current_block_idx
        if block_idx == -1:
            return
            
        log_debug(f"Applying font '{font_file}' to lines {line_indices} in block {block_idx}")
        for line_idx in line_indices:
            key = (block_idx, line_idx)
            if key not in self.mw.string_metadata:
                if font_file == "default": continue
                self.mw.string_metadata[key] = {}
            
            if font_file == "default":
                if "font_file" in self.mw.string_metadata[key]:
                    del self.mw.string_metadata[key]["font_file"]
            else:
                self.mw.string_metadata[key]["font_file"] = font_file
            
            if not self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]
        
        self._apply_and_rescan()

    def apply_width_to_lines(self, line_indices, width):
        block_idx = self.mw.current_block_idx
        if block_idx == -1:
            return

        log_debug(f"Applying width '{width}' to lines {line_indices} in block {block_idx}")
        is_default_width = (width == 0 or width == self.mw.line_width_warning_threshold_pixels)

        for line_idx in line_indices:
            key = (block_idx, line_idx)
            if key not in self.mw.string_metadata:
                if is_default_width: continue
                self.mw.string_metadata[key] = {}

            if is_default_width:
                if "width" in self.mw.string_metadata[key]:
                    del self.mw.string_metadata[key]["width"]
            else:
                self.mw.string_metadata[key]["width"] = width

            if not self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]
        
        self._apply_and_rescan()

    def apply_width_to_range(self, start_line, end_line, width):
        block_idx = self.mw.current_block_idx
        if block_idx == -1:
            return

        log_debug(f"Applying width '{width}' to lines {start_line}-{end_line} in block {block_idx}")
        is_default_width = (width == 0 or width == self.mw.line_width_warning_threshold_pixels)

        for line_idx in range(start_line, end_line + 1):
            key = (block_idx, line_idx)
            if key not in self.mw.string_metadata:
                if is_default_width: continue
                self.mw.string_metadata[key] = {}

            if is_default_width:
                if "width" in self.mw.string_metadata[key]:
                    del self.mw.string_metadata[key]["width"]
            else:
                self.mw.string_metadata[key]["width"] = width

            if not self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]
        
        self._apply_and_rescan()