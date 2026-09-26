"""The Alembic chain builds the full schema from an empty database (see conftest)."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

import models  # noqa: F401  (registers every table on Base.metadata)
from database import Base

# Drift that predates Module 8 (auth_tokens, Module 1). Listed explicitly so any
# new drift fails this test instead of being hidden.
_KNOWN_DRIFT = {
    ("modify_nullable", "auth_tokens", "created_at"),
    ("remove_index", "auth_tokens", "ix_auth_tokens_user_id"),
    ("add_index", "auth_tokens", "ix_auth_tokens_id"),
}


def _drift_key(diff) -> tuple:
    # Column-level diffs arrive wrapped in a list of tuples.
    if isinstance(diff, list):
        diff = diff[0]
    kind = diff[0]
    if kind in {"add_index", "remove_index"}:
        return (kind, diff[1].table.name, diff[1].name)
    if kind.startswith("modify_"):
        return (kind, diff[2], diff[3])
    return (kind, repr(diff[1:]))


def test_vector_extension_is_installed(pg_engine):
    with pg_engine.connect() as conn:
        version = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
    assert version is not None


def test_migrated_schema_matches_models(pg_engine):
    with pg_engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        drift = {_drift_key(d) for d in compare_metadata(context, Base.metadata)}
    assert drift - _KNOWN_DRIFT == set()


def test_all_model_tables_exist(pg_engine):
    tables = set(inspect(pg_engine).get_table_names())
    assert set(Base.metadata.tables) <= tables
