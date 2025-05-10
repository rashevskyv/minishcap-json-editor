from PyQt5.QtWidgets import (QPlainTextEdit, QMainWindow)
from PyQt5.QtGui import (QPainter, QFont, QPaintEvent, QKeyEvent, QKeySequence, QMouseEvent)
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
    SEARCH_MATCH_HIGHLIGHT_COLOR, WIDTH_EXCEEDED_LINE_COLOR,
    CHARACTER_LIMIT_LINE_POSITION, CHARACTER_LIMIT_LINE_COLOR,
    CHARACTER_LIMIT_LINE_WIDTH
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

        self.highlightManager = TextHighlightManager(self)
        self.mouse_handler = LNETMouseHandlers(self)
        self.highlight_interface = LNETHighlightInterface(self)
        self.paint_handler = LNETPaintHandlers(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)

        if not self.isReadOnly():
            self.cursorPositionChanged.connect(self.highlightManager.updateCurrentLineHighlight)
            if not self.isUndoRedoEnabled():
                self.setUndoRedoEnabled(True)
        else:
            self.setContextMenuPolicy(Qt.CustomContextMenu)
            self.customContextMenuRequested.connect(self.mouse_handler.showContextMenu)

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
        self.character_limit_line_width = CHARACTER_LIMIT_LINE_WIDTH

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

        self._update_auxiliary_widths()

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
             self.setContextMenuPolicy(Qt.DefaultContextMenu)
             try: self.customContextMenuRequested.disconnect(self.mouse_handler.showContextMenu)
             except TypeError: pass
             if not self.isUndoRedoEnabled(): self.setUndoRedoEnabled(True)
        else:
             self.setContextMenuPolicy(Qt.CustomContextMenu)
             try: self.customContextMenuRequested.disconnect(self.mouse_handler.showContextMenu)
             except TypeError: pass
             self.customContextMenuRequested.connect(self.mouse_handler.showContextMenu)
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
        self.lineNumberArea.updateGeometry()
        self.lineNumberArea.update()

    def updateLineNumberArea(self, rect: QRectF, dy: int):
        if dy: self.lineNumberArea.scroll(0, dy)
        else: self.lineNumberArea.update(0, 0, self.lineNumberArea.width(), self.lineNumberArea.height())
        if self.isVisible():
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))
        if self.isVisible():
            self.viewport().update()

    def paintEvent(self, event: QPaintEvent):
        self.paint_handler.paintEvent(event)

    def super_paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)

    def lineNumberAreaPaintEvent(self, event, painter_device):
        self.paint_handler.lineNumberAreaPaintEvent(event, painter_device)

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