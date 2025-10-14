# --- START OF FILE ui/updaters/title_status_bar_updater.py ---
import os
from utils.utils import log_debug
from .base_ui_updater import BaseUIUpdater

class TitleStatusBarUpdater(BaseUIUpdater):
    def __init__(self, main_window, data_processor):
        super().__init__(main_window, data_processor)

    def update_title(self):
        title = "JSON Text Editor"

        # Check if a project is open
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and hasattr(self.mw.project_manager, 'current_project') and self.mw.project_manager.current_project:
            project_name = self.mw.project_manager.current_project.name
            title += f" - [{project_name}]"
        elif self.mw.json_path:
            title += f" - [{os.path.basename(self.mw.json_path)}]"
        else:
            title += " - [No File Open]"

        if self.mw.unsaved_changes:
            title += " *"
        self.mw.setWindowTitle(title)

    def update_statusbar_paths(self):
        if hasattr(self.mw, 'original_path_label') and self.mw.original_path_label:
            orig_filename = os.path.basename(self.mw.json_path) if self.mw.json_path else "[not specified]"
            self.mw.original_path_label.setText(f"Original: {orig_filename}")
            self.mw.original_path_label.setToolTip(self.mw.json_path if self.mw.json_path else "Path to original file")
        if hasattr(self.mw, 'edited_path_label') and self.mw.edited_path_label:
            edited_filename = os.path.basename(self.mw.edited_json_path) if self.mw.edited_json_path else "[not specified]"
            self.mw.edited_path_label.setText(f"Changes: {edited_filename}")
            self.mw.edited_path_label.setToolTip(self.mw.edited_json_path if self.mw.edited_json_path else "Path to changes file")