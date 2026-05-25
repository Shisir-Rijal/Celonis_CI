"""Unit tests for app/ingestion/chunking/none_enriched.py.

Covers:
- Always returns exactly one Chunk
- Header format: "Company: X | Type: Y | Date: YYYY-MM-DD | Title: T"
- Title is omitted from header when metadata.title is None
- Original text is preserved in chunk content
- chunking_strategy is set to "none"
- Returned object is a valid Chunk instance with populated metadata
"""

from datetime import datetime, timezone

import pytest

from app.ingestion.chunking.none_enriched import chunk_none_enriched
from app.models.schemas import Chunk, ChunkMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_metadata(**overrides) -> ChunkMetadata:
    base = {
        "company": "Celonis",
        "source_type": "social",
        "source_origin": "owned",
        "date": datetime(2025, 3, 15, tzinfo=timezone.utc),
        "url": "https://linkedin.com/posts/example",
        "title": "New AI Features Launch",
        "language": "en",
        "topic": ["product"],
        "content_type": "text",
        "visual_type": None,
        "chunking_strategy": "none",
    }
    base.update(overrides)
    return ChunkMetadata(**base)


SAMPLE_TEXT = "Excited to announce our new AI features this quarter!"


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

class TestNoneEnrichedOutputShape:
    def test_returns_exactly_one_chunk(self):
        chunks = chunk_none_enriched(SAMPLE_TEXT, make_metadata())
        assert len(chunks) == 1

    def test_returns_chunk_instance(self):
        chunk = chunk_none_enriched(SAMPLE_TEXT, make_metadata())[0]
        assert isinstance(chunk, Chunk)

    def test_chunk_id_is_set(self):
        chunk = chunk_none_enriched(SAMPLE_TEXT, make_metadata())[0]
        assert chunk.id is not None

    def test_chunk_created_at_is_set(self):
        chunk = chunk_none_enriched(SAMPLE_TEXT, make_metadata())[0]
        assert chunk.created_at is not None


# ---------------------------------------------------------------------------
# Header format
# ---------------------------------------------------------------------------

class TestNoneEnrichedHeaderFormat:
    def test_header_contains_company(self):
        chunk = chunk_none_enriched(SAMPLE_TEXT, make_metadata())[0]
        assert "Company: Celonis" in chunk.content

    def test_header_contains_source_type(self):
        chunk = chunk_none_enriched(SAMPLE_TEXT, make_metadata())[0]
        assert "Type: social" in chunk.content

    def test_header_contains_date(self):
        chunk = chunk_none_enriched(SAMPLE_TEXT, make_metadata())[0]
        assert "Date: 2025-03-15" in chunk.content

    def test_header_contains_title(self):
        chunk = chunk_none_enriched(SAMPLE_TEXT, make_metadata())[0]
        assert "Title: New AI Features Launch" in chunk.content

    def test_header_omits_title_when_none(self):
        chunk = chunk_none_enriched(SAMPLE_TEXT, make_metadata(title=None))[0]
        assert "Title:" not in chunk.content

    def test_header_uses_pipe_separator(self):
        chunk = chunk_none_enriched(SAMPLE_TEXT, make_metadata())[0]
        header_line = chunk.content.split("\n")[0]
        assert " | " in header_line

    def test_header_comes_before_text(self):
        chunk = chunk_none_enriched(SAMPLE_TEXT, make_metadata())[0]
        header_end = chunk.content.index("\n\n")
        assert SAMPLE_TEXT in chunk.content[header_end:]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestNoneEnrichedMetadata:
    def test_chunking_strategy_is_none(self):
        chunk = chunk_none_enriched(SAMPLE_TEXT, make_metadata())[0]
        assert chunk.metadata.chunking_strategy == "none"

    def test_other_metadata_fields_are_preserved(self):
        meta = make_metadata()
        chunk = chunk_none_enriched(SAMPLE_TEXT, meta)[0]
        assert chunk.metadata.company == meta.company
        assert chunk.metadata.source_type == meta.source_type
        assert chunk.metadata.date == meta.date
