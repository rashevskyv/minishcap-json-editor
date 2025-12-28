# --- START OF FILE INTEGRATION_STEPS.md ---
# Integration Steps для Project System

## 🎯 Мета
Інтегрувати систему проектів в існуючий код без legacy mode.

## ⚠️ ВАЖЛИВО
Файл `ui/ui_setup.py` має проблему з дублюванням коду (система показує його двічі).
Потрібно вручну відредагувати цей файл.

## 📝 Кроки інтеграції

### Крок 1: Оновити меню File (вручну)

**Файл:** `ui/ui_setup.py`

**Знайти** (приблизно рядки 190-205):
```python
    menubar = main_window.menuBar()
    file_menu = menubar.addMenu('&File')
    style = main_window.style()

    open_icon = style.standardIcon(QStyle.SP_DialogOpenButton)
    save_icon = style.standardIcon(QStyle.SP_DialogSaveButton)
    reload_icon = style.standardIcon(QStyle.SP_BrowserReload)
    exit_icon = style.standardIcon(QStyle.SP_DialogCloseButton)
    settings_icon = QIcon.fromTheme('settings', style.standardIcon(QStyle.SP_FileDialogDetailedView))

    main_window.open_action = QAction(open_icon, '&Open Original File...', main_window)
    file_menu.addAction(main_window.open_action)

    main_window.open_changes_action = QAction('Open &Changes File...', main_window)
    file_menu.addAction(main_window.open_changes_action)
    file_menu.addSeparator()
```

**Замінити на:**
```python
    menubar = main_window.menuBar()
    file_menu = menubar.addMenu('&File')
    style = main_window.style()

    open_icon = style.standardIcon(QStyle.SP_DialogOpenButton)
    save_icon = style.standardIcon(QStyle.SP_DialogSaveButton)
    reload_icon = style.standardIcon(QStyle.SP_BrowserReload)
    exit_icon = style.standardIcon(QStyle.SP_DialogCloseButton)
    settings_icon = QIcon.fromTheme('settings', style.standardIcon(QStyle.SP_FileDialogDetailedView))

    # Project actions
    main_window.new_project_action = QAction(QIcon.fromTheme("document-new"), '&New Project...', main_window)
    main_window.new_project_action.setShortcut('Ctrl+N')
    file_menu.addAction(main_window.new_project_action)

    main_window.open_project_action = QAction(open_icon, '&Open Project...', main_window)
    main_window.open_project_action.setShortcut('Ctrl+O')
    file_menu.addAction(main_window.open_project_action)

    main_window.close_project_action = QAction('&Close Project', main_window)
    main_window.close_project_action.setEnabled(False)  # Enabled when project is loaded
    file_menu.addAction(main_window.close_project_action)
    file_menu.addSeparator()

    # Block actions (enabled only when project is open)
    main_window.import_block_action = QAction(QIcon.fromTheme("document-import"), '&Import Block...', main_window)
    main_window.import_block_action.setEnabled(False)  # Enabled when project is loaded
    file_menu.addAction(main_window.import_block_action)
    file_menu.addSeparator()
```

### Крок 2: ✅ Вже зроблено
- ✅ `main.py` - додано імпорт `ProjectManager`
- ✅ `main.py` - додано `self.project_manager = None`
- ✅ `components/project_dialogs.py` - створено діалоги
- ✅ `core/project_manager.py` - реалізовано систему

### Крок 3: Додати хендлери в AppActionHandler

**Файл:** `handlers/app_action_handler.py`

Додати методи для роботи з проектами (код нижче).

### Крок 4: Підключити сигнали

**Файл:** `main_window_event_handler.py` або безпосередньо в `main.py`

Підключити нові action до хендлерів (код нижче).

### Крок 5: Адаптувати завантаження блоків

Коли проект відкритий, блоки беруться з `project_manager`, а не з окремих файлів.

---

## 📄 Код для інтеграції

### Для `handlers/app_action_handler.py`

Додати в кінець класу `AppActionHandler`:

```python
    def create_new_project_action(self):
        """Create a new translation project."""
        from components.project_dialogs import NewProjectDialog
        log_info("Create New Project action triggered.")

        # Get available plugins
        plugins = {}
        plugins_dir = "plugins"
        if os.path.isdir(plugins_dir):
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

        dialog = NewProjectDialog(self.mw, available_plugins=plugins)
        if dialog.exec_() != dialog.Accepted:
            log_info("New project dialog cancelled.")
            return

        info = dialog.get_project_info()
        if not info:
            return

        # Create project using ProjectManager
        from core.project_manager import ProjectManager
        self.mw.project_manager = ProjectManager()

        success = self.mw.project_manager.create_new_project(
            project_dir=info['directory'],
            name=info['name'],
            plugin_name=info['plugin'],
            description=info['description']
        )

        if success:
            log_info(f"Project '{info['name']}' created successfully.")
            QMessageBox.information(
                self.mw,
                "Project Created",
                f"Project '{info['name']}' has been created at:\n{info['directory']}\n\n"
                f"You can now import blocks into this project."
            )

            # Enable project-specific actions
            if hasattr(self.mw, 'close_project_action'):
                self.mw.close_project_action.setEnabled(True)
            if hasattr(self.mw, 'import_block_action'):
                self.mw.import_block_action.setEnabled(True)

            # Update UI
            self.ui_updater.update_title()
            self.ui_updater.populate_blocks()
        else:
            QMessageBox.critical(
                self.mw,
                "Project Creation Failed",
                f"Failed to create project at:\n{info['directory']}"
            )

    def open_project_action(self):
        """Open an existing translation project."""
        from components.project_dialogs import OpenProjectDialog
        log_info("Open Project action triggered.")

        dialog = OpenProjectDialog(self.mw)
        if dialog.exec_() != dialog.Accepted:
            log_info("Open project dialog cancelled.")
            return

        project_path = dialog.get_project_path()
        if not project_path:
            return

        # Load project using ProjectManager
        from core.project_manager import ProjectManager
        self.mw.project_manager = ProjectManager()

        success = self.mw.project_manager.load(project_path)

        if success:
            project = self.mw.project_manager.project
            log_info(f"Project '{project.name}' loaded successfully.")

            # Enable project-specific actions
            if hasattr(self.mw, 'close_project_action'):
                self.mw.close_project_action.setEnabled(True)
            if hasattr(self.mw, 'import_block_action'):
                self.mw.import_block_action.setEnabled(True)

            # Update UI to show blocks
            self.ui_updater.update_title()
            self._populate_blocks_from_project()

            QMessageBox.information(
                self.mw,
                "Project Opened",
                f"Project '{project.name}' loaded successfully.\n\n"
                f"Plugin: {project.plugin_name}\n"
                f"Blocks: {len(project.blocks)}"
            )
        else:
            QMessageBox.critical(
                self.mw,
                "Project Load Failed",
                f"Failed to load project from:\n{project_path}"
            )

    def close_project_action(self):
        """Close the current project."""
        log_info("Close Project action triggered.")

        if self.mw.unsaved_changes:
            reply = QMessageBox.question(
                self.mw,
                'Unsaved Changes',
                "Save changes before closing project?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                if not self.save_data_action(ask_confirmation=False):
                    return
            elif reply == QMessageBox.Cancel:
                return

        # Clear project
        self.mw.project_manager = None

        # Clear UI
        self.mw.data = []
        self.mw.edited_data = {}
        self.mw.block_names = {}
        self.mw.current_block_idx = -1
        self.mw.current_string_idx = -1
        self.mw.unsaved_changes = False

        # Disable project-specific actions
        if hasattr(self.mw, 'close_project_action'):
            self.mw.close_project_action.setEnabled(False)
        if hasattr(self.mw, 'import_block_action'):
            self.mw.import_block_action.setEnabled(False)

        # Update UI
        self.ui_updater.update_title()
        self.ui_updater.populate_blocks()
        self.ui_updater.populate_strings_for_block(-1)

        log_info("Project closed.")

    def import_block_action(self):
        """Import a new block into the current project."""
        from components.project_dialogs import ImportBlockDialog
        log_info("Import Block action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            QMessageBox.warning(
                self.mw,
                "No Project",
                "Please open or create a project first."
            )
            return

        dialog = ImportBlockDialog(self.mw, project_manager=self.mw.project_manager)
        if dialog.exec_() != dialog.Accepted:
            log_info("Import block dialog cancelled.")
            return

        info = dialog.get_block_info()
        if not info:
            return

        # Import block using ProjectManager
        block = self.mw.project_manager.add_block(
            name=info['name'],
            source_file_path=info['source_file'],
            description=info['description']
        )

        if block:
            log_info(f"Block '{info['name']}' imported successfully.")

            # Update UI
            self._populate_blocks_from_project()

            QMessageBox.information(
                self.mw,
                "Block Imported",
                f"Block '{info['name']}' has been imported into the project."
            )
        else:
            QMessageBox.critical(
                self.mw,
                "Import Failed",
                f"Failed to import block from:\n{info['source_file']}"
            )

    def _populate_blocks_from_project(self):
        """Populate block list from current project."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        # Clear current data
        self.mw.block_list_widget.clear()
        self.mw.data = []
        self.mw.block_names = {}

        # Add blocks from project
        for block in self.mw.project_manager.project.blocks:
            # Add block name to block_names dict
            block_idx = len(self.mw.data)
            self.mw.block_names[str(block_idx)] = block.name

            # For now, just add empty placeholder
            # Later we'll load the actual data when block is selected
            self.mw.data.append([])

        # Update UI
        self.ui_updater.populate_blocks()
```

### Для підключення сигналів

Додати в `main_window_event_handler.py` або де підключаються інші action:

```python
    # Project actions
    if hasattr(main_window, 'new_project_action'):
        main_window.new_project_action.triggered.connect(
            lambda: main_window.app_action_handler.create_new_project_action()
        )

    if hasattr(main_window, 'open_project_action'):
        main_window.open_project_action.triggered.connect(
            lambda: main_window.app_action_handler.open_project_action()
        )

    if hasattr(main_window, 'close_project_action'):
        main_window.close_project_action.triggered.connect(
            lambda: main_window.app_action_handler.close_project_action()
        )

    if hasattr(main_window, 'import_block_action'):
        main_window.import_block_action.triggered.connect(
            lambda: main_window.app_action_handler.import_block_action()
        )
```

---

## 🧪 Тестування

Після цих змін можна запустити:

```bash
python main.py
```

**Що тестувати:**

1. **New Project**:
   - File → New Project...
   - Заповнити форму
   - Перевірити що створилася папка з project.uiproj

2. **Open Project**:
   - File → Open Project...
   - Вибрати створений проект
   - Має з'явитися повідомлення про успішне завантаження

3. **Import Block**:
   - File → Import Block...
   - Вибрати текстовий файл
   - Перевірити що блок додався в список

4. **Close Project**:
   - File → Close Project
   - Перевірити що UI очистилося

---

## ❓ Питання?

Якщо щось не працює або незрозуміло - дайте знати!
