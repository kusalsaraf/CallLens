"""FastAPI application factory."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from calllens.api.v1 import health
from calllens.core.config import get_settings
from calllens.core.exceptions import register_exception_handlers
from calllens.core.logging import CorrelationIDMiddleware, configure_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A fully configured ``FastAPI`` instance ready to serve requests.
    """
    settings = get_settings()

    configure_logging(level=logging.DEBUG if settings.app_debug else logging.INFO)

    app = FastAPI(
        title="CallLens API",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
    )

    # Middleware (registered in reverse order of execution)
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Routers
    app.include_router(health.router)

    logger.info("CallLens API started", extra={"env": settings.app_env})

    return app


app = create_app()
