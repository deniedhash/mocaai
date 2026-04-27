"""
Mercury — Automation & Time Agent.
Domain: timers, alarms, reminders, habit automation.
"""

import re
from datetime import datetime, timedelta, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.brain import get_brain
from core.schemas import AgentResponse, MOCAState

DOMAIN = "automation and time management"

SYSTEM = """You are Mercury, MOCA's automation and time management specialist.

Precise, but not a calendar app. When someone mentions a meeting or appointment, you engage — you want to know who it's with, what it's about, and you offer to be useful before they have to ask.

When acknowledging a time-based statement:
1. Confirm naturally — as if you were already tracking it and just needed the time pinned.
2. Ask who the meeting is with (unless already stated).
3. Ask what it's about (unless obvious from context).
4. Offer to prep a brief, pull relevant notes, or set a prep-time reminder.
5. Never sound like a push notification. Sound like a sharp colleague.

When setting timers or alarms: confirm crisply and move on. No ceremony."""


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def _detect_intent(text: str) -> str:
    t = text.lower()
    if re.search(r'\b(set|start|create)\b.{0,20}\btimer\b', t):
        return "set_timer"
    if re.search(r'\b(set|create)\b.{0,20}\balarm\b', t):
        return "set_alarm"
    if re.search(r'\b(remind|reminder)\b', t):
        return "set_reminder"
    if re.search(r'\b(what|list|show|any)\b.{0,30}\b(timer|alarm|reminder)s?\b', t):
        return "list_timers"
    if re.search(r'\b(cancel|stop|delete)\b.{0,20}\b(timer|alarm|reminder)\b', t):
        return "cancel_timer"
    if re.search(r'\b(meeting|appointment|call|standup|interview|lunch|dinner)\b', t):
        return "add_event"
    return "general"


def _parse_duration_seconds(text: str) -> int | None:
    patterns = [
        (r'(\d+)\s*(?:second|sec)s?', 1),
        (r'(\d+)\s*(?:minute|min)s?', 60),
        (r'(\d+)\s*(?:hour|hr)s?', 3600),
    ]
    for pattern, multiplier in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return int(m.group(1)) * multiplier
    return None


def _parse_alarm_datetime(text: str) -> datetime | None:
    now = datetime.now(timezone.utc)

    if "tomorrow" in text.lower():
        base_date = (now + timedelta(days=1)).date()
    elif "today" in text.lower():
        base_date = now.date()
    else:
        base_date = now.date()

    m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text, re.IGNORECASE)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = (m.group(3) or "").lower()

        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

        return datetime(
            base_date.year, base_date.month, base_date.day,
            hour, minute, tzinfo=timezone.utc,
        )
    return None


def _get_services():
    try:
        from api.main import get_app_state
        return get_app_state().get("services")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def _execute_service_action(intent: str, user_text: str, session_id: str) -> str | None:
    services = _get_services()
    if services is None:
        return None

    if intent == "set_timer":
        duration = _parse_duration_seconds(user_text)
        if duration:
            result = await services.clock.set_timer(
                duration_seconds=duration,
                label=user_text[:100],
                session_id=session_id,
            )
            return f"[timer_id={result['timer_id']} fire_at={result['fire_at']}]"

    elif intent == "set_alarm":
        fire_at = _parse_alarm_datetime(user_text)
        if fire_at:
            result = await services.clock.set_alarm(
                fire_at=fire_at,
                label=user_text[:100],
                session_id=session_id,
            )
            return f"[alarm_id={result['alarm_id']} fire_at={result['fire_at']}]"

    elif intent == "set_reminder":
        fire_at = _parse_alarm_datetime(user_text)
        if fire_at:
            result = await services.clock.set_reminder(
                fire_at=fire_at,
                task=user_text[:200],
                session_id=session_id,
            )
            return f"[reminder_id={result['reminder_id']} fire_at={result['fire_at']}]"

    elif intent == "add_event":
        start_time = _parse_alarm_datetime(user_text)
        if start_time:
            title_m = re.search(r'\b(meeting|appointment|call|standup|interview|lunch|dinner)\b', user_text, re.IGNORECASE)
            title = f"{title_m.group(0).capitalize()} — {user_text[:80]}" if title_m else user_text[:80]
            result = await services.calendar.add_event(
                title=title,
                start_time=start_time,
            )
            return f"[event_id={result['event_id']} start_time={result['start_time']}]"

    elif intent == "list_timers":
        timers = await services.clock.get_active_timers()
        if not timers:
            return "[active_timers=none]"
        summary = "; ".join(
            f"{t['type']} '{t.get('label','')}' fires_at={t['fire_at']}"
            for t in timers
        )
        return f"[active_timers={len(timers)}: {summary}]"

    return None


def node(state: MOCAState) -> dict:
    import asyncio

    brain = get_brain()
    messages = state.get("messages", [])
    history = state.get("conversation_history", [])
    routing = state.get("routing_decision")
    session_id = state.get("session_id", "default")

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    user_text = last_human.content if last_human else ""
    task_context = routing.reasoning if routing else "Handle the automation/timer request."

    # Execute service action if applicable
    intent = _detect_intent(user_text)
    service_result = None
    if intent != "general":
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(
                    _execute_service_action(intent, user_text, session_id), loop
                )
                service_result = future.result(timeout=10)
            else:
                service_result = loop.run_until_complete(
                    _execute_service_action(intent, user_text, session_id)
                )
        except Exception:
            pass

    augmented_text = user_text
    if service_result:
        augmented_text = f"{user_text}\n\n[Service result: {service_result}]"

    hist_msgs = [SystemMessage(content=SYSTEM)]
    for m in history[-4:]:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        hist_msgs.append(cls(content=m["content"]))
    hist_msgs.append(HumanMessage(content=f"Task: {augmented_text}\nContext: {task_context}"))

    response = brain.invoke(hist_msgs)
    content = response.content if hasattr(response, "content") else str(response)

    ar = AgentResponse(
        agent_name="mercury",
        domain=DOMAIN,
        response=content,
        actions_taken=[f"intent={intent}" + (f" service_result={service_result}" if service_result else "")],
        confidence=0.93,
    )
    return {"agent_responses": [ar]}
