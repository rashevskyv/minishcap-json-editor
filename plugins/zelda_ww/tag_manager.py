import re
from typing import Optional, Set, List, Tuple
from PyQt5.QtGui import QTextCharFormat, QColor
from plugins.common.tag_manager import GenericTagManager

class TagManager(GenericTagManager):
    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.red_text_format = QTextCharFormat()
        self.blue_text_format = QTextCharFormat()
        self.reconfigure_styles()

    def reconfigure_styles(self):
        super().reconfigure_styles()
        self.red_text_format.setForeground(QColor("#FF4C4C"))
        self.blue_text_format.setForeground(QColor("#0958e0"))

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        return super().get_syntax_highlighting_rules()

    def get_legitimate_tags(self) -> Set[str]:
        return set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return bool(re.fullmatch(r"\[[^\]]+\]", tag_to_check))
