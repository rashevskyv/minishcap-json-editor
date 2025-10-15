# Game Translation Workbench

A PyQt5-based translation workbench for video game localization, specifically designed for retro Nintendo games (The Legend of Zelda series, Pokemon FireRed).

## Features

- **AI-Assisted Translation**: Context-aware translation with glossary management
- **Custom Font Rendering**: Character width calculation for game-specific display constraints
- **Plugin System**: Game-specific rule systems for different titles
- **Tag Management**: Handle game control codes (player names, button icons, etc.)
- **Multi-line Analysis**: Visual feedback for line width violations
- **Spellchecking**: Integrated spellchecking with custom dictionary support

## Setup

### 1. Prerequisites

- Python 3.14.0 or higher
- pip (Python package manager)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Keys

The application supports AI-powered translation using OpenAI and Google Gemini. To use these features:

1. **Copy the example environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and add your API keys**:
   ```bash
   # OpenAI API Keys
   # Get your key from https://platform.openai.com/api-keys
   OPENAI_API_KEY=your_openai_api_key_here

   # Font Tool OpenAI Key (if different from main)
   # If empty, will use OPENAI_API_KEY
   FONT_TOOL_OPENAI_API_KEY=

   # Gemini API Key
   # Get your key from https://aistudio.google.com/app/apikey
   GEMINI_API_KEY=your_gemini_api_key_here

   # DeepL API Key (optional)
   # Get your key from https://www.deepl.com/pro-api
   DEEPL_API_KEY=
   ```

3. **Important**: The `.env` file is excluded from git to protect your API keys. Never commit this file.

### 4. Run the Application

#### Windows
```bash
run.bat
```

The `run.bat` script automatically creates a virtual environment (`venv`) if it doesn't exist, installs dependencies, and launches the application.

#### Manual Start
```bash
python main.py
```

## Supported Games

The application uses a plugin system to support different games:

- **Zelda: Minish Cap** (`zelda_mc`)
- **Zelda: The Wind Waker** (`zelda_ww`)
- **Pokemon FireRed** (`pokemon_fr`)
- **Plain Text** (`plaintext`) - Generic text files

## Project Structure

```
jsonreader/
├── main.py                 # Application entry point
├── core/                   # Core functionality
│   ├── settings_manager.py
│   ├── translation/        # AI translation providers
│   └── ...
├── handlers/               # Business logic handlers
├── ui/                     # UI components
├── components/             # Custom widgets
├── plugins/                # Game-specific plugins
│   ├── zelda_mc/
│   ├── zelda_ww/
│   ├── pokemon_fr/
│   └── plaintext/
├── resources/              # Assets and resources
│   └── spellchecker/       # Dictionary files
├── .env                    # Your API keys (not in git)
├── .env.example            # Template for .env
└── requirements.txt        # Python dependencies
```

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Development guide and architecture documentation
- **[PLAN.md](PLAN.md)** - Future features and roadmap
- **[PROJECT_MANAGER_README.md](PROJECT_MANAGER_README.md)** - Project management features

## Development

See [CLAUDE.md](CLAUDE.md) for detailed development documentation including:
- Architecture overview
- Plugin development
- Adding new game support
- Code organization

## Logs

Application logs are written to `app_debug.txt` in the project root directory.

## License

[Add your license here]
