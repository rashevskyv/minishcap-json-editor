# -*- coding: utf-8 -*-
"""Handler for original text width analysis tool."""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtWidgets import QAction, QMessageBox

from handlers.base_handler import BaseHandler
from components.original_text_analysis_dialog import OriginalTextAnalysisDialog
from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, DEFAULT_CHAR_WIDTH_FALLBACK


class TextAnalysisHandler(BaseHandler):
    """Builds data for the top longest lines and shows the dialog."""

    def __init__(self, main_window, data_processor, ui_updater) -> None:
        super().__init__(main_window, data_processor, ui_updater)
        self._menu_action: Optional[QAction] = None
        self._dialog: Optional[OriginalTextAnalysisDialog] = None

    def ensure_menu_action(self) -> None:
        tools_menu = getattr(self.mw, 'tools_menu', None)
        if not tools_menu:
            log_debug('TextAnalysisHandler: Tools menu is not available yet.')
            return
        if self._menu_action is not None:
            return

        action = QAction('Original Text Width Analysis', self.mw)
        action.setToolTip(
            'Collect the top 100 widest original lines (in pixels) and show a chart.'
        )
        action.triggered.connect(self.analyze_original_text)
        tools_menu.addAction(action)
        self._menu_action = action

    def analyze_original_text(self) -> None:
        data_source = getattr(self.mw, 'data', None)
        if not isinstance(data_source, list) or not data_source:
            QMessageBox.information(
                self.mw,
                'Original Text Analysis',
                'No original data loaded. Please load a file first.',
            )
            return

        font_maps: Dict[str, dict] = getattr(self.mw, 'all_font_maps', {}) or {}
        if not font_maps:
            QMessageBox.warning(
                self.mw,
                'Original Text Analysis',
                'No font maps loaded for the current plugin.',
            )
            return

        initial_font = getattr(self.mw, 'default_font_file', None)
        if initial_font not in font_maps:
            initial_font = next(iter(font_maps))
        initial_map = font_maps.get(initial_font, {})

        raw_entries: List[Dict[str, object]] = []
        for block_idx, block in enumerate(data_source):
            if not isinstance(block, list):
                continue
            for string_idx, value in enumerate(block):
                text = '' if value is None else str(value)
                if not text:
                    continue
                lines = text.split('\n')
                for line_idx, line in enumerate(lines):
                    raw_entries.append(
                        {
                            'text': line,
                            'block_idx': block_idx,
                            'string_idx': string_idx,
                            'line_idx': line_idx,
                        }
                    )

        if not raw_entries:
            QMessageBox.information(
                self.mw,
                'Original Text Analysis',
                'There is no text to analyse.',
            )
            return

        scored_entries: List[Dict[str, object]] = []
        for entry in raw_entries:
            width = calculate_string_width(
                entry.get('text', ''),
                initial_map,
                DEFAULT_CHAR_WIDTH_FALLBACK,
            )
            new_entry = dict(entry)
            new_entry['width_pixels'] = float(width)
            scored_entries.append(new_entry)

        scored_entries.sort(key=lambda item: item['width_pixels'], reverse=True)
        top_entries = scored_entries[:100]
        top_entry = top_entries[0]
        log_debug(
            "TextAnalysisHandler: prepared %d entries, max width %.2f px"
            % (len(top_entries), float(top_entry['width_pixels']))
        )

        if self._dialog is None:
            self._dialog = OriginalTextAnalysisDialog(self.mw)
            self._dialog.on_entry_activated = self._activate_entry

        self._dialog.show_entries(
            raw_entries,
            font_maps,
            initial_font,
            precomputed_entries=top_entries,
        )

    def _activate_entry(self, entry: Dict[str, object]) -> None:
        block = entry.get('block_idx')
        string = entry.get('string_idx')
        line_idx = entry.get('line_idx')
        if block is None or string is None:
            return

        try:
            block_idx = int(block)
            string_idx = int(string)
        except (TypeError, ValueError):
            return
        line_number = None
        if line_idx is not None:
            try:
                line_number = int(line_idx)
            except (TypeError, ValueError):
                line_number = None

        block_widget = getattr(self.mw, 'block_list_widget', None)
        if block_widget and 0 <= block_idx < block_widget.count():
            block_widget.setCurrentRow(block_idx)

        if hasattr(self.mw, 'list_selection_handler'):
            self.mw.list_selection_handler.string_selected_from_preview(string_idx)
        else:
            self.mw.current_block_idx = block_idx
            self.mw.current_string_idx = string_idx
            self.ui_updater.populate_strings_for_block(block_idx)
            self.mw.ui_updater.update_text_views()

        original_editor = getattr(self.mw, 'original_text_edit', None)
        if original_editor and line_number is not None:
            block_obj = original_editor.document().findBlockByNumber(line_number)
            if block_obj.isValid():
                cursor = original_editor.textCursor()
                cursor.setPosition(block_obj.position())
                original_editor.setTextCursor(cursor)
                original_editor.ensureCursorVisible()
