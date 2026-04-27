import logging
from datetime import datetime

logger = logging.getLogger("moca.services.health")

_STUB = {"status": "stub"}


class MOCAHealthService:
    async def get_heart_rate(self) -> dict:
        logger.info("[STUB] get_heart_rate")
        return {**_STUB, "bpm": None}

    async def get_sleep_data(self, date: datetime = None) -> dict:
        logger.info("[STUB] get_sleep_data | date=%s", date)
        return {**_STUB, "hours": None, "quality": None}

    async def get_activity(self, date: datetime = None) -> dict:
        logger.info("[STUB] get_activity | date=%s", date)
        return {**_STUB, "steps": None, "calories": None}

    async def get_stress_level(self) -> dict:
        logger.info("[STUB] get_stress_level")
        return {**_STUB, "level": None}

    async def log_manual_health(self, metric: str, value) -> dict:
        logger.info("[STUB] log_manual_health | metric=%s value=%s", metric, value)
        return {**_STUB, "metric": metric, "value": value}
