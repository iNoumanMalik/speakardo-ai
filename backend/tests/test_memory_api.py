"""Memory API: list, forget and undo, scoped to the current user."""

from uuid import uuid4

import models
from services import memory_store


def _save(db, user, content, **fields):
    values = dict(
        kind="fact", category="work", key=None, subject=None, value=None,
        source="user_explicit", confidence=1.0, importance=0.5,
    )
    values.update(fields)
    memory = memory_store.save_memory(db, user.id, content=content, **values).memory
    db.commit()
    return memory


def test_list_returns_active_memories_without_embeddings(client, db_session, make_user, auth_headers):
    user = make_user()
    _save(db_session, user, "Your office is in Blue Area", key="work_location")
    _save(db_session, user, "Sara's birthday is June 15", kind="important_date",
          category="people", key="birthday", subject="sara")

    body = client.get("/memory", headers=auth_headers(user)).json()

    assert [m["content"] for m in body] == ["Sara's birthday is June 15", "Your office is in Blue Area"]
    assert "embedding" not in body[0]
    assert body[0]["subject"] == "sara"


def test_list_filters(client, db_session, make_user, auth_headers):
    user = make_user()
    _save(db_session, user, "Your office is in Blue Area", key="work_location")
    _save(db_session, user, "Sara's birthday is June 15", kind="important_date", category="people")
    headers = auth_headers(user)

    assert [m["content"] for m in client.get("/memory?category=people", headers=headers).json()] == [
        "Sara's birthday is June 15"
    ]
    assert [m["content"] for m in client.get("/memory?kind=fact", headers=headers).json()] == [
        "Your office is in Blue Area"
    ]
    assert [m["content"] for m in client.get("/memory?q=blue", headers=headers).json()] == [
        "Your office is in Blue Area"
    ]


def test_forget_then_undo(client, db_session, make_user, auth_headers):
    user = make_user()
    memory = _save(db_session, user, "Your office is in Blue Area")
    headers = auth_headers(user)

    forgotten = client.delete(f"/memory/{memory.id}", headers=headers)
    assert forgotten.status_code == 200
    assert forgotten.json()["status"] == "deleted"
    assert client.get("/memory", headers=headers).json() == []

    undone = client.post(f"/memory/{memory.id}/undo", headers=headers)
    assert undone.status_code == 200
    assert undone.json()["undone"] == "forget"
    assert undone.json()["memory"]["status"] == "active"
    assert len(client.get("/memory", headers=headers).json()) == 1


def test_undo_with_nothing_to_undo_is_409(client, db_session, make_user, auth_headers):
    user = make_user()
    memory = _save(db_session, user, "Your office is in Blue Area")
    headers = auth_headers(user)
    client.post(f"/memory/{memory.id}/undo", headers=headers)  # undoes the save

    assert client.post(f"/memory/{memory.id}/undo", headers=headers).status_code == 409


def test_another_users_memory_is_not_found(client, db_session, make_user, auth_headers):
    alice, bob = make_user(), make_user()
    memory = _save(db_session, alice, "Your office is in Blue Area")
    headers = auth_headers(bob)

    assert client.get("/memory", headers=headers).json() == []
    assert client.delete(f"/memory/{memory.id}", headers=headers).status_code == 404
    assert client.post(f"/memory/{memory.id}/undo", headers=headers).status_code == 404
    assert client.delete(f"/memory/{uuid4()}", headers=headers).status_code == 404
    db_session.refresh(memory)
    assert memory.status == models.MemoryStatus.ACTIVE


def test_memory_api_requires_auth(client):
    assert client.get("/memory").status_code == 401
    assert client.delete(f"/memory/{uuid4()}").status_code == 401


def test_memory_settings_via_preferences(client, make_user, auth_headers):
    user = make_user()
    headers = auth_headers(user)

    body = client.patch(
        "/users/me/preferences", json={"learn_from_chat": False}, headers=headers
    ).json()

    assert (body["memory_enabled"], body["learn_from_chat"]) == (True, False)
    assert client.get("/users/me", headers=headers).json()["learn_from_chat"] is False
