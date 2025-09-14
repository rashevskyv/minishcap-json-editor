from typing import Set, List, Tuple
from PyQt5.QtGui import QTextCharFormat, QColor, QFont
import re
from .config import P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER

class TagManager:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref
        self.curly_tag_format = QTextCharFormat()
        self.curly_tag_format.setForeground(QColor("#808080"))
        self.curly_tag_format.setFontItalic(True)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        rules = [
            (r"(\{[^}]*\})", self.curly_tag_format),
        ]
        return rules

    def get_legitimate_tags(self) -> Set[str]:
        return set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return True