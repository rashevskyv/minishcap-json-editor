from PyQt5.QtWidgets import (QPlainTextEdit, QMainWindow, QMenu, QApplication, QAction, 
                             QWidget, QHBoxLayout, QPushButton, QWidgetAction) 
from PyQt5.QtGui import (QPainter, QFont, QPaintEvent, QKeyEvent, QKeySequence, QMouseEvent, QIcon, QPixmap, QColor, QTextLine) 
from PyQt5.QtCore import Qt, QRect, QSize, QRectF, pyqtSignal

from .LineNumberArea import LineNumberArea
from .TextHighlightManager import TextHighlightManager
from utils.utils import log_debug
from utils.syntax_highlighter import JsonTagHighlighter
from constants import (
    EDITOR_PLAYER_TAG as EDITOR_PLAYER_TAG_CONST,
    ORIGINAL_PLAYER_TAG as ORIGINAL_PLAYER_TAG_CONST,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
    MONOSPACE_EDITOR_FONT_FAMILY as DEFAULT_EDITOR_FONT_FAMILY_CONST,
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS
)
from .LNET_constants import (
    CURRENT_LINE_COLOR, LINKED_CURSOR_BLOCK_COLOR, LINKED_CURSOR_POS_COLOR,
    PREVIEW_SELECTED_LINE_COLOR, CRITICAL_PROBLEM_LINE_COLOR,
    WARNING_PROBLEM_LINE_COLOR, TAG_INTERACTION_HIGHLIGHT_COLOR,
    SEARCH_MATCH_HIGHLIGHT_COLOR, WIDTH_EXCEEDED_LINE_COLOR, SHORT_LINE_COLOR,
    CHARACTER_LIMIT_LINE_POSITION, CHARACTER_LIMIT_LINE_COLOR, CHARACTER_LIMIT_LINE_STYLE, CHARACTER_LIMIT_LINE_WIDTH,
    WIDTH_THRESHOLD_LINE_COLOR, WIDTH_THRESHOLD_LINE_STYLE, WIDTH_THRESHOLD_LINE_WIDTH
)
from .LNET_mouse_handlers import LNETMouseHandlers
from .LNET_highlight_interface import LNETHighlightInterface
from .LNET_paint_handlers import LNETPaintHandlers


class LineNumberedTextEdit(QPlainTextEdit):
    lineClicked = pyqtSignal(int)
    addTagMappingRequest = pyqtSignal(str, str)
    calculateLineWidthRequest = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget_id = str(id(self))[-6:]
        self.lineNumberArea = LineNumberArea(self)

        self.current_line_color = CURRENT_LINE_COLOR
        self.linked_cursor_block_color = LINKED_CURSOR_BLOCK_COLOR
        self.linked_cursor_pos_color = LINKED_CURSOR_POS_COLOR
        self.preview_selected_line_color = PREVIEW_SELECTED_LINE_COLOR
        self.critical_problem_line_color = CRITICAL_PROBLEM_LINE_COLOR
        self.warning_problem_line_color = WARNING_PROBLEM_LINE_COLOR
        self.tag_interaction_highlight_color = TAG_INTERACTION_HIGHLIGHT_COLOR
        self.search_match_highlight_color = SEARCH_MATCH_HIGHLIGHT_COLOR
        self.width_exceeded_line_color = WIDTH_EXCEEDED_LINE_COLOR 
        self.short_line_color = SHORT_LINE_COLOR 

        self.highlightManager = TextHighlightManager(self)
        log_debug(f"LNET ({self.objectName()}): highlightManager created. Has 'clear_width_exceed_char_highlights': {hasattr(self.highlightManager, 'clear_width_exceed_char_highlights')}")
        self.mouse_handler = LNETMouseHandlers(self) 
        self.highlight_interface = LNETHighlightInterface(self)
        self.paint_handler = LNETPaintHandlers(self)

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

        self.highlighter = JsonTagHighlighter(self.document())
        self.ensurePolished()

        self.character_limit_line_position = CHARACTER_LIMIT_LINE_POSITION
        self.character_limit_line_color = CHARACTER_LIMIT_LINE_COLOR
        self.character_limit_line_style = CHARACTER_LIMIT_LINE_STYLE
        self.character_limit_line_width = CHARACTER_LIMIT_LINE_WIDTH
        
        self.width_threshold_line_color = WIDTH_THRESHOLD_LINE_COLOR
        self.width_threshold_line_style = WIDTH_THRESHOLD_LINE_STYLE
        self.width_threshold_line_width = WIDTH_THRESHOLD_LINE_WIDTH


        self.editor_player_tag = EDITOR_PLAYER_TAG_CONST
        self.original_player_tag = ORIGINAL_PLAYER_TAG_CONST
        self.font_map = {}
        self.GAME_DIALOG_MAX_WIDTH_PIXELS = DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS
        self.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = DEFAULT_LINE_WIDTH_WARNING_THRESHOLD

        if parent and isinstance(parent, QMainWindow):
            self.editor_player_tag = getattr(parent, 'EDITOR_PLAYER_TAG', EDITOR_PLAYER_TAG_CONST)
            self.original_player_tag = getattr(parent, 'ORIGINAL_PLAYER_TAG', ORIGINAL_PLAYER_TAG_CONST)
            self.font_map = getattr(parent, 'font_map', {})
            self.GAME_DIALOG_MAX_WIDTH_PIXELS = getattr(parent, 'GAME_DIALOG_MAX_WIDTH_PIXELS', DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS)
            self.LINE_WIDTH_WARNING_THRESHOLD_PIXELS = getattr(parent, 'LINE_WIDTH_WARNING_THRESHOLD_PIXELS', DEFAULT_LINE_WIDTH_WARNING_THRESHOLD)
            self.character_limit_line_position = getattr(parent, 'editor_char_limit_line_pos', CHARACTER_LIMIT_LINE_POSITION)


        self._update_auxiliary_widths()

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

        custom_actions_added_header = False

        if self.objectName() == "edited_text_edit" and not self.isReadOnly():
            log_debug(f"LNET ({self.objectName()}): Adding actions for editable text.")
            cursor = self.textCursor() 
            if cursor.hasSelection():
                log_debug(f"LNET ({self.objectName()}): Has selection.")
                if not custom_actions_added_header:
                    menu.addSeparator()
                    custom_actions_added_header = True
                
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
            else:
                log_debug(f"LNET ({self.objectName()}): No selection.")

        elif self.objectName() == "preview_text_edit":
            log_debug(f"LNET ({self.objectName()}): Adding actions for preview.")
            if hasattr(main_window, 'data_processor') and hasattr(main_window, 'editor_operation_handler'):
                current_block_idx_data = main_window.current_block_idx
                clicked_cursor_obj = self.cursorForPosition(position_in_widget_coords)
                clicked_data_line_number = clicked_cursor_obj.blockNumber()

                if current_block_idx_data >= 0 and clicked_data_line_number >= 0:
                    if not custom_actions_added_header:
                        menu.addSeparator()
                        custom_actions_added_header = True 
                    
                    preview_actions_actually_added = False

                    if hasattr(main_window, 'paste_block_action'):
                        paste_block_action = menu.addAction("Paste Block Text Here")
                        paste_block_action.triggered.connect(main_window.editor_operation_handler.paste_block_text)
                        paste_block_action.setEnabled(QApplication.clipboard().text() != "")
                        preview_actions_actually_added = True
                    
                    if hasattr(main_window, 'undo_paste_action'):
                        undo_paste_action = menu.addAction("Undo Last Paste Block")
                        undo_paste_action.triggered.connect(main_window.actions.trigger_undo_paste_action)
                        undo_paste_action.setEnabled(main_window.can_undo_paste)
                        preview_actions_actually_added = True
                    
                    if preview_actions_actually_added:
                        menu.addSeparator()

                    revert_line_action = menu.addAction(f"Revert Data Line {clicked_data_line_number + 1} to Original")
                    if hasattr(main_window.editor_operation_handler, 'revert_single_line'):
                        revert_line_action.triggered.connect(lambda checked=False, line=clicked_data_line_number: main_window.editor_operation_handler.revert_single_line(line))
                        is_revertable = False
                        original_text_for_revert_check = main_window.data_processor._get_string_from_source(current_block_idx_data, clicked_data_line_number, main_window.data, "original_for_revert_check")
                        if original_text_for_revert_check is not None:
                            current_text, _ = main_window.data_processor.get_current_string_text(current_block_idx_data, clicked_data_line_number)
                            if current_text != original_text_for_revert_check:
                                is_revertable = True
                        revert_line_action.setEnabled(is_revertable)
                    else:
                        revert_line_action.setEnabled(False)

                    calc_width_action = menu.addAction(f"Calculate Width for Data Line {clicked_data_line_number + 1}")
                    if hasattr(main_window.editor_operation_handler, 'calculate_width_for_data_line_action'):
                        calc_width_action.triggered.connect(lambda checked=False, line_idx=clicked_data_line_number: main_window.editor_operation_handler.calculate_width_for_data_line_action(line_idx))
                    else:
                        calc_width_action.setEnabled(False)

        elif self.objectName() == "original_text_edit":
            log_debug(f"LNET ({self.objectName()}): Adding actions for original.")
            tag_text_curly, _, _ = self.mouse_handler.get_tag_at_cursor(self.cursorForPosition(position_in_widget_coords), r"\{[^}]*\}")
            if tag_text_curly:
                if not custom_actions_added_header:
                    menu.addSeparator()
                
                copy_tag_action = menu.addAction(f"Copy Tag: {tag_text_curly}")
                copy_tag_action.triggered.connect(lambda checked=False, tag=tag_text_curly: self.mouse_handler.copy_tag_to_clipboard(tag))

    def _update_auxiliary_widths(self):
        current_font_metrics = self.fontMetrics()
        self.pixel_width_display_area_width = current_font_metrics.horizontalAdvance("999") + 6
        self.preview_indicator_area_width = (self.lineNumberArea.preview_indicator_width + self.lineNumberArea.preview_indicator_spacing) * 3 + 2
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
        if not self.isReadOnly():
            if event.matches(QKeySequence.Undo):
                if self.document().isUndoAvailable():
                    self.undo()
                    event.accept()
                    return
            elif event.matches(QKeySequence.Redo):
                if self.document().isRedoAvailable():
                    self.redo()
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
        if self.objectName() == "original_text_edit" or self.objectName() == "edited_text_edit":
            additional_width = self.pixel_width_display_area_width
        elif self.objectName() == "preview_text_edit":
            additional_width = self.preview_indicator_area_width
        return base_width + additional_width

    def updateLineNumberAreaWidth(self, _):
        new_width = self.lineNumberAreaWidth()
        self.setViewportMargins(new_width, 0, 0, 0)
        if hasattr(self, 'lineNumberArea'): # Check before accessing
            self.lineNumberArea.updateGeometry()
            self.lineNumberArea.update()

    def updateLineNumberArea(self, rect: QRectF, dy: int):
        if hasattr(self, 'lineNumberArea'): # Check before accessing
            if dy: self.lineNumberArea.scroll(0, dy)
            else: self.lineNumberArea.update(0, 0, self.lineNumberArea.width(), self.lineNumberArea.height())
        if self.isVisible():
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        if hasattr(self, 'lineNumberArea'): # Check before accessing
            self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))
        if self.isVisible():
            self.viewport().update()

    def paintEvent(self, event: QPaintEvent):
        if hasattr(self, 'paint_handler') and self.paint_handler: # Check before calling
            self.paint_handler.paintEvent(event)
        else:
            super().paintEvent(event) # Fallback if paint_handler is not yet initialized

    def super_paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)

    def lineNumberAreaPaintEvent(self, event, painter_device):
        if hasattr(self, 'paint_handler') and self.paint_handler: # Check before calling
            self.paint_handler.lineNumberAreaPaintEvent(event, painter_device)
        # No super call here as this is specific to our LineNumberArea

    def mousePressEvent(self, event: QMouseEvent):
        self.mouse_handler.mousePressEvent(event) 

    def super_mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.mouse_handler.mouseReleaseEvent(event) 

    def super_mouseReleaseEvent(self, event: QMouseEvent):
        super().mouseReleaseEvent(event)

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

    def setPreviewSelectedLineHighlight(self, line_number: int):
        self.highlight_interface.setPreviewSelectedLineHighlight(line_number)

    def clearPreviewSelectedLineHighlight(self):
        self.highlight_interface.clearPreviewSelectedLineHighlight()

    def setLinkedCursorPosition(self, line_number: int, column_number: int):
        self.highlight_interface.setLinkedCursorPosition(line_number, column_number)

    def applyQueuedHighlights(self):
        self.highlight_interface.applyQueuedHighlights()

    def clearAllProblemTypeHighlights(self):
        self.highlight_interface.clearAllProblemTypeHighlights()

    def addProblemLineHighlight(self, line_number: int):
        self.highlight_interface.addProblemLineHighlight(line_number)

    def removeProblemLineHighlight(self, line_number: int) -> bool:
        return self.highlight_interface.removeProblemLineHighlight(line_number)

    def clearProblemLineHighlights(self):
        self.highlight_interface.clearProblemLineHighlights()

    def hasProblemHighlight(self, line_number = None) -> bool:
        return self.highlight_interface.hasProblemHighlight(line_number)