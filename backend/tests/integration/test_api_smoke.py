"""Smoke tests for the FastAPI endpoints introduced in Issue #6.

Uses httpx.AsyncClient with the app directly (no live server needed).
Auth was added in Issue #14 — protected routes now require a valid token.
A shared fixture logs in once and provides the token for all tests that
need it.
"""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def auth_token() -> str:
    """Log in with the configured APP_PASSWORD and return a valid JWT."""
    from app.config import get_settings
    password = get_settings().APP_PASSWORD

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/login", json={"password": password})

    assert response.status_code == 200, "Login failed in test fixture"
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_health_returns_healthy() -> None:
    """GET /health must return 200 with status healthy — no auth required."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_chat_accepts_query(auth_token: str) -> None:
    """POST /chat with a valid token must return ChatResponse shape."""
    with patch("app.api.chat.search_chunks", new=AsyncMock(return_value=[])):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/chat",
                json={"query": "Who is SAP?"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert "sources" in body
    assert isinstance(body["sources"], list)


@pytest.mark.asyncio
async def test_chat_rejects_missing_query(auth_token: str) -> None:
    """POST /chat without a query field must return 422 (validation error)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/chat",
            json={},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_workflows_returns_list(auth_token: str) -> None:
    """GET /workflows with a valid token must return 200 with an empty list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/workflows",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_root_returns_service_identity() -> None:
    """GET / must return service identity dict — no auth required."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "service" in body

class TestOrchestratorSmoke:
    def test_graph_compiles_and_is_importable(self) -> None:
        """Full orchestrator graph compiles end-to-end and is importable."""
        from app.orchestration.graph import orchestrator_graph

        assert orchestrator_graph is not None