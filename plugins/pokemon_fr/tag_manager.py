from typing import Set, List, Tuple
from PyQt5.QtGui import QTextCharFormat, QColor, QFont
import re
from .config import P_NEWLINE_MARKER, L_NEWLINE_MARKER

class TagManager:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref
        
        self.p_format = QTextCharFormat()
        self.p_format.setForeground(QColor("green"))
        self.p_format.setFontWeight(QFont.Bold)
        
        self.l_format = QTextCharFormat()
        self.l_format.setForeground(QColor("orange"))
        self.l_format.setFontWeight(QFont.Bold)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        rules = [
            (re.escape(P_NEWLINE_MARKER), self.p_format),
            (re.escape(L_NEWLINE_MARKER), self.l_format),
        ]
        return rules

    def get_legitimate_tags(self) -> Set[str]:
        return set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return True