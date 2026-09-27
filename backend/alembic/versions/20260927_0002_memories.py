"""memories and memory_events

The AI memory store (Module 8.1). `subject` is an interim person label until the
people table arrives in 8.3. Forgotten memories are soft-deleted (status
'deleted', deleted_at) and erased 24 hours later by a scheduler job.
memory_events is the audit trail: it never holds content and has no foreign key
to memories, so it outlives erased rows.

Revision ID: 20260927_0002
Revises: 20260927_0001
Create Date: 2026-09-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20260927_0002"
down_revision: Union[str, None] = "20260927_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _in(column: str, values: tuple) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    uuid_t = postgresql.UUID(as_uuid=True)
    now = sa.text("now()")

    op.create_table(
        "memories",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("user_id", uuid_t, nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("key", sa.String(length=48), nullable=True),
        sa.Column("subject", sa.String(length=80), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=True),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("source_message_id", uuid_t, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("sensitivity", sa.String(length=12), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("superseded_by", uuid_t, nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embedding_model", sa.String(length=64), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.CheckConstraint(
            _in("kind", ("fact", "preference", "important_date", "relationship", "note", "event")),
            name="ck_memories_kind",
        ),
        sa.CheckConstraint(
            _in(
                "category",
                ("personal", "work", "people", "health", "finance", "places", "routine", "other"),
            ),
            name="ck_memories_category",
        ),
        sa.CheckConstraint(
            _in(
                "source",
                ("user_explicit", "conversation", "reminder", "onboarding", "manual_edit", "behavior"),
            ),
            name="ck_memories_source",
        ),
        sa.CheckConstraint(
            _in("sensitivity", ("normal", "private", "sensitive")), name="ck_memories_sensitivity"
        ),
        sa.CheckConstraint(
            _in("status", ("active", "pending_confirmation", "superseded", "deleted")),
            name="ck_memories_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_message_id"], ["conversation_messages.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["superseded_by"], ["memories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memories_user_status", "memories", ["user_id", "status"])
    op.create_index("ix_memories_user_key_subject", "memories", ["user_id", "key", "subject"])
    # HNSW works on an empty table and needs no retraining as rows arrive.
    op.create_index(
        "ix_memories_embedding_hnsw",
        "memories",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "memory_events",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("memory_id", uuid_t, nullable=False),
        sa.Column("user_id", uuid_t, nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("actor", sa.String(length=8), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.CheckConstraint(
            _in(
                "action",
                ("created", "updated", "used", "confirmed", "rejected", "deleted", "restored"),
            ),
            name="ck_memory_events_action",
        ),
        sa.CheckConstraint("actor IN ('user', 'system')", name="ck_memory_events_actor"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_events_memory_id", "memory_events", ["memory_id"])
    op.create_index("ix_memory_events_user_created", "memory_events", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_memory_events_user_created", table_name="memory_events")
    op.drop_index("ix_memory_events_memory_id", table_name="memory_events")
    op.drop_table("memory_events")
    op.drop_index("ix_memories_embedding_hnsw", table_name="memories")
    op.drop_index("ix_memories_user_key_subject", table_name="memories")
    op.drop_index("ix_memories_user_status", table_name="memories")
    op.drop_table("memories")
