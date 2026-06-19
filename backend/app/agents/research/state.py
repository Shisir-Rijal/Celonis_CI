import re
from typing import TypedDict, Annotated, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone
import operator
from app.models.schemas import ChunkMetadata
from datetime import date
from typing import Literal
from app.agents.shared.utils.youtube import VideoData

today = date.today().strftime("%Y-%m-%d")


# --- BaseData: shared RAG metadata for every chunk

class BaseData(BaseModel):
    # always required
    company: str
    url: str
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entities: list[str] = []
    # optional — subclasses set chunk-specific defaults
    source_type: str | None = None
    source_origin: Literal["owned", "earned", "third_party", "internal"] | None = None
    title: str | None = None
    language: str | None = None
    topic: list[str] = Field(default_factory=list)
    content_type: Literal["text", "image", "transcript"] | None = None
    visual_type: str | None = None
    chunking_strategy: Literal["structural", "none", "agentic"] | None = None



# --- Node-Models:


# --Events-Node:

class EventsData(BaseModel):
    website_events: list[Any] | None = None
    luma_events: list[Any] | None = None
    meetup_events: list[Any] | None = None
    reported_events: list[Any] | None = None

class EventItem(BaseData):
    # --- chunk constants ---
    content_type: Literal["text"] = "text"
    chunking_strategy: Literal["agentic"] = "agentic"
    topic: list[str] = Field(default_factory=lambda: ["events"])
    # source_origin varies: "owned" (website), "third_party" (meetup/luma), "earned" (news)

    # --- event-specific ---
    name: str | None = None
    event_date: str | None = None      # when the event takes place (≠ BaseData.date = scrape date)
    end_date: str | None = None
    start_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    attendees: int | None = None
    location: str | None = None
    event_topic: str | None = None     # human-readable topic string (≠ BaseData.topic = RAG tags)

    @field_validator("attendees", mode="before")
    @classmethod
    def coerce_attendees(cls, v: object) -> int | None:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            m = re.match(r"[\d,]+", v.strip())
            if m:
                return int(m.group().replace(",", ""))
        return None
    organized_by: str | None = None
    sponsors: list[str] | None = None
    speakers: list[str] | None = None
    summary: str | list[str] | None = None
    source_link: str | None = None
    image: str | None = None
    video: str | None = None


# --Financials-Node:

class FinancialData(BaseData):
    # --- chunk constants ---
    source_type: str | None = "finnhub"
    source_origin: Literal["owned", "earned", "third_party", "internal"] = "earned"
    content_type: Literal["text"] = "text"
    chunking_strategy: Literal["none"] = "none"
    topic: list[str] = Field(default_factory=lambda: ["financials"])

    # --- financials-specific ---
    # market_cap: float | int | None = None     -> need advanced API (paid for)
    # revenue: float | None = None              -> need advanced API (paid for)
    on_stock_market: bool = False
    current_stock_price: float | None = None
    stock_change: float | None = None
    percent_change: float | None = None
    analyst_buy: int | None = None
    analyst_hold: int | None = None
    analyst_sell: int | None = None
    price_history: dict[str, float] = {}


# --News-Node:

class NewsItem(BaseData):
    # --- chunk constants ---
    source_origin: Literal["owned", "earned", "third_party", "internal"] = "earned"
    content_type: Literal["text"] = "text"
    chunking_strategy: Literal["agentic"] = "agentic"
    topic: list[str] = Field(default_factory=lambda: ["news"])

    # --- news-specific ---
    heading: str | None = None
    text: str | None = None
    image: str | None = None
    author: str | None = None
    summary: str | None = None
    published_date: str | None = None  # publication date string (≠ BaseData.date = scrape date)

class NewsData(BaseModel):
    news: list[Any] = []


# --Newsletter-Node:

class NewsletterData(BaseData):
    # --- chunk constants ---
    source_origin: Literal["owned", "earned", "third_party", "internal"] = "owned"
    content_type: Literal["text"] = "text"
    chunking_strategy: Literal["structural"] = "structural"
    topic: list[str] = Field(default_factory=lambda: ["newsletter"])

    # --- newsletter-specific ---
    newsletter: dict[str, Any] | None = None


# --Positioning-Node:

class BlogData(BaseData):
    # --- chunk constants ---
    source_origin: Literal["owned", "earned", "third_party", "internal"] = "owned"
    content_type: Literal["text"] = "text"
    chunking_strategy: Literal["agentic"] = "agentic"
    topic: list[str] = Field(default_factory=lambda: ["blog", "positioning"])

    # --- blog-specific ---
    heading: str | None = None
    subheading: str | None = None
    content: str | list[str] | None = None
    source_link: str | None = None
    publishing_date: str | None = None


# --Positioning-Node:

class PositioningData(BaseData):
    # --- chunk constants ---
    source_origin: Literal["owned", "earned", "third_party", "internal"] = "owned"
    content_type: Literal["text"] = "text"
    chunking_strategy: Literal["structural"] = "structural"
    topic: list[str] = Field(default_factory=lambda: ["positioning"])

    # --- positioning-specific ---
    purpose: str | None = None
    vision: str | None = None
    mission: str | None = None
    company_values: dict[str, Any] | None = None
    employer_values: dict[str, Any] | str | None = None
    employer_positioning: str | None = None
    blogs: list[BlogData] | dict[str, Any] | None = None
    job_positing_employer_description: str | None = None


# --SeoGeo-Node:

class SeoKeywordSighting(BaseData):
    # --- chunk constants ---
    source_type: str | None = "serper_seo"
    source_origin: Literal["owned", "earned", "third_party", "internal"] = "third_party"
    content_type: Literal["text"] = "text"
    chunking_strategy: Literal["none"] = "none"
    topic: list[str] = Field(default_factory=lambda: ["seo"])

    # --- seo-specific ---
    keyword: str
    company_mentioned: bool = False
    position: int | None = None  # rank in Google results (1–10)
    link: str | None = None

class GeoKeywordSighting(BaseData):
    # --- chunk constants ---
    source_origin: Literal["owned", "earned", "third_party", "internal"] = "third_party"
    content_type: Literal["text"] = "text"
    chunking_strategy: Literal["none"] = "none"
    topic: list[str] = Field(default_factory=lambda: ["geo"])
    # source_type varies by LLM (e.g. "geo_gpt-4o-mini", "geo_gemini-2.0-flash")

    # --- geo-specific ---
    keyword: str
    llm: str  # which model was queried
    company_mentioned: bool = False
    context: str | None = None  # excerpt from LLM response mentioning the company

class SeoGeoData(BaseModel):
    seo: list[SeoKeywordSighting] = []
    geo: list[GeoKeywordSighting] = []


# --Socials-Node:

class SocialData(BaseData):
    # --- chunk constants ---
    source_origin: Literal["owned", "earned", "third_party", "internal"] = "owned"
    content_type: Literal["text"] = "text"
    chunking_strategy: Literal["none"] = "none"
    topic: list[str] = Field(default_factory=lambda: ["social_media"])
    source_type: str | None = "brandfetch"

    # --- socials-specific (social links only) ---
    social_links: dict[str, str] | None = None


# --Youtube-Node:

class YoutubeChannelData(BaseData):
    # owned channel data from YouTube Data API
    source_origin: Literal["owned", "earned", "third_party", "internal"] = "owned"
    source_type: str | None = "youtube_api"
    content_type: Literal["text"] = "text"
    chunking_strategy: Literal["structural"] = "structural"
    topic: list[str] = Field(default_factory=lambda: ["youtube", "social_media"])

    subscribers: int | None = None
    video_count: int | None = None
    description: str | None = None
    own_videos: list[VideoData] = []


class YtSearchData(BaseData):
    # third-party YouTube search results about the company
    source_origin: Literal["owned", "earned", "third_party", "internal"] = "third_party"
    source_type: str | None = "youtube_search"
    content_type: Literal["text"] = "text"
    chunking_strategy: Literal["structural"] = "structural"
    topic: list[str] = Field(default_factory=lambda: ["youtube", "social_media"])

    videos: list[VideoData] = []


class YoutubeData(BaseModel):
    # container — mirrors SeoGeoData pattern
    channel: YoutubeChannelData | None = None
    search: YtSearchData | None = None


# --Visuals-Node:

class FontInfo(BaseModel):
    name: str
    type: str | None = None              # e.g. "Heading", "Body" (from Brandfetch)
    weights: list[str] | None = None     # e.g. ["400", "700"]
    sizes: list[str] | None = None       # e.g. ["14px", "48px"] — sizes the font is used at on-page


class SourcedAsset(BaseModel):
    url: str
    source_page: str | None = None  # the page URL this image/video was scraped from


class VisualsData(BaseData):
    # --- chunk constants ---
    source_origin: Literal["owned", "earned", "third_party", "internal"] = "owned"
    content_type: Literal["text"] = "text"   # URLs + descriptions, not binary images
    chunking_strategy: Literal["none"] = "none"
    visual_type: str | None = "brand_assets"
    topic: list[str] = Field(default_factory=lambda: ["visuals", "brand"])
    source_type: str | None = "brandfetch+firecrawl"

    # --- visuals-specific ---
    logo: list[str] = []
    colors: dict[str, list[str]] = {}  # {"primary": [...], "secondary": [...]}
    fonts: list[FontInfo] | None = None
    images: list[SourcedAsset] | None = None
    animations: dict[str, Any] | None = None
    videos: list[SourcedAsset] = []
    icons: dict[str, Any] | None = None


# --Wording-Node:

class WordingData(BaseData):
    # --- chunk constants ---
    source_type: str | None = "finnhub+firecrawl"
    source_origin: Literal["owned", "earned", "third_party", "internal"] = "owned"
    content_type: Literal["text"] = "text"
    chunking_strategy: Literal["none"] = "none"
    topic: list[str] = Field(default_factory=lambda: ["wording", "brand"])

    # --- wording-specific ---
    description: str | None = None  # .company_profile Finnhub


# --- AgentState:

class ResearchState(TypedDict):
    competitor_domain: str
    visuals: VisualsData
    positioning: PositioningData
    financials: FinancialData
    socials: SocialData
    youtube: YoutubeData | None
    seogeo: SeoGeoData
    news: NewsData
    events: EventsData
    newsletter: NewsletterData
    wording: WordingData
    errors: Annotated[list[str], operator.add]
    completed_nodes: Annotated[list[str], operator.add]


# --- CompetitorProfile:

class CompetitorProfile(BaseModel):
    domain: str
    company_name: str | None = None
    # BaseData subclasses require company+url, so None until populated via from_state
    visuals: VisualsData | None = None
    positioning: PositioningData | None = None
    financials: FinancialData | None = None
    socials: SocialData | None = None
    youtube: YoutubeData | None = None
    newsletter: NewsletterData | None = None
    wording: WordingData | None = None
    # Container models have safe empty defaults
    seogeo: SeoGeoData = Field(default_factory=SeoGeoData)
    news: NewsData = Field(default_factory=NewsData)
    events: EventsData = Field(default_factory=EventsData)

    @classmethod
    def from_state(cls, state: ResearchState) -> "CompetitorProfile":
        return cls(
            domain=state["competitor_domain"],
            visuals=state.get("visuals"),
            positioning=state.get("positioning"),
            financials=state.get("financials"),
            socials=state.get("socials"),
            youtube=state.get("youtube"),
            seogeo=state.get("seogeo") or SeoGeoData(),
            news=state.get("news") or NewsData(),
            events=state.get("events") or EventsData(),
            newsletter=state.get("newsletter"),
            wording=state.get("wording"),
        )
