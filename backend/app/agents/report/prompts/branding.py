"""Prompt builder for the Visual Branding competitive intelligence report."""

import json
from datetime import date


def build_branding_prompt(data: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the branding report."""

    # Branding has no companies array — use the most recent node run_at
    latest_run = max(
        (v["run_at"] for v in data.values() if isinstance(v, dict) and "run_at" in v),
        default=str(date.today())
    )[:10]

    system_prompt = """You are a competitive intelligence analyst at Celonis.
Your job is to write concise, executive-ready reports based on visual branding analysis data.
The data covers color, font, and imagery trends across all tracked competitors.

Rules:
- Focus on industry-wide visual trends and where Celonis sits relative to them
- Use the data collection date as your reference point for assessing recency
- Every insight must include a "so what" for Celonis
- Be direct and opinionated. Avoid filler phrases like "it is worth noting that"
- Output clean Markdown with clear sections
- Maximum 600 words"""

    user_prompt = f"""Analyze the following visual branding intelligence data and write a competitive intelligence report.

Data collection date: {latest_run} — use this as your "today" reference point when assessing recency.

Data:
{json.dumps(data, indent=2, ensure_ascii=False)}

Write a report with exactly these sections:

## Executive Summary
2-3 sentences. What is the dominant visual direction in this competitive set, and is Celonis aligned or differentiated?

## Color & Font Trends
What are competitors converging on? What does this signal about how the industry wants to be perceived?

## Imagery & Style Trends
What visual styles are rising or falling? Which competitors are setting the visual agenda?

## Celonis's Visual Position
Based on the data, is Celonis's visual identity a strength or a risk? Where is it distinctive, where does it blend in?

## Implications for Celonis
What should the brand team consider acting on based on this competitive visual intelligence?"""

    return system_prompt, user_prompt