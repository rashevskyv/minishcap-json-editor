# --- START OF FILE handlers/project_action_handler.py ---
# handlers/project_action_handler.py
import os
import json
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from PyQt5.QtCore import Qt
from core.project_manager import ProjectManager
from core.data_manager import load_json_file, load_text_file
from .base_handler import BaseHandler
from utils.logging_utils import log_info, log_warning, log_error, log_debug
# from core.data_manager import load_json_file, load_text_file

class ProjectActionHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)

    def create_new_project_action(self):
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
            description=info['description'],
            source_path=info['source_path'],
            translation_path=info['translation_path'],
            is_directory_mode=info['is_directory_mode'],
            auto_create_translations=info['auto_create_translations']
        )

        if success:
            self.mw.project_manager.sync_project_files()
            project = self.mw.project_manager.project
            log_info(f"Project '{project.name}' created successfully at {info['directory']}.")

            # Update recent projects
            project_file = os.path.join(info['directory'], "project.uiproj")
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.add_recent_project(project_file)
                self.mw.settings_manager.save_settings()
                self._update_recent_projects_menu()

            # Switch plugin if needed
            if info['plugin'] != self.mw.active_game_plugin:
                log_info(f"Switching plugin to '{info['plugin']}'")
                self.mw.active_game_plugin = info['plugin']
                self.mw.load_game_plugin()
                self.ui_updater.update_plugin_status_label()

            # Enable project-specific actions
            if hasattr(self.mw, 'close_project_action'):
                self.mw.close_project_action.setEnabled(True)
            if hasattr(self.mw, 'import_block_action'):
                self.mw.import_block_action.setEnabled(True)
            if hasattr(self.mw, 'import_directory_action'):
                self.mw.import_directory_action.setEnabled(True)
            if hasattr(self.mw, 'add_block_button'):
                self.mw.add_block_button.setEnabled(True)

            # Update UI
            self.ui_updater.update_title()
            self._populate_blocks_from_project()

            QMessageBox.information(
                self.mw,
                "Project Created",
                f"Project '{project.name}' has been created successfully."
            )
        else:
            QMessageBox.critical(self.mw, "Project Creation Failed", "Failed to create project.")

    def open_project_action(self):
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

            # Update recent projects
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.add_recent_project(project_path)
                self.mw.settings_manager.save_settings()
                self._update_recent_projects_menu()

            # Switch plugin if needed
            if project.plugin_name and project.plugin_name != self.mw.active_game_plugin:
                log_info(f"Switching plugin to '{project.plugin_name}'")
                self.mw.active_game_plugin = project.plugin_name
                self.mw.load_game_plugin()
                self.ui_updater.update_plugin_status_label()

            # Load project-specific settings from metadata
            if self.mw.project_manager:
                self.mw.project_manager.load_settings_from_project(self.mw)
                self.mw.project_manager.sync_project_files()

            # Enable project-specific actions
            if hasattr(self.mw, 'close_project_action'):
                self.mw.close_project_action.setEnabled(True)
            if hasattr(self.mw, 'import_block_action'):
                self.mw.import_block_action.setEnabled(True)
            if hasattr(self.mw, 'import_directory_action'):
                self.mw.import_directory_action.setEnabled(True)
            if hasattr(self.mw, 'add_block_button'):
                self.mw.add_block_button.setEnabled(True)

            # Update UI
            self.ui_updater.update_title()
            self._populate_blocks_from_project()

            log_info(f"Project '{project.name}' opened with {len(project.blocks)} blocks.")
        else:
            QMessageBox.critical(
                self.mw,
                "Project Load Failed",
                f"Failed to load project from:\n{project_path}"
            )

    def close_project_action(self):
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
                if hasattr(self.mw, 'app_action_handler'):
                    if not self.mw.app_action_handler.save_data_action(ask_confirmation=False):
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
        if hasattr(self.mw, 'import_directory_action'):
            self.mw.import_directory_action.setEnabled(False)
        if hasattr(self.mw, 'add_block_button'):
            self.mw.add_block_button.setEnabled(False)

        # Update UI
        self.mw.block_list_widget.clear()
        self.ui_updater.populate_strings_for_block(-1)
        self.ui_updater.update_text_views()
        self.ui_updater.update_title()
        self.ui_updater.update_statusbar_paths()

        log_info("Project closed.")

    def import_block_action(self):
        from components.project_dialogs import ImportBlockDialog
        log_info("Import Block action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            QMessageBox.warning(self.mw, "No Project", "Please open or create a project first.")
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
            QMessageBox.information(self.mw, "Block Imported", f"Block '{info['name']}' has been imported.")
        else:
            QMessageBox.critical(self.mw, "Import Failed", "Failed to import block.")

    def import_directory_action(self):
        log_info("Import Directory action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            QMessageBox.warning(self.mw, "No Project", "Please open or create a project first.")
            return

        start_dir = os.path.expanduser("~")
        directory_path = QFileDialog.getExistingDirectory(
            self.mw,
            "Select Directory to Import",
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if not directory_path:
            log_info("Import directory cancelled.")
            return

        # Import directory using ProjectManager
        blocks = self.mw.project_manager.import_directory(directory_path)

        if blocks:
            log_info(f"{len(blocks)} blocks imported successfully from '{directory_path}'.")
            self._populate_blocks_from_project()
            QMessageBox.information(self.mw, "Directory Imported", f"{len(blocks)} blocks have been imported.")
        else:
            QMessageBox.information(self.mw, "Import Result", "No supported files found or failed to import.")

    def delete_block_action(self):
        log_info("Delete Block action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        current_item = self.mw.block_list_widget.currentItem()
        if not current_item:
            return

        block_idx = current_item.data(0, Qt.UserRole)
        block = self.mw.project_manager.project.blocks[block_idx]
        block_name = block.name

        reply = QMessageBox.question(
            self.mw,
            'Delete Block',
            f"Are you sure you want to remove block '{block_name}' from the project?\n\n"
            "This will NOT delete the physical files, only the reference in the project.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Remove block from project
        success = self.mw.project_manager.project.remove_block(block.id)
        if success:
            self.mw.project_manager.save()
            log_info(f"Block '{block_name}' removed from project.")
            self._populate_blocks_from_project()
            QMessageBox.information(self.mw, "Block Deleted", f"Block '{block_name}' has been removed.")
        else:
            QMessageBox.critical(self.mw, "Delete Error", "Failed to remove block.")

    def move_block_up_action(self):
        log_info("Move Block Up action triggered.")
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        current_item = self.mw.block_list_widget.currentItem()
        if not current_item:
            return

        block_idx = current_item.data(Qt.UserRole)
        if block_idx <= 0:
            return

        # Swap blocks
        blocks = self.mw.project_manager.project.blocks
        blocks[block_idx], blocks[block_idx - 1] = blocks[block_idx - 1], blocks[block_idx]
        self.mw.project_manager.save()
        self._populate_blocks_from_project()
        if block_idx > 0:
            self.mw.block_list_widget.select_block_by_index(block_idx - 1)
        elif len(self.mw.project_manager.project.blocks) > 0:
            self.mw.block_list_widget.select_block_by_index(0)

    def move_block_down_action(self):
        log_info("Move Block Down action triggered.")
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        current_item = self.mw.block_list_widget.currentItem()
        if not current_item:
            return

        block_idx = current_item.data(Qt.UserRole)
        if block_idx >= len(self.mw.project_manager.project.blocks) - 1:
            return

        # Swap blocks
        blocks = self.mw.project_manager.project.blocks
        blocks[block_idx], blocks[block_idx + 1] = blocks[block_idx + 1], blocks[block_idx]
        self.mw.project_manager.save()
        self._populate_blocks_from_project()
        if block_idx + 1 < len(self.mw.project_manager.project.blocks):
            self.mw.block_list_widget.select_block_by_index(block_idx + 1)
        else:
            self.mw.block_list_widget.select_block_by_index(block_idx)

    def _populate_blocks_from_project(self):
        """Populate block list from current project and load data."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        # Clear current data
        self.mw.block_list_widget.clear()
        self.mw.data = []
        self.mw.edited_data = {}
        self.mw.block_names = {}
        self.mw.block_to_project_file_map = {} # Mapping data_block_idx -> project_block_idx
        
        # Reset plugin state if it tracks keys (like pokemon_fr)
        if hasattr(self.mw.current_game_rules, 'original_keys'):
            self.mw.current_game_rules.original_keys = []

        # Load each block's data
        self.mw.block_to_project_file_map = {}
        source_parsed_counts = []
        
        for project_block_idx, block in enumerate(self.mw.project_manager.project.blocks):
            source_path = self.mw.project_manager.get_absolute_path(block.source_file)
            
            block_data = []
            if os.path.exists(source_path):
                file_extension = os.path.splitext(source_path)[1].lower()
                if file_extension == '.json':
                    file_content, error = load_json_file(source_path)
                else:
                    # Try loading as text for any other extension
                    file_content, error = load_text_file(source_path)

                if not error and self.mw.current_game_rules:
                    parsed_data, names = self.mw.current_game_rules.load_data_from_json_obj(file_content)
                    count = len(parsed_data) if parsed_data else 1
                    source_parsed_counts.append(count)
                    
                    for sub_block_idx, block_content in enumerate(parsed_data):
                        data_block_idx = len(self.mw.data)
                        self.mw.data.append(block_content)
                        self.mw.block_to_project_file_map[data_block_idx] = project_block_idx
                        
                        # Handle block names
                        if count > 1:
                            p_name = names.get(str(sub_block_idx), f"{block.name} (Part {sub_block_idx+1})")
                            self.mw.block_names[str(data_block_idx)] = p_name
                        else:
                            self.mw.block_names[str(data_block_idx)] = block.name
                else:
                    source_parsed_counts.append(1)
                    data_block_idx = len(self.mw.data)
                    self.mw.data.append([])
                    self.mw.block_to_project_file_map[data_block_idx] = project_block_idx
                    self.mw.block_names[str(data_block_idx)] = block.name
            else:
                source_parsed_counts.append(1)
                data_block_idx = len(self.mw.data)
                self.mw.data.append([])
                self.mw.block_to_project_file_map[data_block_idx] = project_block_idx
                self.mw.block_names[str(data_block_idx)] = block.name

        # Backup authoritative original keys from source files
        plugin_keys_backup = None
        if hasattr(self.mw.current_game_rules, 'original_keys'):
            plugin_keys_backup = list(self.mw.current_game_rules.original_keys)

        # Load edited_file_data
        self.mw.edited_file_data = []
        for project_block_idx, block in enumerate(self.mw.project_manager.project.blocks):
            translation_path = self.mw.project_manager.get_absolute_path(block.translation_file, is_translation=True)
            
            # How many blocks did the source file produce?
            expected_count = source_parsed_counts[project_block_idx]

            if os.path.exists(translation_path):
                file_extension = os.path.splitext(translation_path)[1].lower()
                if file_extension == '.json':
                    file_content, error = load_json_file(translation_path)
                else:
                    file_content, error = load_text_file(translation_path)

                if not error and self.mw.current_game_rules:
                    parsed_edited_data, _ = self.mw.current_game_rules.load_data_from_json_obj(file_content)
                    
                    # Force match the number of blocks to the source structure
                    for i in range(expected_count):
                        if i < len(parsed_edited_data):
                            self.mw.edited_file_data.append(parsed_edited_data[i])
                        else:
                            self.mw.edited_file_data.append([]) # Pad if translation has fewer blocks
                else:
                    for _ in range(expected_count):
                        self.mw.edited_file_data.append([])
            else:
                for _ in range(expected_count):
                    self.mw.edited_file_data.append([])

        # Restore authoritative original keys
        if plugin_keys_backup is not None and hasattr(self.mw.current_game_rules, 'original_keys'):
            self.mw.current_game_rules.original_keys = plugin_keys_backup

        # Update paths for old-style save/load compatibility
        if self.mw.data:
            first_block = self.mw.project_manager.project.blocks[0]
            self.mw.json_path = self.mw.project_manager.get_absolute_path(first_block.source_file)
            self.mw.edited_json_path = self.mw.project_manager.get_absolute_path(first_block.translation_file, is_translation=True)

        # Perform initial scan
        if hasattr(self.mw, 'app_action_handler'):
            self.mw.app_action_handler._perform_initial_silent_scan_all_issues()

        # Update UI
        self.ui_updater.populate_blocks()
        self.ui_updater.update_statusbar_paths()

    def _update_recent_projects_menu(self):
        """Update the Recent Projects submenu with current list."""
        if not hasattr(self.mw, 'recent_projects_menu'):
            return

        # Clear existing menu items
        self.mw.recent_projects_menu.clear()

        # Get recent projects list
        recent_projects = getattr(self.mw, 'recent_projects', [])

        if not recent_projects:
            # Add "No recent projects" action
            no_recent_action = self.mw.recent_projects_menu.addAction("No recent projects")
            no_recent_action.setEnabled(False)
            return

        # Add action for each recent project
        for project_path in recent_projects:
            # Check if file exists
            if os.path.exists(project_path):
                # Get project name from path
                project_name = os.path.splitext(os.path.basename(project_path))[0]
                if project_name == "project":
                    # Use directory name if file is named "project.uiproj"
                    project_name = os.path.basename(os.path.dirname(project_path))

                action = self.mw.recent_projects_menu.addAction(project_name)
                action.setToolTip(project_path)
                # Use lambda with default argument to capture current project_path
                action.triggered.connect(lambda checked=False, path=project_path: self._open_recent_project(path))
            else:
                # Project file doesn't exist, show as unavailable
                action = self.mw.recent_projects_menu.addAction(f"{os.path.basename(project_path)} (missing)")
                action.setEnabled(False)

        # Add separator and "Clear Recent Projects" action
        self.mw.recent_projects_menu.addSeparator()
        clear_action = self.mw.recent_projects_menu.addAction("Clear Recent Projects")
        clear_action.triggered.connect(self._clear_recent_projects)

    def _open_recent_project(self, project_path: str):
        """Open a project from the recent projects list."""
        log_info(f"Opening recent project: {project_path}")

        if not os.path.exists(project_path):
            QMessageBox.critical(
                self.mw,
                "Project Not Found",
                f"Project file not found:\n{project_path}\n\n"
                f"It may have been moved or deleted."
            )
            # Remove from recent projects
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.remove_recent_project(project_path)
                self.mw.settings_manager.save_settings()
                self._update_recent_projects_menu()
            return

        # Load project using ProjectManager
        from core.project_manager import ProjectManager
        self.mw.project_manager = ProjectManager()

        success = self.mw.project_manager.load(project_path)

        if success:
            project = self.mw.project_manager.project
            log_info(f"Recent project '{project.name}' loaded successfully.")

            # Move to top of recent projects
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.add_recent_project(project_path)
                self.mw.settings_manager.save_settings()
                self._update_recent_projects_menu()

            # Switch plugin if needed
            if project.plugin_name and project.plugin_name != self.mw.active_game_plugin:
                log_info(f"Switching plugin to '{project.plugin_name}'")
                self.mw.active_game_plugin = project.plugin_name
                self.mw.load_game_plugin()
                self.ui_updater.update_plugin_status_label()

            # Load project-specific settings from metadata
            if self.mw.project_manager:
                self.mw.project_manager.load_settings_from_project(self.mw)

            # Enable project-specific actions
            if hasattr(self.mw, 'close_project_action'):
                self.mw.close_project_action.setEnabled(True)
            if hasattr(self.mw, 'import_block_action'):
                self.mw.import_block_action.setEnabled(True)
            if hasattr(self.mw, 'import_directory_action'):
                self.mw.import_directory_action.setEnabled(True)
            if hasattr(self.mw, 'add_block_button'):
                self.mw.add_block_button.setEnabled(True)

            # Update UI
            self.ui_updater.update_title()
            self._populate_blocks_from_project()

            log_info(f"Recent project '{project.name}' opened with {len(project.blocks)} blocks.")
        else:
            QMessageBox.critical(
                self.mw,
                "Project Load Failed",
                f"Failed to load project from:\n{project_path}"
            )

    def _clear_recent_projects(self):
        """Clear all recent projects."""
        reply = QMessageBox.question(
            self.mw,
            'Clear Recent Projects',
            "Are you sure you want to clear all recent projects?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.clear_recent_projects()
                self.mw.settings_manager.save_settings()
                self._update_recent_projects_menu()
            log_info("Recent projects cleared.")
