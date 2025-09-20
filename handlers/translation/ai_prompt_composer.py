# --- START OF FILE handlers/translation/ai_prompt_composer.py ---

# handlers/translation/ai_prompt_composer.py
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

        if request_type == "variation":
            instructions = [
                "Create an alternative Ukrainian translation based on the original text.",
                f"Keep exactly {expected_lines} lines (including empty ones) and preserve their order.",
                "Preserve all tags, placeholders, spaces, and punctuation in their original positions.",
                "Follow the glossary terminology and the game's style.",
                "The variation must differ from the current translation while staying semantically accurate.",
                "Do not add comments or meta text; return only the translation.",
            ]
        elif request_type == "variation_list":
            instructions = [
                "Generate 10 different Ukrainian translation alternatives for the provided text.",
                f"Each option must contain exactly {expected_lines} lines (including empty ones) in the same order.",
                "Preserve all tags, placeholders, markup, spaces, and punctuation in their original positions.",
                "Follow the glossary and the tone of the original text.",
                "Return the response as a JSON array with 10 strings and no additional commentary.",
            ]
        elif request_type == "inline_variation":
            instructions = [
                "Generate 10 different Ukrainian alternatives for the specified text segment.",
                "The full text is provided for context. Only modify the segment.",
                "Preserve all tags, placeholders, spaces, and punctuation within the segment.",
                "Return the response as a JSON array of 10 strings, where each string is just the translated segment.",
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
        if request_type in {"variation", "variation_list"} and current_translation:
            user_sections.append("Current translation:")
            user_sections.append(str(current_translation))
        
        if request_type == "inline_variation":
            user_sections.append("Full text (for context):")
            user_sections.append(source_text)
            if selected_text_to_vary:
                user_sections.append("Segment to vary:")
                user_sections.append(selected_text_to_vary)
        else:
            user_sections.append("Original text:")
            user_sections.append(source_text)


        user_content = "\n\n".join([section for section in user_sections if section])
        return combined_system, user_content