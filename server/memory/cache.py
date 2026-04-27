"""
Short-term conversation memory backed by Redis.

Stores the last N messages per session as a JSON list.
N is configured via SHORT_TERM_WINDOW env variable (default: 10).

All functions are async-compatible but use synchronous Redis client
for Phase 1 simplicity. Phase 2 will migrate to aioredis.
"""

import json
import os
from typing import Optional

import redis
from dotenv import load_dotenv

load_dotenv()

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_WINDOW = int(os.getenv("SHORT_TERM_WINDOW", "10"))
_KEY_PREFIX = "moca:session:"
_TTL = 60 * 60 * 24  # 24-hour TTL on session keys

_client: Optional[redis.Redis] = None


def _get_client() -> redis.Redis:
    """Lazy-init Redis client (connection pooled)."""
    global _client
    if _client is None:
        _client = redis.from_url(_REDIS_URL, decode_responses=True)
    return _client


async def get_history(session_id: str) -> list[dict]:
    """
    Return the last N messages for a session.

    Args:
        session_id: Unique session identifier.

    Returns:
        List of {"role": str, "content": str} dicts, oldest first.
    """
    r = _get_client()
    key = f"{_KEY_PREFIX}{session_id}"
    raw = r.get(key)
    if not raw:
        return []
    messages = json.loads(raw)
    return messages[-_WINDOW:]


async def add_message(session_id: str, role: str, content: str) -> None:
    """
    Append a message to the session history and trim to window size.

    Args:
        session_id: Unique session identifier.
        role: 'user' or 'assistant'.
        content: Message text.
    """
    r = _get_client()
    key = f"{_KEY_PREFIX}{session_id}"
    raw = r.get(key)
    messages = json.loads(raw) if raw else []
    messages.append({"role": role, "content": content})
    # Keep only last N * 2 to avoid unbounded growth before trim
    messages = messages[-(  _WINDOW * 2):]
    r.set(key, json.dumps(messages), ex=_TTL)


async def clear_session(session_id: str) -> None:
    """
    Delete all history for a session.

    Args:
        session_id: Unique session identifier.
    """
    r = _get_client()
    key = f"{_KEY_PREFIX}{session_id}"
    r.delete(key)
