"""
MOCA Brain — Dual-brain LLM abstraction with automatic fallback.

Fast brain:  Cerebras llama3.1-8b  — routing, synthesis, extraction (~0.3s)
Smart brain: NIM llama-3.3-70b    — specialist agent execution (~1.7s)

Backwards-compatible: get_brain() still works with single BRAIN_* env vars.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("moca.brain")


class MOCABrain:
    """Manages fast and smart LLM instances with health tracking and fallback."""

    def __init__(self):
        self.fast_brain = None
        self.smart_brain = None
        self.fast_healthy: bool = True
        self.smart_healthy: bool = True
        self._fast_provider: str = ""
        self._fast_model: str = ""
        self._smart_provider: str = ""
        self._smart_model: str = ""
        self._lock = asyncio.Lock()

    def initialize(
        self,
        fast_provider: str = "",
        fast_model: str = "",
        fast_api_key: str = "",
        fast_base_url: str = "",
        smart_provider: str = "",
        smart_model: str = "",
        smart_api_key: str = "",
        smart_base_url: str = "",
    ) -> None:
        from langchain_openai import ChatOpenAI

        timeout = int(os.getenv("BRAIN_TIMEOUT", "60"))

        if fast_api_key:
            self._fast_provider = fast_provider
            self._fast_model = fast_model
            self.fast_brain = ChatOpenAI(
                model=fast_model,
                api_key=fast_api_key,
                base_url=fast_base_url,
                temperature=0.7,
                max_tokens=2048,
                timeout=timeout,
                max_retries=1,
            )
            logger.info("🧠 Fast brain  | provider=%s model=%s", fast_provider, fast_model)

        if smart_api_key:
            self._smart_provider = smart_provider
            self._smart_model = smart_model
            self.smart_brain = ChatOpenAI(
                model=smart_model,
                api_key=smart_api_key,
                base_url=smart_base_url,
                temperature=0.7,
                max_tokens=2048,
                timeout=timeout,
                max_retries=1,
            )
            logger.info("🧠 Smart brain | provider=%s model=%s", smart_provider, smart_model)

        if not self.fast_brain and not self.smart_brain:
            raise ValueError("initialize() called with no valid API keys.")

    def get_router_brain(self):
        """Fast brain for routing/classification. Falls back to smart if fast is down."""
        if self.fast_healthy and self.fast_brain:
            logger.debug("Router → fast brain (%s)", self._fast_model)
            return self.fast_brain
        if self.smart_brain:
            logger.warning("⚠️  Fast brain down — router falling back to smart brain")
            return self.smart_brain
        raise RuntimeError("Both brains offline. MOCA unavailable.")

    def get_agent_brain(self):
        """Smart brain for specialist agents. Falls back to fast if smart is down."""
        if self.smart_healthy and self.smart_brain:
            logger.debug("Agent → smart brain (%s)", self._smart_model)
            return self.smart_brain
        if self.fast_brain:
            logger.warning("⚠️  Smart brain down — agent falling back to fast brain (quality degraded)")
            return self.fast_brain
        raise RuntimeError("Both brains offline. MOCA unavailable.")

    def get_fast_brain(self):
        """Fast brain for synthesis/extraction. Falls back to smart if fast is down."""
        if self.fast_healthy and self.fast_brain:
            logger.debug("Synthesis → fast brain (%s)", self._fast_model)
            return self.fast_brain
        if self.smart_brain:
            logger.warning("⚠️  Fast brain down — synthesis falling back to smart brain")
            return self.smart_brain
        raise RuntimeError("Both brains offline. MOCA unavailable.")

    async def health_check_fast(self) -> bool:
        if not self.fast_brain:
            return False
        from langchain_core.messages import HumanMessage as HM
        try:
            await self.fast_brain.ainvoke([HM(content="ping")])
            if not self.fast_healthy:
                logger.info("✅ Fast brain recovered")
            self.fast_healthy = True
            return True
        except Exception as exc:
            if self.fast_healthy:
                logger.warning("⚠️  Fast brain health check failed: %s", exc)
            self.fast_healthy = False
            return False

    async def health_check_smart(self) -> bool:
        if not self.smart_brain:
            return False
        from langchain_core.messages import HumanMessage as HM
        try:
            await self.smart_brain.ainvoke([HM(content="ping")])
            if not self.smart_healthy:
                logger.info("✅ Smart brain recovered")
            self.smart_healthy = True
            return True
        except Exception as exc:
            if self.smart_healthy:
                logger.warning("⚠️  Smart brain health check failed: %s", exc)
            self.smart_healthy = False
            return False

    async def run_health_checks(self) -> None:
        await asyncio.gather(
            self.health_check_fast(),
            self.health_check_smart(),
        )

    def get_status(self) -> dict:
        status: dict = {}
        if self.fast_brain:
            status["fast"] = {
                "provider": self._fast_provider,
                "model": self._fast_model,
                "healthy": self.fast_healthy,
                "role": "router + synthesis + extraction",
            }
        if self.smart_brain:
            status["smart"] = {
                "provider": self._smart_provider,
                "model": self._smart_model,
                "healthy": self.smart_healthy,
                "role": "specialist agents",
            }
        status["fallback_active"] = (
            (self.fast_brain is not None and not self.fast_healthy)
            or (self.smart_brain is not None and not self.smart_healthy)
        )
        return status


def get_brain():
    """
    Backwards-compatible factory using single BRAIN_* env vars.
    Used when MOCABrain is not available in state.
    """
    from langchain_openai import ChatOpenAI

    model = os.getenv("BRAIN_MODEL", "llama3.1-8b")
    api_key = os.getenv("BRAIN_API_KEY")
    base_url = os.getenv("BRAIN_BASE_URL", "https://api.cerebras.ai/v1")

    if not api_key or api_key == "your_key_here":
        raise ValueError(
            "BRAIN_API_KEY is not set. "
            "Please add it to your .env file."
        )

    timeout = int(os.getenv("BRAIN_TIMEOUT", "60"))

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.7,
        max_tokens=2048,
        timeout=timeout,
        max_retries=1,
    )
