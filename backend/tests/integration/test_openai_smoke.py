"""Smoke tests against the real OpenAI API.

These tests make actual HTTP requests and consume API credits.
They are skipped automatically when OPENAI_API_KEY is not set.

Run manually with:
    uv run pytest tests/integration/test_openai_smoke.py -v -m integration
"""

import os
import pytest

from app.llm.openai_client import OpenAIClient, OpenAISettings


# Skip the entire module if no API key is present.
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping integration tests",
)


@pytest.fixture
def client() -> OpenAIClient:
    """Real OpenAIClient reading from environment variables."""
    return OpenAIClient(settings=OpenAISettings())


@pytest.mark.integration
async def test_complete_returns_nonempty_string(client: OpenAIClient):
    """complete() hits the real API and returns a non-empty string."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Reply briefly."},
        {"role": "user", "content": "Say the word 'hello' and nothing else."},
    ]
    result = await client.complete(messages)

    assert isinstance(result, str)
    assert len(result.strip()) > 0


@pytest.mark.integration
async def test_embed_returns_correct_dimensions(client: OpenAIClient):
    """embed() returns one vector of length 1536 per input text."""
    texts = ["Celonis is a process mining company.", "SAP is an ERP vendor."]
    vectors = await client.embed(texts)

    assert len(vectors) == 2
    assert all(len(v) == 1536 for v in vectors)
    assert all(isinstance(f, float) for v in vectors for f in v)


@pytest.mark.integration
async def test_embed_order_matches_input(client: OpenAIClient):
    """Returned vectors are in the same order as the input texts."""
    texts = ["first", "second", "third"]
    vectors = await client.embed(texts)

    # Each text should produce a different vector.
    assert vectors[0] != vectors[1]
    assert vectors[1] != vectors[2]
    assert len(vectors) == len(texts)
