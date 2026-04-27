"""
MOCA Orchestrator — Phase 2 LangGraph supervisor graph.

Flow:
  START
    → prime_router_node      (LLM intent classification → RoutingDecision)
    → [single agent] OR coordinator_node
    → prime_synthesizer_node (MOCA-voiced final reply)
  END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from agents.prime import prime_router_node, prime_synthesizer_node
from agents.coordinator import coordinator_node
from agents.hermes import node as hermes_node
from agents.athena import node as athena_node
from agents.vulcan import node as vulcan_node
from agents.apollo import node as apollo_node
from agents.aegis import node as aegis_node
from agents.mercury import node as mercury_node
from agents.hestia import node as hestia_node
from agents.cronos import node as cronos_node
from agents.mnemosyne import node as mnemosyne_node
from core.schemas import MOCAState, VALID_AGENTS


# ---------------------------------------------------------------------------
# Routing function (reads RoutingDecision from state)
# ---------------------------------------------------------------------------

def _route_from_prime(state: MOCAState) -> str:
    routing = state.get("routing_decision")
    if not routing or routing.agent == "prime":
        return "prime_synthesizer"

    if routing.is_multi_domain and routing.additional_agents:
        return "coordinator"

    if routing.agent in VALID_AGENTS:
        return routing.agent

    return "prime_synthesizer"


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------

def build_graph():
    """
    Build and compile the Phase 2 MOCA LangGraph graph.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    graph = StateGraph(MOCAState)

    # Register all nodes
    graph.add_node("prime_router", prime_router_node)
    graph.add_node("prime_synthesizer", prime_synthesizer_node)
    graph.add_node("coordinator", coordinator_node)
    graph.add_node("hermes",    hermes_node)
    graph.add_node("athena",    athena_node)
    graph.add_node("vulcan",    vulcan_node)
    graph.add_node("apollo",    apollo_node)
    graph.add_node("aegis",     aegis_node)
    graph.add_node("mercury",   mercury_node)
    graph.add_node("hestia",    hestia_node)
    graph.add_node("cronos",    cronos_node)
    graph.add_node("mnemosyne", mnemosyne_node)

    # Entry point
    graph.set_entry_point("prime_router")

    # Conditional routing from prime_router to agents / coordinator / synthesizer
    graph.add_conditional_edges(
        "prime_router",
        _route_from_prime,
        {
            "hermes":           "hermes",
            "athena":           "athena",
            "vulcan":           "vulcan",
            "apollo":           "apollo",
            "aegis":            "aegis",
            "mercury":          "mercury",
            "hestia":           "hestia",
            "cronos":           "cronos",
            "mnemosyne":        "mnemosyne",
            "coordinator":      "coordinator",
            "prime_synthesizer":"prime_synthesizer",
        },
    )

    # All agents and coordinator feed into synthesizer
    for node_name in list(VALID_AGENTS) + ["coordinator"]:
        graph.add_edge(node_name, "prime_synthesizer")

    # Synthesizer ends the graph
    graph.add_edge("prime_synthesizer", END)

    return graph.compile()
