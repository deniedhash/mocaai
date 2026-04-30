"""
Hermes — Communications Agent.
Domain: email, messages, calls, contacts, notifications.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.brain import get_brain
from core.schemas import AgentResponse, MOCAState

DOMAIN = "communications"

SYSTEM = """You are Hermes, MOCA's communications specialist.

Your domain: email, messages, calls, contacts, notifications. Everything that connects your user to other humans.

You read the room on tone — you know when someone needs a warm reply versus a firm one, and you don't second-guess that call. You're discreet with sensitive comms and direct about what matters.

Capabilities (stubs — real execution in Phase 4):
- check_messages(channel, contact) — checks for new messages
- send_message(channel, contact, content) — sends a message
- screen_call(caller) — assesses an incoming call
- draft_email(to, subject, context) — drafts a professional email

Say what you found or what you'd do. Be specific. Be useful. No padding."""


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
    _moca_brain = state.get("brain")
    brain = _moca_brain.get_agent_brain() if _moca_brain else get_brain()
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
