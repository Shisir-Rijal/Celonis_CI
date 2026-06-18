"""backend/scripts/test_geo_prompts.py

Dummy test to validate GEO analysis and synthesis prompts.

Sends one real keyword to GPT-4o-mini, then runs the structured
analysis on the response. Prints the full GeoAnalysisOutput so we
can validate the prompt quality before building the node.

Run:
    uv run python scripts/test_geo_prompts.py --keyword "process mining"
    uv run python scripts/test_geo_prompts.py --keyword "process mining" --company SAP
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_openai import ChatOpenAI
from app.config import get_settings
from app.prompts.brand.geo_analysis import (
    GeoAnalysisOutput,
    GEO_ANALYSIS_SYSTEM_PROMPT,
    build_geo_analysis_messages,
)


async def run_geo_query(keyword: str, company: str) -> str:
    """Step 1: Ask GPT what companies are known for this keyword."""
    settings = get_settings()
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
    )
    response = await llm.ainvoke([
        {
            "role": "system",
            "content": "Answer concisely. List the main companies or products known for this topic.",
        },
        {
            "role": "user",
            "content": f"Which companies or platforms are the leading providers for: {keyword}?",
        },
    ])
    return response.content


async def run_geo_analysis(
    keyword: str,
    geo_response: str,
    company: str,
) -> GeoAnalysisOutput:
    """Step 2: Analyse the GEO response with structured output."""
    settings = get_settings()
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
    )
    structured_llm = llm.with_structured_output(
        GeoAnalysisOutput,
        method="json_schema",
        strict=True,
    )
    messages = build_geo_analysis_messages(keyword, geo_response, company)
    result: GeoAnalysisOutput = await structured_llm.ainvoke(messages)
    return result


async def main(keyword: str, company: str) -> None:
    print(f"\nKeyword : {keyword}")
    print(f"Company : {company}")
    print("=" * 60)

    print("\n[1/2] Sending GEO query to GPT-4o-mini...")
    geo_response = await run_geo_query(keyword, company)
    print(f"\nRaw LLM response:\n{geo_response}")

    print("\n[2/2] Running structured analysis...")
    analysis = await run_geo_analysis(keyword, geo_response, company)

    print("\nStructured output:")
    print(json.dumps(analysis.model_dump(), indent=2, default=str))

    print("\nQuick summary:")
    print(f"  mentioned           : {analysis.target_mentioned}")
    print(f"  framing             : {analysis.framing}")
    print(f"  recommendation      : {analysis.recommendation_strength}")
    print(f"  use_case            : {analysis.use_case_context}")
    print(f"  counter_positioning : {analysis.counter_positioning}")
    print(f"  co_mentioned        : {analysis.co_mentioned_companies}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", default="process mining")
    parser.add_argument("--company", default="Celonis")
    args = parser.parse_args()

    asyncio.run(main(args.keyword, args.company))
