import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

import models
import schemas
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from ai_service.extractor import extract_reminder_details
from ai_service.router.rules import (
    is_greeting,
    looks_like_question,
    looks_like_reminder,
    match_memory_rule,
)
from ai_service.router.turn import REMINDER_INTENTS, route_turn
from services.chat_history import get_message_for_user, list_history, record_exchange
from services.local_schedule import utc_to_local
from services.memory_chat import (
    handle_memory_rule,
    handle_routed_turn,
    save_conversation_memories,
)
from services.repeat_schedule import repeat_label

from database import get_db
from deps import get_current_user
from rate_limit import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

ROUTER_UNAVAILABLE_REPLY = "I couldn't check that just now. Please try again in a moment."


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


async def _build_reply(
    body: schemas.ChatRequest,
    db: Session,
    current_user: models.User,
    *,
    preparsed: Optional[dict] = None,
) -> Tuple[schemas.ChatResponse, str]:
    """Reminder-flow reply to one chat message, plus the intent stored in history.

    ``preparsed``: reminder slots from the turn router (skips the Layer 3 AI call).
    """
    response, intent = await _reminder_reply(body, db, current_user, preparsed=preparsed)
    response.intent = intent
    return response, intent


async def _reminder_reply(
    body: schemas.ChatRequest,
    db: Session,
    current_user: models.User,
    *,
    preparsed: Optional[dict] = None,
) -> Tuple[schemas.ChatResponse, str]:
    if is_greeting(body.message):
        reply = (
            "Hello! I'm your AI Reminder assistant. How can I help you today? "
            "You can say things like 'Remind me to call Mom tomorrow at 9am'."
        )
        return schemas.ChatResponse(reply=reply, parsed_reminder=None), "greeting"

    recent = _server_recent_reminders(db, current_user.id)
    parsed = await extract_reminder_details(
        body.message,
        pending_context=body.pending_context,
        recent_reminders=recent,
        user_timezone=current_user.timezone,
        preparsed=preparsed,
    )

    if not parsed:
        logger.warning("event=chat_parse_failed user_id=%s", current_user.id)
        reply = (
            "I couldn't quite understand that. Please say what to do and when "
            "(for example: 'Remind me to buy milk at 5 PM today')."
        )
        return schemas.ChatResponse(reply=reply, parsed_reminder=None), "unparsed"

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
            return schemas.ChatResponse(reply=reply, parsed_reminder=draft), intent
        reply = (
            "I couldn't match that to one of your saved reminders. "
            "Open the Reminders tab so your list is up to date, or name the task clearly."
        )
        return schemas.ChatResponse(reply=reply, parsed_reminder=None), intent

    if parsed.get("needs_clarification"):
        q = parsed.get("clarification_question") or (
            "Could you add a bit more detail about what and when?"
        )
        return (
            schemas.ChatResponse(
                reply=q,
                parsed_reminder=_client_reminder_draft(parsed, confirmable=False),
            ),
            intent,
        )

    if parsed.get("needs_time") or not parsed.get("time"):
        task = parsed.get("task") or "that"
        date = parsed.get("date") or ""
        reply = (
            f"I've noted \"{task}\""
            + (f" on {date}" if date else "")
            + ". What time should I remind you? (e.g. 9:00 PM or 21:00)"
        )
        return (
            schemas.ChatResponse(
                reply=reply,
                parsed_reminder=_client_reminder_draft(parsed, confirmable=False),
            ),
            intent,
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
    return (
        schemas.ChatResponse(
            reply=reply,
            parsed_reminder=_client_reminder_draft(parsed, confirmable=True),
        ),
        intent,
    )


async def _route(
    body: schemas.ChatRequest, db: Session, user: models.User
) -> Tuple[schemas.ChatResponse, str, List[models.Memory]]:
    """Decide what the message is for and handle it (design §7).

    1. Answering a reminder draft ("make it 9pm") → reminder flow.
    2. Memory rules ("remember that…", "forget…", "what's my…") → memory engine.
    3. Greetings and clear reminder requests → reminder flow (no router call).
    4. Otherwise one turn-router AI call. If it fails → reminder flow, as before 8.1b.

    Memory changes are committed here, before the history write, so a history
    failure can't undo a save the reply already confirmed.
    """
    if body.pending_context:
        response, intent = await _build_reply(body, db, user)
        return response, intent, []

    rule = match_memory_rule(body.message)
    if rule is not None:
        turn = await handle_memory_rule(rule, db=db, user=user)
        db.commit()
        return turn.response, turn.intent, turn.saved

    if is_greeting(body.message) or looks_like_reminder(body.message):
        response, intent = await _build_reply(body, db, user)
        return response, intent, []

    decision = await route_turn(
        body.message,
        today=utc_to_local(datetime.now(timezone.utc), user.timezone).date().isoformat(),
        timezone=user.timezone,
    )
    if decision is None:
        # No allowlisted provider answered (e.g. a free-tier rate limit). Don't turn
        # a question into a fake reminder; anything else keeps the reminder flow.
        if looks_like_question(body.message):
            return schemas.ChatResponse(reply=ROUTER_UNAVAILABLE_REPLY, intent="unavailable"), "unavailable", []
        response, intent = await _build_reply(body, db, user)
        return response, intent, []

    if decision.intent in REMINDER_INTENTS:
        response, intent = await _build_reply(
            body, db, user, preparsed=decision.reminder_slots()
        )
        # "Remind me to call Sara, she's my sister": the fact is saved too.
        actions, saved = await save_conversation_memories(decision.candidates(), db, user)
        if saved:
            db.commit()
        response.memory_actions = [schemas.MemoryAction(**a) for a in actions]
        return response, intent, saved

    turn = await handle_routed_turn(decision, body.message, db=db, user=user)
    db.commit()
    return turn.response, turn.intent, turn.saved


@router.post("", response_model=schemas.ChatResponse)
@limiter.limit("60/minute")
async def process_chat(
    request: Request,
    body: schemas.ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _ = request
    received_at = datetime.now(timezone.utc)
    logger.info(
        "event=chat_request user_id=%s message_len=%s has_pending_context=%s",
        current_user.id,
        len(body.message or ""),
        bool(body.pending_context),
    )
    response, intent, saved_memories = await _route(body, db, current_user)
    logger.info(
        "event=chat_turn user_id=%s intent=%s memory_actions=%s",
        current_user.id,
        intent,
        len(response.memory_actions),
    )

    # A history failure must never cost the user their reply.
    try:
        user_msg, _ = record_exchange(
            db,
            user_id=current_user.id,
            user_text=body.message,
            reply=response.reply,
            intent=intent,
            received_at=received_at,
            replied_at=datetime.now(timezone.utc),
        )
        db.flush()
        # "You told me on Sep 12": link new memories to the message they came from.
        for memory in saved_memories:
            memory.source_message_id = user_msg.id
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("event=chat_history_write_failed user_id=%s", current_user.id)
    return response


@router.get("/history", response_model=schemas.ChatHistoryResponse)
@limiter.limit("60/minute")
def get_chat_history(
    request: Request,
    before: Optional[UUID] = Query(None, description="Return messages older than this message id"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _ = request
    cursor = None
    if before is not None:
        # Same 404 for a missing id and another user's id, so nothing leaks.
        cursor = get_message_for_user(db, current_user.id, before)
        if cursor is None:
            raise HTTPException(status_code=404, detail="Message not found")

    rows, has_more = list_history(db, current_user.id, before=cursor, limit=limit)
    logger.info(
        "event=chat_history_list user_id=%s count=%s has_more=%s",
        current_user.id,
        len(rows),
        has_more,
    )
    return schemas.ChatHistoryResponse(
        messages=[schemas.ChatHistoryMessage.model_validate(r) for r in rows],
        has_more=has_more,
        next_before=rows[-1].id if has_more and rows else None,
    )
