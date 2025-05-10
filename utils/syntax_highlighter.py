import sys
import re
from PyQt5.QtCore import QRegExp, Qt
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QPen
from PyQt5.QtWidgets import QWidget 

from .utils import log_debug, SPACE_DOT_SYMBOL

class JsonTagHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None): 
        super().__init__(parent)
        log_debug("JsonTagHighlighter initialized.")
        
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

        self.curly_tag_format = QTextCharFormat()
        self.bracket_tag_format = QTextCharFormat()
        self.newline_symbol_format = QTextCharFormat()
        self.literal_newline_format = QTextCharFormat()
        self.space_dot_format = QTextCharFormat()

        self.red_text_format = QTextCharFormat()
        self.green_text_format = QTextCharFormat()
        self.blue_text_format = QTextCharFormat()
        self.default_color_text_format = QTextCharFormat() 

        self.reconfigure_styles() 

    def _apply_css_to_format(self, char_format, css_str, base_color=None):
        if base_color: 
            char_format.setForeground(base_color)

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
        
        try: self.space_dot_format.setForeground(QColor(space_dot_color_hex))
        except Exception: self.space_dot_format.setForeground(QColor(Qt.lightGray))

        self.red_text_format.setForeground(QColor(Qt.red))
        self.green_text_format.setForeground(QColor(Qt.darkGreen)) # Змінено на Qt.darkGreen
        self.blue_text_format.setForeground(QColor(Qt.blue))
        self.default_color_text_format.setForeground(self.default_text_color)

        self.newline_char = newline_symbol
        if self.document(): 
             self.rehighlight()

    def highlightBlock(self, text):
        current_text_format = QTextCharFormat(self.default_color_text_format) 
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
                elif color_name.lower() == 'green':
                    current_text_format = QTextCharFormat(self.green_text_format)
                elif color_name.lower() == 'blue':
                    current_text_format = QTextCharFormat(self.blue_text_format)
                elif color_name.lower() == 'white':
                    current_text_format = QTextCharFormat(self.default_color_text_format)
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