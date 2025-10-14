"""
Plain Text plugin for text translation workbench.

This plugin provides basic text editing functionality with minimal rules:
- Tags enclosed in square brackets []
- Newline handling: \\n, \\r
- Simple text with no special game-specific constraints
"""

import re
from typing import List, Tuple, Dict, Optional, Any
from plugins.base_game_rules import BaseGameRules


class GameRules(BaseGameRules):
    """Plain text game rules with basic tag support."""

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

        For plain text, we support both:
        - Simple text files (one string per line, blank lines separate blocks)
        - JSON arrays of strings

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
        if isinstance(json_obj, str):
            # Split by double newlines to separate blocks
            raw_blocks = json_obj.split('\n\n')

            for i, raw_block in enumerate(raw_blocks):
                # Split block into individual strings (lines)
                lines = [line for line in raw_block.split('\n') if line.strip()]
                if lines:
                    blocks.append(lines)
                    block_names[str(i)] = f"Block {i}"

            # If no blocks found, treat entire content as one block
            if not blocks:
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

        For plain text, we save as simple text format:
        - Each block separated by double newline
        - Each string on its own line

        Args:
            blocks: List of blocks, each block is a list of strings
            block_names: Optional dict of block names (ignored for plain text)

        Returns:
            String containing plain text representation
        """
        output_blocks = []

        for block in blocks:
            # Join strings in block with newlines
            block_text = '\n'.join(str(s) for s in block)
            output_blocks.append(block_text)

        # Join blocks with double newlines
        return '\n\n'.join(output_blocks)

    def get_tag_pattern(self) -> Optional[re.Pattern]:
        """
        Return regex pattern for matching tags in square brackets.

        Matches: [tag], [tag with spaces], [TAG123]
        """
        return re.compile(r'\[([^\]]+)\]')

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
    ) -> str:
        """
        Apply automatic fixes to a data string.

        Plain text has minimal autofix - just basic cleanup.

        Args:
            text: The full data string text
            font_map: Font map for width calculation (not used)
            width_threshold: Width threshold in pixels (not used)

        Returns:
            Fixed text (unchanged for plain text)
        """
        # No autofixes for plain text
        return text

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        """
        Return definitions for all problem types.

        Plain text has no predefined problems.

        Returns:
            Empty dict (no problems defined)
        """
        return {}
