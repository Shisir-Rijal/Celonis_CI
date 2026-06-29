"""Prompt builder for the GEO Intelligence competitive intelligence report."""

import json


def build_geo_prompt(data: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the GEO report."""

    latest_run = max(
        (c["run_at"] for c in data.get("companies", [])),
        default="unknown"
    )[:10]

    system_prompt = """You are a competitive intelligence analyst at Celonis.
Your job is to write concise, executive-ready reports based on GEO (Generative Engine Optimization) data.
GEO measures how often and how favorably AI models mention and recommend each competitor.

Rules:
- Lead with Celonis's position relative to competitors — that is what matters most
- Use the data collection date as your reference point for assessing recency
- Every insight must include a "so what" for Celonis
- Be direct and opinionated. Avoid filler phrases like "it is worth noting that"
- Output clean Markdown with clear sections
- Maximum 600 words"""

    user_prompt = f"""Analyze the following GEO intelligence data and write a competitive intelligence report.

Data collection date: {latest_run} — use this as your "today" reference point when assessing recency.

Data:
{json.dumps(data, indent=2, ensure_ascii=False)}

Write a report with exactly these sections:

## Executive Summary
2-3 sentences. Where does Celonis stand in AI-generated recommendations compared to its competitors?

## GEO Leaderboard
Rank competitors by geo_score. For each, briefly explain what is driving their score — framing, territories, narrative strength.

## Celonis's Gaps
What owned, contested, or absent territories explain Celonis's current score? What is the critical gap?

## Implications for Celonis
What specific actions would move Celonis's GEO score — content strategy, framing changes, territory focus?"""

    return system_prompt, user_prompt