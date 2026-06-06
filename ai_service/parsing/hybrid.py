"""
Hybrid reminder parser — Layer 1 → Layer 2 → Layer 3 (LLM fallback).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .layer1_rules import parse_layer1
from .layer2_datetime import parse_layer2
from .layer3_llm import parse_layer3_llm
from .normalize import normalize_parsed
from .types import ParseResult

logger = logging.getLogger(__name__)

# Skip LLM when rule layers reach this confidence and have no ambiguities.
_RULE_CONFIDENCE_THRESHOLD = 0.72


def _finalize_rule_result(result: ParseResult) -> dict:
    raw = result.to_dict()
    if not raw.get("date") and raw.get("task") and not raw.get("needs_clarification"):
        pass  # normalize_parsed fills today
    if not raw.get("time"):
        raw["needs_time"] = True
    else:
        raw["needs_time"] = False
    if result.ambiguities and not raw.get("clarification_question"):
        raw["needs_clarification"] = True
        raw["clarification_question"] = (
            "Did you mean morning or evening? Please include am/pm."
        )
    normalized = normalize_parsed(raw)
    normalized["_parser_layer"] = result.parser_layer
    normalized["_parser_confidence"] = result.confidence
    return normalized


def should_use_llm(result: ParseResult) -> bool:
    """Return True when Layers 1–2 are not trustworthy enough."""
    if result.ambiguities:
        return True
    if not result.task or len(result.task) < 2:
        return True
    if result.needs_clarification:
        return True

    if result.intent == "edit_saved":
        if not result.editable_reminder_id:
            return True
        return not result.time

    if result.intent == "refine_draft":
        return not result.time

    # Task with or without time — chat handles needs_time.
    if result.confidence >= _RULE_CONFIDENCE_THRESHOLD:
        return False

    if result.task and not result.ambiguities:
        return False

    return True


async def parse_reminder_hybrid(
    message: str,
    *,
    pending_context: Optional[dict[str, Any]] = None,
    recent_reminders: Optional[list] = None,
    user_timezone: Optional[str] = None,
) -> Optional[dict]:
    """
    Run the hybrid pipeline:
    1. Layer 1 — regex / keywords / intent
    2. Layer 2 — dateparser + parsedatetime
    3. Layer 3 — LLM when rules are insufficient
    """
    layer1 = parse_layer1(
        message,
        pending_context=pending_context,
        recent_reminders=recent_reminders,
    )
    layer2 = parse_layer2(
        message,
        layer1,
        user_timezone=user_timezone,
    )

    use_llm = should_use_llm(layer2)

    logger.info(
        "event=hybrid_parse layer1_confidence=%.2f layer2_confidence=%.2f use_llm=%s intent=%s",
        layer1.confidence,
        layer2.confidence,
        use_llm,
        layer2.intent,
    )

    if not use_llm:
        logger.info(
            "event=hybrid_parse_rule_hit layer=%s task=%s date=%s time=%s",
            layer2.parser_layer,
            bool(layer2.task),
            layer2.date,
            layer2.time,
        )
        return _finalize_rule_result(layer2)

    llm_result = await parse_layer3_llm(
        message,
        pending_context=pending_context,
        recent_reminders=recent_reminders,
        user_timezone=user_timezone,
        rule_hints=layer2,
    )
    if llm_result:
        return llm_result

    # LLM unavailable or failed — return best rule parse if usable.
    if layer2.task and not layer2.ambiguities:
        logger.warning("event=hybrid_parse_llm_fallback_to_rules")
        return _finalize_rule_result(layer2)

    logger.warning("event=hybrid_parse_failed")
    return None
