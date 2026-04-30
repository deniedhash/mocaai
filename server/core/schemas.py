"""
MOCA Shared Schemas — all Pydantic models and LangGraph state used across
the agent system. Single source of truth for structured data contracts.
"""

import operator
from typing import Annotated, Any, Optional
from typing_extensions import NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Valid agent names (used for routing validation)
# ---------------------------------------------------------------------------

VALID_AGENTS = frozenset({
    "hermes", "athena", "vulcan", "apollo", "aegis",
    "mercury", "hestia", "cronos", "mnemosyne",
})


# ---------------------------------------------------------------------------
# Routing decision — output of prime_router
# ---------------------------------------------------------------------------

class RoutingDecision(BaseModel):
    """LLM-generated routing decision produced by prime_router_node."""

    agent: str = Field(
        description=(
            "The agent to route to. Must be one of: "
            "hermes, athena, vulcan, apollo, aegis, mercury, hestia, cronos, "
            "mnemosyne. Use 'prime' only if no specialist applies."
        )
    )
    reasoning: str = Field(
        description="One sentence explaining why this agent was chosen."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Routing confidence from 0.0 (unsure) to 1.0 (certain).",
    )
    is_multi_domain: bool = Field(
        default=False,
        description="True if the request requires more than one specialist agent.",
    )
    sub_tasks: list[str] = Field(
        default_factory=list,
        description="Individual sub-tasks for multi-domain requests.",
    )
    additional_agents: list[str] = Field(
        default_factory=list,
        description="Additional agents to invoke for multi-domain requests.",
    )


# ---------------------------------------------------------------------------
# Agent response — output of every domain agent node
# ---------------------------------------------------------------------------

class AgentResponse(BaseModel):
    """Structured response returned by each domain agent to prime_synthesizer."""

    agent_name: str
    domain: str
    response: str
    actions_taken: list[str] = Field(default_factory=list)
    follow_up: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.9)


# ---------------------------------------------------------------------------
# MOCA LangGraph state
# ---------------------------------------------------------------------------

class MOCAState(TypedDict):
    """Full state passed through the MOCA LangGraph graph."""

    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    routing_decision: Optional[RoutingDecision]
    # operator.add reducer means each agent appends, not overwrites
    agent_responses: Annotated[list[AgentResponse], operator.add]
    conversation_history: list[dict]
    final_response: Optional[str]
    # Phase 3 — memory layer (NotRequired = optional channel; agents that don't
    # touch these fields can safely return partial dicts without crashing LangGraph)
    relevant_memories: NotRequired[list[dict]]   # semantic search hits from past sessions
    extracted_facts: NotRequired[list[dict]]     # recently extracted knowledge
    # Phase 5 — context engine snapshot for this request
    current_context: NotRequired[Optional[Any]]  # MOCAContext dataclass instance
    # Phase 6b — dual brain: MOCABrain instance injected by routes, read by agents
    brain: NotRequired[Optional[Any]]
