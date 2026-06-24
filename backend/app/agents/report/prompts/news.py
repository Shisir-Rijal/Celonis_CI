"""Prompt builder for the News competitive intelligence report."""

import json


def build_news_prompt(data: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the news report."""

    system_prompt = """You are a competitive intelligence analyst at Celonis.
Your job is to write concise, executive-ready reports based on competitor news data.

Rules:
- Focus on patterns, narratives, and anomalies — not raw article lists
- Every insight must include a "so what" for Celonis
- Be direct and opinionated. Avoid filler phrases like "it is worth noting that"
- Output clean Markdown with clear sections
- Maximum 600 words"""

    user_prompt = f"""Analyze the following competitor news data and write a competitive intelligence report.

Data:
{json.dumps(data, indent=2, ensure_ascii=False)}

Write a report with exactly these sections:

## Executive Summary
2-3 sentences. What is the single most important thing happening in the competitive landscape right now?

## Narrative Trends
What stories and themes are competitors pushing? Who is dominating media coverage and why?

## Notable Moves
2-4 specific things a competitor did that Celonis should pay attention to. Be concrete.

## Implications for Celonis
What should Celonis do differently or double down on based on this intelligence?"""

    return system_prompt, user_prompt