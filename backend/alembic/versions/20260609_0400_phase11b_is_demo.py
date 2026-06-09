"""Phase 11B: add is_demo flag to calls table.

Revision ID: phase11b_is_demo
Revises: phase10a_topics
Create Date: 2026-06-09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "phase11b_is_demo"
down_revision: str | None = "phase10a_topics"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "calls",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_calls_is_demo", "calls", ["is_demo"])


def downgrade() -> None:
    op.drop_index("ix_calls_is_demo", table_name="calls")
    op.drop_column("calls", "is_demo")
