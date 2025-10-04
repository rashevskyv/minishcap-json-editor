# translation/translation_handler.py
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from PyQt5.QtCore import QTimer, Qt, QPoint, QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QApplication
from handlers.base_handler import BaseHandler
from core.glossary_manager import GlossaryEntry
from core.translation.config import build_default_translation_config
from core.translation.providers import (
    ProviderResponse,
    TranslationProviderError,
    create_translation_provider,
    BaseTranslationProvider,
)
from core.translation.session_manager import TranslationSessionManager
from translation.glossary_handler import GlossaryHandler
from translation.ai_prompt_composer import AIPromptComposer
from translation.translation_ui_handler import TranslationUIHandler
from translation.ai_worker import AIWorker
from components.prompt_editor_dialog import PromptEditorDialog
from utils.logging_utils import log_debug
from utils.utils import convert_spaces_to_dots_for_display, convert_dots_to_spaces_from_editor


class TranslationHandler(BaseHandler):
    _MAX_LOG_EXCERPT = 160

    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self._cached_system_prompt: Optional[str] = None
        self._cached_glossary: Optional[str] = None
        self._session_manager = TranslationSessionManager()
        self._session_mode: str = 'auto'
        self._provider_supports_sessions: bool = False
        self._active_provider_key: Optional[str] = None
        self.thread: Optional[QThread] = None
        self.worker: Optional[AIWorker] = None
        self.translation_progress: Dict[int, Dict[str, Union[set, int]]] = {}
        self.pre_translation_state: Dict[int, List[str]] = {}

        self.glossary_handler = GlossaryHandler(self)
        self.prompt_composer = AIPromptComposer(self)
        self.ui_handler = TranslationUIHandler(self)

        self._glossary_manager = self.glossary_handler.glossary_manager

        QTimer.singleShot(0, self.glossary_handler.install_menu_actions)
    
    def initialize_glossary_highlighting(self):
        self.glossary_handler.initialize_glossary_highlighting()

    def show_glossary_dialog(self, initial_term: Optional[str] = None) -> None:
        self.glossary_handler.show_glossary_dialog(initial_term)

    def get_glossary_entry(self, term: str) -> Optional[GlossaryEntry]:
        return self.glossary_handler.glossary_manager.get_entry(term)

    def add_glossary_entry(self, term: str, context: Optional[str] = None) -> None:
        self.glossary_handler.add_glossary_entry(term, context)

    def edit_glossary_entry(self, term: str) -> None:
        self.glossary_handler.edit_glossary_entry(term)

    def append_selection_to_glossary(self):
        preview_edit = self.mw.preview_text_edit
        selection_range = preview_edit._get_selected_line_range()
        if not selection_range:
            QMessageBox.information(self.mw, "Glossary", "No lines selected in the preview.")
            return

        start_line, end_line = selection_range
        
        block_idx = self.mw.current_block_idx
        if block_idx == -1:
            return

        selected_lines = []
        for i in range(start_line, end_line + 1):
            line_text = self.glossary_handler._get_original_string(block_idx, i)
            if line_text is not None:
                selected_lines.append(line_text)
        
        if not selected_lines:
            return

        term_to_add = "\n".join(selected_lines)
        self.glossary_handler.add_glossary_entry(term_to_add)