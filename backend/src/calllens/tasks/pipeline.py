"""Celery task wrapping run_call_pipeline."""

import asyncio
import logging
import uuid

from celery import Task

from calllens.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="calllens.tasks.pipeline.process_call")  # type: ignore[untyped-decorator]
def process_call_task(self: Task, call_id: str) -> None:
    """Run the call processing pipeline in a Celery worker.

    Args:
        self: The bound Celery Task instance.
        call_id: String representation of the Call UUID.
    """
    from calllens.services.call_pipeline import run_call_pipeline

    logger.info("Starting pipeline task", extra={"call_id": call_id})
    asyncio.run(run_call_pipeline(uuid.UUID(call_id)))
