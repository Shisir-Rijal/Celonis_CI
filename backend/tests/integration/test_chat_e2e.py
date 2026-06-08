"""End-to-end smoke tests for POST /chat (Issue #11).

External dependencies (search_chunks + OpenAI) are mocked so the tests
run without a live database or API key.  Three scenarios are covered:

1. Happy path — retrieval returns chunks, LLM returns a structured reply
   → response shape is correct, sources non-empty, derivation non-empty.
2. No-sources path — retrieval returns an empty list
   → clear "no sources" answer, empty sources, empty derivation.
3. LLM error path — LLM raises LLMProviderError
   → endpoint returns HTTP 503, no stack trace in body.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.schemas import Chunk, ChunkMetadata


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_chunk() -> Chunk:
    """Return a minimal but valid Chunk for use in tests."""
    return Chunk(
        id=uuid4(),
        content="Celonis is a process mining software company.",
        metadata=ChunkMetadata(
            company="Celonis",
            source_type="blog",
            source_origin="owned",
            date=datetime(2024, 1, 1),
            url="https://celonis.com/blog/about",
            title="About Celonis",
            language="en",
            topic=["company"],
            content_type="text",
            visual_type=None,
            chunking_strategy="structural",
        ),
        embedding=None,
        created_at=None,
        relevance_score=0.85,
    )


@pytest.fixture
async def auth_token() -> str:
    """Log in with the configured APP_PASSWORD and return a valid JWT."""
    from app.config import get_settings

    password = get_settings().APP_PASSWORD
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/auth/login", json={"password": password})
    assert response.status_code == 200, "Login failed in test fixture"
    return response.json()["access_token"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_e2e_returns_sources_and_derivation(auth_token: str) -> None:
    """Happy path: retrieval hits → LLM answer → non-empty sources and derivation."""
    chunk = _make_chunk()
    chunk_id = str(chunk.id)

    # The LLM reply must follow the ANSWER / DERIVATION format from the prompt.
    llm_reply = (
        f"ANSWER:\n"
        f"Celonis is a process mining company. [{chunk_id}]\n\n"
        f"DERIVATION:\n"
        f"Source [{chunk_id}] explicitly states that Celonis is a process mining company."
    )

    with (
        patch("app.api.chat.search_chunks", new=AsyncMock(return_value=[chunk])),
        patch("app.api.chat.get_openai_client") as mock_factory,
    ):
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=llm_reply)
        mock_factory.return_value = mock_client

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/chat",
                json={"query": "What is Celonis?"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

    assert response.status_code == 200
    body = response.json()

    assert body["answer"] != ""
    assert body["derivation"] != ""
    assert len(body["sources"]) > 0

    source = body["sources"][0]
    assert source["url"] == "https://celonis.com/blog/about"
    assert source["title"] == "About Celonis"
    assert source["relevance_score"] == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_chat_e2e_no_sources_returns_clear_message(auth_token: str) -> None:
    """Zero retrieval hits → clear answer, empty sources, empty derivation."""
    with patch("app.api.chat.search_chunks", new=AsyncMock(return_value=[])):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/chat",
                json={"query": "Something with no matching sources"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

    assert response.status_code == 200
    body = response.json()

    assert "no relevant sources" in body["answer"].lower()
    assert body["sources"] == []
    assert body["derivation"] == ""


@pytest.mark.asyncio
async def test_chat_e2e_llm_error_returns_503(auth_token: str) -> None:
    """LLM provider failure → HTTP 503, no internal details exposed."""
    from app.exceptions import LLMProviderError

    chunk = _make_chunk()

    with (
        patch("app.api.chat.search_chunks", new=AsyncMock(return_value=[chunk])),
        patch("app.api.chat.get_openai_client") as mock_factory,
    ):
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(side_effect=LLMProviderError("timeout"))
        mock_factory.return_value = mock_client

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/chat",
                json={"query": "What is Celonis?"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

    assert response.status_code == 503
    body = response.json()
    assert "detail" in body
    assert "LLM provider" in body["detail"]
