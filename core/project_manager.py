# --- START OF FILE core/project_manager.py ---
# core/project_manager.py
"""
Project management system for the translation workbench.

This module provides data models and management for the project-oriented paradigm:
- Project: Top-level container holding all project data
- Block: Physical file pair (source/translation)
- Category: Virtual grouping of strings within a block
"""

import os
import json
from typing import List, Dict, Optional, Set, Any
from pathlib import Path
from utils.logging_utils import log_info, log_warning, log_error, log_debug

from .project_models import Category, Block, Project


class ProjectManager:
    """
    Manager class for loading, saving, and manipulating projects.

    The project structure on disk:
    project_folder/
        project.uiproj          # Project metadata file
        sources/                # Source files (read-only originals)
            file1.txt
            file2.txt
        translation/            # Translation files (working copies)
            file1.txt
            file2.txt
    """

    PROJECT_FILE_NAME = "project.uiproj"
    SOURCES_DIR = "sources"
    TRANSLATION_DIR = "translation"

    # Project-specific settings that are saved to project.metadata
    PROJECT_SETTINGS = [
        'font_size',
        'show_multiple_spaces_as_dots',
        'space_dot_color_hex',
        'preview_wrap_lines',
        'editors_wrap_lines',
        'game_dialog_max_width_pixels',
        'line_width_warning_threshold_pixels',
        'default_font_file',
        'newline_display_symbol',
        'newline_css',
        'tag_css',
        'tag_color_rgba',
        'tag_bold',
        'tag_italic',
        'tag_underline',
        'newline_color_rgba',
        'newline_bold',
        'newline_italic',
        'newline_underline',
        'spellchecker_language',
        'default_tag_mappings',
        'autofix_enabled',
        'detection_enabled',
    ]

    def __init__(self, project_path: Optional[str] = None):
        """
        Initialize ProjectManager.

        Args:
            project_path: Path to the project directory or .uiproj file
        """
        self.project: Optional[Project] = None
        self.project_dir: Optional[str] = None
        self.project_file_path: Optional[str] = None

        if project_path:
            self.load(project_path)

    def create_new_project(self, project_dir: str, name: str, plugin_name: str, description: str = "") -> bool:
        """
        Create a new project structure on disk.

        Args:
            project_dir: Directory where project will be created
            name: Project name
            plugin_name: Active game plugin
            description: Optional project description

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory structure
            project_path = Path(project_dir)
            project_path.mkdir(parents=True, exist_ok=True)

            sources_path = project_path / self.SOURCES_DIR
            translation_path = project_path / self.TRANSLATION_DIR
            sources_path.mkdir(exist_ok=True)
            translation_path.mkdir(exist_ok=True)

            # Create project metadata
            from datetime import datetime
            now = datetime.now().isoformat()

            self.project = Project(
                name=name,
                description=description,
                plugin_name=plugin_name,
                created_at=now,
                modified_at=now
            )

            self.project_dir = str(project_path)
            self.project_file_path = str(project_path / self.PROJECT_FILE_NAME)

            # Save project file
            self.save()

            log_info(f"Created new project '{name}' at {project_dir}")
            return True

        except Exception as e:
            log_error(f"Failed to create project: {e}")
            return False

    def load(self, path: str) -> bool:
        """
        Load a project from disk.

        Args:
            path: Path to project directory or .uiproj file

        Returns:
            True if successful, False otherwise
        """
        try:
            path_obj = Path(path)

            # Determine if path is directory or file
            if path_obj.is_dir():
                self.project_dir = str(path_obj)
                self.project_file_path = str(path_obj / self.PROJECT_FILE_NAME)
            elif path_obj.is_file() and path_obj.name.endswith('.uiproj'):
                self.project_dir = str(path_obj.parent)
                self.project_file_path = str(path_obj)
            else:
                log_error(f"Invalid project path: {path}")
                return False

            # Load project file
            if not os.path.exists(self.project_file_path):
                log_error(f"Project file not found: {self.project_file_path}")
                return False

            with open(self.project_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.project = Project.from_dict(data)
            log_info(f"Loaded project '{self.project.name}' from {self.project_dir}")
            return True

        except Exception as e:
            log_error(f"Failed to load project: {e}")
            return False

    def save(self) -> bool:
        """
        Save the current project to disk.

        Returns:
            True if successful, False otherwise
        """
        if not self.project or not self.project_file_path:
            log_warning("No project to save")
            return False

        try:
            # Update modification time
            from datetime import datetime
            self.project.modified_at = datetime.now().isoformat()

            # Save project file
            with open(self.project_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.project.to_dict(), f, indent=4, ensure_ascii=False)

            log_debug(f"Saved project '{self.project.name}' to {self.project_file_path}")
            return True

        except Exception as e:
            log_error(f"Failed to save project: {e}")
            return False

    def add_block(self, name: str, source_file_path: str, translation_file_path: Optional[str] = None, description: str = "") -> Optional[Block]:
        """
        Import a new block (file pair) into the project.

        Args:
            name: Display name for the block
            source_file_path: Path to the source file to import
            translation_file_path: Optional path to existing translation file. If None, source is copied.
            description: Optional block description

        Returns:
            The created Block object, or None on failure
        """
        if not self.project or not self.project_dir:
            log_error("No project loaded")
            return None

        try:
            source_path = Path(source_file_path)
            if not source_path.exists():
                log_error(f"Source file not found: {source_file_path}")
                return None

            # Copy source file to project sources directory
            dest_source_path = Path(self.project_dir) / self.SOURCES_DIR / source_path.name
            import shutil
            shutil.copy2(source_file_path, dest_source_path)

            # Handle translation file
            dest_translation_path = Path(self.project_dir) / self.TRANSLATION_DIR / source_path.name
            if translation_file_path and Path(translation_file_path).exists():
                # Copy existing translation file
                shutil.copy2(translation_file_path, dest_translation_path)
                log_debug(f"Copied translation file from {translation_file_path}")
            else:
                # Copy source as translation (user will edit it)
                shutil.copy2(source_file_path, dest_translation_path)
                log_debug(f"Copied source file as translation template")

            # Create block
            block = Block(
                name=name or source_path.stem,
                source_file=f"{self.SOURCES_DIR}/{source_path.name}",
                translation_file=f"{self.TRANSLATION_DIR}/{source_path.name}",
                description=description
            )

            self.project.add_block(block)
            self.save()

            log_info(f"Added block '{block.name}' to project")
            return block

        except Exception as e:
            log_error(f"Failed to add block: {e}")
            return None

    def get_uncategorized_lines(self, block_id: str, total_lines: int) -> List[int]:
        """
        Get list of line indices that are not assigned to any category.

        Args:
            block_id: ID of the block
            total_lines: Total number of lines in the block

        Returns:
            List of uncategorized line indices
        """
        block = self.project.find_block(block_id) if self.project else None
        if not block:
            return list(range(total_lines))

        categorized = block.get_categorized_line_indices()
        return [i for i in range(total_lines) if i not in categorized]

    def get_absolute_path(self, relative_path: str) -> str:
        """
        Convert a project-relative path to an absolute path.

        Args:
            relative_path: Relative path within project

        Returns:
            Absolute file path
        """
        if not self.project_dir:
            return relative_path
        return str(Path(self.project_dir) / relative_path)

    def get_relative_path(self, absolute_path: str) -> str:
        """
        Convert an absolute path to a project-relative path.

        Args:
            absolute_path: Absolute file path

        Returns:
            Relative path within project
        """
        if not self.project_dir:
            return absolute_path
        try:
            return str(Path(absolute_path).relative_to(self.project_dir))
        except ValueError:
            # Path is not relative to project dir
            return absolute_path

    def save_settings_to_project(self, main_window) -> bool:
        """
        Save project-specific settings from MainWindow to project.metadata.

        Args:
            main_window: MainWindow instance with settings to save

        Returns:
            True if successful, False otherwise
        """
        if not self.project:
            log_warning("No project to save settings to")
            return False

        try:
            # Save each project-specific setting to metadata
            settings_saved = {}
            for setting_name in self.PROJECT_SETTINGS:
                if hasattr(main_window, setting_name):
                    value = getattr(main_window, setting_name)
                    settings_saved[setting_name] = value

            self.project.metadata['settings'] = settings_saved
            log_info(f"Saved {len(settings_saved)} project settings to metadata")

            # Save project to disk
            return self.save()

        except Exception as e:
            log_error(f"Failed to save settings to project: {e}")
            return False

    def load_settings_from_project(self, main_window) -> bool:
        """
        Load project-specific settings from project.metadata to MainWindow.

        Args:
            main_window: MainWindow instance to apply settings to

        Returns:
            True if successful, False otherwise
        """
        if not self.project:
            log_warning("No project to load settings from")
            return False

        try:
            settings = self.project.metadata.get('settings', {})
            if not settings:
                log_info("No project settings found in metadata, using current settings")
                return False

            # Apply each project-specific setting to MainWindow
            settings_loaded = 0
            for setting_name, value in settings.items():
                if hasattr(main_window, setting_name):
                    setattr(main_window, setting_name, value)
                    settings_loaded += 1

            log_info(f"Loaded {settings_loaded} project settings from metadata")
            return True

        except Exception as e:
            log_error(f"Failed to load settings from project: {e}")
            return False

    @property
    def current_project(self) -> Optional[Project]:
        """Get the currently loaded project."""
        return self.project
