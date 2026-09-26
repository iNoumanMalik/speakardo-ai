from typing import Any, Optional


class ProviderError(Exception):
    """Base exception for provider failures."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        retryable: bool = True,
        status_code: Optional[int] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable
        self.status_code = status_code
        self.cause = cause


class ProviderTimeoutError(ProviderError):
    def __init__(self, provider: str, timeout_seconds: float) -> None:
        super().__init__(
            f"Provider timed out after {timeout_seconds}s",
            provider=provider,
            retryable=True,
        )
        self.timeout_seconds = timeout_seconds


class ProviderAuthError(ProviderError):
    def __init__(self, provider: str, message: str = "Authentication failed") -> None:
        super().__init__(message, provider=provider, retryable=False, status_code=401)


class ProviderRateLimitError(ProviderError):
    def __init__(self, provider: str, message: str = "Rate limited") -> None:
        super().__init__(message, provider=provider, retryable=True, status_code=429)


class AllProvidersFailedError(Exception):
    def __init__(self, failures: list[dict[str, Any]]) -> None:
        self.failures = failures
        summary = "; ".join(
            f"{f['provider']}: {f['error']}" for f in failures
        )
        super().__init__(f"All providers failed: {summary}")


class NoSafeProviderError(AllProvidersFailedError):
    """A personal-data call had no allowlisted provider; nothing was sent anywhere."""

    def __init__(self) -> None:
        self.failures = []
        Exception.__init__(
            self,
            "No memory-safe AI provider is configured (see MEMORY_SAFE_PROVIDERS)",
        )
