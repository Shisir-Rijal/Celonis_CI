"""backend/app/orchestration/nodes/correlation.py

Correlation node — stub only (Phase 1).
Real Correlation Agent implementation is a separate issue, different assignee.

Issue #63: stub created for conditional edge wiring
"""

from app.orchestration.state import WorkflowState


async def correlation_node(state: WorkflowState) -> dict:
    # TODO: implement real Correlation Agent in a future issue
    return {}