# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a PyQt5-based translation workbench for video game localization, specifically designed for retro Nintendo games (The Legend of Zelda series, Pokemon FireRed). The application provides specialized tools for managing game text, including:

- AI-assisted translation with context-aware glossary management
- Custom font rendering and width calculation for game-specific display constraints
- Plugin-based game rule systems for different titles
- Tag management for game control codes (player names, button icons, etc.)
- Multi-line text analysis with visual feedback for line width violations

## Development Commands

### Environment Setup
```bash
# Windows
run.bat

# Unix/Linux
./run.sh
```

The `run.bat` script automatically creates a virtual environment (`venv`) if it doesn't exist, installs PyQt5, and launches the application.

### Running the Application
```bash
python main.py
```

### Python Version
Python 3.14.0 (check with `python --version`)

### Dependencies
Install all dependencies from `requirements.txt`:
```bash
pip install -r requirements.txt
```

Key dependencies:
- PyQt5 (GUI framework)
- playwright (web automation for AI interactions)
- deep-translator, googletrans (translation APIs)
- markdown (glossary formatting)

## Architecture

### Core Components

**Main Window (`main.py`)**
- Entry point and central coordinator
- Manages application state through extensive boolean flags (e.g., `is_loading_data`, `is_updating_ui`, `is_pasting_block`)
- Delegates functionality to specialized handlers and managers
- Uses composition pattern with helper classes: `MainWindowHelper`, `MainWindowActions`, `MainWindowUIHandler`, `MainWindowPluginHandler`, `MainWindowEventHandler`, `MainWindowBlockHandler`

**Data Model**
- **Block**: Represents a collection of translatable strings (typically maps to a game text file)
- **String**: Individual translatable text entry within a block
- **Subline**: Individual lines within multi-line strings (important for game display constraints)
- Data structure: `self.data` (list of blocks) and `self.edited_data` (dict of edited strings)
- Block names stored in `self.block_names` dict for custom naming

**Handler Architecture** (located in `handlers/`)
- `AppActionHandler`: File operations (open, save, reload, revert)
- `ListSelectionHandler`: Manages navigation between blocks and strings
- `TextOperationHandler`: Handles text editing operations
- `SearchHandler`: Search functionality across blocks
- `StringSettingsHandler`: Per-string settings (font, width constraints)
- `TranslationHandler`: AI translation integration
- `AIChatHandler`: AI chat interface for context-aware assistance

**UI Components** (located in `components/`)
- `LineNumberedTextEdit`: Custom text editor with line numbers, width warnings, and visual feedback
- `TextHighlightManager`: Manages syntax highlighting and visual indicators
- `CustomListWidget`: Block/string list with drag-and-drop support
- `GlossaryDialog`: Glossary management interface
- `SearchPanelWidget`: Search UI

**Core Services** (located in `core/`)
- `SettingsManager`: Persists application and per-plugin settings to `settings.json`
- `DataStateProcessor`: Validates and processes data state changes
- `GlossaryManager`: Loads, caches, and searches glossary entries (markdown format)
- `SpellcheckerManager`: Integrated spellchecking using `spylls` library (Hunspell-compatible)
  - Checks spelling in `edited_text_edit` only
  - Red wavy underline for misspelled words
  - Context menu option to add words to custom dictionary
  - Dictionaries stored in `resources/spellchecker/` (.dic/.aff files)
  - Custom user dictionary in `resources/spellchecker/custom_dictionary.txt`
- `translation/`: AI provider abstraction (OpenAI, Gemini, etc.)

**Plugin System** (located in `plugins/`)
- Each game has a plugin directory (e.g., `zelda_mc`, `zelda_ww`, `pokemon_fr`)
- Plugins inherit from `BaseGameRules` and implement:
  - `analyze_subline()`: Detect problems (width violations, tag issues, etc.)
  - `autofix_data_string()`: Automatically fix common issues
  - `get_default_tag_mappings()`: Define game-specific tags
  - `get_problem_definitions()`: Register problem types for detection/autofix
  - `load_data_from_json_obj()`, `save_data_to_json_obj()`: Custom serialization
- Plugin configuration stored in `plugins/{game}/config.json`
- Font maps in `plugins/{game}/font_map.json` for precise character width calculation
- Translation prompts in `plugins/{game}/translation_prompts/`

### Data Flow

1. **Loading**: `AppActionHandler` → `load_json_file()` → plugin's `load_data_from_json_obj()` → populate `self.data` and `self.edited_data`
2. **UI Update**: Data change → `UIUpdater` → update preview, editors, status bar
3. **Editing**: User types → `TextOperationHandler` → validate → update `self.edited_data` → mark unsaved
4. **Translation**: User triggers AI → `TranslationHandler` → compose prompt with glossary → call AI provider → update text
5. **Saving**: `AppActionHandler` → plugin's `save_data_to_json_obj()` → `save_json_file()`

### Key Design Patterns

**State Management**
- Heavy use of boolean flags in `MainWindow` to prevent recursive updates
- Always check relevant flags before performing operations (e.g., `if self.is_loading_data: return`)
- Use `self.is_programmatically_changing_text` when updating text programmatically to avoid triggering event handlers

**Plugin Architecture**
- `BaseGameRules` defines interface
- Game-specific logic in plugin subclasses (e.g., `ZeldaMCRules`, `ZeldaWWRules`)
- Dynamic loading via `load_game_plugin()` in `MainWindowPluginHandler`
- Plugin selection persisted in `settings.json` as `active_game_plugin`

**Glossary System**
- Markdown-based storage with sections and tables
- Pattern-based matching with regex compilation cache
- Occurrence indexing for finding all uses of terms
- Session changes tracked for highlighting recent modifications

## Important File Locations

- **Settings**: `settings.json` (root directory)
- **Plugin configs**: `plugins/{game}/config.json`
- **Font maps**: `plugins/{game}/font_map.json`
- **Glossaries**: `plugins/{game}/translation_prompts/glossary.md`
- **Translation prompts**: `plugins/{game}/translation_prompts/prompts.json`
- **Logs**: `app_debug.txt` (generated at runtime)

## Working with the Code

### Adding a New Plugin
1. Create directory `plugins/{game_name}/`
2. Create `config.json` with `display_name` and `default_tag_mappings`
3. Create `font_map.json` if custom width calculation needed
4. Create Python module with class inheriting from `BaseGameRules`
5. Implement required methods (at minimum: `load_data_from_json_obj`, `save_data_to_json_obj`)
6. Optionally create `translation_prompts/` directory with `glossary.md` and `prompts.json`

### Extending Game Rules
- Override `analyze_subline()` to add custom problem detection
- Override `autofix_data_string()` to add automatic fixes
- Define problems in `get_problem_definitions()` with structure:
  ```python
  {
      "PROBLEM_ID": {
          "name": "Short Name",
          "color": "#RRGGBB",
          "explanation": "Detailed explanation",
          "severity": "warning"  # or "error"
      }
  }
  ```
- Enable/disable detection and autofix per problem in plugin config.json

### Translation Integration
- AI providers abstracted in `core/translation/providers.py`
- Prompts composed in `handlers/translation/ai_prompt_composer.py`
- Glossary automatically included in translation context
- Session management tracks translation state
- Results can generate glossary entries for unknown terms

### UI Updates
- Always use `UIUpdater` methods to update UI components
- Never directly modify text editors without setting `is_programmatically_changing_text = True`
- Use `ui/updaters/` for specialized update logic (e.g., `preview_updater.py`, `string_settings_updater.py`)

### Logging
Use utilities from `utils/logging_utils.py`:
- `log_info()`: General information
- `log_warning()`: Warnings
- `log_error()`: Errors
- `log_debug()`: Detailed debugging (verbose)

All logs written to `app_debug.txt` in the root directory.

## Planned Features (from PLAN.md)

The project is transitioning from a file-oriented to a project-oriented paradigm:

- **Project Management**: Create projects (`.uiproj` file) containing multiple blocks
- **Virtual Categories**: Organize strings within blocks using metadata-based categories
- **Tree View**: Replace list widget with hierarchical tree for blocks and categories
- **Drag-and-Drop**: Assign strings to categories via drag-and-drop
- **Filtered Operations**: Apply translation/autofix to specific categories only

Multi-line selection with Ctrl/Shift in preview is already implemented.
