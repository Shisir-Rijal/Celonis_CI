"""Unit tests for partial failure handling in news.run().

Issue #109
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.exceptions import NewsError
from app.agents.research.state import (
    ResearchState, NewsData, NewsItem,
    VisualsData, PositioningData, FinancialData,
    SocialData, SeoGeoData, EventsData, NewsletterData,
)


def _make_state(domain: str = "celonis.com") -> ResearchState:
    return ResearchState(
        competitor_domain=domain,
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


def _make_news_item(heading: str) -> NewsItem:
    return NewsItem(heading=heading, date="2024-01-15")


@pytest.mark.asyncio
async def test_finnhub_fails_serper_and_firecrawl_succeed():
    serper_items = [_make_news_item("Serper article")]
    firecrawl_items = [_make_news_item("Firecrawl article")]

    with (
        patch("app.agents.research.nodes.news._get_symbol", side_effect=Exception("finnhub down")),
        patch("app.agents.research.nodes.news._get_serper_news", new=AsyncMock(return_value=serper_items)),
        patch("app.agents.research.nodes.news._get_firecrawl_news", new=AsyncMock(return_value=firecrawl_items)),
    ):
        from app.agents.research.nodes.news import run
        result = await run(_make_state())

    assert "news" in result
    assert len(result["news"].news) == 2


@pytest.mark.asyncio
async def test_all_sources_fail_raises_news_error():
    with (
        patch("app.agents.research.nodes.news._get_symbol", side_effect=Exception("finnhub down")),
        patch("app.agents.research.nodes.news._get_serper_news", new=AsyncMock(side_effect=Exception("serper down"))),
        patch("app.agents.research.nodes.news._get_firecrawl_news", new=AsyncMock(side_effect=Exception("firecrawl down"))),
    ):
        from app.agents.research.nodes.news import run
        with pytest.raises(NewsError) as exc_info:
            await run(_make_state())

    assert "finnhub" in str(exc_info.value)
    assert "serper" in str(exc_info.value)
    assert "firecrawl" in str(exc_info.value)


@pytest.mark.asyncio
async def test_all_sources_return_empty_no_error():
    with (
        patch("app.agents.research.nodes.news._get_symbol", return_value=None),
        patch("app.agents.research.nodes.news._get_serper_news", new=AsyncMock(return_value=[])),
        patch("app.agents.research.nodes.news._get_firecrawl_news", new=AsyncMock(return_value=[])),
    ):
        from app.agents.research.nodes.news import run
        result = await run(_make_state())

    assert "news" in result
    assert len(result["news"].news) == 0


@pytest.mark.asyncio
async def test_warning_logged_per_failed_source():
    with (
        patch("app.agents.research.nodes.news._get_symbol", side_effect=Exception("finnhub down")),
        patch("app.agents.research.nodes.news._get_serper_news", new=AsyncMock(side_effect=Exception("serper down"))),
        patch("app.agents.research.nodes.news._get_firecrawl_news", new=AsyncMock(return_value=[_make_news_item("article")])),
        patch("app.agents.research.nodes.news.logger") as mock_logger,
    ):
        from app.agents.research.nodes.news import run
        await run(_make_state())

    assert mock_logger.warning.call_count == 2