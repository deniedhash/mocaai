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

import asyncio
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

_state: dict = {"brain": None, "graph": None, "ready": False, "services": None, "context_engine": None}


async def _brain_health_loop(brain) -> None:
    while True:
        await asyncio.sleep(60)
        await brain.run_health_checks()
        parts = []
        if brain.fast_brain:
            parts.append(f"fast={brain.fast_healthy}")
        if brain.smart_brain:
            parts.append(f"smart={brain.smart_healthy}")
        logger.info("Brain health | %s", " ".join(parts))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    logger.info("⚡ MOCA is waking up... (log_level=%s)", _LOG_LEVEL)

    health_task = None
    try:
        from core.brain import MOCABrain
        from core.orchestrator import build_graph

        brain = MOCABrain()

        _PLACEHOLDER = ("your_key_here",)

        def _valid_key(env: str) -> str:
            v = os.getenv(env, "").strip()
            return v if v and v not in _PLACEHOLDER else ""

        fast_key = _valid_key("FAST_BRAIN_API_KEY")
        smart_key = _valid_key("SMART_BRAIN_API_KEY")
        legacy_key = _valid_key("BRAIN_API_KEY")

        if fast_key and smart_key:
            brain.initialize(
                fast_provider=os.getenv("FAST_BRAIN_PROVIDER", "cerebras"),
                fast_model=os.getenv("FAST_BRAIN_MODEL", "llama3.1-8b"),
                fast_api_key=fast_key,
                fast_base_url=os.getenv("FAST_BRAIN_BASE_URL", "https://api.cerebras.ai/v1"),
                smart_provider=os.getenv("SMART_BRAIN_PROVIDER", "nvidia_nim"),
                smart_model=os.getenv("SMART_BRAIN_MODEL", "meta/llama-3.3-70b-instruct"),
                smart_api_key=smart_key,
                smart_base_url=os.getenv("SMART_BRAIN_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            )
            logger.info("⚡ Dual-brain mode | fast=%s smart=%s",
                        os.getenv("FAST_BRAIN_MODEL"), os.getenv("SMART_BRAIN_MODEL"))
        elif fast_key:
            brain.initialize(
                fast_provider=os.getenv("FAST_BRAIN_PROVIDER", "cerebras"),
                fast_model=os.getenv("FAST_BRAIN_MODEL", "llama3.1-8b"),
                fast_api_key=fast_key,
                fast_base_url=os.getenv("FAST_BRAIN_BASE_URL", "https://api.cerebras.ai/v1"),
            )
            logger.info("⚡ Single brain mode — fast only | model=%s", os.getenv("FAST_BRAIN_MODEL"))
        elif smart_key:
            brain.initialize(
                smart_provider=os.getenv("SMART_BRAIN_PROVIDER", "nvidia_nim"),
                smart_model=os.getenv("SMART_BRAIN_MODEL", "meta/llama-3.3-70b-instruct"),
                smart_api_key=smart_key,
                smart_base_url=os.getenv("SMART_BRAIN_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            )
            logger.info("⚡ Single brain mode — smart only | model=%s", os.getenv("SMART_BRAIN_MODEL"))
        elif legacy_key:
            model = os.getenv("BRAIN_MODEL", "llama3.1-8b")
            base_url = os.getenv("BRAIN_BASE_URL", "https://api.cerebras.ai/v1")
            provider = os.getenv("BRAIN_PROVIDER", "cerebras")
            brain.initialize(
                fast_provider=provider, fast_model=model,
                fast_api_key=legacy_key, fast_base_url=base_url,
            )
            logger.info("⚡ Legacy single brain mode | provider=%s model=%s", provider, model)
        else:
            raise ValueError(
                "No brain API key configured. "
                "Set FAST_BRAIN_API_KEY + SMART_BRAIN_API_KEY (dual), "
                "one of them (single), or BRAIN_API_KEY (legacy)."
            )

        _state["brain"] = brain

        _state["graph"] = build_graph()
        logger.info("✅ LangGraph orchestrator compiled")

        health_task = asyncio.create_task(_brain_health_loop(brain))

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

    # Phase 5 — Context Engine
    try:
        from core.context_engine import MOCAContextEngine
        context_engine = MOCAContextEngine()
        _state["context_engine"] = context_engine
        app.state.context_engine = context_engine
        logger.info("✅ MOCA context engine online")
    except Exception as e:
        logger.warning("⚠️  Context engine startup failed (non-fatal): %s", e)
        _state["context_engine"] = None

    yield

    logger.info("🛑 MOCA shutting down.")
    if health_task is not None:
        health_task.cancel()
    if _state.get("services"):
        try:
            await _state["services"].stop_all()
        except Exception as e:
            logger.warning("Service registry shutdown error: %s", e)
    _state["brain"] = None
    _state["graph"] = None
    _state["ready"] = False
    _state["services"] = None
    _state["context_engine"] = None


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
