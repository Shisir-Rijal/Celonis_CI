import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.agents.research.state import ResearchState, EventsData
from app.config import get_settings
from pydantic import BaseModel
from firecrawl import FirecrawlApp
import json
import asyncio
from openai import AsyncOpenAI
import structlog
import httpx
from datetime import date


logger = structlog.get_logger(__name__)
today = date.today().strftime("%Y-%m-%d")


class EventItem(BaseModel):
    name: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    attendees: int | None = None
    location: str | None = None
    topic: str | None = None
    organized_by: str | None = None
    sponsors: str | None = None
    speakers: str | None = None
    agenda: str | None = None
    summary: str | None = None
    source: str | None = None
    source_link: str | None = None
    image: str | None = None
    video: str | None = None
    date: str | None = today


def _extract_event_items(raw_items: list[dict], source: str) -> list[EventItem]:
    return [
        EventItem(
            name=item.get("name"),
            start_date=item.get("start_date"),
            end_date=item.get("end_date"),
            start_time=item.get("start_time"),
            end_time=item.get("end_time"),
            attendees=item.get("attendees"),
            location=item.get("location"),
            topic=item.get("topic"),
            organized_by=item.get("organized_by"),
            sponsors=item.get("sponsors"),
            speakers=item.get("speakers"),
            agenda=item.get("agenda"),
            summary=item.get("summary"),
            source=source,
            source_link=item.get("source_link"),
            image=item.get("image"),
            video=item.get("video"),
        )
        for item in raw_items
    ]


async def _openai_extract_events(content: str, openai: AsyncOpenAI) -> list[dict]:
    response = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "Extract all events from this text. "
                "Return a JSON object with key 'events' containing a list. "
                "Each event has fields: name, start_date, end_date, start_time, end_time, "
                "attendees, location, topic, organized_by, speakers, agenda, summary, source_link. "
                "Use null if a field is not found."
            )},
            {"role": "user", "content": content[:4000]},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content).get("events", [])


# --- Quelle 1: Company-Website ---

async def _scrape_events_from_domain(domain: str, openai: AsyncOpenAI) -> list[EventItem]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": get_settings().SERPER_API_KEY},
            json={"q": f"site:{domain} events OR webinars OR conference", "num": 1},
            timeout=10,
        )
    results = response.json().get("organic", [])
    if not results:
        return []

    url = results[0]["link"]
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    result = await asyncio.to_thread(app.scrape_url, url, formats=["markdown"])
    if not result.markdown:
        return []

    items = await _openai_extract_events(result.markdown, openai)
    return _extract_event_items(items, source="website")


# --- Quelle 2: Meetup + Luma + Google Events + News ---

async def _scrape_events_from_others(domain: str, openai: AsyncOpenAI) -> list[EventItem]:
    company = domain.replace(".com", "").replace(".io", "")
    all_events: list[EventItem] = []

    # Meetup und Luma: Serper findet URL → Firecrawl scraped Seite
    platform_queries = {
        "meetup": f"{company} site:meetup.com",
        "luma": f"{company} site:lu.ma",
    }
    async with httpx.AsyncClient() as client:
        for source, query in platform_queries.items():
            response = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": get_settings().SERPER_API_KEY},
                json={"q": query, "num": 1},
                timeout=10,
            )
            results = response.json().get("organic", [])
            if not results:
                continue

            url = results[0]["link"]
            app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
            scraped = await asyncio.to_thread(app.scrape_url, url, formats=["markdown"])
            if not scraped.markdown:
                continue

            items = await _openai_extract_events(scraped.markdown, openai)
            all_events += _extract_event_items(items, source=source)

    # Google allgemein: Snippets direkt an OpenAI (kein Firecrawl nötig)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": get_settings().SERPER_API_KEY},
            json={"q": f"{company} upcoming events conference webinar 2025", "num": 5},
            timeout=10,
        )
    snippets = "\n".join(
        f"{r.get('title', '')}: {r.get('snippet', '')}"
        for r in response.json().get("organic", [])
    )
    if snippets:
        items = await _openai_extract_events(snippets, openai)
        all_events += _extract_event_items(items, source="google")

    # News über Events der Company
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://google.serper.dev/news",
            headers={"X-API-KEY": get_settings().SERPER_API_KEY},
            json={"q": f"{company} event conference announcement", "num": 5},
            timeout=10,
        )
    news_snippets = "\n".join(
        f"{r.get('title', '')}: {r.get('snippet', '')}"
        for r in response.json().get("news", [])
    )
    if news_snippets:
        items = await _openai_extract_events(news_snippets, openai)
        all_events += _extract_event_items(items, source="news")

    return all_events


async def run(state: ResearchState) -> dict:
    domain = state["competitor_domain"]
    try:
        openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
        domain_events = await _scrape_events_from_domain(domain, openai)
        other_events = await _scrape_events_from_others(domain, openai)

        return {
            "events": EventsData(
                website_events=domain_events,
                meetup_events=[e for e in other_events if e.source == "meetup"],
                loma_events=[e for e in other_events if e.source == "luma"],
                reported_events=[e for e in other_events if e.source in ("google", "news")],
                source="serper+firecrawl",
            ),
            "completed_nodes": ["events"],
        }
    except Exception as e:
        logger.error("node_failed", node="events", error=str(e))
        return {"errors": [f"events: {e}"]}


if __name__ == "__main__":
    import asyncio
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main():
        from app.agents.research.state import VisualsData, PositioningData, FinancialData, SocialData, SeoGeoData, NewsData, NewsletterData

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
            events = result["events"]
            print(events.model_dump_json(indent=2))

    asyncio.run(main())