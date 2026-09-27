"""Multi-provider LLM gateway with fallback orchestration."""

from .embeddings import (
    EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    GeminiEmbeddingProvider,
    OpenAIEmbeddingProvider,
    embed,
)
from .exceptions import (
    AllProvidersFailedError,
    NoSafeProviderError,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from .router import AIRouter
from .types import GenerateResult, ProviderName

__all__ = [
    "AIRouter",
    "AllProvidersFailedError",
    "EMBEDDING_DIMENSIONS",
    "EmbeddingProvider",
    "GeminiEmbeddingProvider",
    "GenerateResult",
    "NoSafeProviderError",
    "OpenAIEmbeddingProvider",
    "ProviderAuthError",
    "ProviderError",
    "ProviderName",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "embed",
]
