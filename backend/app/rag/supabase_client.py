"""Module-level Supabase client.

The client is built once at import time using the global Settings and
reused for the entire application lifetime — no per-request instantiation.

Usage:
    from app.rag.supabase_client import get_supabase

    client = get_supabase()
    response = client.table("chunks").select("*").limit(1).execute()

The module raises ``RuntimeError`` at import time when the required
Supabase credentials (``SUPABASE_URL`` and ``SUPABASE_SERVICE_ROLE_KEY``)
are not present in settings. This surfaces misconfiguration immediately
on startup rather than failing silently on the first DB call.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Return the shared Supabase client, creating it on the first call.

    Uses the service-role key so the backend can bypass Row Level Security
    for write operations. The anon key is reserved for future client-side
    access once RLS policies are in place.

    Returns:
        A fully initialised ``supabase.Client`` instance.

    Raises:
        RuntimeError: If ``SUPABASE_URL`` or ``SUPABASE_SERVICE_ROLE_KEY``
            are not set in the environment / settings.
    """
    settings = get_settings()

    if not settings.SUPABASE_URL:
        raise RuntimeError(
            "SUPABASE_URL is not set. "
            "Add it to .env before using the RAG store."
        )
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not set. "
            "Add it to .env before using the RAG store."
        )

    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
