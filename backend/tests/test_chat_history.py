"""Chat history: POST /chat stores every exchange; GET /chat/history pages it back."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import models
from services.chat_history import SESSION_GAP, record_exchange


def _messages(db, user):
    return (
        db.query(models.ConversationMessage)
        .filter(models.ConversationMessage.user_id == user.id)
        .order_by(models.ConversationMessage.created_at.asc())
        .all()
    )


def _add_message(db, user, *, content, created_at, role=models.ChatRole.USER):
    msg = models.ConversationMessage(
        user_id=user.id,
        session_id=uuid4(),
        role=role,
        content=content,
        created_at=created_at,
    )
    db.add(msg)
    db.commit()
    return msg


def _post_chat(client, headers, message, parsed):
    with patch(
        "routers.chat.extract_reminder_details", new=AsyncMock(return_value=parsed)
    ):
        return client.post("/chat", json={"message": message}, headers=headers)


# --- POST /chat stores both sides of the exchange ---------------------------


def test_greeting_is_stored_with_reply(client, db_session, make_user, auth_headers):
    user = make_user()
    response = client.post("/chat", json={"message": "hi"}, headers=auth_headers(user))

    assert response.status_code == 200
    user_msg, reply_msg = _messages(db_session, user)
    assert (user_msg.role, user_msg.content, user_msg.intent) == ("user", "hi", "greeting")
    assert reply_msg.role == "assistant"
    assert reply_msg.content == response.json()["reply"]
    assert reply_msg.intent is None
    assert reply_msg.session_id == user_msg.session_id
    assert reply_msg.created_at > user_msg.created_at


def test_confirmable_reminder_reply_is_stored(client, db_session, make_user, auth_headers):
    user = make_user()
    parsed = {
        "intent": "create",
        "task": "call mom",
        "date": "2026-10-01",
        "time": "17:00",
        "repeat": None,
    }
    response = _post_chat(client, auth_headers(user), "remind me to call mom at 5pm", parsed)

    assert response.status_code == 200
    assert response.json()["parsed_reminder"]["confirmable"] is True
    user_msg, reply_msg = _messages(db_session, user)
    assert user_msg.intent == "create"
    assert reply_msg.content == response.json()["reply"]


def test_needs_time_reply_is_stored(client, db_session, make_user, auth_headers):
    user = make_user()
    parsed = {"intent": "create", "task": "gym", "date": "2026-10-01", "time": None, "needs_time": True}
    response = _post_chat(client, auth_headers(user), "remind me to go to the gym", parsed)

    assert response.status_code == 200
    assert "What time" in response.json()["reply"]
    assert [m.role for m in _messages(db_session, user)] == ["user", "assistant"]


def test_parse_failure_is_stored_as_unparsed(client, db_session, make_user, auth_headers):
    user = make_user()
    response = _post_chat(client, auth_headers(user), "blorp", None)

    assert response.status_code == 200
    user_msg, _ = _messages(db_session, user)
    assert user_msg.intent == "unparsed"


def test_history_write_failure_still_returns_reply(client, db_session, make_user, auth_headers):
    user = make_user()
    with patch("routers.chat.record_exchange", side_effect=RuntimeError("db down")):
        response = client.post("/chat", json={"message": "hello"}, headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["reply"]
    assert _messages(db_session, user) == []


def test_overlong_message_is_rejected(client, make_user, auth_headers):
    user = make_user()
    response = client.post("/chat", json={"message": "x" * 4001}, headers=auth_headers(user))
    assert response.status_code == 422


# --- Sessions ----------------------------------------------------------------


def test_session_continues_within_gap_and_restarts_after(db_session, make_user):
    user = make_user()
    t0 = datetime(2026, 9, 26, 9, 0, tzinfo=timezone.utc)

    def exchange(at):
        msg, _ = record_exchange(
            db_session,
            user_id=user.id,
            user_text="x",
            reply="y",
            intent="create",
            received_at=at,
            replied_at=at + timedelta(seconds=1),
        )
        db_session.commit()
        return msg.session_id

    first = exchange(t0)
    assert exchange(t0 + timedelta(minutes=10)) == first
    assert exchange(t0 + timedelta(minutes=10) + SESSION_GAP + timedelta(minutes=1)) != first


# --- GET /chat/history --------------------------------------------------------


def test_history_returns_newest_first(client, make_user, auth_headers):
    user = make_user()
    headers = auth_headers(user)
    client.post("/chat", json={"message": "hi"}, headers=headers)
    client.post("/chat", json={"message": "hello"}, headers=headers)

    response = client.get("/chat/history", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [m["role"] for m in body["messages"]] == ["assistant", "user", "assistant", "user"]
    assert [m["content"] for m in body["messages"] if m["role"] == "user"] == ["hello", "hi"]
    assert body["has_more"] is False
    assert body["next_before"] is None


def test_history_pages_with_before_cursor(client, db_session, make_user, auth_headers):
    user = make_user()
    t0 = datetime(2026, 9, 26, 9, 0, tzinfo=timezone.utc)
    for i in range(5):
        _add_message(db_session, user, content=f"m{i}", created_at=t0 + timedelta(minutes=i))
    headers = auth_headers(user)

    page1 = client.get("/chat/history?limit=2", headers=headers).json()
    assert [m["content"] for m in page1["messages"]] == ["m4", "m3"]
    assert page1["has_more"] is True
    assert page1["next_before"] == page1["messages"][-1]["id"]

    page2 = client.get(f"/chat/history?limit=2&before={page1['next_before']}", headers=headers).json()
    assert [m["content"] for m in page2["messages"]] == ["m2", "m1"]
    assert page2["has_more"] is True

    page3 = client.get(f"/chat/history?limit=2&before={page2['next_before']}", headers=headers).json()
    assert [m["content"] for m in page3["messages"]] == ["m0"]
    assert page3["has_more"] is False
    assert page3["next_before"] is None


def test_history_pagination_handles_identical_timestamps(client, db_session, make_user, auth_headers):
    user = make_user()
    same = datetime(2026, 9, 26, 9, 0, tzinfo=timezone.utc)
    for i in range(3):
        _add_message(db_session, user, content=f"m{i}", created_at=same)
    headers = auth_headers(user)

    seen, before = [], None
    for _ in range(3):
        url = "/chat/history?limit=1" + (f"&before={before}" if before else "")
        body = client.get(url, headers=headers).json()
        seen += [m["content"] for m in body["messages"]]
        before = body["next_before"]

    assert sorted(seen) == ["m0", "m1", "m2"]
    assert before is None


def test_history_is_scoped_to_current_user(client, make_user, auth_headers):
    alice, bob = make_user(), make_user()
    client.post("/chat", json={"message": "hi"}, headers=auth_headers(alice))

    body = client.get("/chat/history", headers=auth_headers(bob)).json()
    assert body["messages"] == []


def test_before_cursor_of_another_user_is_not_found(client, db_session, make_user, auth_headers):
    alice, bob = make_user(), make_user()
    alices = _add_message(db_session, alice, content="secret", created_at=datetime.now(timezone.utc))

    response = client.get(f"/chat/history?before={alices.id}", headers=auth_headers(bob))
    assert response.status_code == 404

    missing = client.get(f"/chat/history?before={uuid4()}", headers=auth_headers(bob))
    assert missing.status_code == 404


def test_history_limit_bounds(client, make_user, auth_headers):
    headers = auth_headers(make_user())
    assert client.get("/chat/history?limit=0", headers=headers).status_code == 422
    assert client.get("/chat/history?limit=101", headers=headers).status_code == 422
    assert client.get("/chat/history?limit=100", headers=headers).status_code == 200


def test_history_requires_auth(client):
    assert client.get("/chat/history").status_code == 401


def test_history_is_rate_limited(client, make_user, auth_headers):
    headers = auth_headers(make_user())
    statuses = [client.get("/chat/history", headers=headers).status_code for _ in range(61)]
    assert statuses[:60] == [200] * 60
    assert statuses[60] == 429
