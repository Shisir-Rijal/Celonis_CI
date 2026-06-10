"""Research agent scheduler — arq worker with tier-based cron jobs.

Start the worker alongside the FastAPI server:

    arq app.agents.research.scheduler.WorkerSettings

Each job iterates over all tracked competitor domains and invokes the
matching tier graph. Tier graphs only write their own state keys, so
partial runs accumulate correctly across cadences.

Cadence overview:
    daily      06:00 UTC        — financials
    weekly     Mon 07:00 UTC    — news
    monthly    1st 08:00 UTC    — events, seogeo, newsletter, youtube
    semiannual Jan 1 + Jul 1    — visuals, positioning, socials, wording
"""

import structlog
from urllib.parse import urlparse

from arq import cron
from arq.connections import RedisSettings

from app.agents.research.graph import (
    daily_graph,
    weekly_graph,
    monthly_graph,
    semiannual_graph,
)
from app.config import get_settings

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Domain source
# ---------------------------------------------------------------------------

async def _get_tracked_domains() -> list[str]:
    """Return all competitor domains to be scraped.

    TODO: replace with a Supabase query once the competitors table exists.
    """
    return []


# ---------------------------------------------------------------------------
# Tier jobs
# ---------------------------------------------------------------------------

async def _run_tier(graph, tier: str) -> None:
    domains = await _get_tracked_domains()
    if not domains:
        logger.warning("no_domains_tracked", tier=tier)
        return

    for domain in domains:
        initial_state = {
            "competitor_domain": domain,
            "errors": [],
            "completed_nodes": [],
        }
        try:
            result = await graph.ainvoke(initial_state)
            logger.info(
                "tier_completed",
                tier=tier,
                domain=domain,
                completed=result.get("completed_nodes", []),
            )
            if result.get("errors"):
                logger.warning(
                    "tier_errors",
                    tier=tier,
                    domain=domain,
                    errors=result["errors"],
                )
        except Exception as e:
            logger.error("tier_failed", tier=tier, domain=domain, error=str(e))


async def run_daily(_ctx: dict) -> None:
    await _run_tier(daily_graph, "daily")


async def run_weekly(ctx: dict) -> None:
    await _run_tier(weekly_graph, "weekly")


async def run_monthly(ctx: dict) -> None:
    await _run_tier(monthly_graph, "monthly")


async def run_semiannual(ctx: dict) -> None:
    await _run_tier(semiannual_graph, "semiannual")


# ---------------------------------------------------------------------------
# Worker configuration
# ---------------------------------------------------------------------------

def _redis_settings() -> RedisSettings:
    url = get_settings().REDIS_URL or "redis://localhost:6379"
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/") or 0),
        password=parsed.password,
    )


class WorkerSettings:
    functions = [run_daily, run_weekly, run_monthly, run_semiannual]
    cron_jobs = [
        cron(run_daily,      hour=6,  minute=0),                       # 06:00 UTC every day
        cron(run_weekly,     weekday=0, hour=7, minute=0),             # Monday 07:00 UTC
        cron(run_monthly,    day=1,   hour=8, minute=0),               # 1st of month 08:00 UTC
        cron(run_semiannual, month={1, 7}, day=1, hour=9, minute=0),  # Jan 1 + Jul 1 09:00 UTC
    ]
    redis_settings = _redis_settings()
