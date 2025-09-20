# --- START OF FILE ui/updaters/base_ui_updater.py ---
from utils.utils import log_debug

class BaseUIUpdater:
    def __init__(self, main_window, data_processor):
        self.mw = main_window
        self.data_processor = data_processor
        log_debug(f"Updater '{self.__class__.__name__}' initialized.")