"""Chat turns handled by the memory engine (8.1a rules + 8.1b turn router).

- Rule-matched turns: save, answer, list and forget.
- Routed turns: whatever the turn router decided that isn't a reminder, plus
  facts the user stated along the way (saved from any turn, including reminders).

The caller commits. Budget per turn (design §7): at most one AI call to
understand (extraction or the turn router) and one to reply, plus embeddings.
"""

import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import models
import schemas
from services import memory_store
from services.local_schedule import utc_to_local
from services.repeat_schedule import repeat_label

# ai_service lives next to backend/ (same pattern as routers/chat.py).
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from ai_service.memory.extraction import extract_memory
from ai_service.memory.policy import (
    Decision,
    MemoryCandidate,
    MemorySettings,
    PolicyResult,
    decide,
    is_sensitive_text,
)
from ai_service.memory.scoring import rank
from ai_service.reply.grounded import (
    NOT_SAVED_REPLY,
    ContextMemory,
    ContextReminder,
    generate_reply,
)
from ai_service.router.rules import (
    MEMORY_FORGET,
    MEMORY_LIST,
    MEMORY_QUERY,
    MEMORY_SAVE,
    RuleMatch,
)
from ai_service.router.turn import CHAT, TurnDecision

logger = logging.getLogger(__name__)

MAX_LISTED = 30
MAX_REMINDERS_IN_PROMPT = 10

CATEGORY_TITLES = {
    "personal": "About you",
    "work": "Work",
    "people": "People",
    "places": "Places",
    "routine": "Routine",
    "other": "Other",
}

NOT_SAVED_SENSITIVE = (
    "I don't save health, money or other sensitive details yet, so I haven't stored that."
)
NOT_SAVED_INSTRUCTION = (
    "I can remember facts about you, but not instructions for how I should behave."
)
NOT_SAVED_DISABLED = "Memory is turned off, so I didn't save that."
NOTHING_SAVED_HINT = 'You can say things like "Remember that my office is in Blue Area".'
CHAT_FALLBACK = (
    "I'm here to help. I can set reminders or remember things for you, like "
    '"Remind me to call Sara at 5pm" or "Remember that my office is in Blue Area".'
)


@dataclass
class MemoryTurn:
    response: schemas.ChatResponse
    intent: str
    # New memories to link to the stored user message once it exists.
    saved: list[models.Memory] = field(default_factory=list)


@dataclass
class _Stored:
    """One candidate after the policy and the store have had their say."""

    policy: PolicyResult
    outcome: Optional[memory_store.SaveOutcome] = None

    @property
    def action(self) -> Optional[str]:
        return self.outcome.action if self.outcome else None


def settings_for(user: models.User) -> MemorySettings:
    return MemorySettings(
        memory_enabled=bool(getattr(user, "memory_enabled", True)),
        learn_from_chat=bool(getattr(user, "learn_from_chat", True)),
    )


# --- small text helpers ---------------------------------------------------------------


def _action(type_: str, label: str, memory: Optional[models.Memory] = None, *, undo: bool) -> dict:
    return {
        "type": type_,
        "memory_id": str(memory.id) if memory is not None else None,
        "label": label,
        "undo": undo,
    }


def _label(prefix: str, content: str) -> str:
    """Chip text: "Saved: Your office is in Blue Area" (no trailing period)."""
    return f"{prefix}: {content.strip().rstrip('.')}"


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else f"{text}."


def _inline(text: str) -> str:
    """"Your office is in Blue Area" → "your office is in Blue Area" mid-sentence."""
    text = text.strip().rstrip(".")
    return text[0].lower() + text[1:] if re.match(r"^(?:Your|You)\b", text) else text


def _raw_candidate(text: str) -> MemoryCandidate:
    """Fallback when extraction is unavailable: keep the user's own words as a note."""
    return MemoryCandidate(content=_sentence(text[:1].upper() + text[1:]), basis="explicit_request")


def _reply(
    text: str,
    intent: str,
    actions: Optional[list[dict]] = None,
    *,
    saved: Optional[list[models.Memory]] = None,
) -> MemoryTurn:
    return MemoryTurn(
        schemas.ChatResponse(reply=text, intent=intent, memory_actions=actions or []),
        intent,
        saved or [],
    )


def _local_today(user: models.User) -> str:
    return utc_to_local(datetime.now(timezone.utc), user.timezone).date().isoformat()


# --- AI helpers (mocked in tests) -------------------------------------------------------


async def _embed(text: str) -> tuple[Optional[list[float]], Optional[str]]:
    """Embedding for a memory or a question, or (None, None) on failure."""
    try:
        from ai_service.gateway.embeddings import embed
        from ai_service.gateway.factory import get_default_embedder

        embedder = get_default_embedder()
        vectors = await embed([text], embedder=embedder)
        return vectors[0], embedder.model
    except Exception as exc:
        logger.warning("event=memory_embed_failed error_type=%s", type(exc).__name__)
        return None, None


async def _generate_reply(message: str, **kwargs):
    return await generate_reply(message, **kwargs)


# --- saving ------------------------------------------------------------------------------


async def _store(candidate: MemoryCandidate, settings: MemorySettings, db, user) -> _Stored:
    """Apply the save policy, then embed and store what passes."""
    result = decide(candidate, settings)
    if not result.should_save:
        return _Stored(result)
    c = result.candidate
    embedding, embedding_model = await _embed(c.content)
    outcome = memory_store.save_memory(
        db,
        user.id,
        content=c.content,
        kind=c.kind,
        category=c.category,
        key=c.key,
        subject=c.subject,
        value=c.value,
        source="user_explicit" if c.basis == "explicit_request" else "conversation",
        confidence=result.confidence,
        importance=result.importance,
        temporary_days=result.temporary_days,
        embedding=embedding,
        embedding_model=embedding_model,
    )
    return _Stored(result, outcome)


def _chips(stored: list[_Stored]) -> tuple[list[dict], list[models.Memory]]:
    actions, saved = [], []
    for s in stored:
        memory = s.outcome.memory if s.outcome else None
        if s.action == "saved":
            actions.append(_action("saved", _label("Saved", memory.content), memory, undo=True))
            saved.append(memory)
        elif s.action == "updated":
            actions.append(_action("updated", _label("Updated", memory.content), memory, undo=True))
            saved.append(memory)
    return actions, saved


def _save_reply(stored: list[_Stored]) -> Optional[str]:
    """Templated reply for an explicit save, or None if nothing worth saying."""
    done = [s for s in stored if s.action in ("saved", "updated", "duplicate")]
    if len(done) == 1:
        s = done[0]
        memory = s.outcome.memory
        if s.action == "updated":
            return (
                f"Updated: {_sentence(memory.content)} "
                f"(Before, I had: {_sentence(s.outcome.previous.content)})"
            )
        if s.action == "duplicate":
            return f"I already have that saved: {_sentence(memory.content)}"
        return f"Got it, I'll remember that {_inline(memory.content)}."
    if len(done) > 1:
        return f"Got it, I'll remember those {len(done)} things."
    decisions = {s.policy.decision for s in stored}
    if Decision.SKIP_SENSITIVE in decisions:
        return NOT_SAVED_SENSITIVE
    if Decision.SKIP_INSTRUCTION in decisions:
        return NOT_SAVED_INSTRUCTION
    if Decision.SKIP_DISABLED in decisions:
        return NOT_SAVED_DISABLED
    return None


def _sensitive_chip(stored: list[_Stored]) -> list[dict]:
    if any(s.policy.decision is Decision.SKIP_SENSITIVE for s in stored):
        return [_action("not_saved", "Not saved: sensitive", undo=False)]
    return []


async def save_conversation_memories(
    candidates: list[MemoryCandidate], db, user: models.User
) -> tuple[list[dict], list[models.Memory]]:
    """Facts stated in passing (e.g. inside a reminder): saved quietly, with chips.

    Nothing is said about candidates the policy refuses.
    """
    settings = settings_for(user)
    stored = [await _store(c, settings, db, user) for c in candidates]
    return _chips(stored)


async def _save_rule(match: RuleMatch, db, user: models.User) -> MemoryTurn:
    settings = settings_for(user)
    if not settings.memory_enabled:
        return _reply(NOT_SAVED_DISABLED, MEMORY_SAVE)
    # Checked before the AI call, so a sensitive detail never leaves the server.
    if is_sensitive_text(match.text):
        return _reply(
            NOT_SAVED_SENSITIVE, MEMORY_SAVE, [_action("not_saved", "Not saved: sensitive", undo=False)]
        )
    candidate = await extract_memory(match.text)
    if candidate is None:
        logger.info("event=memory_extraction_fallback user_id=%s", user.id)
        candidate = _raw_candidate(match.text)
    stored = [await _store(candidate, settings, db, user)]
    actions, saved = _chips(stored)
    return _reply(
        _save_reply(stored) or NOT_SAVED_DISABLED,
        MEMORY_SAVE,
        actions + _sensitive_chip(stored),
        saved=saved,
    )


async def _save_routed(
    decision: TurnDecision, message: str, db, user: models.User
) -> MemoryTurn:
    stored = [await _store(c, settings_for(user), db, user) for c in decision.candidates()]
    text = _save_reply(stored)
    if text is None:
        # Nothing clear enough to save ("I think I might switch jobs"): just talk.
        return await _chat(message, db, user)
    actions, saved = _chips(stored)
    return _reply(text, MEMORY_SAVE, actions + _sensitive_chip(stored), saved=saved)


# --- answering ------------------------------------------------------------------------------


def _reminder_facts(db, user: models.User) -> list[ContextReminder]:
    rows = (
        db.query(models.Reminder)
        .filter(
            models.Reminder.user_id == user.id,
            models.Reminder.status != models.ReminderStatus.COMPLETED.value,
        )
        .order_by(models.Reminder.datetime.asc())
        .limit(MAX_REMINDERS_IN_PROMPT)
        .all()
    )
    facts = []
    for r in rows:
        label = repeat_label(r.repeat)
        if label and r.local_time:
            when = f"{label.lower()} at {r.local_time}"
        else:
            when = utc_to_local(r.datetime, user.timezone).strftime("%a %d %b %Y, %H:%M")
        facts.append(ContextReminder(task=r.task, when=when))
    return facts


def _used_chips(memories: list[models.Memory]) -> list[dict]:
    return [_action("used", _label("Used", m.content), m, undo=False) for m in memories]


async def _relevant_memories(question: str, db, user: models.User) -> list[models.Memory]:
    """Semantic search + ranking (design §8). No embedding call if nothing is saved."""
    if memory_store.count_active(db, user.id) == 0:
        return []
    embedding, model = await _embed(question)
    if embedding is None:
        return []
    now = datetime.now(timezone.utc)
    candidates = memory_store.semantic_candidates(db, user.id, embedding, model=model, now=now)
    ranked = rank(
        [
            (
                m,
                similarity,
                m.importance,
                m.confidence,
                m.kind,
                (now - m.created_at).total_seconds() / 86400,
                m.valid_until is not None,
            )
            for m, similarity in candidates
        ]
    )
    return [s.item for s in ranked]


async def _answer(
    question: str,
    db,
    user: models.User,
    *,
    key: Optional[str],
    subject: Optional[str],
) -> MemoryTurn:
    """Exact lookup first (no AI), then semantic search + a grounded reply."""
    exact = memory_store.find_exact(db, user.id, key=key, subject=subject)
    if exact:
        memory_store.mark_used(db, exact)
        if len(exact) == 1:
            text = _sentence(exact[0].content)
        else:
            text = "Here's what I have:\n" + "\n".join(f"• {_sentence(m.content)}" for m in exact[:10])
        return _reply(text, MEMORY_QUERY, _used_chips(exact[:3]))

    memories = await _relevant_memories(question, db, user)
    reminders = _reminder_facts(db, user)
    if not memories and not reminders:
        return _reply(f"{NOT_SAVED_REPLY} {NOTHING_SAVED_HINT}", MEMORY_QUERY)

    reply = await _generate_reply(
        question,
        mode="answer",
        memories=[ContextMemory(m.id, m.content) for m in memories],
        reminders=reminders,
        today=_local_today(user),
        timezone=user.timezone,
    )
    if reply is None:
        if not memories:
            return _reply(f"{NOT_SAVED_REPLY} {NOTHING_SAVED_HINT}", MEMORY_QUERY)
        lines = "\n".join(f"• {_sentence(m.content)}" for m in memories[:3])
        return _reply(f"Here's what I have saved that might help:\n{lines}", MEMORY_QUERY)
    used = [m for m in memories if m.id in set(reply.used_ids)]
    memory_store.mark_used(db, used)
    return _reply(reply.text, MEMORY_QUERY, _used_chips(used))


async def _chat(
    message: str, db, user: models.User, extra_actions: Optional[list[dict]] = None,
    saved: Optional[list[models.Memory]] = None,
) -> MemoryTurn:
    """Small talk: an AI reply with the always-on profile as context."""
    profile = memory_store.profile_memories(db, user.id)
    reply = await _generate_reply(
        message,
        mode="chat",
        memories=[ContextMemory(m.id, m.content) for m in profile],
        reminders=[],
        today=_local_today(user),
        timezone=user.timezone,
    )
    if reply is None:
        return _reply(CHAT_FALLBACK, CHAT, extra_actions, saved=saved)
    used = [m for m in profile if m.id in set(reply.used_ids)]
    memory_store.mark_used(db, used)
    return _reply(reply.text, CHAT, (extra_actions or []) + _used_chips(used), saved=saved)


# --- list and forget --------------------------------------------------------------------------


def _list(db, user: models.User) -> MemoryTurn:
    rows = memory_store.list_active(db, user.id)
    if not rows:
        return _reply(f"I haven't saved anything about you yet. {NOTHING_SAVED_HINT}", MEMORY_LIST)
    groups: dict[str, list[str]] = {}
    for row in rows[:MAX_LISTED]:
        groups.setdefault(row.category, []).append(_sentence(row.content))
    order = list(CATEGORY_TITLES)
    sections = [
        f"{CATEGORY_TITLES.get(category, category.title())}\n"
        + "\n".join(f"• {item}" for item in groups[category])
        for category in sorted(groups, key=lambda c: order.index(c) if c in order else len(order))
    ]
    more = f"\n\n…and {len(rows) - MAX_LISTED} more." if len(rows) > MAX_LISTED else ""
    return _reply("Here's what I remember about you:\n\n" + "\n\n".join(sections) + more, MEMORY_LIST)


def _forget(
    text: str, db, user: models.User, *, key: Optional[str], subject: Optional[str]
) -> MemoryTurn:
    targets = memory_store.find_forget_targets(db, user.id, text=text, key=key, subject=subject)
    if not targets:
        return _reply("I couldn't find anything saved about that.", MEMORY_FORGET)
    exact = key is not None or subject is not None
    if len(targets) > 1 and not exact:
        lines = "\n".join(f"• {_sentence(t.content)}" for t in targets)
        return _reply(
            f"I found a few things. Which one should I forget?\n{lines}\n"
            'Say "forget" with a few words from it.',
            MEMORY_FORGET,
        )
    for target in targets:
        memory_store.forget(db, target)
    actions = [_action("forgotten", _label("Forgot", t.content), t, undo=True) for t in targets]
    if len(targets) == 1:
        reply = f"Okay, I've forgotten that {_inline(targets[0].content)}."
    else:
        reply = f"Okay, I've forgotten {len(targets)} things about that."
    return _reply(reply, MEMORY_FORGET, actions)


# --- entry points ---------------------------------------------------------------------------


async def handle_memory_rule(match: RuleMatch, *, db, user: models.User) -> MemoryTurn:
    if match.intent == MEMORY_SAVE:
        return await _save_rule(match, db, user)
    if match.intent == MEMORY_QUERY:
        return await _answer(match.text, db, user, key=match.key, subject=match.subject)
    if match.intent == MEMORY_LIST:
        return _list(db, user)
    if match.intent == MEMORY_FORGET:
        return _forget(match.text, db, user, key=match.key, subject=match.subject)
    raise ValueError(f"Unknown memory intent: {match.intent}")


async def handle_routed_turn(
    decision: TurnDecision, message: str, *, db, user: models.User
) -> MemoryTurn:
    """Non-reminder intents from the turn router."""
    from ai_service.memory.keys import normalise_key, normalise_subject

    if decision.intent == MEMORY_SAVE:
        return await _save_routed(decision, message, db, user)

    # Stated facts in any other turn are saved quietly, with chips.
    actions, saved = await save_conversation_memories(decision.candidates(), db, user)

    if decision.intent == MEMORY_QUERY:
        target = decision.query
        turn = await _answer(
            message,
            db,
            user,
            key=normalise_key(target.key) if target else None,
            subject=normalise_subject(target.subject) if target else None,
        )
    elif decision.intent == MEMORY_LIST:
        turn = _list(db, user)
    elif decision.intent == MEMORY_FORGET:
        target = decision.forget
        turn = _forget(
            (target.text if target and target.text else message),
            db,
            user,
            key=normalise_key(target.key) if target else None,
            subject=normalise_subject(target.subject) if target else None,
        )
    else:
        return await _chat(message, db, user, actions, saved)

    turn.response.memory_actions = [
        *[schemas.MemoryAction(**a) for a in actions],
        *turn.response.memory_actions,
    ]
    turn.saved = saved + turn.saved
    return turn
