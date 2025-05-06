from PyQt5.QtWidgets import QMessageBox, QInputDialog, QApplication
from PyQt5.QtCore import Qt
from .data_state_processor import DataStateProcessor
from .ui_updater import UIUpdater
from .utils import log_debug
from .tag_utils import replace_tags_based_on_original

class MainWindowEventHandlers:
    def __init__(self, main_window):
        log_debug("MainWindowEventHandlers initialized.")
        self.mw = main_window
        self.data_processor = DataStateProcessor(self.mw)
        self.ui_updater = UIUpdater(self.mw, self.data_processor)
        self.mw.handlers = self
        log_debug("MainWindowEventHandlers setup complete.")

    # ... existing code ...
    # Замість self._replace_tags_based_on_original використовуйте replace_tags_based_on_original
    # Наприклад:
    # text_with_replaced_tags = replace_tags_based_on_original(segment_to_insert, original_text)
    # ... existing code ...