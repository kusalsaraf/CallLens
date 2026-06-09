"""FastAPI application factory."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from calllens.api.v1 import auth, calls, health
from calllens.api.v1.agents import router as agents_router
from calllens.api.v1.analytics import router as analytics_router
from calllens.api.v1.coaching import router as coaching_router
from calllens.api.v1.search import router as search_router
from calllens.api.v1.teams import router as teams_router
from calllens.core.config import get_settings
from calllens.core.exceptions import register_exception_handlers
from calllens.core.logging import CorrelationIDMiddleware, configure_logging
from calllens.db.session import get_session_factory
from calllens.services.seed import seed_defaults

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Run startup/shutdown tasks around the application lifespan."""
    factory = get_session_factory()
    async with factory() as db:
        await seed_defaults(db)
    yield


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
        lifespan=lifespan,
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
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(calls.router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(coaching_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(teams_router, prefix="/api/v1")

    logger.info("CallLens API started", extra={"env": settings.app_env})

    return app


app = create_app()
