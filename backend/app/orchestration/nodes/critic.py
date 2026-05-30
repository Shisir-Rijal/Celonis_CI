"""backend/app/orchestration/nodes/critic.py

Critic node — stub only (implementation separate).
Real logic: LLM-as-judge, hallucination detection, confidence scoring.

Issue #65: Critic node stub and graph wiring
"""

from app.orchestration.state import WorkflowState


async def critic_node(state: WorkflowState) -> dict:
    # TODO: replace stub with real Critic implementation (separate issue)
    return {}