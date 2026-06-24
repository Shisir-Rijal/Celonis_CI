"""Prompt builder for the Events competitive intelligence report."""

import json


def build_events_prompt(data: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the events report."""

    system_prompt = """You are a competitive intelligence analyst at Celonis.
Your job is to write concise, executive-ready reports based on competitor events data.

Rules:
- Focus on patterns and strategic intent behind event choices — not a list of events
- Every insight must include a "so what" for Celonis
- Be direct and opinionated. Avoid filler phrases like "it is worth noting that"
- Output clean Markdown with clear sections
- Maximum 600 words"""

    user_prompt = f"""Analyze the following competitor events data and write a competitive intelligence report.

Data:
{json.dumps(data, indent=2, ensure_ascii=False)}

Write a report with exactly these sections:

## Executive Summary
2-3 sentences. What does the overall events landscape tell us about where competitors are investing?

## Event Strategy Patterns
Which competitors are most active? What topics and formats are they prioritizing? Are there geographic concentrations?

## Whitespace Opportunities
What topics, regions, or audiences are underserved by competitor events that Celonis could own?

## Implications for Celonis
Concrete recommendations for Celonis's own events strategy based on this intelligence."""

    return system_prompt, user_prompt