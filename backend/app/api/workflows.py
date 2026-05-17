"""Workflows router — GET /workflows.

Placeholder for the autonomous workflow management interface.
Real endpoints (trigger, status, history) land in Phase 2 alongside
the ARQ worker setup.
"""

from fastapi import APIRouter, Depends

from app.auth.dependencies import require_auth

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", dependencies=[Depends(require_auth)])
async def list_workflows() -> list:
    """Return the list of available autonomous workflows.

    Stub — returns an empty list until Phase 2 workflow definitions exist.
    """
    return []
