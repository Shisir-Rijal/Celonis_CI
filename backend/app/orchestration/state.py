from pydantic import BaseModel
from app.models.schemas import Chunk

"""backend/app/orchestration/state.py. Defines the WorkflowState
Pydantic model with fields for query input, intermediate agent
outputs, retrieved context, validation results, and final output."""

class WorkflowState(BaseModel):
    """this class defines the state of a workflow, including the query input, intermediate agent outputs, retrieved context, validation results, and final output."""
    query_input: str
    intermediate_agent_outputs: list[str] = []
    retrieved_context: list[Chunk] = []
    validation_results: list[str] = []
    final_output: str = ""