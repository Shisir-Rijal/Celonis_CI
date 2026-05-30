"""backend/tests/unit/test_critic_node.py

Unit tests for critic_node stub.

Issue #65 acceptance criteria:
  - critic_node returns {} without raising, given any state
"""

import pytest

from app.orchestration.nodes.critic import critic_node


@pytest.mark.asyncio
async def test_critic_node_returns_empty_dict() -> None:
    """critic_node stub returns {} without raising, given any state."""
    state = {
        "query": "test",
        "session_id": None,
        "agent_calls": [],
        "decomposed_tasks": [],
        "retrieved_context": [],
        "conversation_history": [],
        "validation_results": [],
        "sources": [],
        "derivation": "",
        "final_output": "",
        "retrieval_mode": "standard",
        "discovery_query": None,
    }

    result = await critic_node(state)

    assert result == {}