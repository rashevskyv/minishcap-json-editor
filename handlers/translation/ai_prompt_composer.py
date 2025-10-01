from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence, Tuple

from .base_translation_handler import BaseTranslationHandler
from core.glossary_manager import GlossaryEntry
from utils.utils import ALL_TAGS_PATTERN
from utils.logging_utils import log_debug


class AIPromptComposer(BaseTranslationHandler):
    """Compose prompts for AI translation/variation tasks and manage placeholders."""

    _TAG_PLACEHOLDER_PREFIX = "__TAG_"
    _PLACEHOLDER_SUFFIX = "__"

    # ------------------------------------------------------------------
    # Placeholder helpers
    # ------------------------------------------------------------------
    def _mask_tags(self, text: str) -> Tuple[str, Dict[str, str]]:
        placeholder_map: Dict[str, str] = {}

        def _replacer(match) -> str:
            placeholder = f"{self._TAG_PLACEHOLDER_PREFIX}{len(placeholder_map)}{self._PLACEHOLDER_SUFFIX}"
            placeholder_map[placeholder] = match.group(0)
            return placeholder

        masked = ALL_TAGS_PATTERN.sub(_replacer, text or '')
        return masked, placeholder_map

    def _restore_tag_placeholders(
        self,
        translated_text: str,
        placeholder_map: Optional[Dict],
        *,
        key: Optional[int] = None,
    ) -> str:
        text = translated_text or ''
        if not placeholder_map:
            return text

        tags_map: Dict[str, str] = {}
        if key is not None and isinstance(placeholder_map, dict):
            entry = placeholder_map.get(str(key))
            if isinstance(entry, dict):
                tags_map = entry.get('tags', entry)
        elif isinstance(placeholder_map, dict) and 'tags' in placeholder_map:
            tags_map = placeholder_map.get('tags', {})
        elif isinstance(placeholder_map, dict):
            for value in placeholder_map.values():
                if isinstance(value, dict):
                    tags_map.update(value.get('tags', value))

        for placeholder, original in tags_map.items():
            text = text.replace(placeholder, original)
        return text

    # ------------------------------------------------------------------
    # Public API used by translation handler
    # ------------------------------------------------------------------
    def prepare_text_for_translation(
        self,
        source_text: str,
        glossary_entries: Sequence[GlossaryEntry],  # kept for possible future use
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        masked_text, tag_map = self._mask_tags(source_text or '')
        placeholder_map: Dict[str, Dict[str, str]] = {}
        if tag_map:
            placeholder_map['tags'] = tag_map
        return masked_text, placeholder_map

    def restore_placeholders(
        self,
        translated_text: str,
        placeholder_map: Optional[Dict],
        *,
        key: Optional[int] = None,
    ) -> str:
        return self._restore_tag_placeholders(translated_text, placeholder_map, key=key)

    # ------------------------------------------------------------------
    # Prompt composition helpers
    # ------------------------------------------------------------------
    def compose_batch_request(
        self,
        system_prompt: str,
        glossary_text: str,
        source_items: List[Dict],
        *,
        block_idx: Optional[int],
        mode_description: str,
        is_retry: bool = False,
        retry_reason: str = '',
    ) -> Tuple[str, str, Dict[str, Dict[str, Dict[str, str]]]]:
        processed_items: List[Dict] = []
        placeholder_map: Dict[str, Dict[str, Dict[str, str]]] = {}

        for item in source_items:
            item_id = item.get('id')
            original_text = str(item.get('text') or '')
            masked_text, tag_map = self._mask_tags(original_text)
            new_item = dict(item)
            new_item['text'] = masked_text
            processed_items.append(new_item)
            if tag_map and item_id is not None:
                placeholder_map[str(item_id)] = {'tags': tag_map}

        json_payload_for_ai = {'strings_to_translate': processed_items}

        if not is_retry:
            instructions = [
                'Translate the "text" field for each object in the "strings_to_translate" array into Ukrainian.',
                'Return a single, valid JSON object with a "translated_strings" key.',
                'The value of "translated_strings" must be an array of objects.',
                'Each object in the returned array must have the original "id" (integer) and a "translation" (string) field.',
                'The number of objects in the "translated_strings" array must exactly match the number of objects provided in the input array.',
                'Follow the rules from the system prompt regarding tags and glossary.',
                'Do not add any explanations or text outside the JSON object.',
            ]
        else:
            instructions = [
                'Your previous response was invalid. Please correct it.',
                f'Error: {retry_reason}',
                'Follow these instructions carefully:',
                'Translate the "text" field for each object in the "strings_to_translate" array into Ukrainian.',
                'Return a single, valid JSON object with a "translated_strings" key.',
                'The value of "translated_strings" must be an array of objects.',
                'Each object must have the original "id" and a "translation" field.',
                'The number of objects must match the input.',
                'Follow the rules from the system prompt regarding tags and glossary.',
                'Do not add any explanations or text outside the JSON object.',
            ]

        combined_system = self._append_glossary_to_system_prompt(system_prompt, glossary_text)

        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else 'Unknown game'
        context_lines = [
            f'Game: {game_name}',
            f'Mode: {mode_description}',
        ]
        if block_idx is not None:
            block_label = self.mw.block_names.get(str(block_idx), f'Block {block_idx}')
            context_lines.append(f'Block: {block_label} (#{block_idx})')

        user_sections = [
            '\n'.join(context_lines),
            'INSTRUCTIONS:\n' + '\n'.join(f'- {instr}' for instr in instructions),
            'JSON DATA TO PROCESS:\n' + json.dumps(json_payload_for_ai, indent=2, ensure_ascii=False),
        ]
        user_content = '\n\n'.join(user_sections)

        log_debug(
            f'Composed batch request for AI. System prompt size: {len(combined_system)}, '
            f'User content size: {len(user_content)}'
        )
        return combined_system, user_content, placeholder_map

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
        placeholder_map: Dict,
        mode_description: str = 'translation variations',
    ) -> Tuple[str, str, Dict]:
        combined_system, user_content = self.compose_messages(
            system_prompt,
            glossary_text,
            source_text,
            block_idx=block_idx,
            string_idx=string_idx,
            expected_lines=expected_lines,
            mode_description=mode_description,
            request_type=request_type,
            current_translation=current_translation,
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
        request_type: str = 'translation',
        current_translation: Optional[str] = None,
    ) -> Tuple[str, str]:
        combined_system = self._append_glossary_to_system_prompt(system_prompt, glossary_text)

        context_lines: List[str] = []
        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else 'Unknown game'
        context_lines.append(f'Game: {game_name}')
        if block_idx is not None and block_idx != -1:
            block_label = self.mw.block_names.get(str(block_idx), f'Block {block_idx}')
            context_lines.append(f'Block: {block_label} (#{block_idx})')
        if string_idx is not None and string_idx != -1:
            context_lines.append(f'Row: #{string_idx}')
        if mode_description:
            context_lines.append(f'Mode: {mode_description}')

        if request_type == 'variation_list':
            instructions = [
                'Generate 10 different Ukrainian translation alternatives for the provided text.',
                f'Each option must contain exactly {expected_lines} lines (including empty ones) in the same order.',
                'Follow the glossary and preserve all tags exactly as they appear.',
                'Follow the tone of the original text.',
                'Return the response as a JSON array with 10 strings and no additional commentary.',
            ]
        elif request_type == 'glossary_notes_variation':
            instructions = [
                'Generate 5 alternative Ukrainian glossary descriptions for the provided term.',
                'Each description should be 1-2 sentences and stay under 60 words.',
                'Preserve any tags/placeholders exactly as provided.',
                'Keep the description informative and suitable for a glossary entry.',
                'Return the response as a JSON array with 5 strings and no additional commentary.',
            ]
        else:
            instructions = [
                'Translate the text into Ukrainian without altering the meaning.',
                f'Keep exactly {expected_lines} lines (including empty ones) and preserve their order.',
                'Use the provided glossary to translate terms. All other tags must be preserved exactly as they appear.',
                'The glossary has absolute priority.',
                'Do not add explanations or meta text; return only the translation.',
            ]

        user_sections: List[str] = ['\n'.join(context_lines), '\n'.join(instructions)]
        if request_type == 'variation_list' and current_translation:
            user_sections.append('Current translation:')
            user_sections.append(str(current_translation))
        elif request_type == 'glossary_notes_variation' and current_translation is not None:
            user_sections.append('Current description:')
            user_sections.append(str(current_translation or '(empty)'))

        user_sections.append('Input text:')
        user_sections.append(source_text)

        user_content = '\n\n'.join([section for section in user_sections if section])
        log_debug(
            f'Composed request for AI. Type={request_type}, System prompt size={len(combined_system)}, '
            f'User content size={len(user_content)}'
        )
        return combined_system, user_content

    def compose_glossary_occurrence_update_request(
        self,
        system_prompt: str,
        glossary_text: str,
        *,
        source_text: str,
        placeholder_map: Dict,
        current_translation: str,
        original_text: str,
        term: str,
        old_translation: str,
        new_translation: str,
        expected_lines: int,
    ) -> Tuple[str, str, Dict]:
        combined_system = self._append_glossary_to_system_prompt(system_prompt, glossary_text)

        instructions = [
            "Update the existing Ukrainian translation to reflect the new glossary term translation.",
            "Preserve all tags, placeholders, punctuation, whitespace, and line breaks exactly as in the input.",
            f"Keep the total number of lines at {expected_lines}; do not add or remove lines.",
            "Use the new glossary translation naturally (adjust case/grammar if required by context).",
            "Return JSON only: {\"translation\": \"...\"} with the updated Ukrainian text.",
        ]

        user_sections = [
            "Context:",
            f"Term: {term}",
            f"Old translation: {old_translation or '[empty]'}",
            f"New translation: {new_translation or '[empty]'}",
            "",
            "Original text (reference only, do not translate it):",
            original_text or '[none]',
            "",
            "Current translation (update this, keep formatting):",
            source_text or '',
            "",
            "Instructions:",
            "\n".join(f"- {item}" for item in instructions),
        ]
        user_content = "\n".join(user_sections)
        return combined_system, user_content, placeholder_map or {}

    def compose_glossary_request(self, system_prompt: str, user_content: str, **_: Dict) -> Tuple[str, str]:
        return system_prompt.strip(), user_content

    @staticmethod
    def _append_glossary_to_system_prompt(system_prompt: str, glossary_text: str) -> str:
        system_prompt = (system_prompt or '').strip()
        if glossary_text:
            return (
                f"{system_prompt}\n\n"
                f"GLOSSARY (use with absolute priority):\n{glossary_text.strip()}"
            )
        return system_prompt
