# -*- coding: utf-8 -*-
"""Glossary management helpers: loading, caching, and pattern matching."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import re
import unicodedata

from utils.logging_utils import log_debug


@dataclass(frozen=True)
class GlossaryEntry:
    """Single glossary record."""

    original: str
    translation: str
    notes: str = ""
    section: Optional[str] = None

    def is_valid(self) -> bool:
        return bool(self.original and self.translation)


@dataclass(frozen=True)
class GlossaryMatch:
    """Result of matching a glossary entry inside text."""

    entry: GlossaryEntry
    start: int
    end: int


@dataclass(frozen=True)
class GlossaryOccurrence:
    """Specific occurrence of a glossary entry in project data."""

    entry: GlossaryEntry
    block_idx: int
    string_idx: int
    line_idx: int
    start: int
    end: int
    line_text: str


class GlossaryManager:
    """Load and cache glossary entries for a plugin with search utilities."""

    def __init__(self) -> None:
        self._entries: List[GlossaryEntry] = []
        self._raw_text: str = ""
        self._compiled_patterns: Dict[str, re.Pattern[str]] = {}
        self._glossary_path: Optional[Path] = None
        self._plugin_name: Optional[str] = None
        self._occurrence_index: Dict[str, List[GlossaryOccurrence]] = {}

    @staticmethod
    def normalize_term(value: str) -> str:
        if value is None:
            return ""
        cleaned = unicodedata.normalize('NFKD', value)
        stripped = ''.join(ch for ch in cleaned if not unicodedata.combining(ch))
        stripped = stripped.lower()
        stripped = re.sub(r"\s+", " ", stripped)
        return stripped.strip()

    def load_from_text(
        self,
        *,
        plugin_name: Optional[str],
        glossary_path: Optional[Path],
        raw_text: str,
    ) -> None:
        """Populate glossary from text buffer."""
        self._plugin_name = plugin_name
        self._glossary_path = glossary_path
        self._raw_text = raw_text or ""
        self._entries = self._parse_markdown(self._raw_text)
        self._build_pattern_cache()
        log_debug(
            f"GlossaryManager: loaded {len(self._entries)} entries for plugin "
            f"{plugin_name or '<global>'} from {str(glossary_path) if glossary_path else '<memory>'}"
        )

    def refresh_from_disk(self) -> None:
        if self._glossary_path and self._glossary_path.exists():
            text = self._glossary_path.read_text(encoding='utf-8')
            self.load_from_text(
                plugin_name=self._plugin_name,
                glossary_path=self._glossary_path,
                raw_text=text,
            )
        else:
            # No glossary file — reset cache to empty
            self.load_from_text(
                plugin_name=self._plugin_name,
                glossary_path=self._glossary_path,
                raw_text="",
            )

    def get_raw_text(self) -> str:
        return self._raw_text

    def get_entries(self) -> Sequence[GlossaryEntry]:
        return list(self._entries)

    def get_entries_sorted_by_length(self) -> Sequence[GlossaryEntry]:
        return sorted(self._entries, key=lambda item: len(item.original or ""), reverse=True)

    def get_compiled_pattern(self, entry: GlossaryEntry) -> Optional[re.Pattern[str]]:
        if not entry or not entry.original:
            return None
        return self._compiled_patterns.get(entry.original)

    def iter_compiled(self) -> Iterable[Tuple[GlossaryEntry, re.Pattern[str]]]:
        for entry in self._entries:
            pattern = self._compiled_patterns.get(entry.original)
            if pattern:
                yield entry, pattern

    def find_matches(self, text: str) -> List[GlossaryMatch]:
        if not text:
            return []
        matches: List[GlossaryMatch] = []
        for entry, pattern in self.iter_compiled():
            for match in pattern.finditer(text):
                matches.append(GlossaryMatch(entry=entry, start=match.start(), end=match.end()))
        return matches

    def build_occurrence_index(self, dataset: Sequence) -> Dict[str, List[GlossaryOccurrence]]:
        occurrences: Dict[str, List[GlossaryOccurrence]] = {entry.original: [] for entry in self._entries}
        if not dataset:
            self._occurrence_index = occurrences
            return occurrences

        compiled_entries = list(self.iter_compiled())
        if not compiled_entries:
            self._occurrence_index = occurrences
            return occurrences

        for block_idx, block in enumerate(dataset):
            if not isinstance(block, list):
                continue
            for string_idx, value in enumerate(block):
                text = '' if value is None else str(value)
                if not text:
                    continue
                lines = text.split('\n')
                for line_idx, line in enumerate(lines):
                    if not line:
                        continue
                    for entry, pattern in compiled_entries:
                        for match in pattern.finditer(line):
                            occ = GlossaryOccurrence(
                                entry=entry,
                                block_idx=block_idx,
                                string_idx=string_idx,
                                line_idx=line_idx,
                                start=match.start(),
                                end=match.end(),
                                line_text=line,
                            )
                            occurrences.setdefault(entry.original, []).append(occ)

        self._occurrence_index = occurrences
        return occurrences

    def get_occurrences_for(self, entry: GlossaryEntry) -> List[GlossaryOccurrence]:
        if entry is None or not entry.original:
            return []
        return list(self._occurrence_index.get(entry.original, []))

    def get_occurrence_map(self) -> Dict[str, List[GlossaryOccurrence]]:
        return {key: list(value) for key, value in self._occurrence_index.items()}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _parse_markdown(self, text: str) -> List[GlossaryEntry]:
        if not text:
            return []
        entries: List[GlossaryEntry] = []
        current_section: Optional[str] = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('## '):
                current_section = line[3:].strip()
                continue
            if not line.startswith('|') or line.startswith('|-'):
                continue
            parts = [part.strip() for part in line.strip('|').split('|')]
            if len(parts) < 3:
                continue
            header_check = [p.lower() for p in parts[:3]]
            if header_check[0] in {'original', 'оригінал'} and header_check[1] in {'translation', 'переклад'}:
                continue
            original, translation = parts[0], parts[1]
            notes = parts[2] if len(parts) >= 3 else ""
            entry = GlossaryEntry(original=original, translation=translation, notes=notes, section=current_section)
            if entry.is_valid():
                entries.append(entry)
        return entries

    def _build_pattern_cache(self) -> None:
        self._compiled_patterns.clear()
        for entry in self._entries:
            if not entry.original:
                continue
            pattern = self._build_regex(entry.original)
            self._compiled_patterns[entry.original] = pattern

    @classmethod
    def _build_regex(cls, term: str) -> re.Pattern[str]:
        escaped = re.escape(term)
        # Allow flexible whitespace matching inside the term
        escaped = escaped.replace(r"\ ", r"\s+")
        prefix = ''
        suffix = ''
        if term and term[0].isalnum():
            prefix = r'(?<!\w)'
        if term and term[-1].isalnum():
            suffix = r'(?!\w)'
        pattern = f"{prefix}{escaped}{suffix}"
        return re.compile(pattern, re.IGNORECASE)
