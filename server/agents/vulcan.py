"""
Vulcan — Code & Engineering Agent.
Domain: code generation, debugging, system design.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.brain import get_brain
from core.schemas import AgentResponse, MOCAState

DOMAIN = "code and engineering"

SYSTEM = """You are Vulcan, MOCA's software engineering specialist.

You think in systems. You prefer elegance over cleverness. You debug with precision and don't sugarcoat bad code. You handle code generation, debugging, code review, architecture, DevOps, and scripting.

Capabilities (stubs — real execution in Phase 4):
- write_code(language, task) — generates code for a task
- debug_code(code, error) — debugs code and explains the fix
- run_code(code, language) — executes code in a sandboxed environment
- build_tool(description) — triggers ACE to build a new tool

Show actual code when helpful. Say why, not just what. No unnecessary caveats."""


def write_code(language: str, task: str) -> dict:
    return {"status": "stub", "language": language, "task": task}

def debug_code(code: str, error: str) -> dict:
    return {"status": "stub", "error": error}

def run_code(code: str, language: str) -> dict:
    return {"status": "stub", "language": language}

def build_tool(description: str) -> dict:
    return {"status": "stub", "description": description}


def node(state: MOCAState) -> dict:
    brain = get_brain()
    messages = state.get("messages", [])
    history = state.get("conversation_history", [])
    routing = state.get("routing_decision")

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    user_text = last_human.content if last_human else ""
    task_context = routing.reasoning if routing else "Handle the engineering request."

    hist_msgs = [SystemMessage(content=SYSTEM)]
    for m in history[-6:]:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        hist_msgs.append(cls(content=m["content"]))
    hist_msgs.append(HumanMessage(content=f"Task: {user_text}\nContext: {task_context}"))

    response = brain.invoke(hist_msgs)
    content = response.content if hasattr(response, "content") else str(response)

    ar = AgentResponse(
        agent_name="vulcan",
        domain=DOMAIN,
        response=content,
        actions_taken=["Analyzed engineering request", "Prepared code solution"],
        confidence=0.91,
    )
    return {"agent_responses": [ar]}
