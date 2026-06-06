"""
Reminder extraction — hybrid Layer 1 → Layer 2 → Layer 3 (LLM).

Public entry: extract_reminder_details()
"""

from __future__ import annotations

import logging
from typing import Optional

from .parsing.hybrid import _finalize_rule_result, parse_reminder_hybrid
from .parsing.layer1_rules import parse_layer1
from .parsing.layer2_datetime import parse_layer2
from .parsing.layer3_llm import clean_json_response, extract_json_from_text
from .parsing.normalize import normalize_parsed

logger = logging.getLogger(__name__)

# Backward-compatible alias.
_normalize_parsed = normalize_parsed


def get_mock_reminder(
    message: str,
    pending_context: Optional[dict] = None,
    user_timezone: Optional[str] = None,
) -> dict:
    """Offline fallback using Layer 1 + Layer 2 only (no LLM)."""
    layer1 = parse_layer1(message, pending_context=pending_context)
    layer2 = parse_layer2(
        message,
        layer1,
        user_timezone=user_timezone,
    )
    return _finalize_rule_result(layer2)


async def extract_reminder_details(
    message: str,
    pending_context: Optional[dict] = None,
    recent_reminders: Optional[list] = None,
    user_timezone: Optional[str] = None,
) -> Optional[dict]:
    """
    Extract structured reminder data via hybrid parsing.

    Returns dict with:
    intent, task, date, time, repeat, needs_time, needs_clarification,
    clarification_question, editable_reminder_id (optional).
    """
    try:
        return await parse_reminder_hybrid(
            message,
            pending_context=pending_context,
            recent_reminders=recent_reminders,
            user_timezone=user_timezone,
        )
    except Exception as e:
        logger.exception("event=extract_reminder_details_exception error=%s", e)
        try:
            return get_mock_reminder(
                message,
                pending_context=pending_context,
                user_timezone=user_timezone,
            )
        except Exception:
            return None


async def test_gemini():
    test_messages = [
        "Remind me to buy milk tomorrow at 3pm",
        "Call mom every Monday at 9am",
        "Team meeting in 2 hours",
        "Pay rent on the 1st of each month at 10am",
    ]
    for msg in test_messages:
        result = await extract_reminder_details(msg)
        print(f"Input: {msg}")
        print(f"Output: {result}\n")
