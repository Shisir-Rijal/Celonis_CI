"""backend/tests/unit/test_capability_result.py

Unit tests for CapabilityResult and topics vocabulary.

Issue #87: CapabilityResult schema and topic vocabulary for Brand Pipeline
"""

import pytest
from pydantic import ValidationError


def test_capability_result_instantiates_without_error() -> None:
    """CapabilityResult can be created with all required fields, error=None."""
    from app.agents.brand.capability import CapabilityResult

    result = CapabilityResult(
        capability="ai_search_coherence",
        company="sap.com",
        data={"mention_rate": 0.64},
    )

    assert result.capability == "ai_search_coherence"
    assert result.company == "sap.com"
    assert result.error is None
    assert result.run_at is not None


def test_capability_result_with_error() -> None:
    """CapabilityResult can be created with error set."""
    from app.agents.brand.capability import CapabilityResult

    result = CapabilityResult(
        capability="tone_of_voice",
        company="ibm.com",
        error="LLM call failed",
    )

    assert result.error == "LLM call failed"
    assert result.data == {}


def test_capability_result_missing_required_fields_raises() -> None:
    """CapabilityResult without required fields raises ValidationError."""
    from app.agents.brand.capability import CapabilityResult

    with pytest.raises(ValidationError):
        CapabilityResult(company="sap.com")


def test_topics_importable_and_no_duplicates() -> None:
    """TOPICS list is importable and contains no duplicate entries."""
    from app.models.topics import TOPICS

    assert isinstance(TOPICS, list)
    assert len(TOPICS) == len(set(TOPICS))
    assert len(TOPICS) > 0
