import logging

logger = logging.getLogger("moca.services.communication")

_STUB = {"status": "stub"}


class MOCACommunicationService:
    async def send_message(self, channel: str, contact: str, content: str) -> dict:
        logger.info("[STUB] send_message | channel=%s contact=%s", channel, contact)
        return {**_STUB, "channel": channel, "contact": contact}

    async def check_messages(self, channel: str, contact: str = None) -> dict:
        logger.info("[STUB] check_messages | channel=%s contact=%s", channel, contact)
        return {**_STUB, "messages": []}

    async def make_call(self, contact: str, channel: str = "phone") -> dict:
        logger.info("[STUB] make_call | contact=%s channel=%s", contact, channel)
        return {**_STUB, "contact": contact, "channel": channel}

    async def screen_call(self, caller_id: str) -> str:
        logger.info("[STUB] screen_call | caller=%s", caller_id)
        return "stub"

    async def get_call_history(self, limit: int = 10) -> list:
        logger.info("[STUB] get_call_history | limit=%d", limit)
        return []
