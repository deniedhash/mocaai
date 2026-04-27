import logging
import uuid
from datetime import datetime

from sqlalchemy import text

from ._db import _get_engine, _run_sync

logger = logging.getLogger("moca.services.device")


class MOCADeviceService:
    async def register_device(
        self,
        name: str,
        device_type: str,
        platform: str,
        always_present: bool = False,
    ) -> dict:
        device_id = str(uuid.uuid4())

        def _insert():
            with _get_engine().connect() as conn:
                conn.execute(text("""
                    INSERT INTO devices
                        (id, name, device_type, platform, always_present, status)
                    VALUES
                        (:id, :name, :dtype, :platform, :always, 'online')
                """), {"id": device_id, "name": name, "dtype": device_type,
                       "platform": platform, "always": always_present})
                conn.commit()

        await _run_sync(_insert)
        logger.info("Device registered | id=%s name=%r type=%s", device_id, name, device_type)
        return {"device_id": device_id, "name": name, "status": "online"}

    async def heartbeat(self, device_id: str, battery_level: int = None) -> bool:
        def _update():
            with _get_engine().connect() as conn:
                conn.execute(text("""
                    UPDATE devices
                    SET last_seen = NOW(), status = 'online', battery_level = :battery
                    WHERE id = :id
                """), {"id": device_id, "battery": battery_level})
                conn.commit()

        await _run_sync(_update)
        logger.debug("Heartbeat | device=%s battery=%s", device_id, battery_level)
        return True

    async def get_best_device(self, priority: str = "normal") -> dict:
        def _query():
            with _get_engine().connect() as conn:
                row = conn.execute(text("""
                    SELECT id, name, device_type, platform, always_present,
                           status, battery_level, last_seen
                    FROM devices
                    WHERE status = 'online'
                    ORDER BY always_present DESC, last_seen DESC NULLS LAST
                    LIMIT 1
                """)).fetchone()
                if row is None:
                    return None
                d = dict(row._mapping)
                if isinstance(d.get("last_seen"), datetime):
                    d["last_seen"] = d["last_seen"].isoformat()
                return d

        return await _run_sync(_query)

    async def get_all_devices(self) -> list:
        def _query():
            with _get_engine().connect() as conn:
                rows = conn.execute(text("""
                    SELECT id, name, device_type, platform, always_present,
                           status, battery_level, last_seen, created_at
                    FROM devices ORDER BY created_at DESC
                """)).fetchall()
                result = []
                for r in rows:
                    row = dict(r._mapping)
                    for k, v in row.items():
                        if isinstance(v, datetime):
                            row[k] = v.isoformat()
                    result.append(row)
                return result

        return await _run_sync(_query)

    async def set_offline(self, device_id: str) -> bool:
        def _update():
            with _get_engine().connect() as conn:
                result = conn.execute(text("""
                    UPDATE devices SET status = 'offline' WHERE id = :id
                """), {"id": device_id})
                conn.commit()
                return result.rowcount > 0

        return await _run_sync(_update)
