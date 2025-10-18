# --- START OF FILE plugins/plain_text/tag_manager.py ---
import re
from typing import Optional, Set, List, Tuple
from PyQt5.QtGui import QTextCharFormat, QColor, QFont
from utils.logging_utils import log_debug

class TagManager:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref
        
        self.tag_format = QTextCharFormat()
        self.newline_symbol_format = QTextCharFormat()
        self.red_text_format = QTextCharFormat()
        self.blue_text_format = QTextCharFormat()
        self.color_default_format = QTextCharFormat()
        
        self.reconfigure_styles()

    def reconfigure_styles(self):
        # Use new Tag Style from settings
        tag_color = getattr(self.mw, 'tag_color_rgba', "#FF8C00") if self.mw else "#FF8C00"
        self.tag_format.setForeground(QColor(tag_color))
        self.tag_format.setFontWeight(QFont.Bold if getattr(self.mw, 'tag_bold', True) else QFont.Normal)
        self.tag_format.setFontItalic(getattr(self.mw, 'tag_italic', False))
        self.tag_format.setFontUnderline(getattr(self.mw, 'tag_underline', False))

        nl_color = getattr(self.mw, 'newline_color_rgba', "#A020F0") if self.mw else "#A020F0"
        self.newline_symbol_format.setForeground(QColor(nl_color))
        self.newline_symbol_format.setFontWeight(QFont.Bold if getattr(self.mw, 'newline_bold', True) else QFont.Normal)
        self.newline_symbol_format.setFontItalic(getattr(self.mw, 'newline_italic', False))
        self.newline_symbol_format.setFontUnderline(getattr(self.mw, 'newline_underline', False))

        self.red_text_format.setForeground(QColor("#FF4C4C"))
        self.blue_text_format.setForeground(QColor("#0958e0"))
        
        default_text_color = QColor("black")
        if self.mw and hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
            editor_widget = self.mw.edited_text_edit
            default_text_color = editor_widget.palette().color(editor_widget.foregroundRole())
        
        self.color_default_format.setForeground(default_text_color)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        self.reconfigure_styles() 
        
        rules = [
            (r"(\[\s*[^\]]*?\s*\])", self.tag_format),
        ]
        
        if self.mw and hasattr(self.mw, 'newline_display_symbol') and self.mw.newline_display_symbol:
            rules.append((r"(" + re.escape(self.mw.newline_display_symbol) + r")", self.newline_symbol_format))
            
        return rules
        
    def get_legitimate_tags(self) -> Set[str]:
        return set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        if re.fullmatch(r"\[[^\]]+\]", tag_to_check):
            return True
        return False
