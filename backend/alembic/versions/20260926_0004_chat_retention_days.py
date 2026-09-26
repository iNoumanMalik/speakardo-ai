"""per-user chat history retention

Adds users.chat_retention_days (default 90; NULL keeps chat history forever).
A daily scheduler job deletes conversation_messages older than it.

Revision ID: 20260926_0004
Revises: 20260926_0003
Create Date: 2026-09-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0004"
down_revision: Union[str, None] = "20260926_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The server default also fills existing users with 90.
    op.add_column(
        "users",
        sa.Column("chat_retention_days", sa.Integer(), nullable=True, server_default="90"),
    )


def downgrade() -> None:
    op.drop_column("users", "chat_retention_days")
