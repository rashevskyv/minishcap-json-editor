# --- START OF FILE ui/updaters/base_ui_updater.py ---
class BaseUIUpdater:
    def __init__(self, main_window, data_processor):
        self.mw = main_window
        self.data_processor = data_processor