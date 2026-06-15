"""Run Research Agent tiers without ARQ/Redis.

Usage (from backend/ directory):

    uv run python scripts/run_research.py              # runs all tiers
    uv run python scripts/run_research.py daily        # only financials
    uv run python scripts/run_research.py weekly       # only news
    uv run python scripts/run_research.py monthly      # events, seogeo, newsletter, youtube
    uv run python scripts/run_research.py semiannual   # visuals, positioning, socials, wording
    uv run python scripts/run_research.py --domain uipath.com monthly  # single domain
"""

import asyncio
import sys
from pathlib import Path

# allow running from repo root or backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Use the OS certificate store on Windows (fixes SSL_CERTIFICATE_VERIFY_FAILED)
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import structlog
from app.agents.research.graph import (
    daily_graph,
    monthly_graph,
    semiannual_graph,
    weekly_graph,
)
from app.rag.supabase_client import get_supabase

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])
logger = structlog.get_logger(__name__)

GRAPHS = {
    "daily": daily_graph,
    "weekly": weekly_graph,
    "monthly": monthly_graph,
    "semiannual": semiannual_graph,
}


async def get_domains(domain_override: str | None) -> list[str]:
    if domain_override:
        return [domain_override]
    db = get_supabase()
    resp = db.table("competitors").select("domain").eq("active", True).execute()
    return [row["domain"] for row in resp.data]


async def run_tier(tier: str, domains: list[str]) -> None:
    graph = GRAPHS[tier]
    logger.info("tier_started", tier=tier, domain_count=len(domains))

    for domain in domains:
        logger.info("domain_started", tier=tier, domain=domain)
        try:
            result = await graph.ainvoke({
                "competitor_domain": domain,
                "errors": [],
                "completed_nodes": [],
            })
            completed = result.get("completed_nodes", [])
            errors = result.get("errors", [])
            logger.info("domain_done", domain=domain, completed=completed)
            if errors:
                logger.warning("domain_errors", domain=domain, errors=errors)
        except Exception as e:
            logger.error("domain_failed", domain=domain, tier=tier, error=str(e))

    logger.info("tier_done", tier=tier)


async def main() -> None:
    args = sys.argv[1:]

    # parse optional --domain flag
    domain_override = None
    if "--domain" in args:
        idx = args.index("--domain")
        domain_override = args[idx + 1]
        args = [a for i, a in enumerate(args) if i != idx and i != idx + 1]

    # determine which tiers to run
    valid_tiers = list(GRAPHS.keys())
    requested = [a for a in args if a in valid_tiers]
    if not requested:
        requested = valid_tiers  # run all if none specified

    domains = await get_domains(domain_override)
    if not domains:
        logger.error("no_domains_found", hint="Add competitors to the competitors table in Supabase")
        return

    logger.info("run_started", tiers=requested, domains=domains)

    for tier in requested:
        await run_tier(tier, domains)

    logger.info("all_done")


if __name__ == "__main__":
    asyncio.run(main())
