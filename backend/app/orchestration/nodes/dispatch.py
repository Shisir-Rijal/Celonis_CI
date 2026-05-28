"""backend/app/orchestration/nodes/dispatch.py

Dispatch node — stub only.
Real implementation in Issue #63.

Issue #61: stub created so graph compiles with both conditional paths
"""

from app.orchestration.state import WorkflowState


async def dispatch_node(state: WorkflowState) -> dict:
    # TODO: implement sequential capability execution in Issue #63
    return {}