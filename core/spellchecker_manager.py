# /home/runner/work/RAG_project/RAG_project/core/spellchecker_manager.py
import os
import re
from typing import List, Optional, Dict
from utils.logging_utils import log_debug, log_warning, log_error
from spylls.hunspell import Dictionary

CUSTOM_DICT_FILENAME = "custom_dictionary.txt"
LOCAL_DICT_PATH = "resources/spellchecker"
MIN_WORD_LENGTH = 3
WORD_PATTERN = re.compile(r"^[a-zA-Zа-яА-ЯіїІїЄєґҐ']+")

class SpellcheckerManager:
    def __init__(self, main_window, language='uk', custom_dict_path=None):
        self.mw = main_window
        self.language = language
        self.custom_dict_path = custom_dict_path or LOCAL_DICT_PATH
        self.hunspell: Optional['Dictionary'] = None
        self.enabled = False
        self.custom_words = set()

        self._initialize_spellchecker()

    def _initialize_spellchecker(self):
        log_debug("Attempting to initialize spellchecker...")
        try:
            dictionary_name = self.language
            search_path = self.custom_dict_path
            
            dictionary_basename = os.path.join(search_path, dictionary_name)
            log_debug(f"Loading dictionary from basename: '{dictionary_basename}'")

            dic_path = f'{dictionary_basename}.dic'
            aff_path = f'{dictionary_basename}.aff'

            if not os.path.exists(dic_path) or not os.path.exists(aff_path):
                log_warning(f"Dictionary files (.dic, .aff) for basename '{dictionary_basename}' not found. Spellchecker will be inactive.")
                self.hunspell = None
                return

            self.hunspell = Dictionary.from_files(dictionary_basename)
            log_debug(f"spylls Dictionary object created successfully for language '{dictionary_name}'.")
            self._load_user_dictionary()

        except Exception as e:
            log_error(f"Failed to initialize spylls for '{self.language}': {e}", exc_info=True)
            self.hunspell = None

    def reload_dictionary(self, language: str, custom_dict_path: Optional[str] = None):
        self.language = language
        self.custom_dict_path = custom_dict_path if custom_dict_path else self.custom_dict_path
        self._initialize_spellchecker()
        log_debug(f"Spellchecker reloaded with language='{language}' and custom_dict='{self.custom_dict_path}'.")

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        log_debug(f"Spellchecker {'enabled' if enabled else 'disabled'}.")

    def scan_local_dictionaries(self) -> Dict[str, str]:
        """Scans for .dic files and returns a map of language code to full path."""
        if not os.path.exists(LOCAL_DICT_PATH):
            return {}
        
        dictionaries = {}
        for filename in os.listdir(LOCAL_DICT_PATH):
            if filename.endswith(".dic"):
                lang_code = os.path.splitext(filename)[0]
                aff_path = os.path.join(LOCAL_DICT_PATH, f"{lang_code}.aff")
                if os.path.exists(aff_path):
                    dictionaries[lang_code] = os.path.join(LOCAL_DICT_PATH, filename)
        
        log_debug(f"Found local dictionaries: {list(dictionaries.keys())}")
        return dictionaries

    def _load_user_dictionary(self):
        if not self.hunspell:
            return
        
        custom_dict_path = os.path.join(LOCAL_DICT_PATH, CUSTOM_DICT_FILENAME)
        if not os.path.exists(custom_dict_path):
            os.makedirs(os.path.dirname(custom_dict_path), exist_ok=True)
            return
        try:
            with open(custom_dict_path, 'r', encoding='utf-8') as f:
                words = [line.strip() for line in f if line.strip()]
                self.custom_words = set(word.lower() for word in words)
            
            for word in self.custom_words:
                self.hunspell.add(word)
            log_debug(f"Loaded {len(self.custom_words)} words from user dictionary.")
        except Exception as e:
            log_warning(f"Failed to load user dictionary: {e}")

    def add_to_custom_dictionary(self, word: str):
        if not self.hunspell:
            return
        normalized_word = word.lower()
        if normalized_word not in self.custom_words:
            self.custom_words.add(normalized_word)
            self.hunspell.add(normalized_word)
            
            custom_dict_path = os.path.join(LOCAL_DICT_PATH, CUSTOM_DICT_FILENAME)
            try:
                with open(custom_dict_path, 'a', encoding='utf-8') as f:
                    f.write(normalized_word + "\n")
                log_debug(f"Added '{normalized_word}' to user dictionary file.")
                if hasattr(self.mw, 'edited_text_edit'):
                    self.mw.edited_text_edit.highlighter.rehighlight()
            except Exception as e:
                log_warning(f"Failed to save user dictionary: {e}")

    def is_misspelled(self, word: str) -> bool:
        if not self.enabled:
            log_debug(f"-> is_misspelled for '{word}': returning False (spellchecker is globally disabled).")
            return False
        if not self.hunspell:
            log_debug(f"-> is_misspelled for '{word}': returning False (hunspell object not initialized).")
            return False

        cleaned_word = word.strip("'")
        
        if len(cleaned_word) < MIN_WORD_LENGTH:
            return False
        if cleaned_word.isdigit():
            return False
        if not WORD_PATTERN.match(cleaned_word):
            return False
        
        is_correct = self.hunspell.lookup(cleaned_word)
        log_debug(f"Spellchecking word '{cleaned_word}': Correct = {is_correct}. Misspelled = {not is_correct}")
        return not is_correct

    def get_suggestions(self, word: str) -> List[str]:
        if not self.enabled or not self.hunspell:
            return []
        
        suggestions = self.hunspell.suggest(word.lower())
        return suggestions if suggestions else []