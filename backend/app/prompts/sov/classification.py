"""backend/app/prompts/sov/classification.py

Structured-output schema and prompt builder for the SoV classification step.

One call per Mention: the LLM picks themes / region / relevance from the
project's controlled vocabularies. Both fields are typed Literal, so
with_structured_output(strict=True) guarantees the model never returns a
value outside the lists.
"""

from pydantic import BaseModel, Field

from app.agents.sov.state import Mention, Region
from app.agents.sov.themes import THEMES, Theme


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class SovClassificationOutput(BaseModel):
    """Classification result for a single Mention."""

    themes: list[Theme] = Field(
        description=(
            "One to three themes from the allowed list that best describe the "
            "mention. Use only themes clearly evidenced in title or content. "
            "Use 'Other' as fallback when the mention is relevant but no "
            "specific theme fits."
        ),
    )
    region: Region = Field(
        description=(
            "Primary geographical region for this mention. Infer from URL TLD, "
            "source, named places, or language. Use 'Global' when no clear "
            "regional anchor exists."
        ),
    )
    is_relevant: bool = Field(
        description=(
            "True if the mention covers software, AI, process, automation, "
            "or business transformation topics. False only for content with "
            "no such angle (e.g. pure stock-price reports, weather, sport)."
        ),
    )
    reasoning: str = Field(
        description=(
            "One sentence (max 25 words) justifying the classification. "
            "Reference specific words from the mention."
        ),
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SOV_CLASSIFICATION_SYSTEM_PROMPT = f"""\
You are a brand intelligence analyst classifying mentions of B2B software \
companies operating in the process mining, process intelligence, automation, \
and digital transformation space.

For each mention you receive, decide:

1. themes — pick 1 to 3 from this exact list, no others:
   {", ".join(THEMES)}
   Only choose themes clearly evidenced in the title or content. \
"Other" is the fallback for relevant mentions where nothing specific fits.

2. region — pick exactly one of: DACH, Europe, NA, APAC, Global.
   - DACH means Germany, Austria, Switzerland.
   - Europe means continental Europe excluding DACH and UK/Ireland excluded.
   - NA means North America (US, Canada, Mexico).
   - APAC means Asia and Pacific (incl. Australia, Japan, India, etc.).
   - Global means no clear regional anchor.
   Use URL TLD, source domain, place names, and language as signals. \
Optional region hints in the user message may help but are not authoritative.

3. is_relevant — true unless the mention has clearly no process / software / \
AI / automation / transformation angle. Default to true when in doubt.

4. reasoning — one short sentence (max 25 words). Cite the wording you saw.

RULES:
- Stay strictly within the allowed themes and regions.
- Do not invent or rename categories.
- Do not use prior knowledge about the company. Only use the provided text.
- A SEO ranking mention is implicitly relevant; focus on classifying the \
keyword's theme.
"""


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

_MAX_CONTENT_CHARS = 2000


def build_classification_messages(
    mention: Mention,
    *,
    region_hint: str | None = None,
    theme_hint: str | None = None,
) -> list[dict]:
    """Build the messages list for one classification call.

    Pass to a ChatOpenAI .with_structured_output(SovClassificationOutput).ainvoke().

    Args:
        mention:      The Mention to classify (only fields up to `language`
                      should be populated; theme/region/etc are what we're
                      filling in).
        region_hint:  Optional cheap pre-classification (e.g. from URL TLD).
                      Surfaced to the LLM as advisory.
        theme_hint:   Optional theme hint, e.g. the SEO keyword for SEO mentions.

    Returns:
        Two-message list ready for ainvoke().
    """
    content = (mention.content or "(no body content)")
    if len(content) > _MAX_CONTENT_CHARS:
        content = content[:_MAX_CONTENT_CHARS] + " […]"

    user_msg = (
        f"COMPANY: {mention.company}\n"
        f"SOURCE: {mention.source_type} ({mention.source})\n"
        f"PUBLISHED: {mention.date.isoformat()}\n"
        f"LANGUAGE: {mention.language or 'unknown'}\n"
        f"URL: {mention.url}\n\n"
        f"TITLE:\n{mention.title}\n\n"
        f"CONTENT:\n{content}\n\n"
        f"HINTS (advisory, may be ignored):\n"
        f"- region_hint: {region_hint or 'none'}\n"
        f"- theme_hint: {theme_hint or 'none'}\n"
    )

    return [
        {"role": "system", "content": SOV_CLASSIFICATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
