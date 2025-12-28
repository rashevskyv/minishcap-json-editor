# --- START OF FILE components/LineNumberedTextEdit.py ---
from PyQt5.QtWidgets import (QPlainTextEdit, QMainWindow, QMenu, QApplication, QAction,
                             QWidget, QHBoxLayout, QPushButton, QWidgetAction, QDialog,
                             QVBoxLayout, QComboBox, QDialogButtonBox, QLabel, QSpinBox, QToolTip)
from PyQt5.QtGui import (QPainter, QFont, QPaintEvent, QKeyEvent, QKeySequence, QMouseEvent, QIcon, QPixmap, QColor, QTextLine, QTextCursor, QDrag)
from PyQt5.QtCore import Qt, QRect, QSize, QRectF, pyqtSignal, QPoint, QMimeData, QByteArray
from typing import Optional, List, Tuple
import os

from .LineNumberArea import LineNumberArea
from .TextHighlightManager import TextHighlightManager
from utils.logging_utils import log_debug, log_error
from utils.syntax_highlighter import JsonTagHighlighter
from core.glossary_manager import GlossaryEntry
from utils.utils import SPACE_DOT_SYMBOL
from utils.constants import (
    EDITOR_PLAYER_TAG as EDITOR_PLAYER_TAG_CONST,
    ORIGINAL_PLAYER_TAG as ORIGINAL_PLAYER_TAG_CONST,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
    MONOSPACE_EDITOR_FONT_FAMILY as DEFAULT_EDITOR_FONT_FAMILY_CONST,
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS
)
from .LNET_constants import (
    LT_CURRENT_LINE_COLOR, LT_LINKED_CURSOR_BLOCK_COLOR, LT_PREVIEW_SELECTED_LINE_COLOR,
    DT_CURRENT_LINE_COLOR, DT_LINKED_CURSOR_BLOCK_COLOR, DT_PREVIEW_SELECTED_LINE_COLOR,
    LINKED_CURSOR_POS_COLOR, TAG_INTERACTION_HIGHLIGHT_COLOR,
    SEARCH_MATCH_HIGHLIGHT_COLOR, WIDTH_EXCEEDED_LINE_COLOR, SHORT_LINE_COLOR,
    EMPTY_ODD_SUBLINE_COLOR, NEW_BLUE_SUBLINE_COLOR,
    CHARACTER_LIMIT_LINE_POSITION, CHARACTER_LIMIT_LINE_COLOR, CHARACTER_LIMIT_LINE_STYLE, CHARACTER_LIMIT_LINE_WIDTH,
    WIDTH_THRESHOLD_LINE_COLOR, WIDTH_THRESHOLD_LINE_STYLE, WIDTH_THRESHOLD_LINE_WIDTH
)
from .LNET_mouse_handlers import LNETMouseHandlers
from .LNET_highlight_interface import LNETHighlightInterface
from .LNET_paint_helpers import LNETPaintHelpers
from .LNET_paint_event_logic import LNETPaintEventLogic
from .LNET_line_number_area_paint_logic import LNETLineNumberAreaPaintLogic

class LineNumberedTextEdit(QPlainTextEdit):
    lineClicked = pyqtSignal(int)
    selectionChanged = pyqtSignal(list)
    addTagMappingRequest = pyqtSignal(str, str)
    calculateLineWidthRequest = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget_id = str(id(self))[-6:]
        
        self._selected_lines = set()
        self._last_clicked_line = -1
        self._previously_selected_lines = set()
        self.drag_start_pos = None

        self.editor_player_tag = EDITOR_PLAYER_TAG_CONST
        self.original_player_tag = ORIGINAL_PLAYER_TAG_CONST
        self.font_map = {}
        self.game_dialog_max_width_pixels = DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS
        self.line_width_warning_threshold_pixels = DEFAULT_LINE_WIDTH_WARNING_THRESHOLD

        if parent and isinstance(parent, QMainWindow):
            self.editor_player_tag = getattr(parent, 'EDITOR_PLAYER_TAG', EDITOR_PLAYER_TAG_CONST)
            self.original_player_tag = getattr(parent, 'ORIGINAL_PLAYER_TAG', ORIGINAL_PLAYER_TAG_CONST)
            self.font_map = getattr(parent, 'font_map', {})
            self.game_dialog_max_width_pixels = getattr(parent, 'game_dialog_max_width_pixels', DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS)
            self.line_width_warning_threshold_pixels = getattr(parent, 'line_width_warning_threshold_pixels', DEFAULT_LINE_WIDTH_WARNING_THRESHOLD)
            self.character_limit_line_position = getattr(parent, 'editor_char_limit_line_pos', CHARACTER_LIMIT_LINE_POSITION)

        self.lineNumberArea = LineNumberArea(self)
        
        main_window_ref = parent if isinstance(parent, QMainWindow) else (self.window() if isinstance(self.window(), QMainWindow) else None)
        self._set_theme_colors(main_window_ref)

        self.highlightManager = TextHighlightManager(self)
        self.mouse_handler = LNETMouseHandlers(self) 
        self.highlight_interface = LNETHighlightInterface(self)
        
        self.paint_helpers = LNETPaintHelpers(self)
        self.paint_event_logic = LNETPaintEventLogic(self, self.paint_helpers)
        self.lineNumberArea.paint_logic = LNETLineNumberAreaPaintLogic(self, self.paint_helpers, main_window_ref)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.mouse_handler.showContextMenu)


        if not self.isReadOnly():
            self.cursorPositionChanged.connect(self.highlightManager.updateCurrentLineHighlight)
            if not self.isUndoRedoEnabled():
                self.setUndoRedoEnabled(True)

        self.updateLineNumberAreaWidth(0)

        initial_font = QFont(DEFAULT_EDITOR_FONT_FAMILY_CONST)
        font_size_to_set = 10
        if parent and hasattr(parent, 'current_font_size') and parent.current_font_size > 0:
            font_size_to_set = parent.current_font_size
        initial_font.setPointSize(font_size_to_set)
        self.setFont(initial_font)

        self.highlighter = JsonTagHighlighter(self.document(), main_window_ref=main_window_ref, editor_widget_ref=self)
        self._current_glossary_tooltip: Optional[str] = None
        self._hovered_glossary_entry: Optional[GlossaryEntry] = None
        self._glossary_manager = None
        self.setMouseTracking(True)
        self.ensurePolished()

        self.character_limit_line_position = CHARACTER_LIMIT_LINE_POSITION
        self.character_limit_line_color = CHARACTER_LIMIT_LINE_COLOR
        self.character_limit_line_style = CHARACTER_LIMIT_LINE_STYLE
        self.character_limit_line_width = CHARACTER_LIMIT_LINE_WIDTH
        
        self.width_threshold_line_color = WIDTH_THRESHOLD_LINE_COLOR
        self.width_threshold_line_style = WIDTH_THRESHOLD_LINE_STYLE
        self.width_threshold_line_width = WIDTH_THRESHOLD_LINE_WIDTH

        self._update_auxiliary_widths()

    def handle_line_number_click(self, y_pos: int):
        cursor = self.cursorForPosition(QPoint(5, y_pos))
        if cursor.isNull():
            return

        block = cursor.block()
        if not block.isValid():
            return
            
        if self.objectName() == "preview_text_edit":
            self.lineClicked.emit(block.blockNumber())
        else:
            scroll_value = self.horizontalScrollBar().value()
            
            selection_cursor = QTextCursor(block)
            selection_cursor.select(QTextCursor.BlockUnderCursor)
            self.setTextCursor(selection_cursor)
            
            self.horizontalScrollBar().setValue(scroll_value)
            self.setFocus()

    def set_glossary_manager(self, manager) -> None:
        self._glossary_manager = manager
        if hasattr(self, 'highlighter') and self.highlighter:
            self.highlighter.set_glossary_manager(manager)

    def _replace_word_at_cursor(self, word_cursor: QTextCursor, replacement: str) -> None:
        """Replace the word selected by the given cursor with the replacement text."""
        if word_cursor.hasSelection():
            word_cursor.insertText(replacement)

    def _open_spellcheck_dialog_for_selection(self, position_in_widget_coords: QPoint) -> None:
        """Open spellcheck dialog for selected lines from edited_text_edit."""
        log_debug(f"LineNumberedTextEdit: _open_spellcheck_dialog_for_selection called")

        try:
            main_window = self.window()
            if not isinstance(main_window, QMainWindow):
                log_debug("LineNumberedTextEdit: main_window is not QMainWindow")
                return

            spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
            log_debug(f"LineNumberedTextEdit: spellchecker_manager={spellchecker_manager}, enabled={spellchecker_manager.enabled if spellchecker_manager else 'N/A'}")

            if not spellchecker_manager:
                log_debug("LineNumberedTextEdit: No spellchecker_manager")
                return

            # Get edited_text_edit
            if not hasattr(main_window, 'edited_text_edit') or not main_window.edited_text_edit:
                log_debug("LineNumberedTextEdit: No edited_text_edit")
                return

            edited_text_edit = main_window.edited_text_edit

            # Get text to spellcheck from edited_text_edit (translation), not preview (original)
            selected_lines = self.get_selected_lines()
            log_debug(f"LineNumberedTextEdit: selected_lines={selected_lines}")

            line_numbers = []
            if selected_lines:
                # Get text from selected lines in edited_text_edit
                text_parts = []
                for line_num in selected_lines:
                    block = edited_text_edit.document().findBlockByNumber(line_num)
                    if block.isValid():
                        text_parts.append(block.text())
                        line_numbers.append(line_num)
                text_to_check = '\n'.join(text_parts)
            else:
                # Get text from line at cursor in edited_text_edit
                cursor = self.cursorForPosition(position_in_widget_coords)
                line_num = cursor.blockNumber()
                log_debug(f"LineNumberedTextEdit: line_num at cursor={line_num}")

                block = edited_text_edit.document().findBlockByNumber(line_num)
                if not block.isValid():
                    log_debug("LineNumberedTextEdit: Block not valid")
                    return
                text_to_check = block.text()
                line_numbers = [line_num]

            log_debug(f"LineNumberedTextEdit: text_to_check length={len(text_to_check)}, line_numbers={line_numbers}")

            if not text_to_check.strip():
                log_debug("LineNumberedTextEdit: text_to_check is empty")
                return

            log_debug("LineNumberedTextEdit: Opening SpellcheckDialog")

            # Import here to avoid circular dependency
            from dialogs.spellcheck_dialog import SpellcheckDialog

            # Open dialog with real line numbers
            dialog = SpellcheckDialog(self, text_to_check, spellchecker_manager,
                                     starting_line_number=0, line_numbers=line_numbers)
            log_debug("LineNumberedTextEdit: SpellcheckDialog created, calling exec_()")

            if dialog.exec_():
                log_debug("LineNumberedTextEdit: Dialog accepted, applying corrections")
                corrected_text = dialog.get_corrected_text()
                # Update edited_text_edit with corrected text
                self._apply_corrected_text_to_editor(corrected_text, line_numbers)
                log_debug("LineNumberedTextEdit: Corrections applied")
            else:
                log_debug("LineNumberedTextEdit: Dialog cancelled")

        except Exception as e:
            log_error(f"LineNumberedTextEdit: Error in _open_spellcheck_dialog_for_selection: {e}", exc_info=True)

    def _apply_corrected_text_to_editor(self, corrected_text: str, line_numbers: List[int]) -> None:
        """Apply corrected text back to the edited_text_edit."""
        main_window = self.window()
        if not isinstance(main_window, QMainWindow):
            return

        if not hasattr(main_window, 'edited_text_edit') or not main_window.edited_text_edit:
            return

        edited_text_edit = main_window.edited_text_edit

        # Split corrected text by lines
        corrected_lines = corrected_text.split('\n')

        # Update each line in edited_text_edit
        for i, line_num in enumerate(line_numbers):
            if i < len(corrected_lines):
                block = edited_text_edit.document().findBlockByNumber(line_num)
                if block.isValid():
                    cursor = QTextCursor(block)
                    cursor.select(QTextCursor.BlockUnderCursor)
                    cursor.insertText(corrected_lines[i])

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        entry = self._find_glossary_entry_at(event.pos())
        tooltip_text = None
        if entry:
            lines = [f"{entry.original} → {entry.translation}"]
            if entry.notes:
                lines.append(entry.notes)
            tooltip_text = "\n".join(lines)

        if tooltip_text and tooltip_text != self._current_glossary_tooltip:
            QToolTip.showText(self.mapToGlobal(event.pos()), tooltip_text, self)
            self._current_glossary_tooltip = tooltip_text
        elif not tooltip_text and self._current_glossary_tooltip:
            QToolTip.hideText()
            self._current_glossary_tooltip = None

        self._hovered_glossary_entry = entry

        if self.objectName() == "preview_text_edit" and event.buttons() == Qt.LeftButton and self._selected_lines:
            if self.drag_start_pos is not None and (event.pos() - self.drag_start_pos).manhattanLength() > QApplication.startDragDistance():
                drag = QDrag(self)
                mime_data = QMimeData()
                
                data = QByteArray()
                data.append(str(sorted(list(self._selected_lines))).encode('utf-8'))
                mime_data.setData("application/x-selected-lines", data)
                
                drag.setMimeData(mime_data)
                drag.exec_(Qt.MoveAction)
                self.drag_start_pos = None

        super().mouseMoveEvent(event)

    def get_selected_lines(self):
        return sorted(list(self._selected_lines))

    def set_selected_lines(self, lines: List[int]):
        self._selected_lines = set(lines)
        self._update_selection_highlight()
        self._emit_selection_changed()

    def clear_selection(self):
        self._selected_lines.clear()
        self._last_clicked_line = -1
        self._update_selection_highlight()
        self._emit_selection_changed()

    def _update_selection_highlight(self):
        lines_to_highlight = self._selected_lines - self._previously_selected_lines
        lines_to_clear = self._previously_selected_lines - self._selected_lines
        
        self.highlightManager.set_background_for_lines(lines_to_highlight, lines_to_clear)
        
        self._previously_selected_lines = self._selected_lines.copy()

    def _emit_selection_changed(self):
        self.selectionChanged.emit(self.get_selected_lines())

    def leaveEvent(self, event) -> None:
        if self._current_glossary_tooltip:
            QToolTip.hideText()
            self._current_glossary_tooltip = None
        self._hovered_glossary_entry = None
        super().leaveEvent(event)

    def _find_glossary_entry_at(self, pos) -> Optional[GlossaryEntry]:
        cursor = self.cursorForPosition(pos)
        block = cursor.block()
        if not block.isValid():
            return None
        data = block.userData()
        matches = getattr(data, 'matches', None)
        if not matches:
            return None
        relative_pos = cursor.position() - block.position()
        for match in matches:
            if match.start <= relative_pos < match.end:
                return match.entry
        return None

    def _set_theme_colors(self, main_window_ref):
        theme = 'light'
        if main_window_ref and hasattr(main_window_ref, 'theme'):
            theme = main_window_ref.theme

        if theme == 'dark':
            self.current_line_color = DT_CURRENT_LINE_COLOR
            self.linked_cursor_block_color = DT_LINKED_CURSOR_BLOCK_COLOR
            self.preview_selected_line_color = DT_PREVIEW_SELECTED_LINE_COLOR
            self.lineNumberArea.odd_line_background = QColor("#303030") 
            self.lineNumberArea.even_line_background = QColor("#383838")
            self.lineNumberArea.number_color = QColor("#B0B0B0")
        else:
            self.current_line_color = LT_CURRENT_LINE_COLOR
            self.linked_cursor_block_color = LT_LINKED_CURSOR_BLOCK_COLOR
            self.preview_selected_line_color = LT_PREVIEW_SELECTED_LINE_COLOR
            self.lineNumberArea.odd_line_background = QColor(Qt.lightGray).lighter(115) 
            self.lineNumberArea.even_line_background = QColor(Qt.white) 
            self.lineNumberArea.number_color = QColor(Qt.darkGray)

        self.linked_cursor_pos_color = LINKED_CURSOR_POS_COLOR
        self.tag_interaction_highlight_color = TAG_INTERACTION_HIGHLIGHT_COLOR
        self.search_match_highlight_color = SEARCH_MATCH_HIGHLIGHT_COLOR
        self.width_exceeded_line_color = WIDTH_EXCEEDED_LINE_COLOR 
        self.short_line_color = SHORT_LINE_COLOR 
        self.empty_odd_subline_color = EMPTY_ODD_SUBLINE_COLOR
        self.new_blue_subline_color = NEW_BLUE_SUBLINE_COLOR 

    def _create_color_button(self, parent_widget, color_name: str, color_rgb_str: str, menu_to_close: QMenu):
        btn = QPushButton(parent_widget)
        button_size = 22 
        btn.setFixedSize(button_size, button_size)
        
        normal_style = f"background-color: {color_rgb_str}; border: 1px solid black; border-radius: 3px;"
        pressed_style = f"background-color: {color_rgb_str}; border: 2px solid darkblue; border-radius: 3px;"
        
        btn.setStyleSheet(normal_style)
        btn.setToolTip(f"Обгорнути тегом {{Color:{color_name.capitalize()}}}")

        btn.pressed.connect(lambda s=pressed_style: btn.setStyleSheet(s))
        
        def on_button_clicked():
            self.mouse_handler._wrap_selection_with_color(color_name)
            btn.setStyleSheet(normal_style)

        btn.clicked.connect(on_button_clicked)
        
        return btn

    def populateContextMenu(self, menu: QMenu, position_in_widget_coords):
        log_debug(f"LNET ({self.objectName()}): populateContextMenu called.")
        main_window = self.window()
        if not isinstance(main_window, QMainWindow):
            return

        translator = getattr(main_window, 'translation_handler', None)
        custom_actions_added = False

        glossary_entry = None
        if self.objectName() == "original_text_edit":
            cursor = self.textCursor()
            selection_text = cursor.selectedText().replace('\u2029', '\r\n').strip()
            if selection_text:
                add_term_candidate = selection_text
                context_line = cursor.block().text().replace('\u2029', ' ').strip()
            else:
                cursor_at_pos = self.cursorForPosition(position_in_widget_coords)
                cursor_at_pos.select(QTextCursor.WordUnderCursor)
                add_term_candidate = cursor_at_pos.selectedText().replace('\u2029', '\r\n').strip()
                context_line = cursor_at_pos.block().text().replace('\u2029', ' ').strip()

            context_line = context_line or ''

            glossary_entry = self._find_glossary_entry_at(position_in_widget_coords)
            existing_entry = None
            if glossary_entry and translator is not None:
                existing_entry = glossary_entry
            elif translator is not None and add_term_candidate:
                existing_entry = translator.get_glossary_entry(add_term_candidate)

            if existing_entry and translator is not None:
                action = menu.addAction("Edit Glossary Entry…")
                action.setEnabled(True)
                action.triggered.connect(
                    lambda checked=False, term=existing_entry.original: translator.edit_glossary_entry(term)
                )
            else:
                action = menu.addAction("Add to Glossary…")
                action_enabled = bool(add_term_candidate) and translator is not None
                action.setEnabled(action_enabled)
                if action_enabled:
                    action.triggered.connect(
                        lambda checked=False, term=add_term_candidate, ctx=context_line: translator.add_glossary_entry(term, ctx)
                    )
            custom_actions_added = True
            if glossary_entry:
                menu.addSeparator()
                term_value = glossary_entry.original
                show_action = menu.addAction(
                    f"Show Glossary Entry for \"{term_value}\""
                )
                if translator:
                    show_action.triggered.connect(
                        lambda checked=False, term=term_value: translator.show_glossary_dialog(term)
                    )
                else:
                    show_action.setEnabled(False)
                menu.addSeparator()

        if self.objectName() == "edited_text_edit" and not self.isReadOnly():
            cursor = self.textCursor()
            has_selection = cursor.hasSelection()

            # Spellchecker: Show suggestions and add to dictionary
            spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
            if spellchecker_manager and spellchecker_manager.enabled:
                # Get word under cursor and its position
                if not has_selection:
                    cursor_at_pos = self.cursorForPosition(position_in_widget_coords)
                    click_position = cursor_at_pos.position()
                    block = cursor_at_pos.block()
                    block_text = block.text()
                    position_in_block = click_position - block.position()

                    # Replace middle dots with spaces for word detection
                    text_with_spaces = block_text.replace('·', ' ')

                    # Find word boundaries at click position using regex
                    import re
                    word_pattern = re.compile(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ\']+')
                    word_under_cursor = ""
                    word_start = 0
                    word_end = 0

                    for match in word_pattern.finditer(text_with_spaces):
                        if match.start() <= position_in_block < match.end():
                            word_under_cursor = match.group(0).strip("'")
                            word_start = match.start()
                            word_end = match.end()
                            break

                    # Create cursor for the actual word (in original text with middle dots)
                    word_cursor = QTextCursor(block)
                    word_cursor.setPosition(block.position() + word_start)
                    word_cursor.setPosition(block.position() + word_end, QTextCursor.KeepAnchor)
                else:
                    # Replace middle dots with spaces, then extract first word, strip apostrophes
                    raw_text = cursor.selectedText().strip()
                    text_with_spaces = raw_text.replace('·', ' ')
                    word_under_cursor = text_with_spaces.split()[0].strip("'") if text_with_spaces.split() else ""
                    word_cursor = cursor

                if word_under_cursor and spellchecker_manager.is_misspelled(word_under_cursor):
                    if not custom_actions_added:
                        menu.addSeparator()
                        custom_actions_added = True

                    # Get spelling suggestions
                    suggestions = spellchecker_manager.get_suggestions(word_under_cursor)

                    if suggestions:
                        # Limit to first 5 suggestions
                        for suggestion in suggestions[:5]:
                            suggestion_action = menu.addAction(f"→ {suggestion}")
                            suggestion_action.triggered.connect(
                                lambda checked=False, s=suggestion, c=word_cursor: self._replace_word_at_cursor(c, s)
                            )
                        menu.addSeparator()
                    else:
                        # No suggestions available
                        no_suggestions_action = menu.addAction("(No suggestions)")
                        no_suggestions_action.setEnabled(False)
                        menu.addSeparator()

                    add_to_dict_action = menu.addAction(f"Add \"{word_under_cursor}\" to Dictionary")
                    add_to_dict_action.triggered.connect(
                        lambda checked=False, word=word_under_cursor: spellchecker_manager.add_to_custom_dictionary(word)
                    )
                    log_debug(f"Added 'Add to Dictionary' context menu item for word: {word_under_cursor}")

            if translator and has_selection:
                if not custom_actions_added:
                    menu.addSeparator()
                    custom_actions_added = True

                variation_action = menu.addAction("AI Variations for Selected")
                variation_action.triggered.connect(translator.generate_variation_for_selection)

            if has_selection:
                if not custom_actions_added:
                    menu.addSeparator()
                    custom_actions_added = True

                color_widget_action = QWidgetAction(menu)
                color_palette_widget = QWidget(menu)
                palette_layout = QHBoxLayout(color_palette_widget)
                palette_layout.setContentsMargins(5, 3, 5, 3)
                palette_layout.setSpacing(4)

                colors_map = {
                    "Red": "rgb(200,0,0)",
                    "Green": "rgb(0,100,0)",
                    "Blue": "rgb(0,0,200)"
                }

                for color_name_str, color_rgb_str in colors_map.items():
                    color_button = self._create_color_button(color_palette_widget, color_name_str, color_rgb_str, menu)
                    palette_layout.addWidget(color_button)

                color_palette_widget.setLayout(palette_layout)
                color_widget_action.setDefaultWidget(color_palette_widget)
                menu.addAction(color_widget_action)
        
        if self.objectName() == "preview_text_edit":
            if not custom_actions_added: menu.addSeparator(); custom_actions_added = True

            translator = getattr(main_window, 'translation_handler', None)
            selected_lines = self.get_selected_lines()

            if translator:
                if selected_lines:
                    num_selected = len(selected_lines)
                    if num_selected > 1:
                        action_text = f"AI Translate {num_selected} Lines (UA)"
                    else:
                        action_text = f"AI Translate Line {selected_lines[0] + 1} (UA)"
                else:
                    cursor = self.cursorForPosition(position_in_widget_coords)
                    line_num = cursor.blockNumber()
                    action_text = f"AI Translate Line {line_num + 1} (UA)"

                translate_action = menu.addAction(action_text)
                translate_action.triggered.connect(lambda: translator.translate_preview_selection(position_in_widget_coords))

                translate_block_action = menu.addAction("AI Translate Entire Block (UA)")
                translate_block_action.triggered.connect(lambda: translator.translate_current_block())

            # Spellcheck options
            spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
            if spellchecker_manager and spellchecker_manager.enabled:
                menu.addSeparator()

                if selected_lines:
                    num_selected = len(selected_lines)
                    if num_selected > 1:
                        spellcheck_text = f"Spellcheck {num_selected} Lines"
                    else:
                        spellcheck_text = f"Spellcheck Line {selected_lines[0] + 1}"
                else:
                    cursor = self.cursorForPosition(position_in_widget_coords)
                    line_num = cursor.blockNumber()
                    spellcheck_text = f"Spellcheck Line {line_num + 1}"

                spellcheck_action = menu.addAction(spellcheck_text)
                spellcheck_action.triggered.connect(
                    lambda: self._open_spellcheck_dialog_for_selection(position_in_widget_coords)
                )

            if len(selected_lines) > 1:
                num_selected = len(selected_lines)
                menu.addSeparator()
                set_font_action = menu.addAction(f"Set Font for {num_selected} Lines...")
                set_font_action.triggered.connect(self.handle_mass_set_font)
                set_width_action = menu.addAction(f"Set Width for {num_selected} Lines...")
                set_width_action.triggered.connect(self.handle_mass_set_width)

    def _update_auxiliary_widths(self):
        current_font_metrics = self.fontMetrics()
        
        max_width_for_calc = self.game_dialog_max_width_pixels
        if max_width_for_calc < 1000: max_width_for_calc = 1000
        
        self.pixel_width_display_area_width = current_font_metrics.horizontalAdvance(str(max_width_for_calc)) + 6
        
        num_indicators_to_display = 0
        main_window = self.window()
        if isinstance(main_window, QMainWindow) and hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
            problem_defs = main_window.current_game_rules.get_problem_definitions()
            num_indicators_to_display = len(problem_defs) 
        
        max_preview_indicators = getattr(self.lineNumberArea, 'max_problem_indicators', 5) 
        num_indicators_to_display = min(num_indicators_to_display, max_preview_indicators)

        indicator_area_width = 0
        indicator_area_width += self.lineNumberArea.preview_indicator_width + self.lineNumberArea.preview_indicator_spacing
        if num_indicators_to_display > 0:
            indicator_area_width += (self.lineNumberArea.preview_indicator_width * num_indicators_to_display) + \
                                    (self.lineNumberArea.preview_indicator_spacing * num_indicators_to_display)
        
        self.preview_indicator_area_width = indicator_area_width + 2


        self.updateLineNumberAreaWidth(0)

    def setFont(self, font: QFont):
        super().setFont(font)
        if hasattr(self, 'highlighter') and self.highlighter:
            self.highlighter.rehighlight()
        self._update_auxiliary_widths()
        if hasattr(self, 'lineNumberArea'):
             self.lineNumberArea.update()
        self.viewport().update()

    def keyPressEvent(self, event: QKeyEvent):
        main_window = self.window()

        is_arrow_key = event.key() in (Qt.Key_Left, Qt.Key_Right)
        if is_arrow_key and event.modifiers() == Qt.NoModifier and not self.isReadOnly():
            move_right = event.key() == Qt.Key_Right
            if self._snap_cursor_out_of_icon_sequences(move_right):
                event.accept()
                return

        if not self.isReadOnly() and event.key() == Qt.Key_Space and getattr(main_window, 'show_multiple_spaces_as_dots', False):
            cursor = self.textCursor()
            block_text = cursor.block().text()
            pos = cursor.positionInBlock()

            char_before = block_text[pos-1] if pos > 0 else '\n'
            char_after = block_text[pos] if pos < len(block_text) else '\n'

            if char_before in (' ', SPACE_DOT_SYMBOL) or char_after in (' ', SPACE_DOT_SYMBOL) or pos == 0 or pos == len(block_text):
                self.textCursor().insertText(SPACE_DOT_SYMBOL)
            else:
                self.textCursor().insertText(' ')
            event.accept()
            return
            
        if not self.isReadOnly() and isinstance(main_window, QMainWindow) and main_window.current_game_rules:
            game_rules = main_window.current_game_rules
            is_enter_key = event.key() in (Qt.Key_Return, Qt.Key_Enter)

            if is_enter_key:
                char_to_insert = ''
                modifiers = event.modifiers()
                
                if modifiers & Qt.ShiftModifier:
                    char_to_insert = game_rules.get_shift_enter_char()
                elif modifiers & Qt.ControlModifier:
                    char_to_insert = game_rules.get_ctrl_enter_char()
                elif modifiers == Qt.NoModifier:
                    char_to_insert = game_rules.get_enter_char()
                
                if char_to_insert:
                    self.textCursor().insertText(char_to_insert)
                    event.accept()
                    return

        super().keyPressEvent(event)

    def setReadOnly(self, ro):
        super().setReadOnly(ro)
        self.highlightManager.clearAllHighlights()
        if not ro:
             self.highlightManager.updateCurrentLineHighlight()
             if not self.isUndoRedoEnabled(): self.setUndoRedoEnabled(True)
        self.viewport().update()

    def lineNumberAreaWidth(self):
        digits = 1; max_val = max(1, self.blockCount())
        while max_val >= 10: max_val //= 10; digits += 1
        current_font_metrics = self.fontMetrics()
        base_width = current_font_metrics.horizontalAdvance('9') * (digits) + 10
        additional_width = 0
        if self.objectName() in ["original_text_edit", "edited_text_edit"] and self.font_map:
            additional_width = self.pixel_width_display_area_width
        elif self.objectName() == "preview_text_edit":
            additional_width = self.preview_indicator_area_width
        return base_width + additional_width

    def updateLineNumberAreaWidth(self, _):
        new_width = self.lineNumberAreaWidth()
        self.setViewportMargins(new_width, 0, 0, 0)
        if hasattr(self, 'lineNumberArea'): 
            self.lineNumberArea.updateGeometry()
            self.lineNumberArea.update()

    def updateLineNumberArea(self, rect: QRectF, dy: int):
        if hasattr(self, 'lineNumberArea'): 
            if dy: self.lineNumberArea.scroll(0, dy)
            else: self.lineNumberArea.update(0, 0, self.lineNumberArea.width(), self.lineNumberArea.height())
        if self.isVisible():
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        if hasattr(self, 'lineNumberArea'): 
            self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))
        if self.isVisible():
            self.viewport().update()

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        if hasattr(self, 'paint_event_logic'): 
            self.paint_event_logic.execute_paint_event(event)

    def lineNumberAreaPaintEvent(self, event, painter_device):
        if hasattr(self.lineNumberArea, 'paint_logic'):
            self.lineNumberArea.paint_logic.execute_paint_event(event, painter_device)

    def mousePressEvent(self, event: QMouseEvent):
        self.mouse_handler.mousePressEvent(event) 

    def super_mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.mouse_handler.mouseReleaseEvent(event) 

    def super_mouseReleaseEvent(self, event: QMouseEvent):
        super().mouseReleaseEvent(event)

    def _get_icon_sequences(self) -> List[str]:
        if self.objectName() == 'preview_text_edit':
            return []
        main_window = self.window()
        if isinstance(main_window, QMainWindow):
            sequences = getattr(main_window, 'icon_sequences', None)
            if isinstance(sequences, list):
                return sequences
        return []

    def _find_icon_sequence_in_block(self, block_text: str, sequences: List[str], position_in_block: int) -> Optional[Tuple[int, int, str]]:
        if not block_text or not sequences:
            return None
        
        for token in sequences:
            start = -1
            while True:
                start = block_text.find(token, start + 1)
                if start == -1:
                    break
                end = start + len(token)
                if start <= position_in_block < end:
                    return start, end, token
        return None

    def _snap_cursor_out_of_icon_sequences(self, move_right: bool) -> bool:
        cursor = self.textCursor()
        if cursor.hasSelection(): return False
        
        block = cursor.block()
        if not block.isValid(): return False

        sequences = self._get_icon_sequences()
        if not sequences: return False

        pos_in_block = cursor.positionInBlock()
        block_text = block.text()
        
        all_matches = []
        for token in sequences:
            start = -1
            while True:
                start = block_text.find(token, start + 1)
                if start == -1: break
                all_matches.append((start, start + len(token), token))
        
        if not all_matches: return False

        for start, end, token in all_matches:
            if start < pos_in_block < end:
                new_pos = end if move_right else start
                new_cursor = QTextCursor(block)
                new_cursor.setPosition(block.position() + new_pos)
                self.setTextCursor(new_cursor)
                self._momentary_highlight_tag(block, start, len(token))
                return True
            elif move_right and pos_in_block == start:
                new_cursor = QTextCursor(block)
                new_cursor.setPosition(block.position() + end)
                self.setTextCursor(new_cursor)
                self._momentary_highlight_tag(block, start, len(token))
                return True
            elif not move_right and pos_in_block == end:
                new_cursor = QTextCursor(block)
                new_cursor.setPosition(block.position() + start)
                self.setTextCursor(new_cursor)
                self._momentary_highlight_tag(block, start, len(token))
                return True
                
        return False

    def _momentary_highlight_tag(self, block, start_in_block, length):
        self.highlight_interface._momentary_highlight_tag(block, start_in_block, length)

    def _apply_all_extra_selections(self):
        self.highlight_interface._apply_all_extra_selections()

    def addCriticalProblemHighlight(self, line_number: int):
        self.highlight_interface.addCriticalProblemHighlight(line_number)

    def removeCriticalProblemHighlight(self, line_number: int) -> bool:
        return self.highlight_interface.removeCriticalProblemHighlight(line_number)

    def clearCriticalProblemHighlights(self):
        self.highlight_interface.clearCriticalProblemHighlights()

    def hasCriticalProblemHighlight(self, line_number = None) -> bool:
        return self.highlight_interface.hasCriticalProblemHighlight(line_number)

    def addWarningLineHighlight(self, line_number: int):
        self.highlight_interface.addWarningLineHighlight(line_number)

    def removeWarningLineHighlight(self, line_number: int) -> bool:
        return self.highlight_interface.removeWarningLineHighlight(line_number)

    def clearWarningLineHighlights(self):
        self.highlight_interface.clearWarningLineHighlights()

    def hasWarningLineHighlight(self, line_number = None) -> bool:
        return self.highlight_interface.hasWarningLineHighlight(line_number)

    def addWidthExceededHighlight(self, line_number: int):
        self.highlight_interface.addWidthExceededHighlight(line_number)

    def removeWidthExceededHighlight(self, line_number: int) -> bool:
        return self.highlight_interface.removeWidthExceededHighlight(line_number)

    def clearWidthExceededHighlights(self):
        self.highlight_interface.clearWidthExceededHighlights()

    def hasWidthExceededHighlight(self, line_number = None) -> bool:
        return self.highlight_interface.hasWidthExceededHighlight(line_number)
    
    def addShortLineHighlight(self, line_number: int):
        self.highlight_interface.addShortLineHighlight(line_number)

    def removeShortLineHighlight(self, line_number: int) -> bool:
        return self.highlight_interface.removeShortLineHighlight(line_number)

    def clearShortLineHighlights(self):
        self.highlight_interface.clearShortLineHighlights()

    def hasShortLineHighlight(self, line_number = None) -> bool:
        return self.highlight_interface.hasShortLineHighlight(line_number)

    def addEmptyOddSublineHighlight(self, block_number: int):
        self.highlight_interface.addEmptyOddSublineHighlight(block_number)

    def removeEmptyOddSublineHighlight(self, block_number: int) -> bool:
        return self.highlight_interface.removeEmptyOddSublineHighlight(block_number)

    def clearEmptyOddSublineHighlights(self):
        self.highlight_interface.clearEmptyOddSublineHighlights()

    def hasEmptyOddSublineHighlight(self, block_number = None) -> bool:
        return self.highlight_interface.hasEmptyOddSublineHighlight(block_number)

    def clearPreviewSelectedLineHighlight(self):
        self.highlightManager.set_background_for_lines(set(), self._previously_selected_lines)
        self.clear_selection()

    def setLinkedCursorPosition(self, line_number: int, column_number: int):
        self.highlight_interface.setLinkedCursorPosition(line_number, column_number)

    def applyQueuedHighlights(self):
        self.editor.highlightManager.applyHighlights()

    def clearAllProblemTypeHighlights(self):
        self.editor.highlightManager.clearAllProblemHighlights()

    def addProblemLineHighlight(self, line_number: int):
        self.addCriticalProblemHighlight(line_number)

    def removeProblemLineHighlight(self, line_number: int) -> bool:
        return self.removeCriticalProblemHighlight(line_number)

    def clearProblemLineHighlights(self):
        self.clearAllProblemTypeHighlights()
        
    def hasProblemHighlight(self, line_number = None) -> bool:
        return self.hasProblemHighlight(line_number)

    def handle_mass_set_font(self):
        selected_lines = self.get_selected_lines()
        if not selected_lines: return

        main_window = self.window()
        dialog = MassFontDialog(main_window)
        if dialog.exec_():
            font_file = dialog.get_selected_font()
            main_window.string_settings_handler.apply_font_to_lines(selected_lines, font_file)

    def handle_mass_set_width(self):
        selected_lines = self.get_selected_lines()
        if not selected_lines: return

        main_window = self.window()
        dialog = MassWidthDialog(main_window)
        if dialog.exec_():
            width = dialog.get_width()
            main_window.string_settings_handler.apply_width_to_lines(selected_lines, width)

class MassFontDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Font for Multiple Lines")
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Select a font to apply to the selected lines:"))
        
        self.font_combo = QComboBox(self)
        self.populate_fonts(parent)
        layout.addWidget(self.font_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate_fonts(self, main_window):
        self.font_combo.addItem(f"Plugin Default ({main_window.default_font_file or 'None'})", "default")
        
        plugin_dir_name = main_window.active_game_plugin
        if plugin_dir_name:
            fonts_dir = os.path.join("plugins", plugin_dir_name, "fonts")
            if os.path.isdir(fonts_dir):
                for filename in sorted(os.listdir(fonts_dir)):
                    if filename.lower().endswith(".json"):
                        self.font_combo.addItem(filename, filename)

    def get_selected_font(self):
        return self.font_combo.currentData()

class MassWidthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Set Width for Multiple Lines")
        layout = QVBoxLayout(self)
        
        self.default_width = self.main_window.line_width_warning_threshold_pixels if self.main_window else 0
        layout.addWidget(QLabel(f"Enter a new width for the selected lines.\nEnter 0 to reset to plugin default ({self.default_width})."))
        
        controls_layout = QHBoxLayout()
        self.width_spinbox = QSpinBox(self)
        self.width_spinbox.setRange(0, 10000)
        self.width_spinbox.setValue(self.default_width)
        controls_layout.addWidget(self.width_spinbox)

        self.default_button = QPushButton("Default", self)
        self.default_button.clicked.connect(self.set_default_width)
        controls_layout.addWidget(self.default_button)
        layout.addLayout(controls_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def get_width(self):
        return self.width_spinbox.value()

    def set_default_width(self):
        self.width_spinbox.setValue(self.default_width)