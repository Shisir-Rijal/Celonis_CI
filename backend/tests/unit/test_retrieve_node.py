"""backend/tests/unit/test_retrieve_node.py

Unit tests for retrieve_node.
search_chunks is mocked so no Supabase connection is needed.

Issue #60 acceptance criteria:
  - Normal path: results written to retrieved_context
  - Empty results: retrieved_context is []
  - search_chunks raising: exception propagates unchanged
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.orchestration.nodes.retrieve import retrieve_node


@pytest.fixture
def mock_chunks():
    """Two mock Chunk objects with content attributes."""
    chunk1 = MagicMock()
    chunk1.content = "Celonis is a process mining platform."
    chunk2 = MagicMock()
    chunk2.content = "Celonis competes with SAP and IBM."
    return [chunk1, chunk2]


@pytest.mark.asyncio
async def test_retrieve_normal_path(mock_chunks) -> None:
    """search_chunks is called with the correct query and results
    are written to retrieved_context as plain text."""
    with patch(
        "app.orchestration.nodes.retrieve.search_chunks",
        new=AsyncMock(return_value=mock_chunks),
    ) as mock_search:
        state = {"query": "What is Celonis?"}
        result = await retrieve_node(state)

        mock_search.assert_called_once_with(query="What is Celonis?", k=10)
        assert result == {
            "retrieved_context": [
                "Celonis is a process mining platform.",
                "Celonis competes with SAP and IBM.",
            ]
        }


@pytest.mark.asyncio
async def test_retrieve_empty_results() -> None:
    """When search_chunks returns an empty list, retrieved_context is []."""
    with patch(
        "app.orchestration.nodes.retrieve.search_chunks",
        new=AsyncMock(return_value=[]),
    ):
        state = {"query": "query with no results"}
        result = await retrieve_node(state)

        assert result == {"retrieved_context": []}


@pytest.mark.asyncio
async def test_retrieve_search_chunks_raises() -> None:
    """When search_chunks raises, the exception propagates unchanged."""
    with patch(
        "app.orchestration.nodes.retrieve.search_chunks",
        new=AsyncMock(side_effect=RuntimeError("Supabase unreachable")),
    ):
        state = {"query": "What is Celonis?"}

        with pytest.raises(RuntimeError, match="Supabase unreachable"):
            await retrieve_node(state)