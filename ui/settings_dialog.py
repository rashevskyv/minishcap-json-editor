import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox,
    QDialogButtonBox, QWidget, QLabel, QTabWidget,
    QCheckBox, QLineEdit, QColorDialog, QPushButton,
    QHBoxLayout, QFileDialog, QMessageBox
)
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import pyqtSignal
from utils.logging_utils import log_debug
from components.labeled_spinbox import LabeledSpinBox

class ColorPickerButton(QPushButton):
    colorChanged = pyqtSignal(QColor)

    def __init__(self, initial_color=QColor("black"), parent=None):
        super().__init__(parent)
        self._color = QColor(initial_color)
        self.setText(self._color.name())
        self.setToolTip("Click to choose a color")
        self.clicked.connect(self.pick_color)
        self._update_style()

    def color(self) -> QColor:
        return self._color

    def setColor(self, color: QColor):
        if self._color != color:
            self._color = color
            self.setText(self._color.name())
            self._update_style()
            self.colorChanged.emit(self._color)

    def _update_style(self):
        self.setStyleSheet(f"background-color: {self._color.name()}; color: {self._get_contrasting_text_color(self._color)};")

    def _get_contrasting_text_color(self, bg_color: QColor) -> str:
        return "white" if bg_color.lightness() < 128 else "black"

    def pick_color(self):
        dialog = QColorDialog(self._color, self)
        if dialog.exec_():
            self.setColor(dialog.selectedColor())

class SettingsDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        
        self.autofix_checkboxes = {}
        self.detection_checkboxes = {}
        self.plugin_changed_requires_restart = False
        self.theme_changed_requires_restart = False
        self.initial_plugin_name = self.mw.active_game_plugin
        self.initial_theme = getattr(self.mw, 'theme', 'auto')
        self.rules_changed_requires_rescan = False

        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget(self)
        main_layout.addWidget(self.tabs)
        
        self.general_tab = QWidget()
        self.plugin_tab = QWidget()

        self.tabs.addTab(self.general_tab, "Global")
        self.tabs.addTab(self.plugin_tab, "Plugin")
        
        self.setup_general_tab()
        self.setup_plugin_tab()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.load_initial_settings()

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

    def _populate_font_list(self, plugin_dir_name: str):
        self.font_file_combo.clear()
        self.font_file_combo.addItem("None", "")

        if not plugin_dir_name:
            return
            
        fonts_dir = os.path.join("plugins", plugin_dir_name, "fonts")
        if not os.path.isdir(fonts_dir):
            return

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
        self.newline_css_edit = QLineEdit(self)
        layout.addRow("Newline Symbol CSS:", self.newline_css_edit)
        self.tag_css_edit = QLineEdit(self)
        layout.addRow("Tag CSS:", self.tag_css_edit)
        self.bracket_tag_color_picker = ColorPickerButton(parent=self)
        layout.addRow("Bracket Tag Color:", self.bracket_tag_color_picker)

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
        if current_theme == 'dark':
            self.theme_combo.setCurrentIndex(2)
        elif current_theme == 'light':
            self.theme_combo.setCurrentIndex(1)
        else:
            self.theme_combo.setCurrentIndex(0)
            
        current_plugin_dir_name = getattr(self.mw, 'active_game_plugin', 'zelda_mc')
        for display_name, dir_name in self.plugin_map.items():
            if dir_name == current_plugin_dir_name:
                self.plugin_combo.blockSignals(True)
                self.plugin_combo.setCurrentText(display_name)
                self.plugin_combo.blockSignals(False)
                break
        
        self._populate_font_list(current_plugin_dir_name)
        
        self.font_size_spinbox.setValue(self.mw.current_font_size)
        self.show_spaces_checkbox.setChecked(self.mw.show_multiple_spaces_as_dots)
        self.space_dot_color_picker.setColor(QColor(self.mw.space_dot_color_hex))
        self.restore_session_checkbox.setChecked(self.mw.restore_unsaved_on_startup)
        
        self.original_path_edit.setText(self.mw.json_path or "")
        self.edited_path_edit.setText(self.mw.edited_json_path or "")
        
        self.preview_wrap_checkbox.setChecked(self.mw.preview_wrap_lines)
        self.editors_wrap_checkbox.setChecked(self.mw.editors_wrap_lines)
        self.newline_symbol_edit.setText(self.mw.newline_display_symbol)
        self.newline_css_edit.setText(self.mw.newline_css)
        self.tag_css_edit.setText(self.mw.tag_css)
        self.bracket_tag_color_picker.setColor(QColor(self.mw.bracket_tag_color_hex))
        self.game_dialog_width_spinbox.setValue(self.mw.game_dialog_max_width_pixels)
        self.width_warning_spinbox.setValue(self.mw.line_width_warning_threshold_pixels)

        current_font_file = getattr(self.mw, 'default_font_file', "")
        font_index = self.font_file_combo.findData(current_font_file)
        if font_index != -1:
            self.font_file_combo.setCurrentIndex(font_index)
        else:
            self.font_file_combo.setCurrentIndex(0) # "None"

        autofix_settings = getattr(self.mw, 'autofix_enabled', {})
        for problem_id, checkbox in self.autofix_checkboxes.items():
            checkbox.setChecked(autofix_settings.get(problem_id, False))
            
        detection_settings = getattr(self.mw, 'detection_enabled', {})
        for problem_id, checkbox in self.detection_checkboxes.items():
            checkbox.setChecked(detection_settings.get(problem_id, True))
        
        self.rules_changed_requires_rescan = False


    def get_settings(self) -> dict:
        selected_display_name = self.plugin_combo.currentText()
        selected_dir_name = self.plugin_map.get(selected_display_name)
        
        autofix_settings = {}
        for problem_id, checkbox in self.autofix_checkboxes.items():
            autofix_settings[problem_id] = checkbox.isChecked()
            
        detection_settings = {}
        for problem_id, checkbox in self.detection_checkboxes.items():
            detection_settings[problem_id] = checkbox.isChecked()

        return {
            'theme': self.theme_combo.currentText().lower(),
            'active_game_plugin': selected_dir_name,
            'font_size': self.font_size_spinbox.value(),
            'show_multiple_spaces_as_dots': self.show_spaces_checkbox.isChecked(),
            'space_dot_color_hex': self.space_dot_color_picker.color().name(),
            'restore_unsaved_on_startup': self.restore_session_checkbox.isChecked(),
            'original_file_path': self.original_path_edit.text(),
            'edited_file_path': self.edited_path_edit.text(),
            'default_font_file': self.font_file_combo.currentData(),
            'preview_wrap_lines': self.preview_wrap_checkbox.isChecked(),
            'editors_wrap_lines': self.editors_wrap_checkbox.isChecked(),
            'newline_display_symbol': self.newline_symbol_edit.text(),
            'newline_css': self.newline_css_edit.text(),
            'tag_css': self.tag_css_edit.text(),
            'bracket_tag_color_hex': self.bracket_tag_color_picker.color().name(),
            'game_dialog_max_width_pixels': self.game_dialog_width_spinbox.value(),
            'line_width_warning_threshold_pixels': self.width_warning_spinbox.value(),
            'autofix_enabled': autofix_settings,
            'detection_enabled': detection_settings
        }