"""Chat turns handled by the memory engine: save, answer, list and forget (8.1a).

Rule-matched messages only; everything else keeps the reminder flow. The caller
commits. Replies are templated here, so these turns need at most one AI call
(extraction for "remember that …") plus one embedding call.
"""

import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

import models
import schemas
from services import memory_store

# ai_service lives next to backend/ (same pattern as routers/chat.py).
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from ai_service.memory.extraction import extract_memory
from ai_service.memory.policy import (
    Decision,
    MemoryCandidate,
    MemorySettings,
    decide,
    is_sensitive_text,
)
from ai_service.router.rules import (
    MEMORY_FORGET,
    MEMORY_LIST,
    MEMORY_QUERY,
    MEMORY_SAVE,
    RuleMatch,
)

logger = logging.getLogger(__name__)

MAX_LISTED = 30

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


@dataclass
class MemoryTurn:
    response: schemas.ChatResponse
    intent: str
    # New memories to link to the stored user message once it exists.
    saved: list[models.Memory] = field(default_factory=list)


def settings_for(user: models.User) -> MemorySettings:
    return MemorySettings(
        memory_enabled=bool(getattr(user, "memory_enabled", True)),
        learn_from_chat=bool(getattr(user, "learn_from_chat", True)),
    )


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


async def _embed(text: str) -> tuple[Optional[list[float]], Optional[str]]:
    """Embedding for a new memory, or (None, None); the backfill job retries later."""
    try:
        from ai_service.gateway.embeddings import embed
        from ai_service.gateway.factory import get_default_embedder

        embedder = get_default_embedder()
        vectors = await embed([text], embedder=embedder)
        return vectors[0], embedder.model
    except Exception as exc:
        logger.warning("event=memory_embed_failed error_type=%s", type(exc).__name__)
        return None, None


async def _save(match: RuleMatch, db, user: models.User) -> MemoryTurn:
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

    result = decide(candidate, settings)
    if result.decision is Decision.SKIP_SENSITIVE:
        return _reply(
            NOT_SAVED_SENSITIVE, MEMORY_SAVE, [_action("not_saved", "Not saved: sensitive", undo=False)]
        )
    if result.decision is Decision.SKIP_INSTRUCTION:
        return _reply(NOT_SAVED_INSTRUCTION, MEMORY_SAVE)
    if not result.should_save:
        return _reply(NOT_SAVED_DISABLED, MEMORY_SAVE)

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
        source="user_explicit",
        confidence=result.confidence,
        importance=result.importance,
        temporary_days=result.temporary_days,
        embedding=embedding,
        embedding_model=embedding_model,
    )
    memory = outcome.memory
    if outcome.action == "duplicate":
        return _reply(f"I already have that saved: {_sentence(memory.content)}", MEMORY_SAVE)
    if outcome.action == "updated":
        reply = (
            f"Updated: {_sentence(memory.content)} "
            f"(Before, I had: {_sentence(outcome.previous.content)})"
        )
        return _reply(
            reply,
            MEMORY_SAVE,
            [_action("updated", _label("Updated", memory.content), memory, undo=True)],
            saved=[memory],
        )
    return _reply(
        f"Got it, I'll remember that {_inline(memory.content)}.",
        MEMORY_SAVE,
        [_action("saved", _label("Saved", memory.content), memory, undo=True)],
        saved=[memory],
    )


def _query(match: RuleMatch, db, user: models.User) -> MemoryTurn:
    rows = memory_store.find_exact(db, user.id, key=match.key, subject=match.subject)
    if not rows:
        return _reply(f"I don't have that saved. Want to tell me? {NOTHING_SAVED_HINT}", MEMORY_QUERY)
    memory_store.mark_used(db, rows)
    if len(rows) == 1:
        return _reply(_sentence(rows[0].content), MEMORY_QUERY)
    lines = "\n".join(f"• {_sentence(r.content)}" for r in rows[:10])
    return _reply(f"Here's what I have:\n{lines}", MEMORY_QUERY)


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


def _forget(match: RuleMatch, db, user: models.User) -> MemoryTurn:
    targets = memory_store.find_forget_targets(
        db, user.id, text=match.text, key=match.key, subject=match.subject
    )
    if not targets:
        return _reply("I couldn't find anything saved about that.", MEMORY_FORGET)
    exact = match.key is not None or match.subject is not None
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


async def handle_memory_rule(match: RuleMatch, *, db, user: models.User) -> MemoryTurn:
    if match.intent == MEMORY_SAVE:
        return await _save(match, db, user)
    if match.intent == MEMORY_QUERY:
        return _query(match, db, user)
    if match.intent == MEMORY_LIST:
        return _list(db, user)
    if match.intent == MEMORY_FORGET:
        return _forget(match, db, user)
    raise ValueError(f"Unknown memory intent: {match.intent}")
