"""
Plain Text plugin for text translation workbench.

This plugin provides basic text editing functionality with minimal rules:
- Tags enclosed in square brackets []
- Newline handling: \\n, \\r
- Simple text with no special game-specific constraints
"""

import re
from typing import List, Tuple, Dict, Optional, Any, Set
from plugins.base_game_rules import BaseGameRules
from PyQt5.QtGui import QTextCharFormat, QColor, QFont


class SimpleProblemAnalyzer:
    """Simple problem analyzer for plain text - no problems detected."""

    def __init__(self):
        pass

    def analyze_data_string(self, text: str, font_map: dict, width_threshold: int) -> List[Set[str]]:
        """
        Analyze a data string and return problems per subline.
        For plain text, returns empty sets (no problems).

        Args:
            text: The full data string to analyze
            font_map: Font map for width calculation (not used)
            width_threshold: Width threshold in pixels (not used)

        Returns:
            List of sets, one per subline, each containing problem IDs (all empty)
        """
        # Split by \n to get sublines
        sublines = text.split('\\n')
        # Return empty problem sets for each subline
        return [set() for _ in sublines]

    def _get_sublines_from_data_string(self, text: str) -> List[str]:
        """Split a data string into sublines."""
        return text.split('\\n')


class GameRules(BaseGameRules):
    """Plain text game rules with basic tag support."""

    def __init__(self, main_window_ref=None):
        """Initialize plain text game rules with minimal problem analyzer."""
        super().__init__(main_window_ref)
        # Create simple problem analyzer that detects no problems
        self.problem_analyzer = SimpleProblemAnalyzer()

    def get_display_name(self) -> str:
        """Return the display name for this plugin."""
        return "Plain Text"

    def get_default_tag_mappings(self) -> Dict[str, str]:
        """
        Return default tag mappings for plain text.
        Plain text has minimal predefined tags.
        """
        return {}

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Optional[Dict[str, str]]]:
        """
        Load data from a JSON object or text file content.

        For plain text: ONE FILE = ONE BLOCK
        - Text files: each line becomes a string in the block
        - JSON arrays: all items become strings in one block

        Args:
            json_obj: Either a list of strings, or raw text content

        Returns:
            Tuple of (blocks, block_names) where:
            - blocks is a list of blocks, each block is a list of strings
            - block_names is an optional dict mapping block indices to names
        """
        blocks = []
        block_names = {}

        # If it's a string, treat it as plain text file content
        # ONE FILE = ONE BLOCK - split by single newlines to get individual strings
        if isinstance(json_obj, str):
            # Split by single newlines to get individual strings
            lines = [line for line in json_obj.split('\n') if line.strip()]
            if lines:
                blocks.append(lines)
                block_names["0"] = "Block 0"

        # If it's a list, treat each item as a string
        elif isinstance(json_obj, list):
            # Single block with all strings
            strings = [str(item) for item in json_obj if item]
            if strings:
                blocks.append(strings)
                block_names["0"] = "Block 0"

        # If it's a dict, try to extract blocks
        elif isinstance(json_obj, dict):
            # Check for common JSON structures
            if 'blocks' in json_obj:
                # Structure: {"blocks": [["str1", "str2"], ["str3"]]}
                for i, block_data in enumerate(json_obj['blocks']):
                    if isinstance(block_data, list):
                        strings = [str(s) for s in block_data if s]
                        if strings:
                            blocks.append(strings)
                            block_names[str(i)] = json_obj.get('block_names', {}).get(str(i), f"Block {i}")
            elif 'strings' in json_obj:
                # Structure: {"strings": ["str1", "str2", "str3"]}
                strings = [str(s) for s in json_obj['strings'] if s]
                if strings:
                    blocks.append(strings)
                    block_names["0"] = "Block 0"
            else:
                # Unknown structure, try to extract any lists
                for key, value in json_obj.items():
                    if isinstance(value, list):
                        strings = [str(s) for s in value if s]
                        if strings:
                            blocks.append(strings)
                            block_names[str(len(blocks)-1)] = key

        # Return at least one empty block if nothing was parsed
        if not blocks:
            blocks = [[]]
            block_names = {"0": "Block 0"}

        return blocks, block_names

    def save_data_to_json_obj(self, blocks: List[List[str]], block_names: Optional[Dict[str, str]] = None) -> Any:
        """
        Save data blocks to a JSON-serializable object.

        For plain text: ONE FILE = ONE BLOCK
        - Each string in the block becomes a line in the file
        - Strings are separated by single newlines

        Args:
            blocks: List of blocks, each block is a list of strings
            block_names: Optional dict of block names (ignored for plain text)

        Returns:
            String containing plain text representation
        """
        # For plain text, we expect only one block
        # Join all strings from all blocks with newlines
        all_strings = []
        for block in blocks:
            all_strings.extend(block)

        return '\n'.join(str(s) for s in all_strings)

    def get_tag_pattern(self) -> Optional[re.Pattern]:
        """
        Return regex pattern for matching tags in square brackets.

        Matches: [tag], [tag with spaces], [TAG123]
        """
        return re.compile(r'\[([^\]]+)\]')

    def get_text_representation_for_preview(self, data_string: str) -> str:
        """
        Convert data string format to preview display format.

        Converts escaped newlines (\\n, \\r) to the configured newline display symbol
        (e.g., ↵) for display in the preview window.

        Args:
            data_string: The data string with escaped newlines

        Returns:
            Text with newline symbols for preview display
        """
        newline_symbol = getattr(self.mw, "newline_display_symbol", "↵") if self.mw else "↵"

        # Convert escaped newlines to display symbol
        processed = str(data_string)
        processed = processed.replace('\\n', newline_symbol)
        processed = processed.replace('\\r', newline_symbol)  # Treat \r same as \n

        return processed

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        """
        Convert data string format to editor display format.

        Converts escaped newlines (\\n, \\r) to actual newline characters
        so they display as separate lines in the editor.

        Args:
            data_string_subline: The data string with escaped newlines

        Returns:
            Text with actual newline characters for editor display
        """
        # Convert escaped newlines to actual newlines
        processed = str(data_string_subline)
        processed = processed.replace('\\n', '\n')
        processed = processed.replace('\\r', '\n')  # Treat \r as \n
        return processed

    def convert_editor_text_to_data(self, text: str) -> str:
        """
        Convert editor text back to data string format.

        Converts actual newline characters back to escaped format (\\n)
        for storage in the data file.

        Args:
            text: The editor text with actual newlines

        Returns:
            Text with escaped newlines for data storage
        """
        # Convert actual newlines back to escaped format
        return text.replace('\n', '\\n')

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        """
        Return syntax highlighting rules for tags and newlines.

        Returns list of (pattern, format) tuples for:
        - Tags in square brackets: [VAR PKNICK(0000)], [tag], etc.
        - Literal newline sequences: \\n, \\r
        - Newline display symbol (if configured)
        """
        rules = []

        # Create format for tags in square brackets
        tag_format = QTextCharFormat()
        if self.mw:
            # Get tag color from settings (default to gray)
            tag_color = getattr(self.mw, 'tag_color_rgba', '#ffa7a7b6')
            try:
                tag_format.setForeground(QColor(tag_color))
            except Exception:
                tag_format.setForeground(QColor('#a7a7b6'))  # Fallback gray

            # Apply tag style settings
            if getattr(self.mw, 'tag_bold', False):
                tag_format.setFontWeight(QFont.Bold)
            if getattr(self.mw, 'tag_italic', True):
                tag_format.setFontItalic(True)
            if getattr(self.mw, 'tag_underline', False):
                tag_format.setFontUnderline(True)
        else:
            # Default styling if no main window reference
            tag_format.setForeground(QColor('#a7a7b6'))
            tag_format.setFontItalic(True)

        # Create format for literal newlines (\\n, \\r)
        literal_newline_format = QTextCharFormat()
        if self.mw:
            # Get newline color from settings
            newline_color = getattr(self.mw, 'newline_color_rgba', '#ffa020f0')
            try:
                literal_newline_format.setForeground(QColor(newline_color))
            except Exception:
                literal_newline_format.setForeground(QColor('#a020f0'))  # Fallback purple

            # Apply newline style settings
            if getattr(self.mw, 'newline_bold', True):
                literal_newline_format.setFontWeight(QFont.Bold)
            if getattr(self.mw, 'newline_italic', False):
                literal_newline_format.setFontItalic(True)
            if getattr(self.mw, 'newline_underline', False):
                literal_newline_format.setFontUnderline(True)
        else:
            # Default styling
            literal_newline_format.setForeground(QColor('#a020f0'))
            literal_newline_format.setFontWeight(QFont.Bold)

        # Create format for newline display symbol (e.g., ↵)
        newline_symbol_format = QTextCharFormat()
        if self.mw:
            newline_color = getattr(self.mw, 'newline_color_rgba', '#ffa020f0')
            try:
                newline_symbol_format.setForeground(QColor(newline_color))
            except Exception:
                newline_symbol_format.setForeground(QColor('#a020f0'))

            if getattr(self.mw, 'newline_bold', True):
                newline_symbol_format.setFontWeight(QFont.Bold)
            if getattr(self.mw, 'newline_italic', False):
                newline_symbol_format.setFontItalic(True)
            if getattr(self.mw, 'newline_underline', False):
                newline_symbol_format.setFontUnderline(True)
        else:
            newline_symbol_format.setForeground(QColor('#a020f0'))
            newline_symbol_format.setFontWeight(QFont.Bold)

        # Add highlighting rules
        # 1. Tags in square brackets
        rules.append((r"(\[\s*[^\]]*?\s*\])", tag_format))

        # 2. Literal newline sequences
        rules.append((r"(\\n)", literal_newline_format))
        rules.append((r"(\\r)", literal_newline_format))

        # 3. Newline display symbol (if configured)
        if self.mw and hasattr(self.mw, 'newline_display_symbol'):
            newline_symbol = getattr(self.mw, 'newline_display_symbol', None)
            if newline_symbol:
                rules.append((r"(" + re.escape(newline_symbol) + r")", newline_symbol_format))

        return rules

    def analyze_subline(
        self,
        text: str,
        next_text: Optional[str],
        subline_number_in_data_string: int,
        qtextblock_number_in_editor: int,
        is_last_subline_in_data_string: bool,
        editor_font_map: Optional[Dict] = None,
        editor_line_width_threshold: Optional[int] = None,
        full_data_string_text_for_logical_check: Optional[str] = None
    ) -> set:
        """
        Analyze a subline for issues.

        Plain text has minimal analysis - only basic tag validation.

        Args:
            text: The subline text to analyze
            next_text: Text of the next subline (if any)
            subline_number_in_data_string: Index of this subline in the data string
            qtextblock_number_in_editor: Line number in the editor
            is_last_subline_in_data_string: Whether this is the last subline
            editor_font_map: Font map for width calculation (not used in plain text)
            editor_line_width_threshold: Width threshold in pixels (not used in plain text)
            full_data_string_text_for_logical_check: Full string for context

        Returns:
            Set of problem IDs (empty for plain text)
        """
        problems = set()

        # Plain text has no specific problems to detect
        # Tags in [] are allowed and don't generate warnings

        return problems

    def autofix_data_string(
        self,
        text: str,
        font_map: Optional[Dict] = None,
        width_threshold: Optional[int] = None
    ) -> Tuple[str, bool]:
        """
        Apply automatic fixes to a data string.

        Plain text has minimal autofix - just basic cleanup.

        Args:
            text: The full data string text
            font_map: Font map for width calculation (not used)
            width_threshold: Width threshold in pixels (not used)

        Returns:
            Tuple of (fixed_text, was_modified)
            For plain text: (text, False) - no modifications
        """
        # No autofixes for plain text
        return text, False

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        """
        Return definitions for all problem types.

        Plain text has no predefined problems.

        Returns:
            Empty dict (no problems defined)
        """
        return {}
