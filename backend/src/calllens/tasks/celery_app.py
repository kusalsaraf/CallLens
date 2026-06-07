"""Celery application instance wired to Redis broker and result backend."""

from celery import Celery

from calllens.core.config import get_settings


def _make_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "calllens",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["calllens.tasks.pipeline"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
    )
    return app


celery_app = _make_celery()
