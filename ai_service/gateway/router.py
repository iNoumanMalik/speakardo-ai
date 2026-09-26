import asyncio
import logging
import time
from typing import Optional

from .base import BaseLLMProvider
from .exceptions import (
    AllProvidersFailedError,
    NoSafeProviderError,
    ProviderError,
    ProviderTimeoutError,
)
from .types import GenerateResult, RouterConfig

logger = logging.getLogger(__name__)


class AIRouter:
    """
    Central orchestrator: provider prioritization, retries, timeout, and fallback chain.
    """

    def __init__(
        self,
        providers: list[BaseLLMProvider],
        config: Optional[RouterConfig] = None,
        safe_providers: Optional[list[BaseLLMProvider]] = None,
    ) -> None:
        if not providers:
            raise ValueError("AIRouter requires at least one configured provider")
        self.providers = providers
        self.config = config or RouterConfig()
        # The only providers allowed to receive memories or chat history.
        self.safe_providers = list(safe_providers or [])

    def _personal_data_chain(
        self, provider_chain: Optional[list[BaseLLMProvider]]
    ) -> list[BaseLLMProvider]:
        allowed = {p.name for p in self.safe_providers}
        chain = [p for p in (provider_chain or self.safe_providers) if p.name in allowed]
        if not chain:
            logger.error("event=ai_personal_data_blocked reason=no_safe_provider")
            raise NoSafeProviderError()
        logger.info(
            "event=ai_personal_data_call providers=%s",
            ",".join(p.name.value for p in chain),
        )
        return chain

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        response_format: Optional[str] = None,
        model: Optional[str] = None,
        provider_chain: Optional[list[BaseLLMProvider]] = None,
        personal_data: bool = False,
    ) -> GenerateResult:
        """Generate text, falling back across providers.

        personal_data=True (prompt carries memories or chat history) restricts the
        chain to MEMORY_SAFE_PROVIDERS and never falls back beyond them.
        """
        if personal_data:
            chain = self._personal_data_chain(provider_chain)
        else:
            chain = provider_chain or self.providers
        failures: list[dict] = []
        fallback_used = False

        for idx, provider in enumerate(chain):
            if idx > 0:
                fallback_used = True

            for attempt in range(1, self.config.max_retries_per_provider + 1):
                started = time.perf_counter()
                try:
                    text = await asyncio.wait_for(
                        provider.generate(
                            prompt,
                            temperature=temperature,
                            response_format=response_format,
                            model=model,
                        ),
                        timeout=self.config.timeout_seconds,
                    )
                    latency_ms = (time.perf_counter() - started) * 1000
                    logger.info(
                        "AI generate success provider=%s model=%s attempt=%s latency_ms=%.1f fallback=%s",
                        provider.name.value,
                        model or provider.model,
                        attempt,
                        latency_ms,
                        fallback_used,
                    )
                    return GenerateResult(
                        text=text,
                        provider=provider.name.value,
                        model=model or provider.model,
                        latency_ms=latency_ms,
                        attempt=attempt,
                        fallback_used=fallback_used,
                    )
                except asyncio.TimeoutError as exc:
                    err = ProviderTimeoutError(provider.name.value, self.config.timeout_seconds)
                    self._record_failure(failures, provider, attempt, err)
                    logger.warning(
                        "AI provider timeout provider=%s attempt=%s",
                        provider.name.value,
                        attempt,
                    )
                except ProviderError as exc:
                    self._record_failure(failures, provider, attempt, exc)
                    logger.warning(
                        "AI provider error provider=%s attempt=%s retryable=%s error=%s",
                        provider.name.value,
                        attempt,
                        exc.retryable,
                        exc,
                    )
                    if not exc.retryable:
                        break
                except Exception as exc:
                    wrapped = ProviderError(
                        str(exc),
                        provider=provider.name.value,
                        cause=exc,
                    )
                    self._record_failure(failures, provider, attempt, wrapped)
                    logger.exception(
                        "Unexpected provider failure provider=%s attempt=%s",
                        provider.name.value,
                        attempt,
                    )

                if attempt < self.config.max_retries_per_provider:
                    await asyncio.sleep(self.config.retry_backoff_seconds * attempt)

        raise AllProvidersFailedError(failures)

    @staticmethod
    def _record_failure(
        failures: list[dict],
        provider: BaseLLMProvider,
        attempt: int,
        exc: Exception,
    ) -> None:
        failures.append(
            {
                "provider": provider.name.value,
                "attempt": attempt,
                "error": str(exc),
                "retryable": getattr(exc, "retryable", True),
            }
        )
