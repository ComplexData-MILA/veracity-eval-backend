"""Semantic cache size limit and per-path freshness

Revision ID: f3c8a1d5e902
Revises: e7a1c3f9b2d4
Create Date: 2026-11-09 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3c8a1d5e902"
down_revision: Union[str, None] = "e7a1c3f9b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Freshness and eviction both go by age
    op.execute("CREATE INDEX ix_semantic_cache_created ON semantic_cache_entries (created_at)")
    # Superseded entries are now deleted on write; clear the ones flagged before
    op.execute("DELETE FROM semantic_cache_entries WHERE invalidated")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_semantic_cache_created")
