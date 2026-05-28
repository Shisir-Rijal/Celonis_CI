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


# ---------------------------------------------------------------------------
# Hybrid retrieval integration — real Supabase, mocked embed_text
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def retrieval_fixture_chunk(supabase_client):
    """Insert a chunk with a known embedding vector for retrieval smoke tests.

    Uses insert_chunk directly (no pipeline) so the embedding vector is
    controlled — the same vector is used as the query vector in vector search,
    guaranteeing the chunk ranks first. No OpenAI credits consumed.

    The chunk stays in the DB after the test run (safe to delete manually).
    """
    from app.models.schemas import Chunk, ChunkMetadata
    from app.rag.repository import insert_chunk

    KNOWN_VECTOR = [0.1] * 1536

    meta = ChunkMetadata(
        company="CelonisSearchTest",
        source_type="press_release",
        source_origin="owned",
        date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        url=f"https://celonis.com/retrieval-smoke-{uuid4()}",
        title="Retrieval Smoke Test",
        language="en",
        topic=["process_mining", "smoke_test"],
        content_type="text",
        visual_type=None,
        chunking_strategy="structural",
    )
    chunk = Chunk(
        id=uuid4(),
        content="Celonis process mining software quarterly results announcement smoke test",
        metadata=meta,
        embedding=KNOWN_VECTOR,
        created_at=None,
        context_header="press_release | CelonisSearchTest | 2025-06-01",
        document_id=None,
    )
    saved = insert_chunk(chunk, client=supabase_client)
    return saved


@pytest.mark.integration
class TestHybridRetrievalIntegration:
    """Smoke tests for the hybrid retrieval RPC functions and search_chunks().

    Uses a fixture chunk with a known embedding vector so no OpenAI call is
    needed. embed_text is mocked to return the same known vector, ensuring
    the fixture chunk ranks first in vector results.
    """

    KNOWN_VECTOR = [0.1] * 1536
    SEARCH_COMPANY = "CelonisSearchTest"

    def test_vector_rpc_finds_fixture_chunk(
        self, supabase_client, retrieval_fixture_chunk
    ) -> None:
        """match_chunks_vector RPC returns our fixture chunk when queried
        with its exact embedding vector."""
        resp = supabase_client.rpc(
            "match_chunks_vector",
            {
                "query_embedding": self.KNOWN_VECTOR,
                "match_count": 10,
                "filter": {"company": self.SEARCH_COMPANY},
            },
        ).execute()
        ids = [r["id"] for r in resp.data]
        assert str(retrieval_fixture_chunk.id) in ids

    def test_bm25_rpc_finds_fixture_chunk(
        self, supabase_client, retrieval_fixture_chunk
    ) -> None:
        """match_chunks_bm25 RPC finds our fixture chunk by keyword."""
        resp = supabase_client.rpc(
            "match_chunks_bm25",
            {
                "query_text": "celonis process mining quarterly",
                "match_count": 10,
                "filter": {"company": self.SEARCH_COMPANY},
            },
        ).execute()
        ids = [r["id"] for r in resp.data]
        assert str(retrieval_fixture_chunk.id) in ids

    def test_metadata_filter_excludes_wrong_company(
        self, supabase_client, retrieval_fixture_chunk
    ) -> None:
        """Filtering by a different company returns no results for our chunk."""
        resp = supabase_client.rpc(
            "match_chunks_vector",
            {
                "query_embedding": self.KNOWN_VECTOR,
                "match_count": 10,
                "filter": {"company": "SAP"},
            },
        ).execute()
        ids = [r["id"] for r in resp.data]
        assert str(retrieval_fixture_chunk.id) not in ids

    @pytest.mark.asyncio
    async def test_search_chunks_no_duplicates(
        self, supabase_client, retrieval_fixture_chunk
    ) -> None:
        """search_chunks() returns no duplicate chunk IDs."""
        from unittest.mock import AsyncMock, patch
        from app.rag.retrieval import search_chunks

        with patch("app.rag.retrieval.embed_text", new=AsyncMock(return_value=self.KNOWN_VECTOR)):
            results = await search_chunks(
                "celonis process mining",
                db_client=supabase_client,
            )

        ids = [str(c.id) for c in results]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_search_chunks_relevance_score_set(
        self, supabase_client, retrieval_fixture_chunk
    ) -> None:
        """Every chunk returned by search_chunks() has relevance_score set."""
        from unittest.mock import AsyncMock, patch
        from app.rag.retrieval import search_chunks

        with patch("app.rag.retrieval.embed_text", new=AsyncMock(return_value=self.KNOWN_VECTOR)):
            results = await search_chunks(
                "celonis process mining",
                db_client=supabase_client,
            )

        assert len(results) > 0
        assert all(c.relevance_score is not None for c in results)

    @pytest.mark.asyncio
    async def test_search_chunks_company_filter_narrows_results(
        self, supabase_client, retrieval_fixture_chunk
    ) -> None:
        """Passing a wrong company filter excludes our fixture chunk."""
        from unittest.mock import AsyncMock, patch
        from app.models.schemas import ChunkFilter
        from app.rag.retrieval import search_chunks

        wrong_filter = ChunkFilter(company="SAP")
        with patch("app.rag.retrieval.embed_text", new=AsyncMock(return_value=self.KNOWN_VECTOR)):
            results = await search_chunks(
                "process mining",
                wrong_filter,
                db_client=supabase_client,
            )

        ids = [str(c.id) for c in results]
        assert str(retrieval_fixture_chunk.id) not in ids

    @pytest.mark.asyncio
    async def test_hybrid_result_contains_fixture_chunk(
        self, supabase_client, retrieval_fixture_chunk
    ) -> None:
        """The fixture chunk appears in hybrid results when queried correctly."""
        from unittest.mock import AsyncMock, patch
        from app.models.schemas import ChunkFilter
        from app.rag.retrieval import search_chunks

        f = ChunkFilter(company=self.SEARCH_COMPANY)
        with patch("app.rag.retrieval.embed_text", new=AsyncMock(return_value=self.KNOWN_VECTOR)):
            results = await search_chunks(
                "celonis process mining quarterly",
                f,
                k=10,
                db_client=supabase_client,
            )

        ids = [str(c.id) for c in results]
        assert str(retrieval_fixture_chunk.id) in ids

@pytest.mark.integration
class TestConversationMemory:
    """Smoke tests for conversation memory repository.

    All inserted rows are deleted after each test so repeated runs
    stay idempotent.
    """

    def test_get_or_create_is_idempotent(self, supabase_client) -> None:
        """Calling get_or_create_conversation twice with the same session_id
        returns the same id both times."""
        from uuid import UUID

        from app.rag.conversation_repository import get_or_create_conversation

        session_id = uuid4()
        try:
            row1 = get_or_create_conversation(session_id, client=supabase_client)
            row2 = get_or_create_conversation(session_id, client=supabase_client)
            assert row1["id"] == row2["id"]
        finally:
            supabase_client.table("conversations").delete().eq(
                "session_id", str(session_id)
            ).execute()

    def test_append_and_retrieve_turns(self, supabase_client) -> None:
        """Append 2 turns, get_recent_turns(limit=1) returns only the most recent."""
        from uuid import UUID

        from app.models.schemas import Source
        from app.rag.conversation_repository import (
            append_turn,
            get_or_create_conversation,
            get_recent_turns,
        )

        session_id = uuid4()
        sources = [
            Source(url="https://celonis.com", title="Smoke test", relevance_score=0.9)
        ]

        try:
            conversation = get_or_create_conversation(
                session_id, client=supabase_client
            )
            conversation_id = UUID(conversation["id"])

            append_turn(
                conversation_id=conversation_id,
                query="First question",
                answer="First answer",
                sources=sources,
                derivation="test",
                turn_number=1,
                client=supabase_client,
            )
            append_turn(
                conversation_id=conversation_id,
                query="Second question",
                answer="Second answer",
                sources=sources,
                derivation="test",
                turn_number=2,
                client=supabase_client,
            )

            # limit=1 → only the most recent DB row → 2 ConversationTurn objects
            turns = get_recent_turns(
                conversation_id, limit=1, client=supabase_client
            )
            assert len(turns) == 2  # 1 DB row = user turn + assistant turn
            assert turns[0].role == "user"
            assert turns[0].content == "Second question"
            assert turns[1].role == "assistant"
            assert turns[1].content == "Second answer"

        finally:
            supabase_client.table("conversations").delete().eq(
                "session_id", str(session_id)
            ).execute()
