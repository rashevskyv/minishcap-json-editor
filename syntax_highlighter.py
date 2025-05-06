import sys
import re
from PyQt5.QtCore import QRegExp, Qt
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

from utils import log_debug # Assuming utils.py is in the same directory

class JsonTagHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        log_debug("JsonTagHighlighter initialized.")

        self.highlightingRules = []

        # Rule 1: Tags {...}
        tagFormat = QTextCharFormat()
        tagFormat.setForeground(QColor(Qt.darkGray)) # Set color to dark gray
        # tagFormat.setFontWeight(QFont.Bold) # Optional: make tags bold
        # Use raw string for regex pattern
        pattern = r"\{[^}]*\}" # Matches { followed by zero or more non-} characters, then }
        self.highlightingRules.append((QRegExp(pattern), tagFormat))
        log_debug(f"Added highlighting rule for tags: Pattern='{pattern}', Color='darkGray'")

        # Rule 2: Newline character \n
        newlineFormat = QTextCharFormat()
        newlineFormat.setForeground(QColor(160, 32, 240)) # Violet color (RGB)
        # newlineFormat.setBackground(QColor(240, 240, 200)) # Optional: subtle background for visibility
        # Important: We need to match the literal characters '\' and 'n' if they appear in the text.
        # QSyntaxHighlighter works on the displayed text block. The actual newline characters
        # control block separation and are not usually part of the block's text content itself
        # in a way that highlightBlock can easily format them directly as visible '\n'.
        # Instead, we might highlight the *representation* if it appears, or accept we can't highlight actual newlines.
        
        # Let's try highlighting the *literal sequence* "\n" if it appears in the string data
        pattern_literal_newline = r"\\n" # Match backslash followed by n literally
        self.highlightingRules.append((QRegExp(pattern_literal_newline), newlineFormat))
        log_debug(f"Added highlighting rule for literal '\\n': Pattern='{pattern_literal_newline}', Color='Violet'")


    def highlightBlock(self, text):
        # log_debug(f"Highlighting block: '{text[:50]}...'") # Can be very verbose
        # Apply all defined rules
        for pattern, format in self.highlightingRules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                # log_debug(f"  Applying format for pattern '{pattern.pattern()}' at index {index}, length {length}")
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length) # Continue searching from end of match

        # Optional: Highlight multi-line comments or strings if needed later
        # self.setCurrentBlockState(0)
        # ... logic for multi-line states ...