"""Chat router — POST /chat.

End-to-end RAG slice (Issue #11):
  1. Retrieve relevant chunks with hybrid search.
  2. Build a prompt via app/prompts/chat_basic.py.
  3. Call the configured LLM.
  4. Parse the structured reply into ChatResponse.

Edge cases handled here:
  - Zero chunks retrieved  → "no sources found" answer, empty sources/derivation.
  - LLMProviderError       → HTTP 503, no stack trace leaked.
"""

import re
import time
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_auth
from app.config import get_settings
from app.exceptions import LLMProviderError
from app.llm.openai_client import get_openai_client
from app.models.schemas import ChatRequest, ChatResponse, Chunk, Source
from app.prompts.chat_basic import build_messages
from app.rag.retrieval import search_chunks

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_response(text: str, chunks: list[Chunk]) -> tuple[str, list[Source], str]:
    """Split the structured LLM reply into answer, sources, and derivation.

    The model is instructed to write:
        ANSWER:
        <text with [uuid] citations>

        DERIVATION:
        <reasoning paragraph>

    We extract both sections with a regex, then collect every UUID that
    appears inside square brackets in the answer and map those back to the
    Chunk objects we retrieved.

    Args:
        text:   Raw string returned by the LLM.
        chunks: The retrieved chunks, used for the ID → Source mapping.

    Returns:
        (answer, sources, derivation) — answer and derivation are plain
        strings; sources is a list of Source objects for each cited chunk.
    """
    # ---- Split into ANSWER / DERIVATION sections -------------------------
    answer_match = re.search(
        r"ANSWER:\s*(.*?)(?=DERIVATION:|$)", text, re.DOTALL | re.IGNORECASE
    )
    deriv_match = re.search(
        r"DERIVATION:\s*(.*?)$", text, re.DOTALL | re.IGNORECASE
    )

    answer = answer_match.group(1).strip() if answer_match else text.strip()
    derivation = deriv_match.group(1).strip() if deriv_match else ""

    # ---- Find cited chunk IDs in the answer section ----------------------
    # UUIDs look like: 3fa85f64-5717-4562-b3fc-2c963f66afa6
    cited_ids: set[str] = set(
        re.findall(r"\[([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]", answer)
    )

    # ---- Map cited IDs → Source objects ----------------------------------
    chunk_by_id = {str(c.id): c for c in chunks}
    sources: list[Source] = [
        Source(
            url=chunk_by_id[cid].metadata.url,
            title=chunk_by_id[cid].metadata.title,
            relevance_score=chunk_by_id[cid].relevance_score or 0.0,
        )
        for cid in cited_ids
        if cid in chunk_by_id
    ]

    # Sort by relevance descending so the frontend can render them in order.
    sources.sort(key=lambda s: s.relevance_score, reverse=True)

    return answer, sources, derivation


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("", response_model=ChatResponse, dependencies=[Depends(require_auth)])
async def chat(request: ChatRequest) -> ChatResponse:
    """Accept a user query and return a grounded answer with source citations.

    Args:
        request: Validated body containing ``query``.

    Returns:
        ChatResponse with answer, cited sources, and a derivation string.
        If no chunks are found, returns a clear "no sources" message with
        empty sources and derivation.

    Raises:
        HTTPException(503): When the LLM provider fails after all retries.
    """
    correlation_id = str(uuid.uuid4())
    log = logger.bind(correlation_id=correlation_id)

    # ------------------------------------------------------------------
    # 1. Retrieve relevant chunks.
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    chunks = await search_chunks(request.query)
    retrieval_ms = int((time.perf_counter() - t0) * 1000)

    chunk_ids = [str(c.id) for c in chunks]
    log.info(
        "chunks_retrieved",
        query=request.query,
        chunk_ids=chunk_ids,
        latency_ms=retrieval_ms,
    )

    # ------------------------------------------------------------------
    # 2. No-sources fast path.
    # ------------------------------------------------------------------
    if not chunks:
        log.info("no_sources_found", query=request.query)
        return ChatResponse(
            answer="No relevant sources were found for your query.",
            sources=[],
            derivation="",
        )

    # ------------------------------------------------------------------
    # 3. Build prompt and call the LLM.
    # ------------------------------------------------------------------
    settings = get_settings()
    messages = build_messages(request.query, chunks)

    try:
        t1 = time.perf_counter()
        raw = await get_openai_client().complete(messages)
        llm_ms = int((time.perf_counter() - t1) * 1000)
        log.info(
            "llm_complete",
            model=settings.OPENAI_CHAT_MODEL,
            latency_ms=llm_ms,
        )
    except LLMProviderError as exc:
        log.error("llm_error", error=str(exc))
        raise HTTPException(
            status_code=503,
            detail="LLM provider unavailable. Please try again later.",
        )

    # ------------------------------------------------------------------
    # 4. Parse the structured reply.
    # ------------------------------------------------------------------
    answer, sources, derivation = _parse_response(raw, chunks)

    return ChatResponse(answer=answer, sources=sources, derivation=derivation)
