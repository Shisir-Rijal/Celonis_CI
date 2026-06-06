"""backend/app/prompts/brand/geo_analysis.py

Prompt template and Pydantic output schema for per-keyword GEO analysis.

Uses LangChain's with_structured_output(strict=True) via OpenAI's constrained
decoding — guarantees 100% schema compliance without json.loads() in
application code.

The reasoning field is intentional: it forces the model to articulate its
classification logic before committing to enum values. This materially
improves consistency on edge cases (e.g. "attributed" vs "recommended").

Issue #90: GEO Intelligence backend
"""

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class GeoAnalysisOutput(BaseModel):
    """Structured analysis of one keyword's LLM response.

    Uses structured chain-of-thought: each field is a specific cognitive step
    that constrains the next. The model cannot classify 'framing' as visionary
    if it already quoted a sentence showing technical language — the earlier
    fields anchor the later ones and prevent self-contradiction.

    Field descriptions become the OpenAI function schema — write them as
    precise instructions, not documentation.
    """

    # ------------------------------------------------------------------
    # Step 1 — Enumerate before judging
    # Forces the model to read carefully before any classification.
    # ------------------------------------------------------------------

    companies_in_response: list[str] = Field(
        description=(
            "List every company, product, or platform name you can find "
            "in the AI response, exactly as written. Include the target company "
            "if present. If no companies are named, return an empty list."
        )
    )

    # ------------------------------------------------------------------
    # Step 2 — Explicit presence check derived from Step 1
    # Grounded in the list above — prevents hallucination about presence.
    # ------------------------------------------------------------------

    target_mentioned: bool = Field(
        description=(
            "Is the target company in your companies_in_response list? "
            "True if yes, false if not. Case-insensitive. "
            "Partial matches do not count (e.g. 'Celon' ≠ 'Celonis')."
        )
    )

    # ------------------------------------------------------------------
    # Step 3 — Verbatim extraction
    # Anchors all subsequent classifications to the actual text.
    # ------------------------------------------------------------------

    exact_quote: str | None = Field(
        description=(
            "If target_mentioned=true, copy the exact sentence or passage "
            "where the target company appears, verbatim, up to 300 characters. "
            "Do not paraphrase. If target_mentioned=false, return null."
        )
    )

    # ------------------------------------------------------------------
    # Step 4 — Tone observation in plain language before classifying
    # Forces articulation of what was actually read before enum assignment.
    # ------------------------------------------------------------------

    tone_observation: str | None = Field(
        description=(
            "If target_mentioned=true, describe in 1 to 2 sentences what the "
            "response actually says about the target company. Use plain language: "
            "what words and phrases does the response use? Is it cautious, "
            "enthusiastic, comparative, qualified? "
            "If target_mentioned=false, return null."
        )
    )

    # ------------------------------------------------------------------
    # Step 5 — Classifications (anchored to Steps 1–4)
    # These must be consistent with exact_quote and tone_observation.
    # ------------------------------------------------------------------

    co_mentioned_companies: list[str] = Field(
        description=(
            "From your companies_in_response list, remove the target company. "
            "Return the rest. These are the companies mentioned alongside "
            "the target. Return an empty list if the target was the only one "
            "or if no companies were found."
        )
    )

    framing: Literal["technical", "strategic", "visionary"] | None = Field(
        description=(
            "Based on exact_quote and tone_observation, how does the response "
            "frame the target company using EXPLICIT language in the text? "
            "Do NOT infer framing from list position — appearing first in a list "
            "with no descriptor is NOT visionary. "
            "'technical': the response explicitly uses functional language about "
            "the company — tool, software, product, analytics, dashboard, solution "
            "(e.g. 'X is a process mining tool', 'X provides analytics capabilities'). "
            "'strategic': the response explicitly uses transformation or enablement "
            "language — platform, partner, enabler, transformation "
            "(e.g. 'X enables enterprise transformation', 'X is an end-to-end platform'). "
            "'visionary': the response uses leadership or pioneer language SPECIFICALLY "
            "about the target company — not as preamble for a list of companies. "
            "Examples: 'X is the leader in process intelligence', 'X pioneered the field', "
            "'X is the #1 provider'. "
            "IMPORTANT: 'The leading providers include X, Y, Z' does NOT qualify — "
            "here 'leading' describes the whole list, not X specifically. "
            "Return null if any of these apply: "
            "(a) target_mentioned=false, "
            "(b) the company appears in a numbered or bulleted list and the only "
            "qualifier in the sentence describes the whole list, not the company "
            "specifically — e.g. 'The leading providers include: 1. X, 2. Y' → "
            "null because 'leading' modifies 'providers', not X, "
            "(c) no sentence in exact_quote contains a descriptor word "
            "applied directly to the target company."
        )
    )

    recommendation_strength: Literal[
        "listed", "attributed", "recommended", "default"
    ] | None = Field(
        description=(
            "Based on exact_quote, how strongly is the target company recommended? "
            "'listed': name appears in an enumeration with no distinguishing "
            "descriptor ('Providers include A, B, X'). "
            "'attributed': mentioned with a positive attribute but not actively "
            "recommended ('X is known for strong process mining capabilities'). "
            "'recommended': actively suggested for a specific situation "
            "('For supply chain analysis, X is a good choice'). "
            "'default': presented as the obvious or first choice "
            "('X is the go-to solution', or named first with clear primacy). "
            "Return null if target_mentioned=false."
        )
    )

    use_case_context: str | None = Field(
        description=(
            "The specific use case, industry, or problem the response is about, "
            "in 3 to 10 words. Derive from the full response, not just the quote. "
            "Examples: 'supply chain optimisation', 'SAP migration for manufacturing', "
            "'financial close automation'. "
            "Return null if the response is generic or target_mentioned=false."
        )
    )

    counter_positioning: str | None = Field(
        description=(
            "Any limitation, criticism, caveat, or negative qualifier the response "
            "attaches specifically to the target company. "
            "Capture the substance in 3 to 12 words. "
            "Examples: 'expensive for mid-market', 'steep learning curve', "
            "'primarily suited for large enterprises'. "
            "Return null if no negative qualifier is present or target_mentioned=false."
        )
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

GEO_ANALYSIS_SYSTEM_PROMPT = """\
You are a senior brand analyst specialising in AI search visibility for \
B2B software companies. Your task is to analyse a single response that an \
AI model produced for a user query and extract structured brand positioning \
insights.

You will receive:
  1. The original user query.
  2. The AI model's full response to that query.
  3. The name of the target company being tracked.

You work through the analysis in sequence — each field builds on the previous. \
Fill every field in order. The earlier fields anchor the later ones: \
if your exact_quote shows functional language, framing cannot be "visionary". \
Follow the evidence in the text, not your prior knowledge about the company.

RULES:

1. Work through fields in order. Do not skip ahead to classifications.

2. Ground every classification in exact_quote and tone_observation. \
If those fields are null, all classification fields must also be null.

3. Do NOT infer or invent. If the evidence is ambiguous, return null. \
Null is correct. A confident wrong answer is not.

4. Do NOT draw on external knowledge about the target company. \
Only what is written in the AI response counts.

5. co_mentioned_companies must never include the target company itself.
"""


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

def build_geo_analysis_messages(
    query: str,
    response: str,
    target_company: str,
) -> list[dict]:
    """Build the messages list for one keyword analysis call.

    Pass to get_structured_chat_client(GeoAnalysisOutput).ainvoke().

    Args:
        query:          The original keyword query sent to the LLM.
        response:       The LLM's full response to that query.
        target_company: The company being tracked, e.g. "Celonis".

    Returns:
        Messages list for the LLM call.
    """
    user_content = (
        f"QUERY: {query}\n\n"
        f"AI RESPONSE TO ANALYSE:\n{response}\n\n"
        f"TARGET COMPANY: {target_company}"
    )
    return [
        {"role": "system", "content": GEO_ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
