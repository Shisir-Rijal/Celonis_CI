from supabase import create_client
from app.config import get_settings

async def get_competitor_domains() -> list[str]:
    settings = get_settings()
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    result = client.table("competitors").select("domain").eq("active", True).execute()
    return [row["domain"] for row in result.data]
