from typing import Set, List, Tuple
from PyQt5.QtGui import QTextCharFormat, QColor, QFont
import re
from .config import P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER

class TagManager:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref
        self.curly_tag_format = QTextCharFormat()
        # Apply configured Tag CSS if present, fallback to gray italic
        tag_css = getattr(self.mw, 'tag_css', None) if self.mw else None
        if tag_css:
            for prop in tag_css.split(';'):
                prop = prop.strip()
                if not prop or ':' not in prop:
                    continue
                key, val = [p.strip().lower() for p in prop.split(':', 1)]
                if key == 'color':
                    self.curly_tag_format.setForeground(QColor(val))
                elif key == 'font-style':
                    self.curly_tag_format.setFontItalic(val == 'italic')
                elif key == 'font-weight':
                    if val == 'bold':
                        self.curly_tag_format.setFontWeight(QFont.Bold)
                    elif val == 'normal':
                        self.curly_tag_format.setFontWeight(QFont.Normal)
        if not self.curly_tag_format.foreground().color().isValid():
            self.curly_tag_format.setForeground(QColor("#808080"))
        if not self.curly_tag_format.fontItalic():
            self.curly_tag_format.setFontItalic(True)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        # Re-apply current Tag CSS in case settings changed
        tag_css = getattr(self.mw, 'tag_css', None) if self.mw else None
        if tag_css:
            fmt = QTextCharFormat()
            for prop in tag_css.split(';'):
                prop = prop.strip()
                if not prop or ':' not in prop:
                    continue
                key, val = [p.strip().lower() for p in prop.split(':', 1)]
                if key == 'color':
                    fmt.setForeground(QColor(val))
                elif key == 'font-style':
                    fmt.setFontItalic(val == 'italic')
                elif key == 'font-weight':
                    if val == 'bold':
                        fmt.setFontWeight(QFont.Bold)
                    elif val == 'normal':
                        fmt.setFontWeight(QFont.Normal)
            # Keep italic default if not specified
            if not fmt.fontItalic():
                fmt.setFontItalic(True)
            self.curly_tag_format = fmt

        rules = [
            (r"(\{[^}]*\})", self.curly_tag_format),
        ]
        return rules

    def get_legitimate_tags(self) -> Set[str]:
        return set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return True
