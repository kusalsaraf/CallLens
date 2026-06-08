"""phase4b_analysis_coaching_audit_agentrun

Revision ID: phase4b_analysis
Revises: phase3a_scoring
Create Date: 2026-06-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "phase4b_analysis"
down_revision: Union[str, None] = "phase3a_scoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "call_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "key_moments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "action_items",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("sentiment_overall", sa.Text(), nullable=True),
        sa.Column("talk_listen_ratio", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("interruptions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "longest_monologue_ms", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("total_turns", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "compliance_passed", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "escalate_for_review", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_id", name="uq_call_analyses_call_id"),
    )
    op.create_index(
        op.f("ix_call_analyses_call_id"), "call_analyses", ["call_id"], unique=True
    )

    op.create_table(
        "coaching_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.Uuid(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_coaching_notes_agent_id"), "coaching_notes", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_coaching_notes_call_id"), "coaching_notes", ["call_id"], unique=False
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)

    op.create_table(
        "call_agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("node", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "evidence_kept", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "evidence_dropped", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "duration_ms", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_call_agent_runs_call_id"), "call_agent_runs", ["call_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_call_agent_runs_call_id"), table_name="call_agent_runs")
    op.drop_table("call_agent_runs")

    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index(op.f("ix_coaching_notes_call_id"), table_name="coaching_notes")
    op.drop_index(op.f("ix_coaching_notes_agent_id"), table_name="coaching_notes")
    op.drop_table("coaching_notes")

    op.drop_index(op.f("ix_call_analyses_call_id"), table_name="call_analyses")
    op.drop_table("call_analyses")
