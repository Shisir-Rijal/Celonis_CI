"""Unit tests for app/models/schemas.py and app/orchestration/state.py.

Covers:
- Valid model construction
- Closed-enum validation (source_origin, content_type, chunking_strategy)
- Optional fields
- JSON round trip
- WorkflowState defaults and nested Chunk validation
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import ValidationError

from app.models.schemas import Chunk, ChunkMetadata
from app.orchestration.state import WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_metadata(**overrides) -> dict:
    """Return a valid ChunkMetadata payload, with optional field overrides."""
    base = {
        "company": "celonis",
        "source_type": "press_release",
        "source_origin": "owned",
        "date": datetime(2026, 5, 16, tzinfo=timezone.utc),
        "url": "https://celonis.com/press/example",
        "title": "Example Press Release",
        "language": "en",
        "topic": ["product_launch", "pricing"],
        "content_type": "text",
        "visual_type": None,
        "chunking_strategy": "structural",
    }
    base.update(overrides)
    return base


def make_chunk(**overrides) -> dict:
    """Return a valid Chunk payload, with optional field overrides."""
    base = {
        "id": uuid4(),
        "content": "Celonis announces new feature.",
        "metadata": ChunkMetadata(**make_metadata()),
        "embedding": None,
        "created_at": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# ChunkMetadata — valid construction
# ---------------------------------------------------------------------------

class TestChunkMetadataValid:
    def test_basic_construction(self):
        meta = ChunkMetadata(**make_metadata())
        assert meta.company == "celonis"
        assert meta.source_origin == "owned"
        assert meta.chunking_strategy == "structural"

    def test_title_can_be_none(self):
        meta = ChunkMetadata(**make_metadata(title=None))
        assert meta.title is None

    def test_topic_can_be_empty(self):
        meta = ChunkMetadata(**make_metadata(topic=[]))
        assert meta.topic == []

    def test_visual_type_can_be_set(self):
        meta = ChunkMetadata(**make_metadata(
            content_type="image",
            visual_type="logo",
        ))
        assert meta.visual_type == "logo"


# ---------------------------------------------------------------------------
# ChunkMetadata — closed-enum validation
# ---------------------------------------------------------------------------

class TestChunkMetadataEnumValidation:
    @pytest.mark.parametrize("bad_value", ["public", "", "OWNED", "INTERNAL"])
    def test_invalid_source_origin_raises(self, bad_value):
        with pytest.raises(ValidationError):
            ChunkMetadata(**make_metadata(source_origin=bad_value))

    @pytest.mark.parametrize("good_value", ["owned", "earned", "third_party", "internal"])
    def test_valid_source_origin_accepted(self, good_value):
        meta = ChunkMetadata(**make_metadata(source_origin=good_value))
        assert meta.source_origin == good_value

    @pytest.mark.parametrize("bad_value", ["video", "audio", "pdf", ""])
    def test_invalid_content_type_raises(self, bad_value):
        with pytest.raises(ValidationError):
            ChunkMetadata(**make_metadata(content_type=bad_value))

    @pytest.mark.parametrize("good_value", ["text", "image", "transcript"])
    def test_valid_content_type_accepted(self, good_value):
        meta = ChunkMetadata(**make_metadata(content_type=good_value))
        assert meta.content_type == good_value

    @pytest.mark.parametrize("bad_value", ["fixed", "llm", "sentence", ""])
    def test_invalid_chunking_strategy_raises(self, bad_value):
        with pytest.raises(ValidationError):
            ChunkMetadata(**make_metadata(chunking_strategy=bad_value))

    @pytest.mark.parametrize("good_value", ["structural", "none", "agentic"])
    def test_valid_chunking_strategy_accepted(self, good_value):
        meta = ChunkMetadata(**make_metadata(chunking_strategy=good_value))
        assert meta.chunking_strategy == good_value


# ---------------------------------------------------------------------------
# ChunkMetadata — JSON round trip
# ---------------------------------------------------------------------------

class TestChunkMetadataRoundTrip:
    def test_dump_and_validate_json(self):
        original = ChunkMetadata(**make_metadata())
        json_str = original.model_dump_json()
        restored = ChunkMetadata.model_validate_json(json_str)
        assert restored == original

    def test_dump_and_validate_dict(self):
        original = ChunkMetadata(**make_metadata())
        restored = ChunkMetadata.model_validate(original.model_dump())
        assert restored == original


# ---------------------------------------------------------------------------
# Chunk — valid construction and optional fields
# ---------------------------------------------------------------------------

class TestChunkValid:
    def test_basic_construction(self):
        chunk = Chunk(**make_chunk())
        assert chunk.content == "Celonis announces new feature."
        assert chunk.embedding is None
        assert chunk.created_at is None

    def test_embedding_can_be_set(self):
        embedding = [0.1, 0.2, 0.3]
        chunk = Chunk(**make_chunk(embedding=embedding))
        assert chunk.embedding == embedding

    def test_metadata_is_validated(self):
        """Nested ChunkMetadata is still validated when passed as a dict."""
        payload = make_chunk()
        payload["metadata"] = make_metadata()  # pass as dict, not model
        chunk = Chunk(**payload)
        assert chunk.metadata.company == "celonis"

    def test_invalid_metadata_raises(self):
        payload = make_chunk()
        payload["metadata"] = make_metadata(source_origin="invalid")
        with pytest.raises(ValidationError):
            Chunk(**payload)


# ---------------------------------------------------------------------------
# Chunk — JSON round trip
# ---------------------------------------------------------------------------

class TestChunkRoundTrip:
    def test_dump_and_validate_json(self):
        original = Chunk(**make_chunk(
            embedding=[0.1, 0.2, 0.3],
            created_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
        ))
        json_str = original.model_dump_json()
        restored = Chunk.model_validate_json(json_str)
        assert restored == original


# ---------------------------------------------------------------------------
# WorkflowState — defaults and construction
# ---------------------------------------------------------------------------

class TestWorkflowState:
    def test_defaults_are_empty(self):
        state = WorkflowState(query_input="Who is SAP's main competitor?")
        assert state.intermediate_agent_outputs == []
        assert state.retrieved_context == []
        assert state.validation_results == []
        assert state.final_output == ""

    def test_retrieved_context_accepts_chunks(self):
        chunk = Chunk(**make_chunk())
        state = WorkflowState(
            query_input="test query",
            retrieved_context=[chunk],
        )
        assert len(state.retrieved_context) == 1
        assert state.retrieved_context[0].content == chunk.content

    def test_invalid_chunk_in_context_raises(self):
        """WorkflowState validates nested Chunks."""
        with pytest.raises(ValidationError):
            WorkflowState(
                query_input="test",
                retrieved_context=[{"id": "not-a-uuid", "content": 123}],
            )
