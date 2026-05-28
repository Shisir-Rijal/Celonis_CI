"""Unit tests for app.ingestion.pipeline.ingest_document.

Everything is mocked — no real Supabase, no real OpenAI.
Tests cover: deduplication short-circuit, happy path, fallback chunking,
document_id stamping, and the error-handling path.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.models.schemas import Chunk, ChunkMetadata
from app.ingestion.pipeline import ingest_document

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_TS = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
FAKE_VECTOR = [0.1] * 1536

DOC_ID = uuid4()
CHUNK_ID_1 = uuid4()
CHUNK_ID_2 = uuid4()


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


def make_chunk(*, context_header: str = "header | Celonis | 2025-01-15", **overrides) -> Chunk:
    defaults = dict(
        id=uuid4(),
        content="Some content.",
        metadata=make_metadata(),
        embedding=None,
        created_at=None,
        context_header=context_header,
    )
    defaults.update(overrides)
    return Chunk(**defaults)


def _doc_row(doc_id: UUID = DOC_ID, status: str = "done") -> dict:
    return {"id": str(doc_id), "ingestion_status": status}


# ---------------------------------------------------------------------------
# Patch targets — all imports are resolved relative to the pipeline module
# ---------------------------------------------------------------------------

BASE = "app.ingestion.pipeline"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    @pytest.mark.asyncio
    async def test_existing_done_document_returns_existing_chunk_ids(self) -> None:
        """If the document hash is already 'done', return existing IDs immediately."""
        existing_ids = [CHUNK_ID_1, CHUNK_ID_2]

        with (
            patch(f"{BASE}.get_document_by_hash", return_value=_doc_row(DOC_ID, "done")),
            patch(f"{BASE}.get_chunk_ids_by_document", return_value=existing_ids) as mock_get,
            patch(f"{BASE}.create_document") as mock_create,
            patch(f"{BASE}.embed_chunks") as mock_embed,
        ):
            result = await ingest_document(
                text="hello",
                metadata=make_metadata(),
                url="https://example.com",
                source_type="news",
                company="celonis",
            )

        assert result == existing_ids
        mock_create.assert_not_called()
        mock_embed.assert_not_called()
        mock_get.assert_called_once_with(DOC_ID, client=None)

    @pytest.mark.asyncio
    async def test_pending_document_reuses_existing_id(self) -> None:
        """A document in 'pending' status re-uses the existing document_id.

        create_document must NOT be called — the DB has UNIQUE(content_hash)
        so inserting again would raise a Unique-Violation. Instead the pipeline
        resets the status to 'pending' and continues with the existing record.
        """
        chunk = make_chunk()
        with (
            patch(f"{BASE}.get_document_by_hash", return_value=_doc_row(DOC_ID, "pending")),
            patch(f"{BASE}.create_document") as mock_create,
            patch(f"{BASE}.update_document_status"),
            patch(f"{BASE}.embed_chunks", new=AsyncMock(return_value=[chunk])),
            patch(f"{BASE}.insert_chunks", return_value=[chunk]),
        ):
            result = await ingest_document(
                text="hello",
                metadata=make_metadata(),
                url="https://example.com",
                source_type="news",
                company="celonis",
                chunks=[chunk],
            )
        assert result == [chunk.id]
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_document_reuses_existing_id(self) -> None:
        """A document in 'error' status is retried without calling create_document."""
        chunk = make_chunk()
        with (
            patch(f"{BASE}.get_document_by_hash", return_value=_doc_row(DOC_ID, "error")),
            patch(f"{BASE}.create_document") as mock_create,
            patch(f"{BASE}.update_document_status"),
            patch(f"{BASE}.embed_chunks", new=AsyncMock(return_value=[chunk])),
            patch(f"{BASE}.insert_chunks", return_value=[chunk]),
        ):
            result = await ingest_document(
                text="hello",
                metadata=make_metadata(),
                url="https://example.com",
                source_type="news",
                company="celonis",
                chunks=[chunk],
            )
        assert result == [chunk.id]
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_document_goes_through_full_pipeline(self) -> None:
        """A document not in the DB creates a record and embeds."""
        chunk = make_chunk()
        with (
            patch(f"{BASE}.get_document_by_hash", return_value=None),
            patch(f"{BASE}.create_document", return_value=_doc_row(DOC_ID)),
            patch(f"{BASE}.update_document_status") as mock_status,
            patch(f"{BASE}.embed_chunks", new=AsyncMock(return_value=[chunk])),
            patch(f"{BASE}.insert_chunks", return_value=[chunk]),
        ):
            result = await ingest_document(
                text="hello",
                metadata=make_metadata(),
                url="https://example.com",
                source_type="news",
                company="celonis",
                chunks=[chunk],
            )
        assert result == [chunk.id]
        mock_status.assert_called_once_with(DOC_ID, "done", client=None)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    @pytest.mark.asyncio
    async def test_returns_chunk_uuids(self) -> None:
        """ingest_document returns a list of UUIDs matching the ingested chunks."""
        chunks = [make_chunk(), make_chunk()]
        embedded = chunks[:]

        with (
            patch(f"{BASE}.get_document_by_hash", return_value=None),
            patch(f"{BASE}.create_document", return_value=_doc_row(DOC_ID)),
            patch(f"{BASE}.update_document_status"),
            patch(f"{BASE}.embed_chunks", new=AsyncMock(return_value=embedded)),
            patch(f"{BASE}.insert_chunks", return_value=embedded),
        ):
            result = await ingest_document(
                text="text",
                metadata=make_metadata(),
                url="https://example.com",
                source_type="news",
                company="celonis",
                chunks=chunks,
            )
        assert len(result) == 2
        assert all(isinstance(uid, UUID) for uid in result)

    @pytest.mark.asyncio
    async def test_document_id_stamped_on_chunks(self) -> None:
        """Every chunk receives the document_id FK before embedding."""
        chunk = make_chunk()
        captured_chunks = []

        async def capture(chunks_arg, **_):
            captured_chunks.extend(chunks_arg)
            return chunks_arg

        with (
            patch(f"{BASE}.get_document_by_hash", return_value=None),
            patch(f"{BASE}.create_document", return_value=_doc_row(DOC_ID)),
            patch(f"{BASE}.update_document_status"),
            patch(f"{BASE}.embed_chunks", side_effect=capture),
            patch(f"{BASE}.insert_chunks", return_value=[chunk]),
        ):
            await ingest_document(
                text="text",
                metadata=make_metadata(),
                url="https://example.com",
                source_type="news",
                company="celonis",
                chunks=[chunk],
            )

        assert captured_chunks[0].document_id == DOC_ID

    @pytest.mark.asyncio
    async def test_status_set_to_done_on_success(self) -> None:
        """On the happy path, update_document_status is called with 'done'."""
        chunk = make_chunk()
        with (
            patch(f"{BASE}.get_document_by_hash", return_value=None),
            patch(f"{BASE}.create_document", return_value=_doc_row(DOC_ID)),
            patch(f"{BASE}.update_document_status") as mock_status,
            patch(f"{BASE}.embed_chunks", new=AsyncMock(return_value=[chunk])),
            patch(f"{BASE}.insert_chunks", return_value=[chunk]),
        ):
            await ingest_document(
                text="text",
                metadata=make_metadata(),
                url="https://example.com",
                source_type="news",
                company="celonis",
                chunks=[chunk],
            )
        mock_status.assert_called_once_with(DOC_ID, "done", client=None)


# ---------------------------------------------------------------------------
# Fallback chunking (chunks=None)
# ---------------------------------------------------------------------------

class TestFallbackChunking:
    @pytest.mark.asyncio
    async def test_fallback_creates_one_chunk(self) -> None:
        """When chunks=None, the pipeline creates exactly one chunk from the text."""
        captured: list[Chunk] = []

        async def capture(chunks_arg, **_):
            captured.extend(chunks_arg)
            return chunks_arg

        fake_chunk_out = make_chunk()
        with (
            patch(f"{BASE}.get_document_by_hash", return_value=None),
            patch(f"{BASE}.create_document", return_value=_doc_row(DOC_ID)),
            patch(f"{BASE}.update_document_status"),
            patch(f"{BASE}.embed_chunks", side_effect=capture),
            patch(f"{BASE}.insert_chunks", return_value=[fake_chunk_out]),
        ):
            await ingest_document(
                text="the full document text",
                metadata=make_metadata(),
                url="https://example.com",
                source_type="news",
                company="celonis",
                # chunks deliberately omitted → fallback path
            )

        assert len(captured) == 1
        assert captured[0].content == "the full document text"

    @pytest.mark.asyncio
    async def test_fallback_chunk_has_non_empty_header(self) -> None:
        """The fallback chunk must have a context_header (or embed_chunks would raise)."""
        captured: list[Chunk] = []

        async def capture(chunks_arg, **_):
            captured.extend(chunks_arg)
            return chunks_arg

        with (
            patch(f"{BASE}.get_document_by_hash", return_value=None),
            patch(f"{BASE}.create_document", return_value=_doc_row(DOC_ID)),
            patch(f"{BASE}.update_document_status"),
            patch(f"{BASE}.embed_chunks", side_effect=capture),
            patch(f"{BASE}.insert_chunks", return_value=[make_chunk()]),
        ):
            await ingest_document(
                text="some text",
                metadata=make_metadata(),
                url="https://example.com",
                source_type="news",
                company="celonis",
            )

        assert captured[0].context_header != ""


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_embed_failure_sets_status_to_error(self) -> None:
        """If embed_chunks raises, status is set to 'error' with the message."""
        chunk = make_chunk()
        with (
            patch(f"{BASE}.get_document_by_hash", return_value=None),
            patch(f"{BASE}.create_document", return_value=_doc_row(DOC_ID)),
            patch(f"{BASE}.update_document_status") as mock_status,
            patch(f"{BASE}.embed_chunks", new=AsyncMock(side_effect=RuntimeError("API down"))),
        ):
            with pytest.raises(RuntimeError, match="API down"):
                await ingest_document(
                    text="text",
                    metadata=make_metadata(),
                    url="https://example.com",
                    source_type="news",
                    company="celonis",
                    chunks=[chunk],
                )

        mock_status.assert_called_once()
        call_args = mock_status.call_args
        assert call_args[0][1] == "error"
        assert "API down" in call_args[1].get("error_detail", "") or "API down" in str(call_args)

    @pytest.mark.asyncio
    async def test_embed_failure_re_raises(self) -> None:
        """The original exception is re-raised after setting document status."""
        chunk = make_chunk()
        with (
            patch(f"{BASE}.get_document_by_hash", return_value=None),
            patch(f"{BASE}.create_document", return_value=_doc_row(DOC_ID)),
            patch(f"{BASE}.update_document_status"),
            patch(f"{BASE}.embed_chunks", new=AsyncMock(side_effect=ValueError("bad header"))),
        ):
            with pytest.raises(ValueError, match="bad header"):
                await ingest_document(
                    text="text",
                    metadata=make_metadata(),
                    url="https://example.com",
                    source_type="news",
                    company="celonis",
                    chunks=[chunk],
                )

    @pytest.mark.asyncio
    async def test_insert_failure_sets_status_to_error(self) -> None:
        """If insert_chunks raises, status is still set to 'error'."""
        chunk = make_chunk()
        with (
            patch(f"{BASE}.get_document_by_hash", return_value=None),
            patch(f"{BASE}.create_document", return_value=_doc_row(DOC_ID)),
            patch(f"{BASE}.update_document_status") as mock_status,
            patch(f"{BASE}.embed_chunks", new=AsyncMock(return_value=[chunk])),
            patch(f"{BASE}.insert_chunks", side_effect=RuntimeError("DB timeout")),
        ):
            with pytest.raises(RuntimeError, match="DB timeout"):
                await ingest_document(
                    text="text",
                    metadata=make_metadata(),
                    url="https://example.com",
                    source_type="news",
                    company="celonis",
                    chunks=[chunk],
                )

        call_args = mock_status.call_args
        assert call_args[0][1] == "error"
