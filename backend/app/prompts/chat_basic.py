"""Basic RAG chat prompt template.

Builds the messages list that chat.py passes to the LLM.  The model is
instructed to answer using only the supplied source chunks, cite each claim
with the chunk's UUID in square brackets, and close with a structured
DERIVATION section that explains the reasoning chain.

Public surface:
    build_messages(query, chunks) -> list[dict]
"""

from app.models.schemas import Chunk

_SYSTEM = """\
You are a precise research assistant. Answer the user's question using ONLY \
the provided sources below. Do not use any outside knowledge.

Rules:
1. After each claim, cite the source chunk using its ID in square brackets, \
e.g. [3fa85f64-5717-4562-b3fc-2c963f66afa6].
2. If no source supports a claim, do not make it.
3. Structure your entire response exactly like this — no extra sections:

ANSWER:
<your answer with inline [chunk-id] citations>

DERIVATION:
<one short paragraph: which chunk says what, and how those facts lead to \
your answer>
"""


def build_messages(query: str, chunks: list[Chunk]) -> list[dict]:
    """Return the messages list for a basic RAG completion.

    Args:
        query:  The user's natural-language question.
        chunks: Retrieved chunks, already sorted by relevance descending.

    Returns:
        A two-element list — system message + user message — ready to pass
        to ChatClient.complete().
    """
    source_lines = "\n\n".join(
        f"[{chunk.id}]\n{(chunk.context_header + chr(10)) if chunk.context_header else ''}{chunk.content}"
        for chunk in chunks
    )

    user_content = f"Sources:\n{source_lines}\n\nQuestion: {query}"

    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user_content},
    ]
