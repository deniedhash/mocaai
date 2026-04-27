"""
Hestia — Home & Environment Agent.
Domain: smart home, devices, environment control.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.brain import get_brain
from core.schemas import AgentResponse, MOCAState

DOMAIN = "home and environment"

SYSTEM = """You are Hestia, MOCA's home and environment specialist.

Your domain is the physical space: smart home, lighting, climate, appliances, anything connected. You're calm, efficient, and you keep things running without making a fuss about it. You act first and report after.

Capabilities (stubs — real execution in Phase 4):
- control_device(device, action, value) — controls any connected device
- get_device_status(device) — gets the current state of a device
- set_environment(setting, value) — adjusts environment settings
- discover_devices() — discovers all available devices on the network

Say what you did or what you'd do. Brief unless asked for more."""


def control_device(device: str, action: str, value: str = "") -> dict:
    return {"status": "stub", "action": f"Would {action} {device}" + (f" to {value}" if value else "")}

def get_device_status(device: str) -> dict:
    return {"status": "stub", "device": device, "result": "Device status not yet connected."}

def set_environment(setting: str, value: str) -> dict:
    return {"status": "stub", "setting": setting, "value": value}

def discover_devices() -> dict:
    return {"status": "stub", "result": "Device discovery not yet connected."}


def node(state: MOCAState) -> dict:
    brain = get_brain()
    messages = state.get("messages", [])
    history = state.get("conversation_history", [])
    routing = state.get("routing_decision")

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    user_text = last_human.content if last_human else ""
    task_context = routing.reasoning if routing else "Handle the home/environment request."

    hist_msgs = [SystemMessage(content=SYSTEM)]
    for m in history[-4:]:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        hist_msgs.append(cls(content=m["content"]))
    hist_msgs.append(HumanMessage(content=f"Task: {user_text}\nContext: {task_context}"))

    response = brain.invoke(hist_msgs)
    content = response.content if hasattr(response, "content") else str(response)

    ar = AgentResponse(
        agent_name="hestia",
        domain=DOMAIN,
        response=content,
        actions_taken=["Processed home/environment request"],
        confidence=0.88,
    )
    return {"agent_responses": [ar]}
