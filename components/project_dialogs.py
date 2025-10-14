# components/project_dialogs.py
"""
Dialog windows for project management:
- NewProjectDialog: Create a new translation project
- OpenProjectDialog: Open an existing project
- ImportBlockDialog: Import a new block into the project
"""

import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QComboBox, QFileDialog, QDialogButtonBox,
    QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt
from utils.logging_utils import log_debug, log_info


class NewProjectDialog(QDialog):
    """
    Dialog for creating a new translation project.

    Collects:
    - Project name
    - Project directory (where to create the project)
    - Active plugin
    - Optional description
    """

    def __init__(self, parent=None, available_plugins=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setMinimumWidth(500)

        self.available_plugins = available_plugins or {}
        self.project_dir = None
        self.project_name = None
        self.plugin_name = None
        self.description = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Form layout for inputs
        form_layout = QFormLayout()

        # Project name
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("e.g., Wind Waker Translation")
        form_layout.addRow("Project Name:", self.name_edit)

        # Project directory
        dir_layout = QHBoxLayout()
        self.dir_edit = QLineEdit(self)
        self.dir_edit.setPlaceholderText("Select where to create the project...")
        self.dir_edit.setReadOnly(True)
        dir_layout.addWidget(self.dir_edit)

        browse_button = QPushButton("Browse...", self)
        browse_button.clicked.connect(self._browse_directory)
        dir_layout.addWidget(browse_button)

        form_layout.addRow("Location:", dir_layout)

        # Plugin selection
        self.plugin_combo = QComboBox(self)
        self._populate_plugins()
        form_layout.addRow("Game Plugin:", self.plugin_combo)

        # Description
        self.description_edit = QTextEdit(self)
        self.description_edit.setPlaceholderText("Optional: Enter project description...")
        self.description_edit.setMaximumHeight(80)
        form_layout.addRow("Description:", self.description_edit)

        layout.addLayout(form_layout)

        # Info label
        info_label = QLabel(
            "A new project folder will be created with 'sources/' and 'translation/' subdirectories.",
            self
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(info_label)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            self
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_plugins(self):
        """Populate plugin dropdown with available plugins."""
        if not self.available_plugins:
            # Fallback: scan plugins directory
            self.available_plugins = self._scan_plugins()

        # Add placeholder item
        self.plugin_combo.addItem("-- Select a plugin --", None)

        for display_name in sorted(self.available_plugins.keys()):
            plugin_dir = self.available_plugins[display_name]
            self.plugin_combo.addItem(display_name, plugin_dir)

    def _scan_plugins(self):
        """Scan plugins directory to find available plugins."""
        plugins = {}
        plugins_dir = "plugins"

        if not os.path.isdir(plugins_dir):
            return plugins

        for item in os.listdir(plugins_dir):
            item_path = os.path.join(plugins_dir, item)
            config_path = os.path.join(item_path, "config.json")

            if os.path.isdir(item_path) and os.path.exists(config_path):
                try:
                    import json
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    display_name = config_data.get("display_name", item)
                    plugins[display_name] = item
                except Exception as e:
                    log_debug(f"Could not read config for plugin '{item}': {e}")
                    plugins[item] = item

        return plugins

    def _browse_directory(self):
        """Open directory picker for project location."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Project Location",
            os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if directory:
            self.dir_edit.setText(directory)

    def _validate_and_accept(self):
        """Validate inputs before accepting."""
        # Validate project name
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Please enter a project name."
            )
            self.name_edit.setFocus()
            return

        # Validate directory
        directory = self.dir_edit.text().strip()
        if not directory:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Please select a location for the project."
            )
            return

        if not os.path.exists(directory):
            QMessageBox.warning(
                self,
                "Invalid Location",
                f"The selected directory does not exist:\n{directory}"
            )
            return

        # Validate plugin selection
        plugin = self.plugin_combo.currentData()
        if plugin is None:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Please select a game plugin for the project."
            )
            self.plugin_combo.setFocus()
            return

        # Build full project path
        # Sanitize project name for filesystem
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')

        project_path = os.path.join(directory, safe_name)

        # Check if project already exists
        if os.path.exists(project_path):
            reply = QMessageBox.question(
                self,
                "Project Exists",
                f"A folder named '{safe_name}' already exists at this location.\n\n"
                f"Do you want to use this folder anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Store results
        self.project_name = name
        self.project_dir = project_path
        self.plugin_name = self.plugin_combo.currentData()
        self.description = self.description_edit.toPlainText().strip()

        log_info(f"NewProjectDialog: Creating project '{name}' at {project_path}")
        self.accept()

    def get_project_info(self):
        """
        Get project information after dialog is accepted.

        Returns:
            dict: Project information or None if cancelled
        """
        if self.result() == QDialog.Accepted:
            return {
                'name': self.project_name,
                'directory': self.project_dir,
                'plugin': self.plugin_name,
                'description': self.description
            }
        return None


class OpenProjectDialog(QDialog):
    """
    Dialog for opening an existing project.

    Currently simple: just pick a .uiproj file or project directory.
    Can be extended with recent projects list.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Project")
        self.setMinimumWidth(500)

        self.project_path = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Instructions
        info_label = QLabel(
            "Select a project file (.uiproj) to open.",
            self
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Path selection
        path_layout = QHBoxLayout()

        self.path_edit = QLineEdit(self)
        self.path_edit.setPlaceholderText("Select project.uiproj file...")
        self.path_edit.setReadOnly(True)
        path_layout.addWidget(self.path_edit)

        browse_file_button = QPushButton("Browse...", self)
        browse_file_button.clicked.connect(self._browse_file)
        path_layout.addWidget(browse_file_button)

        layout.addLayout(path_layout)

        # TODO: Add recent projects list here
        # recent_group = QGroupBox("Recent Projects", self)
        # ...

        layout.addStretch()

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            self
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _browse_file(self):
        """Browse for .uiproj file."""
        # Try to start in a sensible location (user's home or recent projects directory)
        start_dir = os.path.expanduser("~")

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Project File",
            start_dir,
            "Project Files (*.uiproj);;All Files (*)"
        )

        if file_path:
            self.path_edit.setText(file_path)

    def _validate_and_accept(self):
        """Validate selected path before accepting."""
        path = self.path_edit.text().strip()

        if not path:
            QMessageBox.warning(
                self,
                "No Project Selected",
                "Please select a .uiproj file."
            )
            return

        if not os.path.exists(path):
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The selected file does not exist:\n{path}"
            )
            return

        # Validate it's a .uiproj file
        if not os.path.isfile(path):
            QMessageBox.warning(
                self,
                "Invalid Selection",
                "Please select a project file, not a directory."
            )
            return

        if not path.endswith('.uiproj'):
            QMessageBox.warning(
                self,
                "Invalid File",
                "Please select a .uiproj file."
            )
            return

        self.project_path = path
        log_info(f"OpenProjectDialog: Opening project at {path}")
        self.accept()

    def get_project_path(self):
        """
        Get selected project path after dialog is accepted.

        Returns:
            str: Project path or None if cancelled
        """
        if self.result() == QDialog.Accepted:
            return self.project_path
        return None


class ImportBlockDialog(QDialog):
    """
    Dialog for importing a new block (file) into an existing project.

    Collects:
    - Source file path
    - Translation file path (optional)
    - Block name (optional, defaults to filename)
    - Description (optional)
    """

    def __init__(self, parent=None, project_manager=None):
        super().__init__(parent)
        self.setWindowTitle("Import Block")
        self.setMinimumWidth(500)

        self.project_manager = project_manager
        self.source_file = None
        self.translation_file = None
        self.block_name = None
        self.description = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Info text
        if self.project_manager and self.project_manager.project:
            info = QLabel(
                f"Import a new file into project: {self.project_manager.project.name}",
                self
            )
            info.setStyleSheet("font-weight: bold;")
            layout.addWidget(info)

        # Form layout
        form_layout = QFormLayout()

        # Source file selection
        source_layout = QHBoxLayout()
        self.file_edit = QLineEdit(self)
        self.file_edit.setPlaceholderText("Select source file to import...")
        self.file_edit.setReadOnly(True)
        self.file_edit.textChanged.connect(self._on_source_file_selected)
        source_layout.addWidget(self.file_edit)

        browse_source_button = QPushButton("Browse...", self)
        browse_source_button.clicked.connect(self._browse_source_file)
        source_layout.addWidget(browse_source_button)

        form_layout.addRow("Source File:", source_layout)

        # Translation file selection
        translation_layout = QHBoxLayout()
        self.translation_edit = QLineEdit(self)
        self.translation_edit.setPlaceholderText("Optional: select existing translation file...")
        self.translation_edit.setReadOnly(True)
        translation_layout.addWidget(self.translation_edit)

        browse_translation_button = QPushButton("Browse...", self)
        browse_translation_button.clicked.connect(self._browse_translation_file)
        translation_layout.addWidget(browse_translation_button)

        form_layout.addRow("Translation File:", translation_layout)

        # Block name
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("Auto-filled from filename")
        form_layout.addRow("Block Name:", self.name_edit)

        # Description
        self.description_edit = QTextEdit(self)
        self.description_edit.setPlaceholderText("Optional: Enter block description...")
        self.description_edit.setMaximumHeight(80)
        form_layout.addRow("Description:", self.description_edit)

        layout.addLayout(form_layout)

        # Info label
        info_label = QLabel(
            "The source file will be copied to the project's 'sources/' directory.\n"
            "If you don't specify a translation file, the source will be copied to 'translation/'.",
            self
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(info_label)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            self
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _browse_source_file(self):
        """Browse for source file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Source File",
            os.path.expanduser("~"),
            "Supported Files (*.txt *.json);;Text Files (*.txt);;JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            self.file_edit.setText(file_path)

    def _browse_translation_file(self):
        """Browse for translation file."""
        start_dir = os.path.dirname(self.file_edit.text()) if self.file_edit.text() else os.path.expanduser("~")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Translation File (Optional)",
            start_dir,
            "Supported Files (*.txt *.json);;Text Files (*.txt);;JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            self.translation_edit.setText(file_path)

    def _on_source_file_selected(self, file_path):
        """Auto-fill block name from filename if not already set."""
        if file_path and not self.name_edit.text():
            filename = os.path.basename(file_path)
            name_without_ext = os.path.splitext(filename)[0]
            # Make it more readable
            display_name = name_without_ext.replace('_', ' ').title()
            self.name_edit.setText(display_name)

    def _validate_and_accept(self):
        """Validate inputs before accepting."""
        # Validate file
        file_path = self.file_edit.text().strip()
        if not file_path:
            QMessageBox.warning(
                self,
                "No File Selected",
                "Please select a source file to import."
            )
            return

        if not os.path.exists(file_path):
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The selected file does not exist:\n{file_path}"
            )
            return

        # Validate name
        name = self.name_edit.text().strip()
        if not name:
            # Use filename as fallback
            name = os.path.splitext(os.path.basename(file_path))[0]
            name = name.replace('_', ' ').title()

        # Store results
        self.source_file = file_path
        self.translation_file = self.translation_edit.text().strip() or None
        self.block_name = name
        self.description = self.description_edit.toPlainText().strip()

        log_info(f"ImportBlockDialog: Importing block '{name}' from {file_path}")
        if self.translation_file:
            log_info(f"  Translation file: {self.translation_file}")
        self.accept()

    def get_block_info(self):
        """
        Get block information after dialog is accepted.

        Returns:
            dict: Block information or None if cancelled
        """
        if self.result() == QDialog.Accepted:
            return {
                'source_file': self.source_file,
                'translation_file': self.translation_file,
                'name': self.block_name,
                'description': self.description
            }
        return None
