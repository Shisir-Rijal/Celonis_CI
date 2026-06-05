from app.models.schemas import ChunkMetadata


def build_context_header(metadata: ChunkMetadata) -> str:
    """Build a structured context header from chunk metadata."""
    parts = [
        f"Company: {metadata.company}",
        f"Type: {metadata.source_type}",
        f"Date: {metadata.date.strftime('%Y-%m-%d')}",
    ]
    if metadata.title:
        parts.append(f"Title: {metadata.title}")
    return " | ".join(parts)
