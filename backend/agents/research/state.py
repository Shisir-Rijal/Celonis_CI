# Gemeinsamer Datenspeicher
from typing import TypeDict, List

class AgentSate(TypeDict):
    company_name = str
    company_website = str
    purpose = str
    vision = str
    mission = str
    values = dict[str]
    news = dict[str]
    events = list[tuple], None
    logo = str
    colors = str
    typo = str
    images = list[str]
    graphics = list[str]
    animations = list[str], None
    videos = dict[str]
    icons = dict[str], None
    diagrams = dict[str], None
    illustrations = dict[str], None
    social_links = dict[str]
    reddit_content = dict[str]
    stock_price = float, None
    market_share = float, int, None
    revenue = float, int, None
    on_stock_market = bool
    seo = dict[str]
    geo = dict[str]
    errors = list[str], None

    agent_outcome_news = list[str], None
    
