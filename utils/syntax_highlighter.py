import sys
import re
from PyQt5.QtCore import QRegExp, Qt
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QPen
from PyQt5.QtWidgets import QWidget, QMainWindow

from .logging_utils import log_debug
from .utils import SPACE_DOT_SYMBOL

class JsonTagHighlighter(QSyntaxHighlighter):
    STATE_DEFAULT = 0
    STATE_RED = 1
    STATE_GREEN = 2
    STATE_BLUE = 3

    def __init__(self, parent=None, main_window_ref=None):
        super().__init__(parent)
        log_debug("JsonTagHighlighter initialized.")
        self.mw = main_window_ref

        self.default_text_color = QColor(Qt.black)
        doc = self.document()
        editor_widget = None
        if doc:
            parent_object = doc.parent()
            if isinstance(parent_object, QWidget):
                editor_widget = parent_object

        if editor_widget and hasattr(editor_widget, 'palette'):
            self.default_text_color = editor_widget.palette().color(editor_widget.foregroundRole())
        else:
            log_debug("JsonTagHighlighter: Could not get editor widget or palette, using default black text color.")

        self.custom_rules = []
        self.curly_tag_format = QTextCharFormat()
        self.bracket_tag_format = QTextCharFormat()
        self.newline_symbol_format = QTextCharFormat()
        self.literal_newline_format = QTextCharFormat()
        self.space_dot_format = QTextCharFormat()

        self.red_text_format = QTextCharFormat()
        self.green_text_format = QTextCharFormat()
        self.blue_text_format = QTextCharFormat()
        # Ініціалізація self.color_default_format ПЕРЕД першим викликом reconfigure_styles
        self.color_default_format = QTextCharFormat()
        self.color_default_format.setForeground(self.default_text_color) # Встановлюємо тут

        self.reconfigure_styles()
        
    def _apply_css_to_format(self, char_format, css_str, base_color=None):
        if base_color:
            char_format.setForeground(base_color)

        if not css_str: return
        properties = css_str.split(';')
        for prop in properties:
            prop = prop.strip()
            if not prop: continue
            parts = prop.split(':', 1)
            if len(parts) != 2: continue
            key, value = parts[0].strip().lower(), parts[1].strip().lower()
            try:
                if key == 'color': char_format.setForeground(QColor(value))
                elif key == 'background-color': char_format.setBackground(QColor(value))
                elif key == 'font-weight':
                    if value == 'bold': char_format.setFontWeight(QFont.Bold)
                    elif value == 'normal': char_format.setFontWeight(QFont.Normal)
                    else: char_format.setFontWeight(int(value))
                elif key == 'font-style':
                    if value == 'italic': char_format.setFontItalic(True)
                    elif value == 'normal': char_format.setFontItalic(False)
            except Exception as e: log_debug(f"  Error applying CSS property '{prop}': {e}")

    def reconfigure_styles(self, newline_symbol="↵",
                           newline_css_str="color: #A020F0; font-weight: bold;",
                           tag_css_str="color: #808080; font-style: italic;",
                           show_multiple_spaces_as_dots=True,
                           space_dot_color_hex="#BBBBBB",
                           bracket_tag_color_hex="#FF8C00"):
        log_debug(f"JsonTagHighlighter reconfiguring styles: curly_tag_css='{tag_css_str}', bracket_tag_color='{bracket_tag_color_hex}'")

        doc = self.document()
        editor_widget = None
        if doc:
            parent_object = doc.parent()
            if isinstance(parent_object, QWidget):
                editor_widget = parent_object

        if editor_widget and hasattr(editor_widget, 'palette'):
            self.default_text_color = editor_widget.palette().color(editor_widget.foregroundRole())
            log_debug(f"Reconfigure: default_text_color set from editor palette: {self.default_text_color.name()}")
        else:
            self.default_text_color = QColor(Qt.black)
            log_debug("Reconfigure: Could not get editor widget or palette, using default black text color.")
        
        self.color_default_format.setForeground(self.default_text_color) # Оновлюємо формат за замовчуванням

        # Завантаження правил з плагіна гри, якщо можливо
        self.custom_rules = []
        if self.mw and hasattr(self.mw, 'current_game_rules') and self.mw.current_game_rules:
            plugin_rules = self.mw.current_game_rules.get_syntax_highlighting_rules()
            if plugin_rules:
                self.custom_rules = plugin_rules
                log_debug(f"Loaded {len(self.custom_rules)} syntax highlighting rules from game plugin.")
            else:
                log_debug("Game plugin returned no syntax highlighting rules. Using fallback/default styles.")
        else:
            log_debug("No game plugin or main window reference available for syntax rules. Using fallback/default styles.")

        # Якщо плагін не надав правил, використовуємо старі налаштування
        if not self.custom_rules:
            self._apply_css_to_format(self.curly_tag_format, tag_css_str)
            try:
                self.bracket_tag_format.setForeground(QColor(bracket_tag_color_hex))
                self.bracket_tag_format.setFontWeight(QFont.Bold)
            except Exception as e:
                log_debug(f"Error setting BRACKET_TAG style from hex '{bracket_tag_color_hex}': {e}. Using default.")
                self.bracket_tag_format.setForeground(QColor(255, 140, 0))
                self.bracket_tag_format.setFontWeight(QFont.Bold)
            self._apply_css_to_format(self.newline_symbol_format, newline_css_str)
            self._apply_css_to_format(self.literal_newline_format, "color: red; font-weight: bold;")
        else:
            # Очистимо старі формати, оскільки правила з плагіна вже містять QTextCharFormat
            self.curly_tag_format = QTextCharFormat()
            self.bracket_tag_format = QTextCharFormat()
            self.newline_symbol_format = QTextCharFormat()
            self.literal_newline_format = QTextCharFormat()


        try: self.space_dot_format.setForeground(QColor(space_dot_color_hex))
        except Exception: self.space_dot_format.setForeground(QColor(Qt.lightGray))

        self.red_text_format.setForeground(QColor(Qt.red))
        self.green_text_format.setForeground(QColor(Qt.darkGreen))
        self.blue_text_format.setForeground(QColor(Qt.blue))

        self.newline_char = newline_symbol
        if self.document():
             self.rehighlight()

    def highlightBlock(self, text):
        previous_color_state = self.previousBlockState()
        if previous_color_state == -1:
            previous_color_state = self.STATE_DEFAULT

        current_text_format = QTextCharFormat(self.color_default_format)
        current_block_color_state = self.STATE_DEFAULT

        if previous_color_state == self.STATE_RED:
            current_text_format = QTextCharFormat(self.red_text_format)
            current_block_color_state = self.STATE_RED
        elif previous_color_state == self.STATE_GREEN:
            current_text_format = QTextCharFormat(self.green_text_format)
            current_block_color_state = self.STATE_GREEN
        elif previous_color_state == self.STATE_BLUE:
            current_text_format = QTextCharFormat(self.blue_text_format)
            current_block_color_state = self.STATE_BLUE

        # Пріоритет кастомним правилам з плагіна
        if self.custom_rules:
            # Застосовуємо кастомні правила
            for pattern_str, fmt in self.custom_rules:
                try:
                    regex = QRegExp(pattern_str)
                    index = regex.indexIn(text)
                    while index >= 0:
                        length = regex.matchedLength()
                        self.setFormat(index, length, fmt)
                        index = regex.indexIn(text, index + length)
                except Exception as e:
                    log_debug(f"Error applying custom syntax rule (pattern: '{pattern_str}'): {e}")
            
            # Обробка зміни кольору тексту (якщо плагін визначив такі правила)
            # Це приблизна логіка, її треба буде адаптувати до того, як плагін буде передавати інформацію про зміну стану кольору
            # Наприклад, якщо плагін має спеціальні правила для тегів {Color:...}
            color_tag_pattern_str = r"\{\s*Color\s*:\s*(Red|Green|Blue|White)\s*\}"
            for match_color in re.finditer(color_tag_pattern_str, text, re.IGNORECASE):
                color_name = match_color.group(1).lower()
                # Тут ми оновлюємо стан кольору для наступних блоків,
                # але сама підсвітка тегу {Color:...} вже має бути оброблена вище кастомними правилами.
                if color_name == 'red': current_block_color_state = self.STATE_RED
                elif color_name == 'green': current_block_color_state = self.STATE_GREEN
                elif color_name == 'blue': current_block_color_state = self.STATE_BLUE
                elif color_name == 'white': current_block_color_state = self.STATE_DEFAULT
            
            # Підсвітка символу крапки для пробілів, якщо не оброблено кастомними правилами
            if SPACE_DOT_SYMBOL:
                index_dot = text.find(SPACE_DOT_SYMBOL)
                while index_dot >= 0:
                    # Перевіряємо, чи ця позиція вже не відформатована кастомним правилом
                    # Це дуже спрощена перевірка, можливо, знадобиться більш точний механізм
                    is_formatted_by_custom = False
                    for pattern_str, _ in self.custom_rules:
                        try:
                            regex_check = QRegExp(pattern_str)
                            idx_check = regex_check.indexIn(text)
                            while idx_check >= 0:
                                len_check = regex_check.matchedLength()
                                if idx_check <= index_dot < idx_check + len_check:
                                    is_formatted_by_custom = True
                                    break
                                idx_check = regex_check.indexIn(text, idx_check + len_check)
                            if is_formatted_by_custom: break
                        except: pass # Ігноруємо помилки компіляції regex тут

                    if not is_formatted_by_custom:
                        self.setFormat(index_dot, len(SPACE_DOT_SYMBOL), self.space_dot_format)
                    index_dot = text.find(SPACE_DOT_SYMBOL, index_dot + 1)
        else:
            # Запасний варіант, якщо плагін не надав правил (стара логіка)
            last_pos = 0
            parts = [
                r"(\{\s*Color\s*:\s*(Red|Green|Blue|White)\s*\})",
                r"(\{\s*[^}]*?\s*\})",
                r"(\[\s*[^\]]*?\s*\])",
                r"(\\n)"
            ]
            if self.newline_char:
                parts.append(r"(" + re.escape(self.newline_char) + r")")
            if SPACE_DOT_SYMBOL:
                parts.append(r"(" + re.escape(SPACE_DOT_SYMBOL) + r")")

            combined_pattern = re.compile("|".join(parts))

            for match in combined_pattern.finditer(text):
                start, end = match.span()

                if start > last_pos:
                    self.setFormat(last_pos, start - last_pos, current_text_format)

                color_tag_full = match.group(1)
                color_name = match.group(2)
                other_curly_tag = match.group(3)
                bracket_tag = match.group(4)
                literal_newline_tag = match.group(5)

                newline_symbol_match_group_idx = -1
                space_dot_match_group_idx = -1
                current_group_idx_offset = 6
                if self.newline_char:
                    newline_symbol_match_group_idx = current_group_idx_offset
                    current_group_idx_offset +=1
                if SPACE_DOT_SYMBOL:
                    space_dot_match_group_idx = current_group_idx_offset

                newline_char_match = None
                if newline_symbol_match_group_idx != -1 and match.groups()[newline_symbol_match_group_idx-1] is not None :
                    newline_char_match = match.group(newline_symbol_match_group_idx)

                space_dot_char_match = None
                if space_dot_match_group_idx != -1 and match.groups()[space_dot_match_group_idx-1] is not None:
                    space_dot_char_match = match.group(space_dot_match_group_idx)

                if color_tag_full:
                    self.setFormat(start, end - start, self.curly_tag_format)
                    if color_name.lower() == 'red':
                        current_text_format = QTextCharFormat(self.red_text_format)
                        current_block_color_state = self.STATE_RED
                    elif color_name.lower() == 'green':
                        current_text_format = QTextCharFormat(self.green_text_format)
                        current_block_color_state = self.STATE_GREEN
                    elif color_name.lower() == 'blue':
                        current_text_format = QTextCharFormat(self.blue_text_format)
                        current_block_color_state = self.STATE_BLUE
                    elif color_name.lower() == 'white':
                        current_text_format = QTextCharFormat(self.color_default_format)
                        current_block_color_state = self.STATE_DEFAULT
                elif other_curly_tag:
                    self.setFormat(start, end - start, self.curly_tag_format)
                elif bracket_tag:
                    self.setFormat(start, end - start, self.bracket_tag_format)
                elif literal_newline_tag:
                    self.setFormat(start, end - start, self.literal_newline_format)
                elif newline_char_match:
                    self.setFormat(start, end - start, self.newline_symbol_format)
                elif space_dot_char_match:
                    self.setFormat(start, end - start, self.space_dot_format)

                last_pos = end

            if last_pos < len(text):
                self.setFormat(last_pos, len(text) - last_pos, current_text_format)

        self.setCurrentBlockState(current_block_color_state)