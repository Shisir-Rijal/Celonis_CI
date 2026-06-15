import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from datetime import datetime, timezone
from urllib.parse import urlparse
from app.agents.research.state import ResearchState, EventsData, EventItem
from app.agents.research.repositories.research_repository import insert_research_snapshot
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


async def _openai_extract_events(
    content: str,
    openai: AsyncOpenAI,
    source_url: str | None = None,
    strict_events_only: bool = False,
) -> list[dict]:
    source_hint = f"Source URL (use as source_link for all events unless a more specific event page URL is found): {source_url}\n\n" if source_url else ""

    if strict_events_only:
        system_prompt = (
            "You are extracting REAL EVENTS from news articles where the company is directly involved. "
            "Only extract an event if the company is the ORGANIZER, HOST, SPONSOR, or KEY SPEAKER/PARTICIPANT. "
            "A real event is a specific gathering: conference, summit, webinar, meetup, trade show, hackathon, or launch event. "
            "DO NOT extract: product announcements without an event, financial results, earnings calls, opinion articles, "
            "interviews not tied to an event, blog posts, or press releases about products (not events). "
            "If the article does not clearly describe a real event with company involvement, return an empty list. "
            "Return a JSON object with key 'events' containing a list. Each event has:\n"
            "- name: event title\n"
            "- start_date: YYYY-MM-DD if explicitly stated, null otherwise\n"
            "- end_date: YYYY-MM-DD if explicitly stated, null otherwise\n"
            "- start_time: exact time if stated, null otherwise\n"
            "- end_time: exact end time, null otherwise\n"
            "- attendees: integer if stated, null otherwise\n"
            "- location: city + country, venue name, or 'Online' for virtual events\n"
            "- topic: main subject of the event\n"
            "- organized_by: organizer name or null\n"
            "- sponsors: list of sponsor names or null\n"
            "- speakers: list of speaker names or null\n"
            "- summary: 1-2 sentence description of what the event is about and the company's role\n"
            "- source_link: URL of the event page or the article\n"
            "- image: full https:// image URL if present, null otherwise\n"
            "- video: YouTube or Vimeo URL if present, null otherwise"
        )
    else:
        system_prompt = (
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
        )

    response = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": source_hint + content[:6000]},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content).get("events", [])


# --- Quelle 1: Company-Website ---

def _filter_event_card_links(links: list, overview_url: str, domain: str) -> list[str]:
    """Filter FireCrawl page links to individual event card pages.

    Keeps only links that are one path-segment deeper than the overview URL
    and on the same domain — these are the individual event pages linked from cards.
    E.g. overview=/events → keeps /events/fusion, /events/forward, not /events or /blog.
    """
    overview_path = urlparse(overview_url).path.rstrip("/")
    seen: set[str] = set()
    result: list[str] = []

    for raw in links:
        # FireCrawl may return dicts {"url": "..."} or plain strings
        url = raw.get("url", "") if isinstance(raw, dict) else str(raw)
        if not url:
            continue
        # Resolve relative paths
        if url.startswith("/"):
            url = f"https://{domain}{url}"
        if not url.startswith("http"):
            continue

        parsed = urlparse(url)
        # Must be on the same domain
        if domain not in parsed.netloc:
            continue
        path = parsed.path.rstrip("/")
        # Must be a direct child of the overview path (exactly one more segment)
        if not path.startswith(overview_path + "/"):
            continue
        remainder = path[len(overview_path) + 1:]
        if not remainder or "/" in remainder:
            continue
        # Skip obvious non-event suffixes
        if any(remainder.startswith(s) for s in ("page", "filter", "category", "tag", "search", "?", "#")):
            continue

        clean = f"https://{parsed.netloc}{path}"
        if clean not in seen:
            seen.add(clean)
            result.append(clean)

    return result


async def _scrape_individual_event_page(url: str, app: FirecrawlApp, openai: AsyncOpenAI) -> list[dict]:
    try:
        scraped = await asyncio.to_thread(app.scrape_url, url, formats=["markdown"])
        if not getattr(scraped, "markdown", None):
            return []
        return await _openai_extract_events(scraped.markdown, openai, source_url=url)
    except Exception as e:
        logger.warning("individual_event_scrape_failed", url=url, error=str(e))
        return []


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
        overview_url = result["link"]
        try:
            # Request both markdown (for fallback extraction) and links (for card URLs)
            scraped = await asyncio.to_thread(
                app.scrape_url, overview_url, formats=["markdown", "links"]
            )
        except Exception as e:
            logger.warning("event_scrape_failed", url=overview_url, error=str(e))
            continue
        if not getattr(scraped, "markdown", None):
            continue

        # Step 1: filter FireCrawl links to individual event card pages
        page_links = getattr(scraped, "links", []) or []
        individual_urls = _filter_event_card_links(page_links, overview_url, domain)
        logger.info("event_card_urls_found", overview=overview_url, count=len(individual_urls))

        if individual_urls:
            # Step 2: scrape each event card page for full details
            nested = await asyncio.gather(*[
                _scrape_individual_event_page(url, app, openai)
                for url in individual_urls[:8]
            ])
            items = [item for sub in nested for item in sub]
        else:
            # Fallback: extract directly from the overview page markdown
            logger.info("event_card_fallback", overview=overview_url)
            items = await _openai_extract_events(scraped.markdown, openai, source_url=overview_url)

        events = _extract_event_items(items, source="website", company=company, domain=domain)
        for event in events:
            if not event.source_link:
                event.source_link = overview_url
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

    # News — two targeted queries: company-hosted events + company participation
    news_queries = [
        f"{company} hosts OR organizes OR presents at conference summit webinar 2025 2026",
        f"{company} sponsor OR exhibitor OR keynote conference summit 2025 2026",
    ]
    news_items: list[dict] = []
    async with httpx.AsyncClient() as client:
        for q in news_queries:
            resp = await client.post(
                "https://google.serper.dev/news",
                headers={"X-API-KEY": get_settings().SERPER_API_KEY},
                json={"q": q, "num": 5},
                timeout=10,
            )
            news_items += resp.json().get("news", [])

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique_news = []
    for item in news_items:
        url = item.get("link", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_news.append(item)

    if unique_news:
        structured = json.dumps([
            {"title": r.get("title"), "snippet": r.get("snippet"), "url": r.get("link")}
            for r in unique_news
        ], ensure_ascii=False)
        items = await _openai_extract_events(structured, openai, strict_events_only=True)
        events = _extract_event_items(items, source="news", company=company, domain=domain)
        links_by_title = {r.get("title", "").lower(): r.get("link") for r in unique_news}
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

        events_data = EventsData(
            website_events=domain_events,
            meetup_events=[e for e in other_events if e.source_type == "meetup"],
            luma_events=[e for e in other_events if e.source_type == "luma"],
            reported_events=[e for e in other_events if e.source_type in ("google", "news")],
        )
        try:
            insert_research_snapshot(domain, datetime.now(timezone.utc), "events", events_data)
        except Exception as db_err:
            logger.warning("snapshot_write_failed", node="events", error=str(db_err))
        return {
            "events": events_data,
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
