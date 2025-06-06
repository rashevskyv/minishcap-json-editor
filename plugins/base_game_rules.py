from PyQt5.QtGui import QColor, QTextCharFormat
from typing import Optional, Set, Dict, Any, Tuple, List

# plugins/base_game_rules.py

class BaseGameRules:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError("Subclasses must implement get_problem_definitions")

    def analyze_subline(self,
                        text: str,
                        next_text: Optional[str],
                        subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int,
                        is_last_subline_in_data_string: bool,
                        editor_font_map: dict,
                        editor_line_width_threshold: int,
                        full_data_string_text_for_logical_check: str, # New parameter
                        is_target_for_debug: bool = False) -> Set[str]: # New parameter
        raise NotImplementedError("Subclasses must implement analyze_subline")

    def autofix_data_string(self,
                            data_string: str,
                            editor_font_map: dict,
                            editor_line_width_threshold: int) -> Tuple[str, bool]:
        raise NotImplementedError("Subclasses must implement autofix_data_string")

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        return data_string_subline

    def get_text_representation_for_preview(self, data_string: str) -> str:
        return data_string.replace('\n', getattr(self.mw, "newline_display_symbol", "↵")) if self.mw else data_string.replace('\n', "↵")

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        """
        Повертає список правил для підсвітки синтаксису.
        Кожне правило - це кортеж (regex_pattern, QTextCharFormat).
        """
        return []

    def get_legitimate_tags(self) -> Set[str]:
        """
        Повертає множину легітимних тегів для гри.
        """
        return set()

    def get_context_menu_actions(self, editor_widget, selected_text: Optional[str]) -> List[Dict[str, Any]]:
        """
        Повертає список дій для контекстного меню.
        Кожна дія - це словник, наприклад:
        {'text': 'Вставити тег гравця', 'action': callable_function, 'shortcut': 'Ctrl+P'}
        """
        return []

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int) -> Optional[int]:
        """
        Дозволяє плагіну перевизначити стандартний розрахунок ширини рядка.
        Повертає ширину в пікселях або None, щоб використати стандартний розрахунок.
        """
        return None

    def get_plugin_actions(self) -> List[Dict[str, Any]]:
        """
        Повертає список кастомних дій (для меню/тулбарів), які надає плагін.
        Кожна дія - це словник, наприклад:
        {'name': 'my_plugin_action', 'text': 'Моя Дія', 'tooltip': 'Опис моєї дії',
         'icon_theme': 'document-new', 'shortcut': 'Ctrl+Shift+M', 'handler': self.my_action_handler}
        """
        return []