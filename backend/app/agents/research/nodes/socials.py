import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import structlog
import httpx
from pydantic import BaseModel
from app.agents.research.state import ResearchState, SocialData
from app.agents.shared.utils.brandfetch import _get_brand_data
from app.config import get_settings
from app.agents.shared.utils.youtube import _scrape_yt_content_by_search_for, VideoData
# YouTube Data API v3

logger = structlog.get_logger(__name__)

_PLATFORM_MAP = {
    "twitter": "twitter",
    "x": "twitter",
    "instagram": "instagram",
    "facebook": "facebook",
    "linkedin": "linkedin",
    "youtube": "youtube",
    "tiktok": "tiktok",
}


# Scrape Sociallinks:

async def _scrape_social_links(domain: str) -> dict[str, str]:
    data = await _get_brand_data(domain)
    links: dict[str, str] = {}
    for entry in data.get("links", []):
        name = (entry.get("name") or "").lower()
        url = entry.get("url")
        if url and name in _PLATFORM_MAP:
            links[_PLATFORM_MAP[name]] = url
    return links



class YoutubeContent(BaseModel): 
    subscribers: int | None = None
    video_count : int | None = None
    description: str | None = None
    own_videos: list[VideoData] = []



def _channel_param_from_url(url: str) -> dict:
    """Leitet den richtigen API-Parameter aus der YouTube-URL ab."""
    if "/@" in url:
        handle = url.split("/@")[1].split("/")[0].split("?")[0]
        return {"forHandle": f"@{handle}"}
    if "/channel/" in url:
        channel_id = url.split("/channel/")[1].split("/")[0].split("?")[0]
        return {"id": channel_id}
    for prefix in ["/c/", "/user/"]:
        if prefix in url:
            name = url.split(prefix)[1].split("/")[0].split("?")[0]
            return {"forHandle": name}
    # Fallback: letztes Pfadsegment als Handle (z.B. youtube.com/celonis)
    from urllib.parse import urlparse
    path = urlparse(url).path.strip("/")
    if path:
        return {"forHandle": f"@{path}"}
    return {}


async def _scrape_yt_content_about_(youtube_url: str) -> YoutubeContent | None:
    api_key = get_settings().YOUTUBE_API_KEY
    if not api_key or not youtube_url:
        return None

    channel_param = _channel_param_from_url(youtube_url)
    if not channel_param:
        return None

    async with httpx.AsyncClient() as client:
        # 1. Channel-Stats + ID direkt über URL-Parameter
        stats_resp = await client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "statistics,snippet", "key": api_key, **channel_param},
            timeout=10,
        )
        items = stats_resp.json().get("items", [])
        if not items:
            return None
        channel = items[0]
        channel_id = channel["id"]
        stats = channel.get("statistics", {})
        snippet = channel.get("snippet", {})

        # 3. Aktuelle Videos des Channels
        videos_resp = await client.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"channelId": channel_id, "part": "snippet", "order": "date",
                    "maxResults": 10, "type": "video", "key": api_key},
            timeout=10,
        )
        video_items = videos_resp.json().get("items", [])
        video_ids = [v["id"]["videoId"] for v in video_items if v.get("id", {}).get("videoId")]

        # 4. Video-Stats
        vstats: dict = {}
        if video_ids:
            vstats_resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "statistics", "id": ",".join(video_ids), "key": api_key},
                timeout=10,
            )
            vstats = {v["id"]: v.get("statistics", {}) for v in vstats_resp.json().get("items", [])}

    channel_name = snippet.get("title")
    videos = []
    for item in video_items:
        vid_id = item.get("id", {}).get("videoId")
        s = item.get("snippet", {})
        st = vstats.get(vid_id, {})
        videos.append(VideoData(
            title=s.get("title"),
            description=s.get("description"),
            date=s.get("publishedAt"),
            thumbnail=s.get("thumbnails", {}).get("high", {}).get("url"),
            published_by=s.get("channelTitle") or channel_name,
            url=f"https://www.youtube.com/watch?v={vid_id}" if vid_id else None,
            view_count=int(st["viewCount"]) if st.get("viewCount") else None,
            like_count=int(st["likeCount"]) if st.get("likeCount") else None,
            comment_count=int(st["commentCount"]) if st.get("commentCount") else None,
        ))

    return YoutubeContent(
        subscribers=int(stats["subscriberCount"]) if stats.get("subscriberCount") else None,
        video_count=int(stats["videoCount"]) if stats.get("videoCount") else None,
        description=snippet.get("description"),
        own_videos=videos,
    )


async def run(state: ResearchState) -> dict:
    domain = state["competitor_domain"]
    company = domain.replace(".com", "").replace(".io", "")
    logger.info("Run Socials")

    try:
        social_links = await _scrape_social_links(domain)
        youtube_url = social_links.get("youtube")
        youtube_content = await _scrape_yt_content_about_(youtube_url) if youtube_url else None
        search_results = await _scrape_yt_content_by_search_for(company)

        return {
            "socials": SocialData(
                social_links=social_links or None,
                youtube_content=youtube_content or None,
                yt_search_results=search_results or None,
                source="brandfetch",
            ),
            "completed_nodes": ["socials"],
        }
    except Exception as e:
        logger.error("node_failed", node="socials", error=str(e))
        return {"errors": [f"socials: {e}"]}


if __name__ == "__main__":
    import asyncio
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main():
        from app.agents.research.state import VisualsData, PositioningData, FinancialData, SeoGeoData, NewsData, EventsData, NewsletterData

        state = ResearchState(
            competitor_domain="celonis.com",
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
            print(result["socials"].model_dump_json(indent=2))

    asyncio.run(main())
