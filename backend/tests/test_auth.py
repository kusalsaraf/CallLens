"""Tests for authentication endpoints."""

from httpx import AsyncClient

from tests.conftest import _SIGNUP_PAYLOAD, signup_and_get_token

_LOGIN_PAYLOAD = {
    "email": _SIGNUP_PAYLOAD["email"],
    "password": _SIGNUP_PAYLOAD["password"],
}


async def test_signup_success(client: AsyncClient) -> None:
    """Signup returns 200 with a well-formed TokenResponse."""
    resp = await client.post("/api/v1/auth/signup", json=_SIGNUP_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["expires_in"] > 0


async def test_signup_sets_refresh_cookie(client: AsyncClient) -> None:
    """Signup sets an httpOnly refresh_token cookie."""
    resp = await client.post("/api/v1/auth/signup", json=_SIGNUP_PAYLOAD)
    assert resp.status_code == 200
    assert "refresh_token" in resp.cookies


async def test_signup_locked_after_first_user(client: AsyncClient) -> None:
    """Second signup attempt is rejected with 409."""
    await client.post("/api/v1/auth/signup", json=_SIGNUP_PAYLOAD)
    resp = await client.post(
        "/api/v1/auth/signup",
        json={**_SIGNUP_PAYLOAD, "email": "other@example.com"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "conflict"


async def test_login_success(client: AsyncClient) -> None:
    """Login with correct credentials returns 200 and a token."""
    await signup_and_get_token(client)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)


async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    """Wrong password returns generic 401 — never leaks credential details."""
    await signup_and_get_token(client)
    resp = await client.post(
        "/api/v1/auth/login",
        json={**_LOGIN_PAYLOAD, "password": "wrongPassword99"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] == "authentication_required"


async def test_login_unknown_email_returns_401(client: AsyncClient) -> None:
    """Unknown email returns the same generic 401."""
    await signup_and_get_token(client)
    resp = await client.post(
        "/api/v1/auth/login",
        json={**_LOGIN_PAYLOAD, "email": "nobody@example.com"},
    )
    assert resp.status_code == 401


async def test_me_with_valid_token(client: AsyncClient) -> None:
    """GET /me with a valid Bearer token returns user profile."""
    token = await signup_and_get_token(client)
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == _SIGNUP_PAYLOAD["email"]
    assert body["name"] == _SIGNUP_PAYLOAD["name"]
    assert body["is_active"] is True


async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    """GET /me with no Authorization header returns 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_with_bad_token_returns_401(client: AsyncClient) -> None:
    """GET /me with a malformed token returns 401."""
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.valid.jwt"})
    assert resp.status_code == 401


async def test_refresh_issues_new_access_token(client: AsyncClient) -> None:
    """POST /refresh returns a new access token and rotates the refresh cookie."""
    await signup_and_get_token(client)
    # Login to get the refresh cookie stored in the client's cookie jar
    login_resp = await client.post("/api/v1/auth/login", json=_LOGIN_PAYLOAD)
    old_access = login_resp.json()["access_token"]

    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200
    new_access = refresh_resp.json()["access_token"]
    assert new_access != old_access
    # Rotated refresh cookie is set
    assert "refresh_token" in refresh_resp.cookies


async def test_refresh_without_cookie_returns_401(client: AsyncClient) -> None:
    """POST /refresh with no cookie returns 401."""
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_logout_clears_refresh_cookie(client: AsyncClient) -> None:
    """POST /logout deletes the refresh_token cookie."""
    await signup_and_get_token(client)
    await client.post("/api/v1/auth/login", json=_LOGIN_PAYLOAD)

    logout_resp = await client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200
    # Cookie should be cleared (empty value or absent after deletion)
    assert (
        client.cookies.get("refresh_token") is None
        or logout_resp.cookies.get("refresh_token") == ""
    )
