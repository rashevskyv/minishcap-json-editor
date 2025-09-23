# --- START OF FILE handlers/translation/ai_prompt_composer.py ---
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
        if source_text is None:
            return '', {}

        placeholder_map: Dict[str, Dict[str, str]] = {}
        tag_index = 0

        def _replace_tag(match: re.Match) -> str:
            nonlocal tag_index
            placeholder = (
                f"{self._TAG_PLACEHOLDER_PREFIX}{tag_index}{self._PLACEHOLDER_SUFFIX}"
            )
            placeholder_map[placeholder] = {
                'type': 'tag',
                'value': match.group(0),
            }
            tag_index += 1
            return placeholder

        tagged_text = ALL_TAGS_PATTERN.sub(_replace_tag, source_text)

        prepared_text, glossary_placeholders = self._inject_glossary_placeholders(
            tagged_text,
            glossary_entries,
        )
        placeholder_map.update(glossary_placeholders)

        if placeholder_map:
            log_debug(
                f"AIPromptComposer: prepared {len(placeholder_map)} placeholders before translation."
            )
        return prepared_text, placeholder_map

    def _inject_glossary_placeholders(
        self,
        text: str,
        glossary_entries: Sequence[GlossaryEntry],
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        if not text:
            return '', {}

        placeholder_map: Dict[str, Dict[str, str]] = {}
        counter = 0
        working_text = text

        for entry in glossary_entries:
            if not entry.original:
                continue
            pattern = self.main_handler._glossary_manager.get_compiled_pattern(entry)
            if not pattern:
                continue

            def _replace(match: re.Match) -> str:
                nonlocal counter
                placeholder = (
                    f"{self._GLOSS_PLACEHOLDER_PREFIX}{counter}{self._PLACEHOLDER_SUFFIX}"
                )
                placeholder_map[placeholder] = {
                    'type': 'glossary',
                    'value': entry.translation,
                    'original': entry.original,
                }
                counter += 1
                return placeholder

            working_text, replaced = pattern.subn(_replace, working_text)
            if replaced:
                log_debug(
                    f"AIPromptComposer: replaced {replaced} occurrences of glossary term '{entry.original}' with placeholders."
                )

        return working_text, placeholder_map
    
    def restore_placeholders(
        self,
        translated_text: str,
        placeholder_map: Dict[str, Dict[str, str]],
    ) -> str:
        if not placeholder_map:
            return translated_text or ''

        restored = translated_text or ''
        for placeholder, info in placeholder_map.items():
            replacement = info.get('value', '')
            if placeholder not in restored:
                log_debug(
                    f"AIPromptComposer: placeholder '{placeholder}' missing in response; leaving value unchanged."
                )
                continue
            restored = restored.replace(placeholder, replacement)
        return restored
    
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
        payload_strings = []
        full_placeholder_map = {}
        glossary_entries = self.main_handler._glossary_manager.get_entries_sorted_by_length()

        for item in source_items:
            prepared_text, placeholder_map = self.prepare_text_for_translation(
                item["text"], glossary_entries
            )
            payload_strings.append({"id": item["id"], "text": prepared_text})
            full_placeholder_map.update(placeholder_map)

        json_payload_for_ai = {
            "strings_to_translate": payload_strings,
            "placeholder_map": {
                k: v for k, v in full_placeholder_map.items()
            }
        }
        
        if not is_retry:
            instructions = [
                "Translate the `text` field for each object in the `strings_to_translate` array into Ukrainian.",
                "Return a single, valid JSON object with a `translated_strings` key.",
                "The value of `translated_strings` must be an array of objects.",
                "Each object in the returned array must have the original `id` (integer) and a `translation` (string) field.",
                "The number of objects in the `translated_strings` array must exactly match the number of objects in the input `strings_to_translate` array.",
                "Preserve all placeholder tokens (e.g., __TAG_0__, __GLOSS_1__) and their positions in the translated text.",
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
                "Preserve all placeholder tokens.",
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
        return combined_system, user_content, full_placeholder_map
    
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
        
        current_translation_prepared, _ = self.prepare_text_for_translation(str(current_translation), [])

        combined_system, user_content = self.compose_messages(
            system_prompt, glossary_text, source_text,
            block_idx=block_idx, string_idx=string_idx, expected_lines=expected_lines,
            mode_description="translation variations", request_type=request_type,
            current_translation=current_translation_prepared,
            placeholder_tokens=list(placeholder_map.keys())
        )
        return combined_system, user_content, placeholder_map

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
                "Preserve all tags, placeholders, markup, spaces, and punctuation in their original positions.",
                "Follow the glossary and the tone of the original text.",
                "Return the response as a JSON array with 10 strings and no additional commentary.",
            ]
        else:
            instructions = [
                "Translate the text into Ukrainian without altering the meaning.",
                f"Keep exactly {expected_lines} lines (including empty ones) and preserve their order.",
                "Preserve all tags, placeholders, markup, spaces, and punctuation.",
                "The glossary has absolute priority.",
                "Do not add explanations or meta text; return only the translation.",
            ]

        if placeholder_tokens:
            sample_tokens = placeholder_tokens[:4]
            sample_display = ', '.join(sample_tokens)
            if len(placeholder_tokens) > 4:
                sample_display += ', ...'
            instructions.append(
                (
                    "Leave the markers "
                    f"{sample_display} unchanged - they will be automatically restored after translation."
                )
            )

        user_sections = ["\n".join(context_lines), "\n".join(instructions)]
        if request_type in {"variation_list"} and current_translation:
            user_sections.append("Current translation:")
            user_sections.append(str(current_translation))
        
        user_sections.append("Original text:")
        user_sections.append(source_text)


        user_content = "\n\n".join([section for section in user_sections if section])
        log_debug(f"Composed single-string/variation request for AI. System prompt size: {len(combined_system)}, User content size: {len(user_content)}")
        return combined_system, user_content