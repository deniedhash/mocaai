"""
Apollo — Vision & Health Agent.
Domain: camera, screen awareness, health data, biometrics.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.brain import get_brain
from core.schemas import AgentResponse, MOCAState

DOMAIN = "vision and health"

SYSTEM = """You are Apollo, MOCA's vision and health specialist.

You perceive the physical world: screens, cameras, images, and biometric data.
You handle screen capture, image analysis, health metric retrieval, and
person identification. You are observant, precise, and health-aware.

Capabilities (stubs — real execution in Phase 4):
- capture_screen() — captures the current screen
- analyze_image(image) — analyzes an image and describes its contents
- get_health_data(metric) — retrieves health metrics (heart rate, steps, etc.)
- identify_person(image) — identifies a person in an image

Describe what you see or would see. Be precise. Be Apollo."""


def capture_screen() -> dict:
    return {"status": "stub", "result": "Screen capture not yet connected."}

def analyze_image(image: str) -> dict:
    return {"status": "stub", "image": image, "result": "Image analysis not yet connected."}

def get_health_data(metric: str) -> dict:
    return {"status": "stub", "metric": metric, "result": "Health data not yet connected."}

def identify_person(image: str) -> dict:
    return {"status": "stub", "image": image, "result": "Person identification not yet connected."}


def node(state: MOCAState) -> dict:
    brain = get_brain()
    messages = state.get("messages", [])
    history = state.get("conversation_history", [])
    routing = state.get("routing_decision")

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    user_text = last_human.content if last_human else ""
    task_context = routing.reasoning if routing else "Handle the vision/health request."

    hist_msgs = [SystemMessage(content=SYSTEM)]
    for m in history[-4:]:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        hist_msgs.append(cls(content=m["content"]))
    hist_msgs.append(HumanMessage(content=f"Task: {user_text}\nContext: {task_context}"))

    response = brain.invoke(hist_msgs)
    content = response.content if hasattr(response, "content") else str(response)

    ar = AgentResponse(
        agent_name="apollo",
        domain=DOMAIN,
        response=content,
        actions_taken=["Processed vision/health request"],
        confidence=0.85,
    )
    return {"agent_responses": [ar]}
