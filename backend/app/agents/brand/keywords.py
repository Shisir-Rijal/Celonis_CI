"""backend/app/agents/brand/keywords.py

Three-tier brand keyword vocabulary for GEO Intelligence analysis.

Tier 1 — Brand & Category: are we recognised by name in our core space?
Tier 2 — Use-Case / Problem: do we get picked when users describe a problem?
Tier 3 — Competitor Trigger: are we named as an alternative to competitors?

Issue #90: GEO Intelligence backend
"""

# ---------------------------------------------------------------------------
# Tier 1 — Brand & Category Keywords
# Celonis's core positioning territory. Validates dominance and reveals
# which peer group AI places Celonis in.
# ---------------------------------------------------------------------------

BRAND_CATEGORY_KEYWORDS: list[str] = [
    "process mining",
    "process intelligence platform",
    "object centric process mining",
    "process mining tools",
    "process mining software comparison",
    "AI process intelligence",
    "enterprise AI platform",
    "agentic process automation",
    "digital transformation platform",
    "business process automation enterprise",
    "operational efficiency AI",
    "digital twin process mining",
    "process mining for SAP",
    "business process management software",
    "process analytics platform",
]

# ---------------------------------------------------------------------------
# Tier 2 — Use-Case / Problem Keywords
# Users who do not know Celonis describe their problem.
# Reveals territory ownership — who gets recommended when no brand is named.
# ---------------------------------------------------------------------------

USE_CASE_KEYWORDS: list[str] = [
    "how to find bottlenecks in supply chain",
    "what software helps reduce manufacturing downtime",
    "how to automate order to cash process",
    "how to identify inefficiencies in procurement",
    "how to measure operational efficiency in finance",
    "best way to digitize manual workflows enterprise",
    "how to improve business processes after merger",
    "tool to analyse customer journey friction",
    "how to use AI for process optimization in manufacturing",
    "how to consolidate business processes across SAP systems",
]

# ---------------------------------------------------------------------------
# Tier 3 — Competitor Trigger Keywords
# Captures contexts where Celonis should appear as an alternative.
# Reveals whether Celonis wins competitive consideration or is invisible.
# ---------------------------------------------------------------------------

COMPETITOR_TRIGGER_KEYWORDS: list[str] = [
    "SAP Signavio alternatives",
    "ServiceNow workflow automation alternatives",
    "IBM process mining alternatives",
    "UiPath process mining comparison",
    "Appian vs process mining tools",
]

# ---------------------------------------------------------------------------
# Combined set (used by default when running full analysis)
# ---------------------------------------------------------------------------

ALL_BRAND_KEYWORDS: list[str] = (
    BRAND_CATEGORY_KEYWORDS
    + USE_CASE_KEYWORDS
    + COMPETITOR_TRIGGER_KEYWORDS
)

# Tier label map for tagging rows in brand_geo_sightings
KEYWORD_TIER: dict[str, str] = {
    **{kw: "brand_category" for kw in BRAND_CATEGORY_KEYWORDS},
    **{kw: "use_case" for kw in USE_CASE_KEYWORDS},
    **{kw: "competitor_trigger" for kw in COMPETITOR_TRIGGER_KEYWORDS},
}
