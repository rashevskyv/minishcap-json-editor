from typing import Set, List, Tuple
from PyQt5.QtGui import QTextCharFormat, QColor, QFont
import re
from .config import P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER

class TagManager:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref
        self.curly_tag_format = QTextCharFormat()
        tag_color = getattr(self.mw, 'tag_color_rgba', None)
        if tag_color:
            self.curly_tag_format.setForeground(QColor(tag_color))
        self.curly_tag_format.setFontWeight(QFont.Bold if getattr(self.mw, 'tag_bold', True) else QFont.Normal)
        self.curly_tag_format.setFontItalic(getattr(self.mw, 'tag_italic', False))
        self.curly_tag_format.setFontUnderline(getattr(self.mw, 'tag_underline', False))

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        # Re-apply current Tag Style in case settings changed
        fmt = QTextCharFormat()
        tag_color = getattr(self.mw, 'tag_color_rgba', None)
        if tag_color:
            fmt.setForeground(QColor(tag_color))
        fmt.setFontWeight(QFont.Bold if getattr(self.mw, 'tag_bold', True) else QFont.Normal)
        fmt.setFontItalic(getattr(self.mw, 'tag_italic', False))
        fmt.setFontUnderline(getattr(self.mw, 'tag_underline', False))
        self.curly_tag_format = fmt

        rules = [
            (r"(\{[^}]*\})", self.curly_tag_format),
        ]
        return rules

    def get_legitimate_tags(self) -> Set[str]:
        return set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return True
