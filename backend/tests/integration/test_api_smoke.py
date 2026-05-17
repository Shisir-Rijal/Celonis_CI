"""Smoke tests for the FastAPI endpoints introduced in Issue #6.

Uses httpx.AsyncClient with the app directly (no live server needed).
Tests verify that routes exist, accept the right shapes, and return the
right shapes — not that business logic is correct (there is none yet).

Run with:
    uv run pytest tests/integration/test_api_smoke.py -v
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_healthy() -> None:
    """GET /health must return 200 with status healthy."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_chat_stub_accepts_query() -> None:
    """POST /chat must accept a JSON body with query and return ChatResponse shape."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/chat", json={"query": "Who is SAP?"})

    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert "sources" in body
    assert isinstance(body["sources"], list)


@pytest.mark.asyncio
async def test_chat_rejects_missing_query() -> None:
    """POST /chat without a query field must return 422 (validation error)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/chat", json={})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_workflows_returns_list() -> None:
    """GET /workflows must return 200 with an empty list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/workflows")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_root_returns_service_identity() -> None:
    """GET / must return service identity dict."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "service" in body
