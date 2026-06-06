"""backend/app/models/topics.py

Controlled topic vocabulary for Brand Intelligence.

Every Brand Capability uses these labels when categorising output data.
Using a fixed list ensures consistent filtering across capabilities and
future dashboard queries.

Both Nadja's RAG export (Issue #73) and Brand Capabilities import from here.
Do not use free-text topics elsewhere — add to this list instead.

Issue #87: CapabilityResult schema and topic vocabulary for Brand Pipeline
"""

TOPICS: list[str] = [
    # Content types
    "news",
    "press_release",
    "newsletter",
    "social",
    "video",
    "events",
    # Brand & positioning
    "positioning",
    "values",
    "mission",
    "employer_brand",
    "tone_of_voice",
    # Business signals
    "funding",
    "product_launch",
    "partnership",
    "earnings",
    # Brand analysis outputs
    "ai_search",
    "brand_analysis",
]
