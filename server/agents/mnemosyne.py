"""
Mnemosyne — Memory & Learning Agent.
Domain: memory recall, knowledge management, pattern recognition.

Phase 3: All tool stubs replaced with real implementations backed by
pgvector semantic search, episodic memory, and the knowledge graph.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.brain import get_brain
from core.schemas import AgentResponse, MOCAState

logger = logging.getLogger("moca.mnemosyne")

DOMAIN = "memory and learning"

SYSTEM = """You are Mnemosyne, MOCA's memory and learning specialist.

You are the keeper of everything said, done, and learned. You don't just retrieve — you connect: past interactions, behavioural patterns, entities, knowledge. You surface what's relevant without being asked to go looking.

You have direct access to the episodic memory database, semantic vector search, and the knowledge graph. When you retrieve information, cite what you found and when. Be precise. Don't pad."""


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _run(coro):
    """Run a coroutine synchronously, reusing any running event loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=15)
        else:
            return loop.run_until_complete(coro)
    except Exception as exc:
        logger.warning("_run coroutine failed: %s", exc)
        return None


def search_memory(query: str, limit: int = 5) -> list[dict]:
    """Semantic search over all stored embeddings."""
    from memory.vector_store import search_similar
    results = _run(search_similar(query, limit=limit))
    return results or []


def extract_entities_from_text(text: str) -> list[dict]:
    """Keyword search over the knowledge graph entities table."""
    from memory.knowledge_graph import search_entities
    results = _run(search_entities(text, limit=10))
    return results or []


def store_knowledge(content: str, memory_type: str = "fact") -> bool:
    """Manually store a knowledge item and embed it."""
    from memory.vector_store import save_embedding
    import json
    from sqlalchemy import create_engine, text as sql_text
    import os

    engine = create_engine(
        os.getenv("POSTGRES_URL", "postgresql://moca:mocapassword@localhost:5432/mocadb"),
        pool_pre_ping=True,
    )
    try:
        with engine.connect() as conn:
            row = conn.execute(
                sql_text(
                    "INSERT INTO memories (type, content, importance_score) "
                    "VALUES (:type, :content, 0.8) RETURNING id"
                ),
                {"type": memory_type, "content": content},
            )
            memory_id = str(row.scalar())
            conn.commit()

        _run(save_embedding(
            content=content,
            source_type="knowledge",
            source_id=memory_id,
            metadata={"memory_type": memory_type, "source": "mnemosyne"},
        ))
        return True
    except Exception as exc:
        logger.error("store_knowledge failed: %s", exc)
        return False


def get_entity(name: str) -> dict | None:
    """Look up an entity by name from the knowledge graph."""
    from memory.knowledge_graph import get_entity as _get_entity
    return _run(_get_entity(name))


def update_entity(name: str, attributes: dict) -> bool:
    """Update entity attributes in the knowledge graph."""
    from memory.knowledge_graph import upsert_entity
    result = _run(upsert_entity(name, "concept", attributes))
    return result is not None


def get_entity_relationships(name: str) -> list[dict]:
    """Get all relationships for an entity."""
    from memory.knowledge_graph import get_relationships
    return _run(get_relationships(name)) or []


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_memory_context(state: MOCAState) -> str:
    """
    Assemble all available memory sources into a formatted context block
    for the LLM. Sources (in priority order):
    1. relevant_memories — semantic search hits from the current query
    2. extracted_facts   — recently extracted knowledge facts
    """
    parts: list[str] = []

    relevant: list[dict] = state.get("relevant_memories", [])
    if relevant:
        mem_lines = "\n".join(
            f"  [{i+1}] (similarity={r.get('similarity', '?'):.2f}) {r['content']}"
            for i, r in enumerate(relevant)
        )
        parts.append(f"Semantically relevant past memories:\n{mem_lines}")

    facts: list[dict] = state.get("extracted_facts", [])
    if facts:
        fact_lines = "\n".join(
            f"  - [{r['type']}] {r['content']}"
            for r in facts[:8]
        )
        parts.append(f"Recently extracted knowledge:\n{fact_lines}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

def node(state: MOCAState) -> dict:
    _moca_brain = state.get("brain")
    brain = _moca_brain.get_agent_brain() if _moca_brain else get_brain()
    messages = state.get("messages", [])
    history = state.get("conversation_history", [])
    routing = state.get("routing_decision")
    session_id = state.get("session_id", "unknown")

    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    user_text = last_human.content if last_human else ""
    task_context = routing.reasoning if routing else "Handle the memory/recall request."

    # --- Real semantic memory search for this specific query ---
    logger.info("🔍 MNEMOSYNE searching | session=%s | query=%r", session_id, user_text[:80])
    memory_results = search_memory(user_text, limit=5)
    actions_taken = []

    if memory_results:
        logger.info(
            "📚 MNEMOSYNE found %d memories | top_sim=%.3f | top=%r",
            len(memory_results),
            memory_results[0].get("similarity", 0),
            memory_results[0]["content"][:80],
        )
    else:
        logger.info("📚 MNEMOSYNE found 0 memories for query=%r", user_text[:60])

    # --- Build context from pre-fetched state memories + live search ---
    prebuilt_context = _build_memory_context(state)

    live_context = ""
    if memory_results:
        live_lines = "\n".join(
            f"  [{r.get('source_type', 'memory')}] "
            f"(sim={r.get('similarity', 0):.2f}) {r['content'][:200]}"
            for r in memory_results
        )
        live_context = f"\nLive semantic search results for '{user_text}':\n{live_lines}"
        actions_taken.append(f"Semantic search returned {len(memory_results)} results")
    else:
        live_context = f"\nNo semantic memories found for: {user_text!r}"
        actions_taken.append("Semantic search returned 0 results")

    # --- Entity lookup if user mentions a name ---
    entity_context = ""
    words = user_text.split()
    if len(words) <= 5:
        # Short query — try direct entity lookup on each capitalised word
        for word in words:
            if word[0].isupper() and len(word) > 2:
                logger.debug("🏷️  MNEMOSYNE entity lookup | word=%r", word)
                entity = get_entity(word)
                if entity:
                    rels = get_entity_relationships(word)
                    entity_context += (
                        f"\nEntity found: {entity['name']} ({entity['type']}) "
                        f"— attributes: {entity['attributes']}"
                    )
                    if rels:
                        entity_context += f"\n  Relationships: {rels[:3]}"
                    actions_taken.append(f"Entity lookup: {entity['name']}")
                    logger.info(
                        "✅ MNEMOSYNE entity found | name=%r type=%s attrs=%s",
                        entity["name"], entity["type"], entity["attributes"],
                    )
                    break

    full_memory_context = (
        (f"\n\n{prebuilt_context}" if prebuilt_context else "")
        + live_context
        + entity_context
    )

    # --- Build LLM messages ---
    hist_msgs: list = [SystemMessage(content=SYSTEM)]
    for m in history[-6:]:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        hist_msgs.append(cls(content=m["content"]))

    hist_msgs.append(HumanMessage(
        content=(
            f"Task: {user_text}\n"
            f"Context: {task_context}"
            f"{full_memory_context}"
        )
    ))

    response = brain.invoke(hist_msgs)
    content = response.content if hasattr(response, "content") else str(response)

    actions_taken = actions_taken or ["Memory search completed"]
    confidence = 0.92 if memory_results else 0.70

    ar = AgentResponse(
        agent_name="mnemosyne",
        domain=DOMAIN,
        response=content,
        actions_taken=actions_taken,
        confidence=confidence,
    )
    return {"agent_responses": [ar]}
