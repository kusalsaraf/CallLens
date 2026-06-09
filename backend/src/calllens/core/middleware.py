"""Security-related HTTP middleware."""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from calllens.core.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every response.

    Adds X-Content-Type-Options, X-Frame-Options, Referrer-Policy,
    and HSTS (in production only).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Add security headers to the response.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or route handler.

        Returns:
            Response with security headers attached.
        """
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        settings = get_settings()
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


# In-memory sliding window — acceptable for a single-instance deploy.
# For multi-instance, replace with Redis-based rate limiting.
_rate_store: dict[str, list[float]] = defaultdict(list)

_AUTH_PATHS = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/signup",
        "/api/v1/auth/refresh",
    }
)


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter for auth endpoints.

    Limits requests per IP per minute to prevent brute-force attacks.
    Only applies to login, signup, and refresh endpoints.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Check rate limit before processing auth requests.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or route handler.

        Returns:
            429 if rate exceeded, otherwise the normal response.
        """
        if request.url.path not in _AUTH_PATHS or request.method != "POST":
            return await call_next(request)

        settings = get_settings()
        limit = settings.auth_rate_limit_per_minute

        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path}"
        now = time.monotonic()
        window = 60.0

        timestamps = _rate_store[key]
        timestamps[:] = [t for t in timestamps if now - t < window]

        if len(timestamps) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again later."},
            )

        timestamps.append(now)
        return await call_next(request)


def clear_rate_limit_store() -> None:
    """Reset the in-memory rate limit store (for testing)."""
    _rate_store.clear()
