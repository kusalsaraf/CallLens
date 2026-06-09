"""Phase 9A: PII/PCI redaction columns.

Adds redacted_text to transcript_segments, and entities_redacted + redaction_provider
to transcripts.

Revision ID: phase9a_redaction
Revises: phase8a_rubrics
Create Date: 2026-06-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "phase9a_redaction"
down_revision: str | None = "phase8a_rubrics"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Add redaction columns."""
    op.add_column(
        "transcript_segments",
        sa.Column("redacted_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "transcripts",
        sa.Column("redaction_provider", sa.String(32), nullable=True),
    )
    op.add_column(
        "transcripts",
        sa.Column("entities_redacted", sa.dialects.postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Remove redaction columns."""
    op.drop_column("transcripts", "entities_redacted")
    op.drop_column("transcripts", "redaction_provider")
    op.drop_column("transcript_segments", "redacted_text")
