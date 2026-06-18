"""Embedding helpers for the RAG pipeline.

Two public functions:
  embed_text   — embed a single string (used by the Retrieve node at query time)
  embed_chunks — embed a list of Chunk objects in batches (used by the pipeline)

Both delegate to the process-level OpenAIClient singleton. All retry and
error-mapping logic lives in the client — this module just orchestrates
batching and the Contextual Retrieval pattern.
"""

import structlog
from app.exceptions import EmbeddingError
from app.llm.openai_client import get_openai_client
from app.models.schemas import Chunk

logger = structlog.get_logger(__name__)

# OpenAI allows up to 2048 inputs per request; 100 is a safe conservative batch.
BATCH_SIZE = 100


async def embed_text(text: str) -> list[float]:
    """Embed a single string and return its 1536-dim vector.

    Used at query time — the Retrieve node embeds the user's query before
    running the vector similarity search.

    Args:
        text: The string to embed.

    Returns:
        A list of 1536 floats (text-embedding-3-small output).

    Raises:
        EmbeddingError: If the API call fails after all retries.
    """
    client = get_openai_client()
    results = await client.embed([text])
    return results[0]


async def embed_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Embed a list of chunks in batches and set chunk.embedding in place.

    Embeds context_header + "\\n\\n" + content for every chunk — the
    Contextual Retrieval pattern (see CLAUDE.md → RAG strategy). Every
    chunk MUST have a non-empty context_header before this function is
    called. If any chunk is missing a header this is a bug in the upstream
    pipeline and raises immediately.

    Batches calls at BATCH_SIZE (100) so 250 chunks produce at most 3
    API calls. Mutates and returns the same list — no copy is made.

    Args:
        chunks: List of Chunk objects with context_header already set.

    Returns:
        The same list with embedding set on every chunk.

    Raises:
        ValueError: If any chunk has an empty context_header — upstream
            bug, not a recoverable error.
        EmbeddingError: If an API call fails after all retries.
    """
    if not chunks:
        return chunks

    # Enforce the context_header contract — fail loudly, not silently.
    missing = [i for i, c in enumerate(chunks) if not c.context_header]
    if missing:
        raise ValueError(
            f"embed_chunks: {len(missing)} chunk(s) have an empty context_header "
            f"(indices {missing[:5]}{'...' if len(missing) > 5 else ''}). "
            "The pipeline must set context_header before calling embed_chunks."
        )

    client = get_openai_client()

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [f"{c.context_header}\n\n{c.content}" for c in batch]

        vectors = await client.embed(texts)

        for chunk, vector in zip(batch, vectors):
            chunk.embedding = vector

        logger.info(
            "embedded_batch",
            batch_start=i,
            batch_size=len(batch),
            total=len(chunks),
        )

    return chunks
