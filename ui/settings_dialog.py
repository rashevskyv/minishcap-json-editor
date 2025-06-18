import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox,
    QDialogButtonBox, QWidget, QLabel, QTabWidget,
    QCheckBox, QLineEdit, QColorDialog, QPushButton,
    QHBoxLayout, QFileDialog
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

        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget(self)
        main_layout.addWidget(self.tabs)
        
        self.general_tab = QWidget()
        self.display_tab = QWidget()
        self.rules_tab = QWidget()

        self.tabs.addTab(self.general_tab, "Global")
        self.tabs.addTab(self.display_tab, "Plugin: Display")
        self.tabs.addTab(self.rules_tab, "Plugin: Rules")

        self.setup_general_tab()
        self.setup_display_tab()
        self.setup_rules_tab()

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
        
        self.plugin_combo = QComboBox(self)
        self.populate_plugin_list()
        layout.addRow(QLabel("Active Game Plugin:"), self.plugin_combo)
        
        self.font_size_spinbox = LabeledSpinBox("Application Font Size:", 6, 24, 10, parent=self)
        layout.addRow(self.font_size_spinbox)

        self.original_path_edit = QLineEdit(self)
        self.edited_path_edit = QLineEdit(self)
        
        layout.addRow("Original File Path:", self._create_path_selector(self.original_path_edit))
        layout.addRow("Changes File Path:", self._create_path_selector(self.edited_path_edit))

        self.plugin_combo.activated.connect(self.on_plugin_changed)

    def setup_display_tab(self):
        layout = QFormLayout(self.display_tab)
        layout.addRow(QLabel("These settings are specific to the active plugin."))
        
        self.preview_wrap_checkbox = QCheckBox("Wrap lines in preview panel", self)
        layout.addRow(self.preview_wrap_checkbox)
        
        self.editors_wrap_checkbox = QCheckBox("Wrap lines in editor panels", self)
        layout.addRow(self.editors_wrap_checkbox)

        self.show_spaces_checkbox = QCheckBox("Show multiple spaces as dots", self)
        layout.addRow(self.show_spaces_checkbox)

        self.newline_symbol_edit = QLineEdit(self)
        layout.addRow("Newline Symbol:", self.newline_symbol_edit)

        self.newline_css_edit = QLineEdit(self)
        layout.addRow("Newline Symbol CSS:", self.newline_css_edit)
        
        self.tag_css_edit = QLineEdit(self)
        layout.addRow("Tag CSS:", self.tag_css_edit)

        self.space_dot_color_picker = ColorPickerButton(parent=self)
        layout.addRow("Space Dot Color:", self.space_dot_color_picker)
        
        self.bracket_tag_color_picker = ColorPickerButton(parent=self)
        layout.addRow("Bracket Tag Color:", self.bracket_tag_color_picker)
        
    def setup_rules_tab(self):
        layout = QFormLayout(self.rules_tab)
        layout.addRow(QLabel("These settings are specific to the active plugin."))
        
        self.game_dialog_width_spinbox = LabeledSpinBox("Game Dialog Max Width (px):", 100, 500, 240, parent=self)
        layout.addRow(self.game_dialog_width_spinbox)
        
        self.width_warning_spinbox = LabeledSpinBox("Editor Line Width Warning (px):", 100, 500, 208, parent=self)
        layout.addRow(self.width_warning_spinbox)

    def find_plugins(self):
        plugins_dir = "plugins"
        found_plugins = {}
        if not os.path.isdir(plugins_dir):
            return found_plugins
        
        for item in os.listdir(plugins_dir):
            item_path = os.path.join(plugins_dir, item)
            config_path = os.path.join(item_path, "config.json")
            if os.path.isdir(item_path) and os.path.exists(config_path):
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

    def on_plugin_changed(self):
        log_debug("SettingsDialog: Plugin changed in dropdown.")
        
        current_settings = self.get_settings()
        self.mw.settings_manager._save_plugin_settings()
        
        selected_dir_name = self.plugin_map.get(self.plugin_combo.currentText())
        self.mw.active_game_plugin = selected_dir_name
        
        self.mw.settings_manager._load_plugin_settings()
        
        self.load_initial_settings()
        log_debug(f"SettingsDialog: Reloaded UI with settings for '{selected_dir_name}'.")


    def load_initial_settings(self):
        current_plugin_dir_name = getattr(self.mw, 'active_game_plugin', 'zelda_mc')
        for display_name, dir_name in self.plugin_map.items():
            if dir_name == current_plugin_dir_name:
                self.plugin_combo.blockSignals(True)
                self.plugin_combo.setCurrentText(display_name)
                self.plugin_combo.blockSignals(False)
                break
        
        self.font_size_spinbox.setValue(self.mw.current_font_size)
        self.original_path_edit.setText(self.mw.original_file_path or "")
        self.edited_path_edit.setText(self.mw.edited_file_path or "")
        
        self.preview_wrap_checkbox.setChecked(self.mw.preview_wrap_lines)
        self.editors_wrap_checkbox.setChecked(self.mw.editors_wrap_lines)
        self.show_spaces_checkbox.setChecked(self.mw.show_multiple_spaces_as_dots)
        self.newline_symbol_edit.setText(self.mw.newline_display_symbol)
        self.newline_css_edit.setText(self.mw.newline_css)
        self.tag_css_edit.setText(self.mw.tag_css)
        self.space_dot_color_picker.setColor(QColor(self.mw.space_dot_color_hex))
        self.bracket_tag_color_picker.setColor(QColor(self.mw.bracket_tag_color_hex))
        self.game_dialog_width_spinbox.setValue(self.mw.game_dialog_max_width_pixels)
        self.width_warning_spinbox.setValue(self.mw.line_width_warning_threshold_pixels)

    def get_settings(self) -> dict:
        selected_display_name = self.plugin_combo.currentText()
        selected_dir_name = self.plugin_map.get(selected_display_name)
        
        return {
            'active_game_plugin': selected_dir_name,
            'font_size': self.font_size_spinbox.value(),
            'original_file_path': self.original_path_edit.text(),
            'edited_file_path': self.edited_path_edit.text(),
            'preview_wrap_lines': self.preview_wrap_checkbox.isChecked(),
            'editors_wrap_lines': self.editors_wrap_checkbox.isChecked(),
            'show_multiple_spaces_as_dots': self.show_spaces_checkbox.isChecked(),
            'newline_display_symbol': self.newline_symbol_edit.text(),
            'newline_css': self.newline_css_edit.text(),
            'tag_css': self.tag_css_edit.text(),
            'space_dot_color_hex': self.space_dot_color_picker.color().name(),
            'bracket_tag_color_hex': self.bracket_tag_color_picker.color().name(),
            'game_dialog_max_width_pixels': self.game_dialog_width_spinbox.value(),
            'line_width_warning_threshold_pixels': self.width_warning_spinbox.value()
        }