# AI Gateway (multi-provider LLM router)

Production-oriented async orchestration for reminder extraction and future AI tasks.

## Supported providers

| Provider | Env key(s) | Default model |
|----------|------------|---------------|
| OpenAI | `OPENAI_API_KEY` | `gpt-4o-mini` |
| Gemini | `GEMINI_API_KEY` | `models/gemini-2.5-flash` |
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| Groq | `GROQ_API_KEY` | `openai/gpt-oss-120b` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-haiku-4-5` |
| Ollama | `OLLAMA_BASE_URL` (optional key) | `llama3.2` |
| OpenRouter | `OPENROUTER_API_KEY` | `openai/gpt-4o-mini` |

Override models with `OPENAI_MODEL`, `GEMINI_MODEL`, etc.

## Router behavior

- **Fallback chain** via `AI_FALLBACK_CHAIN` (comma-separated), e.g.  
  `gemini,openai,deepseek,groq,ollama`
- **Per-provider retries**: `AI_MAX_RETRIES_PER_PROVIDER` (default `2`)
- **Timeout**: `AI_REQUEST_TIMEOUT_SECONDS` (default `60`)
- **Backoff**: `AI_RETRY_BACKOFF_SECONDS` (default `0.5`)

On failure, the router logs the provider + error and tries the next provider.

## Health endpoint

Backend exposes:

- `GET /health/ai` — configuration + router status (no API calls)
- curl http://127.0.0.1:8000/health/ai
- `GET /health/ai?probe=true` — live minimal request per configured provider
- curl "http://127.0.0.1:8000/health/ai?probe=true"

## Usage

```python
from gateway.factory import get_default_router

router = get_default_router()
result = await router.generate("Say hello", temperature=0)
print(result.provider, result.text)
```

## Personal data: provider allowlist

Calls whose prompt carries memories or chat history must pass `personal_data=True`:

```python
result = await router.generate(prompt, personal_data=True)
```

These calls only reach providers listed in `MEMORY_SAFE_PROVIDERS` (default `openai,anthropic`), in that order, and never fall back to any other provider. The list is built independently of `AI_FALLBACK_CHAIN`. If none of the listed providers is configured, `NoSafeProviderError` is raised (a subclass of `AllProvidersFailedError`) and nothing is sent. A value with no valid provider names allows none.

Gemini, DeepSeek, Groq and OpenRouter can be listed for development with test data (`UNTRUSTED_MEMORY_PROVIDERS` in `factory.py`); the router then logs `event=ai_memory_providers_untrusted` at startup. Ollama runs locally and is not flagged.

## Embeddings

```python
from ai_service.gateway.embeddings import embed

vectors = await embed(["Sara's birthday is June 15"])  # list of 1536-float lists
```

- One provider at a time, chosen by `EMBEDDING_PROVIDER`: `openai` (`text-embedding-3-small`, the default) or `gemini` (`gemini-embedding-001`, free tier, for development). Both produce 1536 dimensions (`EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`). There is no fallback, because vectors from different models can't be compared.
- `get_default_embedder()` refuses to start unless the embedding provider is in `MEMORY_SAFE_PROVIDERS`, since embedded text is always personal data.
- Batches of up to 256 texts (OpenAI) or 100 (Gemini), with retries and timeout from `AI_MAX_RETRIES_PER_PROVIDER` / `AI_REQUEST_TIMEOUT_SECONDS`. Every vector's length is checked. Gemini vectors are normalised to unit length.
- Tests use `gateway/fakes.py` `FakeEmbeddingProvider` (deterministic, offline): `await embed(texts, embedder=FakeEmbeddingProvider())`.

## Add a new provider

1. Add enum value in `gateway/types.py` (`ProviderName`).
2. Implement `BaseLLMProvider` in `gateway/providers/your_provider.py`.
3. Register in `gateway/registry.py` (`build_provider` maps).
4. Add env keys + default model.
5. Include name in `AI_FALLBACK_CHAIN`.
