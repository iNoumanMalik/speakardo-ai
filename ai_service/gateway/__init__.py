"""Multi-provider LLM gateway with fallback orchestration."""

from .embeddings import (
    EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
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
