import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import requests

class TranslationProviderError(Exception):
    """Raised when the translation provider fails to return a valid response."""


@dataclass
class ProviderResponse:
    """Контейнер для результату провайдера разом з метаданими сесії."""

    text: str
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None


class BaseTranslationProvider:
    supports_sessions: bool = False

    def translate(
        self,
        messages: List[Dict[str, str]],
        *,
        session: Optional[Dict[str, str]] = None,
    ) -> ProviderResponse:
        raise NotImplementedError


class OpenAIChatProvider(BaseTranslationProvider):
    def __init__(
        self,
        api_key: str,
        base_url: Optional[str],
        model: str,
        temperature: float,
        max_output_tokens: Optional[int],
        timeout: float,
        extra_headers: Optional[Dict[str, str]] = None,
        extra_payload: Optional[Dict[str, Any]] = None,
        supports_sessions: bool = False,
        conversation_arguments: Optional[List[str]] = None,
    ) -> None:
        if not api_key:
            raise TranslationProviderError("OpenAI Chat provider requires an API key.")
        self.api_key = api_key
        base = (base_url or "https://api.openai.com/v1").rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        self.base_url = base
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens if max_output_tokens and max_output_tokens > 0 else None
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self.extra_payload = {k: v for k, v in (extra_payload or {}).items() if v not in (None, "")}
        self.supports_sessions = supports_sessions
        self._conversation_arguments = list(conversation_arguments or [])

    def _extract_conversation_id(self, payload: Dict[str, Any]) -> Optional[str]:
        for key in ("conversation_id", "conversationId", "conversation"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict):
                nested = value.get("id") or value.get("conversation_id")
                if isinstance(nested, str) and nested:
                    return nested
        session_payload = payload.get("session")
        if isinstance(session_payload, dict):
            for key in ("conversation_id", "id"):
                value = session_payload.get(key)
                if isinstance(value, str) and value:
                    return value
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    for key in ("conversation_id", "conversationId"):
                        value = message.get(key)
                        if isinstance(value, str) and value:
                            return value
                    conv = message.get("conversation")
                    if isinstance(conv, dict):
                        nested = conv.get("id") or conv.get("conversation_id")
                        if isinstance(nested, str) and nested:
                            return nested
        return None

    def translate(
        self,
        messages: List[Dict[str, str]],
        *,
        session: Optional[Dict[str, str]] = None,
    ) -> ProviderResponse:
        url = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": messages,
            "n": 1,
        }
        if self.max_output_tokens:
            payload["max_tokens"] = self.max_output_tokens
        if self.extra_payload:
            payload.update(self.extra_payload)
        if self.supports_sessions and session:
            conversation_id = session.get("conversation_id")
            if conversation_id:
                for key in self._conversation_arguments:
                    payload[key] = conversation_id

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.extra_headers)

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise TranslationProviderError(f"Помилка мережі під час звернення до OpenAI: {exc}") from exc

        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("error", {}).get("message") or error_data
            except ValueError:
                message = response.text
            raise TranslationProviderError(f"OpenAI повернув помилку {response.status_code}: {message}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise TranslationProviderError("OpenAI повернув невалідний JSON.") from exc

        try:
            message = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationProviderError("Відповідь OpenAI не містить тексту перекладу.") from exc

        return ProviderResponse(
            text=message,
            conversation_id=self._extract_conversation_id(payload) if self.supports_sessions else None,
            message_id=payload.get("id"),
            raw_payload=payload,
        )


class OllamaChatProvider(BaseTranslationProvider):
    def __init__(
        self,
        base_url: Optional[str],
        model: str,
        temperature: float,
        timeout: float,
        keep_alive: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.keep_alive = keep_alive or ""
        self.extra_headers = extra_headers or {}

    def translate(
        self,
        messages: List[Dict[str, str]],
        *,
        session: Optional[Dict[str, str]] = None,
    ) -> ProviderResponse:
        url = f"{self.base_url}/api/chat"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        options: Dict[str, Any] = {}
        if self.temperature is not None:
            options["temperature"] = self.temperature
        if options:
            payload["options"] = options
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive

        headers = {"Content-Type": "application/json"}
        headers.update(self.extra_headers)

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise TranslationProviderError(f"Помилка мережі під час звернення до Ollama: {exc}") from exc

        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("error") or error_data
            except ValueError:
                message = response.text
            raise TranslationProviderError(f"Ollama повернула помилку {response.status_code}: {message}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise TranslationProviderError("Ollama повернула невалідний JSON.") from exc

        if "error" in payload:
            raise TranslationProviderError(f"Ollama повідомила про помилку: {payload['error']}")

        try:
            message = payload["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise TranslationProviderError("Відповідь Ollama не містить тексту перекладу.") from exc
        return ProviderResponse(text=message, raw_payload=payload)


def _parse_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else None
    except (TypeError, ValueError):
        return None


def create_translation_provider(provider_name: str, config: Dict[str, Any]) -> BaseTranslationProvider:
    key = (provider_name or "").strip().lower()
    if key in ("openai", "openai_chat", "chatmock"):
        api_key = config.get("api_key") or ""
        if not api_key and config.get("api_key_env"):
            api_key = os.environ.get(str(config.get("api_key_env"))) or ""
        if not api_key and key == "chatmock":
            api_key = "chatmock-placeholder"
        extra_payload: Dict[str, Any] = {}
        for field in ("reasoning_effort", "reasoning_summary", "reasoning_compat"):
            value = config.get(field)
            if value:
                extra_payload[field] = value
        custom_extra = config.get("extra_payload")
        if isinstance(custom_extra, dict):
            extra_payload.update(custom_extra)
        supports_sessions = key == "chatmock"
        conversation_arguments = ["conversation", "conversation_id"] if supports_sessions else []
        return OpenAIChatProvider(
            api_key=api_key,
            base_url=config.get("base_url"),
            model=str(config.get("model", "gpt-4o-mini")),
            temperature=float(config.get("temperature", 0.0)),
            max_output_tokens=_parse_int(config.get("max_output_tokens")),
            timeout=float(config.get("timeout", 60)),
            extra_headers=config.get("extra_headers"),
            extra_payload=extra_payload or None,
            supports_sessions=supports_sessions,
            conversation_arguments=conversation_arguments,
        )
    if key in ("ollama", "ollama_chat"):
        return OllamaChatProvider(
            base_url=config.get("base_url"),
            model=str(config.get("model", "llama3")),
            temperature=float(config.get("temperature", 0.0)),
            timeout=float(config.get("timeout", 60)),
            keep_alive=config.get("keep_alive"),
            extra_headers=config.get("extra_headers"),
        )
    raise TranslationProviderError(f"Невідомий провайдер AI-перекладу: {provider_name}")
