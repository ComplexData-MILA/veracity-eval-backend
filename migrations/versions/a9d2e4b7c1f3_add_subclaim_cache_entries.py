"""Add subclaim cache entries (pgvector)

One entry per atomic subclaim, pointing at the search that gathered its evidence, so a different claim
sharing that subclaim can reuse the search results.

Revision ID: a9d2e4b7c1f3
Revises: f3c8a1d5e902
Create Date: 2026-11-16 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9d2e4b7c1f3"
down_revision: Union[str, None] = "f3c8a1d5e902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute(
        """
        CREATE TABLE subclaim_cache_entries (
            id UUID PRIMARY KEY,
            subclaim_text TEXT NOT NULL,
            subclaim_hash VARCHAR(64) NOT NULL,
            language VARCHAR(32) NOT NULL,
            params_hash VARCHAR(64) NOT NULL,
            embedding vector(768) NOT NULL,
            search_id UUID NOT NULL REFERENCES searches(id) ON DELETE CASCADE,
            label VARCHAR(16),
            expires_at TIMESTAMPTZ NOT NULL,
            hit_count INTEGER NOT NULL DEFAULT 0,
            invalidated BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_subclaim_cache_embedding ON subclaim_cache_entries USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX ix_subclaim_cache_lookup ON subclaim_cache_entries (language, params_hash, created_at)")
    op.execute("CREATE INDEX ix_subclaim_cache_exact ON subclaim_cache_entries (subclaim_hash, language, params_hash)")
    op.execute("CREATE INDEX ix_subclaim_cache_created_at ON subclaim_cache_entries (created_at)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS subclaim_cache_entries")
