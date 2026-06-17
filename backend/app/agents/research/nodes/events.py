import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse
from app.agents.research.state import ResearchState, EventsData, EventItem
from app.agents.research.repositories.research_repository import insert_research_snapshot, get_latest_snapshot
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

TOPIC_TAXONOMY = [
    "Process Mining",
    "AI & Machine Learning",
    "Business Process Management",
    "Cloud & ERP",
    "Analytics & Business Intelligence",
    "Digital Transformation",
    "Automation & RPA",
    "Finance & Accounting",
    "Supply Chain & Operations",
    "Sustainability & ESG",
    "Developer & Technical",
    "Customer Experience",
    "Compliance & Risk",
    "Industry Conference",
    "Other",
]


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


def _name_sim(a: str, b: str) -> float:
    """Normalized name similarity via SequenceMatcher (0–1)."""
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _dedup_events(events: list[EventItem]) -> list[EventItem]:
    """Remove cross-source duplicates: same company + same date + similar name.

    Preference order: website > meetup/luma > google > news (first-seen wins since
    domain_events are prepended before other_events in the combined list).
    """
    result: list[EventItem] = []
    for candidate in events:
        name_c = candidate.name or ""
        date_c = candidate.event_date or ""
        is_dup = False
        for kept in result:
            if kept.company != candidate.company:
                continue
            name_k = kept.name or ""
            date_k = kept.event_date or ""
            sim = _name_sim(name_c, name_k)
            # Same date + similar name
            if date_c and date_k and date_c == date_k and sim > 0.75:
                is_dup = True
                break
            # No dates: rely on very high name similarity alone
            if not date_c and not date_k and sim > 0.9:
                is_dup = True
                break
        if not is_dup:
            result.append(candidate)
    return result


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


async def _classify_topics(events: list[EventItem], openai: AsyncOpenAI) -> None:
    """Batch-normalize event_topic to TOPIC_TAXONOMY (in-place).

    Every event gets a topic. If the LLM proposes a genuinely new topic
    (returned with 'NEW: ' prefix), it is appended to TOPIC_TAXONOMY for
    subsequent batches. Any event still without a topic after all batches
    falls back to 'Other'.
    """
    if not events:
        return
    BATCH_SIZE = 40
    for batch_start in range(0, len(events), BATCH_SIZE):
        batch = events[batch_start : batch_start + BATCH_SIZE]
        taxonomy_str = "\n".join(f"- {t}" for t in TOPIC_TAXONOMY)
        items = [
            {"idx": i, "name": e.name or "", "topic": e.event_topic or ""}
            for i, e in enumerate(batch)
        ]
        try:
            response = await openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"Classify each event into exactly one topic from this list:\n{taxonomy_str}\n\n"
                            "Rules:\n"
                            "- Every event MUST receive a topic — never return empty.\n"
                            "- Choose the best matching topic from the list above.\n"
                            "- Only if truly no existing topic fits, propose a concise new topic "
                            "(2–4 words) prefixed with 'NEW: ' (e.g. 'NEW: Healthcare Innovation').\n"
                            "Return JSON: {\"results\": [{\"idx\": int, \"topic\": string}]}"
                        ),
                    },
                    {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
            )
            results = json.loads(response.choices[0].message.content).get("results", [])
            for r in results:
                idx, topic = r.get("idx"), r.get("topic", "")
                if not isinstance(idx, int) or not isinstance(topic, str):
                    continue
                if not 0 <= idx < len(batch):
                    continue
                if topic.startswith("NEW: "):
                    new_topic = topic[5:].strip()
                    if new_topic and new_topic not in TOPIC_TAXONOMY:
                        TOPIC_TAXONOMY.append(new_topic)
                        logger.info("topic_taxonomy_extended", new_topic=new_topic)
                    topic = new_topic
                if topic:
                    batch[idx].event_topic = topic
        except Exception as e:
            logger.warning("topic_classification_failed", batch_start=batch_start, error=str(e))

    # Guarantee no event is left without a topic
    for e in events:
        if not e.event_topic:
            e.event_topic = "Other"


# Common event-page path segments used to probe domains directly.
_EVENT_PAGE_KEYWORDS = frozenset({"events", "webinar", "webinars", "conference", "summit"})
_COMMON_EVENT_PATHS = [
    "/events", "/events/upcoming", "/events/all",
    "/webinars", "/webinars/upcoming",
    "/resources/events", "/resources/webinars",
    "/community/events", "/company/events",
    "/about/events", "/news-events",
]


async def _discover_event_pages(domain: str, app: FirecrawlApp) -> list[str]:
    """Return candidate event listing URLs for a domain from three parallel sources.

    1. Serper search — most likely to surface the actual events page when indexed.
    2. HEAD-probe of common event paths — catches pages like /events that aren't
       well-indexed but always exist (e.g. anthropic.com/events linked only in footer).
    3. Homepage link scan — finds event page URLs buried in nav/footer links.

    Results are deduplicated; Serper results come first (highest confidence).
    """
    seen: set[str] = set()
    serper_urls: list[str] = []
    probed_urls: list[str] = []
    homepage_urls: list[str] = []

    async def _serper() -> None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": get_settings().SERPER_API_KEY},
                    json={"q": f"site:{domain} events OR webinars OR conference", "num": 5},
                    timeout=10,
                )
            for r in resp.json().get("organic", []):
                url = r.get("link", "")
                if url:
                    serper_urls.append(url)
        except Exception:
            pass

    async def _probe_paths() -> None:
        candidates = [f"https://{domain}{p}" for p in _COMMON_EVENT_PATHS]
        async with httpx.AsyncClient(follow_redirects=True, timeout=5) as client:
            async def _head(url: str) -> str | None:
                try:
                    r = await client.head(url)
                    return url if r.status_code < 400 else None
                except Exception:
                    return None
            results = await asyncio.gather(*[_head(u) for u in candidates])
        probed_urls.extend(u for u in results if u)

    async def _homepage_scan() -> None:
        try:
            scraped = await asyncio.to_thread(
                app.scrape_url, f"https://{domain}", formats=["links"]
            )
            for raw in getattr(scraped, "links", []) or []:
                url = raw.get("url", "") if isinstance(raw, dict) else str(raw)
                if not url or not url.startswith("http") or domain not in url:
                    continue
                parts = [p for p in urlparse(url).path.lower().strip("/").split("/") if p]
                # Keyword must appear in path AND the path must be shallow (≤2 segments)
                if any(kw in parts for kw in _EVENT_PAGE_KEYWORDS) and len(parts) <= 2:
                    homepage_urls.append(url.split("?")[0])
        except Exception:
            pass

    await asyncio.gather(_serper(), _probe_paths(), _homepage_scan())

    ordered: list[str] = []
    for url in serper_urls + probed_urls + homepage_urls:
        clean = url.split("?")[0].rstrip("/")
        if clean and clean not in seen:
            seen.add(clean)
            ordered.append(clean)
    return ordered


async def _scrape_events_from_domain(domain: str, company: str, openai: AsyncOpenAI) -> list[EventItem]:
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)

    overview_urls = await _discover_event_pages(domain, app)
    if not overview_urls:
        return []

    logger.info("event_overview_candidates", domain=domain, count=len(overview_urls))
    all_events: list[EventItem] = []

    for overview_url in overview_urls[:5]:
        try:
            scraped = await asyncio.to_thread(
                app.scrape_url, overview_url, formats=["markdown", "links"]
            )
        except Exception as e:
            logger.warning("event_scrape_failed", url=overview_url, error=str(e))
            continue
        if not getattr(scraped, "markdown", None):
            continue

        # Filter FireCrawl links to individual event card pages
        page_links = getattr(scraped, "links", []) or []
        individual_urls = _filter_event_card_links(page_links, overview_url, domain)
        logger.info("event_card_urls_found", overview=overview_url, count=len(individual_urls))

        if individual_urls:
            nested = await asyncio.gather(*[
                _scrape_individual_event_page(url, app, openai)
                for url in individual_urls[:10]
            ])
            items = [item for sub in nested for item in sub]
        else:
            logger.info("event_card_fallback", overview=overview_url)
            items = await _openai_extract_events(scraped.markdown, openai, source_url=overview_url)

        events = _extract_event_items(items, source="website", company=company, domain=domain)
        for event in events:
            if not event.source_link:
                event.source_link = overview_url
        all_events.extend(events)

    return all_events


# --- Quelle 2: Meetup + Luma ---

_MEETUP_EVENT_RE = re.compile(r"meetup\.com/[^/]+/events/\d+")


def _filter_meetup_event_links(links: list) -> list[str]:
    """Return individual Meetup event page URLs from a group listing page's link list.

    Matches URLs of the form meetup.com/<group>/events/<numeric-id>[/...].
    Strips query parameters and deduplicates.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in links:
        url = raw.get("url", "") if isinstance(raw, dict) else str(raw)
        if not url or not _MEETUP_EVENT_RE.search(url):
            continue
        clean = url.split("?")[0].rstrip("/")
        if clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


async def _scrape_meetup_events(company: str, domain: str, openai: AsyncOpenAI) -> list[EventItem]:
    """Scrape individual Meetup event pages for a company.

    1. Search Serper for the company's Meetup group page.
    2. Fetch the group listing with 'links' to discover individual event URLs.
    3. Scrape each event page so source_link points to the specific event.
    4. Fall back to group-page extraction if no event links are found.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": get_settings().SERPER_API_KEY},
                json={"q": f"{company} site:meetup.com", "num": 3},
                timeout=10,
            )
        meetup_results = resp.json().get("organic", [])
    except Exception:
        return []

    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    all_events: list[EventItem] = []

    for r in meetup_results[:2]:
        group_url = r.get("link", "")
        if not group_url:
            continue
        try:
            scraped = await asyncio.to_thread(app.scrape_url, group_url, formats=["markdown", "links"])
        except Exception as e:
            logger.warning("meetup_group_scrape_failed", url=group_url, error=str(e))
            continue
        if not getattr(scraped, "markdown", None):
            continue

        page_links = getattr(scraped, "links", []) or []
        event_urls = _filter_meetup_event_links(page_links)
        logger.info("meetup_event_links_found", group=group_url, count=len(event_urls))

        if event_urls:
            # Scrape each event page — LLM receives the specific event URL as source hint
            nested = await asyncio.gather(*[
                _scrape_individual_event_page(url, app, openai)
                for url in event_urls[:10]
            ])
            items = [item for sub in nested for item in sub]
            events = _extract_event_items(items, source="meetup", company=company, domain=domain)
            # Guarantee source_link is the specific event page, not the group listing
            for event, evt_url in zip(events, event_urls):
                if not event.source_link or "meetup.com" not in event.source_link:
                    event.source_link = evt_url
        else:
            logger.info("meetup_no_event_links_fallback", group=group_url)
            items = await _openai_extract_events(scraped.markdown, openai, source_url=group_url)
            events = _extract_event_items(items, source="meetup", company=company, domain=domain)
            for e in events:
                if not e.source_link:
                    e.source_link = group_url

        all_events.extend(events)
        if all_events:
            break

    return all_events


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


async def _scrape_luma_events(company: str, domain: str, openai: AsyncOpenAI) -> list[EventItem]:
    """Find and scrape a company's Luma events.

    Strategy:
    1. Try common slug-derived profile URLs (lu.ma/<slug>, lu.ma/c/<slug>).
    2. Search Serper for up to 5 results on lu.ma.
    3. Prioritise company profile pages (short paths) over individual event pages.
    4. Scrape the best candidates until events are found.
    """
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)

    # Build slug variants from company name
    slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
    slug_no_dash = slug.replace("-", "")
    slug_first = slug.split("-")[0]
    direct_urls: list[str] = []
    for s in dict.fromkeys([slug, slug_no_dash, slug_first]):  # preserve order, dedup
        direct_urls += [f"https://lu.ma/{s}", f"https://lu.ma/c/{s}"]

    # Search via Serper for more candidates
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": get_settings().SERPER_API_KEY},
                json={"q": f"{company} events site:lu.ma", "num": 5},
                timeout=10,
            )
        serper_urls = [r.get("link", "") for r in resp.json().get("organic", [])]
    except Exception:
        serper_urls = []

    # Partition: profile pages (short path) vs individual event pages (deeper path)
    seen: set[str] = set()
    profile_urls: list[str] = []
    event_urls: list[str] = []
    for url in direct_urls + serper_urls:
        if not url or url in seen or not url.startswith("http"):
            continue
        seen.add(url)
        path = urlparse(url).path.strip("/")
        if "/" not in path:
            profile_urls.append(url)
        else:
            event_urls.append(url)

    # Try profile pages first; fall back to event pages; cap at 4 total attempts
    all_events: list[EventItem] = []
    for url in (profile_urls + event_urls)[:4]:
        try:
            scraped = await asyncio.to_thread(app.scrape_url, url, formats=["markdown"])
            if not getattr(scraped, "markdown", None):
                continue
            items = await _openai_extract_events(scraped.markdown, openai, source_url=url)
            events = _extract_event_items(items, source="luma", company=company, domain=domain)
            for e in events:
                if not e.source_link:
                    e.source_link = url
            all_events.extend(events)
            if all_events:
                break
        except Exception as e:
            logger.warning("luma_scrape_failed", url=url, error=str(e))

    return all_events


async def _enrich_event_from_web(event: EventItem, openai: AsyncOpenAI) -> None:
    """Search for an event's official page and fill in missing fields (in-place).

    Used for news-derived events whose source_link points to an article rather
    than the actual event page. Tries to find the real event page via Google
    and scrape it for attendees, location, speakers, etc.
    """
    if not event.name:
        return
    query = f'"{event.name}" {event.company}'
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": get_settings().SERPER_API_KEY},
                json={"q": query, "num": 3},
                timeout=10,
            )
        results = resp.json().get("organic", [])
    except Exception:
        return

    # Skip the news article URL we already have
    existing = event.source_link or ""
    candidates = [r["link"] for r in results if r.get("link") and r["link"] != existing]
    if not candidates:
        return

    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    for url in candidates[:2]:
        try:
            scraped = await asyncio.to_thread(app.scrape_url, url, formats=["markdown"])
            if not getattr(scraped, "markdown", None):
                continue
            items = await _openai_extract_events(scraped.markdown, openai, source_url=url)
            if not items:
                continue
            d = items[0]
            if d.get("attendees") is not None and event.attendees is None:
                event.attendees = d["attendees"]
            if d.get("location") and not event.location:
                event.location = d["location"]
            if d.get("start_date") and not event.event_date:
                event.event_date = d["start_date"]
                event.start_date = d["start_date"]
            if d.get("end_date") and not event.end_date:
                event.end_date = d["end_date"]
            if d.get("speakers") and not event.speakers:
                event.speakers = d["speakers"]
            if d.get("sponsors") and not event.sponsors:
                event.sponsors = d["sponsors"]
            if d.get("summary") and not event.summary:
                event.summary = d["summary"]
            event.source_link = url  # point to the real event page, not the article
            break
        except Exception as e:
            logger.warning("event_enrichment_failed", url=url, error=str(e))


async def _scrape_events_from_others(domain: str, company: str, openai: AsyncOpenAI) -> list[EventItem]:
    all_events: list[EventItem] = []

    # Meetup — dedicated function that scrapes individual event pages
    meetup_events = await _scrape_meetup_events(company, domain, openai)
    all_events.extend(meetup_events)

    # Luma (dedicated function with smarter URL discovery)
    luma_events = await _scrape_luma_events(company, domain, openai)
    all_events.extend(luma_events)

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
        # Find official event pages and fill in missing details (attendees, location, etc.)
        if events:
            await asyncio.gather(*[_enrich_event_from_web(e, openai) for e in events])
        all_events.extend(events)

    return all_events


def _load_existing_events(domain: str) -> list[EventItem]:
    """Load all EventItems stored in the most recent snapshot for this domain."""
    data = get_latest_snapshot(domain, "events")
    if not data:
        return []
    existing: list[EventItem] = []
    for key in ("website_events", "meetup_events", "luma_events", "reported_events"):
        for item in data.get(key) or []:
            try:
                existing.append(EventItem.model_validate(item))
            except Exception:
                pass
    return existing


async def run(state: ResearchState) -> dict:
    domain = state["competitor_domain"]
    company = domain.split(".")[0].capitalize()
    try:
        openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)

        existing_events = await asyncio.to_thread(_load_existing_events, domain)
        logger.info("events_existing_loaded", domain=domain, count=len(existing_events))

        domain_events, other_events = await asyncio.gather(
            _scrape_events_from_domain(domain, company, openai),
            _scrape_events_from_others(domain, company, openai),
        )

        # Existing events take priority; new ones are only added if not already present
        all_events_combined = _dedup_events(existing_events + domain_events + other_events)

        # Only classify events that don't have a topic yet
        unclassified = [e for e in all_events_combined if not e.event_topic]
        if unclassified:
            await _classify_topics(unclassified, openai)

        new_count = len(all_events_combined) - len(existing_events)
        logger.info("events_merged", domain=domain, total=len(all_events_combined), new=new_count)

        events_data = EventsData(
            website_events=[e for e in all_events_combined if e.source_type == "website"],
            meetup_events=[e for e in all_events_combined if e.source_type == "meetup"],
            luma_events=[e for e in all_events_combined if e.source_type == "luma"],
            reported_events=[e for e in all_events_combined if e.source_type in ("google", "news")],
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
    import sys as _sys
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main():
        domain = _sys.argv[1] if len(_sys.argv) > 1 else "anthropic.com"
        company = domain.split(".")[0].capitalize()
        openai_client = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)

        print(f"\n=== Scraping events for {domain} ===\n")
        domain_events, other_events = await asyncio.gather(
            _scrape_events_from_domain(domain, company, openai_client),
            _scrape_events_from_others(domain, company, openai_client),
        )
        all_events = _dedup_events(domain_events + other_events)
        await _classify_topics(all_events, openai_client)

        print(f"\nTotal: {len(all_events)} events  "
              f"(website={len(domain_events)}, others={len(other_events)})\n")
        for e in all_events:
            print(f"  [{e.source_type:8}] {(e.name or '?')[:60]:<60} "
                  f"| {e.event_date or '?':>10} | {(e.location or '?')[:30]:<30} "
                  f"| topic={e.event_topic or '?'}")
            if e.source_link:
                print(f"             {e.source_link}")

    asyncio.run(main())
