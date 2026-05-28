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