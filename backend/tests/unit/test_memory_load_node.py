"""backend/tests/unit/test_memory_load_node.py

Unit tests for the memory_load_node.
The memory layer is mocked so no Supabase connection is needed.

Issue #59 acceptance criteria:
  - Normal path: load_conversation_history called with correct session_id,
    returned list written to state
  - session_id=None: returns empty list, load_conversation_history not called
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.orchestration.nodes.memory_load import memory_load_node


@pytest.fixture
def mock_turns():
    """Two mock ConversationTurn objects."""
    user_turn = MagicMock()
    user_turn.role = "user"
    user_turn.content = "What is Celonis?"

    assistant_turn = MagicMock()
    assistant_turn.role = "assistant"
    assistant_turn.content = "Celonis is a process mining platform."

    return [user_turn, assistant_turn]


@pytest.mark.asyncio
async def test_memory_load_normal_path(mock_turns) -> None:
    """load_conversation_history is called with the correct session_id
    and the returned list is written to conversation_history."""
    session_id = uuid4()

    with patch(
        "app.orchestration.nodes.memory_load.load_conversation_history",
        return_value=mock_turns,
    ) as mock_load:
        state = {
            "session_id": session_id,
            "query": "What is Celonis?",
        }
        result = await memory_load_node(state)

        mock_load.assert_called_once_with(session_id, limit=10)
        assert result == {"conversation_history": mock_turns}


@pytest.mark.asyncio
async def test_memory_load_session_id_none() -> None:
    """When session_id is None, return empty history without
    calling the repository."""
    with patch(
        "app.orchestration.nodes.memory_load.load_conversation_history"
    ) as mock_load:
        state = {
            "session_id": None,
            "query": "What is Celonis?",
        }
        result = await memory_load_node(state)

        mock_load.assert_not_called()
        assert result == {"conversation_history": []}


@pytest.mark.asyncio
async def test_memory_load_propagates_exception() -> None:
    """If load_conversation_history raises, the exception propagates
    out of the node — no silent swallowing."""
    session_id = uuid4()

    with patch(
        "app.orchestration.nodes.memory_load.load_conversation_history",
        side_effect=Exception("Supabase unreachable"),
    ):
        state = {
            "session_id": session_id,
            "query": "What is Celonis?",
        }
        with pytest.raises(Exception, match="Supabase unreachable"):
            await memory_load_node(state)
