"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from calllens.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return (and lazily create) the async SQLAlchemy engine.

    When ``DB_USE_PGBOUNCER=true``, disables asyncpg's prepared-statement
    cache (``statement_cache_size=0``) and server-side prepared statements
    so the connection works through transaction-mode poolers like Supabase
    (port 6543) or standalone PgBouncer.

    Returns:
        The shared ``AsyncEngine`` instance.
    """
    global _engine
    if _engine is None:
        settings = get_settings()

        connect_args: dict[str, int] = {}
        if settings.db_use_pgbouncer:
            connect_args["statement_cache_size"] = 0
            connect_args["prepared_statement_cache_size"] = 0

        _engine = create_async_engine(
            settings.database_url,
            echo=settings.app_debug,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return (and lazily create) the async session factory.

    Returns:
        An ``async_sessionmaker`` bound to the shared engine.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request.

    Yields:
        An ``AsyncSession`` that is closed after the request completes.
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session
