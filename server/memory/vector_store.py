"""
Vector store — Phase 3 semantic memory.

Uses sentence-transformers/all-MiniLM-L6-v2 (local, 384-dim, free) to
generate embeddings and pgvector for cosine-similarity search.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

logger = logging.getLogger("moca.vector_store")

_POSTGRES_URL = os.getenv(
    "POSTGRES_URL", "postgresql://moca:mocapassword@localhost:5432/mocadb"
)

_engine = None
_model = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_POSTGRES_URL, pool_pre_ping=True)
        logger.debug("🗄️  DB engine created | url=%s", _POSTGRES_URL.split("@")[-1])
    return _engine


def _get_model():
    """Lazy-init SentenceTransformer. Downloads ~80 MB on first call, then cached."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # type: ignore
        logger.info("📦 Loading SentenceTransformer all-MiniLM-L6-v2 (first load may take a moment)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("✅ Embedding model ready | dimensions=384")
    return _model


async def embed_text(text_input: str) -> list[float]:
    """
    Encode a string into a 384-dim embedding vector using the local model.
    """
    logger.debug("🔢 embed_text | chars=%d | preview=%r", len(text_input), text_input[:60])
    model = _get_model()
    vector = model.encode(text_input, convert_to_numpy=True)
    logger.debug("✅ embed_text done | dims=%d", len(vector))
    return vector.tolist()


async def save_embedding(
    content: str,
    source_type: str,
    source_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional[str]:
    """
    Generate an embedding for `content` and persist it to the embeddings table.
    """
    logger.debug(
        "💾 save_embedding START | source_type=%s | source_id=%s | content=%r",
        source_type, source_id, content[:80],
    )
    try:
        vector = await embed_text(content)
        meta_dict = dict(metadata or {})
        if source_id:
            meta_dict["source_id_ref"] = str(source_id)
        meta_str = json.dumps(meta_dict)
        engine = _get_engine()

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    f"""
                    INSERT INTO embeddings (content, embedding, source_type, metadata)
                    VALUES (:content, '{vector}'::vector, :source_type,
                            CAST(:metadata AS jsonb))
                    RETURNING id
                    """
                ),
                {
                    "content": content,
                    "source_type": source_type,
                    "metadata": meta_str,
                },
            )
            embedding_id = str(row.scalar())
            conn.commit()

        logger.info(
            "💾 Embedding saved | id=%s | source_type=%s | content=%r",
            embedding_id, source_type, content[:60],
        )
        return embedding_id

    except Exception as exc:
        logger.error("❌ save_embedding FAILED | source_type=%s | error=%s", source_type, exc, exc_info=True)
        return None


async def search_similar(
    query: str,
    limit: int = 5,
    source_type: Optional[str] = None,
) -> list[dict]:
    """
    Cosine similarity search over the embeddings table using pgvector.
    """
    logger.info(
        "🔍 search_similar START | query=%r | limit=%d | filter=%s",
        query[:80], limit, source_type or "none",
    )
    try:
        vector = await embed_text(query)
        engine = _get_engine()

        if source_type:
            sql = text(
                f"""
                SELECT id, content, source_type, source_id, metadata, created_at,
                       1 - (embedding <=> '{vector}'::vector) AS similarity
                FROM embeddings
                WHERE source_type = :source_type
                ORDER BY embedding <=> '{vector}'::vector
                LIMIT :limit
                """
            )
            params = {"source_type": source_type, "limit": limit}
        else:
            sql = text(
                f"""
                SELECT id, content, source_type, source_id, metadata, created_at,
                       1 - (embedding <=> '{vector}'::vector) AS similarity
                FROM embeddings
                ORDER BY embedding <=> '{vector}'::vector
                LIMIT :limit
                """
            )
            params = {"limit": limit}

        with engine.connect() as conn:
            # Sequential scan used for correctness on small tables
            # (IVFFlat needs ~300+ rows to activate)
            conn.execute(text("SET LOCAL enable_indexscan = off"))
            result = conn.execute(sql, params)
            rows = result.fetchall()

        results = [
            {
                "id": str(row[0]),
                "content": row[1],
                "source_type": row[2],
                "source_id": str(row[3]) if row[3] else None,
                "metadata": row[4] if row[4] else {},
                "created_at": str(row[5]),
                "similarity": round(float(row[6]), 4),
            }
            for row in rows
        ]

        if results:
            logger.info(
                "✅ search_similar | found=%d | top_sim=%.3f | top_content=%r",
                len(results),
                results[0]["similarity"],
                results[0]["content"][:60],
            )
            for i, r in enumerate(results):
                logger.debug(
                    "   [%d] sim=%.3f src=%s | %r",
                    i + 1, r["similarity"], r["source_type"], r["content"][:80],
                )
        else:
            logger.info("🔍 search_similar | found=0 (no embeddings stored yet or no matches)")

        return results

    except Exception as exc:
        logger.error("❌ search_similar FAILED | query=%r | error=%s", query[:60], exc, exc_info=True)
        return []
