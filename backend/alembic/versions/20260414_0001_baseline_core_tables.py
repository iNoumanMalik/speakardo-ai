"""baseline core tables

Written retroactively on 2026-09-26. The original users, reminders and
device_tokens tables were created by Base.metadata.create_all, so no migration
ever created them and `alembic upgrade head` failed on an empty database
(fresh test DB, Supabase, a new developer machine).

This revision recreates those three tables in the shape 20260415_0001 expects,
before any later columns. Each table is created only if it is missing, and
databases already at a later revision never run it.

Revision ID: 20260414_0001
Revises:
Create Date: 2026-09-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "20260414_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    uuid_t = postgresql.UUID(as_uuid=True)

    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", uuid_t, nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("password", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if not _table_exists("reminders"):
        op.create_table(
            "reminders",
            sa.Column("id", uuid_t, nullable=False),
            sa.Column("user_id", uuid_t, nullable=True),
            sa.Column("task", sa.String(), nullable=False),
            sa.Column("datetime", sa.DateTime(timezone=True), nullable=False),
            sa.Column("repeat", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_reminders_id", "reminders", ["id"])
        op.create_index("ix_reminders_task", "reminders", ["task"])

    if not _table_exists("device_tokens"):
        op.create_table(
            "device_tokens",
            sa.Column("id", uuid_t, nullable=False),
            sa.Column("user_id", uuid_t, nullable=True),
            sa.Column("token", sa.String(), nullable=False),
            sa.Column("platform", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_device_tokens_id", "device_tokens", ["id"])
        op.create_index("ix_device_tokens_token", "device_tokens", ["token"], unique=True)


def downgrade() -> None:
    op.drop_table("device_tokens")
    op.drop_table("reminders")
    op.drop_table("users")
