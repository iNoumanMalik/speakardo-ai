"""Text embeddings for memory search (Module 8).

One provider, no cross-provider fallback: vectors from different models live in
different spaces and cannot be compared. Embedded text is always personal data,
so the embedding provider must be listed in MEMORY_SAFE_PROVIDERS (factory.py).
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

from .exceptions import ProviderAuthError, ProviderError, ProviderTimeoutError
from .types import ProviderName

logger = logging.getLogger(__name__)

# Shared with the vector(1536) column that stores memory embeddings (8.1).
EMBEDDING_DIMENSIONS = 1536
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
MAX_BATCH_SIZE = 256


class EmbeddingProvider(ABC):
    """Turns texts into fixed-size vectors, with timeout, retries and validation."""

    name: ProviderName

    def __init__(
        self,
        *,
        model: str,
        dimensions: int = EMBEDDING_DIMENSIONS,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self.model = model
        self.dimensions = dimensions
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(1, max_retries)
        self.retry_backoff_seconds = retry_backoff_seconds

    def is_configured(self) -> bool:
        return True

    @abstractmethod
    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """One API call for at most MAX_BATCH_SIZE texts, results in input order."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError("Cannot embed empty or non-string text")

        started = time.perf_counter()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[start : start + MAX_BATCH_SIZE]
            result = await self._embed_batch_with_retries(batch)
            self._validate(batch, result)
            vectors.extend(result)

        logger.info(
            "event=ai_embed provider=%s model=%s count=%s latency_ms=%.1f",
            self.name.value,
            self.model,
            len(texts),
            (time.perf_counter() - started) * 1000,
        )
        return vectors

    async def _embed_batch_with_retries(self, batch: list[str]) -> list[list[float]]:
        last_error: Optional[ProviderError] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    self._embed_batch(batch), timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                last_error = ProviderTimeoutError(self.name.value, self.timeout_seconds)
            except ProviderError as exc:
                last_error = exc
                if not exc.retryable:
                    break
            logger.warning(
                "event=ai_embed_retry provider=%s attempt=%s error=%s",
                self.name.value,
                attempt,
                last_error,
            )
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_backoff_seconds * attempt)
        assert last_error is not None
        raise last_error

    def _validate(self, batch: list[str], vectors: list[list[float]]) -> None:
        if len(vectors) != len(batch):
            raise ProviderError(
                f"Expected {len(batch)} embeddings, got {len(vectors)}",
                provider=self.name.value,
                retryable=False,
            )
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ProviderError(
                    f"Expected {self.dimensions}-dimensional embeddings, got {len(vector)}",
                    provider=self.name.value,
                    retryable=False,
                )


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = ProviderName.OPENAI

    def __init__(
        self,
        *,
        api_key: Optional[str],
        model: str = DEFAULT_EMBEDDING_MODEL,
        base_url: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(model=model, **kwargs)
        self._client = None
        if api_key:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def is_configured(self) -> bool:
        return self._client is not None

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._client is None:
            raise ProviderAuthError(self.name.value, "OPENAI_API_KEY is not set")
        from .providers._openai_compat import _map_openai_error

        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions,
            )
        except Exception as exc:
            raise _map_openai_error(exc, self.name) from exc
        return [list(item.embedding) for item in sorted(response.data, key=lambda d: d.index)]


async def embed(
    texts: list[str], *, embedder: Optional[EmbeddingProvider] = None
) -> list[list[float]]:
    """Embed texts with ``embedder``, or the configured default (factory.get_default_embedder)."""
    if embedder is None:
        from .factory import get_default_embedder

        embedder = get_default_embedder()
    return await embedder.embed(texts)
