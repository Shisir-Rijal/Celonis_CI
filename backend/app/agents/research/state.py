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
    logo: list[str] = []  
    colors: dict[str, list[str]] = {}  # {"primary": [...], "secondary": [...]}
    fonts: list[str] | None = None
    images: list[str] | None = None
    animations: dict[str, Any] | None = None
    videos: list[str] = [] 
    icons: dict[str, Any] | None = None
    # diagrams?

class EventsData(BaseData):
    website_events: list[Any] | None = None
    luma_events: list[Any] | None = None
    meetup_events: list[Any] | None = None
    reported_events: list[Any] | None = None

class BlogData(BaseModel):
    heading: str | None = None
    subheading: str | None = None
    content: str | list[str] | None = None
    source_link: str | None = None
    publishing_date: str | None = None

class PositioningData(BaseData):
    purpose: str | None = None
    vision: str | None = None
    mission: str | None = None
    company_values : dict[str, Any] | None = None
    employer_values: dict[str, Any] | str | None = None
    employer_positioning: str | None = None
    blogs: list[BlogData] | dict[str, Any] | None = None
    job_positing_employer_description: str | None = None

class NewsletterData(BaseData):
    newsletter: dict[str, Any] | None = None

class FinancialData(BaseData):
    # Listed?
    on_stock_market: bool = False
    # Aktienkurs
    current_stock_price: float | None = None
    stock_change: float | None = None
    percent_change: float | None = None
    # Evaluation
    # market_cap: float | int | None = None     -> need advanced API (paid for)
    # revenue: float | None = None              -> need advanced API (paid for)
    # Analysis
    analyst_buy: int | None = None
    analyst_hold: int | None = None
    analyst_sell: int | None = None
    # History
    price_history: dict[str, float] = {}

class SocialData(BaseData):
    social_links: dict[str, str] | None = None
    youtube_content: Any | None = None
    yt_search_results: list[Any] | None = None

class SeoKeywordSighting(BaseModel):
    keyword: str
    company_mentioned: bool = False
    position: int | None = None  # rank in Google results (1–10)
    link: str | None = None

class GeoKeywordSighting(BaseModel):
    keyword: str
    llm: str  # which model was queried
    company_mentioned: bool = False
    context: str | None = None  # excerpt from LLM response mentioning the company

class SeoGeoData(BaseData):
    seo: list[SeoKeywordSighting] = []
    geo: list[GeoKeywordSighting] = []

class NewsData(BaseData):
    news: list[Any] = []

class Additionals(BaseData):
    description: str | None # .company_profile Finnhub


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

