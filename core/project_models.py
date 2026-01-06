# --- START OF FILE core/project_models.py ---
# core/project_models.py
"""
Data models for the project-oriented paradigm:
- Project: Top-level container holding all project data
- Block: Physical file pair (source/translation)
- Category: Virtual grouping of strings within a block
"""

import uuid
from typing import List, Dict, Optional, Set, Any
from dataclasses import dataclass, field

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
