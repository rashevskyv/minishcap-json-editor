from PyQt5.QtGui import QPaintEvent
from .LNET_paint_helpers import LNETPaintHelpers
from .LNET_paint_event_logic import LNETPaintEventLogic
from .LNET_line_number_area_paint_logic import LNETLineNumberAreaPaintLogic

class LNETPaintHandlers:
    def __init__(self, editor):
        self.editor = editor
        self.helpers = LNETPaintHelpers(self.editor)
        self.paint_event_logic = LNETPaintEventLogic(self.editor, self.helpers)
        self.line_number_area_paint_logic = LNETLineNumberAreaPaintLogic(self.editor, self.helpers)

    def paintEvent(self, event: QPaintEvent):
        self.paint_event_logic.execute_paint_event(event)

    def lineNumberAreaPaintEvent(self, event, painter_device):
        self.line_number_area_paint_logic.execute_paint_event(event, painter_device)