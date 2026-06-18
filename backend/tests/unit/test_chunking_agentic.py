"""Smoke tests for app/ingestion/chunking/agentic.py.

Mocks the LLM client to verify the contract without hitting a real model:
- One Chunk per LLM-identified section
- context_header is the LLM-generated summary; content is the verbatim section text
- Invalid LLM output raises ChunkingError
- Oversized sections fall back to token windowing; only first sub-chunk keeps the summary as context_header
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import ChunkingError
from app.ingestion.chunking.agentic import chunk_agentic
from app.models.schemas import Chunk, ChunkMetadata


def make_metadata() -> ChunkMetadata:
    return ChunkMetadata(
        company="Celonis",
        source_type="earnings_call",
        source_origin="third_party",
        date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        url="https://example.com",
        title="Q1 Earnings Call",
        language="en",
        topic=[],
        content_type="transcript",
        visual_type=None,
        chunking_strategy="agentic",
    )


def make_client(response: str) -> MagicMock:
    """Return a fake ChatClient whose complete() returns the given string."""
    client = MagicMock()
    client.complete = AsyncMock(return_value=response)
    return client


def llm_response(sections: list[dict]) -> str:
    """Build the JSON string the LLM is expected to return."""
    return json.dumps({"sections": sections})


TEXT = "Full earnings call transcript."


# ---------------------------------------------------------------------------
# Happy path: contract verification
# ---------------------------------------------------------------------------

class TestAgenticContract:
    async def test_returns_one_chunk_per_section(self):
        response = llm_response([
            {"summary": "Revenue overview", "content": "Revenue grew 20%."},
            {"summary": "Outlook", "content": "Strong pipeline ahead."},
        ])
        chunks = await chunk_agentic(TEXT, make_metadata(), make_client(response))
        assert len(chunks) == 2

    async def test_context_header_is_summary(self):
        response = llm_response([
            {"summary": "Summary here", "content": "Content here."},
        ])
        chunks = await chunk_agentic(TEXT, make_metadata(), make_client(response))
        assert chunks[0].context_header == "Summary here"

    async def test_content_is_verbatim_section_text(self):
        response = llm_response([
            {"summary": "Summary here", "content": "Content here."},
        ])
        chunks = await chunk_agentic(TEXT, make_metadata(), make_client(response))
        assert chunks[0].content == "Content here."


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

class TestAgenticOutputShape:
    async def test_returns_chunk_instances(self):
        response = llm_response([{"summary": "S", "content": "C"}])
        chunks = await chunk_agentic(TEXT, make_metadata(), make_client(response))
        assert all(isinstance(c, Chunk) for c in chunks)

    async def test_chunk_ids_are_populated(self):
        response = llm_response([{"summary": "S", "content": "C"}])
        chunks = await chunk_agentic(TEXT, make_metadata(), make_client(response))
        assert all(c.id is not None for c in chunks)

    async def test_chunking_strategy_is_agentic(self):
        response = llm_response([{"summary": "S", "content": "C"}])
        chunks = await chunk_agentic(TEXT, make_metadata(), make_client(response))
        assert all(c.metadata.chunking_strategy == "agentic" for c in chunks)


# ---------------------------------------------------------------------------
# Invalid LLM output → ChunkingError
# ---------------------------------------------------------------------------

class TestAgenticInvalidOutput:
    async def test_invalid_json_raises_chunking_error(self):
        with pytest.raises(ChunkingError):
            await chunk_agentic(TEXT, make_metadata(), make_client("not json"))

    async def test_missing_sections_key_raises_chunking_error(self):
        with pytest.raises(ChunkingError):
            await chunk_agentic(TEXT, make_metadata(), make_client('{"wrong_key": []}'))


# ---------------------------------------------------------------------------
# Oversized section → fallback split
# ---------------------------------------------------------------------------

class TestAgenticOversizedFallback:
    async def test_oversized_section_produces_multiple_chunks(self):
        # ~900 tokens > _MAX_TOKENS (800) → triggers fallback split
        long_content = ("word " * 900).strip()
        response = llm_response([{"summary": "Long section", "content": long_content}])
        chunks = await chunk_agentic(TEXT, make_metadata(), make_client(response))
        assert len(chunks) > 1

    async def test_only_first_sub_chunk_has_summary_as_context_header(self):
        long_content = ("word " * 900).strip()
        response = llm_response([{"summary": "Long section", "content": long_content}])
        chunks = await chunk_agentic(TEXT, make_metadata(), make_client(response))
        assert chunks[0].context_header == "Long section"
        assert chunks[1].context_header != "Long section"
