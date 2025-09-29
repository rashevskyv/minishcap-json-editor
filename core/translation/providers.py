# --- START OF FILE core/translation/providers.py ---

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
import requests
from requests import Timeout
import os

from utils.logging_utils import log_debug

class TranslationProviderError(Exception):
    """Custom exception for provider-related errors."""
    pass

@dataclass
class ProviderResponse:
    """Standardized response from a translation provider."""
    text: Optional[str] = None
    raw_payload: Any = None
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None

class BaseTranslationProvider:
    """Abstract base class for all translation providers."""
    def __init__(self, settings: Dict[str, Any]) -> None:
        self.settings = settings

    def translate(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        raise NotImplementedError

class OpenAIChatProvider(BaseTranslationProvider):
    """Provider for OpenAI-compatible chat completion APIs."""
    def __init__(self, settings: Dict[str, Any]) -> None:
        super().__init__(settings)
        self.api_key = self.settings.get('api_key') or os.getenv(str(self.settings.get('api_key_env')))
        self.base_url = (self.settings.get('base_url') or "https://api.openai.com/v1").rstrip('/')
        self.model = self.settings.get('model')
        if not self.api_key:
            raise TranslationProviderError("OpenAI API key is not set.")
        if not self.model:
            raise TranslationProviderError("OpenAI model is not set.")

    def _prepare_body(self, messages: List[Dict[str, str]], current_settings: Dict[str, Any]) -> Dict[str, Any]:
        body: Dict[str, Any] = {"model": self.model, "messages": messages}
        if isinstance(current_settings.get('temperature'), (float, int)):
            body['temperature'] = current_settings['temperature']
        if isinstance(current_settings.get('max_output_tokens'), int) and current_settings['max_output_tokens'] > 0:
            body['max_tokens'] = current_settings['max_output_tokens']
        return body

    def translate(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        extra_headers = current_settings.get('extra_headers')
        if isinstance(extra_headers, dict):
            headers.update(extra_headers)

        body = self._prepare_body(messages, current_settings)
        
        timeout = 60
        if isinstance(current_settings.get('timeout'), int) and current_settings['timeout'] > 0:
            timeout = current_settings['timeout']

        try:
            response = requests.post(endpoint, headers=headers, json=body, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            text = data['choices'][0]['message']['content'] if data.get('choices') else None
            return ProviderResponse(text=text, raw_payload=data)
        except Timeout:
            raise TranslationProviderError(f"Request timed out after {timeout} seconds.")
        except requests.RequestException as e:
            raise TranslationProviderError(f"API request failed: {e}")

class OpenAIResponsesProvider(BaseTranslationProvider):
    """Provider for the new OpenAI /v1/responses API (e.g., for gpt-5)."""
    def __init__(self, settings: Dict[str, Any]) -> None:
        super().__init__(settings)
        self.api_key = self.settings.get('api_key') or os.getenv(str(self.settings.get('api_key_env')))
        self.base_url = (self.settings.get('base_url') or "https://api.openai.com/v1").rstrip('/')
        self.model = self.settings.get('model')
        if not self.api_key:
            raise TranslationProviderError("OpenAI API key for Responses API is not set.")
        if not self.model:
            raise TranslationProviderError("OpenAI model for Responses API is not set.")

    def translate(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        endpoint = f"{self.base_url}/responses"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        system_prompt = next((m['content'] for m in messages if m['role'] == 'system'), "")
        user_prompt = next((m['content'] for m in messages if m['role'] == 'user'), "")
        full_input = f"{system_prompt}\n\n{user_prompt}".strip()

        body: Dict[str, Any] = {
            "model": self.model,
            "input": full_input,
            "reasoning": {"effort": current_settings.get("reasoning_effort", "low")},
            "text": {"verbosity": current_settings.get("text_verbosity", "low")}
        }
        
        timeout = 120
        if isinstance(current_settings.get('timeout'), int) and current_settings['timeout'] > 0:
            timeout = current_settings['timeout']

        try:
            response = requests.post(endpoint, headers=headers, json=body, timeout=timeout)
            log_debug(f"OpenAIResponsesProvider RAW response: STATUS={response.status_code}, BODY={response.text}")
            response.raise_for_status()
            data = response.json()
            
            text = None
            if data and isinstance(data.get('output'), list) and len(data['output']) > 1:
                message_part = data['output'][1]
                if (message_part.get('type') == 'message' and
                        isinstance(message_part.get('content'), list) and
                        message_part['content']):
                    text_content = message_part['content'][0]
                    if text_content.get('type') == 'output_text':
                        text = text_content.get('text')
            
            return ProviderResponse(text=text, raw_payload=data)
        except Timeout:
            raise TranslationProviderError(f"Request timed out after {timeout} seconds.")
        except requests.RequestException as e:
            raise TranslationProviderError(f"API request failed for Responses API: {e}")

class OllamaChatProvider(BaseTranslationProvider):
    """Provider for Ollama chat APIs."""
    def __init__(self, settings: Dict[str, Any]) -> None:
        super().__init__(settings)
        self.base_url = (self.settings.get('base_url') or "http://localhost:11434").rstrip('/')
        self.model = self.settings.get('model')
        if not self.model:
            raise TranslationProviderError("Ollama model is not set.")

    def translate(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        endpoint = f"{self.base_url}/api/chat"
        headers = {"Content-Type": "application/json"}

        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        extra_headers = current_settings.get('extra_headers')
        if isinstance(extra_headers, dict):
            headers.update(extra_headers)
        
        system_prompt = next((m['content'] for m in messages if m['role'] == 'system'), None)
        user_prompts = [m for m in messages if m['role'] != 'system']

        body: Dict[str, Any] = {"model": self.model, "messages": user_prompts, "stream": False}
        if system_prompt:
            body['system'] = system_prompt
        
        options: Dict[str, Any] = {}
        if isinstance(current_settings.get('temperature'), (float, int)):
            options['temperature'] = current_settings['temperature']
        if options:
            body['options'] = options
        
        if current_settings.get('keep_alive'):
            body['keep_alive'] = current_settings['keep_alive']

        timeout = 120
        if isinstance(current_settings.get('timeout'), int) and current_settings['timeout'] > 0:
            timeout = current_settings['timeout']

        try:
            response = requests.post(endpoint, headers=headers, json=body, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            text = data['message']['content'] if data.get('message') else None
            return ProviderResponse(text=text, raw_payload=data)
        except Timeout:
            raise TranslationProviderError(f"Request timed out after {timeout} seconds.")
        except requests.RequestException as e:
            raise TranslationProviderError(f"API request failed: {e}")

class ChatMockProvider(OpenAIChatProvider):
    """Provider for the ChatMock development server."""
    supports_sessions = True
    
    def _prepare_body(self, messages: List[Dict[str, str]], current_settings: Dict[str, Any]) -> Dict[str, Any]:
        body = super()._prepare_body(messages, current_settings)
        
        if current_settings.get('reasoning_effort'):
            body['reasoning_effort'] = current_settings['reasoning_effort']
        if current_settings.get('reasoning_summary'):
            body['reasoning_summary'] = current_settings['reasoning_summary']
            
        return body

class DeepLProvider(BaseTranslationProvider):
    def translate(self, messages: list, session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        raise NotImplementedError("DeepL provider is not yet implemented.")

class GeminiProvider(BaseTranslationProvider):
    """Provider for Google Gemini API."""
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, settings: Dict[str, Any]) -> None:
        super().__init__(settings)
        self.api_key = self.settings.get('api_key') or os.getenv(str(self.settings.get('api_key_env')))
        self.model = self.settings.get('model')
        if not self.api_key:
            raise TranslationProviderError("Gemini API key is not set.")
        if not self.model:
            raise TranslationProviderError("Gemini model is not set.")

    def translate(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        endpoint = f"{self.BASE_URL}/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        system_prompt = next((m['content'] for m in messages if m['role'] == 'system'), "")
        user_prompt = next((m['content'] for m in messages if m['role'] == 'user'), "")
        
        full_prompt = f"{system_prompt}\n\n{user_prompt}".strip()

        contents = [{"role": "user", "parts": [{"text": full_prompt}]}]
        body: Dict[str, Any] = {"contents": contents}
        
        generation_config = {}
        if isinstance(current_settings.get('temperature'), (float, int)):
            generation_config['temperature'] = current_settings['temperature']
        if generation_config:
            body['generationConfig'] = generation_config

        timeout = 120
        if isinstance(current_settings.get('timeout'), int) and current_settings['timeout'] > 0:
            timeout = current_settings['timeout']

        try:
            response = requests.post(endpoint, headers=headers, json=body, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            
            text = None
            if data.get('candidates'):
                first_candidate = data['candidates'][0]
                if first_candidate.get('content', {}).get('parts'):
                    text = first_candidate['content']['parts'][0].get('text')
            
            return ProviderResponse(text=text, raw_payload=data)
        except Timeout:
            raise TranslationProviderError(f"Request timed out after {timeout} seconds.")
        except requests.RequestException as e:
            error_details = ""
            try:
                error_details = e.response.json()
            except Exception:
                 error_details = e.response.text if e.response else "No response body"
            raise TranslationProviderError(f"API request failed: {e}\nDetails: {error_details}")

def create_translation_provider(provider_key: str, settings: Dict[str, Any]) -> BaseTranslationProvider:
    """Factory function to create a translation provider instance."""
    if provider_key == 'openai_chat':
        return OpenAIChatProvider(settings)
    if provider_key == 'openai_responses':
        return OpenAIResponsesProvider(settings)
    if provider_key == 'ollama_chat':
        return OllamaChatProvider(settings)
    if provider_key == 'chatmock':
        return ChatMockProvider(settings)
    if provider_key == 'deepl':
        return DeepLProvider(settings)
    if provider_key == 'gemini':
        return GeminiProvider(settings)
    raise TranslationProviderError(f"Unknown provider key: {provider_key}")