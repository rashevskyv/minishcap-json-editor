import sys
import re
from PyQt5.QtCore import QRegExp, Qt
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QPen

from utils import log_debug, SPACE_DOT_SYMBOL # Імпортуємо SPACE_DOT_SYMBOL

class JsonTagHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        log_debug("JsonTagHighlighter initialized.")
        self.highlightingRules = []
        self.space_dot_format = QTextCharFormat() # Формат для символу крапки
        self.reconfigure_styles() 

    def _apply_css_to_format(self, char_format, css_str):
        # ... (код без змін) ...
        if not css_str: return
        properties = css_str.split(';')
        for prop in properties:
            prop = prop.strip();
            if not prop: continue
            parts = prop.split(':', 1);
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
                
    def reconfigure_styles(self, newline_symbol="↵", newline_css_str="color: #A020F0; font-weight: bold;", tag_css_str="color: #808080; font-style: italic;",
                           show_multiple_spaces_as_dots=True, space_dot_color_hex="#BBBBBB"):
        log_debug(f"JsonTagHighlighter reconfiguring styles: nl_sym='{newline_symbol}', ..., show_spaces_as_dots='{show_multiple_spaces_as_dots}', space_dot_color='{space_dot_color_hex}'.")
        self.highlightingRules = []
        # self.show_multiple_spaces_as_dots = show_multiple_spaces_as_dots # Цей прапор тепер використовується в UIUpdater

        # Rule 1: Tags {...}
        tagFormat = QTextCharFormat()
        self._apply_css_to_format(tagFormat, tag_css_str)
        self.highlightingRules.append((QRegExp(r"\{[^}]*\}"), tagFormat))

        # Rule 2: Displayed newline symbol (↵)
        newlineFormat = QTextCharFormat()
        self._apply_css_to_format(newlineFormat, newline_css_str)
        if newline_symbol: # Тільки якщо символ визначений
            self.highlightingRules.append((QRegExp(re.escape(newline_symbol)), newlineFormat))
        
        # Rule 3: Literal "\\n" (якщо вони є в тексті)
        literalNewlineFormat = QTextCharFormat()
        literalNewlineFormat.setForeground(QColor("red")) 
        literalNewlineFormat.setFontWeight(QFont.Bold)
        self.highlightingRules.append((QRegExp(r"\\n"), literalNewlineFormat))

        # Rule 4: Стилізація символу SPACE_DOT_SYMBOL (·)
        # Цей прапор show_multiple_spaces_as_dots тепер керує конвертацією в UIUpdater,
        # а хайлайтер просто стилізує крапку, якщо вона є.
        self.space_dot_format = QTextCharFormat() # Скидаємо формат
        try:
            self.space_dot_format.setForeground(QColor(space_dot_color_hex))
            log_debug(f"Set SPACE_DOT_SYMBOL ('{SPACE_DOT_SYMBOL}') foreground color to: {space_dot_color_hex}")
        except Exception as e:
            log_debug(f"Error setting SPACE_DOT_SYMBOL color from hex '{space_dot_color_hex}': {e}. Using default gray.")
            self.space_dot_format.setForeground(QColor(Qt.lightGray))
        
        # Додаємо правило для SPACE_DOT_SYMBOL
        # Важливо екранувати символ крапки, оскільки він є спеціальним у regex
        self.highlightingRules.append((QRegExp(re.escape(SPACE_DOT_SYMBOL)), self.space_dot_format))


    def highlightBlock(self, text):
        # Застосовуємо всі правила
        for pattern, format_obj in self.highlightingRules:
            expression = QRegExp(pattern.pattern()) 
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                if length == 0: 
                    index = expression.indexIn(text, index + 1)
                    continue
                self.setFormat(index, length, format_obj)
                index = expression.indexIn(text, index + length)
        
        # Правило для форматування самих пробілів тепер не потрібне,
        # оскільки ми замінюємо їх на SPACE_DOT_SYMBOL в UIUpdater.
        # Хайлайтер тепер стилізує сам SPACE_DOT_SYMBOL.