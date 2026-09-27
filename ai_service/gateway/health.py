import asyncio
import os
import time
from typing import Any, Optional

from .exceptions import ProviderError
from .factory import (
    UNTRUSTED_MEMORY_PROVIDERS,
    memory_safe_provider_names,
    parse_fallback_chain,
)
from .registry import DEFAULT_MODELS, build_provider, build_providers_from_chain
from .types import ProviderName

PROBE_PROMPT = 'Reply with exactly the word OK and nothing else.'
PROBE_TIMEOUT_SECONDS = float(os.getenv("AI_HEALTH_PROBE_TIMEOUT_SECONDS", "12"))


async def _probe_one(provider, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        text = await asyncio.wait_for(
            provider.generate(PROBE_PROMPT, temperature=0),
            timeout=timeout,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        ok = bool(text and text.strip())
        return {
            "ok": ok,
            "latency_ms": round(latency_ms, 1),
            "sample": (text[:80] + "...") if text and len(text) > 80 else text,
        }
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": f"timeout after {timeout}s",
        }
    except ProviderError as exc:
        return {
            "ok": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": str(exc),
            "retryable": exc.retryable,
        }
    except Exception as exc:
        return {
            "ok": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": str(exc),
        }


async def build_ai_health_report(*, probe: bool = False) -> dict[str, Any]:
    chain = parse_fallback_chain(os.getenv("AI_FALLBACK_CHAIN"))
    chain_set = {n.value for n in chain}
    active = build_providers_from_chain(chain)
    active_names = {p.name.value for p in active}
    safe_names = memory_safe_provider_names()

    router_ready = False
    router_error: Optional[str] = None
    try:
        from .factory import get_default_router

        get_default_router()
        router_ready = True
    except Exception as exc:
        router_error = str(exc)

    provider_rows: list[dict[str, Any]] = []
    probe_tasks = []

    for name in ProviderName:
        instance = build_provider(name)
        row: dict[str, Any] = {
            "name": name.value,
            "configured": instance.is_configured(),
            "model": instance.model,
            "default_model": DEFAULT_MODELS[name],
            "in_fallback_chain": name.value in chain_set,
            "active_in_router": name.value in active_names,
        }
        if probe and instance.is_configured():
            probe_tasks.append((row, instance))
        provider_rows.append(row)

    if probe and probe_tasks:
        results = await asyncio.gather(
            *[_probe_one(inst, PROBE_TIMEOUT_SECONDS) for _, inst in probe_tasks],
            return_exceptions=False,
        )
        for (row, _), probe_result in zip(probe_tasks, results):
            row["probe"] = probe_result

    configured_count = sum(1 for r in provider_rows if r["configured"])
    active_count = len(active_names)
    probed_ok = sum(
        1 for r in provider_rows if r.get("probe", {}).get("ok") is True
    )

    if not router_ready or active_count == 0:
        status = "down"
    elif probe and probed_ok < active_count:
        status = "degraded"
    elif probe and probed_ok == active_count:
        status = "ok"
    elif router_ready and active_count > 0:
        status = "ok"
    else:
        status = "degraded"

    return {
        "status": status,
        "router_ready": router_ready,
        "router_error": router_error,
        "fallback_chain": [n.value for n in chain],
        "active_providers": sorted(active_names),
        "configured_count": configured_count,
        "active_count": active_count,
        "probe_enabled": probe,
        "probe_timeout_seconds": PROBE_TIMEOUT_SECONDS if probe else None,
        # Providers allowed for calls that carry memories or chat history.
        "memory_safe_providers": [
            {
                "name": n.value,
                "configured": build_provider(n).is_configured(),
                "development_only": n in UNTRUSTED_MEMORY_PROVIDERS,
            }
            for n in safe_names
        ],
        "providers": provider_rows,
    }
