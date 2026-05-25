"""
Agentic chunking strategy for longer, high-value content.

Instead of splitting by tokens or headings, the text is sent to an LLM
(for now GPT-4o-mini) -> identifies sections and writes a one-sentence summary for each. 
The summary is addedd to the section content so the embedding captures both the gist and the detail.

Uses the ChatClient abstraction layer, not directly OpenAI.
"""
import json
import uuid
from datetime import datetime, timezone

# app/exceptions.py — raised when LLM returns unusable output
from app.exceptions import ChunkingError
# app/llm/base.py —> abstract interface
from app.llm.base import ChatClient
# app/models/schemas.py —> shared data models
from app.models.schemas import Chunk, ChunkMetadata

_SYSTEM_PROMPT = """
You are a document segmentation assistant. 
Split the provided text into semantically coherent sections.

For each section return:
- "summary": one sentence describing what this section covers
- "content": the verbatim text of this section (no changes, no omissions)

Respond with valid JSON in this exact format:
{"sections": [{"summary": "...", "content": "..."}, ...]}

Rules:
- Keep each section between 2 and 10 paragraphs
- Never omit or alter any part of the original text
- Never merge unrelated topics into one section"""


async def chunk_agentic(
    text: str,
    metadata: ChunkMetadata,
    client: ChatClient,
) -> list[Chunk]:
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]

    # response_format forces valid JSON output
    response = await client.complete(messages, response_format={"type": "json_object"})  

    try:
        sections = json.loads(response)["sections"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise ChunkingError(f"Agentic chunker received invalid JSON from LLM: {exc}") from exc

    now = datetime.now(timezone.utc)
    # model_copy(): Pydantic method —> clones metadata and overrides one field
    chunk_meta = metadata.model_copy(update={"chunking_strategy": "agentic"})  

    return [
        Chunk(
            id=uuid.uuid4(),  # uuid4() generates a random unique ID (stdlib)
            content=f"{section['summary']}\n\n{section['content']}",
            metadata=chunk_meta,
            embedding=None,
            created_at=now,
        )
        for section in sections
    ]
