"""Workflows router — GET /workflows.

Placeholder for the autonomous workflow management interface.
Real endpoints (trigger, status, history) land in Phase 2 alongside
the ARQ worker setup.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("")
async def list_workflows() -> list:
    """Return the list of available autonomous workflows.

    Stub — returns an empty list until Phase 2 workflow definitions exist.
    """
    return []
