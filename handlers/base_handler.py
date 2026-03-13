# --- START OF FILE handlers/base_handler.py ---
class BaseHandler:
    def __init__(self, main_window, data_processor, ui_updater):
        self.mw = main_window
        self.data_processor = data_processor
        self.ui_updater = ui_updater

    @property
    def state(self):
        return self.mw.state

    @property
    def data_store(self):
        return self.mw.data_store
