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
import uuid
from typing import List, Dict, Optional, Set, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from utils.logging_utils import log_info, log_warning, log_error, log_debug


@dataclass
class Category:
    """
    Virtual category for organizing strings within a block.
    Categories exist only as metadata and don't modify source files.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    line_indices: List[int] = field(default_factory=list)  # Indices of strings in this category
    children: List['Category'] = field(default_factory=list)  # Hierarchical support
    parent_id: Optional[str] = None  # Reference to parent category
    color: Optional[str] = None  # Optional color for UI visualization

    def to_dict(self) -> Dict[str, Any]:
        """Convert category to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'line_indices': self.line_indices,
            'children': [child.to_dict() for child in self.children],
            'parent_id': self.parent_id,
            'color': self.color
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Category':
        """Create category from dictionary."""
        children = [Category.from_dict(child) for child in data.get('children', [])]
        return Category(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            description=data.get('description', ''),
            line_indices=data.get('line_indices', []),
            children=children,
            parent_id=data.get('parent_id'),
            color=data.get('color')
        )

    def add_child(self, child: 'Category'):
        """Add a child category."""
        child.parent_id = self.id
        self.children.append(child)

    def remove_child(self, child_id: str) -> bool:
        """Remove a child category by ID."""
        for i, child in enumerate(self.children):
            if child.id == child_id:
                self.children.pop(i)
                return True
        return False

    def find_category(self, category_id: str) -> Optional['Category']:
        """Recursively find a category by ID."""
        if self.id == category_id:
            return self
        for child in self.children:
            found = child.find_category(category_id)
            if found:
                return found
        return None


@dataclass
class Block:
    """
    Represents a physical file pair (source and translation).
    This is the main unit of content in a project.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""  # Display name (can be customized)
    source_file: str = ""  # Relative path within project
    translation_file: str = ""  # Relative path within project
    description: str = ""
    categories: List[Category] = field(default_factory=list)  # Root categories
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional block-specific data

    def to_dict(self) -> Dict[str, Any]:
        """Convert block to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'source_file': self.source_file,
            'translation_file': self.translation_file,
            'description': self.description,
            'categories': [cat.to_dict() for cat in self.categories],
            'metadata': self.metadata
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Block':
        """Create block from dictionary."""
        categories = [Category.from_dict(cat) for cat in data.get('categories', [])]
        return Block(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            source_file=data.get('source_file', ''),
            translation_file=data.get('translation_file', ''),
            description=data.get('description', ''),
            categories=categories,
            metadata=data.get('metadata', {})
        )

    def add_category(self, category: Category):
        """Add a root category to this block."""
        self.categories.append(category)

    def remove_category(self, category_id: str) -> bool:
        """Remove a category by ID."""
        for i, cat in enumerate(self.categories):
            if cat.id == category_id:
                self.categories.pop(i)
                return True
            # Check children recursively
            if cat.remove_child(category_id):
                return True
        return False

    def find_category(self, category_id: str) -> Optional[Category]:
        """Find a category by ID (searches recursively)."""
        for cat in self.categories:
            found = cat.find_category(category_id)
            if found:
                return found
        return None

    def get_all_categories_flat(self) -> List[Category]:
        """Get all categories in a flat list (recursively)."""
        result = []
        for cat in self.categories:
            result.append(cat)
            result.extend(self._get_children_recursive(cat))
        return result

    def _get_children_recursive(self, category: Category) -> List[Category]:
        """Helper method to recursively get all children."""
        result = []
        for child in category.children:
            result.append(child)
            result.extend(self._get_children_recursive(child))
        return result

    def get_categorized_line_indices(self) -> Set[int]:
        """Get all line indices that belong to any category."""
        indices = set()
        for cat in self.get_all_categories_flat():
            indices.update(cat.line_indices)
        return indices


@dataclass
class Project:
    """
    Top-level project container.
    Represents the entire workspace with all blocks and configuration.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    plugin_name: str = ""  # Active game plugin (e.g., "zelda_mc")
    blocks: List[Block] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Project-level metadata
    created_at: str = ""  # ISO timestamp
    modified_at: str = ""  # ISO timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'plugin_name': self.plugin_name,
            'blocks': [block.to_dict() for block in self.blocks],
            'metadata': self.metadata,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'version': '1.0'  # Schema version for future compatibility
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Project':
        """Create project from dictionary."""
        blocks = [Block.from_dict(block) for block in data.get('blocks', [])]
        return Project(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            description=data.get('description', ''),
            plugin_name=data.get('plugin_name', ''),
            blocks=blocks,
            metadata=data.get('metadata', {}),
            created_at=data.get('created_at', ''),
            modified_at=data.get('modified_at', '')
        )

    def add_block(self, block: Block):
        """Add a block to the project."""
        self.blocks.append(block)

    def remove_block(self, block_id: str) -> bool:
        """Remove a block by ID."""
        for i, block in enumerate(self.blocks):
            if block.id == block_id:
                self.blocks.pop(i)
                return True
        return False

    def find_block(self, block_id: str) -> Optional[Block]:
        """Find a block by ID."""
        for block in self.blocks:
            if block.id == block_id:
                return block
        return None

    def find_block_by_name(self, name: str) -> Optional[Block]:
        """Find a block by name."""
        for block in self.blocks:
            if block.name == name:
                return block
        return None


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
