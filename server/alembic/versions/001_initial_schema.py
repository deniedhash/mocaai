"""Initial MOCA schema — conversations, memories, users tables.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-04-27
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # conversations — every interaction turn is stored here
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          SERIAL PRIMARY KEY,
            session_id  VARCHAR(255) NOT NULL,
            role        VARCHAR(50)  NOT NULL,
            content     TEXT         NOT NULL,
            agent       VARCHAR(100),
            metadata    JSONB        DEFAULT '{}',
            created_at  TIMESTAMPTZ  DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_session_id
        ON conversations (session_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_created_at
        ON conversations (created_at DESC)
    """)

    # ------------------------------------------------------------------
    # memories — distilled long-term facts and episodic summaries
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id               SERIAL PRIMARY KEY,
            type             VARCHAR(100) NOT NULL DEFAULT 'episodic',
            content          TEXT         NOT NULL,
            importance_score FLOAT        DEFAULT 0.5,
            metadata         JSONB        DEFAULT '{}',
            created_at       TIMESTAMPTZ  DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_type
        ON memories (type)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_importance
        ON memories (importance_score DESC)
    """)

    # ------------------------------------------------------------------
    # users — user profiles and preferences
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          SERIAL PRIMARY KEY,
            name        VARCHAR(255),
            preferences JSONB       DEFAULT '{}',
            timezone    VARCHAR(100) DEFAULT 'UTC',
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS memories CASCADE")
    op.execute("DROP TABLE IF EXISTS conversations CASCADE")
