"""backend/app/rag/conversation_repository.py

Thin Supabase wrappers for the conversations and conversation_turns tables.
No orchestration logic lives here — this module only reads and writes rows.
All Supabase-specific query syntax is contained in this file.

Follows the same pattern as app/rag/repository.py:
  - optional `client` keyword argument on every function
  - get_supabase() as fallback when client is None
  - raw Supabase exceptions are caught and re-raised as RepositoryError

Issue #58: conversation memory repository and smoke test extension
"""
from typing import Any, cast

from datetime import datetime
from typing import cast
from uuid import UUID

from supabase import Client

from app.exceptions import RepositoryError
from app.models.schemas import Source
from app.orchestration.state import ConversationTurn
from app.rag.supabase_client import get_supabase

_CONVERSATIONS = "conversations"
_TURNS = "conversation_turns"


def get_or_create_conversation(
    session_id: UUID,
    *,
    client: Client | None = None,
) -> dict:
    """Return the conversations row for session_id, creating it if absent.

    Args:
        session_id: The UUID that identifies this chat session.
        client: Optional Supabase client override for testing.

    Returns:
        The conversations row as a plain dict.

    Raises:
        RepositoryError: On any Supabase / network error.
    """
    db = client or get_supabase()
    try:
        result = (
            db.table(_CONVERSATIONS)
            .select("*")
            .eq("session_id", str(session_id))
            .limit(1)
            .execute()
        )
        if result.data:
            return cast(dict, result.data[0])

        # Row absent — insert a new one
        inserted = (
            db.table(_CONVERSATIONS)
            .insert({"session_id": str(session_id)})
            .execute()
        )
        return cast(dict, inserted.data[0])

    except Exception as exc:
        raise RepositoryError(
            f"get_or_create_conversation failed for session {session_id}: {exc}"
        ) from exc


def append_turn(
    conversation_id: UUID,
    query: str,
    answer: str,
    sources: list[Source],
    derivation: str,
    turn_number: int,
    *,
    client: Client | None = None,
) -> None:
    """Append a completed user+assistant exchange to conversation_turns.

    Args:
        conversation_id: The UUID primary key of the parent conversation row.
        query:           The user's message for this turn.
        answer:          The assistant's response.
        sources:         Sources used; serialised to jsonb before insert.
        derivation:      How the answer was derived.
        turn_number:     Sequential index (1-based); computed in memory.py.
        client:          Optional Supabase client override for testing.

    Raises:
        RepositoryError: If conversation_id does not exist or on any DB error.
                         Raw postgrest exceptions must not bubble up.
    """
    db = client or get_supabase()
    try:
        serialised_sources = [s.model_dump(mode="json") for s in sources]
        db.table(_TURNS).insert(
            {
                "conversation_id": str(conversation_id),
                "query": query,
                "answer": answer,
                "sources": serialised_sources,
                "derivation": derivation,
                "turn_number": turn_number,
            }
        ).execute()
    except Exception as exc:
        raise RepositoryError(
            f"append_turn failed for conversation {conversation_id}: {exc}"
        ) from exc


def get_recent_turns(
    conversation_id: UUID,
    limit: int = 10,
    *,
    client: Client | None = None,
) -> list[ConversationTurn]:
    """Return up to *limit* recent turns in chronological order (oldest first).

    Fetches newest-first from the DB (created_at DESC), then reverses so the
    orchestrator receives history in natural reading order.

    Each DB row becomes two ConversationTurn entries: role="user" with the
    query, then role="assistant" with the answer and sources.

    Args:
        conversation_id: UUID primary key of the conversation.
        limit:           Max number of DB rows to fetch. Returns [] if 0.
        client:          Optional Supabase client override for testing.

    Returns:
        ConversationTurn list in chronological order (oldest first).

    Raises:
        RepositoryError: On any Supabase / network error.
    """
    if limit == 0:
        return []

    db = client or get_supabase()
    try:
        result = (
            db.table(_TURNS)
            .select("*")
            .eq("conversation_id", str(conversation_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as exc:
        raise RepositoryError(
            f"get_recent_turns failed for conversation {conversation_id}: {exc}"
        ) from exc

    # Reverse to chronological order (oldest first)
    raw_data = cast(list[dict[str, Any]], result.data or [])
    rows = list(reversed(raw_data))

    turns: list[ConversationTurn] = []
    for row in rows:
        raw_sources = row.get("sources") or []
        row_sources = [Source(**s) for s in raw_sources]
        created_at = datetime.fromisoformat(row["created_at"])

        turns.append(ConversationTurn(
            role="user",
            content=row["query"],
            sources=[],
            derivation="",
            created_at=created_at,
        ))
        turns.append(ConversationTurn(
            role="assistant",
            content=row["answer"],
            sources=row_sources,
            derivation=row.get("derivation", ""),
            created_at=created_at,
        ))

    return turns