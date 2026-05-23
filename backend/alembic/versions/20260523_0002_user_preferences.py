"""Add user timezone and notification preference columns.

Revision ID: 20260523_0002
Revises: 20260523_0001
Create Date: 2026-05-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260523_0002"
down_revision: Union[str, None] = "20260523_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"),
    )
    op.add_column(
        "users",
        sa.Column(
            "notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.alter_column("users", "timezone", server_default=None)
    op.alter_column("users", "notifications_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "notifications_enabled")
    op.drop_column("users", "timezone")
