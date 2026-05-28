"""backend/app/orchestration/memory.py

Orchestration helpers for conversation memory.
These are the two functions that LangGraph nodes call directly.

No direct Supabase access here — all DB operations go through
conversation_repository. turn_number logic lives here (count existing
DB rows + 1), not in the repository.

Issue #58: conversation memory repository and smoke test extension
"""

from __future__ import annotations

from uuid import UUID

from app.models.schemas import Source
from app.orchestration.state import ConversationTurn
from app.rag.conversation_repository import (
    append_turn,
    get_or_create_conversation,
    get_recent_turns,
)


def load_conversation_history(
    session_id: UUID,
    limit: int = 10,
) -> list[ConversationTurn]:
    """Load recent conversation turns for a session.

    Creates the conversation row if it does not yet exist.

    Args:
        session_id: The UUID identifying this chat session.
        limit:      Max number of DB rows (each row = 2 turns) to load.

    Returns:
        ConversationTurn list in chronological order (oldest first).
    """
    conversation = get_or_create_conversation(session_id)
    conversation_id = UUID(conversation["id"])
    return get_recent_turns(conversation_id, limit=limit)


def save_turn(
    session_id: UUID,
    query: str,
    answer: str,
    sources: list[Source],
    derivation: str,
) -> None:
    """Persist a completed turn to Supabase.

    turn_number is computed here as (existing DB rows) + 1.
    Each DB row corresponds to one user+assistant exchange, and
    get_recent_turns returns 2 ConversationTurn objects per row,
    so: db_row_count = len(existing_turns) // 2.

    Args:
        session_id:  The UUID identifying this chat session.
        query:       The user's message.
        answer:      The assistant's final response.
        sources:     Sources cited in the response.
        derivation:  How the answer was produced.
    """
    conversation = get_or_create_conversation(session_id)
    conversation_id = UUID(conversation["id"])

    # Each DB row → 2 ConversationTurn objects, so divide by 2 to get row count
    existing_turns = get_recent_turns(conversation_id, limit=9999)
    turn_number = len(existing_turns) // 2 + 1

    append_turn(
        conversation_id=conversation_id,
        query=query,
        answer=answer,
        sources=sources,
        derivation=derivation,
        turn_number=turn_number,
    )