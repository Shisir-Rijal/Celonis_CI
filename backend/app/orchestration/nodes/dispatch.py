"""backend/app/orchestration/nodes/dispatch.py

Dispatch node — sequential capability execution with retry and conditional routing.

Issue #63: Dispatch node — sequential capability execution with retry and conditional routing
"""

import asyncio
from datetime import UTC, datetime

from app.orchestration.capability_registry import get_capability
from app.orchestration.state import AgentCall, WorkflowState


async def dispatch_node(state: WorkflowState) -> dict:
    """Execute decomposed tasks sequentially and collect AgentCall results.

    For each task:
    - Look up the capability by name in the registry
    - Call it with up to 3 attempts (asyncio.sleep(1) between retries)
    - On unknown capability or exhausted retries, record the error and continue

    Returns a dict updating:
      - agent_calls: list[AgentCall]
    """
    agent_calls: list[AgentCall] = []

    for task in state["decomposed_tasks"]:
        name: str = task.get("capability", "")
        params: dict = task.get("params", {})

        fn = get_capability(name)

        if fn is None:
            agent_calls.append(
                AgentCall(
                    capability=name,
                    input_params=params,
                    output={},
                    sources=[],
                    derivation="",
                    persist_to_rag=False,
                    started_at=None,
                    completed_at=None,
                    error="capability not found",
                )
            )
            continue

        started_at = datetime.now(UTC)
        result: AgentCall | None = None
        last_error: str | None = None

        for attempt in range(3):
            try:
                result = await fn(params)
                if not isinstance(result, AgentCall): 
                    raise TypeError(
                        f"Capability '{name}' must return an AgentCall, "
                        f"got {type(result).__name__!r}."
                    )  
                last_error = None
                break
            except Exception as exc:
                last_error = str(exc)
                if attempt < 2:
                    await asyncio.sleep(1)

        completed_at = datetime.now(UTC)

        if result is not None:
            agent_calls.append(
                result.model_copy(
                    update={"started_at": started_at, "completed_at": completed_at}
                )
            )
        else:
            agent_calls.append(
                AgentCall(
                    capability=name,
                    input_params=params,
                    output={},
                    sources=[],
                    derivation="",
                    persist_to_rag=False,
                    started_at=started_at,
                    completed_at=completed_at,
                    error=last_error,
                )
            )

    return {"agent_calls": agent_calls}


def should_correlate(state: WorkflowState) -> str:
    """Route to correlation if 2+ successful agent_calls, otherwise synthesize."""
    successful = sum(
        1 for call in state.get("agent_calls", []) if call.error is None
    )
    return "correlation" if successful >= 2 else "synthesize"