"""Topics API — taxonomy listing and per-topic stats."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.deps import get_current_user
from calllens.core.exceptions import NotFoundError
from calllens.core.scoring import band as band_from_score
from calllens.db.models.analysis import CallAnalysis
from calllens.db.models.call import Call
from calllens.db.models.topic import CallTopic, Topic
from calllens.db.models.user import User
from calllens.db.session import get_db
from calllens.schemas.analytics import TopicDetailOut, TopicListOut, TopicOut

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("/", response_model=TopicListOut)
async def list_topics(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TopicListOut:
    """Return the full topic taxonomy.

    Args:
        db: Database session.
        current_user: Authenticated user.

    Returns:
        TopicListOut with all topics ordered by name.
    """
    result = await db.execute(select(Topic).order_by(Topic.name))
    topics = result.scalars().all()
    return TopicListOut(
        items=[TopicOut(id=t.id, name=t.name, slug=t.slug, keywords=t.keywords) for t in topics]
    )


@router.get("/{topic_id}", response_model=TopicDetailOut)
async def get_topic(
    topic_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TopicDetailOut:
    """Return a single topic with its aggregate stats.

    Args:
        topic_id: UUID of the topic.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        TopicDetailOut with call_count and avg_overall_score.

    Raises:
        NotFoundError: If the topic does not exist.
    """
    result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    if topic is None:
        raise NotFoundError(f"Topic {topic_id} not found")

    stats = (
        await db.execute(
            select(
                func.count(Call.id.distinct()).label("call_count"),
                func.avg(CallAnalysis.overall_score).label("avg_score"),
            )
            .select_from(CallTopic)
            .join(Call, Call.id == CallTopic.call_id)
            .outerjoin(CallAnalysis, CallAnalysis.call_id == Call.id)
            .where(CallTopic.topic_id == topic_id)
        )
    ).one()

    avg = round(float(stats.avg_score), 1) if stats.avg_score is not None else None

    return TopicDetailOut(
        id=topic.id,
        name=topic.name,
        slug=topic.slug,
        keywords=topic.keywords,
        call_count=stats.call_count,
        avg_overall_score=avg,
        band=band_from_score(int(avg)) if avg is not None else None,
    )
