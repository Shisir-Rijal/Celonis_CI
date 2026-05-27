import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.config import get_settings
import httpx
from pydantic import BaseModel


class VideoData(BaseModel):
    title: str | None = None
    description: str | None = None
    date: str | None = None
    thumbnail: str | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    published_by: str | None = None  # channel name
    url: str | None = None


async def _scrape_yt_content_by_search_for(query: str, max_results: int = 10) -> list[VideoData]:
    api_key = get_settings().YOUTUBE_API_KEY
    if not api_key:
        return []
    async with httpx.AsyncClient() as client:
        search_resp = await client.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"q": query, "type": "video", "maxResults": max_results, "part": "snippet", "key": api_key},
            timeout=10,
        )
        items = search_resp.json().get("items", [])
        if not items:
            return []

        video_ids = [v["id"]["videoId"] for v in items if v.get("id", {}).get("videoId")]
        stats_resp = await client.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "statistics", "id": ",".join(video_ids), "key": api_key},
            timeout=10,
        )
        vstats = {v["id"]: v.get("statistics", {}) for v in stats_resp.json().get("items", [])}

    videos = []
    for item in items:
        vid_id = item.get("id", {}).get("videoId")
        s = item.get("snippet", {})
        st = vstats.get(vid_id, {})
        videos.append(VideoData(
            title=s.get("title"),
            description=s.get("description"),
            date=s.get("publishedAt"),
            thumbnail=s.get("thumbnails", {}).get("high", {}).get("url"),
            published_by=s.get("channelTitle"),
            url=f"https://www.youtube.com/watch?v={vid_id}" if vid_id else None,
            view_count=int(st["viewCount"]) if st.get("viewCount") else None,
            like_count=int(st["likeCount"]) if st.get("likeCount") else None,
            comment_count=int(st["commentCount"]) if st.get("commentCount") else None,
        ))
    return videos
