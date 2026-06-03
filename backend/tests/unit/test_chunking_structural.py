"""Unit tests for app/ingestion/chunking/structural.py.

Covers:
- Heading-based split produces expected number of chunks
- Short sections below min_tokens are merged
- No chunk exceeds max_tokens after windowed split
- Adjacent chunks share exactly overlap_tokens tokens at their boundary
- Each returned Chunk has valid id, created_at, and chunking_strategy="structural"
"""

from datetime import datetime, timezone

from app.ingestion.chunking.structural import _ENCODING, _count_tokens, chunk_structural
from app.models.schemas import Chunk, ChunkMetadata


def make_metadata() -> ChunkMetadata:
    return ChunkMetadata(
        company="Celonis",
        source_type="press_release",
        source_origin="owned",
        date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        url="https://example.com",
        title="Test Doc",
        language="en",
        topic=[],
        content_type="text",
        visual_type=None,
        chunking_strategy="structural",
    )


def _words(n: int) -> str:
    """Return roughly n tokens of filler text."""
    return ("word " * n).strip()


# Three sections each ~250 tokens — above min (200), below max (800)
FIXTURE_MD = f"""\
# Section One

{_words(250)}

## Section Two

{_words(250)}

### Section Three

{_words(250)}
"""


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

class TestOutputShape:
    def test_returns_list_of_chunk_instances(self):
        chunks = chunk_structural(FIXTURE_MD, make_metadata())
        assert isinstance(chunks, list)
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_ids_are_populated(self):
        chunks = chunk_structural(FIXTURE_MD, make_metadata())
        assert all(c.id is not None for c in chunks)

    def test_chunk_created_at_is_populated(self):
        chunks = chunk_structural(FIXTURE_MD, make_metadata())
        assert all(c.created_at is not None for c in chunks)

    def test_chunking_strategy_is_structural(self):
        chunks = chunk_structural(FIXTURE_MD, make_metadata())
        assert all(c.metadata.chunking_strategy == "structural" for c in chunks)

    def test_other_metadata_fields_are_preserved(self):
        meta = make_metadata()
        chunks = chunk_structural(FIXTURE_MD, meta)
        assert all(c.metadata.company == meta.company for c in chunks)
        assert all(c.metadata.source_type == meta.source_type for c in chunks)


# ---------------------------------------------------------------------------
# Heading split: fixture with 3 large sections → 3 chunks
# ---------------------------------------------------------------------------

class TestHeadingSplit:
    def test_three_sections_produce_three_chunks(self):
        # Each section is ~250 tokens → above min (200), so no merging
        chunks = chunk_structural(FIXTURE_MD, make_metadata())
        assert len(chunks) == 3

    def test_chunk_content_starts_with_heading(self):
        chunks = chunk_structural(FIXTURE_MD, make_metadata())
        assert chunks[0].content.startswith("# Section One")
        assert chunks[1].content.startswith("## Section Two")
        assert chunks[2].content.startswith("### Section Three")


# ---------------------------------------------------------------------------
# Min token bound: short sections are merged
# ---------------------------------------------------------------------------

class TestMinTokenBound:
    def test_short_sections_merge_into_one(self):
        # Two ~10-token sections; min_tokens=30 forces them to merge
        md = "# A\n\n" + _words(10) + "\n\n## B\n\n" + _words(10)
        chunks = chunk_structural(md, make_metadata(), min_tokens=30, max_tokens=800)
        assert len(chunks) == 1

    def test_merged_chunk_contains_both_headings(self):
        md = "# Alpha\n\n" + _words(10) + "\n\n## Beta\n\n" + _words(10)
        chunks = chunk_structural(md, make_metadata(), min_tokens=30, max_tokens=800)
        assert "# Alpha" in chunks[0].content
        assert "## Beta" in chunks[0].content


# ---------------------------------------------------------------------------
# Max token bound: oversized sections are split
# ---------------------------------------------------------------------------

class TestMaxTokenBound:
    def test_long_section_produces_multiple_chunks(self):
        md = "# Big Section\n\n" + _words(300)
        chunks = chunk_structural(md, make_metadata(), min_tokens=10, max_tokens=100)
        assert len(chunks) > 1

    def test_no_chunk_exceeds_max_tokens(self):
        md = "# Big Section\n\n" + _words(300)
        chunks = chunk_structural(md, make_metadata(), min_tokens=10, max_tokens=100)
        for c in chunks:
            assert _count_tokens(c.content) <= 100


# ---------------------------------------------------------------------------
# Overlap: adjacent chunks share tokens at their boundary
# ---------------------------------------------------------------------------

class TestOverlap:
    def test_adjacent_chunks_share_overlap_tokens(self):
        overlap = 20
        md = "# Section\n\n" + _words(300)
        chunks = chunk_structural(md, make_metadata(), min_tokens=10, max_tokens=100, overlap_tokens=overlap)
        assert len(chunks) >= 2
        tokens_first = _ENCODING.encode(chunks[0].content)
        tokens_second = _ENCODING.encode(chunks[1].content)
        assert tokens_first[-overlap:] == tokens_second[:overlap]
