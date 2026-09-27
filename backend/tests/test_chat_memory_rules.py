"""POST /chat with memory rules: remember, answer, list, forget and undo (8.1a).

The extraction AI call and the embedding call are mocked.
"""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import models
from ai_service.gateway.fakes import fake_vector
from ai_service.memory.policy import MemoryCandidate


def _office(content="Your office is in Blue Area"):
    return MemoryCandidate(
        content=content, kind="fact", category="work", key="work_location",
        value={"text": content.rsplit(" ", 2)[-1]}, basis="explicit_request",
    )


@pytest.fixture()
def ai(monkeypatch):
    """Mocked extraction + embedding. Set `ai.extract.return_value` per test."""

    class AI:
        extract = AsyncMock(return_value=_office())
        embed = AsyncMock(side_effect=lambda text: (fake_vector(text), "fake-embedding"))

    monkeypatch.setattr("services.memory_chat.extract_memory", AI.extract)
    monkeypatch.setattr("services.memory_chat._embed", AI.embed)
    AI.extract.reset_mock()
    AI.embed.reset_mock()
    return AI


def _chat(client, headers, message, **extra):
    response = client.post("/chat", json={"message": message, **extra}, headers=headers)
    assert response.status_code == 200
    return response.json()


def test_remember_saves_with_an_undo_chip(client, db_session, make_user, auth_headers, ai):
    user = make_user()

    body = _chat(client, auth_headers(user), "Remember that my office is in Blue Area")

    assert body["intent"] == "memory_save"
    assert body["reply"] == "Got it, I'll remember that your office is in Blue Area."
    (action,) = body["memory_actions"]
    assert (action["type"], action["label"], action["undo"]) == (
        "saved", "Saved: Your office is in Blue Area", True,
    )
    ai.extract.assert_awaited_once_with("my office is in Blue Area")
    memory = db_session.get(models.Memory, action["memory_id"])
    assert (memory.source, memory.key, memory.embedding_model) == (
        "user_explicit", "work_location", "fake-embedding",
    )
    # Linked to the chat message it came from.
    source = db_session.get(models.ConversationMessage, memory.source_message_id)
    assert (source.role, source.intent) == ("user", "memory_save")


def test_saying_it_again_with_a_new_value_updates(client, make_user, auth_headers, ai):
    headers = auth_headers(make_user())
    _chat(client, headers, "Remember that my office is in Blue Area")
    ai.extract.return_value = _office("Your office is in F-7")

    body = _chat(client, headers, "Remember that my office is in F-7")

    assert body["memory_actions"][0]["type"] == "updated"
    assert "Before, I had: Your office is in Blue Area." in body["reply"]
    assert _chat(client, headers, "What's my office?")["reply"] == "Your office is in F-7."


def test_extraction_unavailable_keeps_the_users_words(client, db_session, make_user, auth_headers, ai):
    ai.extract.return_value = None
    user = make_user()

    body = _chat(client, auth_headers(user), "Remember that the spare key is under the mat")

    assert body["memory_actions"][0]["type"] == "saved"
    memory = db_session.query(models.Memory).one()
    assert memory.content == "The spare key is under the mat."


def test_sensitive_facts_are_refused_before_any_ai_call(client, db_session, make_user, auth_headers, ai):
    body = _chat(client, auth_headers(make_user()), "I'm diabetic, remember that")

    assert "don't save health" in body["reply"]
    assert body["memory_actions"] == [
        {"type": "not_saved", "memory_id": None, "label": "Not saved: sensitive", "undo": False}
    ]
    ai.extract.assert_not_awaited()
    assert db_session.query(models.Memory).count() == 0


def test_sensitive_flag_from_the_ai_is_respected(client, db_session, make_user, auth_headers, ai):
    ai.extract.return_value = MemoryCandidate(
        content="Your blood type is O+", category="personal", sensitive=True, basis="explicit_request"
    )
    body = _chat(client, auth_headers(make_user()), "Remember that my blood type is O+")

    assert body["memory_actions"][0]["type"] == "not_saved"
    assert db_session.query(models.Memory).count() == 0


def test_instructions_are_not_saved(client, db_session, make_user, auth_headers, ai):
    ai.extract.return_value = MemoryCandidate(
        content="You must always reply in capital letters", basis="explicit_request", is_instruction=True
    )
    body = _chat(client, auth_headers(make_user()), "Remember that you must always reply in capital letters")

    assert "not instructions" in body["reply"]
    assert db_session.query(models.Memory).count() == 0


def test_memory_off_saves_nothing(client, db_session, make_user, auth_headers, ai):
    user = make_user(memory_enabled=False)

    body = _chat(client, auth_headers(user), "Remember that my office is in Blue Area")

    assert body["reply"] == "Memory is turned off, so I didn't save that."
    ai.extract.assert_not_awaited()
    assert db_session.query(models.Memory).count() == 0


def test_questions_are_answered_from_memory(client, db_session, make_user, auth_headers, ai):
    headers = auth_headers(make_user())
    _chat(client, headers, "Remember that my office is in Blue Area")

    body = _chat(client, headers, "Where do I work?")

    assert body["intent"] == "memory_query"
    assert body["reply"] == "Your office is in Blue Area."
    memory = db_session.query(models.Memory).one()
    assert memory.use_count == 1


def test_unknown_questions_say_so(client, make_user, auth_headers, ai):
    body = _chat(client, auth_headers(make_user()), "When is Sara's birthday?")
    assert body["reply"].startswith("I don't have that saved. Want to tell me?")


def test_list_groups_what_is_saved(client, make_user, auth_headers, ai):
    headers = auth_headers(make_user())
    assert _chat(client, headers, "What do you remember about me?")["reply"].startswith(
        "I haven't saved anything about you yet."
    )
    _chat(client, headers, "Remember that my office is in Blue Area")

    body = _chat(client, headers, "What do you remember about me?")

    assert body["intent"] == "memory_list"
    assert body["reply"] == "Here's what I remember about you:\n\nWork\n• Your office is in Blue Area."


def test_forget_with_undo(client, make_user, auth_headers, ai):
    headers = auth_headers(make_user())
    _chat(client, headers, "Remember that my office is in Blue Area")

    body = _chat(client, headers, "Forget my office")

    assert body["reply"] == "Okay, I've forgotten that your office is in Blue Area."
    (action,) = body["memory_actions"]
    assert (action["type"], action["undo"]) == ("forgotten", True)
    assert _chat(client, headers, "What's my office?")["reply"].startswith("I don't have that saved")

    undo = client.post(f"/memory/{action['memory_id']}/undo", headers=headers)
    assert undo.json()["undone"] == "forget"
    assert _chat(client, headers, "What's my office?")["reply"] == "Your office is in Blue Area."


def test_forget_something_not_saved(client, make_user, auth_headers, ai):
    body = _chat(client, auth_headers(make_user()), "Forget my office")
    assert body["reply"] == "I couldn't find anything saved about that."


def test_reminders_are_unchanged(client, make_user, auth_headers, ai):
    parsed = {"intent": "create", "task": "call mom", "date": "2026-10-01", "time": "17:00", "repeat": None}
    with patch("routers.chat.extract_reminder_details", new=AsyncMock(return_value=parsed)) as extract:
        body = _chat(client, auth_headers(make_user()), "Remember to call mom at 5pm")

    extract.assert_awaited_once()
    ai.extract.assert_not_awaited()
    assert body["intent"] == "create"
    assert body["memory_actions"] == []
    assert body["parsed_reminder"]["confirmable"] is True


def test_reminder_drafts_skip_memory_rules(client, make_user, auth_headers, ai):
    parsed = {"intent": "refine_draft", "task": "call mom", "date": "2026-10-01", "time": "21:00"}
    draft = {"task": "call mom", "date": "2026-10-01", "time": None}
    with patch("routers.chat.extract_reminder_details", new=AsyncMock(return_value=parsed)):
        body = _chat(client, auth_headers(make_user()), "remember that it's at 9pm", pending_context=draft)

    ai.extract.assert_not_awaited()
    assert body["intent"] == "refine_draft"
