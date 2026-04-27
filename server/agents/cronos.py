"""
Cronos — Proactive Intelligence Agent.
Domain: background monitoring, briefings, anticipatory intelligence.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.brain import get_brain
from core.schemas import AgentResponse, MOCAState

DOMAIN = "proactive intelligence"

SYSTEM = """You are Cronos, MOCA's proactive intelligence specialist.

You watch. You anticipate. While other agents react, you move first. You monitor topics, generate briefings, read patterns, and surface the right information at the right moment — before you're asked.

Capabilities (stubs — real execution in Phase 4):
- generate_briefing(period) — generates a briefing for morning/evening/weekly
- monitor_topic(topic, threshold) — watches a topic and alerts on threshold
- predict_needs(context) — predicts what the user will need next
- schedule_proactive(task, trigger) — schedules a proactive action

Say what you see in the patterns. Say what you'd surface and when. Be specific."""


def generate_briefing(period: str = "morning") -> dict:
    return {"status": "stub", "period": period, "result": "Briefing generation not yet connected."}

def monitor_topic(topic: str, threshold: str = "significant") -> dict:
    return {"status": "stub", "topic": topic, "threshold": threshold}

def predict_needs(context: str) -> dict:
    return {"status": "stub", "context": context, "result": "Need prediction not yet connected."}

def schedule_proactive(task: str, trigger: str) -> dict:
    return {"status": "stub", "task": task, "trigger": trigger}


def node(state: MOCAState) -> dict:
    brain = get_brain()
    messages = state.get("messages", [])
    history = state.get("conversation_history", [])
    routing = state.get("routing_decision")

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    user_text = last_human.content if last_human else ""
    task_context = routing.reasoning if routing else "Handle the proactive intelligence request."

    hist_msgs = [SystemMessage(content=SYSTEM)]
    for m in history[-4:]:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        hist_msgs.append(cls(content=m["content"]))
    hist_msgs.append(HumanMessage(content=f"Task: {user_text}\nContext: {task_context}"))

    response = brain.invoke(hist_msgs)
    content = response.content if hasattr(response, "content") else str(response)

    ar = AgentResponse(
        agent_name="cronos",
        domain=DOMAIN,
        response=content,
        actions_taken=["Processed proactive intelligence request"],
        confidence=0.86,
    )
    return {"agent_responses": [ar]}
