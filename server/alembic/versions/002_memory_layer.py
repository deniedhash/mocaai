"""Phase 3 Memory Layer — pgvector embeddings, entities, relationships.

Revision ID: 002_memory_layer
Revises: 001_initial_schema
Create Date: 2026-04-27
"""

from typing import Sequence, Union
from alembic import op

revision: str = "002_memory_layer"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # pgvector extension — must come first
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ------------------------------------------------------------------
    # embeddings — semantic vector store
    # 384 dimensions = all-MiniLM-L6-v2 output size (local, free model)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
            content     TEXT        NOT NULL,
            embedding   vector(384),
            source_type VARCHAR(50),
            source_id   UUID,
            metadata    JSONB       DEFAULT '{}',
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # IVFFlat index for fast approximate cosine search
    # lists=100 is reasonable for moderate data volumes; raise for > 1M rows
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_cosine
        ON embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_source_type
        ON embeddings (source_type)
    """)

    # ------------------------------------------------------------------
    # entities — knowledge graph nodes
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id         UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
            name       VARCHAR(200) NOT NULL,
            type       VARCHAR(50)  NOT NULL,
            attributes JSONB        DEFAULT '{}',
            created_at TIMESTAMPTZ  DEFAULT NOW(),
            updated_at TIMESTAMPTZ  DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_name_lower
        ON entities (LOWER(name))
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_entities_type
        ON entities (type)
    """)

    # ------------------------------------------------------------------
    # relationships — knowledge graph edges
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            id           UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
            entity_a     UUID        REFERENCES entities(id) ON DELETE CASCADE,
            entity_b     UUID        REFERENCES entities(id) ON DELETE CASCADE,
            relationship VARCHAR(100),
            metadata     JSONB       DEFAULT '{}',
            created_at   TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_relationships_entity_a
        ON relationships (entity_a)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_relationships_entity_b
        ON relationships (entity_b)
    """)

    # ------------------------------------------------------------------
    # Auto-update updated_at on entities
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql'
    """)

    op.execute("""
        CREATE TRIGGER update_entities_updated_at
        BEFORE UPDATE ON entities
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_entities_updated_at ON entities")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column")
    op.execute("DROP TABLE IF EXISTS relationships CASCADE")
    op.execute("DROP TABLE IF EXISTS entities CASCADE")
    op.execute("DROP TABLE IF EXISTS embeddings CASCADE")
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
    op.execute("DROP EXTENSION IF EXISTS vector")
