"""phase3a_scoring_models

Revision ID: phase3a_scoring
Revises: 6a831ce6d751
Create Date: 2026-06-07 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "phase3a_scoring"
down_revision: Union[str, None] = "6a831ce6d751"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend the callstatus enum with scoring pipeline states.
    # ADD VALUE IF NOT EXISTS is idempotent — safe to re-run.
    op.execute("ALTER TYPE callstatus ADD VALUE IF NOT EXISTS 'scoring'")
    op.execute("ALTER TYPE callstatus ADD VALUE IF NOT EXISTS 'scored'")

    op.create_table(
        "rubrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_rubrics_name"),
    )

    op.create_table(
        "rubric_dimensions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rubric_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["rubric_id"], ["rubrics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rubric_id", "key", name="uq_rubric_dimensions_rubric_key"),
    )
    op.create_index(
        op.f("ix_rubric_dimensions_rubric_id"), "rubric_dimensions", ["rubric_id"], unique=False
    )

    op.create_table(
        "call_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("dimension_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("is_supported", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dimension_id"], ["rubric_dimensions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_call_scores_call_id"), "call_scores", ["call_id"], unique=False)
    op.create_index(
        op.f("ix_call_scores_dimension_id"), "call_scores", ["dimension_id"], unique=False
    )

    op.create_table(
        "score_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("call_score_id", sa.Uuid(), nullable=False),
        sa.Column("segment_id", sa.Uuid(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["call_score_id"], ["call_scores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["segment_id"], ["transcript_segments.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_score_evidence_call_score_id"), "score_evidence", ["call_score_id"], unique=False
    )
    op.create_index(
        op.f("ix_score_evidence_segment_id"), "score_evidence", ["segment_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_score_evidence_segment_id"), table_name="score_evidence")
    op.drop_index(op.f("ix_score_evidence_call_score_id"), table_name="score_evidence")
    op.drop_table("score_evidence")

    op.drop_index(op.f("ix_call_scores_dimension_id"), table_name="call_scores")
    op.drop_index(op.f("ix_call_scores_call_id"), table_name="call_scores")
    op.drop_table("call_scores")

    op.drop_index(op.f("ix_rubric_dimensions_rubric_id"), table_name="rubric_dimensions")
    op.drop_table("rubric_dimensions")

    op.drop_table("rubrics")

    # PostgreSQL does not support removing enum values — intentionally omitted.
