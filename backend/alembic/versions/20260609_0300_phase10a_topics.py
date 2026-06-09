"""Phase 10A: topics and call_topics tables.

Revision ID: phase10a_topics
Revises: phase9a_redaction
Create Date: 2026-06-09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "phase10a_topics"
down_revision: str | None = "phase9a_redaction"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("keywords", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "call_topics",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "call_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("calls.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "topic_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("relevance", sa.Float, nullable=False),
        sa.UniqueConstraint("call_id", "topic_id", name="uq_call_topic"),
    )


def downgrade() -> None:
    op.drop_table("call_topics")
    op.drop_table("topics")
