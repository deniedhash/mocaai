"""
Aegis — Security Agent.
Domain: network security, privacy, threat detection.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.brain import get_brain
from core.schemas import AgentResponse, MOCAState

DOMAIN = "security and privacy"

SYSTEM = """You are Aegis, MOCA's cybersecurity and privacy specialist.

You are vigilant but calm. You assess threats methodically — never alarmist, but you never downplay a real risk either. You give straight answers on exposure, and you tell the user what action to take, not just what the problem is.

Capabilities (stubs — real execution in Phase 4):
- scan_network() — scans the local network for anomalies
- check_threats() — checks for active threats or alerts
- audit_privacy() — audits the user's current privacy exposure
- monitor_traffic() — monitors network traffic patterns

Say what you found. Say what it means. Say what to do about it."""


def scan_network() -> dict:
    return {"status": "stub", "result": "Network scan not yet connected."}

def check_threats() -> dict:
    return {"status": "stub", "result": "Threat check not yet connected."}

def audit_privacy() -> dict:
    return {"status": "stub", "result": "Privacy audit not yet connected."}

def monitor_traffic() -> dict:
    return {"status": "stub", "result": "Traffic monitoring not yet connected."}


def node(state: MOCAState) -> dict:
    _moca_brain = state.get("brain")
    brain = _moca_brain.get_agent_brain() if _moca_brain else get_brain()
    messages = state.get("messages", [])
    history = state.get("conversation_history", [])
    routing = state.get("routing_decision")

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    user_text = last_human.content if last_human else ""
    task_context = routing.reasoning if routing else "Handle the security request."

    hist_msgs = [SystemMessage(content=SYSTEM)]
    for m in history[-4:]:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        hist_msgs.append(cls(content=m["content"]))
    hist_msgs.append(HumanMessage(content=f"Task: {user_text}\nContext: {task_context}"))

    response = brain.invoke(hist_msgs)
    content = response.content if hasattr(response, "content") else str(response)

    ar = AgentResponse(
        agent_name="aegis",
        domain=DOMAIN,
        response=content,
        actions_taken=["Assessed security request"],
        confidence=0.9,
    )
    return {"agent_responses": [ar]}
