"""backend/app/prompts/brand/geo_synthesis.py

Prompt template and Pydantic output schema for the GEO synthesis narrative.

Uses with_structured_output(strict=True) to guarantee schema compliance.
The narrative field is a free-form string — synthesis cannot be enum-constrained,
but the surrounding metadata fields are enforced by the schema.

Issue #90: GEO Intelligence backend
"""

import json
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class GeoSynthesisOutput(BaseModel):
    """Structured synthesis of all keyword analysis results.

    Uses structured chain-of-thought: the model works through seven analytical
    steps before writing the narrative. Each reasoning field anchors the next.
    The narrative is written last and must be consistent with all prior fields.

    Reasoning fields are stored — they feed the frontend's strategic maps
    and are valuable data beyond the narrative text.
    """

    # ------------------------------------------------------------------
    # Reasoning Step 1 — Landscape read
    # What is the overall picture before any interpretation?
    # ------------------------------------------------------------------

    landscape_observation: str = Field(
        description=(
            "Before any interpretation: state the raw numbers. "
            "How many keywords in total? How many had a mention? "
            "Which tier had the highest mention rate? "
            "What was the most common framing across all mentions? "
            "2 to 3 factual sentences. No interpretation yet."
        )
    )

    # ------------------------------------------------------------------
    # Reasoning Step 2 — Territory mapping
    # Where does the brand own, contest, or lose the conversation?
    # ------------------------------------------------------------------

    owned_territories: list[str] = Field(
        description=(
            "Use cases or keyword clusters where the target company appears "
            "with recommendation_strength of 'recommended' or 'organic'. "
            "These are the territories the brand owns in AI perception. "
            "List them in 3 to 8 words each. Return empty list if none."
        )
    )

    contested_territories: list[str] = Field(
        description=(
            "Use cases or keyword clusters where the target company appears "
            "but only as 'listed' or 'attributed' — present but not dominant. "
            "These are contested territories. "
            "List them in 3 to 8 words each. Return empty list if none."
        )
    )

    absent_territories: list[str] = Field(
        description=(
            "Use cases or keyword clusters where the target company does NOT "
            "appear at all, but where competitor companies do appear. "
            "Derive from use_case_context fields of non-mentions combined "
            "with co_mentioned_companies of those keywords. "
            "These are lost territories. List in 3 to 8 words each. "
            "Return empty list if no clear absent territory emerges."
        )
    )

    # ------------------------------------------------------------------
    # Reasoning Step 3 — Peer group analysis
    # Who does AI associate with this brand — and is that right?
    # ------------------------------------------------------------------

    primary_peer_group: list[str] = Field(
        description=(
            "The 3 to 5 companies that appear most frequently alongside the "
            "target company across all keyword results. "
            "Count co_mentioned_companies occurrences and rank by frequency. "
            "These are who AI considers the target's natural peers."
        )
    )

    peer_group_assessment: str = Field(
        description=(
            "Are the primary peers the strategically correct comparison set? "
            "If a process mining company is grouped with BI tools, that is wrong. "
            "If it is grouped with direct competitors, that is correct. "
            "1 to 2 sentences. Be specific about which companies and why the "
            "grouping is correct or incorrect."
        )
    )

    # ------------------------------------------------------------------
    # Reasoning Step 4 — Critical gap with competitive context
    # The most strategically important absent territory, with owner named.
    # ------------------------------------------------------------------

    critical_gap: str = Field(
        description=(
            "The single most strategically important territory where the target "
            "company is absent but a specific competitor is strong. "
            "Format: '[territory] — owned by [competitor]'. "
            "Example: 'mid-market SAP migration — owned by SAP Signavio'. "
            "This must come from the data, not inference. "
            "If no clear critical gap exists, write 'no critical gap identified'."
        )
    )

    # ------------------------------------------------------------------
    # Reasoning Step 5 — Counter-positioning pattern
    # What criticism does AI consistently attach to this brand?
    # ------------------------------------------------------------------

    counter_positioning_theme: str | None = Field(
        description=(
            "The most consistent criticism, limitation, or negative qualifier "
            "attached to the target company across all mentions. "
            "Look for recurring themes in counter_positioning fields. "
            "Examples: 'enterprise-only positioning', 'cost concerns for mid-market', "
            "'implementation complexity'. "
            "State the theme in 5 to 15 words. "
            "Return null if fewer than 2 keywords surfaced a criticism."
        )
    )

    # ------------------------------------------------------------------
    # Reasoning Step 6 — Framing gap
    # Is the brand framed at the right strategic level?
    # ------------------------------------------------------------------

    framing_gap: str | None = Field(
        description=(
            "If the dominant framing is 'technical' but the company positions "
            "itself as 'strategic' or 'visionary' in its own messaging, "
            "describe the gap in 1 sentence. "
            "Example: 'AI perceives Celonis as a technical tool while the "
            "company claims strategic transformation leadership.' "
            "Return null if framing is aligned or data is insufficient."
        )
    )

    # ------------------------------------------------------------------
    # Step 7 — Narrative (written last, anchored to all steps above)
    # This is what the CMO reads.
    # ------------------------------------------------------------------

    narrative: str = Field(
        description=(
            "Strategic brand briefing in plain English prose. "
            "300 to 450 words. No bullet points, no headers, no markdown. "
            "Written for the CMO and Brand Strategy lead. "
            "Must flow through: landscape numbers → owned territory → "
            "contested territory → absent territory (with competitor names) → "
            "peer group assessment → counter-positioning → framing gap → "
            "single most important strategic implication. "
            "Every sentence must be grounded in your reasoning steps above. "
            "Do not introduce information not present in your prior fields. "
            "Forbidden: 'room to grow', 'opportunity for improvement', "
            "'it is worth noting', 'this analysis shows', 'in conclusion', "
            "'the brand has potential'."
        )
    )

    # ------------------------------------------------------------------
    # Calculated metadata (for KPI tiles in frontend)
    # ------------------------------------------------------------------

    mention_rate: float = Field(
        description=(
            "Fraction of total keywords where the target company was mentioned. "
            "Between 0.0 and 1.0. Calculated from landscape_observation data."
        )
    )

    dominant_framing: Literal["technical", "strategic", "visionary"] | None = Field(
        description=(
            "Most frequent framing across all mentions. "
            "Return null if fewer than 3 mentions had a classified framing."
        )
    )

    strongest_tier: Literal["brand_category", "use_case", "competitor_trigger"] | None = Field(
        description=(
            "Keyword tier with the highest mention rate. "
            "Return null if data is insufficient to determine."
        )
    )

    top_counter_positioning: str | None = Field(
        description=(
            "Copy of counter_positioning_theme, condensed to 3 to 12 words. "
            "Used for the KPI tile. Return null if counter_positioning_theme is null."
        )
    )

    gap_keyword_count: int = Field(
        description=(
            "Number of keywords where the target company was not mentioned at all."
        )
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

GEO_SYNTHESIS_SYSTEM_PROMPT = """\
You are a senior brand strategist with 15 years of B2B software brand analysis. \
You have been commissioned to produce a strategic AI search visibility briefing \
for the executive team of a B2B software company.

You will receive structured data from a GEO Intelligence run: one record per \
keyword tested, each containing presence, framing, competitor co-mentions, \
use case context, and counter-positioning signals.

You work through the analysis in seven explicit steps before writing the \
narrative. Each step is a field you fill in order. The narrative is written \
last and must be fully anchored in your prior reasoning — introduce no new \
information in the narrative that is not already present in your reasoning fields.

HOW A BRAND ANALYST THINKS:

Step 1 — Read the landscape before interpreting it. \
Count first. What are the raw numbers? Which tier performs best? \
What framing dominates? Do not interpret yet.

Step 2 — Map the territory. \
Separate keywords into three buckets: owned (strong recommendation), \
contested (present but weak), absent (not mentioned). \
The absent bucket is the most strategically important.

Step 3 — Analyse the peer group. \
Who does AI place this brand alongside? Is that the right company? \
Being grouped with BI tools when you are a process mining platform is a \
strategic signal — AI has misclassified your category.

Step 4 — Find the critical gap. \
Of all absent territories, which one hurts most strategically? \
Name it precisely and name the competitor who owns it instead.

Step 5 — Surface the counter-positioning pattern. \
If three or more keywords surfaced the same criticism, that is a pattern. \
"Expensive" repeated across keywords is not noise — it is what AI has learned \
about the brand from millions of web documents.

Step 6 — Assess the framing gap. \
Compare the dominant framing in the data against what the company claims \
about itself. If they claim "strategic transformation platform" but AI \
consistently says "process mining tool", that gap is the most actionable \
finding in the entire briefing.

Step 7 — Write the narrative. \
Only now write the 300 to 450 word prose briefing. \
Every claim must trace back to a specific reasoning field above. \
No new data, no hedging, no generic observations.

ABSOLUTE RULES:

1. Fill all reasoning fields before the narrative field.

2. Name competitors by name in every field where they are relevant. \
"A competitor" is not acceptable. "SAP Signavio" is.

3. Cite specific numbers in the narrative. \
"14 of 30 keywords" beats "frequently mentioned".

4. The following phrases are banned from the narrative: \
"room to grow", "opportunity for improvement", "it is worth noting", \
"this analysis shows", "in conclusion", "the brand has potential", \
"AI search is increasingly important", "our analysis reveals".

5. Do not fabricate patterns. If counter-positioning data is thin, \
write "no consistent counter-positioning pattern in this dataset". \
Never invent criticisms.

6. The narrative is for a CMO who has already read the data. \
Do not re-summarise the numbers — interpret them.
"""


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

def build_geo_synthesis_messages(
    sightings: list[dict[str, Any]],
    target_company: str,
    total_keywords: int,
) -> list[dict]:
    """Build the messages list for the synthesis call.

    Args:
        sightings:      List of per-keyword analysis results. Each entry
                        should include: keyword, tier, mentioned, framing,
                        recommendation_strength, use_case_context,
                        counter_positioning, co_mentioned_companies.
        target_company: The company being analysed, e.g. "Celonis".
        total_keywords: Total number of keywords in the run (including
                        those with no mention).

    Returns:
        Messages list for the LLM call.
    """
    payload = {
        "target_company": target_company,
        "total_keywords_tested": total_keywords,
        "results": sightings,
    }
    user_content = (
        f"Here is the dataset for your strategic briefing.\n\n"
        f"{json.dumps(payload, indent=2, default=str)}\n\n"
        f"Write the structured output now."
    )
    return [
        {"role": "system", "content": GEO_SYNTHESIS_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
