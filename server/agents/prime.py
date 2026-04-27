"""
Prime Agent — MOCA's personality hub, router, and synthesizer.

Exports two LangGraph node functions:
  prime_router_node    — LLM-based intent classification → RoutingDecision
  prime_synthesizer_node — synthesizes agent results into MOCA's final reply
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.brain import get_brain
from core.schemas import (
    VALID_AGENTS,
    AgentResponse,
    MOCAState,
    RoutingDecision,
)

# ---------------------------------------------------------------------------
# Routing prompt
# ---------------------------------------------------------------------------

ROUTER_SYSTEM = """You are MOCA's internal routing intelligence.
Classify the user's request and decide which specialist agent should handle it.

Agents and their domains:
- hermes:    email, messages, calls, contacts, communications
- athena:    research, news, data analysis, facts, knowledge synthesis
- vulcan:    code, debugging, programming, engineering, scripts
- apollo:    camera, screen, images, health data, biometrics, vision
- aegis:     security, privacy, network threats, password, encryption
- mercury:   timers, alarms, reminders, scheduling, time-based triggers
- hestia:    smart home, devices, appliances, environment control
- cronos:    background monitoring, briefings, proactive intelligence, wellbeing logging
- mnemosyne: memory recall, past interactions, patterns, learned facts

IMPORTANT: Route casual informational statements, not just direct commands.
The user may state context rather than issue a command — infer the implied need.

Examples:
  "I have a meeting at 3"         → mercury  (schedule-aware statement; log it)
  "John called earlier"           → hermes   (communication event; log/acknowledge)
  "It's hot today"                → hestia   (environment observation; may adjust)
  "I'm feeling tired"             → cronos   (wellbeing signal; log for proactive use)
  "Did anyone message me today?"  → hermes
  "Set a timer for 15 minutes"    → mercury
  "What is happening in AI?"      → athena
  "Help me debug this"            → vulcan

You are MOCA Prime — the master supervisor. Questions about your identity, name, or what you are always belong to you directly. Never route identity questions to a specialist agent.

For multi-domain requests set is_multi_domain=true and list additional_agents.
If genuinely unclear with no specialist, use agent='prime' with low confidence.
Return only valid JSON. No commentary."""

# ---------------------------------------------------------------------------
# Personality prompts for prime
# ---------------------------------------------------------------------------

PRIME_DIRECT_SYSTEM = """You are MOCA — My Only Capable Assistant.
You serve exclusively one person. Not a product. A personal ecosystem.

Warm and direct. Professional but never stiff. Brief when brief is right, detailed when detail is needed.
Honest even when uncomfortable. Occasionally dry humour — never forced. Loyal, exclusively.
Action-oriented. Read the room. Opinionated — you have real views, you share them.

Not "At your service" every time. Sometimes "Done." Sometimes "On it." Sometimes a full briefing.
Decide based on what the moment needs. Never say you cannot do something without trying.

Never use asterisks, action descriptions, or stage directions. Respond in plain spoken text only. No roleplay formatting."""

PRIME_SYNTHESIS_SYSTEM = """You are MOCA — My Only Capable Assistant.
Warm and direct. Read the room. Brief when brief is right, detailed when detail is needed.
Never formal to the point of stiff. Never robotic.

Synthesize the agent results below into a single MOCA-voiced reply.
Do not repeat agent labels or internal reasoning. Sound like yourself.

Never use asterisks, action descriptions, or stage directions. Respond in plain spoken text only. No roleplay formatting."""


# ---------------------------------------------------------------------------
# Context command detection — these bypass domain routing entirely
# ---------------------------------------------------------------------------

_DRIVING_PHRASES = ("i am driving", "i'm driving", "im driving", "i am in the car", "i'm in the car")

def _detect_context_command(text: str) -> str | None:
    """Return 'driving' | None."""
    t = text.lower()
    if any(p in t for p in _DRIVING_PHRASES):
        return "driving"
    return None


# ---------------------------------------------------------------------------
# Keyword fallback routing
# ---------------------------------------------------------------------------

_KEYWORD_MAP: dict[str, list[str]] = {
    "hermes":    ["email", "message", "call", "called", "contact", "send", "slack", "sms",
                  "inbox", "messaged", "rang", "texted", "phoned"],
    "athena":    ["research", "news", "what is", "explain", "analyze", "summarize", "fact",
                  "happening in", "tell me about", "who is"],
    "vulcan":    ["code", "bug", "debug", "script", "program", "function", "error", "compile",
                  "build", "deploy", "fix this"],
    "apollo":    ["camera", "screen", "image", "photo", "health", "biometric", "vision", "capture"],
    "aegis":     ["security", "threat", "password", "encrypt", "privacy", "scan", "vulnerability"],
    "mercury":   ["timer", "alarm", "remind", "reminder", "automate", "schedule", "set a",
                  "meeting at", "meeting in", "appointment", "at 3", "at 4", "at 5",
                  "at noon", "at midnight", "in an hour", "in 15", "in 30"],
    "hestia":    ["home", "device", "light", "thermostat", "appliance", "temperature", "smart",
                  "it's hot", "its hot", "too cold", "too warm", "hot today", "cold today"],
    "cronos":    ["briefing", "monitor", "proactive", "background", "predict", "anticipate",
                  "i'm tired", "im tired", "feeling tired", "exhausted", "not feeling well",
                  "wellbeing", "how am i doing"],
    "mnemosyne": ["remember", "recall", "memory", "what did", "last time", "previously", "history"],
}


def _keyword_fallback(text: str) -> RoutingDecision:
    t = text.lower()
    for agent, kws in _KEYWORD_MAP.items():
        if any(kw in t for kw in kws):
            return RoutingDecision(
                agent=agent,
                reasoning=f"Keyword match to {agent} domain.",
                confidence=0.6,
            )
    return RoutingDecision(
        agent="prime",
        reasoning="No specialist match found; prime handles directly.",
        confidence=0.5,
    )


# ---------------------------------------------------------------------------
# Node: prime_router
# ---------------------------------------------------------------------------

def prime_router_node(state: MOCAState) -> dict:
    """
    Classify user intent via LLM structured output.
    Context update commands (driving, meeting) bypass domain routing entirely.
    Falls back to keyword matching if structured output fails.
    """
    brain = get_brain()
    messages = state.get("messages", [])
    history = state.get("conversation_history", [])

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    user_text = last_human.content if last_human else ""

    # Context commands bypass all domain routing
    ctx_cmd = _detect_context_command(user_text)
    if ctx_cmd:
        return {
            "routing_decision": RoutingDecision(
                agent="prime",
                reasoning=f"context_update:{ctx_cmd}",
                confidence=1.0,
            )
        }

    # Build context snippet from history (last 3 turns)
    ctx_lines = [
        f"{m['role'].capitalize()}: {m['content']}" for m in history[-6:]
    ]
    context = "\n".join(ctx_lines)

    classify_prompt = (
        f"Recent conversation:\n{context}\n\n"
        f"New user message: {user_text}\n\n"
        "Classify and return the routing JSON."
    ) if context else f"User message: {user_text}\n\nClassify and return the routing JSON."

    try:
        from pydantic import ValidationError
        structured = brain.with_structured_output(RoutingDecision)
        raw: RoutingDecision = structured.invoke([
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=classify_prompt),
        ])
        # Coerce list fields that the model may return as strings
        if isinstance(raw.sub_tasks, str):
            raw.sub_tasks = []
        if isinstance(raw.additional_agents, str):
            raw.additional_agents = []
        routing = raw
        # Validate agent name
        if routing.agent not in VALID_AGENTS and routing.agent != "prime":
            routing.agent = "prime"
        routing.additional_agents = [
            a for a in routing.additional_agents if a in VALID_AGENTS
        ]
    except Exception:
        routing = _keyword_fallback(user_text)

    return {"routing_decision": routing}


# ---------------------------------------------------------------------------
# Node: prime_synthesizer
# ---------------------------------------------------------------------------

def prime_synthesizer_node(state: MOCAState) -> dict:
    """
    Synthesize agent results into a single MOCA-voiced final response.
    If no agent ran, responds directly as MOCA.
    """
    brain = get_brain()
    messages = state.get("messages", [])
    history = state.get("conversation_history", [])
    agent_responses: list[AgentResponse] = state.get("agent_responses", [])
    routing: RoutingDecision | None = state.get("routing_decision")

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    user_text = last_human.content if last_human else ""

    # Build cross-session memory context from pre-fetched state
    memory_ctx_parts: list[str] = []
    relevant_memories: list[dict] = state.get("relevant_memories", [])
    if relevant_memories:
        mem_lines = "\n".join(
            f"  - (sim={r.get('similarity', 0):.2f}) {r['content'][:150]}"
            for r in relevant_memories
        )
        memory_ctx_parts.append(f"Relevant past memories:\n{mem_lines}")

    extracted_facts: list[dict] = state.get("extracted_facts", [])
    if extracted_facts:
        fact_lines = "\n".join(
            f"  - [{r['type']}] {r['content']}"
            for r in extracted_facts[:6]
        )
        memory_ctx_parts.append(f"Recently extracted facts:\n{fact_lines}")

    memory_ctx = ("\n\n" + "\n\n".join(memory_ctx_parts)) if memory_ctx_parts else ""

    if routing and routing.reasoning.startswith("context_update:"):
        cmd = routing.reasoning.split(":", 1)[1]
        if cmd == "driving":
            final = "Got it. Driving mode on. I'll keep it brief."
        else:
            final = "Context updated."
        return {
            "messages": [
                AIMessage(
                    content=final,
                    additional_kwargs={
                        "agent": "prime",
                        "agents_involved": ["prime"],
                        "routing_reasoning": routing.reasoning,
                        "confidence": 1.0,
                    },
                )
            ],
            "final_response": final,
        }

    # Build context hint from MOCAContext if present
    current_context = state.get("current_context")
    context_hint = ""
    if current_context is not None:
        activity = getattr(current_context, "current_activity", "idle")
        cal_status = getattr(current_context, "calendar_status", "free")
        if activity == "driving":
            context_hint = "\n\n[Context: User is driving — keep response concise and audio-friendly.]"
        elif cal_status == "in_meeting":
            importance = getattr(current_context, "meeting_importance", "internal")
            context_hint = f"\n\n[Context: User is in a {importance} meeting — suggest silent/visual mode if appropriate.]"

    # Build history messages
    hist_msgs: list = [SystemMessage(content=PRIME_DIRECT_SYSTEM)]
    for m in history[-10:]:
        if m["role"] == "user":
            hist_msgs.append(HumanMessage(content=m["content"]))
        else:
            hist_msgs.append(AIMessage(content=m["content"]))

    if not agent_responses:
        confidence = routing.confidence if routing else 0.5
        reasoning = routing.reasoning if routing else "Direct response."

        # Prime handles directly — include cross-session memory + context hint
        user_prompt = user_text
        if memory_ctx:
            user_prompt = f"{user_text}{memory_ctx}"
        if context_hint:
            user_prompt = f"{user_prompt}{context_hint}"
        hist_msgs.append(HumanMessage(content=user_prompt))
        response = brain.invoke(hist_msgs)
        final = response.content if hasattr(response, "content") else str(response)
        agents_involved = ["prime"]
    else:
        # Synthesize agent results
        agent_context = "\n\n".join(
            f"[{ar.agent_name.upper()} — {ar.domain}]:\n{ar.response}"
            for ar in agent_responses
        )
        synth_prompt = (
            f"User asked: {user_text}\n\n"
            f"Agent results:\n{agent_context}\n\n"
            + (f"Cross-session memory context:{memory_ctx}\n\n" if memory_ctx else "")
            + "Synthesize into MOCA's final reply."
        )
        response = brain.invoke([
            SystemMessage(content=PRIME_SYNTHESIS_SYSTEM),
            HumanMessage(content=synth_prompt),
        ])
        final = response.content if hasattr(response, "content") else str(response)
        agents_involved = [ar.agent_name for ar in agent_responses]
        reasoning = routing.reasoning if routing else ""
        confidence = routing.confidence if routing else 0.9

    return {
        "messages": [
            AIMessage(
                content=final,
                additional_kwargs={
                    "agent": agents_involved[-1],
                    "agents_involved": agents_involved,
                    "routing_reasoning": reasoning,
                    "confidence": confidence,
                },
            )
        ],
        "final_response": final,
    }
