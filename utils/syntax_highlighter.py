import sys
import re
from PyQt5.QtCore import QRegExp, Qt
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QPen, QTextDocument
from PyQt5.QtWidgets import QWidget, QMainWindow

from .logging_utils import log_debug
from .utils import SPACE_DOT_SYMBOL
from plugins.pokemon_fr.config import P_NEWLINE_MARKER, L_NEWLINE_MARKER, P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER

class JsonTagHighlighter(QSyntaxHighlighter):
    STATE_DEFAULT = 0
    STATE_RED = 1
    STATE_GREEN = 2
    STATE_BLUE = 3

    def __init__(self, parent: QTextDocument, main_window_ref=None):
        super().__init__(parent)
        log_debug("JsonTagHighlighter initialized.")
        self.mw = main_window_ref
        
        self.default_text_color = QColor(Qt.black)
        
        current_theme = getattr(self.mw, 'theme', 'auto')
        if current_theme == 'dark':
            self.default_text_color = QColor("#E0E0E0")
        else:
            editor_widget = parent.parent() if parent else None
            if editor_widget and isinstance(editor_widget, QWidget) and hasattr(editor_widget, 'palette'):
                self.default_text_color = editor_widget.palette().color(editor_widget.foregroundRole())
            else:
                log_debug("JsonTagHighlighter: Could not get editor widget or palette, using default black text color.")

        self.custom_rules = []
        self.curly_tag_format = QTextCharFormat()
        self.bracket_tag_format = QTextCharFormat()
        self.newline_symbol_format = QTextCharFormat()
        self.literal_newline_format = QTextCharFormat()
        self.space_dot_format = QTextCharFormat()
        self.p_marker_format = QTextCharFormat()
        self.l_marker_format = QTextCharFormat()


        self.red_text_format = QTextCharFormat()
        self.green_text_format = QTextCharFormat()
        self.blue_text_format = QTextCharFormat()
        self.color_default_format = QTextCharFormat()
        self.color_default_format.setForeground(self.default_text_color)
        
        parent.contentsChange.connect(self.on_contents_change)

        self.reconfigure_styles()
        
    def on_contents_change(self, position, chars_removed, chars_added):
        self.rehighlight()

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
        log_debug(f"JsonTagHighlighter reconfiguring styles...")
        
        doc = self.document()
        editor_widget = doc.parent() if doc else None
        
        current_theme = getattr(self.mw, 'theme', 'auto')
        if current_theme == 'dark':
            self.default_text_color = QColor("#E0E0E0")
        else:
            if editor_widget and hasattr(editor_widget, 'palette'):
                self.default_text_color = editor_widget.palette().color(editor_widget.foregroundRole())
            else:
                 self.default_text_color = QColor(Qt.black)
        
        self.color_default_format.setForeground(self.default_text_color)
        
        self.custom_rules = []
        if self.mw and hasattr(self.mw, 'current_game_rules') and self.mw.current_game_rules:
            plugin_rules = self.mw.current_game_rules.get_syntax_highlighting_rules()
            if plugin_rules:
                self.custom_rules = plugin_rules
                log_debug(f"Loaded {len(self.custom_rules)} syntax highlighting rules from game plugin.")

        self._apply_css_to_format(self.curly_tag_format, tag_css_str)
        try:
            self.bracket_tag_format.setForeground(QColor(bracket_tag_color_hex))
            self.bracket_tag_format.setFontWeight(QFont.Bold)
        except Exception as e:
            self.bracket_tag_format.setForeground(QColor(255, 140, 0))
            self.bracket_tag_format.setFontWeight(QFont.Bold)
        self._apply_css_to_format(self.newline_symbol_format, newline_css_str)
        self._apply_css_to_format(self.literal_newline_format, "color: red; font-weight: bold;")
        
        self.p_marker_format.setForeground(QColor("green"))
        self.p_marker_format.setFontWeight(QFont.Bold)
        self.l_marker_format.setForeground(QColor("orange"))
        self.l_marker_format.setFontWeight(QFont.Bold)


        try: self.space_dot_format.setForeground(QColor(space_dot_color_hex))
        except Exception: self.space_dot_format.setForeground(QColor(Qt.lightGray))

        self.red_text_format.setForeground(QColor("#FF4C4C"))
        self.green_text_format.setForeground(QColor("#4CAF50"))
        self.blue_text_format.setForeground(QColor("#0958e0"))

        self.newline_char = newline_symbol
        if self.document():
             self.rehighlight()

    def highlightBlock(self, text):
        previous_color_state = self.previousBlockState()
        if previous_color_state == -1: previous_color_state = self.STATE_DEFAULT

        current_text_format = self.color_default_format
        if previous_color_state == self.STATE_RED: current_text_format = self.red_text_format
        elif previous_color_state == self.STATE_GREEN: current_text_format = self.green_text_format
        elif previous_color_state == self.STATE_BLUE: current_text_format = self.blue_text_format
        self.setFormat(0, len(text), current_text_format)
        
        color_tag_pattern = re.compile(r"\{\s*Color\s*:\s*(Red|Green|Blue|White)\s*\}", re.IGNORECASE)
        last_pos = 0
        current_block_color_state = previous_color_state
        for match in color_tag_pattern.finditer(text):
            start, end = match.span()
            color_name = match.group(1).lower()

            format_to_apply = self.color_default_format
            if previous_color_state == self.STATE_RED: format_to_apply = self.red_text_format
            elif previous_color_state == self.STATE_GREEN: format_to_apply = self.green_text_format
            elif previous_color_state == self.STATE_BLUE: format_to_apply = self.blue_text_format
            
            if start > last_pos:
                self.setFormat(last_pos, start - last_pos, format_to_apply)
            
            if color_name == 'red': current_block_color_state = self.STATE_RED
            elif color_name == 'green': current_block_color_state = self.STATE_GREEN
            elif color_name == 'blue': current_block_color_state = self.STATE_BLUE
            else: current_block_color_state = self.STATE_DEFAULT
            
            last_pos = end
            previous_color_state = current_block_color_state
            
        if last_pos < len(text):
            final_format = self.color_default_format
            if current_block_color_state == self.STATE_RED: final_format = self.red_text_format
            elif current_block_color_state == self.STATE_GREEN: final_format = self.green_text_format
            elif current_block_color_state == self.STATE_BLUE: final_format = self.blue_text_format
            self.setFormat(last_pos, len(text) - last_pos, final_format)

        all_rules = self.custom_rules + [
            (r"(\{[^}]*\})", self.curly_tag_format),
            (r"(\[[^\]]*\])", self.bracket_tag_format),
            (r"(\\n)", self.literal_newline_format),
            (re.escape(self.newline_char), self.newline_symbol_format),
            (re.escape(SPACE_DOT_SYMBOL), self.space_dot_format),
            (re.escape(P_NEWLINE_MARKER), self.p_marker_format),
            (re.escape(L_NEWLINE_MARKER), self.l_marker_format),
            (re.escape(P_VISUAL_EDITOR_MARKER), self.p_marker_format),
            (re.escape(L_VISUAL_EDITOR_MARKER), self.l_marker_format),
        ]
        
        for pattern_str, fmt in all_rules:
            try:
                for match in re.finditer(pattern_str, text):
                    self.setFormat(match.start(), match.end() - match.start(), fmt)
            except Exception as e:
                log_debug(f"Error applying syntax rule (pattern: '{pattern_str}'): {e}")

        self.setCurrentBlockState(current_block_color_state)