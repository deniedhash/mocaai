"""
MOCA Memory Layer — thin context/state wrapper for Phase 1.
Extended in Phase 2 with semantic compression and context budgeting.
"""

from memory.cache import get_history, add_message, clear_session


class ContextManager:
    """Manages active session context for the orchestrator."""

    def __init__(self, session_id: str):
        self.session_id = session_id

    async def get_context(self) -> list[dict]:
        """Return current short-term history for this session."""
        return await get_history(self.session_id)

    async def push(self, role: str, content: str):
        """Add a message to the session context."""
        await add_message(self.session_id, role, content)

    async def clear(self):
        """Wipe session context."""
        await clear_session(self.session_id)
