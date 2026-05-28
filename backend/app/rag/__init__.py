"""app/rag package.

search_chunks is a stub here — real implementation built in Issue #10.
"""

from app.models.schemas import Chunk


def search_chunks(
    query: str,
    limit: int = 10,
    filters: dict | None = None,
) -> list[Chunk]:
    """Stub — real hybrid search implementation built in Issue #10."""
    raise NotImplementedError("search_chunks not yet implemented")