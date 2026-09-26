import os
from typing import Dict, Optional

from .base import BaseLLMProvider
from .providers import (
    AnthropicProvider,
    DeepSeekProvider,
    GeminiProvider,
    GroqProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
)
from .types import ProviderName


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


DEFAULT_MODELS: Dict[ProviderName, str] = {
    ProviderName.OPENAI: "gpt-4o-mini",
    ProviderName.GEMINI: "models/gemini-2.5-flash",
    ProviderName.DEEPSEEK: "deepseek-chat",
    ProviderName.GROQ: "llama-3.3-70b-versatile",
    ProviderName.ANTHROPIC: "claude-haiku-4-5",
    ProviderName.OLLAMA: "llama3.2",
    ProviderName.OPENROUTER: "openai/gpt-4o-mini",
}


def build_provider(name: ProviderName) -> BaseLLMProvider:
    model_env = {
        ProviderName.OPENAI: "OPENAI_MODEL",
        ProviderName.GEMINI: "GEMINI_MODEL",
        ProviderName.DEEPSEEK: "DEEPSEEK_MODEL",
        ProviderName.GROQ: "GROQ_MODEL",
        ProviderName.ANTHROPIC: "ANTHROPIC_MODEL",
        ProviderName.OLLAMA: "OLLAMA_MODEL",
        ProviderName.OPENROUTER: "OPENROUTER_MODEL",
    }
    key_env = {
        ProviderName.OPENAI: "OPENAI_API_KEY",
        ProviderName.GEMINI: "GEMINI_API_KEY",
        ProviderName.DEEPSEEK: "DEEPSEEK_API_KEY",
        ProviderName.GROQ: "GROQ_API_KEY",
        ProviderName.ANTHROPIC: "ANTHROPIC_API_KEY",
        ProviderName.OLLAMA: "OLLAMA_API_KEY",
        ProviderName.OPENROUTER: "OPENROUTER_API_KEY",
    }
    base_env = {
        ProviderName.OPENAI: "OPENAI_BASE_URL",
        ProviderName.GEMINI: None,
        ProviderName.DEEPSEEK: "DEEPSEEK_BASE_URL",
        ProviderName.GROQ: "GROQ_BASE_URL",
        ProviderName.ANTHROPIC: "ANTHROPIC_BASE_URL",
        ProviderName.OLLAMA: "OLLAMA_BASE_URL",
        ProviderName.OPENROUTER: "OPENROUTER_BASE_URL",
    }

    model = _env(model_env[name], DEFAULT_MODELS[name])
    api_key = _env(key_env[name])
    base_url = _env(base_env[name]) if base_env[name] else None

    provider_map = {
        ProviderName.OPENAI: OpenAIProvider,
        ProviderName.GEMINI: GeminiProvider,
        ProviderName.DEEPSEEK: DeepSeekProvider,
        ProviderName.GROQ: GroqProvider,
        ProviderName.ANTHROPIC: AnthropicProvider,
        ProviderName.OLLAMA: OllamaProvider,
        ProviderName.OPENROUTER: OpenRouterProvider,
    }
    return provider_map[name](model=model or DEFAULT_MODELS[name], api_key=api_key, base_url=base_url)


def build_providers_from_chain(chain: list[ProviderName]) -> list[BaseLLMProvider]:
    providers: list[BaseLLMProvider] = []
    for name in chain:
        provider = build_provider(name)
        if provider.is_configured():
            providers.append(provider)
    return providers
