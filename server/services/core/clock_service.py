import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from ._db import _get_engine, _run_sync

logger = logging.getLogger("moca.services.clock")


class MOCAClockService:
    def __init__(self):
        self._scheduler = None

    def set_scheduler(self, scheduler) -> None:
        self._scheduler = scheduler

    async def set_timer(
        self,
        duration_seconds: int,
        label: str,
        session_id: str,
        context: str = None,
    ) -> dict:
        timer_id = str(uuid.uuid4())
        fire_at = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

        def _insert():
            with _get_engine().connect() as conn:
                conn.execute(text("""
                    INSERT INTO timers
                        (id, type, label, fire_at, duration_seconds, session_id, context, status)
                    VALUES
                        (:id, 'timer', :label, :fire_at, :dur, :sid, :ctx, 'active')
                """), {"id": timer_id, "label": label, "fire_at": fire_at,
                       "dur": duration_seconds, "sid": session_id, "ctx": context})
                conn.commit()

        await _run_sync(_insert)

        if self._scheduler:
            self._scheduler.add_job(
                self._on_timer_fired,
                "date",
                run_date=fire_at,
                args=[timer_id],
                id=timer_id,
                replace_existing=True,
            )

        logger.info("Timer set | id=%s label=%r dur=%ds fire_at=%s",
                    timer_id, label, duration_seconds, fire_at.isoformat())
        return {"timer_id": timer_id, "fire_at": fire_at.isoformat(), "label": label}

    async def set_alarm(
        self,
        fire_at: datetime,
        label: str,
        session_id: str,
        recurrence: dict = None,
        context: str = None,
    ) -> dict:
        alarm_id = str(uuid.uuid4())
        if fire_at.tzinfo is None:
            fire_at = fire_at.replace(tzinfo=timezone.utc)
        rec_json = json.dumps(recurrence) if recurrence else None

        def _insert():
            with _get_engine().connect() as conn:
                conn.execute(text("""
                    INSERT INTO timers
                        (id, type, label, fire_at, session_id, recurrence, context, status)
                    VALUES
                        (:id, 'alarm', :label, :fire_at, :sid,
                         CAST(:rec AS jsonb), :ctx, 'active')
                """), {"id": alarm_id, "label": label, "fire_at": fire_at,
                       "sid": session_id, "rec": rec_json, "ctx": context})
                conn.commit()

        await _run_sync(_insert)

        if self._scheduler:
            self._scheduler.add_job(
                self._on_timer_fired,
                "date",
                run_date=fire_at,
                args=[alarm_id],
                id=alarm_id,
                replace_existing=True,
            )

        logger.info("Alarm set | id=%s label=%r fire_at=%s", alarm_id, label, fire_at.isoformat())
        return {"alarm_id": alarm_id, "fire_at": fire_at.isoformat(), "label": label}

    async def set_reminder(
        self,
        fire_at: datetime,
        task: str,
        session_id: str,
    ) -> dict:
        reminder_id = str(uuid.uuid4())
        if fire_at.tzinfo is None:
            fire_at = fire_at.replace(tzinfo=timezone.utc)

        def _insert():
            with _get_engine().connect() as conn:
                conn.execute(text("""
                    INSERT INTO timers
                        (id, type, label, fire_at, session_id, status)
                    VALUES
                        (:id, 'reminder', :task, :fire_at, :sid, 'active')
                """), {"id": reminder_id, "task": task, "fire_at": fire_at, "sid": session_id})
                conn.commit()

        await _run_sync(_insert)

        if self._scheduler:
            self._scheduler.add_job(
                self._on_timer_fired,
                "date",
                run_date=fire_at,
                args=[reminder_id],
                id=reminder_id,
                replace_existing=True,
            )

        logger.info("Reminder set | id=%s task=%r fire_at=%s", reminder_id, task, fire_at.isoformat())
        return {"reminder_id": reminder_id, "fire_at": fire_at.isoformat(), "task": task}

    async def get_active_timers(self) -> list:
        def _query():
            with _get_engine().connect() as conn:
                rows = conn.execute(text("""
                    SELECT id, type, label, fire_at, duration_seconds,
                           session_id, status, created_at
                    FROM timers
                    WHERE status = 'active'
                    ORDER BY fire_at ASC
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

    async def cancel_timer(self, timer_id: str) -> bool:
        if self._scheduler:
            try:
                self._scheduler.remove_job(timer_id)
            except Exception:
                pass

        def _update():
            with _get_engine().connect() as conn:
                result = conn.execute(text("""
                    UPDATE timers SET status = 'cancelled'
                    WHERE id = :id AND status = 'active'
                """), {"id": timer_id})
                conn.commit()
                return result.rowcount > 0

        return await _run_sync(_update)

    async def _on_timer_fired(self, timer_id: str):
        logger.info("Timer fired | id=%s", timer_id)

        def _update():
            with _get_engine().connect() as conn:
                conn.execute(text("""
                    UPDATE timers SET status = 'fired' WHERE id = :id
                """), {"id": timer_id})
                conn.commit()

        try:
            await _run_sync(_update)
        except Exception as exc:
            logger.warning("Failed to mark timer fired | id=%s err=%s", timer_id, exc)

    async def restore_active_timers(self):
        """Re-schedule active timers after a server restart."""
        timers = await self.get_active_timers()
        now = datetime.now(timezone.utc)
        restored = 0
        for t in timers:
            fire_at_raw = t["fire_at"]
            if isinstance(fire_at_raw, str):
                fire_at = datetime.fromisoformat(fire_at_raw)
            else:
                fire_at = fire_at_raw
            if fire_at.tzinfo is None:
                fire_at = fire_at.replace(tzinfo=timezone.utc)
            if fire_at > now and self._scheduler:
                tid = str(t["id"])
                self._scheduler.add_job(
                    self._on_timer_fired,
                    "date",
                    run_date=fire_at,
                    args=[tid],
                    id=tid,
                    replace_existing=True,
                )
                restored += 1
        logger.info("Restored %d active timer(s) from DB", restored)
