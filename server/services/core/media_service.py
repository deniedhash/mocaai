import logging

logger = logging.getLogger("moca.services.media")

_STUB = {"status": "stub"}


class MOCAMediaService:
    async def play(self, content: str, service: str = None) -> dict:
        logger.info("[STUB] play | content=%r service=%s", content, service)
        return {**_STUB, "content": content, "service": service}

    async def pause(self) -> dict:
        logger.info("[STUB] pause")
        return _STUB

    async def set_volume(self, level: int) -> dict:
        logger.info("[STUB] set_volume | level=%d", level)
        return {**_STUB, "volume": level}

    async def get_now_playing(self) -> dict:
        logger.info("[STUB] get_now_playing")
        return {**_STUB, "track": None}

    async def search_content(self, query: str, service: str = None) -> dict:
        logger.info("[STUB] search_content | query=%r service=%s", query, service)
        return {**_STUB, "results": []}
