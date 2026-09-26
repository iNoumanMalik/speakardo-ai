"""Test doubles for the gateway. Never used in production code."""

from __future__ import annotations

import hashlib
import math
import random

from .embeddings import EMBEDDING_DIMENSIONS, EmbeddingProvider
from .types import ProviderName


def fake_vector(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    """Deterministic unit vector: the same text always maps to the same vector."""
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    values = [rng.gauss(0.0, 1.0) for _ in range(dimensions)]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


class FakeEmbeddingProvider(EmbeddingProvider):
    """Offline embedder for tests. Records every batch in ``calls``."""

    name = ProviderName.OPENAI

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        super().__init__(model="fake-embedding", dimensions=dimensions, max_retries=1)
        self.calls: list[list[str]] = []

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [fake_vector(t, self.dimensions) for t in texts]
