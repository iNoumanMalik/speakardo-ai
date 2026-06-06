"""Unit tests for hybrid reminder parsing (Layers 1–2, no LLM)."""

from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

# ai_service lives next to backend/
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
)

from ai_service.extractor import get_mock_reminder
from ai_service.parsing.hybrid import parse_reminder_hybrid, should_use_llm
from ai_service.parsing.layer1_rules import parse_layer1
from ai_service.parsing.layer2_datetime import parse_layer2


@pytest.fixture()
def fixed_tz():
    return "America/New_York"


def test_layer1_extracts_task_and_repeat():
    result = parse_layer1("Remind me to take medicine every day")
    assert result.task == "take medicine"
    assert result.repeat == "daily"


def test_layer2_parses_tomorrow_at_3pm(fixed_tz):
    layer1 = parse_layer1("Remind me to buy milk tomorrow at 3pm")
    result = parse_layer2(
        "Remind me to buy milk tomorrow at 3pm",
        layer1,
        user_timezone=fixed_tz,
    )
    assert result.task == "buy milk"
    assert result.time == "15:00"
    assert result.date is not None
    assert not should_use_llm(result)


def test_layer2_in_2_hours(fixed_tz):
    layer1 = parse_layer1("Team standup in 2 hours")
    result = parse_layer2(
        "Team standup in 2 hours",
        layer1,
        user_timezone=fixed_tz,
    )
    assert "standup" in (result.task or "").lower()
    assert result.time is not None
    assert result.date is not None


def test_task_only_skips_llm():
    layer1 = parse_layer1("Remind me to call Ali")
    layer2 = parse_layer2("Remind me to call Ali", layer1, user_timezone="UTC")
    assert layer2.task == "call Ali"
    assert layer2.time is None
    assert not should_use_llm(layer2)


def test_refine_draft_time_follow_up():
    pending = {
        "task": "call mom",
        "date": "2026-05-25",
        "time": None,
        "repeat": None,
    }
    layer1 = parse_layer1("make it 9pm", pending_context=pending)
    assert layer1.intent == "refine_draft"
    layer2 = parse_layer2(
        "make it 9pm",
        layer1,
        user_timezone="UTC",
    )
    assert layer2.time == "21:00"
    assert layer2.task == "call mom"
    assert not should_use_llm(layer2)


def test_ambiguous_time_uses_llm():
    layer1 = parse_layer1("Remind me to call Ali at 3")
    layer2 = parse_layer2(
        "Remind me to call Ali at 3",
        layer1,
        user_timezone="UTC",
    )
    assert should_use_llm(layer2)


def test_mock_reminder_full_parse():
    parsed = get_mock_reminder(
        "Remind me to buy milk tomorrow at 3pm",
        user_timezone="UTC",
    )
    assert parsed["task"] == "buy milk"
    assert parsed["time"] == "15:00"
    assert parsed["needs_time"] is False


def test_edit_saved_match():
    recent = [
        {"id": "uuid-gym", "task": "Gym workout", "datetime": "2026-05-25T06:00:00+00:00"},
    ]
    layer1 = parse_layer1(
        "Change my gym reminder to 7pm",
        recent_reminders=recent,
    )
    assert layer1.intent == "edit_saved"
    assert layer1.editable_reminder_id == "uuid-gym"


def test_hybrid_uses_rules_without_llm():
    with patch(
        "ai_service.parsing.hybrid.parse_layer3_llm",
        new_callable=AsyncMock,
    ) as mock_llm:
        result = asyncio.run(
            parse_reminder_hybrid(
                "Remind me to water plants tomorrow at 8am",
                user_timezone="UTC",
            )
        )
        mock_llm.assert_not_called()
        assert result is not None
        assert result["task"] == "water plants"
        assert result["time"] == "08:00"
        assert result.get("_parser_layer") in ("layer1", "layer2")


def test_hybrid_calls_llm_when_ambiguous():
    with patch(
        "ai_service.parsing.hybrid.parse_layer3_llm",
        new_callable=AsyncMock,
    ) as mock_llm:
        mock_llm.return_value = {
            "intent": "create",
            "task": "call Ali",
            "date": "2026-05-25",
            "time": "15:00",
            "repeat": None,
            "needs_time": False,
            "needs_clarification": False,
            "clarification_question": None,
            "editable_reminder_id": None,
        }
        result = asyncio.run(
            parse_reminder_hybrid(
                "Remind me to call Ali at 3",
                user_timezone="UTC",
            )
        )
        mock_llm.assert_called_once()
        assert result is not None
        assert result["time"] == "15:00"
