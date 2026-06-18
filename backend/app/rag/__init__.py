try:
    from app.rag.retrieval import search_chunks
except ImportError:
    # Issue #10 not yet merged — async stub until real implementation lands
    async def search_chunks(query: str, k: int = 10, filters=None):  # type: ignore[misc]
        raise NotImplementedError("search_chunks not yet implemented")

__all__ = ["search_chunks"]