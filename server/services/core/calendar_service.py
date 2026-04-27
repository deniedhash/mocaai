import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from ._db import _get_engine, _run_sync

logger = logging.getLogger("moca.services.calendar")


class MOCACalendarService:
    async def add_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime = None,
        attendees: list = None,
        location: str = None,
        importance: str = "normal",
        notes: str = None,
    ) -> dict:
        event_id = str(uuid.uuid4())
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time and end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        attendees_json = json.dumps(attendees or [])

        def _insert():
            with _get_engine().connect() as conn:
                conn.execute(text("""
                    INSERT INTO events
                        (id, title, start_time, end_time, attendees,
                         location, importance, notes)
                    VALUES
                        (:id, :title, :start, :end, CAST(:attendees AS jsonb),
                         :loc, :importance, :notes)
                """), {"id": event_id, "title": title, "start": start_time,
                       "end": end_time, "attendees": attendees_json,
                       "loc": location, "importance": importance, "notes": notes})
                conn.commit()

        await _run_sync(_insert)
        logger.info("Event added | id=%s title=%r start=%s", event_id, title, start_time)
        return {"event_id": event_id, "title": title, "start_time": start_time.isoformat()}

    async def get_events(self, date: datetime = None, range_days: int = 1) -> list:
        if date is None:
            date = datetime.now(timezone.utc)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        end_date = date + timedelta(days=range_days)

        def _query():
            with _get_engine().connect() as conn:
                rows = conn.execute(text("""
                    SELECT id, title, start_time, end_time, attendees,
                           location, importance, notes, created_at
                    FROM events
                    WHERE start_time >= :start AND start_time < :end
                    ORDER BY start_time ASC
                """), {"start": date, "end": end_date}).fetchall()
                return _serialize_rows(rows)

        return await _run_sync(_query)

    async def get_upcoming(self, hours: int = 24) -> list:
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours)

        def _query():
            with _get_engine().connect() as conn:
                rows = conn.execute(text("""
                    SELECT id, title, start_time, end_time, attendees,
                           location, importance, notes, created_at
                    FROM events
                    WHERE start_time >= :now AND start_time <= :cutoff
                    ORDER BY start_time ASC
                """), {"now": now, "cutoff": cutoff}).fetchall()
                return _serialize_rows(rows)

        return await _run_sync(_query)

    async def update_event(self, event_id: str, updates: dict) -> dict:
        allowed = {"title", "start_time", "end_time", "location", "importance", "notes"}
        fields = {k: v for k, v in updates.items() if k in allowed}
        if not fields:
            return {"event_id": event_id, "updated": False}

        set_clause = ", ".join(f"{k} = :{k}" for k in fields)
        fields["event_id"] = event_id

        def _update():
            with _get_engine().connect() as conn:
                conn.execute(text(f"UPDATE events SET {set_clause} WHERE id = :event_id"),
                             fields)
                conn.commit()

        await _run_sync(_update)
        logger.info("Event updated | id=%s fields=%s", event_id, list(fields.keys()))
        return {"event_id": event_id, "updated": True, "fields": list(fields.keys())}

    async def delete_event(self, event_id: str) -> bool:
        def _delete():
            with _get_engine().connect() as conn:
                result = conn.execute(text("DELETE FROM events WHERE id = :id"),
                                      {"id": event_id})
                conn.commit()
                return result.rowcount > 0

        deleted = await _run_sync(_delete)
        logger.info("Event deleted | id=%s success=%s", event_id, deleted)
        return deleted


def _serialize_rows(rows) -> list:
    result = []
    for r in rows:
        row = dict(r._mapping)
        for k, v in row.items():
            if isinstance(v, datetime):
                row[k] = v.isoformat()
        result.append(row)
    return result
