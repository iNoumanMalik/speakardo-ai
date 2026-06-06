"""Add local wall-clock fields for travel-aware repeating reminders."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260526_0001"
down_revision: Union[str, None] = "20260525_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reminders", sa.Column("local_time", sa.String(length=5), nullable=True))
    op.add_column("reminders", sa.Column("local_weekday", sa.Integer(), nullable=True))
    op.add_column(
        "reminders",
        sa.Column("local_day_of_month", sa.Integer(), nullable=True),
    )
    op.add_column(
        "reminders",
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill local_time from stored UTC + user timezone (best effort).
    op.execute(
        """
        UPDATE reminders r
        SET local_time = to_char(
            (r.datetime AT TIME ZONE 'UTC') AT TIME ZONE COALESCE(u.timezone, 'UTC'),
            'HH24:MI'
        )
        FROM users u
        WHERE r.user_id = u.id AND r.local_time IS NULL
        """
    )
    op.execute(
        """
        UPDATE reminders r
        SET local_weekday = EXTRACT(
            DOW FROM ((r.datetime AT TIME ZONE 'UTC') AT TIME ZONE COALESCE(u.timezone, 'UTC'))
        )::int
        FROM users u
        WHERE r.user_id = u.id
          AND r.repeat IS NOT NULL
          AND r.local_weekday IS NULL
        """
    )
    op.execute(
        """
        UPDATE reminders r
        SET local_day_of_month = EXTRACT(
            DAY FROM ((r.datetime AT TIME ZONE 'UTC') AT TIME ZONE COALESCE(u.timezone, 'UTC'))
        )::int
        FROM users u
        WHERE r.user_id = u.id
          AND r.repeat IS NOT NULL
          AND r.local_day_of_month IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("reminders", "snoozed_until")
    op.drop_column("reminders", "local_day_of_month")
    op.drop_column("reminders", "local_weekday")
    op.drop_column("reminders", "local_time")
