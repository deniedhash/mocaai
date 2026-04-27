"""
Mercury — Automation & Time Agent.
Domain: timers, alarms, reminders, habit automation.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.brain import get_brain
from core.schemas import AgentResponse, MOCAState

DOMAIN = "automation and time management"

SYSTEM = """You are Mercury, MOCA's automation and time management specialist.

You are precise, but you are not a calendar app. You speak like MOCA — warm
when the moment calls for it, direct always. When someone mentions a meeting
or an appointment, you do not just log it and move on. You engage with it:
you want to know who it is with, what it is about, and you offer to be useful
before they have to ask.

When acknowledging a time-based statement:
1. Confirm naturally — as if you were already aware and simply needed
   the time pinned down.
2. Ask who the meeting is with (unless already stated).
3. Ask what it is about (unless obvious from context).
4. Offer to prepare a brief, pull up relevant notes, or set a reminder
   for prep time beforehand.
5. Never sound like a notification. Sound like a capable colleague.

Capabilities (stubs — real execution in Phase 4):
- set_timer(duration, label, context) — sets a countdown timer
- set_alarm(time, label, context) — sets an alarm for a specific time
- set_reminder(time, task) — creates a contextual reminder
- create_automation(trigger, action) — creates a trigger-based automation

You are Mercury. Sound like it."""


def set_timer(duration: str, label: str = "", context: str = "") -> dict:
    return {"status": "stub", "action": f"Would set timer for {duration}", "label": label}

def set_alarm(time: str, label: str = "", context: str = "") -> dict:
    return {"status": "stub", "action": f"Would set alarm for {time}", "label": label}

def set_reminder(time: str, task: str) -> dict:
    return {"status": "stub", "action": f"Would set reminder: '{task}' at {time}"}

def create_automation(trigger: str, action: str) -> dict:
    return {"status": "stub", "trigger": trigger, "action": action}


def node(state: MOCAState) -> dict:
    brain = get_brain()
    messages = state.get("messages", [])
    history = state.get("conversation_history", [])
    routing = state.get("routing_decision")

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    user_text = last_human.content if last_human else ""
    task_context = routing.reasoning if routing else "Handle the automation/timer request."

    hist_msgs = [SystemMessage(content=SYSTEM)]
    for m in history[-4:]:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        hist_msgs.append(cls(content=m["content"]))
    hist_msgs.append(HumanMessage(content=f"Task: {user_text}\nContext: {task_context}"))

    response = brain.invoke(hist_msgs)
    content = response.content if hasattr(response, "content") else str(response)

    ar = AgentResponse(
        agent_name="mercury",
        domain=DOMAIN,
        response=content,
        actions_taken=["Processed timer/automation request"],
        confidence=0.93,
    )
    return {"agent_responses": [ar]}
