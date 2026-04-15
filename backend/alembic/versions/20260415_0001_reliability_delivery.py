"""reliability delivery tracking

Revision ID: 20260415_0001
Revises:
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


revision = "20260415_0001"
down_revision = None
branch_labels = None
depends_on = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table_name in insp.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    try:
        cols = insp.get_columns(table_name)
    except Exception:
        return False
    return any(c["name"] == column_name for c in cols)


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    try:
        idxs = insp.get_indexes(table_name)
    except Exception:
        return False
    return any(i["name"] == index_name for i in idxs)


def upgrade() -> None:
    uuid_t = _uuid_type()
    dialect = op.get_bind().dialect.name

    with op.batch_alter_table("reminders") as batch:
        batch.alter_column("user_id", existing_type=uuid_t, nullable=False)
        batch.alter_column("status", existing_type=sa.String(), nullable=False)
        if not _column_exists("reminders", "processing_started_at"):
            batch.add_column(sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True))
        if not _column_exists("reminders", "triggered_at"):
            batch.add_column(sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True))
        if not _column_exists("reminders", "next_attempt_at"):
            batch.add_column(sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
        if not _column_exists("reminders", "attempt_count"):
            batch.add_column(sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
        if not _column_exists("reminders", "last_error"):
            batch.add_column(sa.Column("last_error", sa.Text(), nullable=True))

    with op.batch_alter_table("device_tokens") as batch:
        batch.alter_column("user_id", existing_type=uuid_t, nullable=False)

    if dialect == "postgresql":
        op.alter_column("reminders", "attempt_count", server_default=None)

    if not _table_exists("delivery_attempts"):
        op.create_table(
            "delivery_attempts",
            sa.Column("id", uuid_t, nullable=False),
            sa.Column("reminder_id", uuid_t, nullable=False),
            sa.Column("device_token_id", uuid_t, nullable=False),
            sa.Column(
                "dedupe_key", sa.String(), nullable=False
            ),  # Prevents duplicate sends (unique)
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("provider_message_id", sa.String(), nullable=True),
            sa.Column("error_code", sa.String(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["device_token_id"], ["device_tokens.id"]),
            sa.ForeignKeyConstraint(["reminder_id"], ["reminders.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("delivery_attempts", op.f("ix_delivery_attempts_id")):
        op.create_index(op.f("ix_delivery_attempts_id"), "delivery_attempts", ["id"], unique=False)
    if not _index_exists("delivery_attempts", op.f("ix_delivery_attempts_reminder_id")):
        op.create_index(
            op.f("ix_delivery_attempts_reminder_id"),
            "delivery_attempts",
            ["reminder_id"],
            unique=False,
        )
    if not _index_exists("delivery_attempts", op.f("ix_delivery_attempts_device_token_id")):
        op.create_index(
            op.f("ix_delivery_attempts_device_token_id"),
            "delivery_attempts",
            ["device_token_id"],
            unique=False,
        )
    if not _index_exists("delivery_attempts", op.f("ix_delivery_attempts_dedupe_key")):
        op.create_index(
            op.f("ix_delivery_attempts_dedupe_key"),
            "delivery_attempts",
            ["dedupe_key"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_delivery_attempts_dedupe_key"), table_name="delivery_attempts")
    op.drop_index(op.f("ix_delivery_attempts_device_token_id"), table_name="delivery_attempts")
    op.drop_index(op.f("ix_delivery_attempts_reminder_id"), table_name="delivery_attempts")
    op.drop_index(op.f("ix_delivery_attempts_id"), table_name="delivery_attempts")
    op.drop_table("delivery_attempts")

    with op.batch_alter_table("device_tokens") as batch:
        batch.alter_column("user_id", existing_type=_uuid_type(), nullable=True)

    with op.batch_alter_table("reminders") as batch:
        batch.drop_column("last_error")
        batch.drop_column("attempt_count")
        batch.drop_column("next_attempt_at")
        batch.drop_column("triggered_at")
        batch.drop_column("processing_started_at")
        batch.alter_column("status", existing_type=sa.String(), nullable=True)
        batch.alter_column("user_id", existing_type=_uuid_type(), nullable=True)
