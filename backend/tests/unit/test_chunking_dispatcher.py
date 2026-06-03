"""Unit tests for app/ingestion/chunking/dispatcher.py.

Tests only the routing logic — not the individual strategies.
Each strategy is mocked so we only verify which one gets called.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import ChunkingError
from app.ingestion.chunking.dispatcher import chunk
from app.models.schemas import ChunkMetadata


def make_metadata(source_type: str) -> ChunkMetadata:
    return ChunkMetadata(
        company="Celonis",
        source_type=source_type,
        source_origin="owned",
        date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        url="https://example.com",
        title=None,
        language="en",
        topic=[],
        content_type="text",
        visual_type=None,
        chunking_strategy="structural",
    )


TEXT = "Some text."

_STRUCTURAL = "app.ingestion.chunking.dispatcher.chunk_structural"
_NONE_ENRICHED = "app.ingestion.chunking.dispatcher.chunk_none_enriched"
_AGENTIC = "app.ingestion.chunking.dispatcher.chunk_agentic"


class TestStructuralRouting:
    @pytest.mark.parametrize("source_type", ["press_release", "news", "website", "career_page"])
    async def test_routes_to_structural(self, source_type):
        with patch(_STRUCTURAL, return_value=[]) as mock_fn:
            await chunk(TEXT, make_metadata(source_type))
            mock_fn.assert_called_once()


class TestNoneEnrichedRouting:
    @pytest.mark.parametrize("source_type", ["social", "geo_response", "reddit"])
    async def test_routes_to_none_enriched(self, source_type):
        with patch(_NONE_ENRICHED, return_value=[]) as mock_fn:
            await chunk(TEXT, make_metadata(source_type))
            mock_fn.assert_called_once()


class TestAgenticRouting:
    @pytest.mark.parametrize("source_type", ["earnings_call", "analyst_report"])
    async def test_routes_to_agentic_with_client(self, source_type):
        client = MagicMock()
        with patch(_AGENTIC, new_callable=AsyncMock, return_value=[]) as mock_fn:
            await chunk(TEXT, make_metadata(source_type), client=client)
            mock_fn.assert_called_once()

    @pytest.mark.parametrize("source_type", ["earnings_call", "analyst_report"])
    async def test_raises_without_client(self, source_type):
        with pytest.raises(ChunkingError):
            await chunk(TEXT, make_metadata(source_type), client=None)


class TestFallback:
    async def test_unknown_source_type_falls_back_to_structural(self):
        with patch(_STRUCTURAL, return_value=[]) as mock_fn:
            await chunk(TEXT, make_metadata("unknown_type"))
            mock_fn.assert_called_once()
