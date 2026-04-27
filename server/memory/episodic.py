"""
Long-term episodic memory backed by PostgreSQL.

Phase 3 additions:
  - extract_and_store_knowledge: LLM-driven fact/entity extraction with
    JSON parsing safety net (handles markdown fences, missing keys, bad JSON).
  - get_recent_knowledge: Retrieve latest extracted facts for context injection.

Phase 1 baseline (still present):
  - save_interaction: Persist every conversation turn.
  - search_relevant: Basic keyword search (fallback when vector search unavailable).
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

load_dotenv()

logger = logging.getLogger("moca.episodic")

_POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://moca:mocapassword@localhost:5432/mocadb")

_engine = None

# ---------------------------------------------------------------------------
# Extraction prompt — instructs LLM to return strictly valid JSON
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """You are a knowledge extraction engine. Extract structured facts from the conversation below.

Return ONLY valid JSON — no explanations, no markdown code blocks, no text outside the JSON.

Required format (use empty lists if nothing found):
{{
  "facts": ["user has a meeting at 3pm"],
  "people": ["John — colleague"],
  "preferences": ["prefers direct communication"],
  "commitments": ["will reply to John by Friday"],
  "entities": ["Acme Corp (org)"]
}}

User said: {message}
MOCA replied: {response}

Return only the JSON object."""


def _get_engine():
    """Lazy-init SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(_POSTGRES_URL, pool_pre_ping=True)
    return _engine


# ---------------------------------------------------------------------------
# Phase 1 baseline — unchanged
# ---------------------------------------------------------------------------


async def save_interaction(
    session_id: str,
    role: str,
    content: str,
    agent: Optional[str] = "prime",
    metadata: Optional[dict] = None,
) -> None:
    """
    Persist a single interaction turn to the conversations table.
    """
    engine = _get_engine()
    meta_json = metadata or {}
    logger.debug(
        "💬 save_interaction | session=%s role=%s agent=%s | content=%r",
        session_id, role, agent, content[:80],
    )

    with Session(engine) as session:
        session.execute(
            text(
                """
                INSERT INTO conversations (session_id, role, content, agent, metadata, created_at)
                VALUES (:session_id, :role, :content, :agent, CAST(:metadata AS jsonb), :created_at)
                """
            ),
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "agent": agent,
                "metadata": str(meta_json).replace("'", '"'),
                "created_at": datetime.now(timezone.utc),
            },
        )
        session.commit()
    logger.debug("✅ save_interaction done | session=%s role=%s", session_id, role)


async def search_relevant(query: str, limit: int = 5) -> list[dict]:
    """
    Search past interactions by keyword relevance (Phase 1 fallback).
    """
    logger.debug("🔎 search_relevant | query=%r | limit=%d", query[:60], limit)
    engine = _get_engine()
    terms = query.split()[:5]
    logger.debug("   terms=%s", terms)

    conditions = " OR ".join([f"content ILIKE :term{i}" for i in range(len(terms))])
    params = {f"term{i}": f"%{term}%" for i, term in enumerate(terms)}
    params["limit"] = limit

    with Session(engine) as session:
        result = session.execute(
            text(
                f"""
                SELECT session_id, role, content, agent, created_at
                FROM conversations
                WHERE {conditions}
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            params,
        )
        rows = result.fetchall()

    logger.debug("✅ search_relevant | found=%d rows", len(rows))
    return [
        {
            "session_id": row[0],
            "role": row[1],
            "content": row[2],
            "agent": row[3],
            "created_at": str(row[4]),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Phase 3 — Knowledge extraction
# ---------------------------------------------------------------------------


def _parse_extraction_json(raw: str) -> Optional[dict]:
    """
    Robustly parse LLM extraction output.

    Handles:
    - Markdown code fences (```json ... ``` or ``` ... ```)
    - Leading/trailing whitespace
    - Missing top-level keys (fills with empty lists)
    - Completely invalid JSON (returns None so caller can bail gracefully)
    """
    text_clean = raw.strip()

    # Strip markdown code fences if present
    if text_clean.startswith("```"):
        # Remove opening fence (```json or ```)
        text_clean = re.sub(r"^```[a-zA-Z]*\n?", "", text_clean)
        # Remove closing fence
        text_clean = re.sub(r"```\s*$", "", text_clean).strip()

    # Try to extract just the JSON object if there's surrounding prose
    json_match = re.search(r"\{.*\}", text_clean, re.DOTALL)
    if json_match:
        text_clean = json_match.group(0)

    try:
        data = json.loads(text_clean)
    except (json.JSONDecodeError, ValueError):
        return None

    # Normalise: ensure all expected keys exist
    defaults = {
        "facts": [],
        "people": [],
        "preferences": [],
        "commitments": [],
        "entities": [],
    }
    for key, default in defaults.items():
        if key not in data or not isinstance(data[key], list):
            data[key] = default

    return data


async def extract_and_store_knowledge(
    session_id: str,
    message: str,
    response: str,
    agent: str,
) -> None:
    """
    Run LLM knowledge extraction on a user/assistant exchange, then persist
    the extracted facts to the memories table and generate embeddings.

    Designed to run as a background task — all errors are logged and absorbed,
    never surfaced to the caller.

    Args:
        session_id: Current session identifier (stored as metadata).
        message:    The user's message.
        response:   MOCA's reply.
        agent:      Which agent produced the response.
    """
    from core.brain import get_brain  # lazy import to avoid circular deps
    from memory.vector_store import save_embedding
    from memory.knowledge_graph import upsert_entity

    logger.info(
        "🧠 extract_and_store_knowledge START | session=%s agent=%s | msg=%r",
        session_id, agent, message[:80],
    )

    try:
        brain = get_brain()
        from langchain_core.messages import HumanMessage

        prompt = _EXTRACTION_PROMPT.format(message=message, response=response)
        logger.debug("   📤 Sending extraction prompt to LLM...")
        llm_result = brain.invoke([HumanMessage(content=prompt)])
        raw = llm_result.content if hasattr(llm_result, "content") else str(llm_result)
        logger.debug("   📥 LLM raw response: %r", raw[:300])

    except Exception as exc:
        logger.warning("❌ Knowledge extraction LLM call failed: %s", exc)
        return

    # --- JSON safety net ---
    data = _parse_extraction_json(raw)
    if data is None:
        logger.warning(
            "❌ JSON parse failed | session=%s | raw=%r",
            session_id, raw[:300],
        )
        return

    logger.info(
        "📋 Parsed extraction | facts=%d people=%d prefs=%d commitments=%d entities=%d",
        len(data.get("facts", [])),
        len(data.get("people", [])),
        len(data.get("preferences", [])),
        len(data.get("commitments", [])),
        len(data.get("entities", [])),
    )
    if logger.isEnabledFor(logging.DEBUG):
        for k, v in data.items():
            if v:
                logger.debug("   [%s] %s", k, v)

    # Collect all items to embed
    all_items: list[tuple[str, str]] = []  # (content, memory_type)

    for fact in data.get("facts", []):
        if fact.strip():
            all_items.append((fact.strip(), "fact"))

    for pref in data.get("preferences", []):
        if pref.strip():
            all_items.append((pref.strip(), "preference"))

    for commitment in data.get("commitments", []):
        if commitment.strip():
            all_items.append((commitment.strip(), "commitment"))

    # Persist to memories table and embed each item
    engine = _get_engine()
    stored_count = 0
    for content_item, memory_type in all_items:
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        INSERT INTO memories (type, content, importance_score, metadata)
                        VALUES (:type, :content, :score, CAST(:metadata AS jsonb))
                        RETURNING id
                        """
                    ),
                    {
                        "type": memory_type,
                        "content": content_item,
                        "score": 0.7,
                        "metadata": json.dumps({
                            "session_id": session_id,
                            "agent": agent,
                        }),
                    },
                )
                memory_id = str(row.scalar())
                conn.commit()

            logger.info(
                "   ✅ Memory stored | id=%s type=%s | %r",
                memory_id, memory_type, content_item[:80],
            )
            stored_count += 1

            # Store embedding for semantic search
            await save_embedding(
                content=content_item,
                source_type="knowledge",
                source_id=memory_id,
                metadata={"session_id": session_id, "memory_type": memory_type},
            )

        except Exception as exc:
            logger.warning("❌ Failed to store memory item %r: %s", content_item, exc)

    # Store person/entity embeddings and upsert into knowledge graph
    person_count = 0
    for person_entry in data.get("people", []):
        if not person_entry.strip():
            continue
        parts = re.split(r"\s*[—–-]\s*", person_entry.strip(), maxsplit=1)
        person_name = parts[0].strip()
        role_note = parts[1].strip() if len(parts) > 1 else ""

        try:
            attrs = {"role": role_note} if role_note else {}
            entity_id = await upsert_entity(person_name, "person", attrs)
            logger.info(
                "   👤 Person entity | id=%s name=%r role=%r",
                entity_id, person_name, role_note,
            )
            await save_embedding(
                content=f"{person_name}: {role_note}" if role_note else person_name,
                source_type="knowledge",
                metadata={"session_id": session_id, "entity_type": "person", "name": person_name},
            )
            person_count += 1
        except Exception as exc:
            logger.warning("❌ Failed to store person entity %r: %s", person_name, exc)

    entity_count = 0
    for entity_entry in data.get("entities", []):
        if not entity_entry.strip():
            continue
        match = re.match(r"(.+?)\s*\((\w+)\)\s*$", entity_entry.strip())
        if match:
            entity_name, entity_type = match.group(1).strip(), match.group(2).strip()
        else:
            entity_name, entity_type = entity_entry.strip(), "concept"

        try:
            entity_id = await upsert_entity(entity_name, entity_type)
            logger.info(
                "   🏷️  Entity | id=%s name=%r type=%s",
                entity_id, entity_name, entity_type,
            )
            await save_embedding(
                content=entity_entry.strip(),
                source_type="knowledge",
                metadata={"session_id": session_id, "entity_type": entity_type},
            )
            entity_count += 1
        except Exception as exc:
            logger.warning("❌ Failed to store entity %r: %s", entity_name, exc)

    total = stored_count + person_count + entity_count
    logger.info(
        "🧠 extract_and_store_knowledge DONE | session=%s | "
        "memories=%d persons=%d entities=%d | total=%d items stored",
        session_id, stored_count, person_count, entity_count, total,
    )


# ---------------------------------------------------------------------------
# Phase 3 — Context helpers
# ---------------------------------------------------------------------------


async def get_recent_knowledge(limit: int = 10) -> list[dict]:
    """
    Fetch the most recently extracted knowledge items from the memories table.
    """
    logger.debug("📚 get_recent_knowledge | limit=%d", limit)
    try:
        engine = _get_engine()
        with Session(engine) as session:
            rows = session.execute(
                text(
                    """
                    SELECT type, content, metadata, created_at
                    FROM memories
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).fetchall()

        results = [
            {
                "type": r[0],
                "content": r[1],
                "metadata": r[2] or {},
                "created_at": str(r[3]),
            }
            for r in rows
        ]
        logger.debug("✅ get_recent_knowledge | returned=%d items", len(results))
        if results and logger.isEnabledFor(logging.DEBUG):
            for r in results[:3]:
                logger.debug("   [%s] %r", r["type"], r["content"][:80])
        return results
    except Exception as exc:
        logger.error("❌ get_recent_knowledge failed: %s", exc, exc_info=True)
        return []

