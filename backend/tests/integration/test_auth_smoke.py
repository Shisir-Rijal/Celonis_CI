"""Auth integration smoke tests.

Tests the full login → token → protected route flow against the real
FastAPI app (no live server, uses ASGI transport).

Requires APP_PASSWORD and JWT_SECRET to be set in the environment or .env.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_login_with_correct_password_returns_token() -> None:
    """POST /auth/login with correct APP_PASSWORD returns a JWT."""
    from app.config import get_settings
    password = get_settings().APP_PASSWORD

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/login", json={"password": password})

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 86400
    assert len(body["access_token"]) > 20


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401() -> None:
    """POST /auth/login with wrong password returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/login", json={"password": "wrong-password"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_without_token_returns_401() -> None:
    """POST /chat without Authorization header returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/chat", json={"query": "test"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_with_invalid_token_returns_401() -> None:
    """POST /chat with a garbage token returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/chat",
            json={"query": "test"},
            headers={"Authorization": "Bearer not.a.real.token"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_full_login_then_chat_flow() -> None:
    """Login → use returned token → POST /chat returns SSE stream."""
    from app.config import get_settings
    password = get_settings().APP_PASSWORD

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: login
        login_response = await client.post("/auth/login", json={"password": password})
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Step 2: use token to hit /chat
        chat_response = await client.post(
            "/chat",
            json={"query": "Who is SAP?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert chat_response.status_code == 200
    assert "text/event-stream" in chat_response.headers.get("content-type", "")
    assert "data:" in chat_response.text


@pytest.mark.asyncio
async def test_health_works_without_token() -> None:
    """/health remains accessible without authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
