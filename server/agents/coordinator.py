"""
Multi-Domain Coordinator — handles requests that span multiple agents.

Called by the orchestrator when prime_router sets is_multi_domain=True.
Executes each required agent in sequence and accumulates responses.
"""

from core.schemas import AgentResponse, MOCAState

# Import all agent node functions
from agents.hermes import node as hermes_node
from agents.athena import node as athena_node
from agents.vulcan import node as vulcan_node
from agents.apollo import node as apollo_node
from agents.aegis import node as aegis_node
from agents.mercury import node as mercury_node
from agents.hestia import node as hestia_node
from agents.cronos import node as cronos_node
from agents.mnemosyne import node as mnemosyne_node

_AGENT_MAP = {
    "hermes":    hermes_node,
    "athena":    athena_node,
    "vulcan":    vulcan_node,
    "apollo":    apollo_node,
    "aegis":     aegis_node,
    "mercury":   mercury_node,
    "hestia":    hestia_node,
    "cronos":    cronos_node,
    "mnemosyne": mnemosyne_node,
}


def coordinator_node(state: MOCAState) -> dict:
    """
    Sequentially invoke all agents required for a multi-domain request.
    Collects their AgentResponse objects for prime_synthesizer to unify.
    """
    routing = state.get("routing_decision")
    if not routing:
        return {"agent_responses": []}

    agents_to_run: list[str] = []
    if routing.agent in _AGENT_MAP:
        agents_to_run.append(routing.agent)
    for a in routing.additional_agents:
        if a in _AGENT_MAP and a not in agents_to_run:
            agents_to_run.append(a)

    all_responses: list[AgentResponse] = []
    for agent_name in agents_to_run:
        node_fn = _AGENT_MAP[agent_name]
        try:
            result = node_fn(state)
            all_responses.extend(result.get("agent_responses", []))
        except Exception as e:
            all_responses.append(AgentResponse(
                agent_name=agent_name,
                domain="unknown",
                response=f"Agent encountered an error: {str(e)}",
                confidence=0.0,
            ))

    return {"agent_responses": all_responses}
