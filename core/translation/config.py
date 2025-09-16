from copy import deepcopy
from typing import Any, Dict

DEFAULT_TRANSLATION_CONFIG: Dict[str, Any] = {
    "provider": "disabled",
    "providers": {
        "openai_chat": {
            "api_key": "",
            "api_key_env": "OPENAI_API_KEY",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "max_output_tokens": 0,
            "timeout": 60,
            "extra_headers": {}
        },
        "ollama_chat": {
            "base_url": "http://localhost:11434",
            "model": "llama3",
            "temperature": 0.0,
            "timeout": 120,
            "keep_alive": "",
            "extra_headers": {}
        },
        "chatmock": {
            "base_url": "http://127.0.0.1:8000",
            "model": "gpt-5",
            "api_key": "chatmock-placeholder",
            "temperature": 0.0,
            "timeout": 60,
            "reasoning_effort": "medium",
            "reasoning_summary": "auto",
            "extra_headers": {}
        }
    }
}

def build_default_translation_config() -> Dict[str, Any]:
    """Return a deep copy of the default translation configuration."""
    return deepcopy(DEFAULT_TRANSLATION_CONFIG)

def merge_translation_config(base_config: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Merge user overrides into the default translation configuration."""
    merged = deepcopy(base_config) if base_config else {}
    if not isinstance(overrides, dict):
        return merged

    provider_key = overrides.get("provider")
    if isinstance(provider_key, str) and provider_key:
        merged["provider"] = provider_key

    providers_overrides = overrides.get("providers")
    if isinstance(providers_overrides, dict):
        merged.setdefault("providers", {})
        for name, cfg in providers_overrides.items():
            if name not in merged["providers"]:
                merged["providers"][name] = {}
            if isinstance(cfg, dict):
                merged["providers"][name].update(cfg)
            else:
                merged["providers"][name] = cfg

    for key, value in overrides.items():
        if key in ("provider", "providers"):
            continue
        merged[key] = value

    return merged
