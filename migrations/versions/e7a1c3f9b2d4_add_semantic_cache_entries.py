"""Add semantic cache entries (pgvector)

Revision ID: e7a1c3f9b2d4
Revises: d4b11a8426a8
Create Date: 2026-10-27 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7a1c3f9b2d4"
down_revision: Union[str, None] = "d4b11a8426a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE semantic_cache_entries (
            id UUID PRIMARY KEY,
            claim_text TEXT NOT NULL,
            claim_hash VARCHAR(64) NOT NULL,
            language VARCHAR(32) NOT NULL,
            params_hash VARCHAR(64) NOT NULL,
            embedding vector(768) NOT NULL,
            source_analysis_id UUID NOT NULL REFERENCES analysis(id) ON DELETE CASCADE,
            veracity_score DOUBLE PRECISION NOT NULL,
            analysis_text TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            hit_count INTEGER NOT NULL DEFAULT 0,
            invalidated BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_semantic_cache_embedding ON semantic_cache_entries " "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX ix_semantic_cache_lookup ON semantic_cache_entries (language, params_hash, expires_at)")
    op.execute("CREATE INDEX ix_semantic_cache_exact ON semantic_cache_entries (claim_hash, language, params_hash)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS semantic_cache_entries")
