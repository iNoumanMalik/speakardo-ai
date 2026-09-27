"""memory privacy settings on users

memory_enabled (false = save nothing) and learn_from_chat (false = only explicit
"remember that ..." requests are saved). Both default to true.

Revision ID: 20260927_0001
Revises: 20260926_0004
Create Date: 2026-09-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260927_0001"
down_revision: Union[str, None] = "20260926_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "users",
        sa.Column("learn_from_chat", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("users", "learn_from_chat")
    op.drop_column("users", "memory_enabled")
