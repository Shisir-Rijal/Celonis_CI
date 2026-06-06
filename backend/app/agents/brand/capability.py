"""backend/app/agents/brand/capability.py

Shared output schema for Brand Intelligence Capability agents.

Every capability returns a CapabilityResult. The structured data goes
into the capability's own Supabase table. The run_at field enables
delta tracking — compare two run_at values to see what changed.

Issue #87: CapabilityResult schema and topic vocabulary for Brand Pipeline
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CapabilityResult(BaseModel):
    """Output schema for every Brand Intelligence Capability.

    Fields
    ------
    capability:
        Name of the capability that produced this result,
        e.g. "ai_search_coherence".
    company:
        Domain of the analysed competitor, e.g. "sap.com".
    run_at:
        When this result was produced. Defaults to now.
        Used for delta tracking — compare two run_at values.
    data:
        Structured output written to the capability's Supabase table.
        Schema is defined by each capability individually.
    error:
        Set if the capability failed. None on success.
    """

    capability: str
    company: str
    run_at: datetime = Field(default_factory=datetime.utcnow)
    data: dict[str, Any] = {}
    error: str | None = None
