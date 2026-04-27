import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.core.clock_service import MOCAClockService
from services.core.notification_service import MOCANotificationService
from services.core.device_service import MOCADeviceService
from services.core.calendar_service import MOCACalendarService
from services.core.location_service import MOCALocationService
from services.core.communication_service import MOCACommunicationService
from services.core.health_service import MOCAHealthService
from services.core.media_service import MOCAMediaService
from services.core.security_service import MOCASecurityService

logger = logging.getLogger("moca.services.registry")


class MOCAServiceRegistry:
    def __init__(self):
        self.clock = MOCAClockService()
        self.notification = MOCANotificationService()
        self.device = MOCADeviceService()
        self.calendar = MOCACalendarService()
        self.location = MOCALocationService()
        self.communication = MOCACommunicationService()
        self.health = MOCAHealthService()
        self.media = MOCAMediaService()
        self.security = MOCASecurityService()
        self._scheduler: AsyncIOScheduler = None

    async def start_all(self):
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        self.clock.set_scheduler(self._scheduler)
        self._scheduler.start()
        logger.info("✅ APScheduler started")

        services = [
            ("clock", self.clock),
            ("notification", self.notification),
            ("device", self.device),
            ("calendar", self.calendar),
            ("location", self.location),
            ("communication", self.communication),
            ("health", self.health),
            ("media", self.media),
            ("security", self.security),
        ]
        for name, _ in services:
            logger.info("✅ Service online | %s", name)

        try:
            await self.clock.restore_active_timers()
        except Exception as exc:
            logger.warning("Timer restore failed (non-fatal): %s", exc)

    async def stop_all(self):
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("APScheduler shut down")
        logger.info("🛑 All MOCA services stopped")

    def status(self) -> list[dict]:
        names = [
            "clock", "notification", "device", "calendar", "location",
            "communication", "health", "media", "security",
        ]
        return [{"name": n, "status": "online"} for n in names]
