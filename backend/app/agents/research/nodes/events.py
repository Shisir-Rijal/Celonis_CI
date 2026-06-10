import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.agents.research.state import ResearchState, EventsData, EventItem
from app.config import get_settings
from pydantic import BaseModel
from firecrawl import V1FirecrawlApp as FirecrawlApp
import json
import asyncio
from openai import AsyncOpenAI
import structlog
import httpx


logger = structlog.get_logger(__name__)



_SOURCE_ORIGIN = {
    "website": "owned",
    "meetup": "third_party",
    "luma": "third_party",
    "google": "earned",
    "news": "earned",
}


def _extract_event_items(raw_items: list[dict], source: str, company: str, domain: str) -> list[EventItem]:
    return [
        _normalize_location(EventItem(
            # --- BaseData: dynamic fields ---
            company=company,
            url=item.get("source_link") or f"https://{domain}",
            title=item.get("name"),
            source_type=source,
            source_origin=_SOURCE_ORIGIN.get(source, "earned"),
            # --- EventItem-specific ---
            name=item.get("name"),
            event_date=item.get("start_date"),
            start_date=item.get("start_date"),
            end_date=item.get("end_date"),
            start_time=item.get("start_time"),
            end_time=item.get("end_time"),
            attendees=item.get("attendees"),
            location=item.get("location"),
            event_topic=item.get("topic"),
            organized_by=item.get("organized_by"),
            sponsors=item.get("sponsors"),
            speakers=item.get("speakers"),
            summary=item.get("summary"),
            source_link=item.get("source_link"),
            image=img if (img := item.get("image")) and img.startswith("http") else None,
            video=item.get("video"),
        ))
        for item in raw_items
    ]


_ONLINE_KEYWORDS = {"webinar", "virtual", "online", "call", "livestream", "live stream", "zoom", "teams", "remote"}


def _normalize_location(event: EventItem) -> EventItem:
    if not event.location:
        name_lower = (event.name or "").lower()
        topic_lower = (event.event_topic or "").lower()
        if any(kw in name_lower or kw in topic_lower for kw in _ONLINE_KEYWORDS):
            event.location = "Online"
    return event


async def _openai_extract_events(content: str, openai: AsyncOpenAI, source_url: str | None = None) -> list[dict]:
    source_hint = f"Source URL (use as source_link for all events unless a more specific event page URL is found): {source_url}\n\n" if source_url else ""
    response = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "Extract all events from this content. "
                "Return a JSON object with key 'events' containing a list. "
                "Each event has these fields:\n"
                "- name: event title\n"
                "- start_date: YYYY-MM-DD — only set if a date is EXPLICITLY written next to or under this specific event. Do NOT infer, guess, or borrow a date from a different event. Use null if the date for this event is not clearly stated.\n"
                "- end_date: YYYY-MM-DD — same rule as start_date, only if explicitly stated for this event. Null otherwise.\n"
                "- start_time: exact time as shown directly for this event (e.g. '10:00 AM ET', '14:30 CET'). Null if not explicitly stated for this event.\n"
                "- end_time: exact end time for this event, or null\n"
                "- attendees: integer number of expected or registered attendees, or null\n"
                "- location: city + country, venue name, or 'Online' for webinars/virtual/calls/Zoom/Teams events — never leave null for webinars\n"
                "- topic: main subject or theme of the event — infer from the event name and content if not explicitly stated (e.g. 'AI & Machine Learning', 'Developer Conference'). Only null if truly no context is available.\n"
                "- organized_by: name of the company or person organizing the event, or null\n"
                "- sponsors: list of sponsor names if mentioned, or null\n"
                "- speakers: list of speaker names if mentioned, or null\n"
                "- summary: 1-2 sentence description of what the event is about — write your own if no description is present on the page, based on the event name, topic, and any available context. Never null.\n"
                "- source_link: use the provided source URL if no specific event URL exists\n"
                "- image: only set if a FULL image URL (starting with https:// or http://) is directly associated with this specific event in the content (e.g. an event thumbnail next to the event title). Do NOT use relative paths, page banners, or unrelated images. Null if the URL is not complete or if unsure.\n"
                "- video: a YouTube or Vimeo URL explicitly linked to this event, or null\n"
                "Rules: each field must be specific to the individual event — never share or copy values between events. "
                "If the event is a webinar, call, virtual event, or has no physical location, set location to 'Online'. "
                "Only return real events, not navigation links or generic pages."
            )},
            {"role": "user", "content": source_hint + content[:6000]},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content).get("events", [])


# --- Quelle 1: Company-Website ---

async def _scrape_events_from_domain(domain: str, company: str, openai: AsyncOpenAI) -> list[EventItem]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": get_settings().SERPER_API_KEY},
            json={"q": f"site:{domain} events OR webinars OR conference", "num": 3},
            timeout=10,
        )
    results = response.json().get("organic", [])
    if not results:
        return []

    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    all_events: list[EventItem] = []

    for result in results[:3]:
        url = result["link"]
        try:
            scraped = await asyncio.to_thread(app.scrape_url, url, formats=["markdown", "rawHtml"])
        except Exception as e:
            logger.warning("event_scrape_failed", url=url, error=str(e))
            continue
        if not getattr(scraped, "markdown", None):
            continue

        items = await _openai_extract_events(scraped.markdown, openai, source_url=url)
        events = _extract_event_items(items, source="website", company=company, domain=domain)

        for event in events:
            if not event.source_link:
                event.source_link = url

        all_events.extend(events)

    return all_events


# --- Quelle 2: Meetup + Luma ---

async def _scrape_platform(source: str, url: str, company: str, domain: str, openai: AsyncOpenAI) -> list[EventItem]:
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    try:
        scraped = await asyncio.to_thread(app.scrape_url, url, formats=["markdown", "rawHtml"])
    except Exception as e:
        logger.warning("platform_scrape_failed", source=source, url=url, error=str(e))
        return []
    if not getattr(scraped, "markdown", None):
        return []

    items = await _openai_extract_events(scraped.markdown, openai, source_url=url)
    events = _extract_event_items(items, source=source, company=company, domain=domain)

    for event in events:
        if not event.source_link:
            event.source_link = url

    return events


async def _scrape_events_from_others(domain: str, company: str, openai: AsyncOpenAI) -> list[EventItem]:
    all_events: list[EventItem] = []

    platform_queries = {
        "meetup": f"{company} site:meetup.com",
        "luma": f"{company} site:lu.ma",
    }
    async with httpx.AsyncClient() as client:
        serper_tasks = {
            source: client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": get_settings().SERPER_API_KEY},
                json={"q": query, "num": 1},
                timeout=10,
            )
            for source, query in platform_queries.items()
        }
        serper_results = {src: (await req).json() for src, req in serper_tasks.items()}

    for source, data in serper_results.items():
        results = data.get("organic", [])
        if not results:
            continue
        url = results[0]["link"]
        events = await _scrape_platform(source, url, company, domain, openai)
        all_events.extend(events)

    # Google general search — pass structured data (title + snippet + link + image)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": get_settings().SERPER_API_KEY},
            json={"q": f"{company} upcoming events conference webinar 2025 2026", "num": 5},
            timeout=10,
        )
    google_items = resp.json().get("organic", [])
    if google_items:
        structured = json.dumps([
            {"title": r.get("title"), "snippet": r.get("snippet"), "url": r.get("link")}
            for r in google_items
        ], ensure_ascii=False)
        items = await _openai_extract_events(structured, openai)
        events = _extract_event_items(items, source="google", company=company, domain=domain)
        links_by_title = {r.get("title", "").lower(): r.get("link") for r in google_items}
        for event in events:
            if not event.source_link:
                event.source_link = links_by_title.get((event.name or "").lower())
        all_events.extend(events)

    # News
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://google.serper.dev/news",
            headers={"X-API-KEY": get_settings().SERPER_API_KEY},
            json={"q": f"{company} event conference announcement", "num": 5},
            timeout=10,
        )
    news_items = resp.json().get("news", [])
    if news_items:
        structured = json.dumps([
            {"title": r.get("title"), "snippet": r.get("snippet"), "url": r.get("link")}
            for r in news_items
        ], ensure_ascii=False)
        items = await _openai_extract_events(structured, openai)
        events = _extract_event_items(items, source="news", company=company, domain=domain)
        links_by_title = {r.get("title", "").lower(): r.get("link") for r in news_items}
        for event in events:
            if not event.source_link:
                event.source_link = links_by_title.get((event.name or "").lower())
        all_events.extend(events)

    return all_events


async def run(state: ResearchState) -> dict:
    domain = state["competitor_domain"]
    company = domain.split(".")[0].capitalize()
    try:
        openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
        domain_events, other_events = await asyncio.gather(
            _scrape_events_from_domain(domain, company, openai),
            _scrape_events_from_others(domain, company, openai),
        )

        return {
            "events": EventsData(
                website_events=domain_events,
                meetup_events=[e for e in other_events if e.source_type == "meetup"],
                luma_events=[e for e in other_events if e.source_type == "luma"],
                reported_events=[e for e in other_events if e.source_type in ("google", "news")],
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
            print(result["events"].model_dump_json(indent=2))

    asyncio.run(main())
