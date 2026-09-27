"""Provider allowlist: personal-data calls only ever reach MEMORY_SAFE_PROVIDERS."""

import asyncio
import os
import sys

import pytest

# ai_service lives next to backend/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ai_service.gateway.base import BaseLLMProvider
from ai_service.gateway.exceptions import (
    AllProvidersFailedError,
    NoSafeProviderError,
    ProviderError,
)
from ai_service.gateway.factory import (
    DEFAULT_MEMORY_SAFE_PROVIDERS,
    get_default_router,
    memory_safe_provider_names,
    parse_provider_list,
)
from ai_service.gateway.router import AIRouter
from ai_service.gateway.types import ProviderName, RouterConfig

P = ProviderName


class _Provider(BaseLLMProvider):
    def __init__(self, name: ProviderName, *, fail: bool = False) -> None:
        super().__init__(model=f"{name.value}-model")
        self.name = name
        self.fail = fail
        self.calls = 0

    async def generate(self, prompt, **kwargs) -> str:
        self.calls += 1
        if self.fail:
            raise ProviderError("boom", provider=self.name.value, retryable=False)
        return f"reply from {self.name.value}"


def _router(providers, safe_providers):
    config = RouterConfig(max_retries_per_provider=1, retry_backoff_seconds=0)
    return AIRouter(providers=providers, config=config, safe_providers=safe_providers)


def _generate(router, **kwargs):
    return asyncio.run(router.generate("prompt", **kwargs))


def test_personal_data_uses_safe_providers_in_order():
    gemini, openai, anthropic = _Provider(P.GEMINI), _Provider(P.OPENAI), _Provider(P.ANTHROPIC)
    router = _router([gemini, openai], [openai, anthropic])

    result = _generate(router, personal_data=True)

    assert result.provider == "openai"
    assert gemini.calls == 0


def test_personal_data_never_falls_back_to_unsafe_providers():
    gemini, deepseek = _Provider(P.GEMINI), _Provider(P.DEEPSEEK)
    openai, anthropic = _Provider(P.OPENAI, fail=True), _Provider(P.ANTHROPIC, fail=True)
    router = _router([gemini, deepseek], [openai, anthropic])

    with pytest.raises(AllProvidersFailedError):
        _generate(router, personal_data=True)

    assert (openai.calls, anthropic.calls) == (1, 1)
    assert (gemini.calls, deepseek.calls) == (0, 0)


def test_no_safe_provider_fails_closed_without_calling_anything():
    gemini = _Provider(P.GEMINI)
    router = _router([gemini], [])

    with pytest.raises(NoSafeProviderError) as exc_info:
        _generate(router, personal_data=True)

    assert isinstance(exc_info.value, AllProvidersFailedError)
    assert gemini.calls == 0


def test_explicit_chain_is_filtered_to_safe_providers():
    gemini, openai, anthropic = _Provider(P.GEMINI), _Provider(P.OPENAI), _Provider(P.ANTHROPIC)
    router = _router([gemini], [openai, anthropic])

    result = _generate(router, personal_data=True, provider_chain=[gemini, anthropic])

    assert result.provider == "anthropic"
    assert (gemini.calls, openai.calls) == (0, 0)


def test_non_personal_calls_keep_the_normal_fallback_chain():
    gemini, openai = _Provider(P.GEMINI), _Provider(P.OPENAI)
    router = _router([gemini, openai], [openai])

    assert _generate(router).provider == "gemini"


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, list(DEFAULT_MEMORY_SAFE_PROVIDERS)),
        ("  ", list(DEFAULT_MEMORY_SAFE_PROVIDERS)),
        ("OpenAI, anthropic,openai", [P.OPENAI, P.ANTHROPIC]),
        ("anthropic,bogus", [P.ANTHROPIC]),
        ("bogus", []),  # a typo fails closed rather than falling back to defaults
    ],
)
def test_parse_provider_list(raw, expected):
    assert parse_provider_list(raw, DEFAULT_MEMORY_SAFE_PROVIDERS) == expected


def test_default_allowlist_is_openai_and_anthropic(monkeypatch):
    monkeypatch.delenv("MEMORY_SAFE_PROVIDERS", raising=False)
    assert memory_safe_provider_names() == [P.OPENAI, P.ANTHROPIC]


def test_default_router_builds_safe_providers_outside_the_fallback_chain(monkeypatch):
    monkeypatch.setenv("AI_FALLBACK_CHAIN", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("MEMORY_SAFE_PROVIDERS", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    get_default_router.cache_clear()
    try:
        router = get_default_router()
        assert [p.name for p in router.providers] == [P.OPENAI]
        assert [p.name for p in router.safe_providers] == [P.ANTHROPIC]
    finally:
        get_default_router.cache_clear()


def test_router_warns_when_a_development_only_provider_is_allowed(monkeypatch, caplog):
    monkeypatch.setenv("AI_FALLBACK_CHAIN", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("MEMORY_SAFE_PROVIDERS", "gemini,openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    get_default_router.cache_clear()
    try:
        with caplog.at_level("WARNING", logger="ai_service.gateway.factory"):
            router = get_default_router()
        assert [p.name for p in router.safe_providers] == [P.GEMINI, P.OPENAI]
        assert "event=ai_memory_providers_untrusted providers=gemini" in caplog.text
    finally:
        get_default_router.cache_clear()


def test_trusted_providers_log_no_warning(monkeypatch, caplog):
    monkeypatch.setenv("AI_FALLBACK_CHAIN", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.delenv("MEMORY_SAFE_PROVIDERS", raising=False)
    get_default_router.cache_clear()
    try:
        with caplog.at_level("WARNING", logger="ai_service.gateway.factory"):
            get_default_router()
        assert "ai_memory_providers_untrusted" not in caplog.text
    finally:
        get_default_router.cache_clear()
