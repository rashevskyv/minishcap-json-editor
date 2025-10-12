# Dialog for interactive spellchecking of selected text
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTextEdit, QListWidget, QSplitter,
                             QDialogButtonBox, QWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QTextBlockFormat
from typing import List, Tuple
import re


class SpellcheckDialog(QDialog):
    """Interactive dialog for spellchecking text with suggestions."""

    def __init__(self, parent, text: str, spellchecker_manager, starting_line_number: int = 0):
        super().__init__(parent)
        self.spellchecker_manager = spellchecker_manager
        self.original_text = text
        self.current_text = text
        self.misspelled_words = []
        self.current_word_index = 0
        self.starting_line_number = starting_line_number  # Line number in preview window

        self.setWindowTitle("Spellcheck")
        self.setMinimumSize(900, 600)
        self.setup_ui()
        self.find_misspelled_words()
        self.pre_highlight_all_misspelled_words()
        self.show_current_word()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Top label with navigation
        top_layout = QHBoxLayout()
        self.status_label = QLabel("Checking spelling...")
        top_layout.addWidget(self.status_label)

        top_layout.addStretch()

        # Navigation buttons
        self.prev_button = QPushButton("← Previous")
        self.prev_button.clicked.connect(self.go_to_previous_word)
        top_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("Next →")
        self.next_button.clicked.connect(self.go_to_next_word)
        top_layout.addWidget(self.next_button)

        layout.addLayout(top_layout)

        # Main splitter (3 panels)
        splitter = QSplitter(Qt.Horizontal)

        # Left panel: Misspelled words list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Misspelled Words:"))

        self.misspelled_list = QListWidget()
        self.misspelled_list.itemClicked.connect(self.jump_to_word_from_list)
        left_layout.addWidget(self.misspelled_list)

        splitter.addWidget(left_widget)

        # Middle panel: Text editor with line numbers
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 0, 0, 0)

        middle_layout.addWidget(QLabel("Text:"))

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(self.current_text)
        self.text_edit.setReadOnly(True)
        # Set monospace font
        font = QFont("Courier New", 10)
        self.text_edit.setFont(font)
        middle_layout.addWidget(self.text_edit)

        splitter.addWidget(middle_widget)

        # Right panel: Suggestions and actions
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.word_label = QLabel("Word:")
        right_layout.addWidget(self.word_label)

        right_layout.addWidget(QLabel("Suggestions:"))

        self.suggestions_list = QListWidget()
        self.suggestions_list.itemDoubleClicked.connect(self.replace_with_suggestion)
        right_layout.addWidget(self.suggestions_list)

        # Action buttons
        button_layout = QVBoxLayout()

        self.ignore_button = QPushButton("Ignore")
        self.ignore_button.clicked.connect(self.ignore_word)
        button_layout.addWidget(self.ignore_button)

        self.ignore_all_button = QPushButton("Ignore All")
        self.ignore_all_button.clicked.connect(self.ignore_all_word)
        button_layout.addWidget(self.ignore_all_button)

        self.replace_button = QPushButton("Replace")
        self.replace_button.clicked.connect(self.replace_word)
        button_layout.addWidget(self.replace_button)

        self.add_to_dict_button = QPushButton("Add to Dictionary")
        self.add_to_dict_button.clicked.connect(self.add_to_dictionary)
        button_layout.addWidget(self.add_to_dict_button)

        button_layout.addStretch()
        right_layout.addLayout(button_layout)

        splitter.addWidget(right_widget)

        # Set splitter sizes (20%, 50%, 30%)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 3)

        layout.addWidget(splitter)

        # Bottom buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)

    def find_misspelled_words(self):
        """Find all misspelled words in the text."""
        self.misspelled_words = []
        word_pattern = re.compile(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ\']+'   )

        lines = self.current_text.split('\n')
        char_offset = 0
        for line_idx, line in enumerate(lines):
            # Replace middle dots with spaces for word detection
            line_with_spaces = line.replace('·', ' ')

            for match in word_pattern.finditer(line_with_spaces):
                word = match.group(0)
                if self.spellchecker_manager.is_misspelled(word):
                    start_pos = char_offset + match.start()
                    end_pos = char_offset + match.end()
                    self.misspelled_words.append((start_pos, end_pos, word, line_idx))
            char_offset += len(line) + 1  # +1 for newline character

    def pre_highlight_all_misspelled_words(self):
        """Highlight all misspelled words with red wavy underline."""
        cursor = self.text_edit.textCursor()
        cursor.setPosition(0)

        # Create format for misspelled words (red wavy underline)
        misspell_format = QTextCharFormat()
        misspell_format.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        misspell_format.setUnderlineColor(QColor("red"))

        for start, end, word, line_idx in self.misspelled_words:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(misspell_format)

        # Populate misspelled words list
        self.misspelled_list.clear()
        for start, end, word, line_idx in self.misspelled_words:
            display_line_num = self.starting_line_number + line_idx + 1
            self.misspelled_list.addItem(f"Line {display_line_num}: {word}")

    def show_current_word(self):
        """Display current misspelled word and its suggestions."""
        if self.current_word_index >= len(self.misspelled_words):
            # No more words
            self.status_label.setText("Spellcheck complete!")
            self.word_label.setText("No more misspelled words.")
            self.suggestions_list.clear()
            self.ignore_button.setEnabled(False)
            self.ignore_all_button.setEnabled(False)
            self.replace_button.setEnabled(False)
            self.add_to_dict_button.setEnabled(False)
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return

        start, end, word, line_idx = self.misspelled_words[self.current_word_index]

        # Update status
        total = len(self.misspelled_words)
        current = self.current_word_index + 1
        self.status_label.setText(f"Word {current} of {total}")

        # Update word label with line number
        display_line_num = self.starting_line_number + line_idx + 1
        self.word_label.setText(f"Line {display_line_num}: \"{word}\"")

        # Highlight word in text with yellow background + red underline
        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)

        # Set yellow background AND red wavy underline for the selection
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#FFFF00"))  # Yellow highlight
        fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        fmt.setUnderlineColor(QColor("red"))
        cursor.mergeCharFormat(fmt)

        # Move cursor to show the word
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

        # Highlight current word in the list
        self.misspelled_list.setCurrentRow(self.current_word_index)

        # Get suggestions
        self.suggestions_list.clear()
        suggestions = self.spellchecker_manager.get_suggestions(word)
        for suggestion in suggestions[:10]:  # Show up to 10 suggestions
            self.suggestions_list.addItem(suggestion)

        if suggestions:
            self.suggestions_list.setCurrentRow(0)

        # Enable/disable navigation buttons
        self.prev_button.setEnabled(self.current_word_index > 0)
        self.next_button.setEnabled(self.current_word_index < len(self.misspelled_words) - 1)

    def go_to_previous_word(self):
        """Navigate to previous misspelled word."""
        if self.current_word_index > 0:
            # Clear current highlight before moving
            self.clear_current_word_highlight()
            self.current_word_index -= 1
            self.show_current_word()

    def go_to_next_word(self):
        """Navigate to next misspelled word."""
        if self.current_word_index < len(self.misspelled_words) - 1:
            # Clear current highlight before moving
            self.clear_current_word_highlight()
            self.current_word_index += 1
            self.show_current_word()

    def clear_current_word_highlight(self):
        """Remove yellow highlight from current word, keep red underline."""
        if self.current_word_index < len(self.misspelled_words):
            start, end, word, line_idx = self.misspelled_words[self.current_word_index]
            cursor = self.text_edit.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)

            # Reset background but keep red underline
            fmt = QTextCharFormat()
            fmt.setBackground(Qt.transparent)
            fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
            fmt.setUnderlineColor(QColor("red"))
            cursor.mergeCharFormat(fmt)

    def jump_to_word_from_list(self, item):
        """Jump to word when clicked in the misspelled words list."""
        clicked_index = self.misspelled_list.row(item)
        if clicked_index != self.current_word_index:
            self.clear_current_word_highlight()
            self.current_word_index = clicked_index
            self.show_current_word()

    def ignore_word(self):
        """Ignore current word and move to next."""
        self.clear_current_word_highlight()
        self.current_word_index += 1
        self.show_current_word()

    def ignore_all_word(self):
        """Ignore all occurrences of current word."""
        if self.current_word_index >= len(self.misspelled_words):
            return

        _, _, word, _ = self.misspelled_words[self.current_word_index]
        # Remove all occurrences of this word from the list
        self.misspelled_words = [
            (s, e, w, l) for s, e, w, l in self.misspelled_words
            if w.lower() != word.lower()
        ]
        self.pre_highlight_all_misspelled_words()
        self.show_current_word()

    def replace_word(self):
        """Replace current word with selected suggestion."""
        if self.current_word_index >= len(self.misspelled_words):
            return

        current_item = self.suggestions_list.currentItem()
        if not current_item:
            return

        replacement = current_item.text()
        self.replace_with_suggestion(current_item)

    def replace_with_suggestion(self, item):
        """Replace word with the given suggestion."""
        if self.current_word_index >= len(self.misspelled_words):
            return

        start, end, word, line_idx = self.misspelled_words[self.current_word_index]
        replacement = item.text()

        # Replace in text
        self.current_text = self.current_text[:start] + replacement + self.current_text[end:]
        self.text_edit.setPlainText(self.current_text)

        # Adjust positions for remaining words
        length_diff = len(replacement) - len(word)
        self.misspelled_words = [
            (s + length_diff if s > start else s,
             e + length_diff if e > start else e,
             w,
             l)
            for i, (s, e, w, l) in enumerate(self.misspelled_words)
            if i != self.current_word_index
        ]

        # Re-apply highlights
        self.pre_highlight_all_misspelled_words()

        # Stay at current index (next word)
        self.show_current_word()

    def add_to_dictionary(self):
        """Add current word to custom dictionary."""
        if self.current_word_index >= len(self.misspelled_words):
            return

        _, _, word, _ = self.misspelled_words[self.current_word_index]
        self.spellchecker_manager.add_to_custom_dictionary(word)

        # Remove this word and all its occurrences from list
        word_lower = word.lower()
        self.misspelled_words = [
            (s, e, w, l) for s, e, w, l in self.misspelled_words
            if w.lower() != word_lower
        ]
        self.pre_highlight_all_misspelled_words()
        self.show_current_word()

    def get_corrected_text(self) -> str:
        """Get the corrected text."""
        return self.current_text
