import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import asyncio
import structlog
import httpx
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.agents.research.state import ResearchState, YoutubeData, YoutubeChannelData, YtSearchData
from app.agents.research.repositories.research_repository import insert_research_snapshot, snapshot_exists
from app.agents.shared.utils.youtube import _scrape_yt_content_by_search_for, VideoData
from app.config import get_settings

logger = structlog.get_logger(__name__)


def _channel_param_from_url(url: str) -> dict:
    """Derive the correct YouTube Data API parameter from a channel URL."""
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
    path = urlparse(url).path.strip("/")
    if path:
        return {"forHandle": f"@{path}"}
    return {}


async def _scrape_channel(youtube_url: str, company: str) -> YoutubeChannelData | None:
    api_key = get_settings().YOUTUBE_API_KEY
    if not api_key or not youtube_url:
        return None

    channel_param = _channel_param_from_url(youtube_url)
    if not channel_param:
        return None

    async with httpx.AsyncClient() as client:
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

        videos_resp = await client.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "channelId": channel_id, "part": "snippet", "order": "date",
                "maxResults": 10, "type": "video", "key": api_key,
            },
            timeout=10,
        )
        video_items = videos_resp.json().get("items", [])
        video_ids = [v["id"]["videoId"] for v in video_items if v.get("id", {}).get("videoId")]

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

    return YoutubeChannelData(
        company=company,
        url=youtube_url,
        title=f"YouTube: {company}",
        subscribers=int(stats["subscriberCount"]) if stats.get("subscriberCount") else None,
        video_count=int(stats["videoCount"]) if stats.get("videoCount") else None,
        description=snippet.get("description"),
        own_videos=videos,
    )


async def run(state: ResearchState) -> dict:
    domain = state["competitor_domain"]
    if snapshot_exists(domain, "youtube"):
        logger.info("node_skipped_cached", node="youtube", domain=domain)
        return {"completed_nodes": ["youtube"]}
    company = domain.split(".")[0].capitalize()
    logger.info("run_youtube", domain=domain)

    # Read the YouTube URL that was stored by the socials node
    socials = state.get("socials")
    youtube_url = socials.social_links.get("youtube") if socials and socials.social_links else None
    if not youtube_url:
        logger.info("youtube_url_not_found", domain=domain, hint="run socials node first")

    try:
        channel, search_videos = await asyncio.gather(
            _scrape_channel(youtube_url, company) if youtube_url else asyncio.sleep(0, result=None),
            _scrape_yt_content_by_search_for(company),
        )

        youtube_data = YoutubeData(
            channel=channel,
            search=YtSearchData(
                company=company,
                url=f"https://www.youtube.com/results?search_query={company}",
                title=f"YouTube Search: {company}",
                videos=search_videos or [],
            ) if search_videos else None,
        )
        try:
            insert_research_snapshot(domain, datetime.now(timezone.utc), "youtube", youtube_data)
        except Exception as db_err:
            logger.warning("snapshot_write_failed", node="youtube", error=str(db_err))
        return {
            "youtube": youtube_data,
            "completed_nodes": ["youtube"],
        }
    except Exception as e:
        logger.error("node_failed", node="youtube", error=str(e))
        return {"errors": [f"youtube: {e}"]}


if __name__ == "__main__":
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main():
        from app.agents.research.state import SocialData
        state = ResearchState(
            competitor_domain="celonis.com",
            socials=SocialData(
                company="Celonis",
                url="https://celonis.com",
                social_links={"youtube": "https://www.youtube.com/@celonis"},
            ),
            errors=[],
            completed_nodes=[],
        )
        result = await run(state)
        if result.get("errors"):
            print("Errors:", result["errors"])
        else:
            yt = result.get("youtube")
            if yt and yt.channel:
                print(yt.channel.model_dump_json(indent=2))
            if yt and yt.search:
                print(yt.search.model_dump_json(indent=2))

    asyncio.run(main())
