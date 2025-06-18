from typing import Set, List, Tuple
from PyQt5.QtGui import QTextCharFormat, QColor, QFont
import re
from .config import P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER

class TagManager:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        return []

    def get_legitimate_tags(self) -> Set[str]:
        return set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return True