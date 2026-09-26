import os
import logging
from functools import lru_cache

from dotenv import load_dotenv

from .embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from .registry import _env, build_providers_from_chain
from .router import AIRouter
from .types import ProviderName, RouterConfig

load_dotenv()
logger = logging.getLogger(__name__)

# Providers allowed to see memories or chat history when MEMORY_SAFE_PROVIDERS is
# unset (design.md §9: API terms say they don't train on or retain API data).
DEFAULT_MEMORY_SAFE_PROVIDERS = (ProviderName.OPENAI, ProviderName.ANTHROPIC)


def parse_fallback_chain(raw: str | None) -> list[ProviderName]:
    if not raw:
        return [
            ProviderName.GEMINI,
            ProviderName.OPENAI,
            ProviderName.DEEPSEEK,
            ProviderName.GROQ,
            ProviderName.OLLAMA,
        ]
    names: list[ProviderName] = []
    for part in raw.split(","):
        token = part.strip().lower()
        if not token:
            continue
        try:
            names.append(ProviderName(token))
        except ValueError:
            continue
    return names or [ProviderName.GEMINI]


def parse_provider_list(
    raw: str | None, default: tuple[ProviderName, ...]
) -> list[ProviderName]:
    """Comma-separated provider names, in order. Unknown names are dropped.

    Unlike parse_fallback_chain, a value with no valid names yields an empty list
    rather than a default, so a typo fails closed instead of widening access.
    """
    if raw is None or not raw.strip():
        return list(default)
    names: list[ProviderName] = []
    for part in raw.split(","):
        token = part.strip().lower()
        if not token:
            continue
        try:
            name = ProviderName(token)
        except ValueError:
            logger.warning("event=ai_provider_unknown name=%s", token)
            continue
        if name not in names:
            names.append(name)
    return names


def memory_safe_provider_names() -> list[ProviderName]:
    return parse_provider_list(
        os.getenv("MEMORY_SAFE_PROVIDERS"), DEFAULT_MEMORY_SAFE_PROVIDERS
    )


@lru_cache(maxsize=1)
def get_default_router() -> AIRouter:
    chain = parse_fallback_chain(os.getenv("AI_FALLBACK_CHAIN"))
    providers = build_providers_from_chain(chain)
    if not providers:
        raise RuntimeError(
            "No AI providers configured. Set at least one API key "
            "(e.g. GEMINI_API_KEY, OPENAI_API_KEY) and AI_FALLBACK_CHAIN."
        )
    # Built independently of AI_FALLBACK_CHAIN: a safe provider need not be in it.
    safe_names = memory_safe_provider_names()
    safe_providers = build_providers_from_chain(safe_names)
    config = RouterConfig(
        fallback_chain=chain,
        timeout_seconds=float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "60")),
        max_retries_per_provider=int(os.getenv("AI_MAX_RETRIES_PER_PROVIDER", "2")),
        retry_backoff_seconds=float(os.getenv("AI_RETRY_BACKOFF_SECONDS", "0.5")),
    )
    logger.info(
        "event=ai_router_configured provider_chain=%s active_providers=%s "
        "memory_safe_providers=%s timeout_s=%s retries=%s backoff_s=%s",
        ",".join([c.value for c in chain]),
        ",".join([p.name.value for p in providers]),
        ",".join([p.name.value for p in safe_providers]) or "none",
        config.timeout_seconds,
        config.max_retries_per_provider,
        config.retry_backoff_seconds,
    )
    return AIRouter(providers=providers, config=config, safe_providers=safe_providers)


@lru_cache(maxsize=1)
def get_default_embedder() -> EmbeddingProvider:
    provider = (_env("EMBEDDING_PROVIDER") or ProviderName.OPENAI.value).lower()
    if provider != ProviderName.OPENAI.value:
        raise RuntimeError(
            f"EMBEDDING_PROVIDER={provider!r} is not supported; only 'openai' is."
        )
    dimensions = int(_env("EMBEDDING_DIMENSIONS") or EMBEDDING_DIMENSIONS)
    if dimensions != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"EMBEDDING_DIMENSIONS must be {EMBEDDING_DIMENSIONS} to match the "
            f"memory vector column, got {dimensions}."
        )
    # Embedded text is always personal data.
    if ProviderName.OPENAI not in memory_safe_provider_names():
        raise RuntimeError(
            "Embeddings carry personal data: add 'openai' to MEMORY_SAFE_PROVIDERS."
        )
    embedder = OpenAIEmbeddingProvider(
        api_key=_env("OPENAI_API_KEY"),
        base_url=_env("OPENAI_BASE_URL"),
        model=_env("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL,
        dimensions=dimensions,
        timeout_seconds=float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "60")),
        max_retries=int(os.getenv("AI_MAX_RETRIES_PER_PROVIDER", "2")),
        retry_backoff_seconds=float(os.getenv("AI_RETRY_BACKOFF_SECONDS", "0.5")),
    )
    logger.info(
        "event=ai_embedder_configured provider=%s model=%s dimensions=%s configured=%s",
        embedder.name.value,
        embedder.model,
        embedder.dimensions,
        embedder.is_configured(),
    )
    return embedder
