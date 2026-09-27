"""Embeddings: OpenAI and Gemini at 1536 dimensions, fully mocked."""

import asyncio
import math
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

# ai_service lives next to backend/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ai_service.gateway.embeddings import (
    EMBEDDING_DIMENSIONS,
    MAX_BATCH_SIZE,
    GeminiEmbeddingProvider,
    OpenAIEmbeddingProvider,
    embed,
)
from ai_service.gateway.exceptions import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
)
from ai_service.gateway.factory import get_default_embedder
from ai_service.gateway.fakes import FakeEmbeddingProvider, fake_vector


def _response(texts, dims=EMBEDDING_DIMENSIONS, *, reverse=False):
    items = [
        SimpleNamespace(index=i, embedding=fake_vector(t, dims)) for i, t in enumerate(texts)
    ]
    return SimpleNamespace(data=list(reversed(items)) if reverse else items)


def _openai_embedder(create):
    embedder = OpenAIEmbeddingProvider(
        api_key="test-key", max_retries=2, retry_backoff_seconds=0
    )
    embedder._client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    return embedder


def _run(coro):
    return asyncio.run(coro)


def test_openai_embedder_sends_model_and_dimensions():
    create = AsyncMock(side_effect=lambda **kw: _response(kw["input"]))
    vectors = _run(_openai_embedder(create).embed(["Sara's birthday is June 15"]))

    assert len(vectors) == 1 and len(vectors[0]) == EMBEDDING_DIMENSIONS
    kwargs = create.call_args.kwargs
    assert kwargs["model"] == "text-embedding-3-small"
    assert kwargs["dimensions"] == EMBEDDING_DIMENSIONS
    assert kwargs["input"] == ["Sara's birthday is June 15"]


def test_openai_embedder_batches_and_keeps_input_order():
    texts = [f"memory {i}" for i in range(MAX_BATCH_SIZE + 44)]
    create = AsyncMock(side_effect=lambda **kw: _response(kw["input"], reverse=True))

    vectors = _run(_openai_embedder(create).embed(texts))

    assert [len(c.kwargs["input"]) for c in create.call_args_list] == [MAX_BATCH_SIZE, 44]
    assert vectors == [fake_vector(t) for t in texts]


def test_wrong_dimensions_raise_without_retry():
    create = AsyncMock(side_effect=lambda **kw: _response(kw["input"], dims=768))

    with pytest.raises(ProviderError) as exc_info:
        _run(_openai_embedder(create).embed(["x"]))

    assert exc_info.value.retryable is False
    assert create.call_count == 1


def test_missing_vectors_raise():
    create = AsyncMock(return_value=_response(["only one"]))

    with pytest.raises(ProviderError):
        _run(_openai_embedder(create).embed(["a", "b"]))


def test_retryable_error_is_retried():
    create = AsyncMock(side_effect=[ProviderRateLimitError("openai"), _response(["x"])])

    assert len(_run(_openai_embedder(create).embed(["x"]))) == 1
    assert create.call_count == 2


def test_empty_input_makes_no_call_and_blank_text_is_rejected():
    create = AsyncMock()
    embedder = _openai_embedder(create)

    assert _run(embedder.embed([])) == []
    with pytest.raises(ValueError):
        _run(embedder.embed(["ok", "   "]))
    assert create.call_count == 0


def test_unconfigured_embedder_raises_auth_error():
    embedder = OpenAIEmbeddingProvider(api_key=None)
    assert embedder.is_configured() is False
    with pytest.raises(ProviderAuthError):
        _run(embedder.embed(["x"]))


def test_fake_embedder_is_deterministic_and_records_calls():
    fake = FakeEmbeddingProvider()

    first, again, other = _run(embed(["a", "a", "b"], embedder=fake))

    assert first == again and first != other
    assert math.isclose(sum(v * v for v in first), 1.0)
    assert fake.calls == [["a", "a", "b"]]


# --- Factory -------------------------------------------------------------------


@pytest.fixture()
def fresh_embedder(monkeypatch):
    for name in ("EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "EMBEDDING_DIMENSIONS", "MEMORY_SAFE_PROVIDERS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_default_embedder.cache_clear()
    yield monkeypatch
    get_default_embedder.cache_clear()


def test_default_embedder(fresh_embedder):
    embedder = get_default_embedder()
    assert isinstance(embedder, OpenAIEmbeddingProvider)
    assert (embedder.model, embedder.dimensions) == ("text-embedding-3-small", 1536)


@pytest.mark.parametrize(
    "name, value",
    [
        ("EMBEDDING_DIMENSIONS", "768"),
        ("EMBEDDING_PROVIDER", "groq"),  # no embedding support
        ("MEMORY_SAFE_PROVIDERS", "anthropic"),
    ],
)
def test_factory_refuses_unsafe_or_mismatched_config(fresh_embedder, name, value):
    fresh_embedder.setenv(name, value)
    with pytest.raises(RuntimeError):
        get_default_embedder()


def test_gemini_embedder_needs_gemini_on_the_allowlist(fresh_embedder):
    fresh_embedder.setenv("EMBEDDING_PROVIDER", "gemini")
    with pytest.raises(RuntimeError, match="MEMORY_SAFE_PROVIDERS"):
        get_default_embedder()


def test_gemini_embedder_is_built_and_flagged_as_development_only(fresh_embedder, caplog):
    fresh_embedder.setenv("EMBEDDING_PROVIDER", "gemini")
    fresh_embedder.setenv("MEMORY_SAFE_PROVIDERS", "gemini,openai")
    fresh_embedder.setenv("GEMINI_API_KEY", "test-gemini-key")

    with caplog.at_level("WARNING", logger="ai_service.gateway.factory"):
        embedder = get_default_embedder()

    assert isinstance(embedder, GeminiEmbeddingProvider)
    assert (embedder.model, embedder.dimensions) == ("gemini-embedding-001", 1536)
    assert "event=ai_memory_providers_untrusted providers=gemini" in caplog.text


# --- Gemini ----------------------------------------------------------------------


class _GeminiError(Exception):
    def __init__(self, code):
        super().__init__(f"gemini error {code}")
        self.code = code


def _gemini_embedder(embed_content):
    embedder = GeminiEmbeddingProvider(
        api_key="test-key", max_retries=2, retry_backoff_seconds=0
    )
    embedder._client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))
    )
    return embedder


def _gemini_response(texts, value=2.0, dims=EMBEDDING_DIMENSIONS):
    return SimpleNamespace(embeddings=[SimpleNamespace(values=[value] * dims) for _ in texts])


def test_gemini_embedder_requests_1536_dimensions_and_normalises():
    embed_content = AsyncMock(side_effect=lambda **kw: _gemini_response(kw["contents"]))

    (vector,) = _run(_gemini_embedder(embed_content).embed(["Sara's birthday is June 15"]))

    kwargs = embed_content.call_args.kwargs
    assert kwargs["model"] == "gemini-embedding-001"
    assert kwargs["config"] == {"output_dimensionality": EMBEDDING_DIMENSIONS}
    assert len(vector) == EMBEDDING_DIMENSIONS
    assert math.isclose(sum(v * v for v in vector), 1.0)


def test_gemini_embedder_batches_100_at_a_time():
    embed_content = AsyncMock(side_effect=lambda **kw: _gemini_response(kw["contents"]))

    vectors = _run(_gemini_embedder(embed_content).embed([f"m{i}" for i in range(150)]))

    assert [len(c.kwargs["contents"]) for c in embed_content.call_args_list] == [100, 50]
    assert len(vectors) == 150


@pytest.mark.parametrize(
    "code, error, calls",
    [
        (403, ProviderAuthError, 1),  # bad key: not retried
        (400, ProviderError, 1),  # bad request: not retried
        (429, ProviderRateLimitError, 2),  # rate limited: retried
        (503, ProviderError, 2),  # server error: retried
    ],
)
def test_gemini_errors_are_mapped(code, error, calls):
    embed_content = AsyncMock(side_effect=_GeminiError(code))

    with pytest.raises(error):
        _run(_gemini_embedder(embed_content).embed(["x"]))

    assert embed_content.call_count == calls
