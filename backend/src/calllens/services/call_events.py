"""Publish call status changes to Redis pub/sub."""

import json
import logging
import uuid

import redis.asyncio as aioredis

from calllens.core.config import get_settings

logger = logging.getLogger(__name__)


async def publish_call_event(
    call_id: uuid.UUID,
    status: str,
    detail: str | None = None,
) -> None:
    """Publish a status-change event to the call's Redis channel.

    Args:
        call_id: ID of the call whose status changed.
        status: New status string (value of CallStatus enum).
        detail: Optional error detail; present only on failure.
    """
    settings = get_settings()
    channel = f"call:{call_id}:events"
    payload = json.dumps({"status": status, "detail": detail})
    r: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=False)
    try:
        await r.publish(channel, payload)
        logger.debug("Published event", extra={"channel": channel, "status": status})
    finally:
        await r.aclose()
