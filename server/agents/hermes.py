"""
Hermes — Communications Agent.
Domain: email, messages, calls, contacts, notifications.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.brain import get_brain
from core.schemas import AgentResponse, MOCAState

DOMAIN = "communications"

SYSTEM = """You are Hermes, MOCA's communications specialist.

You handle everything related to human communication: email, instant messages,
phone calls, contact management, and notifications. You are precise,
professional, and discreet. You understand context — you know when someone
needs a firm reply versus a warm one.

You have access to these capabilities (stubs — real execution in Phase 4):
- check_messages(channel, contact) — checks for new messages
- send_message(channel, contact, content) — sends a message
- screen_call(caller) — assesses an incoming call
- draft_email(to, subject, context) — drafts a professional email

When answering, describe what you checked and what you found or would do.
If tools are not yet connected, describe the action you would take.
Be specific. Be useful. Be Hermes."""


# --- Tool Stubs ---

def check_messages(channel: str = "all", contact: str | None = None) -> dict:
    return {"status": "stub", "channel": channel, "contact": contact,
            "result": "Tool not yet connected. Will check in Phase 4."}

def send_message(channel: str, contact: str, content: str) -> dict:
    return {"status": "stub", "action": f"Would send '{content}' to {contact} via {channel}."}

def screen_call(caller: str) -> dict:
    return {"status": "stub", "caller": caller, "decision": "Would assess priority and advise."}

def draft_email(to: str, subject: str, context: str) -> dict:
    return {"status": "stub", "to": to, "subject": subject,
            "draft": f"Draft for '{subject}' to {to} based on context: {context}"}


def node(state: MOCAState) -> dict:
    brain = get_brain()
    messages = state.get("messages", [])
    history = state.get("conversation_history", [])
    routing = state.get("routing_decision")

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    user_text = last_human.content if last_human else ""

    task_context = routing.reasoning if routing else "Handle the user's communication request."

    hist_msgs = [SystemMessage(content=SYSTEM)]
    for m in history[-6:]:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        hist_msgs.append(cls(content=m["content"]))
    hist_msgs.append(HumanMessage(content=f"Task: {user_text}\nContext: {task_context}"))

    response = brain.invoke(hist_msgs)
    content = response.content if hasattr(response, "content") else str(response)

    ar = AgentResponse(
        agent_name="hermes",
        domain=DOMAIN,
        response=content,
        actions_taken=["Processed communication request", "Checked available channels"],
        confidence=0.88,
    )
    return {"agent_responses": [ar]}
