"""Shared pytest fixtures. Every database test runs on Postgres, never SQLite.

The test database is migrated from scratch with the real Alembic chain once per
run and emptied after every test. Start it with:

    docker compose -f docker/docker-compose.yml up -d
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# env_config loads the repo-root .env with override=True, so it must be imported
# before DATABASE_URL is pointed at the test database; otherwise .env wins.
import env_config  # noqa: E402,F401
from sqlalchemy.engine import make_url  # noqa: E402

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg2://user:password@localhost:5432/ai_reminder_test"
)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or DEFAULT_TEST_DATABASE_URL


def _unsafe_test_url_reason(url: str) -> str | None:
    """The suite drops and truncates the target schema: only allow a local *_test DB."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        return "tests must run on Postgres"
    if parsed.host not in {"localhost", "127.0.0.1"}:
        return f"host must be localhost, got {parsed.host!r}"
    if not (parsed.database or "").endswith("_test"):
        return f"database name must end in _test, got {parsed.database!r}"
    return None


_reason = _unsafe_test_url_reason(TEST_DATABASE_URL)
if _reason:
    pytest.exit(f"Refusing to run tests against TEST_DATABASE_URL: {_reason}", returncode=2)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["AUTO_CREATE_SCHEMA"] = "false"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

import database  # noqa: E402
import models  # noqa: E402
from auth_security import create_access_token  # noqa: E402
from services.notifications import NotificationResult  # noqa: E402

_truncate_sql: str | None = None


class _NoopScheduler:
    def shutdown(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32chars-minimum!!")


@pytest.fixture(autouse=True)
def block_real_push(monkeypatch):
    """No test may reach FCM. Tests that need a delivery patch this themselves."""
    fake = MagicMock(
        return_value=NotificationResult(
            success=False,
            error_code="test_blocked",
            error_message="real push notifications are blocked in tests",
        )
    )
    monkeypatch.setattr("services.scheduler.send_push_notification", fake)
    return fake


@pytest.fixture(autouse=True)
def block_real_ai(monkeypatch):
    """No test may reach a real AI provider. Tests that need AI output patch these.

    Defaults behave like "no provider available": the turn router falls back to
    the reminder parser, replies use their templated fallbacks, nothing is embedded.
    """
    import routers.chat
    import services.memory_chat

    monkeypatch.setattr(routers.chat, "route_turn", AsyncMock(return_value=None))
    monkeypatch.setattr(services.memory_chat, "_generate_reply", AsyncMock(return_value=None))
    monkeypatch.setattr(services.memory_chat, "_embed", AsyncMock(return_value=(None, None)))
    monkeypatch.setattr(services.memory_chat, "extract_memory", AsyncMock(return_value=None))


@pytest.fixture(scope="session")
def pg_engine():
    global _truncate_sql
    engine = database.engine
    safe_url = make_url(TEST_DATABASE_URL).render_as_string(hide_password=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError:
        pytest.exit(
            f"Postgres test database is unreachable ({safe_url}). Start it with: "
            "docker compose -f docker/docker-compose.yml up -d",
            returncode=3,
        )

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    # No ini file: alembic/env.py then skips fileConfig, which would otherwise
    # reconfigure logging for the rest of the run.
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")

    tables = [t for t in inspect(engine).get_table_names() if t != "alembic_version"]
    _truncate_sql = f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"
    yield engine


@pytest.fixture()
def db_session(pg_engine):
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        # TRUNCATE rather than a rolled-back transaction: code under test that
        # opens SessionLocal itself (scheduler, email background tasks) must see
        # the same committed rows.
        with pg_engine.begin() as conn:
            conn.execute(text(_truncate_sql))


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    import app as app_module
    from database import get_db
    from rate_limit import limiter

    def override_get_db():
        yield db_session

    # The app lifespan would start APScheduler against the test database.
    monkeypatch.setattr(app_module, "start_scheduler", lambda: _NoopScheduler())
    limiter.reset()
    app_module.app.dependency_overrides[get_db] = override_get_db
    with TestClient(app_module.app) as test_client:
        yield test_client
    app_module.app.dependency_overrides.clear()


@pytest.fixture()
def make_user(db_session):
    def _make(**fields) -> models.User:
        values = {
            "email": f"user-{uuid4().hex[:10]}@example.com",
            "password": "hashed",
            "email_verified": True,
            "timezone": "UTC",
        }
        values.update(fields)
        user = models.User(**values)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make


@pytest.fixture()
def auth_headers():
    def _headers(user: models.User) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return _headers
