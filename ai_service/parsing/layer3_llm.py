"""
Layer 3 — LLM fallback.

Used when Layers 1–2 are not confident enough.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from ..gateway.exceptions import AllProvidersFailedError
from ..gateway.factory import get_default_router
from .normalize import normalize_parsed
from .types import ParseResult

logger = logging.getLogger(__name__)


def clean_json_response(content: str) -> str:
    content = content.strip()
    if content.startswith("```json"):
        content = content.replace("```json", "").replace("```", "").strip()
    elif content.startswith("```"):
        content = content.replace("```", "").strip()
    return content


def extract_json_from_text(text: str) -> dict:
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return {}


def _today_utc() -> str:
    from .normalize import _today_utc as today

    return today()


def _rule_hints(rules: Optional[ParseResult]) -> str:
    if rules is None:
        return "null"
    payload = {
        "intent": rules.intent,
        "task": rules.task,
        "date": rules.date,
        "time": rules.time,
        "repeat": rules.repeat,
        "editable_reminder_id": rules.editable_reminder_id,
        "confidence": rules.confidence,
        "ambiguities": rules.ambiguities,
    }
    return json.dumps(payload, ensure_ascii=False)


async def parse_layer3_llm(
    message: str,
    *,
    pending_context: Optional[dict[str, Any]] = None,
    recent_reminders: Optional[list] = None,
    user_timezone: Optional[str] = None,
    rule_hints: Optional[ParseResult] = None,
) -> Optional[dict]:
    try:
        router = get_default_router()
    except RuntimeError:
        logger.warning("event=ai_layer3_router_missing")
        return None

    now = datetime.now()
    tz_note = user_timezone or "UTC"
    ctx_json = (
        json.dumps(pending_context, ensure_ascii=False) if pending_context else "null"
    )
    recent_json = (
        json.dumps(recent_reminders, ensure_ascii=False) if recent_reminders else "[]"
    )
    hints_json = _rule_hints(rule_hints)

    system_prompt = f"""
You extract reminder data from chat. User timezone: {tz_note}. Reference now (server): {now.strftime('%Y-%m-%d %H:%M:%S')}.
Resolve relative phrases ("today", "tomorrow", "in 2 hours") in the user's timezone. Dates: YYYY-MM-DD. Times: HH:MM 24-hour.

Pending draft (merge/refine if the user is answering or correcting): {ctx_json}

Existing reminders (id + task + datetime) — match "change my gym reminder" etc.: {recent_json}

Rule-based parser hints (may be partial — correct or complete them): {hints_json}

Return ONE JSON object only (no markdown):
{{
  "intent": "create" | "refine_draft" | "edit_saved",
  "task": string or null,
  "date": "YYYY-MM-DD" or null,
  "time": "HH:MM" or null,
  "repeat": string or null,
  "needs_time": boolean,
  "needs_clarification": boolean,
  "clarification_question": string or null,
  "editable_reminder_id": string UUID or null
}}

Rules:
- Merge pending draft on time-only corrections ("make it 9pm").
- Default date to today ({_today_utc()}) when task is set but no date given.
- Task without time → needs_time true.
- Ambiguous time ("at 3") → needs_clarification true with one short question.
- edit_saved when user clearly refers to a listed reminder.
- repeat: null, "daily", "weekly", "weekdays", or "monthly" only.
- Raw JSON only.
"""

    try:
        logger.info(
            "event=ai_layer3_request pending_context=%s recent_reminders_count=%s rule_confidence=%s",
            bool(pending_context),
            len(recent_reminders or []),
            rule_hints.confidence if rule_hints else None,
        )
        full_prompt = f"{system_prompt}\n\nUser message: {message}"
        result = await router.generate(
            full_prompt,
            temperature=0,
            response_format="json",
        )
        if not result.text:
            logger.warning(
                "event=ai_layer3_empty_response provider=%s model=%s",
                result.provider,
                result.model,
            )
            return None

        reply_content = clean_json_response(result.text)
        try:
            parsed = json.loads(reply_content)
        except json.JSONDecodeError:
            parsed = extract_json_from_text(reply_content)

        if not parsed or "task" not in parsed:
            logger.warning(
                "event=ai_layer3_invalid_payload provider=%s model=%s",
                result.provider,
                result.model,
            )
            return None

        logger.info(
            "event=ai_layer3_success provider=%s model=%s fallback_used=%s intent=%s",
            result.provider,
            result.model,
            result.fallback_used,
            parsed.get("intent"),
        )
        normalized = normalize_parsed(parsed)
        normalized["_parser_layer"] = "layer3"
        return normalized
    except AllProvidersFailedError as e:
        logger.error("event=ai_layer3_all_providers_failed error=%s", e)
        return None
    except Exception as e:
        logger.exception("event=ai_layer3_exception error=%s", e)
        return None
