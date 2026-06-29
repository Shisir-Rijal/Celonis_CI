"""backend/app/agents/sov/state.py

State schema for the Share-of-Voice agent.

A SoV run loads mentions from research_snapshots (and brand_geo_sightings if
ever extended), enriches them with theme / region / relevance classifications
via LLM, and persists them to sov_mentions.

The Mention model is the unit of work that flows through the pipeline:
load_mentions builds them, classify fills in themes/region/is_relevant,
persist writes them to the database.

SovPipelineState is the LangGraph state container that carries the in-flight
mentions between nodes.
"""

from datetime import date, datetime
from typing import Annotated, Literal, TypedDict
import operator

from pydantic import BaseModel

from app.agents.sov.themes import Theme


# ---------------------------------------------------------------------------
# Region vocabulary
# ---------------------------------------------------------------------------
# SEO mentions are always Global (Google rankings in this project are not
# locale-scoped). News mentions get a region inferred from language + domain
# heuristics with an LLM fallback.

Region = Literal["DACH", "Europe", "NA", "APAC", "Global"]


# ---------------------------------------------------------------------------
# Mention — the unit of work
# ---------------------------------------------------------------------------

class Mention(BaseModel):
    """One classified mention of a competitor in a single piece of content.

    Fields are populated in two phases:
    - load_mentions sets everything down to `language`
    - classify fills in `themes`, `region`, `is_relevant`, `reasoning`
    """

    # --- always set by load_mentions ---
    company: str
    source_type: Literal["news", "seo"]
    source: str                         # e.g. 'finnhub' | 'serper' | 'firecrawl' | 'google_serp'
    title: str
    content: str | None = None
    date: date                          # publication date (or research run date for SEO)
    month_bucket: str                   # 'YYYY-MM', derived from date
    url: str
    language: str | None = None

    # --- filled in by classify ---
    themes: list[Theme] = []
    region: Region | None = None
    is_relevant: bool | None = None
    reasoning: str | None = None


# ---------------------------------------------------------------------------
# SovPipelineState — LangGraph state container
# ---------------------------------------------------------------------------

class SovPipelineState(TypedDict):
    """Shared state for the SoV LangGraph pipeline.

    Fields
    ------
    run_at:
        Timestamp at which this run started. Stamped onto every persisted row.
    companies:
        Active competitor domains loaded from the `competitors` table at the
        start of the run.
    candidate_mentions:
        Mentions loaded from research_snapshots, with URLs that are not yet
        present in sov_mentions. Populated by load_mentions_node.
    classified_mentions:
        Same mentions, enriched with themes / region / is_relevant.
        Populated by classify_node.
    persisted_count:
        Number of rows successfully inserted by persist_node.
    errors:
        Additive list — each node appends its own errors without overwriting
        errors from other nodes.
    """

    run_at: datetime
    companies: list[str]
    candidate_mentions: list[Mention]
    classified_mentions: list[Mention]
    persisted_count: int
    errors: Annotated[list[str], operator.add]
