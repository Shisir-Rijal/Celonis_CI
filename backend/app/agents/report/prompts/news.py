"""Prompt builder for the News competitive intelligence report."""

import json


def build_news_prompt(data: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the news report."""

    system_prompt = """You are a competitive intelligence analyst at Celonis.
Your job is to write concise, executive-ready reports based on competitor news data.

Rules:
- Use topic tags to identify thematic patterns across competitors
- Prioritize insights from firecrawl (official) sources over serper (third-party media)
- Every insight must include a "so what" for Celonis
- Be direct and opinionated. Avoid filler phrases like "it is worth noting that"
- Output clean Markdown with clear sections
- Maximum 600 words"""

    user_prompt = f"""Analyze the following competitor news data and write a competitive intelligence report.

Each article has a source_type (firecrawl = official company source, finnhub = financial media, serper = third-party media)
and topic tags (e.g. Product Launch, Partnership, AI & Technology).

Data:
{json.dumps(data, indent=2, ensure_ascii=False)}

Write a report with exactly these sections:

## Executive Summary
2-3 sentences. What is the single most important thing happening in the competitive landscape right now?

## Narrative Trends
What stories and themes are competitors pushing? Use the topic_summary data to identify which topics
are most active across the competitive set.

## Notable Moves
2-4 specific things a competitor did that Celonis should pay attention to.
Prioritize insights from official sources (firecrawl). Be concrete.

## Implications for Celonis
What should Celonis do differently or double down on based on this intelligence?"""

    return system_prompt, user_prompt