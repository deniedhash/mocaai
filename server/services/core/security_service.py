import logging

logger = logging.getLogger("moca.services.security")

_STUB = {"status": "stub"}


class MOCASecurityService:
    async def scan_network(self) -> dict:
        logger.info("[STUB] scan_network")
        return {**_STUB, "devices_found": None}

    async def check_threats(self) -> dict:
        logger.info("[STUB] check_threats")
        return {**_STUB, "threats": []}

    async def audit_privacy(self) -> dict:
        logger.info("[STUB] audit_privacy")
        return {**_STUB, "issues": []}

    async def log_security_event(self, event: dict) -> dict:
        logger.info("[STUB] log_security_event | event=%s", event)
        return {**_STUB, "logged": True}

    async def get_security_status(self) -> dict:
        logger.info("[STUB] get_security_status")
        return {**_STUB, "overall": "unknown"}
