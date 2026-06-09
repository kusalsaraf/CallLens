"""phase8a_rubric_crud

Revision ID: phase8a_rubrics
Revises: phase7a_embeddings
Create Date: 2026-06-09 01:00:00.000000

Add is_active column to rubrics, rubric_id FK to calls, and set the
seed Support QA rubric as active.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "phase8a_rubrics"
down_revision: str | None = "phase7a_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rubrics",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.add_column(
        "calls",
        sa.Column(
            "rubric_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("rubrics.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_calls_rubric_id", "calls", ["rubric_id"])

    # Mark the default seed rubric as active
    op.execute("UPDATE rubrics SET is_active = true WHERE is_default = true")


def downgrade() -> None:
    op.drop_index("ix_calls_rubric_id", table_name="calls")
    op.drop_column("calls", "rubric_id")
    op.drop_column("rubrics", "is_active")
