"""Phase 4 Core Services Layer — timers, notifications, events, geofences,
location_history, devices.

Revision ID: 003_services_layer
Revises: 002_memory_layer
Create Date: 2026-04-27
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_services_layer"
down_revision: Union[str, None] = "002_memory_layer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS timers (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type             VARCHAR(20)  NOT NULL,
            label            VARCHAR(200),
            fire_at          TIMESTAMP    NOT NULL,
            duration_seconds INTEGER,
            session_id       VARCHAR(100),
            context          TEXT,
            recurrence       JSONB,
            status           VARCHAR(20)  DEFAULT 'active',
            created_at       TIMESTAMP    DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_timers_status  ON timers (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_timers_fire_at ON timers (fire_at)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            message      TEXT        NOT NULL,
            priority     VARCHAR(20) DEFAULT 'normal',
            session_id   VARCHAR(100),
            devices      VARCHAR(50) DEFAULT 'best',
            status       VARCHAR(20) DEFAULT 'pending',
            delivered_at TIMESTAMP,
            created_at   TIMESTAMP   DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_session ON notifications (session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_status  ON notifications (status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name           VARCHAR(100) NOT NULL,
            device_type    VARCHAR(50),
            platform       VARCHAR(50),
            always_present BOOLEAN      DEFAULT FALSE,
            status         VARCHAR(20)  DEFAULT 'offline',
            battery_level  INTEGER,
            last_seen      TIMESTAMP,
            created_at     TIMESTAMP    DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title       VARCHAR(300) NOT NULL,
            start_time  TIMESTAMP    NOT NULL,
            end_time    TIMESTAMP,
            attendees   JSONB        DEFAULT '[]',
            location    VARCHAR(300),
            importance  VARCHAR(20)  DEFAULT 'normal',
            notes       TEXT,
            created_at  TIMESTAMP    DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_start_time ON events (start_time)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS geofences (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name           VARCHAR(100) NOT NULL,
            latitude       FLOAT        NOT NULL,
            longitude      FLOAT        NOT NULL,
            radius_meters  FLOAT        NOT NULL,
            zone_type      VARCHAR(50),
            created_at     TIMESTAMP    DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS location_history (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            latitude      FLOAT        NOT NULL,
            longitude     FLOAT        NOT NULL,
            device_id     UUID,
            location_type VARCHAR(50),
            zone_name     VARCHAR(100),
            accuracy      FLOAT,
            created_at    TIMESTAMP    DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_location_history_created ON location_history (created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS location_history")
    op.execute("DROP TABLE IF EXISTS geofences")
    op.execute("DROP TABLE IF EXISTS events")
    op.execute("DROP TABLE IF EXISTS devices")
    op.execute("DROP TABLE IF EXISTS notifications")
    op.execute("DROP TABLE IF EXISTS timers")
