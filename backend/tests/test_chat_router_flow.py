"""POST /chat through the turn router (8.1b). All AI calls are mocked."""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import models
from ai_service.reply.grounded import Reply
from ai_service.router.turn import TurnDecision
from services import memory_store

VEC = [1.0] + [0.0] * 1535  # every text embeds to the same vector: similarity 1.0


def _decision(**fields) -> TurnDecision:
    return TurnDecision.model_validate(fields)


def _sara(**overrides):
    fact = {
        "content": "Your sister Sara's birthday is June 15", "kind": "important_date",
        "category": "people", "key": "birthday", "subject": "Sara",
        "value": {"month": 6, "day": 15}, "basis": "stated",
    }
    fact.update(overrides)
    return fact


@pytest.fixture()
def ai(monkeypatch):
    """Turn router, embeddings and replies, all mocked. Set return values per test."""

    class AI:
        route = AsyncMock(return_value=None)
        embed = AsyncMock(return_value=(VEC, "fake-embedding"))
        reply = AsyncMock(return_value=None)
        extract_reminder = AsyncMock(return_value=None)

    monkeypatch.setattr("routers.chat.route_turn", AI.route)
    monkeypatch.setattr("services.memory_chat._embed", AI.embed)
    monkeypatch.setattr("services.memory_chat._generate_reply", AI.reply)
    monkeypatch.setattr("routers.chat.extract_reminder_details", AI.extract_reminder)
    return AI


def _chat(client, headers, message):
    response = client.post("/chat", json={"message": message}, headers=headers)
    assert response.status_code == 200
    return response.json()


def _save(db, user, content, **fields):
    values = dict(kind="fact", category="other", key=None, subject=None, value=None,
                  source="conversation", confidence=1.0, importance=0.5,
                  embedding=VEC, embedding_model="fake-embedding")
    values.update(fields)
    memory = memory_store.save_memory(db, user.id, content=content, **values).memory
    db.commit()
    return memory


# --- saving without "remember" ----------------------------------------------------------


def test_a_stated_fact_is_saved_without_saying_remember(client, db_session, make_user, auth_headers, ai):
    ai.route.return_value = _decision(intent="memory_save", memories=[_sara()])

    body = _chat(client, auth_headers(make_user()), "My sister Sara's birthday is June 15")

    assert body["intent"] == "memory_save"
    assert body["reply"] == "Got it, I'll remember that your sister Sara's birthday is June 15."
    assert body["memory_actions"][0]["type"] == "saved"
    memory = db_session.query(models.Memory).one()
    assert (memory.source, memory.subject, memory.key) == ("conversation", "sara", "birthday")


def test_moving_city_updates_the_old_value(client, db_session, make_user, auth_headers, ai):
    user = make_user()
    _save(db_session, user, "Your home city is Islamabad", key="home_city", category="places")
    ai.route.return_value = _decision(intent="memory_save", memories=[{
        "content": "Your home city is Lahore", "kind": "fact", "category": "places",
        "key": "home_city", "basis": "stated",
    }])

    body = _chat(client, auth_headers(user), "I moved to Lahore")

    assert body["memory_actions"][0]["type"] == "updated"
    assert "(Before, I had: Your home city is Islamabad.)" in body["reply"]


def test_temporary_facts_expire(client, db_session, make_user, auth_headers, ai):
    ai.route.return_value = _decision(intent="memory_save", memories=[{
        "content": "You're in Karachi this week", "kind": "fact", "category": "places",
        "basis": "stated", "temporary_days": 7,
    }])

    _chat(client, auth_headers(make_user()), "I'm in Karachi this week")

    memory = db_session.query(models.Memory).one()
    left = memory.valid_until - datetime.now(timezone.utc)
    assert timedelta(days=6) < left <= timedelta(days=7)


def test_guesses_are_not_saved_and_get_a_normal_reply(client, db_session, make_user, auth_headers, ai):
    ai.route.return_value = _decision(intent="memory_save", memories=[{
        "content": "You might switch jobs", "basis": "guess",
    }])
    ai.reply.return_value = Reply("Sounds like a big decision. Want to talk it through?")

    body = _chat(client, auth_headers(make_user()), "I think I might switch jobs")

    assert body["intent"] == "chat"
    assert body["reply"] == "Sounds like a big decision. Want to talk it through?"
    assert db_session.query(models.Memory).count() == 0


def test_sensitive_facts_in_conversation_are_refused(client, db_session, make_user, auth_headers, ai):
    ai.route.return_value = _decision(intent="memory_save", memories=[{
        "content": "You have asthma", "category": "health", "basis": "stated", "sensitive": True,
    }])

    body = _chat(client, auth_headers(make_user()), "I have asthma")

    assert "don't save health" in body["reply"]
    assert body["memory_actions"][0]["type"] == "not_saved"
    assert db_session.query(models.Memory).count() == 0


# --- answering ----------------------------------------------------------------------------


def test_questions_use_semantic_search_and_show_used_chips(client, db_session, make_user, auth_headers, ai):
    user = make_user()
    memory = _save(db_session, user, "Your sister Sara's birthday is June 15",
                   kind="important_date", category="people")
    ai.route.return_value = _decision(intent="memory_query", query={"text": "Sara's birthday"})
    ai.reply.return_value = Reply("Sara's birthday is on June 15.", used_ids=[memory.id])

    body = _chat(client, auth_headers(user), "What day was Sara born?")

    kwargs = ai.reply.await_args.kwargs
    assert kwargs["mode"] == "answer"
    assert [m.text for m in kwargs["memories"]] == ["Your sister Sara's birthday is June 15"]
    assert body["reply"] == "Sara's birthday is on June 15."
    assert body["memory_actions"] == [{
        "type": "used", "memory_id": str(memory.id),
        "label": "Used: Your sister Sara's birthday is June 15", "undo": False,
    }]
    db_session.refresh(memory)
    assert memory.use_count == 1


def test_reminders_answer_questions_too(client, db_session, make_user, auth_headers, ai):
    user = make_user(timezone="Asia/Karachi")
    db_session.add(models.Reminder(
        user_id=user.id, task="Dentist appointment",
        datetime=datetime(2026, 9, 30, 5, 0, tzinfo=timezone.utc), status="pending",
    ))
    db_session.commit()
    ai.route.return_value = _decision(intent="memory_query", query={"text": "dentist appointment"})
    ai.reply.return_value = Reply("Your dentist appointment is on Wednesday at 10:00.")

    body = _chat(client, auth_headers(user), "When is my dentist appointment?")

    (reminder,) = ai.reply.await_args.kwargs["reminders"]
    assert (reminder.task, reminder.when) == ("Dentist appointment", "Wed 30 Sep 2026, 10:00")
    assert body["reply"] == "Your dentist appointment is on Wednesday at 10:00."


def test_nothing_saved_means_no_ai_reply(client, make_user, auth_headers, ai):
    ai.route.return_value = _decision(intent="memory_query", query={"text": "car"})

    body = _chat(client, auth_headers(make_user()), "What car do I drive?")

    assert body["reply"].startswith("I don't have that saved. Want to tell me?")
    ai.embed.assert_not_awaited()
    ai.reply.assert_not_awaited()


# --- small talk ----------------------------------------------------------------------------------


def test_small_talk_gets_an_ai_reply(client, make_user, auth_headers, ai):
    ai.route.return_value = _decision(intent="chat")
    ai.reply.return_value = Reply("You're welcome! Anything else I can do?")

    body = _chat(client, auth_headers(make_user()), "thanks!")

    assert ai.reply.await_args.kwargs["mode"] == "chat"
    assert (body["intent"], body["reply"]) == ("chat", "You're welcome! Anything else I can do?")


def test_small_talk_falls_back_when_no_provider_answers(client, make_user, auth_headers, ai):
    ai.route.return_value = _decision(intent="chat")

    body = _chat(client, auth_headers(make_user()), "how are you?")

    assert body["reply"].startswith("I'm here to help.")


def test_facts_mentioned_in_small_talk_are_saved(client, db_session, make_user, auth_headers, ai):
    ai.route.return_value = _decision(intent="chat", memories=[{
        "content": "Your dog is called Max", "kind": "fact", "category": "personal",
        "key": "pet_name", "basis": "stated",
    }])
    ai.reply.return_value = Reply("Max sounds lovely!")

    body = _chat(client, auth_headers(make_user()), "Just got back from walking my dog Max")

    assert body["memory_actions"][0]["label"] == "Saved: Your dog is called Max"
    assert db_session.query(models.Memory).one().source == "conversation"


# --- reminders -------------------------------------------------------------------------------------


def test_routed_reminders_use_router_slots_and_save_stated_facts(client, db_session, make_user, auth_headers, ai):
    ai.route.return_value = _decision(
        intent="reminder_create",
        reminder={"task": "call Sara", "date": "2026-09-28", "time": "17:00"},
        memories=[{"content": "Sara is your sister", "kind": "relationship", "category": "people",
                   "key": "relationship", "subject": "Sara", "basis": "stated"}],
    )
    ai.extract_reminder.return_value = {
        "intent": "create", "task": "call Sara", "date": "2026-09-28", "time": "17:00",
    }

    body = _chat(client, auth_headers(make_user()), "Call my sister Sara tomorrow at 5pm")

    assert ai.extract_reminder.await_args.kwargs["preparsed"]["task"] == "call Sara"
    assert body["parsed_reminder"]["confirmable"] is True
    assert body["memory_actions"][0]["label"] == "Saved: Sara is your sister"
    assert db_session.query(models.Memory).one().subject == "sara"


def test_router_failure_falls_back_to_the_reminder_parser(client, make_user, auth_headers, ai):
    ai.extract_reminder.return_value = None  # and route_turn returns None by default

    body = _chat(client, auth_headers(make_user()), "blorp")

    ai.route.assert_awaited_once()
    ai.extract_reminder.assert_awaited_once()
    assert body["intent"] == "unparsed"


@pytest.mark.parametrize("message", ["hello", "Remind me to call mom at 5pm"])
def test_greetings_and_clear_reminders_skip_the_router(client, make_user, auth_headers, ai, message):
    ai.extract_reminder.return_value = {"intent": "create", "task": "call mom", "date": "2026-09-28", "time": "17:00"}

    _chat(client, auth_headers(make_user()), message)

    ai.route.assert_not_awaited()


def test_router_failure_on_a_question_asks_to_try_again(client, make_user, auth_headers, ai):
    """A rate-limited router must not turn "What car do I drive?" into a reminder."""
    body = _chat(client, auth_headers(make_user()), "What car do I drive?")

    ai.extract_reminder.assert_not_awaited()
    assert body["intent"] == "unavailable"
    assert body["reply"] == "I couldn't check that just now. Please try again in a moment."
    assert body["parsed_reminder"] is None
