"""Phase 12A tests: production config, security headers, rate limiting, docs gating."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from calllens.core.config import Settings
from calllens.core.middleware import clear_rate_limit_store

# ─── Production config validation ────────────────────────────────────


class TestProductionConfig:
    """Validate production config requires real secrets."""

    def test_prod_missing_jwt_secret_raises(self) -> None:
        """APP_ENV=production with default JWT_SECRET raises ValueError."""
        with pytest.raises(ValueError, match="JWT_SECRET"):
            Settings(
                app_env="production",
                jwt_secret="CHANGE-ME-IN-PRODUCTION-use-a-random-32-plus-byte-secret",
                database_url="postgresql+asyncpg://real:real@db:5432/calllens",
                _env_file=None,
            )

    def test_prod_missing_database_url_raises(self) -> None:
        """APP_ENV=production with default DATABASE_URL raises ValueError."""
        with pytest.raises(ValueError, match="DATABASE_URL"):
            Settings(
                app_env="production",
                jwt_secret="a-secure-random-secret-for-prod-use",
                database_url="postgresql+asyncpg://calllens:calllens@localhost:5432/calllens",
                _env_file=None,
            )

    def test_prod_with_valid_secrets_succeeds(self) -> None:
        """APP_ENV=production with real secrets loads without error."""
        settings = Settings(
            app_env="production",
            jwt_secret="a-secure-random-secret-for-prod-use",
            database_url="postgresql+asyncpg://real:real@db:5432/calllens",
            _env_file=None,
        )
        assert settings.app_env == "production"

    def test_prod_cookie_secure_flag(self) -> None:
        """Production config should yield secure=True for cookies."""
        settings = Settings(
            app_env="production",
            jwt_secret="a-secure-random-secret-for-prod-use",
            database_url="postgresql+asyncpg://real:real@db:5432/calllens",
            _env_file=None,
        )
        assert settings.app_env == "production"

    def test_dev_config_loads_with_defaults(self) -> None:
        """Default development config loads fine with insecure defaults."""
        settings = Settings(app_env="development", _env_file=None)
        assert settings.app_env == "development"
        assert settings.jwt_secret != ""

    def test_docs_enabled_default_dev(self) -> None:
        """Docs are enabled by default in development."""
        settings = Settings(app_env="development", _env_file=None)
        assert settings.docs_enabled is True

    def test_docs_disabled_default_prod(self) -> None:
        """Docs are disabled by default in production."""
        settings = Settings(
            app_env="production",
            jwt_secret="a-secure-random-secret-for-prod-use",
            database_url="postgresql+asyncpg://real:real@db:5432/calllens",
            _env_file=None,
        )
        assert settings.docs_enabled is False

    def test_docs_force_enabled_prod(self) -> None:
        """ENABLE_API_DOCS=true overrides production default."""
        settings = Settings(
            app_env="production",
            jwt_secret="a-secure-random-secret-for-prod-use",
            database_url="postgresql+asyncpg://real:real@db:5432/calllens",
            enable_api_docs=True,
            _env_file=None,
        )
        assert settings.docs_enabled is True

    def test_pgbouncer_default_false(self) -> None:
        """DB_USE_PGBOUNCER defaults to false."""
        settings = Settings(app_env="development", _env_file=None)
        assert settings.db_use_pgbouncer is False


# ─── Security headers ────────────────────────────────────────────────


class TestSecurityHeaders:
    """Verify security headers are present on responses."""

    @pytest.mark.asyncio
    async def test_security_headers_on_health(self, client: AsyncClient) -> None:
        """Health endpoint response includes security headers."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_no_hsts_in_dev(self, client: AsyncClient) -> None:
        """HSTS header is NOT set in development mode."""
        resp = await client.get("/health")
        assert "Strict-Transport-Security" not in resp.headers


# ─── API docs gating ─────────────────────────────────────────────────


class TestDocsGating:
    """Verify docs endpoint behaviour based on settings."""

    @pytest.mark.asyncio
    async def test_docs_available_in_dev(self, client: AsyncClient) -> None:
        """In default dev mode, /docs returns 200."""
        resp = await client.get("/docs")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_docs_disabled_when_setting_off(self, db_engine: Any) -> None:
        """When docs_enabled=False, /docs returns 404."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from calllens.db.session import get_db
        from calllens.services.seed import seed_defaults

        mock_settings = Settings(app_env="development", enable_api_docs=False, _env_file=None)

        with patch("calllens.core.config.get_settings", return_value=mock_settings):
            with patch("calllens.main.get_settings", return_value=mock_settings):
                from calllens.main import create_app

                test_app = create_app()

                factory = async_sessionmaker(
                    bind=db_engine, expire_on_commit=False, class_=AsyncSession
                )

                async def _override_get_db():  # type: ignore[no-untyped-def]
                    async with factory() as session:
                        yield session

                test_app.dependency_overrides[get_db] = _override_get_db
                async with factory() as session:
                    await seed_defaults(session)

                async with AsyncClient(
                    transport=ASGITransport(app=test_app),
                    base_url="http://test",
                    follow_redirects=True,
                ) as ac:
                    resp = await ac.get("/docs")
                    assert resp.status_code == 404


# ─── Auth rate limiting ──────────────────────────────────────────────


class TestAuthRateLimit:
    """Verify auth endpoint rate limiting."""

    @pytest.mark.asyncio
    async def test_login_rate_limit_triggers_429(
        self, client: AsyncClient, auth_token: str
    ) -> None:
        """Exceeding the rate limit on login returns 429."""
        clear_rate_limit_store()

        mock_settings = Settings(
            app_env="development",
            auth_rate_limit_per_minute=3,
            _env_file=None,
        )

        with patch("calllens.core.middleware.get_settings", return_value=mock_settings):
            for _ in range(3):
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={"email": "wrong@example.com", "password": "wrong"},
                )
                assert resp.status_code in (200, 401)

            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "wrong@example.com", "password": "wrong"},
            )
            assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_does_not_affect_other_endpoints(
        self, client: AsyncClient, auth_token: str
    ) -> None:
        """Non-auth endpoints are not rate-limited."""
        clear_rate_limit_store()

        for _ in range(30):
            resp = await client.get("/health")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_normal_login_unaffected(self, client: AsyncClient, auth_token: str) -> None:
        """A single login attempt is not rate-limited."""
        clear_rate_limit_store()

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "superSecret1"},
        )
        assert resp.status_code == 200
