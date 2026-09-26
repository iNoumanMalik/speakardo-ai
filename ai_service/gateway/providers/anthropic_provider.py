from typing import Optional

from ..base import BaseLLMProvider
from ..exceptions import ProviderAuthError, ProviderError, ProviderRateLimitError
from ..types import ProviderName

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None


class AnthropicProvider(BaseLLMProvider):
    name = ProviderName.ANTHROPIC

    def __init__(self, *, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        super().__init__(model=model, api_key=api_key, base_url=base_url)
        self._client = (
            AsyncAnthropic(api_key=api_key, base_url=base_url) if AsyncAnthropic and api_key else None
        )

    def is_configured(self) -> bool:
        return bool(self._client)

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        response_format: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        if not self._client:
            raise ProviderAuthError(
                self.name.value,
                "ANTHROPIC_API_KEY is not set or anthropic SDK unavailable",
            )

        model_id = model or self.model
        try:
            # anthropic SDK 1.x removed `temperature` from create(); it is still an
            # API field, so it goes through extra_body. The default model
            # (claude-haiku-4-5) accepts it; Opus 4.7 and later reject any sampling
            # parameter, so drop this if ANTHROPIC_MODEL moves to one of those.
            response = await self._client.messages.create(
                model=model_id,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
                extra_body={"temperature": temperature},
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            msg = str(exc)
            if status == 401:
                raise ProviderAuthError(self.name.value, msg) from exc
            if status == 429:
                raise ProviderRateLimitError(self.name.value, msg) from exc
            raise ProviderError(msg, provider=self.name.value, status_code=status, cause=exc) from exc

        parts = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        if not parts:
            raise ProviderError("Empty Anthropic response", provider=self.name.value, retryable=True)
        return "\n".join(parts).strip()
