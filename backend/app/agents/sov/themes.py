"""backend/app/agents/sov/themes.py

Single source of truth for the theme taxonomy used by the Share-of-Voice agent.

The same vocabulary appears in three places downstream:
- the Pydantic classification schema (Literal type for strict LLM output)
- the LLM prompt text (so the model sees the allowed values)
- API-side validation (when filtering mentions by theme)

To add or rename a theme, change THEMES here — Theme below picks up the change
automatically via typing.Literal.
"""

from typing import Literal, get_args


# ---------------------------------------------------------------------------
# Theme vocabulary
# ---------------------------------------------------------------------------
# Oriented on the GEO brand keywords but kept intentionally small (~10 items).
# "Other" is the fallback bucket for mentions that do not fit anywhere else.

Theme = Literal[
    "Process Mining",
    "Process Intelligence",
    "AI & GenAI",
    "Agentic AI",
    "Automation",
    "Digital Transformation",
    "Supply Chain",
    "ERP & SAP",
    "Other",
]

# Runtime list, derived from the Literal type so the two can never drift apart.
THEMES: list[str] = list(get_args(Theme))
