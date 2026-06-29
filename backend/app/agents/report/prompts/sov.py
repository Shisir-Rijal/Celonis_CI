"""Prompt builder for the Share of Voice competitive intelligence report."""

import json


def build_sov_prompt(data: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the SOV report."""

    latest_run = max(
        (c["latest_month"] for c in data.get("companies", []) if c.get("latest_month")),
        default="unknown"
    )

    system_prompt = """You are a competitive intelligence analyst at Celonis.
Your job is to write concise, executive-ready reports based on Share of Voice (SOV) data.
SOV measures how often and in what context each competitor appears across news and SEO sources.

Rules:
- Lead with Celonis's share of voice position relative to competitors
- Use theme and region data to identify where competitors dominate and where Celonis has gaps
- Every insight must include a "so what" for Celonis
- Be direct and opinionated. Avoid filler phrases like "it is worth noting that"
- Output clean Markdown with clear sections
- Maximum 600 words"""

    user_prompt = f"""Analyze the following Share of Voice data and write a competitive intelligence report.

Data period: {latest_run} — use this as your reference point for recency.
Each company entry includes total mentions, relevant mentions, relevance rate,
theme distribution, and regional spread across news and SEO sources.

Data:
{json.dumps(data, indent=2, ensure_ascii=False)}

Write a report with exactly these sections:

## Executive Summary
2-3 sentences. How does Celonis's share of voice compare to the competitive set overall?

## SOV Leaderboard
Rank competitors by relevant_mentions. For each, highlight their dominant themes and regions.

## Theme Analysis
Which themes are competitors owning? Where is Celonis present and where is it absent?

## Regional Gaps
Which regions are underserved by Celonis compared to competitors?

## Implications for Celonis
What content, PR, or SEO actions would improve Celonis's share of voice most effectively?"""

    return system_prompt, user_prompt