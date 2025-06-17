from utils.logging_utils import log_debug

class BaseHandler:
    def __init__(self, main_window, data_processor, ui_updater):
        self.mw = main_window
        self.data_processor = data_processor
        self.ui_updater = ui_updater
        log_debug(f"Handler '{self.__class__.__name__}' initialized.")