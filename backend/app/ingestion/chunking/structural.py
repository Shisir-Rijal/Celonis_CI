"""
Structural chunking 
-> chunkingstrategy for Markdown-content.

Splits text at Markdown headings (#, ##, ...).
Sections below min_tokens are merged with next ones; sections above max_tokens are
split using a sliding token window with overlap so no context is lost at boundaries.
All resulting chunks share the same metadata as the source document, with
chunking_strategy set to "structural".

Defaults: min 200 tokens, max 800 tokens, 80 token overlap (cl100k_base encoding).

??? min tokens sinnvoll oder lieber auch sehr keline Chunks ???
"""
import re
import uuid
from datetime import datetime, timezone

import tiktoken

from app.models.schemas import Chunk, ChunkMetadata

_ENCODING = tiktoken.get_encoding("cl100k_base")

DEFAULT_MIN_TOKENS = 200
DEFAULT_MAX_TOKENS = 800
DEFAULT_OVERLAP_TOKENS = 80


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _split_at_headings(text: str) -> list[str]:
    """Split markdown text into sections at each heading line."""
    parts = re.split(r"(?=^#{1,6}\s)", text, flags=re.MULTILINE)
    return [p.strip() for p in parts if p.strip()]


def _merge_short_sections(sections: list[str], min_tokens: int) -> list[str]:
    """Merge consecutive sections until the combined text exceeds min_tokens."""
    merged: list[str] = []
    buffer = ""
    for section in sections:
        candidate = (buffer + "\n\n" + section).strip() if buffer else section
        if _count_tokens(candidate) < min_tokens:
            buffer = candidate
        else:
            merged.append(candidate)
            buffer = ""
    if buffer:
        if merged:
            merged[-1] = merged[-1] + "\n\n" + buffer
        else:
            merged.append(buffer)
    return merged


def _split_by_tokens(text: str, max_tokens: int, overlap: int) -> list[str]:
    """Split text that exceeds max_tokens into windows with overlap."""
    tokens = _ENCODING.encode(text)
    step = max_tokens - overlap
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunks.append(_ENCODING.decode(tokens[start:end]))
        if end == len(tokens):
            break
        start += step
    return chunks


def chunk_structural(
    text: str,
    metadata: ChunkMetadata,
    min_tokens: int = DEFAULT_MIN_TOKENS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    sections = _split_at_headings(text)
    merged = _merge_short_sections(sections, min_tokens)

    chunk_texts: list[str] = []
    for section in merged:
        if _count_tokens(section) <= max_tokens:
            chunk_texts.append(section)
        else:
            chunk_texts.extend(_split_by_tokens(section, max_tokens, overlap_tokens))

    now = datetime.now(timezone.utc)
    chunk_meta = metadata.model_copy(update={"chunking_strategy": "structural"})

    return [
        Chunk(
            id=uuid.uuid4(),
            content=chunk_text,
            metadata=chunk_meta,
            embedding=None,
            created_at=now,
        )
        for chunk_text in chunk_texts
    ]