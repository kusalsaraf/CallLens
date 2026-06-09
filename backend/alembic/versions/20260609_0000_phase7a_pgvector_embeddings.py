"""phase7a_pgvector_embeddings

Revision ID: phase7a_embeddings
Revises: phase4b_analysis
Create Date: 2026-06-09 00:00:00.000000

Enable the pgvector extension, migrate the transcript_segments.embedding
column from ARRAY(Float) to Vector(384), and add an HNSW index for
cosine-similarity search.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "phase7a_embeddings"
down_revision: str | None = "phase4b_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMBEDDING_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.drop_column("transcript_segments", "embedding")
    op.add_column(
        "transcript_segments",
        sa.Column("embedding", Vector(_EMBEDDING_DIM), nullable=True),
    )

    op.create_index(
        "ix_transcript_segments_embedding_hnsw",
        "transcript_segments",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_transcript_segments_embedding_hnsw", table_name="transcript_segments")
    op.drop_column("transcript_segments", "embedding")
    op.add_column(
        "transcript_segments",
        sa.Column(
            "embedding",
            sa.ARRAY(sa.Float()),
            nullable=True,
        ),
    )
