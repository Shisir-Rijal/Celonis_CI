# Gemeinsamer Datenspeicher

from typing import TypedDict, Annotated, Any
from pydantic import BaseModel, Field
from datetime import datetime
import operator


# --- BaseData: Time and Source for all BaseModels

class BaseData(BaseModel):
    source: str | None = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)


# --- BaseModels: Sub-Models

class VisualsData(BaseData): 
    logo: str | None = None
    colors: list[str] = []
    typography: str | None = None
    images: list[str] | None = None
    graphics: list[str] | None = None
    animations: dict[str, Any] | None = None
    videos: dict[str, Any] = {}
    icons: dict[str, Any] | None = None
    diagrams: dict[str, Any] | None = None
    illustrations: dict[str, Any] | None = None

class EventsData(BaseData):
    website_events: list[tuple] | None = None
    udemy_events: list[tuple] | None = None
    loma_events: list[tuple] | None = None
    meetup_events: list[tuple] | None = None
    event_reports: list[tuple] | None = None # Youtube auch?

class PositioningData(BaseData):
    purpose: str | None = None
    vision: str | None = None
    mission: str | None = None
    values: dict[str, Any] | None = None
    blogs: dict[str, Any] | None = None

class NewsletterData(BaseData):
    newsletter: dict[str, Any] | None = None

class FinancialData(BaseData):      
    revenue: float | None = None
    stock_price: float | None = None
    on_stock_market: bool = False
    market_share: float | int | None = None

class SocialLinks(BaseData):
    instagram: str | None = None
    linkedin: str | None = None
    facebook: str | None = None
    reddit: str | None = None
    youtube: str | None = None
    tiktok: str | None = None
    website: str | None = None

class SocialData(BaseData):
    social_links: SocialLinks = Field(default_factory=SocialLinks)
    reddit_content: dict[str, Any] | None = None
    youtube_content: dict[str, Any] | None = None

class SeoGeoData(BaseData):
    seo: dict[str, Any] = {}
    geo: dict[str, Any] = {} 

class NewsData(BaseData):
    news: dict[str, Any] = {}
    articles: dict[str, Any] = {}


# --- AgentState:

class ResearchState(TypedDict):
    competitor_domain: str
    visuals: VisualsData
    positioning: PositioningData
    financials: FinancialData
    socials: SocialData
    seogeo: SeoGeoData
    news: NewsData
    events: EventsData
    newsletter: NewsletterData
    errors: Annotated[list[str], operator.add]
    completed_nodes: Annotated[list[str], operator.add]


# --- CompetitorProfile:

class CompetitorProfile(BaseModel):
    domain: str
    company_name: str | None = None
    visuals: VisualsData = Field(default_factory=VisualsData)
    positioning: PositioningData = Field(default_factory=PositioningData)
    financials: FinancialData = Field(default_factory=FinancialData)
    socials: SocialData = Field(default_factory=SocialData)
    seogeo: SeoGeoData = Field(default_factory=SeoGeoData)
    news: NewsData = Field(default_factory=NewsData)
    events: EventsData = Field(default_factory=EventsData)
    newsletter: NewsletterData = Field(default_factory=NewsletterData)

    @classmethod
    def from_state(cls, state: ResearchState) -> "CompetitorProfile":
        return cls(
            domain=state["competitor_domain"],
            visuals=state["visuals"],
            positioning=state["positioning"],
            financials=state["financials"],
            socials=state["socials"],
            seogeo=state["seogeo"],
            news=state["news"],
            events=state["events"],
            newsletter=state["newsletter"],
        )

