"""Chat router — POST /chat.

Currently returns a stub response. The real orchestrator logic is wired
up in Issue #11. Auth middleware (Issue #14) will protect this route
before orchestrator logic lands.
"""

import structlog
from fastapi import APIRouter

from app.models.schemas import ChatRequest, ChatResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Accept a user query and return a response.

    Args:
        request: Validated body containing ``query``.

    Returns:
        A ``ChatResponse`` with an answer and source citations.
        In the stub phase the answer is a fixed placeholder and
        sources is an empty list.
    """
    logger.info("chat_request_received", query_length=len(request.query))

    # Stub — replaced by orchestrator in Issue #11
    return ChatResponse(
        answer="[stub] Orchestrator not yet wired up. Query received: "
               + request.query,
        sources=[],
    )
