"""Unit tests for app.rag.retrieval.

All tests are fully mocked — no Supabase, no OpenAI.
The integration smoke test (test_supabase_smoke.py) covers the real DB path.

Test classes:
  TestBuildRpcFilter    — ChunkFilter → JSONB dict serialisation
  TestRrfMerge          — RRF scoring with synthetic ranked lists
  TestApplyTopicFilter  — in-Python topic post-filter
  TestRowToChunk        — RPC row → Chunk deserialisation (incl. pgvector string)
  TestSearchChunks      — search_chunks() end-to-end with mocked searches
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.schemas import Chunk, ChunkFilter, ChunkMetadata
from app.rag.retrieval import (
    _apply_topic_filter,
    _build_rpc_filter,
    _row_to_chunk,
    _rrf_merge,
    search_chunks,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

FIXED_TS = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
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
        topic=["product", "announcement"],
        content_type="text",
        visual_type=None,
        chunking_strategy="structural",
    )
    defaults.update(overrides)
    return ChunkMetadata(**defaults)


def make_rpc_row(chunk_id: str | None = None, **overrides) -> dict:
    """Simulate a row as returned by a Supabase RPC call."""
    cid = chunk_id or str(uuid4())
    defaults = dict(
        id=cid,
        content="Celonis announced something.",
        metadata=make_metadata().model_dump(mode="json"),
        context_header="press_release | Celonis | 2025-06-01",
        document_id=str(uuid4()),
        embedding=None,
        created_at=FIXED_TS.isoformat(),
    )
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# _build_rpc_filter
# ---------------------------------------------------------------------------

class TestBuildRpcFilter:
    def test_empty_filter_returns_empty_dict(self) -> None:
        result = _build_rpc_filter(ChunkFilter())
        assert result == {}

    def test_company_included_when_set(self) -> None:
        result = _build_rpc_filter(ChunkFilter(company="Celonis"))
        assert result["company"] == "Celonis"

    def test_none_fields_omitted(self) -> None:
        result = _build_rpc_filter(ChunkFilter(company="Celonis", source_type=None))
        assert "source_type" not in result

    def test_all_fields_serialised(self) -> None:
        f = ChunkFilter(
            company="Celonis",
            source_type="news",
            source_origin="owned",
            date_from=FIXED_TS,
            date_to=FIXED_TS,
        )
        result = _build_rpc_filter(f)
        assert result["company"] == "Celonis"
        assert result["source_type"] == "news"
        assert result["source_origin"] == "owned"
        assert "date_from" in result
        assert "date_to" in result

    def test_datetime_serialised_as_string(self) -> None:
        f = ChunkFilter(date_from=FIXED_TS)
        result = _build_rpc_filter(f)
        assert isinstance(result["date_from"], str)
        assert "2025" in result["date_from"]

    def test_topic_not_included_in_rpc_filter(self) -> None:
        """topic is applied in Python after retrieval — not pushed to Postgres."""
        result = _build_rpc_filter(ChunkFilter(topic=["product"]))
        assert "topic" not in result


# ---------------------------------------------------------------------------
# _rrf_merge
# ---------------------------------------------------------------------------

class TestRrfMerge:
    def test_single_list_scores_correctly(self) -> None:
        """With only vector results, score = 1/(60+rank)."""
        rows = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        ranked = _rrf_merge(rows, [])
        # rank 1 → 1/61, rank 2 → 1/62, rank 3 → 1/63
        assert ranked[0][0] == "a"
        assert abs(ranked[0][1] - 1 / 61) < 1e-9
        assert abs(ranked[1][1] - 1 / 62) < 1e-9

    def test_chunk_in_both_lists_scores_higher(self) -> None:
        """A chunk appearing in both lists accumulates scores from both."""
        shared_id = "shared"
        vector_rows = [{"id": shared_id}, {"id": "v_only"}]
        bm25_rows = [{"id": shared_id}, {"id": "b_only"}]
        ranked = dict(_rrf_merge(vector_rows, bm25_rows))
        # shared appears at rank 1 in both: 1/61 + 1/61
        assert ranked[shared_id] > ranked["v_only"]
        assert ranked[shared_id] > ranked["b_only"]
        assert abs(ranked[shared_id] - 2 / 61) < 1e-9

    def test_empty_lists_return_empty(self) -> None:
        assert _rrf_merge([], []) == []

    def test_result_sorted_descending(self) -> None:
        vector_rows = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        bm25_rows = [{"id": "c"}, {"id": "b"}]
        ranked = _rrf_merge(vector_rows, bm25_rows)
        scores = [score for _, score in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_only_bm25_results(self) -> None:
        bm25_rows = [{"id": "x"}, {"id": "y"}]
        ranked = _rrf_merge([], bm25_rows)
        assert ranked[0][0] == "x"
        assert abs(ranked[0][1] - 1 / 61) < 1e-9

    def test_custom_k_value(self) -> None:
        rows = [{"id": "a"}]
        ranked = _rrf_merge(rows, [], k=0)
        # k=0: score = 1/(0+1) = 1.0
        assert abs(ranked[0][1] - 1.0) < 1e-9

    def test_no_duplicate_ids_in_result(self) -> None:
        """Each chunk_id appears at most once in the merged output."""
        rows = [{"id": "a"}, {"id": "b"}]
        ranked = _rrf_merge(rows, rows)  # same list for both
        ids = [cid for cid, _ in ranked]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# _apply_topic_filter
# ---------------------------------------------------------------------------

class TestApplyTopicFilter:
    def _make_chunk(self, topics: list[str]) -> Chunk:
        return Chunk(
            id=uuid4(),
            content="text",
            metadata=make_metadata(topic=topics),
            embedding=None,
            created_at=None,
        )

    def test_keeps_matching_chunk(self) -> None:
        chunk = self._make_chunk(["product", "launch"])
        result = _apply_topic_filter([chunk], ["launch"])
        assert chunk in result

    def test_removes_non_matching_chunk(self) -> None:
        chunk = self._make_chunk(["finance"])
        result = _apply_topic_filter([chunk], ["product"])
        assert result == []

    def test_partial_overlap_matches(self) -> None:
        """Any topic in common is enough to keep the chunk."""
        chunk = self._make_chunk(["product", "launch", "q1"])
        result = _apply_topic_filter([chunk], ["q1", "earnings"])
        assert chunk in result

    def test_empty_chunks_returns_empty(self) -> None:
        assert _apply_topic_filter([], ["product"]) == []


# ---------------------------------------------------------------------------
# _row_to_chunk
# ---------------------------------------------------------------------------

class TestRowToChunk:
    def test_basic_row_parses_correctly(self) -> None:
        row = make_rpc_row()
        chunk = _row_to_chunk(row)
        assert chunk.content == "Celonis announced something."
        assert chunk.metadata.company == "Celonis"

    def test_pgvector_string_embedding_parsed(self) -> None:
        """Supabase returns vector as string — must be parsed to list[float]."""
        row = make_rpc_row(embedding="[0.1,0.2,0.3]")
        chunk = _row_to_chunk(row)
        assert chunk.embedding == [0.1, 0.2, 0.3]

    def test_none_embedding_preserved(self) -> None:
        row = make_rpc_row(embedding=None)
        chunk = _row_to_chunk(row)
        assert chunk.embedding is None

    def test_list_embedding_preserved(self) -> None:
        row = make_rpc_row(embedding=[0.5, 0.6])
        chunk = _row_to_chunk(row)
        assert chunk.embedding == [0.5, 0.6]

    def test_missing_document_id_gives_none(self) -> None:
        row = make_rpc_row()
        row.pop("document_id")
        chunk = _row_to_chunk(row)
        assert chunk.document_id is None


# ---------------------------------------------------------------------------
# search_chunks — end-to-end with mocked searches
# ---------------------------------------------------------------------------

BASE = "app.rag.retrieval"

ID_A = str(uuid4())
ID_B = str(uuid4())
ID_C = str(uuid4())


class TestSearchChunks:
    def _make_rows(self, *ids: str) -> list[dict]:
        return [make_rpc_row(chunk_id=cid) for cid in ids]

    @pytest.mark.asyncio
    async def test_returns_chunks_in_rrf_order(self) -> None:
        """Chunks that appear in both lists rank higher."""
        vector_rows = self._make_rows(ID_A, ID_B)
        bm25_rows = self._make_rows(ID_A, ID_C)
        # ID_A is in both → highest RRF score

        with (
            patch(f"{BASE}.embed_text", new=AsyncMock(return_value=FAKE_VECTOR)),
            patch(f"{BASE}.asyncio.to_thread", new=AsyncMock(side_effect=[
                bm25_rows,   # first to_thread call: BM25 (runs with embed in gather)
                vector_rows, # second to_thread call: vector search
            ])),
        ):
            result = await search_chunks("celonis process mining")

        assert result[0].id.hex.replace("-", "") == ID_A.replace("-", "") or \
               str(result[0].id) == ID_A

    @pytest.mark.asyncio
    async def test_relevance_score_set_on_all_chunks(self) -> None:
        rows = self._make_rows(ID_A, ID_B)
        with (
            patch(f"{BASE}.embed_text", new=AsyncMock(return_value=FAKE_VECTOR)),
            patch(f"{BASE}.asyncio.to_thread", new=AsyncMock(side_effect=[
                rows, rows,
            ])),
        ):
            result = await search_chunks("test query")
        assert all(c.relevance_score is not None for c in result)

    @pytest.mark.asyncio
    async def test_no_duplicates_in_result(self) -> None:
        """Same chunk appearing in both lists must appear only once."""
        rows = self._make_rows(ID_A, ID_B)
        with (
            patch(f"{BASE}.embed_text", new=AsyncMock(return_value=FAKE_VECTOR)),
            patch(f"{BASE}.asyncio.to_thread", new=AsyncMock(side_effect=[
                rows, rows,
            ])),
        ):
            result = await search_chunks("test query")
        ids = [str(c.id) for c in result]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(self) -> None:
        with (
            patch(f"{BASE}.embed_text", new=AsyncMock(return_value=FAKE_VECTOR)),
            patch(f"{BASE}.asyncio.to_thread", new=AsyncMock(side_effect=[[], []])),
        ):
            result = await search_chunks("something obscure")
        assert result == []

    @pytest.mark.asyncio
    async def test_topic_filter_applied_after_merge(self) -> None:
        """Chunks not matching the topic filter are removed from results."""
        row_match = make_rpc_row(chunk_id=ID_A)
        row_match["metadata"]["topic"] = ["product"]
        row_no_match = make_rpc_row(chunk_id=ID_B)
        row_no_match["metadata"]["topic"] = ["finance"]

        rows = [row_match, row_no_match]
        with (
            patch(f"{BASE}.embed_text", new=AsyncMock(return_value=FAKE_VECTOR)),
            patch(f"{BASE}.asyncio.to_thread", new=AsyncMock(side_effect=[rows, rows])),
        ):
            result = await search_chunks(
                "test", ChunkFilter(topic=["product"])
            )
        assert all("product" in c.metadata.topic for c in result)

    @pytest.mark.asyncio
    async def test_none_filter_treated_as_empty_filter(self) -> None:
        """search_chunks(query, None) should not raise."""
        rows = self._make_rows(ID_A)
        with (
            patch(f"{BASE}.embed_text", new=AsyncMock(return_value=FAKE_VECTOR)),
            patch(f"{BASE}.asyncio.to_thread", new=AsyncMock(side_effect=[rows, rows])),
        ):
            result = await search_chunks("test", None)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_k_limits_results(self) -> None:
        """At most k chunks are returned."""
        rows = self._make_rows(ID_A, ID_B, ID_C)
        with (
            patch(f"{BASE}.embed_text", new=AsyncMock(return_value=FAKE_VECTOR)),
            patch(f"{BASE}.asyncio.to_thread", new=AsyncMock(side_effect=[rows, []])),
        ):
            result = await search_chunks("test", k=2)
        assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_embed_error_propagates(self) -> None:
        """If embed_text raises, search_chunks propagates the error."""
        with patch(f"{BASE}.embed_text", new=AsyncMock(side_effect=RuntimeError("API down"))):
            with pytest.raises(RuntimeError, match="API down"):
                await search_chunks("test")
