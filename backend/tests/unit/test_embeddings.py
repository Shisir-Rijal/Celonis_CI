"""Unit tests for app.rag.embeddings.

All tests mock the OpenAI client — no real API calls, no DB writes.
The mock's embed() method is an AsyncMock so we can await it normally.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.schemas import Chunk, ChunkMetadata
from app.rag.embeddings import BATCH_SIZE, embed_chunks, embed_text

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

FIXED_TS = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
FAKE_VECTOR = [0.1] * 1536


def make_metadata(**overrides) -> ChunkMetadata:
    defaults = dict(
        company="Celonis",
        source_type="press_release",
        source_origin="owned",
        date=FIXED_TS,
        url="https://celonis.com/example",
        title="Example",
        language="en",
        topic=["test"],
        content_type="text",
        visual_type=None,
        chunking_strategy="structural",
    )
    defaults.update(overrides)
    return ChunkMetadata(**defaults)


def make_chunk(*, context_header: str = "press_release | Celonis | 2025-01-15", **overrides) -> Chunk:
    defaults = dict(
        id=uuid4(),
        content="Celonis announced something important.",
        metadata=make_metadata(),
        embedding=None,
        created_at=None,
        context_header=context_header,
    )
    defaults.update(overrides)
    return Chunk(**defaults)


def mock_openai_client(vectors: list[list[float]]) -> MagicMock:
    """Return a fake OpenAI client whose embed() is an AsyncMock."""
    client = MagicMock()
    client.embed = AsyncMock(return_value=vectors)
    return client


# ---------------------------------------------------------------------------
# embed_text
# ---------------------------------------------------------------------------

class TestEmbedText:
    @pytest.mark.asyncio
    async def test_returns_vector(self) -> None:
        """embed_text returns the first (and only) vector from the batch."""
        fake_client = mock_openai_client([FAKE_VECTOR])
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            result = await embed_text("hello world")
        assert result == FAKE_VECTOR

    @pytest.mark.asyncio
    async def test_calls_embed_with_single_item_list(self) -> None:
        """embed_text wraps the string in a list before calling client.embed."""
        fake_client = mock_openai_client([FAKE_VECTOR])
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            await embed_text("test query")
        fake_client.embed.assert_awaited_once_with(["test query"])

    @pytest.mark.asyncio
    async def test_propagates_client_error(self) -> None:
        """If client.embed raises, the error is propagated unchanged."""
        fake_client = MagicMock()
        fake_client.embed = AsyncMock(side_effect=RuntimeError("API down"))
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            with pytest.raises(RuntimeError, match="API down"):
                await embed_text("boom")


# ---------------------------------------------------------------------------
# embed_chunks — happy path
# ---------------------------------------------------------------------------

class TestEmbedChunksHappyPath:
    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self) -> None:
        """embed_chunks([]) is a no-op — no API call, returns empty list."""
        fake_client = mock_openai_client([])
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            result = await embed_chunks([])
        assert result == []
        fake_client.embed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_single_chunk_embedding_set(self) -> None:
        """embed_chunks sets chunk.embedding on the chunk in place."""
        chunk = make_chunk()
        fake_client = mock_openai_client([FAKE_VECTOR])
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            result = await embed_chunks([chunk])
        assert result[0].embedding == FAKE_VECTOR

    @pytest.mark.asyncio
    async def test_returns_same_list_object(self) -> None:
        """embed_chunks mutates and returns the original list, not a copy."""
        chunks = [make_chunk(), make_chunk()]
        fake_client = mock_openai_client([FAKE_VECTOR, FAKE_VECTOR])
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            result = await embed_chunks(chunks)
        assert result is chunks

    @pytest.mark.asyncio
    async def test_text_sent_to_api_includes_header_and_content(self) -> None:
        """The text passed to embed() is 'context_header\\n\\ncontent'."""
        chunk = make_chunk(context_header="My Header", content="My Content")
        fake_client = mock_openai_client([FAKE_VECTOR])
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            await embed_chunks([chunk])
        call_args = fake_client.embed.call_args[0][0]  # positional arg 0
        assert call_args == ["My Header\n\nMy Content"]

    @pytest.mark.asyncio
    async def test_multiple_chunks_all_embeddings_set(self) -> None:
        """Every chunk in a list gets its embedding set correctly."""
        chunks = [make_chunk() for _ in range(3)]
        vectors = [[float(i)] * 1536 for i in range(3)]
        fake_client = mock_openai_client(vectors)
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            result = await embed_chunks(chunks)
        for i, chunk in enumerate(result):
            assert chunk.embedding == vectors[i]


# ---------------------------------------------------------------------------
# embed_chunks — batching
# ---------------------------------------------------------------------------

class TestEmbedChunksBatching:
    @pytest.mark.asyncio
    async def test_single_batch_when_below_batch_size(self) -> None:
        """Fewer chunks than BATCH_SIZE → exactly one API call."""
        chunks = [make_chunk() for _ in range(5)]
        fake_client = mock_openai_client([FAKE_VECTOR] * 5)
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            await embed_chunks(chunks)
        assert fake_client.embed.await_count == 1

    @pytest.mark.asyncio
    async def test_two_batches_when_over_batch_size(self) -> None:
        """BATCH_SIZE + 1 chunks → exactly two API calls."""
        n = BATCH_SIZE + 1
        chunks = [make_chunk() for _ in range(n)]

        # embed() returns different-sized lists per call: BATCH_SIZE then 1
        async def side_effect(texts):  # noqa: ANN001
            return [FAKE_VECTOR] * len(texts)

        fake_client = MagicMock()
        fake_client.embed = AsyncMock(side_effect=side_effect)
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            result = await embed_chunks(chunks)
        assert fake_client.embed.await_count == 2
        assert all(c.embedding == FAKE_VECTOR for c in result)

    @pytest.mark.asyncio
    async def test_exact_batch_size_is_one_call(self) -> None:
        """Exactly BATCH_SIZE chunks → one API call."""
        chunks = [make_chunk() for _ in range(BATCH_SIZE)]
        fake_client = MagicMock()
        fake_client.embed = AsyncMock(return_value=[FAKE_VECTOR] * BATCH_SIZE)
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            await embed_chunks(chunks)
        assert fake_client.embed.await_count == 1


# ---------------------------------------------------------------------------
# embed_chunks — missing context_header (unhappy path)
# ---------------------------------------------------------------------------

class TestEmbedChunksMissingHeader:
    @pytest.mark.asyncio
    async def test_raises_value_error_when_header_missing(self) -> None:
        """A chunk with an empty context_header triggers ValueError immediately."""
        bad_chunk = make_chunk(context_header="")
        fake_client = mock_openai_client([])
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            with pytest.raises(ValueError, match="context_header"):
                await embed_chunks([bad_chunk])
        # No API call should have been made.
        fake_client.embed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_error_message_includes_missing_indices(self) -> None:
        """The ValueError names the indices of the offending chunks."""
        chunks = [
            make_chunk(context_header="ok"),
            make_chunk(context_header=""),   # index 1 — missing
            make_chunk(context_header="ok"),
            make_chunk(context_header=""),   # index 3 — missing
        ]
        with patch("app.rag.embeddings.get_openai_client", return_value=MagicMock()):
            with pytest.raises(ValueError) as exc_info:
                await embed_chunks(chunks)
        msg = str(exc_info.value)
        assert "1" in msg
        assert "3" in msg

    @pytest.mark.asyncio
    async def test_all_missing_headers_reported(self) -> None:
        """When all chunks are missing headers, the count is reported correctly."""
        chunks = [make_chunk(context_header="") for _ in range(3)]
        with patch("app.rag.embeddings.get_openai_client", return_value=MagicMock()):
            with pytest.raises(ValueError, match="3 chunk"):
                await embed_chunks(chunks)

    @pytest.mark.asyncio
    async def test_api_not_called_on_header_error(self) -> None:
        """embed() is never awaited when a header validation fails."""
        fake_client = mock_openai_client([])
        bad_chunks = [make_chunk(context_header="")]
        with patch("app.rag.embeddings.get_openai_client", return_value=fake_client):
            with pytest.raises(ValueError):
                await embed_chunks(bad_chunks)
        fake_client.embed.assert_not_awaited()
