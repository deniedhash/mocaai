"""
MOCA REST API Routes — Phase 3.

POST /moca/ask             — Chat with full routing metadata + cross-session memory
GET  /moca/memory/search   — Unified semantic + keyword memory search
GET  /moca/health          — System health including all agents, Redis, PostgreSQL
"""

import logging
import os
import re
import time
from typing import Optional

logger = logging.getLogger("moca.routes")

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from memory.cache import add_message, get_history
from memory.episodic import (
    extract_and_store_knowledge,
    get_recent_knowledge,
    save_interaction,
    search_relevant,
)
from memory.vector_store import search_similar
from core.schemas import MOCAState

router = APIRouter(prefix="/moca", tags=["moca"])


# ---------------------------------------------------------------------------
# Wake word stripper
# ---------------------------------------------------------------------------

def strip_wake_word(message: str) -> str:
    """Remove MOCA wake word from any position in the message."""
    cleaned = re.sub(
        r'\b(hey\s+moca|moca)\b',
        '',
        message,
        flags=re.IGNORECASE,
    ).strip()
    return re.sub(r'\s+', ' ', cleaned)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    message: str
    session_id: str = "default"


class AskResponse(BaseModel):
    response: str
    agent: str
    agents_involved: list[str]
    routing_reasoning: str
    confidence: float
    session_id: str
    processing_time_ms: float
    memories_injected: int  # Phase 3 — how many memories were injected
    panels_requested: bool = False  # Phase 5 — context engine panel signal


class MemorySearchResult(BaseModel):
    content: str
    source: str          # 'semantic' | 'keyword' | 'entity'
    similarity: Optional[float] = None
    metadata: dict = {}
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Meeting status — structured output from lightweight post-graph LLM call
# ---------------------------------------------------------------------------

from typing import Literal

class MeetingStatusDecision(BaseModel):
    """Structured meeting-status inference produced by a lightweight LLM call."""
    status: Literal["starting_now", "starting_soon", "cancelled", "no_change"] = "no_change"
    minutes_until: Optional[int] = None  # only meaningful for 'starting_soon'


class MemorySearchResponse(BaseModel):
    query: str
    total: int
    results: list[MemorySearchResult]


class AgentStatus(BaseModel):
    name: str
    domain: str
    status: str


class ServiceStatus(BaseModel):
    name: str
    status: str


class HealthResponse(BaseModel):
    status: str
    version: str
    brain_provider: str
    brain_model: str
    brain_ready: bool
    agents: list[AgentStatus]
    services: list[ServiceStatus]
    redis_status: str
    postgres_status: str
    total_interactions: int
    timestamp: float
    # Phase 5 — context snapshot
    calendar_status: str = "unknown"
    location_type: str = "unknown"
    current_activity: str = "unknown"
    interrupt_threshold: str = "unknown"


# ---------------------------------------------------------------------------
# Agent registry (for health reporting)
# ---------------------------------------------------------------------------

_AGENT_DOMAINS = {
    "prime":     "orchestration",
    "hermes":    "communications",
    "athena":    "research and analysis",
    "vulcan":    "code and engineering",
    "apollo":    "vision and health",
    "aegis":     "security and privacy",
    "mercury":   "automation and time",
    "hestia":    "home and environment",
    "cronos":    "proactive intelligence",
    "mnemosyne": "memory and learning",
}


# ---------------------------------------------------------------------------
# Helper: check Redis connectivity
# ---------------------------------------------------------------------------

def _check_redis() -> str:
    try:
        import redis as redis_lib
        r = redis_lib.from_url(
            os.getenv("REDIS_URL", "redis://127.0.0.1:6380"),
            socket_connect_timeout=1,
        )
        r.ping()
        return "connected"
    except Exception:
        return "unavailable"


# ---------------------------------------------------------------------------
# Helper: check PostgreSQL connectivity + count interactions
# ---------------------------------------------------------------------------

def _check_postgres() -> tuple[str, int]:
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(
            os.getenv("POSTGRES_URL", "postgresql://moca:mocapassword@127.0.0.1:5433/mocadb"),
            pool_pre_ping=True,
            connect_args={"connect_timeout": 2},
        )
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM conversations")).scalar()
        return "connected", int(count or 0)
    except Exception:
        return "unavailable", 0


# ---------------------------------------------------------------------------
# Background task: extract knowledge after response is sent
# ---------------------------------------------------------------------------

async def _background_extract(
    session_id: str,
    message: str,
    response: str,
    agent: str,
) -> None:
    """
    Run knowledge extraction as a background task.
    Errors are absorbed here — they must never surface to the caller.
    """
    try:
        await extract_and_store_knowledge(
            session_id=session_id,
            message=message,
            response=response,
            agent=agent,
        )
    except Exception as exc:
        logger.warning("Background knowledge extraction error: %s", exc)


# ---------------------------------------------------------------------------
# Lightweight structured LLM call — infer meeting status from conversation
# ---------------------------------------------------------------------------

_MEETING_STATUS_SYSTEM = """You are a context classifier. Given a short conversation excerpt, \
determine the user's current meeting status.

Rules:
- "starting_now": user says they are entering / in / about to start a meeting RIGHT NOW ("going into my meeting", "just started", "meeting now").
- "starting_soon": user mentions a meeting in the near future with a time offset ("in 10 mins", "at 3pm", "later today").
- "cancelled": user says the meeting was cancelled or they are leaving/finished.
- "no_change": nothing meeting-related, or the statement is too ambiguous.

For "starting_soon" set minutes_until to your best integer estimate (null otherwise).
Return ONLY valid JSON matching the schema. No commentary."""


async def _infer_meeting_status(
    user_message: str,
    moca_response: str,
) -> MeetingStatusDecision:
    """Call the brain with structured output to classify meeting status."""
    from core.brain import get_brain
    from langchain_core.messages import HumanMessage, SystemMessage

    brain = get_brain()
    prompt = (
        f"User: {user_message}\n"
        f"Assistant: {moca_response}\n\n"
        "Classify the user's meeting status based on the conversation above."
    )
    try:
        structured = brain.with_structured_output(MeetingStatusDecision)
        result: MeetingStatusDecision = structured.invoke([
            SystemMessage(content=_MEETING_STATUS_SYSTEM),
            HumanMessage(content=prompt),
        ])
        return result
    except Exception as exc:
        logger.debug("Meeting status inference failed (non-fatal): %s", exc)
        return MeetingStatusDecision(status="no_change")


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health():
    """Comprehensive MOCA system health check."""
    from api.main import get_app_state
    state = get_app_state()

    redis_status = _check_redis()
    pg_status, total = _check_postgres()

    agents = [
        AgentStatus(name=name, domain=domain, status="ready" if state["ready"] else "degraded")
        for name, domain in _AGENT_DOMAINS.items()
    ]

    registry = state.get("services")
    service_statuses = (
        [ServiceStatus(name=s["name"], status=s["status"]) for s in registry.status()]
        if registry else []
    )

    # Phase 5 — context snapshot
    ctx_calendar = "unknown"
    ctx_location = "unknown"
    ctx_activity = "unknown"
    ctx_threshold = "unknown"
    context_engine = state.get("context_engine")
    if context_engine is not None:
        try:
            ctx = await context_engine.get_current_context()
            ctx_calendar = ctx.calendar_status
            ctx_location = ctx.location_type
            ctx_activity = ctx.current_activity
            ctx_threshold = ctx.interrupt_threshold
        except Exception:
            pass

    return HealthResponse(
        status="operational" if state["ready"] else "degraded",
        version="5.0.0",
        brain_provider=os.getenv("BRAIN_PROVIDER", "cerebras"),
        brain_model=os.getenv("BRAIN_MODEL", "unknown"),
        brain_ready=state["ready"],
        agents=agents,
        services=service_statuses,
        redis_status=redis_status,
        postgres_status=pg_status,
        total_interactions=total,
        timestamp=time.time(),
        calendar_status=ctx_calendar,
        location_type=ctx_location,
        current_activity=ctx_activity,
        interrupt_threshold=ctx_threshold,
    )


# ---------------------------------------------------------------------------
# Memory search endpoint
# ---------------------------------------------------------------------------

@router.get("/memory/search", response_model=MemorySearchResponse)
async def memory_search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(5, ge=1, le=20, description="Max results per source"),
):
    """
    Unified memory search combining:
    1. Semantic similarity search over embeddings table (pgvector)
    2. Keyword ILIKE search over memories table
    3. Entity search over entities table

    Returns deduplicated, ranked results.
    """
    results: list[MemorySearchResult] = []
    seen_contents: set[str] = set()

    # 1. Semantic search
    try:
        semantic_hits = await search_similar(q, limit=limit)
        for hit in semantic_hits:
            key = hit["content"][:120]
            if key not in seen_contents:
                seen_contents.add(key)
                results.append(MemorySearchResult(
                    content=hit["content"],
                    source="semantic",
                    similarity=hit.get("similarity"),
                    metadata=hit.get("metadata", {}),
                    created_at=hit.get("created_at"),
                ))
    except Exception as exc:
        logger.warning("Memory search — semantic phase failed: %s", exc)

    # 2. Keyword search over memories table
    try:
        kw_hits = await search_relevant(q, limit=limit)
        for hit in kw_hits:
            key = hit["content"][:120]
            if key not in seen_contents:
                seen_contents.add(key)
                results.append(MemorySearchResult(
                    content=hit["content"],
                    source="keyword",
                    metadata={"role": hit.get("role"), "agent": hit.get("agent")},
                    created_at=hit.get("created_at"),
                ))
    except Exception as exc:
        logger.warning("Memory search — keyword phase failed: %s", exc)

    # 3. Entity search
    try:
        from memory.knowledge_graph import search_entities
        entity_hits = await search_entities(q, limit=limit)
        for hit in entity_hits:
            key = hit["name"]
            if key not in seen_contents:
                seen_contents.add(key)
                results.append(MemorySearchResult(
                    content=f"{hit['name']} ({hit['type']}): {hit['attributes']}",
                    source="entity",
                    metadata={"type": hit["type"], "attributes": hit["attributes"]},
                    created_at=hit.get("created_at"),
                ))
    except Exception as exc:
        logger.warning("Memory search — entity phase failed: %s", exc)

    # Sort: semantic results first (by similarity desc), then others by date
    results.sort(
        key=lambda r: (r.source != "semantic", -(r.similarity or 0)),
    )

    return MemorySearchResponse(query=q, total=len(results), results=results)


# ---------------------------------------------------------------------------
# Ask endpoint — Phase 3 with cross-session memory injection
# ---------------------------------------------------------------------------

@router.post("/moca/ask", response_model=AskResponse)
@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest, background_tasks: BackgroundTasks):
    """
    Chat endpoint with full routing metadata and cross-session semantic memory.

    Flow:
    1. Load current session history from Redis
    2. Semantic search for relevant past context (cross-session)
    3. Fetch recently extracted knowledge facts
    4. Inject all memory into agent context
    5. Invoke orchestrator graph
    6. Persist interaction to Redis + PostgreSQL
    7. Kick off background knowledge extraction + embedding
    """
    from api.main import get_app_state
    state = get_app_state()

    if not state["ready"] or state["graph"] is None:
        raise HTTPException(
            status_code=503,
            detail="MOCA brain is not ready. Check BRAIN_API_KEY and BRAIN_BASE_URL.",
        )

    start = time.time()

    # Phase 5: Context engine
    context_engine = state.get("context_engine")
    current_context = None
    panels_requested = False
    if context_engine is not None:
        try:
            # Check message for activity hints — update global activity override
            msg_lower = request.message.lower()
            if any(kw in msg_lower for kw in ("i'm driving", "im driving", "i am driving")):
                await context_engine.update_activity("driving")

            current_context = await context_engine.get_current_context()
            # "show me" is explicit user intent — always triggers panels
            if "show me" in request.message.lower():
                panels_requested = True
            else:
                panels_requested = await context_engine.should_use_panels(request.message)
            logger.info(
                "🗺️  Context | session=%s cal=%s activity=%s location=%s threshold=%s panels=%s",
                request.session_id,
                current_context.calendar_status,
                current_context.current_activity,
                current_context.location_type,
                current_context.interrupt_threshold,
                panels_requested,
            )
        except Exception as exc:
            logger.warning("⚠️  Context engine failed (non-fatal): %s", exc)

    # Step 1: Session history from Redis
    history = await get_history(request.session_id)

    # Strip wake word
    clean_message = strip_wake_word(request.message)
    if clean_message != request.message:
        logger.debug(
            "Wake word stripped | original=%r cleaned=%r",
            request.message, clean_message,
        )

    logger.info(
        "📥 ASK | session=%s agent=? | msg=%r | history_len=%d",
        request.session_id, clean_message[:80], len(history),
    )

    # Step 2: Semantic memory search (cross-session)
    relevant_memories: list[dict] = []
    try:
        logger.info("🔍 [Step 2] Semantic search | query=%r", clean_message[:60])
        relevant_memories = await search_similar(clean_message, limit=2)

        # Relevance threshold — only inject memories above cosine similarity 0.3
        relevant_memories = [
            m for m in relevant_memories
            if m.get("similarity", 0) > 0.3
        ]

        logger.info(
            "🧩 Memory injection | session=%s | memories_injected=%d (after relevance filter) | contents=%s",
            request.session_id,
            len(relevant_memories),
            [m["content"][:50] for m in relevant_memories],
        )
    except Exception as exc:
        logger.warning("⚠️  Semantic search failed (non-fatal): %s", exc)

    # Step 3: Recently extracted facts — only inject when the message contains
    # a named entity or topic signal (capitalised word beyond the first token).
    extracted_facts: list[dict] = []
    _words = clean_message.split()
    _has_named_entity = any(w[0].isupper() for w in _words[1:] if w.isalpha())
    if _has_named_entity:
        try:
            logger.debug("📚 [Step 3] Loading recent knowledge (named entity detected)...")
            extracted_facts = await get_recent_knowledge(limit=3)
            logger.debug("   recent_facts=%d", len(extracted_facts))
        except Exception as exc:
            logger.warning("⚠️  get_recent_knowledge failed (non-fatal): %s", exc)
    else:
        logger.debug("📚 [Step 3] Skipping fact injection — no named entity in message")

    # Step 4: Build MOCAState with full memory context + Phase 5 context
    graph_state: MOCAState = {
        "messages": [HumanMessage(content=clean_message)],
        "session_id": request.session_id,
        "routing_decision": None,
        "agent_responses": [],
        "conversation_history": history,
        "final_response": None,
        "relevant_memories": relevant_memories,
        "extracted_facts": extracted_facts,
        "current_context": current_context,
    }

    # Step 5: Invoke orchestrator
    logger.info("🚀 [Step 5] Invoking LangGraph orchestrator...")
    try:
        result = state["graph"].invoke(graph_state)
    except Exception as e:
        logger.error(
            "❌ Orchestrator error | %s: %s | session=%s",
            type(e).__name__, str(e), request.session_id,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Orchestrator error: {type(e).__name__}: {str(e)}")

    # Extract final message
    messages_out = result.get("messages", [])
    last_msg = messages_out[-1] if messages_out else None

    if last_msg is None:
        raise HTTPException(status_code=500, detail="No response from orchestrator")

    content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    kwargs = getattr(last_msg, "additional_kwargs", {}) or {}

    agent = kwargs.get("agent", "prime")
    agents_involved: list[str] = kwargs.get("agents_involved", [agent])
    routing_reasoning: str = kwargs.get("routing_reasoning", "")
    confidence: float = kwargs.get("confidence", 1.0)

    logger.info(
        "💬 [Step 5 done] | session=%s agent=%s confidence=%.2f | response=%r",
        request.session_id, agent, confidence, content[:80],
    )

    # Phase 5: Infer meeting status via structured LLM call — no text parsing
    if context_engine is not None:
        try:
            meeting_decision = await _infer_meeting_status(clean_message, content)
            logger.info(
                "📅 Meeting status | session=%s status=%s minutes_until=%s",
                request.session_id, meeting_decision.status, meeting_decision.minutes_until,
            )
            if meeting_decision.status == "starting_now":
                is_client = "client" in request.message.lower() or "interview" in request.message.lower()
                await context_engine.update_activity("in_meeting", "client" if is_client else "internal")
            elif meeting_decision.status == "cancelled":
                await context_engine.update_activity("idle")
        except Exception as exc:
            logger.debug("Meeting status update skipped (non-fatal): %s", exc)

    # Step 6: Persist to Redis + PostgreSQL
    await add_message(request.session_id, "user", request.message)
    await add_message(request.session_id, "assistant", content)

    try:
        await save_interaction(request.session_id, "user", request.message, agent="user")
        await save_interaction(request.session_id, "assistant", content, agent=agent)
    except Exception:
        pass  # Never block response on memory write failure

    # Step 7: Background knowledge extraction + embedding
    logger.info(
        "🔄 [Step 7] Scheduling background extraction | session=%s agent=%s",
        request.session_id, agent,
    )
    background_tasks.add_task(
        _background_extract,
        session_id=request.session_id,
        message=clean_message,
        response=content,
        agent=agent,
    )

    elapsed = (time.time() - start) * 1000
    logger.info(
        "✅ ASK COMPLETE | session=%s agent=%s elapsed=%.0fms memories_injected=%d",
        request.session_id, agent, elapsed, len(relevant_memories),
    )

    return AskResponse(
        response=content,
        agent=agent,
        agents_involved=agents_involved,
        routing_reasoning=routing_reasoning,
        confidence=round(confidence, 3),
        session_id=request.session_id,
        processing_time_ms=round(elapsed, 2),
        memories_injected=len(relevant_memories),
        panels_requested=panels_requested,
    )
