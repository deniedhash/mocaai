"""
MOCA FastAPI Application — Main entry point.

Endpoints:
  GET  /moca/health       — System health status
  POST /moca/ask          — Synchronous chat
  WS   /moca/stream       — Real-time bidirectional WebSocket

Lifespan:
  - Validates brain provider on startup
  - Builds LangGraph orchestrator graph
  - Graceful shutdown cleanup
"""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# ---------------------------------------------------------------------------
# Logging configuration
# Set LOG_LEVEL=DEBUG in .env to see every memory operation in detail.
# Set LOG_LEVEL=INFO  in .env for production-level output.
# ---------------------------------------------------------------------------

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)-25s  %(message)s",
    datefmt="%H:%M:%S",
)

# Quiet down noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("torch").setLevel(logging.WARNING)
logging.getLogger("filelock").setLevel(logging.WARNING)
logging.getLogger("watchfiles").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

logger = logging.getLogger("moca.main")

# ---------------------------------------------------------------------------
# Application State
# ---------------------------------------------------------------------------

_state: dict = {"brain": None, "graph": None, "ready": False, "services": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    logger.info("⚡ MOCA is waking up... (log_level=%s)", _LOG_LEVEL)

    try:
        from core.brain import get_brain
        from core.orchestrator import build_graph

        _state["brain"] = get_brain()
        logger.info("✅ Brain loaded | provider=%s model=%s",
                    os.getenv("BRAIN_PROVIDER", "cerebras"),
                    os.getenv("BRAIN_MODEL", "unknown"))

        _state["graph"] = build_graph()
        logger.info("✅ LangGraph orchestrator compiled")

        # Pre-warm embedding model + DB engine so first request is fast
        try:
            from memory.vector_store import embed_text, _get_engine
            await embed_text("warmup")
            logger.info("✅ Embedding model warmed up")
            _get_engine()
            logger.info("✅ DB engine initialised")
        except Exception as e:
            logger.warning("⚠️  Warmup step failed (non-fatal): %s", e)

        _state["ready"] = True
        logger.info("🧠 MOCA is ready — all systems operational")

    except Exception as e:
        logger.warning("⚠️  MOCA startup warning: %s", e)
        logger.warning("   Server will start but LLM calls may fail until config is corrected.")
        _state["ready"] = False

    # Phase 4 — Core Services Layer
    try:
        from services.registry import MOCAServiceRegistry
        registry = MOCAServiceRegistry()
        await registry.start_all()
        _state["services"] = registry
        app.state.services = registry
        logger.info("✅ MOCA service registry online")
    except Exception as e:
        logger.warning("⚠️  Service registry startup failed (non-fatal): %s", e)
        _state["services"] = None

    yield

    logger.info("🛑 MOCA shutting down.")
    if _state.get("services"):
        try:
            await _state["services"].stop_all()
        except Exception as e:
            logger.warning("Service registry shutdown error: %s", e)
    _state["brain"] = None
    _state["graph"] = None
    _state["ready"] = False
    _state["services"] = None


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MOCA — My Only Capable Assistant",
    description="Fully autonomous AI ecosystem server — Phase 3",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS — all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

from api.routes import router as rest_router
from api.websocket import router as ws_router

app.include_router(rest_router)
app.include_router(ws_router)


# ---------------------------------------------------------------------------
# Expose app state to routes
# ---------------------------------------------------------------------------

def get_app_state() -> dict:
    return _state
