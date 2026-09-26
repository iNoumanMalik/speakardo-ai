"""AnthropicProvider calls messages.create with arguments the installed SDK accepts."""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import create_autospec

# ai_service lives next to backend/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ai_service.gateway.providers.anthropic_provider import AnthropicProvider


def test_generate_matches_the_installed_sdk_signature():
    provider = AnthropicProvider(model="claude-haiku-4-5", api_key="test-key")
    response = SimpleNamespace(content=[SimpleNamespace(type="text", text="OK")])

    async def respond(*args, **kwargs):
        return response

    # Autospec binds calls against the real create() signature, so an argument the
    # SDK no longer accepts (e.g. temperature in anthropic 1.x) raises TypeError.
    create = create_autospec(
        provider._client.messages.create, side_effect=lambda *a, **kw: respond()
    )
    provider._client.messages.create = create

    text = asyncio.run(provider.generate("Reply OK", temperature=0))

    assert text == "OK"
    kwargs = create.call_args.kwargs
    assert kwargs["model"] == "claude-haiku-4-5"
    assert "temperature" not in kwargs
    assert kwargs["extra_body"] == {"temperature": 0}
