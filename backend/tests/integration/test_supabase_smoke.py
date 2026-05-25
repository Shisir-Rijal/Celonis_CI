"""Integration smoke test for Supabase RAG store.

Requires a real Supabase project with migration 001_chunks.sql applied.
Reads credentials from SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.

Run explicitly:
    uv run pytest backend/tests/integration/test_supabase_smoke.py -v -m integration

Not included in the default test run (marked @pytest.mark.integration).
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

# Guard: skip entire module if credentials are not present.
# This keeps the default `pytest` run clean even without a Supabase project.
pytest.importorskip("supabase")


@pytest.fixture(scope="module")
def supabase_client():
    """Return the shared Supabase client.

    Skips the test module if SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY are
    not set — so CI without Supabase credentials simply skips rather than
    failing.
    """
    from app.config import get_settings
    from app.rag.supabase_client import get_supabase

    try:
        settings = get_settings()
    except Exception:
        pytest.skip("Could not load settings.")

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        pytest.skip(
            "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set — skipping Supabase integration."
        )

    get_supabase.cache_clear()
    return get_supabase()


@pytest.mark.integration
class TestSupabaseRoundTrip:
    def test_insert_and_fetch_chunk(self, supabase_client) -> None:
        """Insert a Chunk, read it back, verify field equality."""
        from app.models.schemas import Chunk, ChunkMetadata
        from app.rag.repository import get_chunk_by_id, insert_chunk

        chunk_id = uuid4()
        meta = ChunkMetadata(
            company="Celonis",
            source_type="press_release",
            source_origin="owned",
            date=datetime(2025, 6, 1, tzinfo=timezone.utc),
            url="https://celonis.com/smoke-test",
            title="Smoke Test Chunk",
            language="en",
            topic=["test"],
            content_type="text",
            visual_type=None,
            chunking_strategy="structural",
        )
        chunk = Chunk(
            id=chunk_id,
            content="Integration smoke test — safe to delete.",
            metadata=meta,
            embedding=None,
            created_at=None,
        )

        saved = insert_chunk(chunk, client=supabase_client)

        assert saved.id == chunk_id
        assert saved.content == chunk.content
        assert saved.metadata.company == "Celonis"
        assert saved.metadata.source_origin == "owned"
        # created_at must be set by the DB default after insert.
        assert saved.created_at is not None

        fetched = get_chunk_by_id(chunk_id, client=supabase_client)
        assert fetched is not None
        assert fetched.id == chunk_id
        assert fetched.content == chunk.content
        assert fetched.metadata.topic == ["test"]

    def test_client_is_reused(self, supabase_client) -> None:
        """get_supabase() returns the same instance on repeated calls."""
        from app.rag.supabase_client import get_supabase

        client_a = get_supabase()
        client_b = get_supabase()
        assert client_a is client_b

    def test_get_missing_chunk_returns_none(self, supabase_client) -> None:
        """Fetching a non-existent UUID returns None, not an exception."""
        from app.rag.repository import get_chunk_by_id

        result = get_chunk_by_id(uuid4(), client=supabase_client)
        assert result is None
