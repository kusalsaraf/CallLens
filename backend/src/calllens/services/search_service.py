"""Semantic search over transcript segments using pgvector cosine similarity."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.scoring import band
from calllens.db.models.agent import Agent
from calllens.db.models.analysis import CallAnalysis
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.embeddings.factory import get_embedder

logger = logging.getLogger(__name__)


async def search(
    db: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    agent_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: CallStatus | None = None,
) -> list[dict[str, Any]]:
    """Embed *query*, search segment embeddings, and return results grouped by call.

    Args:
        db: Active database session.
        query: The natural-language search query.
        limit: Maximum number of matching segments to retrieve (before grouping).
        agent_id: Optional filter — only segments from calls by this agent.
        team_id: Optional filter — only segments from calls by agents on this team.
        date_from: Optional filter — calls created on or after this timestamp.
        date_to: Optional filter — calls created on or before this timestamp.
        status: Optional filter — only calls with this status.

    Returns:
        A list of dicts, one per call, sorted by best-match similarity (desc).
        Each dict contains call metadata and a ``snippets`` list of matching
        segments with their similarity scores.
    """
    embedder = get_embedder()
    query_vec = await embedder.embed_query(query)

    distance_expr = TranscriptSegment.embedding.cosine_distance(query_vec)

    stmt = (
        select(
            TranscriptSegment.id.label("segment_id"),
            TranscriptSegment.start_ms,
            TranscriptSegment.text,
            (1 - distance_expr).label("similarity"),
            Call.id.label("call_id"),
            Call.created_at.label("uploaded_at"),
            Call.agent_id,
            Agent.name.label("agent_name"),
            CallAnalysis.overall_score,
        )
        .join(Transcript, TranscriptSegment.transcript_id == Transcript.id)
        .join(Call, Transcript.call_id == Call.id)
        .outerjoin(Agent, Call.agent_id == Agent.id)
        .outerjoin(CallAnalysis, CallAnalysis.call_id == Call.id)
        .where(TranscriptSegment.embedding.isnot(None))
    )

    if agent_id is not None:
        stmt = stmt.where(Call.agent_id == agent_id)
    if team_id is not None:
        stmt = stmt.where(Agent.team_id == team_id)
    if date_from is not None:
        stmt = stmt.where(Call.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Call.created_at <= date_to)
    if status is not None:
        stmt = stmt.where(Call.status == status)

    stmt = stmt.order_by(distance_expr.asc()).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    calls_map: dict[uuid.UUID, dict[str, Any]] = {}
    for row in rows:
        cid = row.call_id
        if cid not in calls_map:
            overall = row.overall_score
            calls_map[cid] = {
                "call_id": cid,
                "agent_name": row.agent_name,
                "overall_score": overall,
                "band": band(overall) if overall is not None else None,
                "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
                "snippets": [],
            }
        calls_map[cid]["snippets"].append(
            {
                "segment_id": row.segment_id,
                "start_ms": row.start_ms,
                "text": row.text,
                "similarity": round(float(row.similarity), 4),
            }
        )

    return sorted(
        calls_map.values(),
        key=lambda c: max(s["similarity"] for s in c["snippets"]),
        reverse=True,
    )
