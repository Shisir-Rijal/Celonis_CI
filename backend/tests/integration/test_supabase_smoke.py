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


# ---------------------------------------------------------------------------
# Pipeline integration — real Supabase, mocked embed_chunks
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPipelineIntegration:
    """End-to-end pipeline smoke tests.

    Writes real rows to the documents and chunks tables.
    embed_chunks is mocked so no OpenAI credits are consumed.

    Rows written here are real test data — safe to inspect in Supabase Studio
    and delete manually after if desired.
    """

    @pytest.mark.asyncio
    async def test_ingest_document_creates_document_and_chunk(
        self, supabase_client
    ) -> None:
        """ingest_document writes a document row + chunk row to Supabase."""
        from datetime import timezone
        from unittest.mock import AsyncMock, patch

        from app.ingestion.pipeline import ingest_document
        from app.models.schemas import Chunk, ChunkMetadata
        from app.rag.document_repository import get_document_by_hash, compute_content_hash
        from app.rag.repository import get_chunk_by_id

        unique_text = f"Integration smoke test — pipeline — {uuid4()}"
        meta = ChunkMetadata(
            company="Celonis",
            source_type="press_release",
            source_origin="owned",
            date=datetime(2025, 6, 1, tzinfo=timezone.utc),
            url=f"https://celonis.com/smoke-pipeline-{uuid4()}",
            title="Pipeline Smoke Test",
            language="en",
            topic=["test"],
            content_type="text",
            visual_type=None,
            chunking_strategy="structural",
        )
        test_chunk = Chunk(
            id=uuid4(),
            content=unique_text,
            metadata=meta,
            embedding=None,
            created_at=None,
            context_header="press_release | Celonis | 2025-06-01",
        )

        fake_vector = [0.0] * 1536

        async def fake_embed(chunks, **_):
            for c in chunks:
                c.embedding = fake_vector
            return chunks

        with patch("app.ingestion.pipeline.embed_chunks", side_effect=fake_embed):
            chunk_ids = await ingest_document(
                text=unique_text,
                metadata=meta,
                url=meta.url,
                source_type="press_release",
                company="Celonis",
                chunks=[test_chunk],
                db_client=supabase_client,
            )

        assert len(chunk_ids) == 1

        # Document row exists with status 'done'
        content_hash = compute_content_hash(unique_text)
        doc = get_document_by_hash(content_hash, client=supabase_client)
        assert doc is not None
        assert doc["ingestion_status"] == "done"

        # Chunk row exists and is linked back to the document
        from uuid import UUID
        saved_chunk = get_chunk_by_id(chunk_ids[0], client=supabase_client)
        assert saved_chunk is not None
        assert saved_chunk.document_id == UUID(doc["id"])
        assert saved_chunk.embedding == fake_vector

    @pytest.mark.asyncio
    async def test_ingest_duplicate_document_returns_existing_ids(
        self, supabase_client
    ) -> None:
        """Calling ingest_document twice with the same text returns the same chunk IDs."""
        from datetime import timezone
        from unittest.mock import AsyncMock, patch

        from app.ingestion.pipeline import ingest_document
        from app.models.schemas import Chunk, ChunkMetadata

        unique_text = f"Duplicate dedup test — {uuid4()}"
        meta = ChunkMetadata(
            company="Celonis",
            source_type="news",
            source_origin="earned",
            date=datetime(2025, 6, 1, tzinfo=timezone.utc),
            url=f"https://celonis.com/dedup-{uuid4()}",
            title="Dedup Test",
            language="en",
            topic=["test"],
            content_type="text",
            visual_type=None,
            chunking_strategy="none",
        )
        test_chunk = Chunk(
            id=uuid4(),
            content=unique_text,
            metadata=meta,
            embedding=None,
            created_at=None,
            context_header="news | Celonis | 2025-06-01",
        )

        async def fake_embed(chunks, **_):
            for c in chunks:
                c.embedding = [0.0] * 1536
            return chunks

        with patch("app.ingestion.pipeline.embed_chunks", side_effect=fake_embed):
            first_ids = await ingest_document(
                text=unique_text,
                metadata=meta,
                url=meta.url,
                source_type="news",
                company="Celonis",
                chunks=[test_chunk],
                db_client=supabase_client,
            )

        # Second call — embed_chunks must NOT be called (deduplication)
        with patch("app.ingestion.pipeline.embed_chunks", new=AsyncMock()) as mock_embed:
            second_ids = await ingest_document(
                text=unique_text,
                metadata=meta,
                url=meta.url,
                source_type="news",
                company="Celonis",
                chunks=[test_chunk],
                db_client=supabase_client,
            )
            mock_embed.assert_not_awaited()

        assert first_ids == second_ids
