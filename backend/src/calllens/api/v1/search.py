"""Semantic search API endpoint."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.deps import get_current_user
from calllens.core.exceptions import ValidationError
from calllens.db.models.call import CallStatus
from calllens.db.models.user import User
from calllens.db.session import get_db
from calllens.schemas.search import SearchResponse
from calllens.services.search_service import search

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 20


@router.get("", response_model=SearchResponse)
async def search_calls(
    q: Annotated[str, Query(description="Natural-language search query")],
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = _DEFAULT_LIMIT,
    agent_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: str | None = None,
) -> SearchResponse:
    """Search transcript segments by semantic similarity.

    Args:
        q: The natural-language query string (must be non-empty).
        db: Injected database session.
        user: Authenticated user (auth guard).
        limit: Max matching segments (before grouping by call).
        agent_id: Optional filter by agent UUID.
        team_id: Optional filter by team UUID.
        date_from: Optional lower bound on call creation date.
        date_to: Optional upper bound on call creation date.
        status: Optional call status filter.

    Returns:
        Search results grouped by call with segment snippets.
    """
    stripped = q.strip()
    if not stripped:
        raise ValidationError("Search query must be non-empty.")

    call_status: CallStatus | None = None
    if status is not None:
        try:
            call_status = CallStatus(status)
        except ValueError as exc:
            raise ValidationError(f"Invalid status: {status!r}") from exc

    results = await search(
        db,
        stripped,
        limit=limit,
        agent_id=agent_id,
        team_id=team_id,
        date_from=date_from,
        date_to=date_to,
        status=call_status,
    )

    return SearchResponse(
        query=stripped,
        results=results,
        total=len(results),
    )
