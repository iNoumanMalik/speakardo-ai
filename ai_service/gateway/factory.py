import os
import logging
from functools import lru_cache

from dotenv import load_dotenv

from .registry import build_providers_from_chain
from .router import AIRouter
from .types import ProviderName, RouterConfig

load_dotenv()
logger = logging.getLogger(__name__)


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


@lru_cache(maxsize=1)
def get_default_router() -> AIRouter:
    chain = parse_fallback_chain(os.getenv("AI_FALLBACK_CHAIN"))
    providers = build_providers_from_chain(chain)
    if not providers:
        raise RuntimeError(
            "No AI providers configured. Set at least one API key "
            "(e.g. GEMINI_API_KEY, OPENAI_API_KEY) and AI_FALLBACK_CHAIN."
        )
    config = RouterConfig(
        fallback_chain=chain,
        timeout_seconds=float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "60")),
        max_retries_per_provider=int(os.getenv("AI_MAX_RETRIES_PER_PROVIDER", "2")),
        retry_backoff_seconds=float(os.getenv("AI_RETRY_BACKOFF_SECONDS", "0.5")),
    )
    logger.info(
        "event=ai_router_configured provider_chain=%s active_providers=%s timeout_s=%s retries=%s backoff_s=%s",
        ",".join([c.value for c in chain]),
        ",".join([p.name.value for p in providers]),
        config.timeout_seconds,
        config.max_retries_per_provider,
        config.retry_backoff_seconds,
    )
    return AIRouter(providers=providers, config=config)
