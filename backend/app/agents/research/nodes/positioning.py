import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import asyncio
import structlog
import httpx
import json
from openai import AsyncOpenAI
from firecrawl import V1FirecrawlApp as FirecrawlApp
from app.agents.research.state import ResearchState, PositioningData, BlogData
from app.config import get_settings


logger = structlog.get_logger(__name__)


async def _fetch_markdown(query: str, num: int = 3) -> str | None:
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": get_settings().SERPER_API_KEY},
            json={"q": query, "num": num},
            timeout=10,
        )
    results = resp.json().get("organic", [])
    for r in results:
        try:
            scraped = await asyncio.to_thread(app.scrape_url, r["link"], formats=["markdown"])
            md = getattr(scraped, "markdown", None)
            if md:
                return md
        except Exception:
            continue
    return None


async def _extract_about_company(markdown: str, openai: AsyncOpenAI) -> dict:
    resp = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "Extract company positioning from this about OR company page. "
                "Return a JSON object with fields:\n"
                "- purpose: the company's purpose or overarching goal, or null\n"
                "- vision: the future state the company aims for, or null\n"
                "- mission: the company's long-term mission statement, or null\n"
                "- company_values: the company's core values as a service provider — return as a dict {value_name: description}, or null\n"
                "Use null for any field not found on this page."
            )},
            {"role": "user", "content": markdown[:5000]},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


async def _extract_employer(markdown: str, openai: AsyncOpenAI) -> dict:
    resp = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "Extract employer branding information from careers OR jobs page. "
                "Return a JSON object with fields:\n"
                "- employer_values: values the company promotes as an employer — return as a dict {value_name: description}, or null\n"
                "- employer_positioning: a short text describing how the company positions itself as an employer (culture, benefits, work environment), or null\n"
                "- job_positing_employer_description: the exact company description or 'about us' blurb used in job postings, or null\n"
                "Use null for any field not found on this page."
            )},
            {"role": "user", "content": markdown[:5000]},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


async def _scrape_blog_posts(listing_markdown: str, company: str, openai: AsyncOpenAI) -> list | None:
    # Step 1: extract individual blog post URLs from the listing page
    url_resp = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "Extract individual blog post URLs from this blog listing page. "
                "Return a JSON object with key 'urls' containing a list of full URLs (starting with https://). "
                "Only include URLs that link to individual articles, not category or tag pages. Max 5 URLs."
            )},
            {"role": "user", "content": listing_markdown[:4000]},
        ],
        response_format={"type": "json_object"},
    )
    urls: list[str] = json.loads(url_resp.choices[0].message.content).get("urls", [])
    if not urls:
        return None

    # Step 2: scrape each post and extract full content
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)

    async def _scrape_one(url: str) -> BlogData | None:
        try:
            scraped = await asyncio.to_thread(app.scrape_url, url, formats=["markdown"])
            md = getattr(scraped, "markdown", None)
            if not md:
                return None
            resp = await openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "Extract this blog post. Return a JSON object with fields:\n"
                        "- heading: article title\n"
                        "- subheading: subtitle or lead sentence if present, or null\n"
                        "- content: the FULL text of the article — every paragraph and section, not a summary\n"
                        "- publishing_date: YYYY-MM-DD if explicitly stated, null otherwise"
                    )},
                    {"role": "user", "content": md[:10000]},
                ],
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            return BlogData(
                company=company,
                url=url,
                title=data.get("heading"),
                source_type="firecrawl",
                heading=data.get("heading"),
                subheading=data.get("subheading"),
                content=data.get("content"),
                source_link=url,
                publishing_date=data.get("publishing_date"),
            )
        except Exception:
            return None

    results = await asyncio.gather(*[_scrape_one(u) for u in urls[:5]])
    blogs = [r for r in results if r is not None]
    return blogs or None


async def _scrape_positioning(domain: str) -> PositioningData:
    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)

    company = domain.replace(".com", "").replace(".io", "").replace(".de", "")
    about_md, careers_md, blog_md = await asyncio.gather(
        _fetch_markdown(f"site:{domain} about OR company OR mission OR vision OR values"),
        _fetch_markdown(f"{company} careers employer culture benefits site:{domain}"),
        _fetch_markdown(f"site:{domain} blog OR insights OR resources"),
    )

    about_data, employer_data, blogs = await asyncio.gather(
        _extract_about_company(about_md, openai) if about_md else asyncio.sleep(0, result={}),
        _extract_employer(careers_md, openai) if careers_md else asyncio.sleep(0, result={}),
        _scrape_blog_posts(blog_md, company, openai) if blog_md else asyncio.sleep(0, result=None),
    )

    return PositioningData(
        company=company,
        url=f"https://{domain}/about",
        title=f"Positioning: {company}",
        source_type="serper+firecrawl",
        purpose=about_data.get("purpose"),
        vision=about_data.get("vision"),
        mission=about_data.get("mission"),
        company_values=about_data.get("company_values"),
        employer_values=employer_data.get("employer_values"),
        employer_positioning=employer_data.get("employer_positioning"),
        job_positing_employer_description=employer_data.get("job_positing_employer_description"),
        blogs=blogs,
    )


async def run(state: ResearchState) -> dict:
    domain = state["competitor_domain"]
    try:
        data = await _scrape_positioning(domain)
        return {
            "positioning": data,
            "completed_nodes": ["positioning"],
        }
    except Exception as e:
        logger.error("node_failed", node="positioning", error=str(e))
        return {"errors": [f"positioning: {e}"]}


if __name__ == "__main__":
    import asyncio
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main():
        from app.agents.research.state import VisualsData, FinancialData, SocialData, SeoGeoData, NewsData, EventsData, NewsletterData

        state = ResearchState(
            competitor_domain="ibm.com",
            visuals=VisualsData(),
            positioning=PositioningData(),
            financials=FinancialData(),
            socials=SocialData(),
            seogeo=SeoGeoData(),
            news=NewsData(),
            events=EventsData(),
            newsletter=NewsletterData(),
            errors=[],
            completed_nodes=[],
        )
        result = await run(state)
        if result.get("errors"):
            print("Errors:", result["errors"])
        else:
            print(result["positioning"].model_dump_json(indent=2))

    asyncio.run(main())