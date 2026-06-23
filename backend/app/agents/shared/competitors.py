from supabase import create_client
from app.config import get_settings

async def get_competitor_domains() -> list[str]:
    settings = get_settings()
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    result = client.table("competitors").select("domain").eq("active", True).execute()
    return [row["domain"] for row in result.data]


async def get_competitor_names() -> dict[str, str]:
    """{domain: display name} for every active competitor, e.g. "ibm.com" ->
    "IBM", "uipath.com" -> "UiPath" — the real names from the competitors
    table (migration 009), not a naive domain.split(".")[0].capitalize()
    guess (which mangles multi-word/special-cased brands)."""
    settings = get_settings()
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    result = client.table("competitors").select("domain, name").eq("active", True).execute()
    return {row["domain"]: row["name"] for row in result.data}
