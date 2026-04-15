"""reliability delivery tracking

Revision ID: 20260415_0001
Revises:
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260415_0001"
down_revision = None
branch_labels = None
depends_on = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def upgrade() -> None:
    uuid_t = _uuid_type()
    dialect = op.get_bind().dialect.name

    with op.batch_alter_table("reminders") as batch:
        batch.alter_column("user_id", existing_type=uuid_t, nullable=False)
        batch.alter_column("status", existing_type=sa.String(), nullable=False)
        batch.add_column(sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("last_error", sa.Text(), nullable=True))

    with op.batch_alter_table("device_tokens") as batch:
        batch.alter_column("user_id", existing_type=uuid_t, nullable=False)

    if dialect == "postgresql":
        op.alter_column("reminders", "attempt_count", server_default=None)

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
    op.create_index(op.f("ix_delivery_attempts_id"), "delivery_attempts", ["id"], unique=False)
    op.create_index(
        op.f("ix_delivery_attempts_reminder_id"),
        "delivery_attempts",
        ["reminder_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_delivery_attempts_device_token_id"),
        "delivery_attempts",
        ["device_token_id"],
        unique=False,
    )
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
