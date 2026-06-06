import logging
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

import models
import schemas
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from ai_service.extractor import extract_reminder_details
from services.repeat_schedule import repeat_label

from database import get_db
from deps import get_current_user
from rate_limit import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


def _server_recent_reminders(db: Session, user_id: UUID, limit: int = 40) -> List[Dict[str, Any]]:
    rows = (
        db.query(models.Reminder)
        .filter(
            models.Reminder.user_id == user_id,
            models.Reminder.status != models.ReminderStatus.COMPLETED.value,
        )
        .order_by(models.Reminder.datetime.asc())
        .limit(limit)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": str(r.id),
                "task": r.task,
                "datetime": r.datetime.isoformat() if r.datetime else None,
                "repeat": r.repeat,
                "status": r.status,
            }
        )
    return out


def _client_reminder_draft(parsed: dict, *, confirmable: bool) -> dict:
    return {
        "task": parsed.get("task"),
        "date": parsed.get("date"),
        "time": parsed.get("time"),
        "repeat": parsed.get("repeat"),
        "confirmable": confirmable,
    }


@router.post("", response_model=schemas.ChatResponse)
@limiter.limit("60/minute")
async def process_chat(
    request: Request,
    body: schemas.ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _ = request
    logger.info(
        "event=chat_request user_id=%s message_len=%s has_pending_context=%s",
        current_user.id,
        len(body.message or ""),
        bool(body.pending_context),
    )
    message_lower = body.message.lower().strip()
    greetings = [
        "hi",
        "hello",
        "hey",
        "greetings",
        "good morning",
        "good afternoon",
        "good evening",
    ]
    if message_lower in greetings or any(
        message_lower.startswith(g + " ") for g in greetings
    ):
        reply = (
            "Hello! I'm your AI Reminder assistant. How can I help you today? "
            "You can say things like 'Remind me to call Mom tomorrow at 9am'."
        )
        return schemas.ChatResponse(reply=reply, parsed_reminder=None)

    recent = _server_recent_reminders(db, current_user.id)
    parsed = await extract_reminder_details(
        body.message,
        pending_context=body.pending_context,
        recent_reminders=recent,
        user_timezone=current_user.timezone,
    )

    if not parsed:
        logger.warning("event=chat_parse_failed user_id=%s", current_user.id)
        reply = (
            "I couldn't quite understand that. Please say what to do and when "
            "(for example: 'Remind me to buy milk at 5 PM today')."
        )
        return schemas.ChatResponse(reply=reply, parsed_reminder=None)

    intent = parsed.get("intent") or "create"
    logger.info(
        "event=chat_parse_result user_id=%s intent=%s needs_time=%s needs_clarification=%s parser_layer=%s",
        current_user.id,
        intent,
        parsed.get("needs_time"),
        parsed.get("needs_clarification"),
        parsed.get("_parser_layer"),
    )
    eid = parsed.get("editable_reminder_id")

    if intent == "edit_saved" and eid:
        allowed = {str(r.get("id")) for r in recent if r.get("id")}
        has_slot = (
            bool(parsed.get("task"))
            and bool(parsed.get("date"))
            and bool(parsed.get("time"))
            and not parsed.get("needs_time")
            and not parsed.get("needs_clarification")
        )
        if str(eid) in allowed and has_slot:
            task = parsed["task"]
            date = parsed["date"]
            time_str = parsed["time"]
            reply = (
                f"Update your reminder to \"{task}\" on {date} at {time_str}? "
                "Tap yes to save the change."
            )
            draft = _client_reminder_draft(parsed, confirmable=True)
            draft["edit_reminder_id"] = str(eid)
            return schemas.ChatResponse(reply=reply, parsed_reminder=draft)
        reply = (
            "I couldn't match that to one of your saved reminders. "
            "Open the Reminders tab so your list is up to date, or name the task clearly."
        )
        return schemas.ChatResponse(reply=reply, parsed_reminder=None)

    if parsed.get("needs_clarification"):
        q = parsed.get("clarification_question") or (
            "Could you add a bit more detail about what and when?"
        )
        return schemas.ChatResponse(
            reply=q,
            parsed_reminder=_client_reminder_draft(parsed, confirmable=False),
        )

    if parsed.get("needs_time") or not parsed.get("time"):
        task = parsed.get("task") or "that"
        date = parsed.get("date") or ""
        reply = (
            f"I've noted \"{task}\""
            + (f" on {date}" if date else "")
            + ". What time should I remind you? (e.g. 9:00 PM or 21:00)"
        )
        return schemas.ChatResponse(
            reply=reply,
            parsed_reminder=_client_reminder_draft(parsed, confirmable=False),
        )

    task = parsed.get("task", "your task")
    date = parsed.get("date", "")
    time_str = parsed.get("time", "")
    repeat_hint = ""
    if parsed.get("repeat"):
        label = repeat_label(parsed.get("repeat"))
        if label:
            repeat_hint = f" ({label.lower()})"
    reply = f"Should I remind you to {task} on {date} at {time_str}{repeat_hint}?"
    return schemas.ChatResponse(
        reply=reply,
        parsed_reminder=_client_reminder_draft(parsed, confirmable=True),
    )
