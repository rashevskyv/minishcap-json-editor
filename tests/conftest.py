# --- START OF FILE tests/conftest.py ---
"""
Shared fixtures for all test modules.
"""
import os
import sys
import json
import tempfile
import pytest
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture
def temp_dir():
    """Temporary directory that is cleaned up after test."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def sample_json_data():
    """Sample JSON data representing game text blocks."""
    return [
        ["Hello, {PLAYER}!", "Welcome to Hyrule.", "Press {A_BUTTON} to continue."],
        ["Good morning!", "The weather is nice today."],
    ]


@pytest.fixture
def sample_json_path(temp_dir, sample_json_data):
    """A temporary JSON file with sample data."""
    path = os.path.join(temp_dir, "test_data.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(sample_json_data, f, ensure_ascii=False)
    return path


@pytest.fixture
def sample_text_content():
    """Sample text content (Kruptar format)."""
    return "Привіт, {PLAYER}!\n{END}\n\nДобрий ранок!\n{END}\n"


@pytest.fixture
def sample_text_path(temp_dir, sample_text_content):
    """A temporary text file with sample Kruptar-format content."""
    path = os.path.join(temp_dir, "test_data.txt")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(sample_text_content)
    return path


@pytest.fixture
def sample_utf16_path(temp_dir):
    """A temporary UTF-16 encoded text file."""
    path = os.path.join(temp_dir, "test_utf16.txt")
    with open(path, 'w', encoding='utf-16') as f:
        f.write("Тестовий текст UTF-16")
    return path


@pytest.fixture
def invalid_json_path(temp_dir):
    """A temporary file with invalid JSON."""
    path = os.path.join(temp_dir, "bad.json")
    with open(path, 'w', encoding='utf-8') as f:
        f.write("{invalid json content!!")
    return path


@pytest.fixture
def sample_font_map():
    """A font map with character widths for testing."""
    return {
        'a': {'width': 6}, 'b': {'width': 6}, 'c': {'width': 5},
        'd': {'width': 6}, 'e': {'width': 5}, 'f': {'width': 4},
        'g': {'width': 6}, 'h': {'width': 6}, 'i': {'width': 2},
        'j': {'width': 3}, 'k': {'width': 5}, 'l': {'width': 2},
        'm': {'width': 8}, 'n': {'width': 6}, 'o': {'width': 6},
        'p': {'width': 6}, 'q': {'width': 6}, 'r': {'width': 4},
        's': {'width': 5}, 't': {'width': 4}, 'u': {'width': 6},
        'v': {'width': 6}, 'w': {'width': 8}, 'x': {'width': 6},
        'y': {'width': 6}, 'z': {'width': 5},
        ' ': {'width': 4},
        '.': {'width': 2}, ',': {'width': 2}, '!': {'width': 2},
        '?': {'width': 5}, "'": {'width': 2},
        'А': {'width': 7}, 'Б': {'width': 7}, 'В': {'width': 7},
        'а': {'width': 6}, 'б': {'width': 6}, 'в': {'width': 6},
        '{PLAYER}': {'width': 48},
        '[L-Stick]': {'width': 12},
        '[L]': {'width': 8},
        '[A]': {'width': 10},
    }


@pytest.fixture
def sample_glossary_md():
    """Sample glossary in Markdown table format."""
    return """## Glossary

| Original | Translation | Notes |
|---|---|---|
| Link | Лінк | Ім'я головного героя |
| Zelda | Зельда | Принцеса |
| Rupee | Рупія | Ігрова валюта |
| Hyrule | Хайрул | Назва королівства |
"""


@pytest.fixture
def empty_font_map():
    """An empty font map."""
    return {}
