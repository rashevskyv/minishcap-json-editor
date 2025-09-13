import os
import re
from typing import Any, Tuple, Dict, List

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug

class GameRules(BaseGameRules):
    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.problem_analyzer = self

    def load_data_from_json_obj(self, file_content: Any) -> Tuple[list, dict]:
        if not isinstance(file_content, str):
            log_debug(f"Wind Waker Plugin: Expected file content as a string, but got {type(file_content)}")
            return [], {}

        strings = re.split(r'\{END\}\r?\n', file_content)
        
        if strings and (not strings[-1] or strings[-1].isspace()):
            strings.pop()
            
        processed_strings = [s.strip().replace('\r\n', '\n').replace('\r', '\n') for s in strings]

        data_for_app = [processed_strings]
        
        block_name = "Block 0"
        if self.mw and self.mw.json_path:
            block_name = os.path.basename(self.mw.json_path)
            
        block_names = {"0": block_name}
        
        log_debug(f"Wind Waker Plugin: Loaded {len(processed_strings)} strings from TXT file into one block named '{block_name}'.")
        return data_for_app, block_names

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if not data or not isinstance(data[0], list):
            log_debug(f"Wind Waker Plugin: Save data is in unexpected format. Expected list of lists.")
            return ""

        strings_to_save = data[0]
        
        content_parts = []
        for s in strings_to_save:
            content_parts.append(s + "{END}\n")
        
        # Об'єднуємо частини, додаючи порожній рядок між ними
        content = "\n".join(content_parts)
        
        # Додаємо фінальний перенос рядка, якщо є вміст, щоб імітувати порожній рядок в кінці
        if content:
            content += "\n"
            
        return content

    def get_display_name(self) -> str:
        return "Zelda: The Wind Waker"

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        return {}

    def analyze_subline(self, text: str, **kwargs) -> set:
        return set()

    def autofix_data_string(self, data_string: str, **kwargs) -> Tuple[str, bool]:
        return data_string, False