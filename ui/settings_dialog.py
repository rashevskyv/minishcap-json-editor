# /home/runner/work/RAG_project/RAG_project/ui/settings_dialog.py
import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox,
    QDialogButtonBox, QWidget, QLabel, QTabWidget,
    QCheckBox, QLineEdit, QColorDialog, QPushButton,
    QHBoxLayout, QFileDialog, QMessageBox, QGroupBox,
    QDoubleSpinBox, QSpinBox, QStackedWidget
)
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import pyqtSignal, Qt
from utils.logging_utils import log_debug
from components.labeled_spinbox import LabeledSpinBox
from components.dictionary_manager_dialog import DictionaryManagerDialog
from core.translation.config import build_default_translation_config, merge_translation_config
import pycountry

class ColorPickerButton(QPushButton):
    colorChanged = pyqtSignal(QColor)

    def __init__(self, initial_color=QColor("black"), parent=None):
        super().__init__(parent)
        self._color = QColor(initial_color)
        try:
            self.setText(self._color.name(QColor.HexArgb))
        except Exception:
            self.setText(self._color.name())
        self.setToolTip("Click to choose a color")
        self.clicked.connect(self.pick_color)
        self._update_style()

    def color(self) -> QColor:
        return self._color

    def setColor(self, color: QColor):
        if self._color != color:
            self._color = color
            try:
                self.setText(self._color.name(QColor.HexArgb))
            except Exception:
                self.setText(self._color.name())
            self._update_style()
            self.colorChanged.emit(self._color)

    def _update_style(self):
        self.setStyleSheet(f"background-color: {self._color.name()}; color: {self._get_contrasting_text_color(self._color)};")

    def _get_contrasting_text_color(self, bg_color: QColor) -> str:
        return "white" if bg_color.lightness() < 128 else "black"

    def pick_color(self):
        try:
            options = QColorDialog.ShowAlphaChannel
        except Exception:
            options = 0
        chosen = QColorDialog.getColor(self._color, self.window(), "Select Color", options)
        if chosen.isValid():
            self.setColor(chosen)

class SettingsDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        
        self.autofix_checkboxes = {}
        self.detection_checkboxes = {}
        self.translation_config_snapshot = build_default_translation_config()
        self.plugin_changed_requires_restart = False
        self.theme_changed_requires_restart = False
        self.initial_plugin_name = self.mw.active_game_plugin
        self.initial_theme = getattr(self.mw, 'theme', 'auto')
        self.rules_changed_requires_rescan = False

        self._glossary_manual_api_keys = {}
        self._glossary_updating_api_key = False

        self.provider_page_map = {
            "disabled": 0,
            "openai_chat": 1,
            "openai_responses": 2,
            "chatmock": 1,
            "ollama_chat": 3,
            "deepl": 4,
            "gemini": 5,
            "perplexity": 6
        }

        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget(self)
        main_layout.addWidget(self.tabs)
        
        self.general_tab = QWidget()
        self.plugin_tab = QWidget()
        self.spelling_tab = QWidget()
        self.ai_translation_tab = QWidget()
        self.ai_glossary_tab = QWidget()

        self.tabs.addTab(self.general_tab, "Global")
        self.tabs.addTab(self.plugin_tab, "Plugin")
        self.tabs.addTab(self.spelling_tab, "Spelling")
        self.tabs.addTab(self.ai_translation_tab, "AI Translation")
        self.tabs.addTab(self.ai_glossary_tab, "AI Glossary")
        
        self.setup_general_tab()
        self.setup_plugin_tab()
        self.setup_spelling_tab()
        self.setup_ai_translation_tab()
        self.setup_ai_glossary_tab()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.load_initial_settings()

    def _get_lang_name(self, code):
        try:
            lang_code_part = code.split('_')[0]
            lang = pycountry.languages.get(alpha_2=lang_code_part)
            return lang.name if lang else code
        except Exception:
            return code

    def _create_path_selector(self, line_edit: QLineEdit):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        
        layout.addWidget(line_edit)
        
        browse_button = QPushButton("...")
        browse_button.setFixedSize(24, 24)
        browse_button.clicked.connect(lambda: self._browse_for_file(line_edit))
        layout.addWidget(browse_button)
        
        return widget

    def _browse_for_file(self, line_edit: QLineEdit):
        start_dir = os.path.dirname(line_edit.text()) if line_edit.text() else ""
        path, _ = QFileDialog.getOpenFileName(self, "Select File", start_dir, "JSON Files (*.json);;All Files (*)")
        if path:
            line_edit.setText(path)

    def setup_general_tab(self):
        layout = QFormLayout(self.general_tab)
        
        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(["Auto", "Light", "Dark"])
        layout.addRow(QLabel("Theme (requires restart):"), self.theme_combo)
        
        self.plugin_combo = QComboBox(self)
        self.populate_plugin_list()
        layout.addRow(QLabel("Active Game Plugin:"), self.plugin_combo)
        
        self.font_size_spinbox = LabeledSpinBox("Application Font Size:", 6, 24, 10, parent=self)
        layout.addRow(self.font_size_spinbox)
        
        self.show_spaces_checkbox = QCheckBox("Show special spaces as dots", self)
        layout.addRow(self.show_spaces_checkbox)
        
        self.space_dot_color_picker = ColorPickerButton(parent=self)
        layout.addRow("Space Dot Color:", self.space_dot_color_picker)
        
        self.restore_session_checkbox = QCheckBox("Restore unsaved session on startup", self)
        self.restore_session_checkbox.setToolTip("If unchecked, any unsaved changes will be discarded on close.")
        layout.addRow(self.restore_session_checkbox)

        self.prompt_editor_checkbox = QCheckBox("Show prompt editor before AI requests", self)
        layout.addRow(self.prompt_editor_checkbox)

        self.plugin_combo.activated.connect(self.on_plugin_changed)
        self.theme_combo.activated.connect(self.on_theme_changed)


    def setup_plugin_tab(self):
        plugin_layout = QVBoxLayout(self.plugin_tab)
        self.plugin_tabs = QTabWidget(self.plugin_tab)
        plugin_layout.addWidget(self.plugin_tabs)
        self.rebuild_plugin_tabs()

    def rebuild_plugin_tabs(self):
        while self.plugin_tabs.count():
            self.plugin_tabs.removeTab(0)

        paths_tab = QWidget()
        display_tab = QWidget()
        rules_tab = QWidget()
        detection_tab = QWidget()
        autofix_tab = QWidget()

        self.plugin_tabs.addTab(paths_tab, "File Paths")
        self.plugin_tabs.addTab(display_tab, "Display")
        self.plugin_tabs.addTab(rules_tab, "Rules")
        self.plugin_tabs.addTab(detection_tab, "Detection")
        self.plugin_tabs.addTab(autofix_tab, "Auto-fix")

        self._setup_paths_subtab(paths_tab)
        self._setup_display_subtab(display_tab)
        self._setup_rules_subtab(rules_tab)
        
        self.detection_checkboxes.clear()
        self.autofix_checkboxes.clear()
        self._setup_detection_subtab(detection_tab)
        self._setup_autofix_subtab(autofix_tab)

    def setup_spelling_tab(self):
        layout = QFormLayout(self.spelling_tab)
        
        self.spellcheck_enabled_checkbox = QCheckBox("Enable spell checking", self)
        layout.addRow(self.spellcheck_enabled_checkbox)
        
        self.spellcheck_language_combo = QComboBox(self)
        layout.addRow("Dictionary Language:", self.spellcheck_language_combo)
        
        manage_button = QPushButton("Manage Dictionaries...", self)
        manage_button.clicked.connect(self._open_dictionary_manager)
        layout.addRow(manage_button)
        
        self.populate_spellchecker_languages()

    def _open_dictionary_manager(self):
        dialog = DictionaryManagerDialog(self)
        dialog.exec_()
        self.populate_spellchecker_languages()

    def populate_spellchecker_languages(self):
        current_lang_data = self.spellcheck_language_combo.currentData()
        self.spellcheck_language_combo.clear()
        if self.mw and self.mw.spellchecker_manager:
            available_dicts = self.mw.spellchecker_manager.scan_local_dictionaries()
            for lang_code in sorted(available_dicts.keys()):
                display_name = self._get_lang_name(lang_code)
                self.spellcheck_language_combo.addItem(f"{display_name} ({lang_code})", lang_code)
        
        if current_lang_data:
            index = self.spellcheck_language_combo.findData(current_lang_data)
            if index != -1:
                self.spellcheck_language_combo.setCurrentIndex(index)

    def _populate_font_list(self, plugin_dir_name: str):
        self.font_file_combo.clear()
        self.font_file_combo.addItem("None", "")

        if not plugin_dir_name:
            return
            
        fonts_dir = os.path.join("plugins", plugin_dir_name, "fonts")
        if os.path.isdir(fonts_dir):
            for filename in sorted(os.listdir(fonts_dir)):
                if filename.lower().endswith(".json"):
                    self.font_file_combo.addItem(filename, filename)

    def _setup_display_subtab(self, tab):
        layout = QFormLayout(tab)
        self.font_file_combo = QComboBox(self)
        layout.addRow("Default Font for Plugin:", self.font_file_combo)
        
        self.preview_wrap_checkbox = QCheckBox("Wrap lines in preview panel", self)
        layout.addRow(self.preview_wrap_checkbox)
        self.editors_wrap_checkbox = QCheckBox("Wrap lines in editor panels", self)
        layout.addRow(self.editors_wrap_checkbox)
        self.newline_symbol_edit = QLineEdit(self)
        layout.addRow("Newline Symbol:", self.newline_symbol_edit)

        newline_style_row = QWidget(self)
        nlr = QHBoxLayout(newline_style_row); nlr.setContentsMargins(0,0,0,0)
        self.newline_color_picker = ColorPickerButton(parent=self)
        self.newline_bold_chk = QCheckBox("Bold", self)
        self.newline_italic_chk = QCheckBox("Italic", self)
        self.newline_underline_chk = QCheckBox("Underline", self)
        nlr.addWidget(self.newline_color_picker)
        nlr.addWidget(self.newline_bold_chk)
        nlr.addWidget(self.newline_italic_chk)
        nlr.addWidget(self.newline_underline_chk)
        nlr.addStretch(1)
        layout.addRow("Newline Symbol Style:", newline_style_row)

        tag_style_row = QWidget(self)
        tsr = QHBoxLayout(tag_style_row); tsr.setContentsMargins(0,0,0,0)
        self.tag_color_picker = ColorPickerButton(parent=self)
        self.tag_bold_chk = QCheckBox("Bold", self)
        self.tag_italic_chk = QCheckBox("Italic", self)
        self.tag_underline_chk = QCheckBox("Underline", self)
        tsr.addWidget(self.tag_color_picker)
        tsr.addWidget(self.tag_bold_chk)
        tsr.addWidget(self.tag_italic_chk)
        tsr.addWidget(self.tag_underline_chk)
        tsr.addStretch(1)
        layout.addRow("Tag Style:", tag_style_row)

    def on_rules_changed(self):
        self.rules_changed_requires_rescan = True
        log_debug("SettingsDialog: Rules changed, marked for rescan.")

    def _setup_rules_subtab(self, tab):
        layout = QFormLayout(tab)
        self.game_dialog_width_spinbox = LabeledSpinBox("Game Dialog Max Width (px):", 100, 10000, 240, parent=self)
        self.game_dialog_width_spinbox.spin_box.valueChanged.connect(self.on_rules_changed)
        layout.addRow(self.game_dialog_width_spinbox)
        
        self.width_warning_spinbox = LabeledSpinBox("Editor Line Width Warning (px):", 100, 10000, 208, parent=self)
        self.width_warning_spinbox.spin_box.valueChanged.connect(self.on_rules_changed)
        layout.addRow(self.width_warning_spinbox)

    def _setup_paths_subtab(self, tab):
        layout = QFormLayout(tab)
        self.original_path_edit = QLineEdit(self)
        self.original_path_edit.setObjectName("PathLineEdit")
        self.edited_path_edit = QLineEdit(self)
        self.edited_path_edit.setObjectName("PathLineEdit")
        layout.addRow("Original File Path:", self._create_path_selector(self.original_path_edit))
        layout.addRow("Changes File Path:", self._create_path_selector(self.edited_path_edit))

    def _populate_checkbox_subtab(self, tab, checkbox_dict, title):
        layout = QFormLayout(tab)
        layout.addRow(QLabel(title))
        
        if not self.mw.current_game_rules:
            return

        problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        if not problem_definitions:
            return

        sorted_problem_ids = sorted(
            problem_definitions.keys(),
            key=lambda pid: problem_definitions[pid].get("priority", 99)
        )

        for problem_id in sorted_problem_ids:
            definition = problem_definitions[problem_id]
            checkbox = QCheckBox(definition.get("name", problem_id), self)
            checkbox.setToolTip(definition.get("description", "No description available."))
            checkbox_dict[problem_id] = checkbox
            checkbox.stateChanged.connect(self.on_rules_changed)
            layout.addRow(checkbox)

    def _setup_detection_subtab(self, tab):
        self._populate_checkbox_subtab(tab, self.detection_checkboxes, "Enable/disable problem detection:")

    def _setup_autofix_subtab(self, tab):
        self._populate_checkbox_subtab(tab, self.autofix_checkboxes, "Enable/disable auto-fix for specific problems:")

    def on_provider_changed(self, index):
        provider_key = self.translation_provider_combo.itemData(index)
        page_index = self.provider_page_map.get(provider_key, 0)
        self.ai_provider_pages.setCurrentIndex(page_index)

    def setup_ai_translation_tab(self):
        layout = QVBoxLayout(self.ai_translation_tab)
        provider_form = QFormLayout()
        self.translation_provider_combo = QComboBox(self)
        self.translation_provider_combo.addItem("Disabled", "disabled")
        self.translation_provider_combo.addItem("OpenAI Chat Completions", "openai_chat")
        self.translation_provider_combo.addItem("OpenAI Responses (gpt-5)", "openai_responses")
        self.translation_provider_combo.addItem("ChatMock (GPT-5 via ChatGPT)", "chatmock")
        self.translation_provider_combo.addItem("Ollama Chat", "ollama_chat")
        self.translation_provider_combo.addItem("DeepL", "deepl")
        self.translation_provider_combo.addItem("Gemini", "gemini")
        self.translation_provider_combo.addItem("Perplexity", "perplexity")
        provider_form.addRow("Active Provider:", self.translation_provider_combo)
        layout.addLayout(provider_form)

        self.ai_provider_pages = QStackedWidget(self)
        layout.addWidget(self.ai_provider_pages)

        disabled_page = QWidget()
        self.ai_provider_pages.addWidget(disabled_page)

        openai_group = QGroupBox("OpenAI Chat (gpt-4o, etc.) / ChatMock", self.ai_translation_tab)
        openai_layout = QFormLayout(openai_group)
        self.openai_api_key_edit = QLineEdit(self)
        self.openai_api_key_edit.setEchoMode(QLineEdit.Password)
        self.openai_api_key_edit.setPlaceholderText("Bearer token")
        openai_layout.addRow("API Key:", self.openai_api_key_edit)
        self.openai_api_key_env_edit = QLineEdit(self)
        self.openai_api_key_env_edit.setPlaceholderText("OPENAI_API_KEY")
        openai_layout.addRow("API Key Env Var:", self.openai_api_key_env_edit)
        self.openai_base_url_edit = QLineEdit(self)
        self.openai_base_url_edit.setPlaceholderText("https://api.openai.com/v1 or http://127.0.0.1:8000")
        openai_layout.addRow("Base URL:", self.openai_base_url_edit)
        self.openai_model_edit = QLineEdit(self)
        self.openai_model_edit.setPlaceholderText("gpt-4o-mini")
        openai_layout.addRow("Model:", self.openai_model_edit)
        self.openai_temperature_spin = QDoubleSpinBox(self)
        self.openai_temperature_spin.setRange(0.0, 2.0); self.openai_temperature_spin.setDecimals(2); self.openai_temperature_spin.setSingleStep(0.05); self.openai_temperature_spin.setValue(0.0)
        openai_layout.addRow("Temperature:", self.openai_temperature_spin)
        self.openai_max_tokens_spin = QSpinBox(self)
        self.openai_max_tokens_spin.setRange(0, 200000); self.openai_max_tokens_spin.setSingleStep(100); self.openai_max_tokens_spin.setSpecialValueText("Provider default"); self.openai_max_tokens_spin.setValue(0)
        openai_layout.addRow("Max Output Tokens:", self.openai_max_tokens_spin)
        self.openai_timeout_spin = QSpinBox(self)
        self.openai_timeout_spin.setRange(1, 600); self.openai_timeout_spin.setSuffix(" s"); self.openai_timeout_spin.setValue(60)
        openai_layout.addRow("Request Timeout:", self.openai_timeout_spin)
        self.ai_provider_pages.addWidget(openai_group)

        openai_responses_group = QGroupBox("OpenAI Responses API (gpt-5)", self.ai_translation_tab)
        openai_responses_layout = QFormLayout(openai_responses_group)
        self.responses_use_chat_key_checkbox = QCheckBox("Use API Key from OpenAI Chat", self)
        openai_responses_layout.addRow(self.responses_use_chat_key_checkbox)
        self.responses_api_key_edit = QLineEdit(self); self.responses_api_key_edit.setEchoMode(QLineEdit.Password); openai_responses_layout.addRow("API Key:", self.responses_api_key_edit)
        self.responses_model_edit = QLineEdit(self); self.responses_model_edit.setText("gpt-5"); openai_responses_layout.addRow("Model:", self.responses_model_edit)
        self.responses_effort_combo = QComboBox(self); self.responses_effort_combo.addItems(["low", "medium", "high"]); openai_responses_layout.addRow("Reasoning Effort:", self.responses_effort_combo)
        self.responses_verbosity_combo = QComboBox(self); self.responses_verbosity_combo.addItems(["low", "medium", "high"]); openai_responses_layout.addRow("Text Verbosity:", self.responses_verbosity_combo)
        self.responses_timeout_spin = QSpinBox(self); self.responses_timeout_spin.setRange(1, 600); self.responses_timeout_spin.setSuffix(" s"); self.responses_timeout_spin.setValue(120); openai_responses_layout.addRow("Request Timeout:", self.responses_timeout_spin)
        self.ai_provider_pages.addWidget(openai_responses_group)
        self.responses_use_chat_key_checkbox.stateChanged.connect(
            lambda state: self.responses_api_key_edit.setDisabled(state == Qt.Checked)
        )
        self.responses_use_chat_key_checkbox.stateChanged.connect(self._refresh_glossary_api_key_from_translation)

        ollama_group = QGroupBox("Ollama Chat API", self.ai_translation_tab)
        ollama_layout = QFormLayout(ollama_group)
        self.ollama_base_url_edit = QLineEdit(self); self.ollama_base_url_edit.setPlaceholderText("http://localhost:11434"); ollama_layout.addRow("Base URL:", self.ollama_base_url_edit)
        self.ollama_model_edit = QLineEdit(self); self.ollama_model_edit.setPlaceholderText("llama3"); ollama_layout.addRow("Model:", self.ollama_model_edit)
        self.ollama_temperature_spin = QDoubleSpinBox(self); self.ollama_temperature_spin.setRange(0.0, 2.0); self.ollama_temperature_spin.setDecimals(2); self.ollama_temperature_spin.setSingleStep(0.05); self.ollama_temperature_spin.setValue(0.0); ollama_layout.addRow("Temperature:", self.ollama_temperature_spin)
        self.ollama_timeout_spin = QSpinBox(self); self.ollama_timeout_spin.setRange(1, 600); self.ollama_timeout_spin.setSuffix(" s"); self.ollama_timeout_spin.setValue(120); ollama_layout.addRow("Request Timeout:", self.ollama_timeout_spin)
        self.ollama_keep_alive_edit = QLineEdit(self); self.ollama_keep_alive_edit.setPlaceholderText("e.g. 5m or leave blank"); ollama_layout.addRow("Keep Alive:", self.ollama_keep_alive_edit)
        self.ai_provider_pages.addWidget(ollama_group)

        deepl_group = QGroupBox("DeepL API", self.ai_translation_tab)
        deepl_layout = QFormLayout(deepl_group)
        self.deepl_api_key_edit = QLineEdit(self); self.deepl_api_key_edit.setEchoMode(QLineEdit.Password); self.deepl_api_key_edit.setPlaceholderText("DeepL API Key"); deepl_layout.addRow("API Key:", self.deepl_api_key_edit)
        self.deepl_server_url_edit = QLineEdit(self); self.deepl_server_url_edit.setPlaceholderText("e.g. https://api.deepl.com (Pro)"); deepl_layout.addRow("Server URL (Pro):", self.deepl_server_url_edit)
        self.ai_provider_pages.addWidget(deepl_group)

        gemini_group = QGroupBox("Google Gemini API", self.ai_translation_tab)
        gemini_layout = QFormLayout(gemini_group)
        self.gemini_base_url_edit = QLineEdit(self)
        self.gemini_base_url_edit.setPlaceholderText("Leave empty for native API")
        gemini_layout.addRow("Base URL (optional):", self.gemini_base_url_edit)
        self.gemini_api_key_edit = QLineEdit(self); self.gemini_api_key_edit.setEchoMode(QLineEdit.Password); self.gemini_api_key_edit.setPlaceholderText("Gemini API Key"); gemini_layout.addRow("API Key:", self.gemini_api_key_edit)
        self.gemini_model_edit = QLineEdit(self); self.gemini_model_edit.setPlaceholderText("gemini-1.5-flash-latest"); gemini_layout.addRow("Model:", self.gemini_model_edit)
        self.ai_provider_pages.addWidget(gemini_group)

        perplexity_group = QGroupBox("Perplexity API", self.ai_translation_tab)
        perplexity_layout = QFormLayout(perplexity_group)
        self.perplexity_api_key_edit = QLineEdit(self)
        self.perplexity_api_key_edit.setEchoMode(QLineEdit.Password)
        self.perplexity_api_key_edit.setPlaceholderText("Bearer token")
        perplexity_layout.addRow("API Key:", self.perplexity_api_key_edit)
        self.perplexity_base_url_edit = QLineEdit(self)
        self.perplexity_base_url_edit.setPlaceholderText("https://api.perplexity.ai")
        perplexity_layout.addRow("Base URL:", self.perplexity_base_url_edit)
        self.perplexity_model_edit = QLineEdit(self)
        self.perplexity_model_edit.setPlaceholderText("sonar-medium-8x7b-chat")
        perplexity_layout.addRow("Model:", self.perplexity_model_edit)
        self.perplexity_temperature_spin = QDoubleSpinBox(self)
        self.perplexity_temperature_spin.setRange(0.0, 2.0); self.perplexity_temperature_spin.setDecimals(2); self.perplexity_temperature_spin.setSingleStep(0.05); self.perplexity_temperature_spin.setValue(0.0)
        perplexity_layout.addRow("Temperature:", self.perplexity_temperature_spin)
        self.perplexity_max_tokens_spin = QSpinBox(self)
        self.perplexity_max_tokens_spin.setRange(0, 200000); self.perplexity_max_tokens_spin.setSingleStep(100); self.perplexity_max_tokens_spin.setSpecialValueText("Provider default"); self.perplexity_max_tokens_spin.setValue(0)
        perplexity_layout.addRow("Max Output Tokens:", self.perplexity_max_tokens_spin)
        self.perplexity_timeout_spin = QSpinBox(self)
        self.perplexity_timeout_spin.setRange(1, 600); self.perplexity_timeout_spin.setSuffix(" s"); self.perplexity_timeout_spin.setValue(60)
        perplexity_layout.addRow("Request Timeout:", self.perplexity_timeout_spin)
        self.ai_provider_pages.addWidget(perplexity_group)

        self.translation_provider_combo.currentIndexChanged.connect(self.on_provider_changed)
        self.openai_api_key_edit.textChanged.connect(self._refresh_glossary_api_key_from_translation)
        self.openai_api_key_env_edit.textChanged.connect(self._refresh_glossary_api_key_from_translation)
        self.responses_api_key_edit.textChanged.connect(self._refresh_glossary_api_key_from_translation)
        self.gemini_api_key_edit.textChanged.connect(self._refresh_glossary_api_key_from_translation)
        layout.addStretch(1)

    def setup_ai_glossary_tab(self):
        layout = QFormLayout(self.ai_glossary_tab)

        self.glossary_provider_combo = QComboBox(self)
        # For now, let's keep it simple. We can expand this later.
        self.glossary_provider_combo.addItems(["OpenAI", "Ollama", "Gemini"])
        layout.addRow("Provider:", self.glossary_provider_combo)

        self.glossary_api_key_edit = QLineEdit(self)
        self.glossary_api_key_edit.setEchoMode(QLineEdit.Password)
        self.glossary_api_key_edit.setPlaceholderText("Provider API Key")
        layout.addRow("API Key:", self.glossary_api_key_edit)

        self.glossary_use_translation_key_checkbox = QCheckBox("Use API key from AI Translation", self)
        layout.addRow("", self.glossary_use_translation_key_checkbox)

        self.glossary_model_edit = QLineEdit(self)
        self.glossary_model_edit.setPlaceholderText("e.g., gpt-4o-mini")
        layout.addRow("Model:", self.glossary_model_edit)

        self.glossary_chunk_size_spin = QSpinBox(self)
        self.glossary_chunk_size_spin.setRange(1000, 32000)
        self.glossary_chunk_size_spin.setSingleStep(100)
        self.glossary_chunk_size_spin.setSuffix(" chars")
        layout.addRow("Text Chunk Size:", self.glossary_chunk_size_spin)

        self.glossary_use_translation_key_checkbox.stateChanged.connect(self._on_glossary_use_translation_key_changed)
        self.glossary_provider_combo.currentIndexChanged.connect(self._on_glossary_provider_changed)
        self.glossary_api_key_edit.textChanged.connect(self._on_glossary_api_key_changed)


    def _set_glossary_api_key_text(self, value: str) -> None:
        self._glossary_updating_api_key = True
        try:
            self.glossary_api_key_edit.setText(value or "")
        finally:
            self._glossary_updating_api_key = False

    def _get_translation_credentials_for_glossary(self, provider_name: str) -> dict:
        providers_cfg = {}
        if isinstance(self.translation_config_snapshot, dict):
            providers_cfg = self.translation_config_snapshot.get('providers', {}) or {}

        if provider_name == 'OpenAI':
            api_key = self.openai_api_key_edit.text().strip()
            if not api_key and not self.responses_use_chat_key_checkbox.isChecked():
                api_key = self.responses_api_key_edit.text().strip()
                if not api_key:
                    api_key = providers_cfg.get('openai_responses', {}).get('api_key', '')
            if not api_key:
                api_key = providers_cfg.get('openai_chat', {}).get('api_key', '')

            api_key_env = self.openai_api_key_env_edit.text().strip()
            if not api_key_env:
                api_key_env = providers_cfg.get('openai_chat', {}).get('api_key_env', '')

            return {
                'api_key': api_key,
                'api_key_env': api_key_env
            }

        if provider_name == 'Gemini':
            api_key = self.gemini_api_key_edit.text().strip()
            api_key_env = ''
            gemini_cfg = providers_cfg.get('gemini', {}) or {}
            if not api_key:
                api_key = gemini_cfg.get('api_key', '')
            api_key_env = gemini_cfg.get('api_key_env', '')
            return {
                'api_key': api_key,
                'api_key_env': api_key_env
            }

        return {}

    def _update_glossary_api_key_controls(self, provider_name: str = None) -> None:
        provider = provider_name or self.glossary_provider_combo.currentText()
        use_translation = self.glossary_use_translation_key_checkbox.isChecked()
        self.glossary_api_key_edit.setEnabled(not use_translation)

        if use_translation:
            credentials = self._get_translation_credentials_for_glossary(provider)
            self._set_glossary_api_key_text(credentials.get('api_key') or '')
        else:
            manual_value = self._glossary_manual_api_keys.get(provider, '')
            self._set_glossary_api_key_text(manual_value)

    def _refresh_glossary_api_key_from_translation(self, *args):
        if not self.glossary_use_translation_key_checkbox.isChecked():
            return
        provider = self.glossary_provider_combo.currentText()
        if provider in ("OpenAI", "Gemini"):
            self._update_glossary_api_key_controls(provider)

    def _on_glossary_use_translation_key_changed(self, state):
        provider = self.glossary_provider_combo.currentText()
        if state == Qt.Checked:
            self._glossary_manual_api_keys[provider] = self.glossary_api_key_edit.text().strip()
        self._update_glossary_api_key_controls(provider)

    def _on_glossary_provider_changed(self, index):
        provider = self.glossary_provider_combo.itemText(index)
        if not provider:
            provider = self.glossary_provider_combo.currentText()
        self._update_glossary_api_key_controls(provider)

    def _on_glossary_api_key_changed(self, text):
        if self._glossary_updating_api_key:
            return
        if self.glossary_use_translation_key_checkbox.isChecked():
            return
        provider = self.glossary_provider_combo.currentText()
        self._glossary_manual_api_keys[provider] = text.strip()


    def find_plugins(self):
        plugins_dir = "plugins"
        found_plugins = {}
        if not os.path.isdir(plugins_dir):
            return found_plugins
        
        for item in os.listdir(plugins_dir):
            item_path = os.path.join(plugins_dir, item)
            config_path = os.path.join(item_path, "config.json")
            if os.path.isdir(item_path) and os.path.exists(config_path) and item != "import_plugins":
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    display_name = config_data.get("display_name", item)
                    found_plugins[display_name] = item
                except Exception as e:
                    log_debug(f"Could not read config for plugin '{item}': {e}")
                    found_plugins[item] = item
        return found_plugins

    def populate_plugin_list(self):
        self.plugin_map = self.find_plugins()
        self.plugin_combo.addItems(self.plugin_map.keys())

    def on_theme_changed(self, index):
        log_debug("SettingsDialog: Theme changed in dropdown.")
        selected_theme = self.theme_combo.currentText().lower()
        if selected_theme != self.initial_theme:
            self.theme_changed_requires_restart = True
            QMessageBox.information(self, "Theme Change", "A restart is required to apply the new theme.", QMessageBox.Ok)
        else:
            self.theme_changed_requires_restart = False

    def on_plugin_changed(self, index):
        log_debug("SettingsDialog: Plugin changed in dropdown.")
        selected_dir_name = self.plugin_map.get(self.plugin_combo.currentText())
        
        self._populate_font_list(selected_dir_name)
        
        if selected_dir_name == self.initial_plugin_name:
            self.plugin_changed_requires_restart = False
            return

        self.plugin_changed_requires_restart = True
        QMessageBox.information(self, "Plugin Change", "A restart is required to switch the game plugin.", QMessageBox.Ok)


    def load_initial_settings(self):
        current_theme = getattr(self.mw, 'theme', 'auto')
        if current_theme == 'dark': self.theme_combo.setCurrentIndex(2)
        elif current_theme == 'light': self.theme_combo.setCurrentIndex(1)
        else: self.theme_combo.setCurrentIndex(0)
            
        current_plugin_dir_name = getattr(self.mw, 'active_game_plugin', 'zelda_mc')
        for display_name, dir_name in self.plugin_map.items():
            if dir_name == current_plugin_dir_name:
                self.plugin_combo.blockSignals(True); self.plugin_combo.setCurrentText(display_name); self.plugin_combo.blockSignals(False)
                break
        
        self._populate_font_list(current_plugin_dir_name)
        
        self.font_size_spinbox.setValue(self.mw.current_font_size)
        self.show_spaces_checkbox.setChecked(self.mw.show_multiple_spaces_as_dots)
        self.space_dot_color_picker.setColor(QColor(self.mw.space_dot_color_hex))
        self.restore_session_checkbox.setChecked(self.mw.restore_unsaved_on_startup)
        self.prompt_editor_checkbox.setChecked(getattr(self.mw, 'prompt_editor_enabled', True))
        
        self.original_path_edit.setText(self.mw.json_path or ""); self.edited_path_edit.setText(self.mw.edited_json_path or "")
        
        self.preview_wrap_checkbox.setChecked(self.mw.preview_wrap_lines); self.editors_wrap_checkbox.setChecked(self.mw.editors_wrap_lines)
        self.newline_symbol_edit.setText(self.mw.newline_display_symbol)
        
        nl_color = getattr(self.mw, 'newline_color_rgba', '#A020F0'); self.newline_color_picker.setColor(QColor(nl_color))
        self.newline_bold_chk.setChecked(getattr(self.mw, 'newline_bold', True)); self.newline_italic_chk.setChecked(getattr(self.mw, 'newline_italic', False)); self.newline_underline_chk.setChecked(getattr(self.mw, 'newline_underline', False))
        
        tag_color = getattr(self.mw, 'tag_color_rgba', getattr(self.mw, 'bracket_tag_color_hex', '#FF8C00')); self.tag_color_picker.setColor(QColor(tag_color))
        self.tag_bold_chk.setChecked(getattr(self.mw, 'tag_bold', True)); self.tag_italic_chk.setChecked(getattr(self.mw, 'tag_italic', False)); self.tag_underline_chk.setChecked(getattr(self.mw, 'tag_underline', False))
        
        self.game_dialog_width_spinbox.setValue(self.mw.game_dialog_max_width_pixels); self.width_warning_spinbox.setValue(self.mw.line_width_warning_threshold_pixels)

        current_font_file = getattr(self.mw, 'default_font_file', ""); font_index = self.font_file_combo.findData(current_font_file)
        if font_index != -1: self.font_file_combo.setCurrentIndex(font_index)
        else: self.font_file_combo.setCurrentIndex(0)

        autofix_settings = getattr(self.mw, 'autofix_enabled', {}); detection_settings = getattr(self.mw, 'detection_enabled', {})
        for problem_id, checkbox in self.autofix_checkboxes.items(): checkbox.setChecked(autofix_settings.get(problem_id, False))
        for problem_id, checkbox in self.detection_checkboxes.items(): checkbox.setChecked(detection_settings.get(problem_id, True))

        self.translation_config_snapshot = merge_translation_config(build_default_translation_config(), getattr(self.mw, 'translation_config', {}))
        provider_key = self.translation_config_snapshot.get('provider', 'disabled')
        provider_index = self.translation_provider_combo.findData(provider_key)
        if provider_index != -1: self.translation_provider_combo.setCurrentIndex(provider_index)
        else: self.translation_provider_combo.setCurrentIndex(0)

        providers_cfg = self.translation_config_snapshot.get('providers', {})
        
        openai_cfg = providers_cfg.get('openai_chat', {}); chatmock_cfg = providers_cfg.get('chatmock', {})
        active_openai_cfg = openai_cfg if provider_key != 'chatmock' else chatmock_cfg
        self.openai_api_key_edit.setText(active_openai_cfg.get('api_key', '')); self.openai_api_key_env_edit.setText(active_openai_cfg.get('api_key_env', ''))
        self.openai_base_url_edit.setText(active_openai_cfg.get('base_url', '')); self.openai_model_edit.setText(active_openai_cfg.get('model', ''))
        try: self.openai_temperature_spin.setValue(float(active_openai_cfg.get('temperature', 0.0)))
        except (TypeError, ValueError): self.openai_temperature_spin.setValue(0.0)
        try: self.openai_max_tokens_spin.setValue(int(active_openai_cfg.get('max_output_tokens', 0) or 0))
        except (TypeError, ValueError): self.openai_max_tokens_spin.setValue(0)
        try: self.openai_timeout_spin.setValue(int(active_openai_cfg.get('timeout', 60) or 60))
        except (TypeError, ValueError): self.openai_timeout_spin.setValue(60)

        responses_cfg = providers_cfg.get('openai_responses', {})
        self.responses_api_key_edit.setText(responses_cfg.get('api_key', ''))
        self.responses_model_edit.setText(responses_cfg.get('model', 'gpt-5'))
        self.responses_effort_combo.setCurrentText(responses_cfg.get('reasoning_effort', 'low'))
        self.responses_verbosity_combo.setCurrentText(responses_cfg.get('text_verbosity', 'low'))
        self.responses_timeout_spin.setValue(responses_cfg.get('timeout', 120))
        use_chat_key = responses_cfg.get('use_chat_key', False)
        self.responses_use_chat_key_checkbox.setChecked(use_chat_key)
        self.responses_api_key_edit.setDisabled(use_chat_key)


        ollama_cfg = providers_cfg.get('ollama_chat', {})
        self.ollama_base_url_edit.setText(ollama_cfg.get('base_url', '')); self.ollama_model_edit.setText(ollama_cfg.get('model', ''))
        try: self.ollama_temperature_spin.setValue(float(ollama_cfg.get('temperature', 0.0)))
        except (TypeError, ValueError): self.ollama_temperature_spin.setValue(0.0)
        try: self.ollama_timeout_spin.setValue(int(ollama_cfg.get('timeout', 120) or 120))
        except (TypeError, ValueError): self.ollama_timeout_spin.setValue(120)
        self.ollama_keep_alive_edit.setText(ollama_cfg.get('keep_alive', ''))

        deepl_cfg = providers_cfg.get('deepl', {}); self.deepl_api_key_edit.setText(deepl_cfg.get('api_key', '')); self.deepl_server_url_edit.setText(deepl_cfg.get('server_url', ''))
        gemini_cfg = providers_cfg.get('gemini', {}); self.gemini_api_key_edit.setText(gemini_cfg.get('api_key', '')); self.gemini_model_edit.setText(gemini_cfg.get('model', '')); self.gemini_base_url_edit.setText(gemini_cfg.get('base_url', ''))

        perplexity_cfg = providers_cfg.get('perplexity', {})
        self.perplexity_api_key_edit.setText(perplexity_cfg.get('api_key', ''))
        self.perplexity_base_url_edit.setText(perplexity_cfg.get('base_url', ''))
        self.perplexity_model_edit.setText(perplexity_cfg.get('model', ''))
        try: self.perplexity_temperature_spin.setValue(float(perplexity_cfg.get('temperature', 0.0)))
        except (TypeError, ValueError): self.perplexity_temperature_spin.setValue(0.0)
        try: self.perplexity_max_tokens_spin.setValue(int(perplexity_cfg.get('max_output_tokens', 0) or 0))
        except (TypeError, ValueError): self.perplexity_max_tokens_spin.setValue(0)
        try: self.perplexity_timeout_spin.setValue(int(perplexity_cfg.get('timeout', 60) or 60))
        except (TypeError, ValueError): self.perplexity_timeout_spin.setValue(60)

        # Load AI Glossary settings
        glossary_ai_cfg = getattr(self.mw, 'glossary_ai', {})
        glossary_provider = glossary_ai_cfg.get('provider', 'OpenAI')
        provider_index = self.glossary_provider_combo.findText(glossary_provider)
        if provider_index >= 0:
            self.glossary_provider_combo.blockSignals(True)
            self.glossary_provider_combo.setCurrentIndex(provider_index)
            self.glossary_provider_combo.blockSignals(False)
        else:
            self.glossary_provider_combo.setCurrentText(glossary_provider)

        manual_key = glossary_ai_cfg.get('api_key', '')
        self._glossary_manual_api_keys[glossary_provider] = manual_key

        use_translation_key = glossary_ai_cfg.get('use_translation_api_key', False)
        self.glossary_use_translation_key_checkbox.blockSignals(True)
        self.glossary_use_translation_key_checkbox.setChecked(use_translation_key)
        self.glossary_use_translation_key_checkbox.blockSignals(False)

        self._update_glossary_api_key_controls(glossary_provider)

        self.glossary_model_edit.setText(glossary_ai_cfg.get('model', 'gpt-4o'))
        self.glossary_chunk_size_spin.setValue(glossary_ai_cfg.get('chunk_size', 8000))
        
        # Load Spellchecker settings
        self.spellcheck_enabled_checkbox.setChecked(getattr(self.mw, 'spellchecker_enabled', False))
        current_lang = getattr(self.mw, 'spellchecker_language', 'uk')
        lang_index = self.spellcheck_language_combo.findData(current_lang)
        if lang_index != -1:
            self.spellcheck_language_combo.setCurrentIndex(lang_index)

        self.on_provider_changed(self.translation_provider_combo.currentIndex())
        self.rules_changed_requires_rescan = False


    def get_settings(self) -> dict:
        selected_display_name = self.plugin_combo.currentText(); selected_dir_name = self.plugin_map.get(selected_display_name)
        
        autofix_settings = {pid: cb.isChecked() for pid, cb in self.autofix_checkboxes.items()}
        detection_settings = {pid: cb.isChecked() for pid, cb in self.detection_checkboxes.items()}

        translation_config_to_save = merge_translation_config(build_default_translation_config(), self.translation_config_snapshot)
        provider_key = self.translation_provider_combo.currentData() or 'disabled'
        translation_config_to_save['provider'] = provider_key
        providers_cfg = translation_config_to_save.setdefault('providers', {})
        
        openai_cfg = providers_cfg.setdefault('openai_chat', {}); chatmock_cfg = providers_cfg.setdefault('chatmock', {})
        openai_values = {
            'api_key': self.openai_api_key_edit.text().strip(), 'api_key_env': self.openai_api_key_env_edit.text().strip(),
            'base_url': self.openai_base_url_edit.text().strip(), 'model': self.openai_model_edit.text().strip(),
            'temperature': float(self.openai_temperature_spin.value()), 'max_output_tokens': int(self.openai_max_tokens_spin.value()),
            'timeout': int(self.openai_timeout_spin.value())
        }
        if provider_key == 'chatmock': chatmock_cfg.update(openai_values)
        else: openai_cfg.update(openai_values)
        
        responses_cfg = providers_cfg.setdefault('openai_responses', {})
        use_chat_key = self.responses_use_chat_key_checkbox.isChecked()
        api_key_to_save = self.openai_api_key_edit.text().strip() if use_chat_key else self.responses_api_key_edit.text().strip()
        responses_cfg.update({
            'api_key': api_key_to_save, 'model': self.responses_model_edit.text().strip(),
            'reasoning_effort': self.responses_effort_combo.currentText(), 'text_verbosity': self.responses_verbosity_combo.currentText(),
            'timeout': self.responses_timeout_spin.value(), 'use_chat_key': use_chat_key
        })

        ollama_cfg = providers_cfg.setdefault('ollama_chat', {}); ollama_cfg.update({
            'base_url': self.ollama_base_url_edit.text().strip(), 'model': self.ollama_model_edit.text().strip(),
            'temperature': float(self.ollama_temperature_spin.value()), 'timeout': int(self.ollama_timeout_spin.value()),
            'keep_alive': self.ollama_keep_alive_edit.text().strip()
        })

        deepl_cfg = providers_cfg.setdefault('deepl', {}); deepl_cfg.update({'api_key': self.deepl_api_key_edit.text().strip(), 'server_url': self.deepl_server_url_edit.text().strip()})
        gemini_cfg = providers_cfg.setdefault('gemini', {}); gemini_cfg.update({'api_key': self.gemini_api_key_edit.text().strip(), 'model': self.gemini_model_edit.text().strip(), 'base_url': self.gemini_base_url_edit.text().strip()})
        
        perplexity_cfg = providers_cfg.setdefault('perplexity', {}); perplexity_cfg.update({
            'api_key': self.perplexity_api_key_edit.text().strip(),
            'base_url': self.perplexity_base_url_edit.text().strip(),
            'model': self.perplexity_model_edit.text().strip(),
            'temperature': float(self.perplexity_temperature_spin.value()),
            'max_output_tokens': int(self.perplexity_max_tokens_spin.value()),
            'timeout': int(self.perplexity_timeout_spin.value())
        })

        self.translation_config_snapshot = translation_config_to_save

        glossary_provider = self.glossary_provider_combo.currentText()
        use_translation_key = self.glossary_use_translation_key_checkbox.isChecked()
        manual_key = self._glossary_manual_api_keys.get(glossary_provider, '')
        if not use_translation_key:
            manual_key = self.glossary_api_key_edit.text().strip()

        glossary_ai_settings = {
            'provider': glossary_provider,
            'api_key': manual_key or '',
            'use_translation_api_key': use_translation_key,
            'model': self.glossary_model_edit.text().strip(),
            'chunk_size': self.glossary_chunk_size_spin.value()
        }

        return {
            'theme': self.theme_combo.currentText().lower(), 'active_game_plugin': selected_dir_name,
            'font_size': self.font_size_spinbox.value(), 'show_multiple_spaces_as_dots': self.show_spaces_checkbox.isChecked(),
            'space_dot_color_hex': self.space_dot_color_picker.color().name(), 'restore_unsaved_on_startup': self.restore_session_checkbox.isChecked(),
            'prompt_editor_enabled': self.prompt_editor_checkbox.isChecked(),
            'original_file_path': self.original_path_edit.text(), 'edited_file_path': self.edited_path_edit.text(),
            'default_font_file': self.font_file_combo.currentData(), 'preview_wrap_lines': self.preview_wrap_checkbox.isChecked(),
            'editors_wrap_lines': self.editors_wrap_checkbox.isChecked(), 'newline_display_symbol': self.newline_symbol_edit.text(),
            'newline_color_rgba': self.newline_color_picker.color().name(QColor.HexArgb) if hasattr(QColor, 'HexArgb') else self.newline_color_picker.color().name(),
            'newline_bold': self.newline_bold_chk.isChecked(), 'newline_italic': self.newline_italic_chk.isChecked(), 'newline_underline': self.newline_underline_chk.isChecked(),
            'tag_color_rgba': self.tag_color_picker.color().name(QColor.HexArgb) if hasattr(QColor, 'HexArgb') else self.tag_color_picker.color().name(),
            'tag_bold': self.tag_bold_chk.isChecked(), 'tag_italic': self.tag_italic_chk.isChecked(), 'tag_underline': self.tag_underline_chk.isChecked(),
            'game_dialog_max_width_pixels': self.game_dialog_width_spinbox.value(), 'line_width_warning_threshold_pixels': self.width_warning_spinbox.value(),
            'autofix_enabled': autofix_settings, 'translation_config': translation_config_to_save, 'detection_enabled': detection_settings,
            'glossary_ai': glossary_ai_settings,
            'spellchecker_enabled': self.spellcheck_enabled_checkbox.isChecked(),
            'spellchecker_language': self.spellcheck_language_combo.currentData(),
        }