"""Add failed to claim status

Revision ID: d4b11a8426a8
Revises: 345aea7c066f
Create Date: 2026-09-14 11:01:07.820588

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4b11a8426a8"
down_revision: Union[str, None] = "345aea7c066f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE claim_status ADD VALUE IF NOT EXISTS 'failed'")


def downgrade():
    raise NotImplementedError("Removing 'failed' requires rebuilding the PostgreSQL enum.")
