# Gemini Code Assistant Context

This document provides context for the Gemini Code Assistant to understand the project structure, conventions, and tasks.

## Project Overview

This project is a sophisticated GUI-based dialogue editor for video games, built with Python and the PyQt5 framework. It is designed to facilitate the translation and editing of in-game text, which is stored in JSON or text files. The editor is highly extensible through a plugin-based architecture, allowing it to support various games with unique text formats, character encodings, and validation rules.

The core functionality of the application includes:

*   **Side-by-side Editing:** A clear and intuitive interface for comparing and editing original and translated text.
*   **Plugin System:** A modular design that allows for game-specific logic to be encapsulated in plugins. Each plugin can define its own rules for parsing data, syntax highlighting, error checking, and auto-fixing. Currently, there are plugins for "The Legend of Zelda: The Minish Cap", "The Legend of Zelda: The Wind Waker", and "Pokémon FireRed".
*   **Advanced Error Detection:** The editor can detect a wide range of potential issues in the translated text, such as line width exceeding game limits, incorrect tag usage, and logical errors.
*   **Syntax Highlighting:** The editor provides customizable syntax highlighting for in-game tags and special characters, making it easier to read and edit the text.
*   **AI-Powered Tools:** The editor integrates with AI services to provide features like automatic translation and text variation generation.
*   **Glossary Support:** The editor can highlight terms from a glossary, ensuring consistency in translation.

## Building and Running

The project is written in Python and uses PyQt5 for the GUI. To run the application, you need to have Python and the required dependencies installed.

### Dependencies

The project's dependencies are listed in the `requirements.txt` file:

*   PyQt5
*   requests

### Running the Application

To run the application, execute the `main.py` script:

```bash
python main.py
```

Alternatively, you can use the provided `run.bat` (for Windows) or `run.sh` (for Linux/macOS).

## Development Conventions

### Code Structure

The project is organized into the following directories:

*   `components`: Reusable UI components, such as custom widgets and dialogs.
*   `core`: Core application logic, including data management, settings, and translation services.
*   `handlers`: Event handlers and action handlers that connect the UI to the application logic.
*   `plugins`: Game-specific plugins. Each plugin is a subdirectory containing the rules and configuration for a specific game.
*   `ui`: UI setup and related modules.
*   `utils`: Utility modules, such as logging and syntax highlighting.

### Plugin Architecture

The plugin system is a key part of the application's design. Each plugin is a Python package located in the `plugins` directory. A plugin must provide a `rules.py` file that contains a `GameRules` class that inherits from `plugins.base_game_rules.BaseGameRules`. This class defines the game-specific logic for the editor.

### Settings

The application uses JSON files to store settings. Global settings are stored in `settings.json`, while plugin-specific settings are stored in a `config.json` file within the plugin's directory.

### UI

The UI is built with PyQt5. The main window UI is set up in the `ui/ui_setup.py` module. The application uses a dark theme by default, but this can be changed in the settings.

### Commit Message Strategy

This project follows the **Conventional Commits** specification. Commit messages should be structured as follows:

```
<type>(<scope>): <short summary>
<BLANK LINE>
<optional body>
<BLANK LINE>
<optional footer>
```

-   **type**: `feat` (new feature), `fix` (bug fix), `docs`, `style`, `refactor`, `test`, `chore`, etc.
-   **scope**: The part of the codebase affected (e.g., `ui`, `plugin`, `core`).

### Communication Language

Our primary language of communication for this project is **Ukrainian**.