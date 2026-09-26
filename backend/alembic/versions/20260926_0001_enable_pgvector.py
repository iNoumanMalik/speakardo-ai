"""enable the pgvector extension

Module 8 stores memory embeddings as vector(1536) columns (from 8.1). This
revision only enables the extension; no vector columns are created yet.

Revision ID: 20260926_0001
Revises: 20260809_0001
Create Date: 2026-09-26
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260926_0001"
down_revision: Union[str, None] = "20260809_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
