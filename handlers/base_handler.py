# --- START OF FILE handlers/base_handler.py ---
class BaseHandler:
    def __init__(self, context, data_processor, ui_updater):
        self.ctx = context
        self.data_processor = data_processor
        self.ui_updater = ui_updater

    @property
    def mw(self):
        """Temporary property for backward compatibility during refactoring."""
        return self.ctx

    @property
    def state(self):
        return self.ctx.state

    @property
    def data_store(self):
        return self.ctx.data_store
