"""Health check router."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Return service health status.

    Always returns 200 with ``{"status": "healthy"}``. Used by load
    balancers and uptime monitors to check the process is alive.
    """
    return {"status": "healthy"}
