import re
import json
import os
from typing import Optional, Set, List, Tuple
from PyQt5.QtGui import QTextCharFormat, QColor, QFont
from PyQt5.QtCore import Qt
from utils.logging_utils import log_debug

class TagManager:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref
        self._legitimate_exact_tags_cache: Optional[Set[str]] = None
        # self._legitimate_tag_patterns_cache: Optional[List[re.Pattern]] = None # Більше не потрібен
        # self.tag_patterns_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tag_patterns.json") # Більше не потрібен

        self.curly_tag_format = QTextCharFormat()
        self.curly_tag_format.setForeground(QColor("#808080"))
        self.curly_tag_format.setFontItalic(True)

        self.bracket_tag_format = QTextCharFormat()
        self.bracket_tag_format.setForeground(QColor("#FFA500"))
        self.bracket_tag_format.setFontWeight(QFont.Bold)

        self.newline_symbol_format = QTextCharFormat()
        self.newline_symbol_format.setForeground(QColor("#A020F0"))
        self.newline_symbol_format.setFontWeight(QFont.Bold)

        self.literal_newline_format = QTextCharFormat()
        self.literal_newline_format.setForeground(QColor("red"))
        self.literal_newline_format.setFontWeight(QFont.Bold)

        self.color_red_format = QTextCharFormat()
        self.color_red_format.setForeground(Qt.red)
        self.color_green_format = QTextCharFormat()
        self.color_green_format.setForeground(Qt.darkGreen)
        self.color_blue_format = QTextCharFormat()
        self.color_blue_format.setForeground(Qt.blue)
        self.color_default_format = QTextCharFormat()

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        default_text_color_from_editor = QColor(Qt.black)
        if self.mw and hasattr(self.mw, 'preview_text_edit') and self.mw.preview_text_edit:
            palette = self.mw.preview_text_edit.palette()
            default_text_color_from_editor = palette.color(self.mw.preview_text_edit.foregroundRole())
        self.color_default_format.setForeground(default_text_color_from_editor)

        rules = [
            (r"(\{\s*Color\s*:\s*Red\s*\})", self.curly_tag_format),
            (r"(\{\s*Color\s*:\s*Green\s*\})", self.curly_tag_format),
            (r"(\{\s*Color\s*:\s*Blue\s*\})", self.curly_tag_format),
            (r"(\{\s*Color\s*:\s*White\s*\})", self.curly_tag_format),
            (r"(\{\s*[^}]*?\s*\})", self.curly_tag_format), # Загальне правило для {тегів}
            (r"(\[\s*[^\]]*?\s*\])", self.bracket_tag_format), # Загальне правило для [тегів]
            (r"(\\n)", self.literal_newline_format),
        ]
        if self.mw and hasattr(self.mw, 'newline_display_symbol') and self.mw.newline_display_symbol:
            rules.append((r"(" + re.escape(self.mw.newline_display_symbol) + r")", self.newline_symbol_format))
        return rules

    def _ensure_exact_tags_loaded(self):
        if self._legitimate_exact_tags_cache is None:
            self._legitimate_exact_tags_cache = set()
            if self.mw and hasattr(self.mw, 'default_tag_mappings'):
                for key, value in self.mw.default_tag_mappings.items():
                    self._legitimate_exact_tags_cache.add(key)    # [tag]
                    self._legitimate_exact_tags_cache.add(value)   # {TAG}
            # Додаємо основні фігурні теги, які завжди легітимні, навіть якщо їх немає в мапінгах
            self._legitimate_exact_tags_cache.add("{Player}")
            # Можна додати сюди інші "завжди легітимні" точні теги
            log_debug(f"Loaded {len(self._legitimate_exact_tags_cache)} exact legitimate tags.")


    def get_legitimate_tags(self) -> Set[str]:
        self._ensure_exact_tags_loaded()
        return self._legitimate_exact_tags_cache if self._legitimate_exact_tags_cache is not None else set()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        self._ensure_exact_tags_loaded()

        # Перевірка квадратних тегів
        if tag_to_check.startswith('[') and tag_to_check.endswith(']'):
            # Квадратний тег легітимний, якщо він є ключем у default_tag_mappings
            return self._legitimate_exact_tags_cache is not None and tag_to_check in self._legitimate_exact_tags_cache
        
        # Перевірка фігурних тегів
        if tag_to_check.startswith('{') and tag_to_check.endswith('}'):
            # Фігурний тег легітимний, якщо він є значенням у default_tag_mappings
            # АБО якщо це один з "завжди легітимних" фігурних тегів
            # АБО якщо ми вирішимо, що всі фігурні теги легітимні за замовчуванням
            if self._legitimate_exact_tags_cache is not None and tag_to_check in self._legitimate_exact_tags_cache:
                return True
            # Для Minish Cap, багато {Symbol:XX} та інших фігурних тегів не мапляться,
            # але є легітимними. Тому, якщо це фігурний тег, вважаємо його легітимним.
            # Можна додати більш складну логіку, якщо потрібно розрізняти типи фігурних тегів.
            return True 

        return False # Якщо тег не квадратний і не фігурний