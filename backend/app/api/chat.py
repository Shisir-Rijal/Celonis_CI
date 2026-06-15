"""backend/app/api/chat.py

Chat router — POST /chat.
Runs the full orchestrator graph and streams progress + result via SSE.

Supersedes the stub from Issue #11.
Issue #66: Respond node and SSE chat endpoint — orchestrator end-to-end
"""

import json
import structlog
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth.dependencies import require_auth
from app.orchestration.graph import orchestrator_graph
from app.orchestration.state import WorkflowState

from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Node name → SSE phase label
_PHASE_MAP: dict[str, str] = {
    "retrieve": "retrieving",
    "assess": "assessing",
    "dispatch": "dispatching",
}


class ChatBody(BaseModel):
    query: str
    session_id: str | None = None


@router.post("", dependencies=[Depends(require_auth)])
async def chat(body: ChatBody) -> StreamingResponse:
    """Run the orchestrator graph and stream SSE events to the client.

    Events emitted:
      {"type": "phase", "phase": "retrieving" | "assessing" | "dispatching"}
      {"type": "message", "answer": ..., "sources": [...], "derivation": ..., "session_id": ...}
      {"type": "error", "message": ...}  — only on unhandled exceptions
    """
    session_id: UUID = UUID(body.session_id) if body.session_id else uuid4()
    logger.info(
        "chat_request_received",
        query_length=len(body.query),
        session_id=str(session_id),
    )

    initial_state: WorkflowState = {
        "session_id": session_id,
        "query": body.query,
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

    async def event_stream()-> AsyncGenerator[str, None]:
        final_answer = ""
        final_sources: list = []
        final_derivation = ""

        try:
            async for event in orchestrator_graph.astream_events(
                initial_state, version="v2"
            ):
                evt_type: str = event["event"]
                evt_name: str = event.get("name", "")

                # Phase events: emit when a node starts
                if evt_type == "on_chain_start":
                    phase = _PHASE_MAP.get(evt_name)
                    if phase:
                        payload = {"type": "phase", "phase": phase}
                        yield f"data: {json.dumps(payload)}\n\n"

                # Capture final answer when synthesize completes
                elif evt_type == "on_chain_end" and evt_name == "synthesize":
                    output = event["data"].get("output", {})
                    final_answer = output.get("final_output", "")
                    final_derivation = output.get("derivation", "")
                    raw_sources = output.get("sources", [])
                    final_sources = [
                        s.model_dump() if hasattr(s, "model_dump") else s
                        for s in raw_sources
                    ]

            # Graph completed — emit final message
            message_payload = {
                "type": "message",
                "answer": final_answer,
                "sources": final_sources,
                "derivation": final_derivation,
                "session_id": str(session_id),
            }
            yield f"data: {json.dumps(message_payload)}\n\n"

        except Exception as exc:
            logger.error("chat_graph_error", error=str(exc))
            error_payload = {"type": "error", "message": str(exc)}
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
