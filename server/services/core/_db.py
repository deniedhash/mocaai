import asyncio
import os

from sqlalchemy import create_engine

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            os.getenv("POSTGRES_URL", "postgresql://moca:mocapassword@127.0.0.1:5433/mocadb"),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


async def _run_sync(fn):
    return await asyncio.to_thread(fn)
