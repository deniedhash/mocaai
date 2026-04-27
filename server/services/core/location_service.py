import logging
import math
import uuid
from datetime import datetime

from sqlalchemy import text

from ._db import _get_engine, _run_sync

logger = logging.getLogger("moca.services.location")


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


class MOCALocationService:
    async def update_location(
        self,
        latitude: float,
        longitude: float,
        device_id: str,
        accuracy: float = None,
    ) -> dict:
        geofences = await self._get_geofences()
        location_type = "unknown"
        zone_name = None

        for gf in geofences:
            dist = _haversine_m(latitude, longitude, gf["latitude"], gf["longitude"])
            if dist <= gf["radius_meters"]:
                location_type = gf["zone_type"]
                zone_name = gf["name"]
                break

        entry_id = str(uuid.uuid4())

        def _insert():
            with _get_engine().connect() as conn:
                conn.execute(text("""
                    INSERT INTO location_history
                        (id, latitude, longitude, device_id, location_type,
                         zone_name, accuracy)
                    VALUES
                        (:id, :lat, :lon, :did, :ltype, :zname, :acc)
                """), {"id": entry_id, "lat": latitude, "lon": longitude,
                       "did": device_id, "ltype": location_type,
                       "zname": zone_name, "acc": accuracy})
                conn.commit()

        await _run_sync(_insert)
        logger.debug("Location updated | device=%s type=%s zone=%s", device_id, location_type, zone_name)
        return {"entry_id": entry_id, "location_type": location_type, "zone_name": zone_name}

    async def add_geofence(
        self,
        name: str,
        latitude: float,
        longitude: float,
        radius_meters: float,
        zone_type: str,
    ) -> dict:
        geofence_id = str(uuid.uuid4())

        def _insert():
            with _get_engine().connect() as conn:
                conn.execute(text("""
                    INSERT INTO geofences (id, name, latitude, longitude, radius_meters, zone_type)
                    VALUES (:id, :name, :lat, :lon, :radius, :ztype)
                """), {"id": geofence_id, "name": name, "lat": latitude,
                       "lon": longitude, "radius": radius_meters, "ztype": zone_type})
                conn.commit()

        await _run_sync(_insert)
        logger.info("Geofence added | id=%s name=%r type=%s", geofence_id, name, zone_type)
        return {"geofence_id": geofence_id, "name": name, "zone_type": zone_type}

    async def get_current_location(self) -> dict:
        def _query():
            with _get_engine().connect() as conn:
                row = conn.execute(text("""
                    SELECT id, latitude, longitude, device_id, location_type,
                           zone_name, accuracy, created_at
                    FROM location_history
                    ORDER BY created_at DESC NULLS LAST
                    LIMIT 1
                """)).fetchone()
                if row is None:
                    return {}
                d = dict(row._mapping)
                if isinstance(d.get("created_at"), datetime):
                    d["created_at"] = d["created_at"].isoformat()
                return d

        return await _run_sync(_query)

    async def get_location_type(self) -> str:
        loc = await self.get_current_location()
        return loc.get("location_type", "unknown")

    async def _get_geofences(self) -> list:
        def _query():
            with _get_engine().connect() as conn:
                rows = conn.execute(text("""
                    SELECT name, latitude, longitude, radius_meters, zone_type
                    FROM geofences
                """)).fetchall()
                return [dict(r._mapping) for r in rows]

        return await _run_sync(_query)
