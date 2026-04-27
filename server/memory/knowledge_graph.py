"""
Knowledge Graph — Phase 3 entity and relationship tracking.

Provides a lightweight graph layer backed by PostgreSQL (entities +
relationships tables). Neo4j is a future option; this keeps the logic
clean and isolated so the swap is straightforward later.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

logger = logging.getLogger("moca.knowledge_graph")

_POSTGRES_URL = os.getenv(
    "POSTGRES_URL", "postgresql://moca:mocapassword@localhost:5432/mocadb"
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_POSTGRES_URL, pool_pre_ping=True)
    return _engine


# ---------------------------------------------------------------------------
# Entity operations
# ---------------------------------------------------------------------------


async def upsert_entity(
    name: str,
    entity_type: str,
    attributes: Optional[dict] = None,
) -> Optional[str]:
    """
    Insert or merge attributes into an existing entity (case-insensitive name match).
    """
    logger.debug("🏷️  upsert_entity | name=%r type=%s attrs=%s", name, entity_type, attributes)
    try:
        attrs = attributes or {}
        engine = _get_engine()

        with engine.connect() as conn:
            # Check if entity already exists (case-insensitive)
            existing = conn.execute(
                text("SELECT id, attributes FROM entities WHERE LOWER(name) = LOWER(:name)"),
                {"name": name},
            ).fetchone()

            if existing:
                entity_id = str(existing[0])
                merged = {**(existing[1] or {}), **attrs}
                conn.execute(
                    text(
                        """
                        UPDATE entities
                        SET attributes = CAST(:attributes AS jsonb), updated_at = NOW()
                        WHERE id = CAST(:id AS uuid)
                        """
                    ),
                    {"attributes": json.dumps(merged), "id": entity_id},
                )
                logger.info(
                    "🔄 Entity UPDATED | id=%s name=%r merged_attrs=%s",
                    entity_id, name, merged,
                )
            else:
                row = conn.execute(
                    text(
                        """
                        INSERT INTO entities (name, type, attributes)
                        VALUES (:name, :type, CAST(:attributes AS jsonb))
                        RETURNING id
                        """
                    ),
                    {
                        "name": name,
                        "type": entity_type,
                        "attributes": json.dumps(attrs),
                    },
                )
                entity_id = str(row.scalar())
                logger.info(
                    "✨ Entity CREATED | id=%s name=%r type=%s attrs=%s",
                    entity_id, name, entity_type, attrs,
                )

            conn.commit()

        return entity_id

    except Exception as exc:
        logger.error("❌ upsert_entity FAILED | name=%r | %s", name, exc, exc_info=True)
        return None


async def get_entity(name: str) -> Optional[dict]:
    """Look up an entity by name (case-insensitive)."""
    logger.debug("🔍 get_entity | name=%r", name)
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, name, type, attributes, created_at, updated_at
                    FROM entities
                    WHERE LOWER(name) = LOWER(:name)
                    """
                ),
                {"name": name},
            ).fetchone()

        if not row:
            logger.debug("   get_entity | %r not found", name)
            return None

        result = {
            "id": str(row[0]),
            "name": row[1],
            "type": row[2],
            "attributes": row[3] or {},
            "created_at": str(row[4]),
            "updated_at": str(row[5]),
        }
        logger.info("✅ get_entity | found name=%r type=%s attrs=%s", result["name"], result["type"], result["attributes"])
        return result
    except Exception as exc:
        logger.error("❌ get_entity FAILED | name=%r | %s", name, exc, exc_info=True)
        return None


async def search_entities(query: str, limit: int = 10) -> list[dict]:
    """Keyword search across entity names and attributes."""
    logger.debug("🔍 search_entities | query=%r limit=%d", query, limit)
    try:
        engine = _get_engine()
        pattern = f"%{query}%"
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, name, type, attributes, created_at, updated_at
                    FROM entities
                    WHERE name ILIKE :pattern
                       OR attributes::text ILIKE :pattern
                    ORDER BY name
                    LIMIT :limit
                    """
                ),
                {"pattern": pattern, "limit": limit},
            ).fetchall()

        results = [
            {
                "id": str(r[0]),
                "name": r[1],
                "type": r[2],
                "attributes": r[3] or {},
                "created_at": str(r[4]),
                "updated_at": str(r[5]),
            }
            for r in rows
        ]
        logger.info("✅ search_entities | query=%r found=%d", query, len(results))
        return results
    except Exception as exc:
        logger.error("❌ search_entities FAILED: %s", exc, exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Relationship operations
# ---------------------------------------------------------------------------


async def add_relationship(
    name_a: str,
    name_b: str,
    relationship: str,
    metadata: Optional[dict] = None,
) -> Optional[str]:
    """Record a directed relationship between two entities (upserts both first)."""
    logger.info("🔗 add_relationship | %r -[%s]-> %r", name_a, relationship, name_b)
    try:
        # Ensure both entities exist
        id_a = await upsert_entity(name_a, "concept")
        id_b = await upsert_entity(name_b, "concept")

        if not id_a or not id_b:
            return None

        engine = _get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO relationships (entity_a, entity_b, relationship, metadata)
                    VALUES (CAST(:a AS uuid), CAST(:b AS uuid), :rel, CAST(:meta AS jsonb))
                    RETURNING id
                    """
                ),
                {
                    "a": id_a,
                    "b": id_b,
                    "rel": relationship,
                    "meta": json.dumps(metadata or {}),
                },
            )
            rel_id = str(row.scalar())
            conn.commit()

        logger.info(
            "✅ Relationship stored | id=%s | %r -[%s]-> %r",
            rel_id, name_a, relationship, name_b,
        )
        return rel_id

    except Exception as exc:
        logger.error(
            "❌ add_relationship FAILED (%r, %r): %s", name_a, name_b, exc, exc_info=True
        )
        return None


async def get_relationships(entity_name: str) -> list[dict]:
    """
    Retrieve all relationships where `entity_name` appears (either direction).

    Returns:
        List of dicts with entity_a, entity_b, relationship, metadata.
    """
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        ea.name AS name_a,
                        eb.name AS name_b,
                        r.relationship,
                        r.metadata,
                        r.created_at
                    FROM relationships r
                    JOIN entities ea ON r.entity_a = ea.id
                    JOIN entities eb ON r.entity_b = eb.id
                    WHERE LOWER(ea.name) = LOWER(:name)
                       OR LOWER(eb.name) = LOWER(:name)
                    ORDER BY r.created_at DESC
                    LIMIT 50
                    """
                ),
                {"name": entity_name},
            ).fetchall()

        return [
            {
                "entity_a": r[0],
                "entity_b": r[1],
                "relationship": r[2],
                "metadata": r[3] or {},
                "created_at": str(r[4]),
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error("get_relationships failed: %s", exc, exc_info=True)
        return []
