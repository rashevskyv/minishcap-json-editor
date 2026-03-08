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

    def create_new_project(self, project_dir: str, name: str, plugin_name: str, description: str = "",
                           source_path: str = "", translation_path: Optional[str] = None,
                           is_directory_mode: bool = True, auto_create_translations: bool = False) -> bool:
        """
        Create a new project structure on disk.

        Args:
            project_dir: Directory where project file will be created
            name: Project name
            plugin_name: Active game plugin
            description: Optional project description
            source_path: External source file or directory
            translation_path: External translation file or directory (optional if auto_create is True)
            is_directory_mode: True if source_path/translation_path are directories
            auto_create_translations: True to auto-create missing translation files

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create project directory
            project_path = Path(project_dir)
            project_path.mkdir(parents=True, exist_ok=True)

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
            
            # Store external path settings
            self.project.metadata['source_path'] = source_path
            self.project.metadata['translation_path'] = translation_path
            self.project.metadata['is_directory_mode'] = is_directory_mode
            self.project.metadata['auto_create_translations'] = auto_create_translations

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

    def add_block(self, name: str, source_file_path: str, translation_file_path: Optional[str] = None, description: str = "", target_relative_path: str = "") -> Optional[Block]:
        """
        Register a new block (file pair) in the project. Does NOT copy files.

        Args:
            name: Display name for the block
            source_file_path: Relative path to the source file
            translation_file_path: Optional relative path to existing translation file
            description: Optional block description
            target_relative_path: Optional relative directory path (deprecated/ignored)

        Returns:
            The created Block object, or None on failure
        """
        if not self.project or not self.project_dir:
            log_error("No project loaded")
            return None

        try:
            source_path = Path(source_file_path)

            source_rel_path = source_file_path.replace('\\', '/')
            trans_rel_path = translation_file_path.replace('\\', '/') if translation_file_path else source_rel_path

            # Create block
            block = Block(
                name=name or source_path.stem,
                source_file=source_rel_path,
                translation_file=trans_rel_path,
                description=description
            )

            self.project.add_block(block)
            self.save()

            log_info(f"Registered block '{block.name}' loosely linked at {source_rel_path}")
            return block

        except Exception as e:
            log_error(f"Failed to register block: {e}")
            return None

    def sync_project_files(self):
        """
        Synchronize files from external directories with project blocks.
        """
        if not self.project:
            return

        source_path = self.project.metadata.get('source_path', '')
        translation_path = self.project.metadata.get('translation_path')
        is_directory_mode = self.project.metadata.get('is_directory_mode', True)
        auto_create = self.project.metadata.get('auto_create_translations', False)
        
        if not source_path or not os.path.exists(source_path):
            log_warning("Source path is invalid or missing during sync.")
            return

        supported_extensions = {'.json', '.txt'}
        existing_blocks = {b.source_file: b for b in self.project.blocks}
        found_sources = set()

        if is_directory_mode:
            root_path = Path(source_path)
            for filepath in root_path.rglob('*'):
                if filepath.is_file() and filepath.suffix.lower() in supported_extensions:
                    rel_path = filepath.relative_to(root_path).as_posix()
                    found_sources.add(rel_path)
                    
                    if rel_path not in existing_blocks:
                        # Auto-create translation logic could go here or when saving
                        self.add_block(
                            name=filepath.stem,
                            source_file_path=rel_path,
                            translation_file_path=rel_path
                        )
        else:
            # File mode
            filepath = Path(source_path)
            if filepath.is_file() and filepath.suffix.lower() in supported_extensions:
                rel_path = filepath.name
                found_sources.add(rel_path)
                if rel_path not in existing_blocks:
                    # In file mode, if translation isn't auto-created, translation_path is likely a file
                    trans_rel_path = Path(translation_path).name if translation_path else rel_path
                    self.add_block(
                        name=filepath.stem,
                        source_file_path=rel_path,
                        translation_file_path=trans_rel_path
                    )
                    
        # Remove blocks that no longer exist
        blocks_to_remove = [b.id for b in self.project.blocks if b.source_file not in found_sources]
        for bid in blocks_to_remove:
            self.project.remove_block(bid)
            
        if blocks_to_remove or len(found_sources) > len(existing_blocks):
            self.save()

    def import_directory(self, root_dir_path: str) -> List[Block]:
        """
        Legacy functionality for loose imports. Not used in normal external directory modes.
        """
        # Kept for compatibility, redirects to normal behavior essentially
        return []

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

    def get_absolute_path(self, relative_path: str, is_translation: bool = False) -> str:
        """
        Convert a block-relative path to an absolute path.

        Args:
            relative_path: Relative path within external source/translation directory
            is_translation: Determine whether to use source_path or translation_path

        Returns:
            Absolute file path
        """
        if not self.project:
            return relative_path
            
        is_directory_mode = self.project.metadata.get('is_directory_mode', True)
        base_path = self.project.metadata.get('translation_path') if is_translation else self.project.metadata.get('source_path')
        
        if not base_path:
            # Fallback auto create translation path or default directory
            if is_translation and self.project.metadata.get('auto_create_translations', False):
                base_path = Path(self.project.metadata.get('source_path', '')).parent / 'translation'
            else:
                return relative_path

        if is_directory_mode:
            return str(Path(base_path) / relative_path)
        else:
            return str(base_path)

    def get_relative_path(self, absolute_path: str, is_translation: bool = False) -> str:
        """
        Convert an absolute path to a relative path against external directories.

        Args:
            absolute_path: Absolute file path
            is_translation: True if checking against translation_path

        Returns:
            Relative path within project
        """
        if not self.project:
            return absolute_path
            
        base_path = self.project.metadata.get('translation_path') if is_translation else self.project.metadata.get('source_path')
        if not base_path:
            return absolute_path
            
        try:
            return str(Path(absolute_path).relative_to(base_path))
        except ValueError:
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
