# --- START OF FILE core/translation/session_manager.py ---

"""Session manager for chat-based translation providers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


MAX_HISTORY_MESSAGES = 20  # user+assistant pairs


@dataclass
class TranslationSessionState:
    """Active provider session state."""

    provider_key: str
    system_content: str
    conversation_id: Optional[str] = None
    bootstrapped: bool = False
    glossary_sent: bool = False
    history: List[Dict[str, str]] = field(default_factory=list)
    session_instructions: str = ""
    bootstrap_viewed: bool = False

    def set_instructions(self, instructions: str) -> None:
        self.session_instructions = (instructions or "").strip()

    def prepare_request(
        self, user_message: Dict[str, str]
    ) -> Tuple[List[Dict[str, str]], Optional[Dict[str, str]]]:
        """Return request messages and optional session payload."""
        message_copy = {"role": user_message["role"], "content": user_message["content"]}
        if not self.bootstrapped:
            return [
                {"role": "system", "content": self.system_content},
                message_copy,
            ], None
        if self.conversation_id:
            return [message_copy], {"conversation_id": self.conversation_id}
        history_copy = [{"role": item["role"], "content": item["content"]} for item in self.history]
        if history_copy:
            return [*history_copy, message_copy], None
        return [message_copy], None

    def record_exchange(
        self,
        *,
        user_content: str,
        assistant_content: str,
        conversation_id: Optional[str],
    ) -> None:
        """Record the exchange and persist the conversation identifier."""
        self.bootstrapped = True
        if conversation_id:
            self.conversation_id = conversation_id
        self.history.append({"role": "user", "content": user_content})
        self.history.append({"role": "assistant", "content": assistant_content})
        if len(self.history) > (MAX_HISTORY_MESSAGES * 2):
            self.history = self.history[-(MAX_HISTORY_MESSAGES * 2):]


class TranslationSessionManager:
    """Manage creation and reset of translation sessions."""

    def __init__(self) -> None:
        self._state: Optional[TranslationSessionState] = None

    def reset(self) -> None:
        self._state = None

    def ensure_session(
        self,
        *,
        provider_key: str,
        system_content: str,
        supports_sessions: bool,
    ) -> Optional[TranslationSessionState]:
        if not supports_sessions:
            self._state = None
            return None

        normalized = system_content.strip()
        if self._state:
            if (
                self._state.provider_key != provider_key
                or self._state.system_content != normalized
            ):
                self._state = None

        if not self._state:
            self._state = TranslationSessionState(
                provider_key=provider_key,
                system_content=normalized,
            )
        return self._state

    def get_state(self) -> Optional[TranslationSessionState]:
        return self._state
