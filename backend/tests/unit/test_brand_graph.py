"""backend/tests/unit/test_brand_graph.py

Unit tests for the Brand Intelligence Pipeline graph scaffold.

Issue #86: Brand Intelligence Pipeline — LangGraph foundation and manual runner
"""

import pytest


def test_brand_graph_compiles_and_is_importable() -> None:
    """brand_graph compiles cleanly and is importable without error."""
    from app.agents.brand.graph import brand_graph

    assert brand_graph is not None


def test_brand_pipeline_state_has_required_fields() -> None:
    """BrandPipelineState has all required fields with correct types."""
    from app.agents.brand.state import BrandPipelineState
    import typing

    hints = typing.get_type_hints(BrandPipelineState)

    assert "competitor_domain" in hints
    assert "nodes_to_run" in hints
    assert "profile" in hints
    assert "results" in hints
    assert "errors" in hints
    assert "completed_capabilities" in hints
