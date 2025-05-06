import sys
import re
from PyQt5.QtCore import QRegExp, Qt
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QPen

from utils import log_debug, SPACE_DOT_SYMBOL 

class JsonTagHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        log_debug("JsonTagHighlighter initialized.")
        self.highlightingRules = []
        self.space_dot_format = QTextCharFormat() 
        
        # Значення за замовчуванням, які будуть перезаписані reconfigure_styles
        self.bracket_tag_color_hex = "#FFA500" # Помаранчевий
        self.bracket_tag_format = QTextCharFormat()
        try:
            self.bracket_tag_format.setForeground(QColor(self.bracket_tag_color_hex))
        except: # noqa
            self.bracket_tag_format.setForeground(QColor(255,165,0))


        self.reconfigure_styles() 

    def _apply_css_to_format(self, char_format, css_str):
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
                
    def reconfigure_styles(self, newline_symbol="↵", 
                           newline_css_str="color: #A020F0; font-weight: bold;", 
                           tag_css_str="color: #808080; font-style: italic;", 
                           show_multiple_spaces_as_dots=True, # Не використовується тут, але приймається
                           space_dot_color_hex="#BBBBBB",
                           bracket_tag_color_hex="#FFA500"):
        log_debug(f"JsonTagHighlighter reconfiguring styles: ..., curly_tag_css='{tag_css_str}', bracket_tag_color='{bracket_tag_color_hex}'")
        self.highlightingRules = []
        
        # Rule 1: Теги {...} (колір з tag_css_str)
        curly_tag_format = QTextCharFormat()
        self._apply_css_to_format(curly_tag_format, tag_css_str) 
        self.highlightingRules.append((QRegExp(r"\{[^}]*\}"), curly_tag_format))

        # Rule 2: Displayed newline symbol (↵)
        newlineFormat = QTextCharFormat()
        self._apply_css_to_format(newlineFormat, newline_css_str)
        if newline_symbol: 
            self.highlightingRules.append((QRegExp(re.escape(newline_symbol)), newlineFormat))
        
        # Rule 3: Literal "\\n"
        literalNewlineFormat = QTextCharFormat()
        literalNewlineFormat.setForeground(QColor("red")); literalNewlineFormat.setFontWeight(QFont.Bold)
        self.highlightingRules.append((QRegExp(r"\\n"), literalNewlineFormat))

        # Rule 4: Стилізація символу SPACE_DOT_SYMBOL (·)
        self.space_dot_format = QTextCharFormat()
        try:
            self.space_dot_format.setForeground(QColor(space_dot_color_hex))
        except Exception: self.space_dot_format.setForeground(QColor(Qt.lightGray))
        if SPACE_DOT_SYMBOL: 
             self.highlightingRules.append((QRegExp(re.escape(SPACE_DOT_SYMBOL)), self.space_dot_format))

        # Rule 5: Теги [...] (колір з bracket_tag_color_hex)
        self.bracket_tag_color_hex = bracket_tag_color_hex 
        self.bracket_tag_format = QTextCharFormat()
        try:
            self.bracket_tag_format.setForeground(QColor(self.bracket_tag_color_hex))
            log_debug(f"Set BRACKET_TAG [...] foreground color to: {self.bracket_tag_color_hex}")
        except Exception as e:
            log_debug(f"Error setting BRACKET_TAG color from hex '{self.bracket_tag_color_hex}': {e}. Using default orange.")
            self.bracket_tag_format.setForeground(QColor(255, 165, 0)) 
        pattern_bracket_tag = r"\[[^\]]*\]" 
        self.highlightingRules.append((QRegExp(pattern_bracket_tag), self.bracket_tag_format))


    def highlightBlock(self, text):
        for pattern, format_obj in self.highlightingRules:
            expression = QRegExp(pattern.pattern()) 
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                if length == 0: index = expression.indexIn(text, index + 1); continue
                self.setFormat(index, length, format_obj)
                index = expression.indexIn(text, index + length)