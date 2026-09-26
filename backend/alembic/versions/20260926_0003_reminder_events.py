"""log reminder events in reminder_events

Append-only log of created / fired / snoozed / completed / edited / deleted
events ('dismissed' is reserved for 8B). Habit mining in 8B needs weeks of this
history, so collection starts in 8.0.

reminder_id deliberately has no foreign key: events must survive the reminder
being deleted. Rows are removed with the user (ON DELETE CASCADE on user_id).

Revision ID: 20260926_0003
Revises: 20260926_0002
Create Date: 2026-09-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260926_0003"
down_revision: Union[str, None] = "20260926_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reminder_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reminder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event", sa.String(length=16), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("local_time", sa.String(length=5), nullable=True),
        sa.Column("weekday", sa.SmallInteger(), nullable=True),
        sa.CheckConstraint(
            "event IN ('created', 'fired', 'snoozed', 'completed', 'dismissed', 'edited', 'deleted')",
            name="ck_reminder_events_event",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reminder_events_user_occurred", "reminder_events", ["user_id", "occurred_at"]
    )
    op.create_index("ix_reminder_events_reminder_id", "reminder_events", ["reminder_id"])


def downgrade() -> None:
    op.drop_index("ix_reminder_events_reminder_id", table_name="reminder_events")
    op.drop_index("ix_reminder_events_user_occurred", table_name="reminder_events")
    op.drop_table("reminder_events")
