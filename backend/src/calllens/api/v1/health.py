"""Health and readiness check endpoints."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.exceptions import AppError
from calllens.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Return a simple liveness response.

    Returns:
        A JSON object confirming the service is running.
    """
    return {"status": "ok"}


@router.get("/readiness")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Check that the service and its dependencies are ready to serve traffic.

    Verifies database connectivity by issuing a lightweight query.

    Args:
        db: Injected async database session.

    Returns:
        A JSON object with status ``"ok"`` when all checks pass.

    Raises:
        AppError: When the database connectivity check fails.
    """
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("Readiness check failed: database unreachable")
        raise AppError(
            "Database unavailable", status_code=503, error_code="db_unavailable"
        ) from exc

    return {"status": "ok"}
