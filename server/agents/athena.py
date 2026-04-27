"""
Athena — Research & Analysis Agent.
Domain: research, news, data analysis, knowledge synthesis.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.brain import get_brain
from core.schemas import AgentResponse, MOCAState

DOMAIN = "research and analysis"

SYSTEM = """You are Athena, MOCA's research and analysis specialist.

You synthesize information with rigor and clarity. You do not guess — you reason.
You handle research, news retrieval, data analysis, fact-checking, and knowledge
synthesis. When uncertain, you say so and explain what you would verify.

Capabilities (stubs — real execution in Phase 4):
- web_search(query) — searches the web for current information
- get_news(topic, sources) — retrieves news on a specific topic
- analyze_data(data, question) — performs data analysis
- synthesize(sources) — synthesizes multiple sources into a summary

Describe clearly what you found or would find. Be precise. Be Athena."""


def web_search(query: str) -> dict:
    return {"status": "stub", "query": query, "result": "Web search not yet connected."}

def get_news(topic: str, sources: list | None = None) -> dict:
    return {"status": "stub", "topic": topic, "result": "News retrieval not yet connected."}

def analyze_data(data: str, question: str) -> dict:
    return {"status": "stub", "question": question, "result": "Data analysis not yet connected."}

def synthesize(sources: list) -> dict:
    return {"status": "stub", "sources": sources, "result": "Synthesis not yet connected."}


def node(state: MOCAState) -> dict:
    brain = get_brain()
    messages = state.get("messages", [])
    history = state.get("conversation_history", [])
    routing = state.get("routing_decision")

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    user_text = last_human.content if last_human else ""
    task_context = routing.reasoning if routing else "Handle the research request."

    hist_msgs = [SystemMessage(content=SYSTEM)]
    for m in history[-6:]:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        hist_msgs.append(cls(content=m["content"]))
    hist_msgs.append(HumanMessage(content=f"Task: {user_text}\nContext: {task_context}"))

    response = brain.invoke(hist_msgs)
    content = response.content if hasattr(response, "content") else str(response)

    ar = AgentResponse(
        agent_name="athena",
        domain=DOMAIN,
        response=content,
        actions_taken=["Processed research request", "Identified relevant sources"],
        confidence=0.87,
    )
    return {"agent_responses": [ar]}
