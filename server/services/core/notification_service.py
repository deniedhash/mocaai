import logging
import uuid
from datetime import datetime

from sqlalchemy import text

from ._db import _get_engine, _run_sync

logger = logging.getLogger("moca.services.notification")


class MOCANotificationService:
    async def notify(
        self,
        message: str,
        priority: str,
        session_id: str,
        devices: str = "best",
        context: dict = None,
    ) -> dict:
        notification_id = str(uuid.uuid4())
        logger.info(
            "Notification | id=%s priority=%s session=%s msg=%r",
            notification_id, priority, session_id, message[:80],
        )

        def _insert():
            with _get_engine().connect() as conn:
                conn.execute(text("""
                    INSERT INTO notifications
                        (id, message, priority, session_id, devices, status)
                    VALUES
                        (:id, :msg, :priority, :sid, :devices, 'pending')
                """), {"id": notification_id, "msg": message, "priority": priority,
                       "sid": session_id, "devices": devices})
                conn.commit()

        await _run_sync(_insert)
        return {"notification_id": notification_id, "status": "pending", "priority": priority}

    async def get_pending(self, session_id: str) -> list:
        def _query():
            with _get_engine().connect() as conn:
                rows = conn.execute(text("""
                    SELECT id, message, priority, devices, created_at
                    FROM notifications
                    WHERE session_id = :sid AND status = 'pending'
                    ORDER BY created_at ASC
                """), {"sid": session_id}).fetchall()
                result = []
                for r in rows:
                    row = dict(r._mapping)
                    for k, v in row.items():
                        if isinstance(v, datetime):
                            row[k] = v.isoformat()
                    result.append(row)
                return result

        return await _run_sync(_query)

    async def mark_delivered(self, notification_id: str) -> bool:
        def _update():
            with _get_engine().connect() as conn:
                result = conn.execute(text("""
                    UPDATE notifications
                    SET status = 'delivered', delivered_at = NOW()
                    WHERE id = :id AND status = 'pending'
                """), {"id": notification_id})
                conn.commit()
                return result.rowcount > 0

        return await _run_sync(_update)
