"""Unit tests for app.rag.repository.

All tests use a mock Supabase client — no real DB connection required.
The mock mimics the supabase-py v2 response shape:
    response.data = [<row dict>, ...]
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.models.schemas import Chunk, ChunkMetadata
from app.rag.repository import (
    _chunk_to_row,
    _row_to_chunk,
    get_chunk_by_id,
    insert_chunk,
    insert_chunks,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXED_ID = UUID("12345678-1234-5678-1234-567812345678")
FIXED_TS = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def make_metadata(**overrides) -> ChunkMetadata:
    defaults = dict(
        company="Celonis",
        source_type="press_release",
        source_origin="owned",
        date=FIXED_TS,
        url="https://celonis.com/press/example",
        title="Example Press Release",
        language="en",
        topic=["product", "announcement"],
        content_type="text",
        visual_type=None,
        chunking_strategy="structural",
    )
    defaults.update(overrides)
    return ChunkMetadata(**defaults)


def make_chunk(**overrides) -> Chunk:
    defaults = dict(
        id=FIXED_ID,
        content="Celonis announced a new product today.",
        metadata=make_metadata(),
        embedding=None,
        created_at=None,
    )
    defaults.update(overrides)
    return Chunk(**defaults)


def make_row(chunk: Chunk) -> dict:
    """Build the dict that the Supabase response would return for a chunk."""
    return {
        "id": str(chunk.id),
        "content": chunk.content,
        "metadata": chunk.metadata.model_dump(mode="json"),
        "embedding": chunk.embedding,
        "created_at": chunk.created_at.isoformat() if chunk.created_at else FIXED_TS.isoformat(),
    }


def mock_client(rows: list[dict]) -> MagicMock:
    """Create a mock Supabase client whose table(...).X.execute() returns rows."""
    response = MagicMock()
    response.data = rows

    table_mock = MagicMock()
    table_mock.insert.return_value.execute.return_value = response
    table_mock.select.return_value.eq.return_value.limit.return_value.execute.return_value = response

    client = MagicMock()
    client.table.return_value = table_mock
    return client


# ---------------------------------------------------------------------------
# _chunk_to_row
# ---------------------------------------------------------------------------

class TestChunkToRow:
    def test_id_is_string(self) -> None:
        row = _chunk_to_row(make_chunk())
        assert isinstance(row["id"], str)
        assert row["id"] == str(FIXED_ID)

    def test_metadata_is_dict(self) -> None:
        row = _chunk_to_row(make_chunk())
        assert isinstance(row["metadata"], dict)
        assert row["metadata"]["company"] == "Celonis"

    def test_created_at_omitted_when_none(self) -> None:
        row = _chunk_to_row(make_chunk(created_at=None))
        assert "created_at" not in row

    def test_created_at_included_when_set(self) -> None:
        chunk = make_chunk(created_at=FIXED_TS)
        row = _chunk_to_row(chunk)
        assert "created_at" in row
        assert row["created_at"] == FIXED_TS.isoformat()

    def test_embedding_preserved(self) -> None:
        emb = [0.1, 0.2, 0.3]
        row = _chunk_to_row(make_chunk(embedding=emb))
        assert row["embedding"] == emb

    def test_embedding_none_preserved(self) -> None:
        row = _chunk_to_row(make_chunk(embedding=None))
        assert row["embedding"] is None


# ---------------------------------------------------------------------------
# _row_to_chunk
# ---------------------------------------------------------------------------

class TestRowToChunk:
    def test_round_trip(self) -> None:
        original = make_chunk(created_at=FIXED_TS)
        row = make_row(original)
        restored = _row_to_chunk(row)
        assert restored.id == original.id
        assert restored.content == original.content
        assert restored.metadata.company == original.metadata.company

    def test_id_is_uuid(self) -> None:
        row = make_row(make_chunk())
        chunk = _row_to_chunk(row)
        assert isinstance(chunk.id, UUID)

    def test_missing_embedding_is_none(self) -> None:
        row = make_row(make_chunk())
        row.pop("embedding", None)
        chunk = _row_to_chunk(row)
        assert chunk.embedding is None


# ---------------------------------------------------------------------------
# insert_chunk
# ---------------------------------------------------------------------------

class TestInsertChunk:
    def test_returns_chunk(self) -> None:
        chunk = make_chunk()
        row = make_row(chunk)
        client = mock_client([row])
        result = insert_chunk(chunk, client=client)
        assert isinstance(result, Chunk)
        assert result.id == chunk.id

    def test_calls_table_insert(self) -> None:
        chunk = make_chunk()
        row = make_row(chunk)
        client = mock_client([row])
        insert_chunk(chunk, client=client)
        client.table.assert_called_once_with("chunks")

    def test_propagates_supabase_error(self) -> None:
        chunk = make_chunk()
        client = MagicMock()
        client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB down")
        with pytest.raises(RuntimeError, match="DB down"):
            insert_chunk(chunk, client=client)


# ---------------------------------------------------------------------------
# insert_chunks
# ---------------------------------------------------------------------------

class TestInsertChunks:
    def test_bulk_insert_returns_list(self) -> None:
        chunks = [make_chunk(id=uuid4()), make_chunk(id=uuid4())]
        rows = [make_row(c) for c in chunks]
        client = mock_client(rows)
        results = insert_chunks(chunks, client=client)
        assert len(results) == 2
        assert all(isinstance(r, Chunk) for r in results)

    def test_empty_list_raises_value_error(self) -> None:
        client = MagicMock()
        with pytest.raises(ValueError, match="empty"):
            insert_chunks([], client=client)

    def test_propagates_supabase_error(self) -> None:
        chunks = [make_chunk()]
        client = MagicMock()
        client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("timeout")
        with pytest.raises(RuntimeError, match="timeout"):
            insert_chunks(chunks, client=client)


# ---------------------------------------------------------------------------
# get_chunk_by_id
# ---------------------------------------------------------------------------

class TestGetChunkById:
    def test_returns_chunk_when_found(self) -> None:
        chunk = make_chunk(created_at=FIXED_TS)
        row = make_row(chunk)
        client = mock_client([row])
        result = get_chunk_by_id(FIXED_ID, client=client)
        assert result is not None
        assert result.id == FIXED_ID

    def test_returns_none_when_not_found(self) -> None:
        client = mock_client([])
        result = get_chunk_by_id(uuid4(), client=client)
        assert result is None

    def test_propagates_supabase_error(self) -> None:
        client = MagicMock()
        (
            client.table.return_value
            .select.return_value
            .eq.return_value
            .limit.return_value
            .execute.side_effect
        ) = RuntimeError("network error")
        with pytest.raises(RuntimeError, match="network error"):
            get_chunk_by_id(FIXED_ID, client=client)


# ---------------------------------------------------------------------------
# Supabase client — config guard
# ---------------------------------------------------------------------------

class TestSupabaseClientGuard:
    def test_missing_url_raises_runtime_error(self) -> None:
        from app.config import Settings
        from app.rag.supabase_client import get_supabase

        settings_no_url = Settings(
            OPENAI_API_KEY="test",
            APP_PASSWORD="valid-password-123",
            JWT_SECRET="a" * 32,
            SUPABASE_URL=None,
            SUPABASE_SERVICE_ROLE_KEY="some-key",
        )
        # Clear the lru_cache so the patched settings take effect.
        get_supabase.cache_clear()
        with patch("app.rag.supabase_client.get_settings", return_value=settings_no_url):
            with pytest.raises(RuntimeError, match="SUPABASE_URL"):
                get_supabase()
        get_supabase.cache_clear()

    def test_missing_service_role_key_raises_runtime_error(self) -> None:
        from app.config import Settings
        from app.rag.supabase_client import get_supabase

        settings_no_key = Settings(
            OPENAI_API_KEY="test",
            APP_PASSWORD="valid-password-123",
            JWT_SECRET="a" * 32,
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY=None,
        )
        get_supabase.cache_clear()
        with patch("app.rag.supabase_client.get_settings", return_value=settings_no_key):
            with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
                get_supabase()
        get_supabase.cache_clear()
