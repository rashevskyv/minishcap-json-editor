# handlers/translation/ai_prompt_composer.py ---
import json
import re
from typing import Dict, List, Optional, Sequence, Tuple

from .base_translation_handler import BaseTranslationHandler
from core.glossary_manager import GlossaryEntry
from utils.utils import ALL_TAGS_PATTERN
from utils.logging_utils import log_debug

class AIPromptComposer(BaseTranslationHandler):
    _TAG_PLACEHOLDER_PREFIX = "__TAG_"
    _GLOSS_PLACEHOLDER_PREFIX = "__GLOS_"
    _PLACEHOLDER_SUFFIX = "__"

    def prepare_text_for_translation(
        self,
        source_text: str,
        glossary_entries: Sequence[GlossaryEntry],
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        # Повертаємо текст як є, без плейсхолдерів
        return source_text or '', {}

    def _inject_glossary_placeholders(
        self,
        text: str,
        glossary_entries: Sequence[GlossaryEntry],
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        return text, {}
    
    def restore_placeholders(
        self,
        translated_text: str,
        placeholder_map: Dict[str, Dict[str, str]],
    ) -> str:
        # Плейсхолдерів більше немає, повертаємо текст як є
        return translated_text or ''
    
    def compose_batch_request(
        self,
        system_prompt: str,
        glossary_text: str,
        source_items: List[Dict],
        *,
        block_idx: Optional[int],
        mode_description: str,
        is_retry: bool = False,
        retry_reason: str = ""
    ) -> Tuple[str, str, Dict]:
        
        json_payload_for_ai = {
            "strings_to_translate": source_items
        }
        
        if not is_retry:
            instructions = [
                "Translate the `text` field for each object in the `strings_to_translate` array into Ukrainian.",
                "Return a single, valid JSON object with a `translated_strings` key.",
                "The value of `translated_strings` must be an array of objects.",
                "Each object in the returned array must have the original `id` (integer) and a `translation` (string) field.",
                "The number of objects in the `translated_strings` array must exactly match the number of objects in the input `strings_to_translate` array.",
                "Follow the rules from the system prompt regarding tags and glossary.",
                "Do not add any explanations or text outside the JSON object."
            ]
        else:
            instructions = [
                "Your previous response was invalid. Please correct it.",
                f"Error: {retry_reason}",
                "Follow these instructions carefully:",
                "Translate the `text` field for each object in the `strings_to_translate` array into Ukrainian.",
                "Return a single, valid JSON object with a `translated_strings` key.",
                "The value of `translated_strings` must be an array of objects.",
                "Each object must have the original `id` and a `translation` field.",
                "The number of objects must match the input.",
                "Follow the rules from the system prompt regarding tags and glossary.",
                "Do not add any explanations or text outside the JSON object."
            ]

        combined_system = system_prompt.strip()
        if glossary_text:
            combined_system = (
                f"{combined_system}\n\n"
                f"GLOSSARY (use with absolute priority):\n{glossary_text.strip()}"
            )
        
        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else "Unknown game"
        context_lines = [
            f"Game: {game_name}",
            f"Mode: {mode_description}"
        ]
        if block_idx is not None:
            block_label = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
            context_lines.append(f"Block: {block_label} (#{block_idx})")

        user_sections = [
            "\n".join(context_lines),
            "INSTRUCTIONS:\n" + "\n".join(f"- {i}" for i in instructions),
            "JSON DATA TO PROCESS:\n" + json.dumps(json_payload_for_ai, indent=2, ensure_ascii=False)
        ]
        user_content = "\n\n".join(user_sections)

        log_debug(f"Composed batch request for AI. System prompt size: {len(combined_system)}, User content size: {len(user_content)}")
        log_debug(f"Full JSON payload sent to AI:\n{json.dumps(json_payload_for_ai, indent=2, ensure_ascii=False)}")
        return combined_system, user_content, {}
    
    def compose_variation_request(
        self,
        system_prompt: str,
        glossary_text: str,
        source_text: str,
        *,
        block_idx: Optional[int],
        string_idx: Optional[int],
        expected_lines: int,
        current_translation: str,
        request_type: str,
        placeholder_map: dict
    ) -> Tuple[str, str, Dict]:
        
        combined_system, user_content = self.compose_messages(
            system_prompt, glossary_text, source_text,
            block_idx=block_idx, string_idx=string_idx, expected_lines=expected_lines,
            mode_description="translation variations", request_type=request_type,
            current_translation=current_translation,
            placeholder_tokens=[]
        )
        return combined_system, user_content, {}

    def compose_messages(
        self,
        system_prompt: str,
        glossary_text: str,
        source_text: str,
        *,
        block_idx: Optional[int],
        string_idx: Optional[int],
        expected_lines: int,
        mode_description: str,
        request_type: str = "translation",
        current_translation: Optional[str] = None,
        placeholder_tokens: Optional[List[str]] = None,
        selected_text_to_vary: Optional[str] = None
    ) -> Tuple[str, str]:
        combined_system = system_prompt.strip()
        if glossary_text:
            combined_system = (
                f"{combined_system}\n\n"
                f"GLOSSARY (use with absolute priority):\n{glossary_text.strip()}"
            )

        context_lines: List[str] = []
        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else "Unknown game"
        context_lines.append(f"Game: {game_name}")
        if block_idx is not None and block_idx != -1:
            block_label = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
            context_lines.append(f"Block: {block_label} (#{block_idx})")
        if string_idx is not None and string_idx != -1:
            context_lines.append(f"Row: #{string_idx}")
        if mode_description:
            context_lines.append(f"Mode: {mode_description}")

        if request_type == "variation_list":
            instructions = [
                "Generate 10 different Ukrainian translation alternatives for the provided text.",
                f"Each option must contain exactly {expected_lines} lines (including empty ones) in the same order.",
                "Follow the glossary and preserve all tags exactly as they appear.",
                "Follow the tone of the original text.",
                "Return the response as a JSON array with 10 strings and no additional commentary.",
            ]
        else:
            instructions = [
                "Translate the text into Ukrainian without altering the meaning.",
                f"Keep exactly {expected_lines} lines (including empty ones) and preserve their order.",
                "Use the provided glossary to translate terms. All other tags must be preserved exactly as they appear.",
                "The glossary has absolute priority.",
                "Do not add explanations or meta text; return only the translation.",
            ]

        user_sections = ["\n".join(context_lines), "\n".join(instructions)]
        if request_type in {"variation_list"} and current_translation:
            user_sections.append("Current translation:")
            user_sections.append(str(current_translation))
        
        user_sections.append("Original text:")
        user_sections.append(source_text)


        user_content = "\n\n".join([section for section in user_sections if section])
        log_debug(f"Composed single-string/variation request for AI. System prompt size: {len(combined_system)}, User content size: {len(user_content)}")
        return combined_system, user_content# handlers/translation/ai_prompt_composer.py ---
import json
import re
from typing import Dict, List, Optional, Sequence, Tuple

from .base_translation_handler import BaseTranslationHandler
from core.glossary_manager import GlossaryEntry
from utils.utils import ALL_TAGS_PATTERN
from utils.logging_utils import log_debug

class AIPromptComposer(BaseTranslationHandler):
    _TAG_PLACEHOLDER_PREFIX = "__TAG_"
    _GLOSS_PLACEHOLDER_PREFIX = "__GLOS_"
    _PLACEHOLDER_SUFFIX = "__"

    def prepare_text_for_translation(
        self,
        source_text: str,
        glossary_entries: Sequence[GlossaryEntry],
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        # Повертаємо текст як є, без плейсхолдерів
        return source_text or '', {}

    def _inject_glossary_placeholders(
        self,
        text: str,
        glossary_entries: Sequence[GlossaryEntry],
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        return text, {}
    
    def restore_placeholders(
        self,
        translated_text: str,
        placeholder_map: Dict[str, Dict[str, str]],
    ) -> str:
        # Плейсхолдерів більше немає, повертаємо текст як є
        return translated_text or ''
    
    def compose_batch_request(
        self,
        system_prompt: str,
        glossary_text: str,
        source_items: List[Dict],
        *,
        block_idx: Optional[int],
        mode_description: str,
        is_retry: bool = False,
        retry_reason: str = ""
    ) -> Tuple[str, str, Dict]:
        
        json_payload_for_ai = {
            "strings_to_translate": source_items
        }
        
        if not is_retry:
            instructions = [
                "Translate the `text` field for each object in the `strings_to_translate` array into Ukrainian.",
                "Return a single, valid JSON object with a `translated_strings` key.",
                "The value of `translated_strings` must be an array of objects.",
                "Each object in the returned array must have the original `id` (integer) and a `translation` (string) field.",
                "The number of objects in the `translated_strings` array must exactly match the number of objects in the input `strings_to_translate` array.",
                "Follow the rules from the system prompt regarding tags and glossary.",
                "Do not add any explanations or text outside the JSON object."
            ]
        else:
            instructions = [
                "Your previous response was invalid. Please correct it.",
                f"Error: {retry_reason}",
                "Follow these instructions carefully:",
                "Translate the `text` field for each object in the `strings_to_translate` array into Ukrainian.",
                "Return a single, valid JSON object with a `translated_strings` key.",
                "The value of `translated_strings` must be an array of objects.",
                "Each object must have the original `id` and a `translation` field.",
                "The number of objects must match the input.",
                "Follow the rules from the system prompt regarding tags and glossary.",
                "Do not add any explanations or text outside the JSON object."
            ]

        combined_system = system_prompt.strip()
        if glossary_text:
            combined_system = (
                f"{combined_system}\n\n"
                f"GLOSSARY (use with absolute priority):\n{glossary_text.strip()}"
            )
        
        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else "Unknown game"
        context_lines = [
            f"Game: {game_name}",
            f"Mode: {mode_description}"
        ]
        if block_idx is not None:
            block_label = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
            context_lines.append(f"Block: {block_label} (#{block_idx})")

        user_sections = [
            "\n".join(context_lines),
            "INSTRUCTIONS:\n" + "\n".join(f"- {i}" for i in instructions),
            "JSON DATA TO PROCESS:\n" + json.dumps(json_payload_for_ai, indent=2, ensure_ascii=False)
        ]
        user_content = "\n\n".join(user_sections)

        log_debug(f"Composed batch request for AI. System prompt size: {len(combined_system)}, User content size: {len(user_content)}")
        log_debug(f"Full JSON payload sent to AI:\n{json.dumps(json_payload_for_ai, indent=2, ensure_ascii=False)}")
        return combined_system, user_content, {}
    
    def compose_variation_request(
        self,
        system_prompt: str,
        glossary_text: str,
        source_text: str,
        *,
        block_idx: Optional[int],
        string_idx: Optional[int],
        expected_lines: int,
        current_translation: str,
        request_type: str,
        placeholder_map: dict
    ) -> Tuple[str, str, Dict]:
        
        combined_system, user_content = self.compose_messages(
            system_prompt, glossary_text, source_text,
            block_idx=block_idx, string_idx=string_idx, expected_lines=expected_lines,
            mode_description="translation variations", request_type=request_type,
            current_translation=current_translation,
            placeholder_tokens=[]
        )
        return combined_system, user_content, {}

    def compose_messages(
        self,
        system_prompt: str,
        glossary_text: str,
        source_text: str,
        *,
        block_idx: Optional[int],
        string_idx: Optional[int],
        expected_lines: int,
        mode_description: str,
        request_type: str = "translation",
        current_translation: Optional[str] = None,
        placeholder_tokens: Optional[List[str]] = None,
        selected_text_to_vary: Optional[str] = None
    ) -> Tuple[str, str]:
        combined_system = system_prompt.strip()
        if glossary_text:
            combined_system = (
                f"{combined_system}\n\n"
                f"GLOSSARY (use with absolute priority):\n{glossary_text.strip()}"
            )

        context_lines: List[str] = []
        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else "Unknown game"
        context_lines.append(f"Game: {game_name}")
        if block_idx is not None and block_idx != -1:
            block_label = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
            context_lines.append(f"Block: {block_label} (#{block_idx})")
        if string_idx is not None and string_idx != -1:
            context_lines.append(f"Row: #{string_idx}")
        if mode_description:
            context_lines.append(f"Mode: {mode_description}")

        if request_type == "variation_list":
            instructions = [
                "Generate 10 different Ukrainian translation alternatives for the provided text.",
                f"Each option must contain exactly {expected_lines} lines (including empty ones) in the same order.",
                "Follow the glossary and preserve all tags exactly as they appear.",
                "Follow the tone of the original text.",
                "Return the response as a JSON array with 10 strings and no additional commentary.",
            ]
        else:
            instructions = [
                "Translate the text into Ukrainian without altering the meaning.",
                f"Keep exactly {expected_lines} lines (including empty ones) and preserve their order.",
                "Use the provided glossary to translate terms. All other tags must be preserved exactly as they appear.",
                "The glossary has absolute priority.",
                "Do not add explanations or meta text; return only the translation.",
            ]

        user_sections = ["\n".join(context_lines), "\n".join(instructions)]
        if request_type in {"variation_list"} and current_translation:
            user_sections.append("Current translation:")
            user_sections.append(str(current_translation))
        
        user_sections.append("Original text:")
        user_sections.append(source_text)


        user_content = "\n\n".join([section for section in user_sections if section])
        log_debug(f"Composed single-string/variation request for AI. System prompt size: {len(combined_system)}, User content size: {len(user_content)}")
        return combined_system, user_content